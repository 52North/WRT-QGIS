"""Converting u & v componenet of the vector field into a single scalar & vector dataset group for QGIS to render."""

import math
from collections import OrderedDict

from qgis.core import (
    QgsMeshDataBlock,
    QgsMeshDataset,
    QgsMeshDatasetGroup,
    QgsMeshDatasetGroupMetadata,
    QgsMeshDatasetIndex,
    QgsMeshDatasetMetadata,
    QgsMeshDatasetValue,
)

from . import netcdf_meta

_CACHE_STEPS = 3


class DerivedVectorDataset(QgsMeshDataset):
    """One timestep of the derived field, read from its two source groups."""

    def __init__(self, group, step):
        super().__init__()
        self._group = group
        self._step = step

    def _components(self):
        return self._group.components(self._step)

    def datasetValues(self, is_scalar, value_index, count):
        """The interleaved block QGIS renders from.

        Always a 2D block: QGIS derives the magnitude itself when the group is
        the active scalar group, so one implementation serves both axes.
        """
        east, north = self._components()
        available = max(0, min(count, len(east) - value_index))
        block = QgsMeshDataBlock(QgsMeshDataBlock.Vector2DDouble, count)
        values = [0.0] * (2 * count)
        stop = value_index + available
        values[0 : 2 * available : 2] = east[value_index:stop]
        values[1 : 2 * available : 2] = north[value_index:stop]
        block.setValues(values)
        block.setValid(True)
        return block

    def datasetValue(self, value_index):
        east, north = self._components()
        if not 0 <= value_index < len(east):
            return QgsMeshDatasetValue()
        return QgsMeshDatasetValue(east[value_index], north[value_index])

    def isActive(self, index):
        return True

    def areFacesActive(self, face_index, count):
        block = QgsMeshDataBlock(QgsMeshDataBlock.ActiveFlagInteger, count)
        block.setValid(True)
        return block

    def metadata(self):
        return QgsMeshDatasetMetadata(
            self._group.relative_time(self._step),
            True,
            self._group.minimum(),
            self._group.maximum(),
            0,
        )

    def valuesCount(self):
        return self._group.value_count


class DerivedVectorDatasetGroup(QgsMeshDatasetGroup):
    """The east/north pair of MDAL groups, published as one vector group."""

    def __init__(self, mesh_layer, name, east_index, north_index, magnitude_range, unit=""):
        super().__init__(name)
        self._layer = mesh_layer
        self._east_index = east_index
        self._north_index = north_index
        self._minimum, self._maximum = magnitude_range
        self._cache = OrderedDict()

        self.setDataType(QgsMeshDatasetGroupMetadata.DataOnVertices)
        self.setIsScalar(False)
        self.setMinimumMaximum(self._minimum, self._maximum)
        self.setReferenceTime(mesh_layer.temporalProperties().referenceTime())
        if unit:
            self.addExtraMetadata("units", unit)

        self.value_count = mesh_layer.dataProvider().vertexCount()
        self._step_count = mesh_layer.datasetCount(QgsMeshDatasetIndex(east_index, 0))
        self._datasets = [DerivedVectorDataset(self, step) for step in range(self._step_count)]

    # sources

    def components(self, step):
        """``(east values, north values)`` for one timestep, from a small cache."""
        cached = self._cache.get(step)
        if cached is not None:
            self._cache.move_to_end(step)
            return cached

        east = self._read(self._east_index, step)
        north = self._read(self._north_index, step)
        self._cache[step] = (east, north)
        while len(self._cache) > _CACHE_STEPS:
            self._cache.popitem(last=False)
        return east, north

    def _read(self, group_index, step):
        block = self._layer.datasetValues(
            QgsMeshDatasetIndex(group_index, step), 0, self.value_count
        )
        if block is None or not block.isValid():
            return [math.nan] * self.value_count
        return block.values()

    def relative_time(self, step):
        """Hours from the layer's reference time, copied from the east source.

        Sharing the source group's clock is what keeps the derived field in step
        with the canvas temporal range, and so with the timeline dock.
        """
        return self._layer.datasetRelativeTime(QgsMeshDatasetIndex(self._east_index, step)).hours()

    def minimum(self):
        return self._minimum

    def maximum(self):
        return self._maximum

    # QgsMeshDatasetGroup

    def initialize(self):
        """Statistics are supplied up front."""

    def datasetCount(self):
        return self._step_count

    def dataset(self, index):
        return self._datasets[index]

    def datasetMetadata(self, index):
        return self._datasets[index].metadata()

    def type(self):
        return QgsMeshDatasetGroup.Virtual

    def datasetGroupNamesDependentOn(self):
        return []

    def writeXml(self, doc, context):
        return doc.createElement("derived-vector-dataset-group")


def _match_group(variables, value_range):
    """The scalar variable whose value range fingerprints ``value_range``."""
    for variable in variables:
        if variable["kind"] != "scalar":
            continue
        if netcdf_meta.ranges_match((variable["vmin"], variable["vmax"]), value_range):
            return variable
    return None


def _bounding_magnitude(east, north):
    """Fallback ramp bounds when the component arrays cannot be read."""
    largest_east = max(abs(east["vmin"]), abs(east["vmax"]))
    largest_north = max(abs(north["vmin"]), abs(north["vmax"]))
    return 0.0, math.hypot(largest_east, largest_north)


def attach_derived_vectors(mesh_layer, netcdf_path, variables, pretty_name):
    """Merge every unpaired component pair in the file into a vector group.

    Returns ``(derived variables, merged indexes, groups)``: the variable dicts
    to add to the sidebar, the indexes of the component groups they replace, and
    the group objects themselves, which the caller must keep alive for as long
    as the layer.

    A pair MDAL already merged is skipped on its own — its components are not
    scalar groups any more, so nothing fingerprints against them.
    """
    derived = []
    merged = set()
    groups = []

    for pair in netcdf_meta.component_pairs(netcdf_meta.read_variables(netcdf_path)):
        east_range = netcdf_meta.value_range(pair["east"]["subdataset"])
        north_range = netcdf_meta.value_range(pair["north"]["subdataset"])
        east = _match_group(variables, east_range)
        north = _match_group(variables, north_range)
        if east is None or north is None or east["index"] == north["index"]:
            continue
        if east["index"] in merged or north["index"] in merged:
            continue

        name = pretty_name(east["raw_name"])
        magnitude = netcdf_meta.magnitude_range(
            pair["east"]["subdataset"], pair["north"]["subdataset"]
        ) or _bounding_magnitude(east, north)

        group = DerivedVectorDatasetGroup(
            mesh_layer,
            name,
            east["index"],
            north["index"],
            magnitude,
            pair["units"],
        )
        if not mesh_layer.addDatasets(group):
            continue

        groups.append(group)
        merged.update({east["index"], north["index"]})
        derived.append(
            {
                "index": mesh_layer.datasetGroupCount() - 1,
                "raw_name": f"{pair['east']['var']} / {pair['north']['var']}",
                "name": name,
                "kind": "vector",
                "unit": pair["units"],
                "vmin": magnitude[0],
                "vmax": magnitude[1],
            }
        )

    return derived, merged, groups
