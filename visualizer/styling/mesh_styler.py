import re

from qgis.core import (
    QgsColorRampShader,
    QgsMeshRendererVectorWindBarbSettings,
    QgsRectangle,
    QgsStyle,
)
from qgis.PyQt.QtGui import QColor

VECTOR_COLOR = QColor(31, 58, 95)
VECTOR_LINE_WIDTH = 0.8

# Modifying this value will change the spacing of arrows and streamlines on the map.
VECTOR_GRID_PX = 24

# Modifying this value will change the spacing of wind barbs on the map.
BARB_GRID_PX = 48
# Reduced barb shaft lenghth to avoid overlap with the arrowhead on the map.
BARB_SHAFT_MM = 7.0

# Barbs are the meteorological convention for wind, but not for currents.
_WIND_RE = re.compile(r"wind", re.I)

_RAMP_CLASSES = 32

NO_GROUP = -1  # No active group, renders nothing on that axis.

# Ramp per variable family, matched against the display name.
# (ramp name, invert) — inverted RdYlBu reads cold-blue to hot-red.
_RAMP_RULES = [
    (re.compile(r"wave height|hm0", re.I), ("BuYl", False)),
    (re.compile(r"wave period|tp\b", re.I), ("Purples", False)),
    (re.compile(r"direction", re.I), ("Spectral", False)),
    (re.compile(r"temperature", re.I), ("RdYlBu", True)),
    (re.compile(r"salinity", re.I), ("Greens", False)),
    (re.compile(r"pressure", re.I), ("Spectral", True)),
    (re.compile(r"velocity|current", re.I), ("Plasma", False)),
    (re.compile(r"wind", re.I), ("Viridis", False)),
]
_DEFAULT_RAMP = ("Viridis", False)


def is_wind_variable(name):
    """Wind gets barbs, everything else arrows — asked by the card label too."""
    return bool(_WIND_RE.search(name))


def ramp_for(name):
    for pattern, ramp in _RAMP_RULES:
        if pattern.search(name):
            return ramp
    return _DEFAULT_RAMP


def color_ramp_for(name):
    """The ramp this variable is painted with for a variable name, and whether it is inverted.

    Returns (ramp or None, ramp name).
    """
    ramp_name, invert = ramp_for(name)
    ramp = QgsStyle.defaultStyle().colorRamp(ramp_name)
    if ramp is None:
        ramp_name = _DEFAULT_RAMP[0]
        ramp = QgsStyle.defaultStyle().colorRamp(ramp_name)
    if ramp is not None and invert and hasattr(ramp, "invert"):
        ramp.invert()
    return ramp, ramp_name


def _shader(vmin, vmax, name):
    ramp, _ = color_ramp_for(name)
    # taking care of vmin == vmax is the caller's responsibility; the shader will crash if they are equal.
    if vmax <= vmin:
        vmax = vmin + 1e-6
    shader = QgsColorRampShader(vmin, vmax, ramp, QgsColorRampShader.Interpolated)
    shader.classifyColorRamp(_RAMP_CLASSES, -1, QgsRectangle(), None)
    return shader


# The scalar and vector axes of a shared layer are set independently: each
# function touches only its own axis so the two can be shown together.


def apply_scalar(layer, variable, opacity):
    """Show one scalar group as a colour-ramped surface."""
    group = variable["index"]
    settings = layer.rendererSettings()
    settings.setActiveScalarDatasetGroup(group)

    scalar = settings.scalarSettings(group)
    scalar.setColorRampShader(_shader(variable["vmin"], variable["vmax"], variable["name"]))
    scalar.setClassificationMinimumMaximum(variable["vmin"], variable["vmax"])
    scalar.setOpacity(opacity)
    settings.setScalarSettings(group, scalar)

    layer.setRendererSettings(settings)
    layer.triggerRepaint()


def apply_vector(layer, variable, opacity):
    """Show one vector group: wind barbs for wind, arrows otherwise."""
    group = variable["index"]
    is_wind = is_wind_variable(variable["name"])
    settings = layer.rendererSettings()
    settings.setActiveVectorDatasetGroup(group)

    vector = settings.vectorSettings(group)
    color = QColor(VECTOR_COLOR)
    color.setAlphaF(opacity)
    vector.setColor(color)
    vector.setLineWidth(VECTOR_LINE_WIDTH)

    if is_wind:
        barb = vector.windBarbSettings()
        barb.setMagnitudeUnits(
            QgsMeshRendererVectorWindBarbSettings.WindSpeedUnit.MetersPerSecond
        )  # convert m/s to knots for wind barbs
        barb.setShaftLength(BARB_SHAFT_MM)
        vector.setWindBarbSettings(barb)
        vector.setSymbology(vector.WindBarbs)
    else:
        vector.setSymbology(vector.Arrows)

    vector.setOnUserDefinedGrid(True)
    spacing = BARB_GRID_PX if is_wind else VECTOR_GRID_PX
    vector.setUserGridCellWidth(spacing)
    vector.setUserGridCellHeight(spacing)
    settings.setVectorSettings(group, vector)

    layer.setRendererSettings(settings)
    layer.triggerRepaint()


def apply(layer, variable, opacity, show_colormap=True, show_vectors=True):
    """A vector group along with its colormap, as treated by MDAL."""
    if variable["kind"] == "vector":
        if show_vectors:
            apply_vector(layer, variable, opacity)
        if show_colormap:
            apply_scalar(layer, variable, opacity)
    else:
        apply_scalar(layer, variable, opacity)


def clear(layer, kind):
    """Stop rendering one axis, leaving the other untouched."""
    settings = layer.rendererSettings()
    if kind == "vector":
        settings.setActiveVectorDatasetGroup(NO_GROUP)
    else:
        settings.setActiveScalarDatasetGroup(NO_GROUP)
    layer.setRendererSettings(settings)
    layer.triggerRepaint()
