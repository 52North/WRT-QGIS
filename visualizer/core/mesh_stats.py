"""Summary statistics for one mesh dataset group inside a map rectangle."""

import math
from dataclasses import dataclass, field
from statistics import fmean, median

from qgis.core import QgsMesh, QgsMeshDatasetGroupMetadata, QgsMeshDatasetIndex

DATA_ON_VERTICES = QgsMeshDatasetGroupMetadata.DataOnVertices
DATA_ON_FACES = QgsMeshDatasetGroupMetadata.DataOnFaces

# The maximum number of elements in a mesh that the stats code will handle.
MAX_ELEMENTS = 4_000_000

# The maximum number of elements in a rectangle that the stats code will handle.
MAX_REGION_CELLS = 150_000

BIN_COUNT = 24  # The number of bins in the histogram for a dataset group.


def data_type_of(mesh_layer, variable):
    """Whether ``variable``'s values are indexed by vertex, face, edge or volume."""
    metadata = mesh_layer.datasetGroupMetadata(QgsMeshDatasetIndex(variable["index"], 0))
    return metadata.dataType()


class MeshGeometry:
    """Element centre coordinates for one mesh layer, built once and lazily."""

    def __init__(self, mesh_layer):
        self._mesh = QgsMesh()
        data_provider = mesh_layer.dataProvider()
        if data_provider is not None:
            data_provider.populateMesh(self._mesh)
        self._vertex_xs = None
        self._vertex_ys = None
        self._face_xs = None
        self._face_ys = None

    @property
    def element_count(self):
        """Cells in the whole grid — whichever of vertices or faces is larger."""
        return max(self._mesh.vertexCount(), self._mesh.faceCount())

    @property
    def is_too_large(self):
        return self.element_count > MAX_ELEMENTS

    @property
    def is_empty(self):
        return self._mesh.vertexCount() == 0

    def coordinates(self, data_type):
        """``(xs, ys)`` flat lists indexed the way the value block is, or None."""
        if data_type == DATA_ON_VERTICES:
            return self._vertex_coordinates()
        if data_type == DATA_ON_FACES:
            return self._face_coordinates()
        return None

    def _vertex_coordinates(self):
        if self._vertex_xs is None:
            mesh = self._mesh
            count = mesh.vertexCount()
            xs = [0.0] * count
            ys = [0.0] * count
            for i in range(count):
                vertex = mesh.vertex(i)
                xs[i] = vertex.x()
                ys[i] = vertex.y()
            self._vertex_xs = xs
            self._vertex_ys = ys
        return self._vertex_xs, self._vertex_ys

    def _face_coordinates(self):
        if self._face_xs is None:
            vertex_xs, vertex_ys = self._vertex_coordinates()
            mesh = self._mesh
            count = mesh.faceCount()
            xs = [0.0] * count
            ys = [0.0] * count
            for i in range(count):
                corners = mesh.face(i)
                if not corners:
                    continue
                total = float(len(corners))
                xs[i] = sum(vertex_xs[corner] for corner in corners) / total
                ys[i] = sum(vertex_ys[corner] for corner in corners) / total
            self._face_xs = xs
            self._face_ys = ys
        return self._face_xs, self._face_ys


class RegionSelection:
    """The element indices inside one rectangle, for one data type.

    Rebuilt only when the box moves - never on a clock tick, which is what keeps
    playback affordable on a large grid.
    """

    def __init__(self, geometry, data_type, rect_layer):
        self.is_supported = False
        self.indices = []
        self.total_elements = 0

        coordinates = geometry.coordinates(data_type)
        if coordinates is None:
            return
        self.is_supported = True

        xs, ys = coordinates
        self.total_elements = len(xs)
        x_min = rect_layer.xMinimum()
        x_max = rect_layer.xMaximum()
        y_min = rect_layer.yMinimum()
        y_max = rect_layer.yMaximum()

        # Check each element's centre against the rectangle, and keep the indices of those inside.
        self.indices = [
            i
            for i in range(self.total_elements)
            if x_min <= xs[i] <= x_max and y_min <= ys[i] <= y_max
        ]

    @property
    def is_empty(self):
        return not self.indices

    @property
    def is_over_limit(self):
        return len(self.indices) > MAX_REGION_CELLS


@dataclass
class RegionStats:
    """Basic stats of the selected bounding box, for one dataset group at one timestep."""

    is_supported: bool = True
    is_over_limit: bool = False
    total_in_box: int = 0  # grid cells in the box, no-data included
    count: int = 0  # values actually summarised, no-data excluded
    minimum: float = None
    maximum: float = None
    mean: float = None
    median: float = None
    std_dev: float = None
    values: list = field(default_factory=list)

    @property
    def has_values(self):
        return self.count > 0


def collect_values(raw, indices, first, is_vector, active_flags=None):
    """Makes a flat list of the requested values, dropping no-data."""

    values = []
    append = values.append
    for index in indices:
        offset = index - first
        if active_flags is not None and not active_flags[offset]:
            continue
        if is_vector:
            x_component = raw[2 * offset]
            y_component = raw[2 * offset + 1]
            if not (math.isfinite(x_component) and math.isfinite(y_component)):
                continue
            append(math.sqrt(x_component**2 + y_component**2))
        else:
            value = raw[offset]
            if math.isfinite(
                value
            ):  # Rejecting NaN and Inf, which are the no-data values for floats.
                append(value)
    return values


def summarize(values, total_in_box):
    if not values:
        return RegionStats(total_in_box=total_in_box)
    mean_value = fmean(values)
    variance = fmean([(value - mean_value) ** 2 for value in values])
    return RegionStats(
        total_in_box=total_in_box,
        count=len(values),
        minimum=min(values),
        maximum=max(values),
        mean=mean_value,
        median=median(values),
        std_dev=math.sqrt(variance),
        values=values,
    )


def region_stats(mesh_layer, variable, frame_index, selection):
    """Statistics for one dataset group inside ``selection``, at one timestep."""
    if not selection.is_supported:
        return RegionStats(is_supported=False)

    # Capping the number of elements in the box for performance reasons.
    if selection.is_over_limit:
        return RegionStats(is_over_limit=True, total_in_box=len(selection.indices))

    indices = selection.indices
    if not indices:
        return RegionStats(total_in_box=0)

    first = indices[0]
    span = indices[-1] - first + 1
    dataset_index = QgsMeshDatasetIndex(variable["index"], frame_index)
    # The dataset values are returned in a flat list, indexed the same way as the mesh elements.
    block = mesh_layer.datasetValues(dataset_index, first, span)
    if block is None or not block.isValid():
        return RegionStats(total_in_box=len(selection.indices))

    active_flags = None
    if data_type_of(mesh_layer, variable) == DATA_ON_FACES:
        # The active flags are returned in a flat list, indexed the same way as the mesh faces.
        active_block = mesh_layer.areFacesActive(dataset_index, first, span)
        if active_block is not None and active_block.isValid():
            active_flags = active_block.active()

    values = collect_values(
        block.values(), indices, first, variable["kind"] == "vector", active_flags
    )
    return summarize(values, len(selection.indices))


def bin_values(values, minimum, maximum, count=BIN_COUNT):
    """``(counts, edges)`` for a histogram; ``edges`` holds ``count + 1`` entries."""
    if not values:
        return [], []
    if maximum <= minimum:
        # A flat region still adds one bin, so that the histogram can be drawn.
        return [len(values)], [minimum, maximum]

    width = (maximum - minimum) / count
    counts = [0] * count
    for value in values:
        slot = int((value - minimum) / width)
        if slot >= count:  # the maximum lands exactly on the top edge
            slot = count - 1
        elif slot < 0:
            slot = 0
        counts[slot] += 1
    edges = [minimum + width * i for i in range(count + 1)]
    return counts, edges
