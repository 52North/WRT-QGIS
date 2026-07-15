from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    QgsLineSymbol,
    QgsMarkerLineSymbolLayer,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsProperty,
    QgsRuleBasedRenderer,
    QgsSimpleLineSymbolLayer,
    QgsSvgMarkerSymbolLayer,
    QgsSymbolLayer,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsUnitTypes,
    QgsVectorLayerSimpleLabeling,
)

ARROW_COLOR = QColor(70, 130, 180)
SAILBOAT_FILL = QColor(255, 165, 0)
SAILBOAT_STROKE = QColor(180, 100, 0)
BOAT_FILL = QColor(220, 50, 50)
BOAT_STROKE = QColor(140, 20, 20)

SOURCE_FLAG_FILL = QColor(34, 197, 94)
SOURCE_FLAG_STROKE = QColor(21, 128, 61)
DEST_FLAG_FILL = QColor(239, 68, 68)
DEST_FLAG_STROKE = QColor(153, 27, 27)


def style_route_line(layer, color=ARROW_COLOR):
    line = QgsSimpleLineSymbolLayer(color)
    line.setWidth(0.6)
    line.setWidthUnit(QgsUnitTypes.RenderMillimeters)

    dot_sub_symbol = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "2.2",
        "size_unit": "MM",
        "color": color.name(),
        "outline_style": "no",
    })

    dots = QgsMarkerLineSymbolLayer(True)
    dots.setPlacement(QgsMarkerLineSymbolLayer.Vertex)
    dots.setSubSymbol(dot_sub_symbol)

    symbol = QgsLineSymbol()
    symbol.changeSymbolLayer(0, line)
    symbol.appendSymbolLayer(dots)
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()


def _make_svg_marker(svg_path, size_mm, fill, stroke, angle_expression=None):
    svg_layer = QgsSvgMarkerSymbolLayer(svg_path, size_mm, 0)
    svg_layer.setSizeUnit(QgsUnitTypes.RenderMillimeters)
    svg_layer.setFillColor(fill)
    svg_layer.setStrokeColor(stroke)
    if angle_expression is not None:
        svg_layer.setDataDefinedProperty(
            QgsSymbolLayer.PropertyAngle,
            QgsProperty.fromExpression(angle_expression),
        )

    symbol = QgsMarkerSymbol()
    symbol.changeSymbolLayer(0, svg_layer)
    return symbol


def style_sailboat_points(layer, svg_path, size_mm=5.0, fill=SAILBOAT_FILL, stroke=SAILBOAT_STROKE):
    layer.renderer().setSymbol(_make_svg_marker(svg_path, size_mm, fill, stroke, '"bearing" + 90'))
    layer.triggerRepaint()


def style_boat_marker(layer, svg_path, size_mm=9.5, fill=BOAT_FILL, stroke=BOAT_STROKE):
    layer.renderer().setSymbol(_make_svg_marker(svg_path, size_mm, fill, stroke, '"bearing" + 90'))
    layer.triggerRepaint()


def style_markers_layer(layer, svg_path, size_mm=14.0):
    def _rule(label, expr, fill, stroke):
        sym = _make_svg_marker(svg_path, size_mm, fill, stroke)
        rule = QgsRuleBasedRenderer.Rule(sym)
        rule.setFilterExpression(expr)
        rule.setLabel(label)
        return rule

    root = QgsRuleBasedRenderer.Rule(None)
    root.appendChild(_rule("Source",      "\"role\" = 'source'",      SOURCE_FLAG_FILL, SOURCE_FLAG_STROKE))
    root.appendChild(_rule("Destination", "\"role\" = 'destination'", DEST_FLAG_FILL,   DEST_FLAG_STROKE))
    layer.setRenderer(QgsRuleBasedRenderer(root))

    fmt = QgsTextFormat()
    font = QFont("Sans Serif", 9)
    font.setBold(True)
    fmt.setFont(font)
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(1.0)
    buf.setColor(QColor(255, 255, 255))
    fmt.setBuffer(buf)

    pal = QgsPalLayerSettings()
    pal.fieldName = "label"
    pal.enabled = True
    pal.setFormat(fmt)
    pal.placement = QgsPalLayerSettings.AroundPoint
    pal.dist = size_mm * 0.75
    pal.distUnits = QgsUnitTypes.RenderMillimeters
    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()
