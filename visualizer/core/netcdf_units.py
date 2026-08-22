"""Units for mesh dataset groups, read straight from the file's CF attributes."""

import re

# MDAL appends a suffix to variable names when it merges u/v components into a vector group.
_SUFFIX = re.compile(
    r"_(?:depth|height_above_ground|valid_time|time|level|sigma|elevation):.*$", re.I
)

# Prefix dropped from a variable name when MDAL merges u/v components into a vector group.
_COMPONENT_WORDS = frozenset(
    {"u", "v", "x", "y", "component", "eastward", "northward", "zonal", "meridional"}
)

# The unit strings that should be shown in a legend, rather than the raw CF attribute.
_UNIT_LABELS = {
    "m s-1": "m/s",
    "m s**-1": "m/s",
    "degrees_c": "°C",
    "degree_c": "°C",
    "celsius": "°C",
    "degree": "°",
    "degrees": "°",
    "degrees_north": "°",
    "degrees_east": "°",
    "degree_true": "°",
    "psu": "PSU",
    "percent": "%",
}

_PER_SECOND = re.compile(r"^(.*?)\s*(?:s-1|s\*\*-1|/s)$", re.I)


def _key(name):
    """A comparable form of a variable name, blind to level suffixes and u/v wording."""
    name = _SUFFIX.sub("", name)
    words = [word for word in re.split(r"[^a-zA-Z0-9]+", name) if word]
    kept = [word for word in words if word.lower() not in _COMPONENT_WORDS]
    while kept and kept[0].lower() in ["of", "the"]:
        kept.pop(0)
    return "".join(kept).lower()


def format_unit(raw):
    """A CF unit string as a legend should show it, or "" when there is nothing to show."""
    unit = (raw or "").strip()
    if not unit:
        return ""
    label = _UNIT_LABELS.get(unit.lower())
    if label is not None:
        return label
    match = _PER_SECOND.match(unit)
    if match and match.group(1):
        return f"{match.group(1).strip()}/s"
    return unit


def unit_table(netcdf_path):
    """``{normalised variable name: unit}`` for everything GDAL can read in the file."""
    try:
        from osgeo import gdal
    except ImportError:
        return {}

    table = {}
    try:
        container = gdal.Open(netcdf_path)
        if container is None:
            return table
        for uri, _description in container.GetSubDatasets() or []:
            variable = uri.rsplit(":", 1)[-1].strip('"')
            sub = gdal.Open(uri)
            if sub is None:
                continue
            metadata = sub.GetMetadata()
            unit = format_unit(metadata.get(f"{variable}#units"))
            if not unit:
                continue
            for label in (
                metadata.get(f"{variable}#long_name"),
                metadata.get(f"{variable}#standard_name"),
                variable,
            ):
                if label:
                    table.setdefault(_key(label), unit)
    except Exception:
        return table
    return table


def unit_for(table, raw_name):
    """The unit for one MDAL group name, or "" when the file did not name one."""
    return table.get(_key(raw_name), "")
