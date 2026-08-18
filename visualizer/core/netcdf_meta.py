"""NetCDF header introspection, for the u/v component pairs."""

import math
import re

_MISSING = object()

_EAST_TOKENS = [
    re.compile(r"eastward", re.I),
    re.compile(r"_x_velocity", re.I),
    re.compile(r"\bx[-_ ]?component(\s+of)?", re.I),
    re.compile(r"\bu[-_ ]?component(\s+of)?", re.I),
    re.compile(r"\bzonal", re.I),
]
_NORTH_TOKENS = [
    re.compile(r"northward", re.I),
    re.compile(r"_y_velocity", re.I),
    re.compile(r"\by[-_ ]?component(\s+of)?", re.I),
    re.compile(r"\bv[-_ ]?component(\s+of)?", re.I),
    re.compile(r"\bmeridional", re.I),
]

# Regex for u/v component prefixes, e.g. "utotal" or "vtotal".
_EAST_PREFIX = re.compile(r"^u(?=[a-z0-9_])", re.I)
_NORTH_PREFIX = re.compile(r"^v(?=[a-z0-9_])", re.I)

EAST = "east"
NORTH = "north"

_RANGE_TOLERANCE = 1e-6


def _normalize(text):
    """Lowercased, with every run of non-alphanumerics collapsed to one space."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _split_direction(text, is_variable_name=False):
    """``(direction, base)`` for ``text``, or None when it marks no direction."""
    for direction, patterns in ((EAST, _EAST_TOKENS), (NORTH, _NORTH_TOKENS)):
        for pattern in patterns:
            if pattern.search(text):
                return direction, _normalize(pattern.sub(" ", text))
    if is_variable_name:
        for direction, prefix in ((EAST, _EAST_PREFIX), (NORTH, _NORTH_PREFIX)):
            if prefix.search(text):
                return direction, _normalize(prefix.sub("", text))
    return None


def _gdal():
    from osgeo import gdal

    gdal.UseExceptions()
    return gdal


def read_variables(netcdf_path):
    """One dict per NetCDF variable GDAL exposes as a subdataset.

    Keys: ``var``, ``subdataset``, ``long_name``, ``standard_name``, ``units``,
    ``band_count``. Header reads only — no pixel data is touched here.
    """
    gdal = _gdal()
    container = gdal.Open(netcdf_path)
    if container is None:
        return []

    variables = []
    for subdataset_name, _ in container.GetSubDatasets():
        name = subdataset_name.rsplit(":", 1)[-1].strip('"')
        subdataset = gdal.Open(subdataset_name)
        if subdataset is None:
            continue
        metadata = subdataset.GetMetadata()
        variables.append(
            {
                "var": name,
                "subdataset": subdataset_name,
                "long_name": metadata.get(f"{name}#long_name", ""),
                "standard_name": metadata.get(f"{name}#standard_name", ""),
                "units": metadata.get(f"{name}#units", ""),
                "band_count": subdataset.RasterCount,
            }
        )
    return variables


def _identity(variable):
    """``(direction, base key)`` for one variable, or None if it is not a component."""
    for key in ("standard_name", "long_name"):
        text = (variable.get(key) or "").strip()
        if text:
            split = _split_direction(text)
            if split is not None:
                return split
    return _split_direction(variable["var"], is_variable_name=True)


def component_pairs(variables):
    """Group the component variables into east/north pairs of the same field."""
    by_base = {}
    for variable in variables:
        identity = _identity(variable)
        if identity is None:
            continue
        direction, base = identity
        by_base.setdefault(base, {}).setdefault(direction, variable)

    pairs = []
    for base, sides in by_base.items():
        east = sides.get(EAST)
        north = sides.get(NORTH)
        if east is None or north is None:
            continue
        pairs.append(
            {
                "base": base,
                "east": east,
                "north": north,
                "units": (east.get("units") or north.get("units") or "").strip(),
            }
        )
    return pairs


def value_range(subdataset_name):
    """``(minimum, maximum)`` over every band of one variable, or None."""
    gdal = _gdal()
    subdataset = gdal.Open(subdataset_name)
    if subdataset is None:
        return None

    minimum = None
    maximum = None
    for band_index in range(1, subdataset.RasterCount + 1):
        try:
            band_min, band_max = subdataset.GetRasterBand(band_index).ComputeRasterMinMax(False)
        except RuntimeError:  # an all-nodata band has no range to report
            continue
        minimum = band_min if minimum is None else min(minimum, band_min)
        maximum = band_max if maximum is None else max(maximum, band_max)
    if minimum is None:
        return None
    return minimum, maximum


def ranges_match(first, second):
    """Whether two ``(minimum, maximum)`` pairs describe the same data."""
    if first is None or second is None:
        return False
    span = max(abs(first[1] - first[0]), abs(second[1] - second[0]), 1e-12)
    return all(abs(a - b) <= _RANGE_TOLERANCE * span for a, b in zip(first, second, strict=True))


def magnitude_range(east_subdataset, north_subdataset):
    """``(minimum, maximum)`` of ``hypot(east, north)`` across every timestep.

    Returns None if the arrays cannot be read, leaving the bound to the caller.
    """
    try:
        import numpy

        gdal = _gdal()
        east = gdal.Open(east_subdataset)
        north = gdal.Open(north_subdataset)
    except Exception:
        return None
    if east is None or north is None or east.RasterCount != north.RasterCount:
        return None

    minimum = math.inf
    maximum = -math.inf
    for band_index in range(1, east.RasterCount + 1):
        east_values = east.GetRasterBand(band_index).ReadAsArray()
        north_values = north.GetRasterBand(band_index).ReadAsArray()
        if east_values is None or north_values is None:
            continue
        magnitudes = numpy.hypot(east_values, north_values)
        if not numpy.any(numpy.isfinite(magnitudes)):
            continue
        minimum = min(minimum, float(numpy.nanmin(magnitudes)))
        maximum = max(maximum, float(numpy.nanmax(magnitudes)))

    if not math.isfinite(minimum) or not math.isfinite(maximum):
        return None
    return minimum, maximum
