import re

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsMeshDatasetIndex,
    QgsMeshLayer,
    QgsTask,
)
from qgis.PyQt.QtCore import QCoreApplication, QDateTime, pyqtSignal

from . import variable_catalog

_PROVIDER = "mdal"

_FALLBACK_CRS = "EPSG:4326"

# Regex to clean up the raw variable names into more human-readable.
_NAME_CLEANUPS = [
    (re.compile(r"\s*@\s*Specified height level above ground", re.I), ""),
    (re.compile(r"_height_above_ground:(\d+(?:\.\d+)?)", re.I), r" @ \1 m"),
    (re.compile(r"\s*_depth:\s*[\d.]+", re.I), ""),
    (re.compile(r"\s*@\s*Ground or water surface", re.I), " (surface)"),
    (re.compile(r"\s*@\s*Mean sea level", re.I), ""),
]


def _pretty_name(raw):
    name = raw
    for pattern, repl in _NAME_CLEANUPS:
        name = pattern.sub(repl, name)
    name = name.replace("_", " ")
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        return raw
    return name[0].upper() + name[1:]


def _unit(metadata):
    """The variable's unit as MDAL copied it out of the file, or ""."""
    try:
        options = metadata.extraOptions()
    except AttributeError:
        return ""
    for key, value in options.items():
        if key.strip().lower() in ("unit", "units"):
            return value.strip()
    return ""


def _dedupe(names):
    """Suffix repeated display names so every card is distinguishable."""
    seen = {}
    out = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        out.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    return out


def _assign_names(variables):
    """Give every variable its final display name, unique across the list.

    The catalog names the fields it recognises; anything else keeps the name
    MDAL derived from the file.
    """
    proposed = [
        variable_catalog.canonical_name(
            variable["raw_name"], variable.get("name") or _pretty_name(variable["raw_name"])
        )
        for variable in variables
    ]
    # _dedupe returns one name per input, so the two sides cannot drift apart.
    for variable, name in zip(variables, _dedupe(proposed), strict=True):
        variable["name"] = name


def build_layer(netcdf_path):
    """Open the file as a mesh. Safe to call from a worker thread."""
    layer = QgsMeshLayer(netcdf_path, "Weather data", _PROVIDER)
    if not layer.isValid():
        raise ValueError(
            "MDAL could not read this file as a mesh.\n\n"
            "Weather visualization needs a gridded, CF-style NetCDF "
            "(lat/lon plus a time axis)."
        )
    if not layer.crs().isValid():
        layer.setCrs(QgsCoordinateReferenceSystem(_FALLBACK_CRS))
    return layer


class WeatherMeshLoader:
    """Metadata for one weather file, wrapped around a single mesh layer."""

    def __init__(self, netcdf_path, layer):
        self._path = netcdf_path
        self._layer = layer
        self._derived_groups = []
        self._variables = self._read_variables()
        if not self._variables:
            raise ValueError("No weather variables found in this file.")
        # Read the clock while every group is still one MDAL wrote, then merge
        # the component pairs MDAL left apart and name whatever survives.
        self._timestamps = self._read_timestamps()
        self._variables = self._merge_components(self._variables)
        _assign_names(self._variables)

    @property
    def path(self):
        return self._path

    @property
    def layer(self):
        return self._layer

    @property
    def variables(self):
        return self._variables

    @property
    def timestamps(self):
        return self._timestamps

    def _read_variables(self):
        raw = []
        for i in range(self._layer.datasetGroupCount()):
            md = self._layer.datasetGroupMetadata(QgsMeshDatasetIndex(i, 0))
            raw.append(
                {
                    "index": i,
                    "raw_name": md.name(),
                    "kind": "scalar" if md.isScalar() else "vector",
                    "unit": _unit(md),
                    "vmin": md.minimum(),
                    "vmax": md.maximum(),
                }
            )
        return raw

    def _merge_components(self, variables):
        """Replace each u/v scalar pair with the one vector field it describes."""
        from .derived_vector import attach_derived_vectors

        try:
            derived, merged, groups = attach_derived_vectors(
                self._layer, self._path, variables, _pretty_name
            )
        except Exception:
            return variables

        self._derived_groups = groups
        return [v for v in variables if v["index"] not in merged] + derived

    def _read_timestamps(self):
        """Absolute timestamps for the slider, as reference time + offset."""
        ref = self._layer.temporalProperties().referenceTime()
        group = self._variables[0]["index"]
        count = self._layer.datasetCount(QgsMeshDatasetIndex(group, 0))
        stamps = []
        for step in range(count):
            interval = self._layer.datasetRelativeTime(QgsMeshDatasetIndex(group, step))
            stamps.append(ref.addSecs(int(interval.seconds())) if ref.isValid() else QDateTime())
        return stamps


class LoadWeatherMeshTask(QgsTask):
    """Opens the mesh off the GUI thread; a big file takes seconds."""

    done = pyqtSignal(object, object)  # (loader or None, exception or None)

    def __init__(self, netcdf_path):
        super().__init__("Loading weather data", QgsTask.CanCancel)
        self._path = netcdf_path
        self._loader = None
        self._exc = None

    def run(self):
        try:
            layer = build_layer(self._path)
            # Read metadata here, while the layer still belongs to this thread.
            loader = WeatherMeshLoader(self._path, layer)
            # Hand the layer to the GUI thread before anyone renders it.
            layer.moveToThread(QCoreApplication.instance().thread())
            self._loader = loader
            return True
        except Exception as exc:  # an unreadable file is a result, not a crash
            self._exc = exc
            return False

    def finished(self, ok):
        self.done.emit(self._loader, self._exc)
