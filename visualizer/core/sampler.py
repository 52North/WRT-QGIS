"""Read a mesh dataset value at a map point, for the "weather at vessel" readout."""

import math

from qgis.core import QgsMeshDatasetIndex


def sample_variable(mesh_layer, variable, frame_index, point_xy):
    """Value of one dataset group at ``point_xy`` on ``frame_index``.

    Returns a float for a scalar group and (magnitude, direction) for a vector
    group. None when the point falls outside the mesh or the value is Nan.
    """
    if mesh_layer is None or frame_index is None:
        return None

    index = QgsMeshDatasetIndex(variable["index"], frame_index)
    value = mesh_layer.datasetValue(index, point_xy)
    if value is None:
        return None

    if variable["kind"] == "vector":
        x_component, y_component = value.x(), value.y()
        if math.isnan(x_component) or math.isnan(y_component):
            return None
        magnitude = math.sqrt(x_component**2 + y_component**2)
        direction = (270.0 - math.degrees(math.atan2(y_component, x_component))) % 360.0
        return (magnitude, direction)

    scalar = value.scalar()
    return None if scalar is None or math.isnan(scalar) else scalar
