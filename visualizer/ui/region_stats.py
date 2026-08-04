"""The Advanced section: statistics for the weather inside a drawn box."""

from qgis.core import (
    QgsCoordinateTransform,
    QgsCsException,
    QgsGeometry,
    QgsProject,
    QgsRectangle,
    QgsWkbTypes,
)
from qgis.gui import QgsRubberBand
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...config_wizard.ui.map_tools import RectangleMapTool
from ...config_wizard.ui.ui_kit import COLOR_MUTED
from ..core import mesh_stats
from ..styling.mesh_styler import color_ramp_for
from .color_palette import MONO_FAMILY, WEATHER_COLOR, WEATHER_TINT, WEATHER_TINT_BORDER
from .histogram import Histogram
from .readout import StatCard, format_value

# Recompute debounced to avoid thrashing the mesh layer with repeated queries while the user drags the box around.
_RECOMPUTE_MS = 250

_BAND_COLOR = QColor(37, 99, 235)
_BAND_FILL = QColor(37, 99, 235, 28)

_DRAW_TEXT = "Draw box on map"
_FINISH_TEXT = "Finish drawing"

_HINT_IDLE = "Draw a box over the weather to summarise the values inside it."
_HINT_NO_WEATHER = "Load a weather NetCDF to summarise a region."
_HINT_NO_VARIABLE = "Tick a layer to see its statistics inside the box."
_HINT_DRAWING = "Drag a box on the map. Double-click or press Enter to confirm, Escape to cancel."
_HINT_TOO_MANY = "Box covers {cells:,} grid cells — the limit is {limit:,}. Draw a smaller box."
_HINT_MESH_TOO_LARGE = (
    "Weather grid has {cells:,} cells; region statistics supports up to {limit:,}."
)

_REGION_QSS = f"""
QLabel#Hint {{ font-size: 10px; color: {COLOR_MUTED}; }}
QLabel#HistTick {{ font-family: {MONO_FAMILY}; font-size: 10px; color: {COLOR_MUTED}; }}
"""


class _VariableStatsBlock(QWidget):
    """One variable's numbers above its distribution."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._card = StatCard("", WEATHER_COLOR, WEATHER_TINT, WEATHER_TINT_BORDER)
        layout.addWidget(self._card)

        self._histogram = Histogram()
        layout.addWidget(self._histogram)

        ticks = QHBoxLayout()
        ticks.setContentsMargins(2, 0, 2, 0)
        self._low_label = QLabel()
        self._low_label.setObjectName("HistTick")
        self._high_label = QLabel()
        self._high_label.setObjectName("HistTick")
        self._high_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ticks.addWidget(self._low_label)
        ticks.addStretch()
        ticks.addWidget(self._high_label)
        layout.addLayout(ticks)

    def show_stats(self, variable, stats):
        is_vector = variable["kind"] == "vector"
        title = f"{variable['name']} · magnitude" if is_vector else variable["name"]
        self._card.set_title(title)

        if not stats.is_supported:
            self._show_message(("Data", "on edges — unsupported"))
            return
        if stats.is_over_limit:
            self._show_message(("Cells", f"{stats.total_in_box:,} — over limit"))
            return
        if not stats.has_values:
            self._show_message(("Cells", "0"))
            return

        unit = variable.get("unit", "") or ""

        cells = f"{stats.count:,}"
        if stats.total_in_box > stats.count:
            cells = f"{stats.count:,} of {stats.total_in_box:,}"
        rows = [
            ("Cells", cells),
            ("Min", format_value(stats.minimum, unit)),
            ("Max", format_value(stats.maximum, unit)),
            ("Mean", format_value(stats.mean, unit)),
            ("Median", format_value(stats.median, unit)),
            ("Std dev", format_value(stats.std_dev, unit)),
        ]
        self._card.set_rows(rows)

        counts, edges = mesh_stats.bin_values(stats.values, stats.minimum, stats.maximum)
        ramp, _ = color_ramp_for(variable["name"])
        self._histogram.set_data(counts, edges, ramp, self._ramp_range(variable, stats))
        self._histogram.setVisible(True)
        self._low_label.setText(f"{stats.minimum:.4g}")
        self._high_label.setText(f"{stats.maximum:.4g}")

    def _ramp_range(self, variable, stats):
        """The range the map's own shader uses, so the bar colours agree with it."""
        vmin = variable.get("vmin")
        vmax = variable.get("vmax")
        if vmin is None or vmax is None or vmax <= vmin:
            return (stats.minimum, stats.maximum)
        return (vmin, vmax)

    def _show_message(self, row):
        self._card.set_rows([row])
        self._histogram.clear()
        self._histogram.setVisible(False)
        self._low_label.clear()
        self._high_label.clear()


class RegionStatsSection(QWidget):
    """Draw a box over the weather mesh and summarise the ticked variables in it."""

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self._iface = iface

        self._mesh_layer = None
        self._mesh_loader = None
        self._variables = []
        self._frame_index = None

        self._geometry = None
        self._selections = {}
        self._rect_layer = None  # canonical box, in the mesh layer's CRS
        self._band = None
        self._map_tool = None
        self._previous_map_tool = None
        self._is_drawing = False
        self._is_collapsed = True
        self._is_crs_watched = False

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._recompute)

        self._build_ui()
        self._refresh_controls()

    # UI

    def _build_ui(self):
        self.setStyleSheet(_REGION_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self._draw_btn = QPushButton(_DRAW_TEXT)
        self._draw_btn.clicked.connect(self._on_draw_clicked)
        buttons.addWidget(self._draw_btn, 1)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._clear_region)
        buttons.addWidget(self._clear_btn)
        layout.addLayout(buttons)

        self._hint = QLabel(_HINT_NO_WEATHER)
        self._hint.setObjectName("Hint")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        self._blocks = [_VariableStatsBlock(), _VariableStatsBlock()]
        for block in self._blocks:
            block.setVisible(False)
            layout.addWidget(block)

    def _refresh_controls(self):
        has_weather = self._mesh_layer is not None
        self._draw_btn.setEnabled(has_weather)
        self._clear_btn.setEnabled(has_weather and self._rect_layer is not None)
        self._draw_btn.setText(_FINISH_TEXT if self._is_drawing else _DRAW_TEXT)

    def _set_hint(self, text):
        self._hint.setText(text)

    def _hide_blocks(self):
        for block in self._blocks:
            block.setVisible(False)

    # panel-facing setters

    def set_source(self, mesh_layer, mesh_loader):
        """A weather file was loaded, or the loaded one went away."""
        self._finish_draw()
        self._drop_band()
        self._mesh_layer = mesh_layer
        self._mesh_loader = mesh_loader
        self._geometry = None
        self._selections = {}
        self._rect_layer = None
        self._variables = []
        self._frame_index = None
        self._hide_blocks()
        self._watch_canvas_crs(mesh_layer is not None)
        self._set_hint(_HINT_IDLE if mesh_layer is not None else _HINT_NO_WEATHER)
        self._refresh_controls()

    def set_variables(self, variables):
        """The ticked variable dicts, scalar first — same source as the legend."""
        self._variables = list(variables)[: len(self._blocks)]
        self._schedule_recompute()

    def set_frame(self, frame_index):
        self._frame_index = frame_index
        self._schedule_recompute()

    def set_collapsed(self, is_collapsed):
        """Nothing is computed while Advanced is shut."""
        self._is_collapsed = is_collapsed
        if not is_collapsed:
            self._recompute()

    def teardown(self):
        self._timer.stop()
        self._drop_map_tool()
        self._drop_band()
        self._watch_canvas_crs(False)
        self._geometry = None
        self._selections = {}
        self._rect_layer = None
        self._mesh_layer = None
        self._mesh_loader = None
        self._variables = []
        self._frame_index = None
        self._hide_blocks()
        self._set_hint(_HINT_NO_WEATHER)
        self._refresh_controls()

    # drawing

    def _on_draw_clicked(self):
        if self._is_drawing:
            self._finish_draw()
        else:
            self._start_draw()

    def _start_draw(self):
        if self._mesh_layer is None:
            return
        canvas = self._iface.mapCanvas()
        self._previous_map_tool = canvas.mapTool()
        map_tool = self._ensure_map_tool()
        self._is_drawing = True
        canvas.setMapTool(map_tool)

        if self._rect_layer is not None:
            canvas_rect = self._to_canvas_rect(self._rect_layer)
            if canvas_rect is not None:
                map_tool.set_rectangle(canvas_rect)
        self._set_hint(_HINT_DRAWING)
        self._refresh_controls()

    def _ensure_map_tool(self):
        """One tool for the whole section's life."""
        if self._map_tool is None:
            self._map_tool = RectangleMapTool(self._iface.mapCanvas())
            self._map_tool.rectangleConfirmed.connect(self._on_rect_confirmed)
            self._map_tool.cancelled.connect(self._finish_draw)
            self._map_tool.deactivated.connect(self._on_tool_deactivated)
        return self._map_tool

    def _finish_draw(self):
        if not self._is_drawing:
            return
        canvas = self._iface.mapCanvas()

        if self._previous_map_tool is not None:
            canvas.setMapTool(self._previous_map_tool)
        else:
            canvas.unsetMapTool(self._map_tool)
        self._previous_map_tool = None

    def _on_tool_deactivated(self):
        """Also fires when the user picks another tool from the QGIS toolbar."""
        self._is_drawing = False
        self._previous_map_tool = None
        if self._hint.text() == _HINT_DRAWING:
            self._set_hint(_HINT_IDLE)
        self._refresh_controls()

    def _drop_map_tool(self):
        if self._map_tool is None:
            return
        self._finish_draw()
        self._iface.mapCanvas().unsetMapTool(self._map_tool)
        self._map_tool.detach()  # its own rubber bands outlive deactivate()
        self._map_tool = None

    def _on_rect_confirmed(self, canvas_rect):
        rect_layer = self._to_layer_rect(canvas_rect)
        self._finish_draw()
        if rect_layer is None:
            self._set_hint("Cannot project the box onto the weather grid.")
            return
        self._rect_layer = rect_layer
        self._selections = {}
        self._show_band()
        self._refresh_controls()
        self._recompute()

    def _clear_region(self):
        self._finish_draw()
        self._drop_band()
        self._rect_layer = None
        self._selections = {}
        self._hide_blocks()
        self._set_hint(_HINT_IDLE)
        self._refresh_controls()

    # rubber band

    def _show_band(self):
        if self._rect_layer is None or self._mesh_layer is None:
            return
        canvas_rect = self._to_canvas_rect(self._rect_layer)
        if canvas_rect is None:
            return
        if self._band is None:
            self._band = QgsRubberBand(self._iface.mapCanvas(), QgsWkbTypes.PolygonGeometry)
            self._band.setColor(_BAND_COLOR)
            self._band.setFillColor(_BAND_FILL)
            self._band.setWidth(2)
            self._band.setLineStyle(Qt.DashLine)
        self._band.setToGeometry(QgsGeometry.fromRect(canvas_rect), None)

    def _drop_band(self):
        if self._band is None:
            return
        self._band.reset(QgsWkbTypes.PolygonGeometry)

        scene = self._band.scene()
        if scene is not None:
            scene.removeItem(self._band)
        self._band = None

    def _watch_canvas_crs(self, should_watch):
        """Keep the box over the same ground when the project CRS changes."""
        canvas = self._iface.mapCanvas()
        if should_watch and not self._is_crs_watched:
            canvas.destinationCrsChanged.connect(self._show_band)
            self._is_crs_watched = True
        elif not should_watch and self._is_crs_watched:
            canvas.destinationCrsChanged.disconnect(self._show_band)
            self._is_crs_watched = False

    # CRS

    def _to_layer_rect(self, canvas_rect):
        """The confirmed box arrives in canvas CRS; the mesh is indexed in its own."""
        return self._transformed(canvas_rect, to_layer=True)

    def _to_canvas_rect(self, rect_layer):
        return self._transformed(rect_layer, to_layer=False)

    def _transformed(self, rect, to_layer):
        if self._mesh_layer is None:
            return None
        canvas_crs = self._iface.mapCanvas().mapSettings().destinationCrs()
        layer_crs = self._mesh_layer.crs()
        if canvas_crs == layer_crs:
            return QgsRectangle(rect)
        source, destination = (canvas_crs, layer_crs) if to_layer else (layer_crs, canvas_crs)
        try:
            transform = QgsCoordinateTransform(source, destination, QgsProject.instance())
            return transform.transformBoundingBox(rect)
        except QgsCsException:
            return None

    # statistics

    def _schedule_recompute(self):
        if self._is_collapsed:
            return
        if not self._timer.isActive():
            self._timer.start(_RECOMPUTE_MS)

    def _recompute(self):
        if self._is_collapsed or self._mesh_layer is None:
            return
        if self._rect_layer is None:
            self._hide_blocks()
            self._set_hint(_HINT_IDLE)
            return
        if not self._variables:
            self._hide_blocks()
            self._set_hint(_HINT_NO_VARIABLE)
            return
        if self._frame_index is None:
            self._hide_blocks()
            self._set_hint("No weather frame at the current time.")
            return

        geometry = self._ensure_geometry()
        if geometry is None:
            self._hide_blocks()
            return
        if geometry.is_too_large:
            self._hide_blocks()
            self._set_hint(
                _HINT_MESH_TOO_LARGE.format(
                    cells=geometry.element_count, limit=mesh_stats.MAX_ELEMENTS
                )
            )
            return

        # Every selection first: a scalar on vertices and a vector on faces are
        # counted separately, and one of them being over refuses the whole box.
        selections = [self._selection_for(geometry, variable) for variable in self._variables]
        over_limit = [selection for selection in selections if selection.is_over_limit]
        if over_limit:
            self._hide_blocks()
            self._set_hint(
                _HINT_TOO_MANY.format(
                    cells=max(len(selection.indices) for selection in over_limit),
                    limit=mesh_stats.MAX_REGION_CELLS,
                )
            )
            return

        for block, variable, selection in zip(
            self._blocks, self._variables, selections, strict=False
        ):
            stats = mesh_stats.region_stats(
                self._mesh_layer, variable, self._frame_index, selection
            )
            block.show_stats(variable, stats)
            block.setVisible(True)
        for block in self._blocks[len(self._variables) :]:
            block.setVisible(False)
        # After the loop: the hint reads the selections it has just built.
        self._set_hint(self._region_hint())

    def _region_hint(self):
        """Say why a box can be legal yet still cover nothing."""
        if not self._rect_layer.intersects(self._mesh_layer.extent()):
            return "Box covers no mesh cells — it falls outside the weather grid."
        supported = [selection for selection in self._selections.values() if selection.is_supported]
        if supported and all(selection.is_empty for selection in supported):
            return "Box is smaller than one grid cell — draw a larger box."
        return _HINT_IDLE

    def _selection_for(self, geometry, variable):
        data_type = mesh_stats.data_type_of(self._mesh_layer, variable)
        selection = self._selections.get(data_type)
        if selection is None:
            selection = mesh_stats.RegionSelection(geometry, data_type, self._rect_layer)
            self._selections[data_type] = selection
        return selection

    def _ensure_geometry(self):
        """Copy the mesh frame out once per loaded file, on the first box only."""
        if self._geometry is not None or self._mesh_layer is None:
            return self._geometry
        self._set_hint("Indexing mesh…")
        self._hint.repaint()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            geometry = mesh_stats.MeshGeometry(self._mesh_layer)
        finally:
            QApplication.restoreOverrideCursor()
        if geometry.is_empty:
            self._set_hint("The weather mesh has no cells to summarise.")
            return None
        self._geometry = geometry
        return geometry
