"""Load a WRT ``config.json`` from disk back into the wizard's config dict."""

import copy
import json
import re
from datetime import datetime

from .defaults import DEFAULT_ALGORITHM, DEFAULTS, INTERNAL_KEYS

# Format the pages parse departure/arrival times with (QDateTime.fromString).
TIME_FORMAT = "%Y-%m-%dT%H:%MZ"

# Accepted on input time formats.
_INPUT_TIME_FORMATS = (
    "%Y-%m-%dT%H:%MZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H:%M:%S",
)

_INT_PATTERN = re.compile(r"^[+-]?\d+$")

# In case the imported config has keys that are not present here are ignored are not editable.
WIZARD_EDITABLE_KEYS = frozenset(
    {
        # Page 1 — route
        "DEFAULT_ROUTE",
        "DEFAULT_MAP",
        "DEPARTURE_TIME",
        "INTERMEDIATE_WAYPOINTS",
        "ROUTE_PATH",
        # Page 2 — algorithm
        "ALGORITHM_TYPE",
        "ARRIVAL_TIME",
        "DELTA_FUEL",
        "ROUTER_HDGS_SEGMENTS",
        "ROUTER_HDGS_INCREMENTS_DEG",
        "BOAT_SPEED_BOUNDARIES",
        "ISOCHRONE_NUMBER_OF_ROUTES",
        "ISOCHRONE_MINIMISATION_CRITERION",
        "ISOCHRONE_MAX_ROUTING_STEPS",
        "ISOCHRONE_PRUNE_GROUPS",
        "ISOCHRONE_PRUNE_SECTOR_DEG_HALF",
        "ISOCHRONE_PRUNE_SEGMENTS",
        "ISOCHRONE_PRUNE_SYMMETRY_AXIS",
        "GENETIC_NUMBER_GENERATIONS",
        "GENETIC_NUMBER_OFFSPRINGS",
        "GENETIC_POPULATION_SIZE",
        "GENETIC_POPULATION_TYPE",
        "GENETIC_POPULATION_PATH",
        "GENETIC_OBJECTIVES",
        "GENETIC_MUTATION_TYPE",
        "GENETIC_CROSSOVER_TYPE",
        "GENETIC_CROSSOVER_PATCHER",
        "GENETIC_REPAIR_TYPE",
        "GENETIC_FIX_RANDOM_SEED",
        "GCR_SLIDER_ANGLE_STEP",
        "GCR_SLIDER_DISTANCE_MOVE",
        "GCR_SLIDER_DYNAMIC_PARAMETERS",
        "GCR_SLIDER_LAND_BUFFER",
        "GCR_SLIDER_INTERPOLATE",
        "GCR_SLIDER_INTERP_DIST",
        "GCR_SLIDER_INTERP_NORMALIZED",
        "GCR_SLIDER_MAX_POINTS",
        "GCR_SLIDER_THRESHOLD",
        "DIJKSTRA_NOF_NEIGHBORS",
        "DIJKSTRA_STEP",
        "DIJKSTRA_MASK_FILE",
        # Page 3 — boat
        "BOAT_TYPE",
        "BOAT_SPEED",
        "BOAT_LENGTH",
        "BOAT_BREADTH",
        "BOAT_SMCR_POWER",
        "BOAT_SMCR_SPEED",
        "BOAT_FUEL_RATE",
        "BOAT_HBR",
        "BOAT_DRAUGHT_AFT",
        "BOAT_DRAUGHT_FORE",
        "BOAT_ROUGHNESS_DISTRIBUTION_LEVEL",
        "BOAT_ROUGHNESS_LEVEL",
        "BOAT_UNDER_KEEL_CLEARANCE",
        "BOAT_OVERLOAD_FACTOR",
        "BOAT_PROPULSION_EFFICIENCY",
        "BOAT_SPEED_MAX",
        "BOAT_FACTOR_CALM_WATER",
        "BOAT_FACTOR_WAVE_FORCES",
        "BOAT_FACTOR_WIND_FORCES",
        "AIR_MASS_DENSITY",
        "COURSES_FILE",
        "BOAT_AOD",
        "BOAT_AXV",
        "BOAT_AYV",
        "BOAT_CMC",
        "BOAT_HC",
        "BOAT_BS1",
        "BOAT_HS1",
        "BOAT_HS2",
        "BOAT_LS1",
        "BOAT_LS2",
        # Page 4 — weather & depth
        "WEATHER_DATA",
        "DEPTH_DATA",
        "DELTA_TIME_FORECAST",
        "TIME_FORECAST",
        # Page 5 — constraints
        "CONSTRAINTS_LIST",
    }
)

# Boat keys that default to "" (unset) but are read back with float() by page 3.
_OPTIONAL_NUMERIC_KEYS = frozenset(
    {
        "BOAT_LENGTH",
        "BOAT_BREADTH",
        "BOAT_FUEL_RATE",
        "BOAT_HBR",
        "BOAT_SMCR_POWER",
        "BOAT_SMCR_SPEED",
        "BOAT_SPEED_MAX",
        "BOAT_AOD",
        "BOAT_AXV",
        "BOAT_AYV",
        "BOAT_CMC",
        "BOAT_HC",
        "BOAT_BS1",
        "BOAT_HS1",
        "BOAT_HS2",
        "BOAT_LS1",
        "BOAT_LS2",
    }
)

BOOL_KEYS = frozenset(key for key, value in DEFAULTS.items() if isinstance(value, bool))

NUMERIC_KEYS = (
    frozenset(
        key
        for key, value in DEFAULTS.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )
    | _OPTIONAL_NUMERIC_KEYS
)

# Coordinate keys the export writes as a list of floats; the pages want "a,b,c,d".
_COORD_KEYS = ("DEFAULT_ROUTE", "DEFAULT_MAP")
_TIME_KEYS = ("DEPARTURE_TIME", "ARRIVAL_TIME")


class ConfigLoadError(Exception):
    """Raised when a file cannot be read or is not a JSON object."""


def read_config_file(path):
    """Return the raw JSON object at ``path``. Raises ConfigLoadError."""
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except OSError as error:
        raise ConfigLoadError(f"Could not read the file:\n{error}") from error
    except json.JSONDecodeError as error:
        raise ConfigLoadError(f"The file is not valid JSON:\n{error}") from error
    if not isinstance(raw, dict):
        raise ConfigLoadError(
            "The file must contain a JSON object of configuration keys, "
            f"not a {type(raw).__name__}."
        )
    return raw


def load_config_json(path):
    """Load ``path`` into a wizard config dict.

    Returns ``(config, warnings)`` where warnings are human-readable notes about
    values that could not be used as-is. Raises ConfigLoadError for unusable files.
    """
    return normalize_config(read_config_file(path))


def normalize_config(raw):
    """Overlay a raw config.json object onto DEFAULTS, coercing values the pages
    expect in a specific shape. Returns ``(config, warnings)``."""
    config = copy.deepcopy(DEFAULTS)
    warnings = []

    for key, value in raw.items():
        if key in _COORD_KEYS:
            coords = _coords_to_text(value)
            if coords is None:
                warnings.append(f"{key}: expected 4 coordinates — kept the default.")
                continue
            config[key] = coords
        elif key in _TIME_KEYS:
            stamp = _normalize_time(value)
            if stamp is None:
                warnings.append(f"{key}: unrecognised timestamp {value!r} — kept the default.")
                continue
            config[key] = stamp
        elif key == "INTERMEDIATE_WAYPOINTS":
            waypoints, dropped = _normalize_waypoints(value)
            if dropped:
                warnings.append(f"{key}: ignored {dropped} malformed waypoint(s).")
            config[key] = waypoints
        elif key == "GENETIC_REPAIR_TYPE":
            config[key] = list(value) if isinstance(value, list) else [value]
        elif key == "BOAT_SPEED_BOUNDARIES":
            bounds = _normalize_speed_bounds(value)
            if bounds is None:
                warnings.append(f"{key}: expected [min, max] speeds — kept the default.")
                continue
            config[key] = bounds
        elif key == "CONSTRAINTS_LIST":
            config[key] = list(value) if isinstance(value, list) else config[key]
        elif key in BOOL_KEYS:
            flag = _to_bool(value)
            if flag is None:
                warnings.append(f"{key}: expected true/false — kept the default.")
                continue
            config[key] = flag
        elif key in NUMERIC_KEYS:
            number = _to_number(value)
            if number is None:
                warnings.append(f"{key}: expected a number — kept the default.")
                continue
            config[key] = number
        else:
            config[key] = value

    _restore_internal_state(config, raw)

    # Wizard-internal keys are restored above, so they are not "unknown" either.
    not_editable = sorted(set(raw) - WIZARD_EDITABLE_KEYS - INTERNAL_KEYS)
    if not_editable:
        warnings.append("Kept as-is (no wizard field for these): " + ", ".join(not_editable) + ".")
    return config, warnings


def _coords_to_text(value):
    """ "lat,lon,lat,lon" from either a string or the exported list of 4 floats."""
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        return None
    if len(parts) != 4:
        return None
    try:
        return ",".join(_format_coord(part) for part in parts)
    except (TypeError, ValueError):
        return None


def _format_coord(value):
    """Trim binary-float noise (3.4000000000000004) without losing real precision."""
    return f"{float(value):.10f}".rstrip("0").rstrip(".") or "0"


def _normalize_time(value):
    """Re-emit a timestamp in TIME_FORMAT, or None if it cannot be parsed."""
    if isinstance(value, datetime):
        return value.strftime(TIME_FORMAT)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return ""
    for fmt in _INPUT_TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime(TIME_FORMAT)
        except ValueError:
            continue
    return None


def _normalize_waypoints(value):
    """Return ``([[lat, lon], ...], dropped_count)``."""
    if not isinstance(value, (list, tuple)):
        return [], 1
    waypoints = []
    dropped = 0
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            dropped += 1
            continue
        try:
            waypoints.append([float(item[0]), float(item[1])])
        except (TypeError, ValueError):
            dropped += 1
    return waypoints, dropped


def _normalize_speed_bounds(value):
    """Return ``[min, max]`` floats for BOAT_SPEED_BOUNDARIES, or None if unusable."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        low, high = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None
    return [low, high] if low < high else None


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "yes", "1"):
            return True
        if text in ("false", "no", "0"):
            return False
    return None


def _to_number(value):
    """Coerce to int/float. Empty strings mean "unset"; None marks a bad value."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        try:
            return int(text) if _INT_PATTERN.match(text) else float(text)
        except ValueError:
            return None
    return None


def _restore_internal_state(config, raw):
    """Rebuild the wizard-internal keys that INTERNAL_KEYS strips on export."""
    intent = raw.get("_GENETIC_INTENT")
    if not intent:
        crossover = config.get("GENETIC_CROSSOVER_TYPE", "random")
        intent = {"waypoints": "waypoints", "speed": "speed"}.get(crossover, "speed_waypoints")
    config["_GENETIC_INTENT"] = intent

    schedule = raw.get("_GENETIC_SCHEDULE")
    if not schedule:
        # Waypoints-only mode fixes the schedule by exactly one of BOAT_SPEED/ARRIVAL_TIME.
        schedule = (
            "via_arrival" if intent == "waypoints" and config.get("ARRIVAL_TIME") else "via_speed"
        )
    config["_GENETIC_SCHEDULE"] = schedule

    # If the file does not carry the advanced flag, infer it from the algorithm type.
    is_advanced = raw.get("_ALGO_ADVANCED")
    if is_advanced is None:
        is_advanced = config.get("ALGORITHM_TYPE") != DEFAULT_ALGORITHM
    config["_ALGO_ADVANCED"] = bool(_to_bool(is_advanced))
