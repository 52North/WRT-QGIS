"""NetCDF / raster dataset inspection and coverage validation.

Pure (GUI-free) logic for the weather & depth page: it opens a file with GDAL,
reads its spatial extent and CF time axis, and checks whether that coverage
contains the route's map bounds and forecast period. ``InspectNetcdfTask`` wraps
the heavy ``inspect_netcdf`` call so it can run off the UI thread.
"""

import re
from datetime import datetime, timedelta

from osgeo import gdal, osr
from qgis.core import QgsTask
from qgis.PyQt.QtCore import pyqtSignal

UNIT_SECONDS = {
    "seconds": 1,
    "second": 1,
    "secs": 1,
    "sec": 1,
    "s": 1,
    "minutes": 60,
    "minute": 60,
    "mins": 60,
    "min": 60,
    "hours": 3600,
    "hour": 3600,
    "hrs": 3600,
    "hr": 3600,
    "h": 3600,
    "days": 86400,
    "day": 86400,
    "d": 86400,
}


def parse_time_units(units):
    """Parse a CF time-units string like 'hours since 1970-01-01 00:00:00'.

    :return: (seconds_per_unit, reference_datetime) or None if unparseable.
    """
    m = re.match(r"\s*(\w+)\s+since\s+(.+)", units, re.IGNORECASE)
    if not m:
        return None
    unit, ref = m.group(1).lower(), m.group(2).strip()
    if unit not in UNIT_SECONDS:
        return None
    # Normalise the reference date: drop trailing 'Z'/timezone, fractional secs.
    ref = ref.replace("T", " ").rstrip("Z").strip()
    ref = re.sub(r"\s+[+-]\d{1,2}:?\d{2}$", "", ref)  # strip +HH:MM offset
    ref = re.sub(r"\.\d+", "", ref)  # strip fractional secs
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return UNIT_SECONDS[unit], datetime.strptime(ref, fmt)
        except ValueError:
            continue
    return None


def _datasets(path):
    """Open a file and yield a gdal dataset per geospatial variable.

    NetCDF variables are exposed as GDAL subdatasets (NETCDF:"file":var); a
    plain raster has none, so the root dataset itself is yielded.

    :raises ValueError: if the file cannot be opened by GDAL at all.
    """

    def _open(name):
        # GDAL <4 returns None on failure; GDAL 4 / UseExceptions() raises.
        try:
            return gdal.Open(name)
        except RuntimeError:
            return None

    gdal.PushErrorHandler("CPLQuietErrorHandler")
    try:
        root = _open(path)
        if root is None:
            raise ValueError("not a readable NetCDF/raster file")
        subs = root.GetSubDatasets()
        if not subs:
            yield root
            return
        for name, _desc in subs:
            ds = _open(name)
            if ds is not None:
                yield ds
    finally:
        gdal.PopErrorHandler()


def spatial_extent(ds, gt):
    """Return ((lat_min, lon_min, lat_max, lon_max), (dx, dy)) for a dataset."""
    nx, ny = ds.RasterXSize, ds.RasterYSize
    dx, dy = abs(gt[1]), abs(gt[5])
    # Pixel-edge corners from the geotransform, then pull in half a cell.
    xs = sorted((gt[0], gt[0] + gt[1] * nx))
    ys = sorted((gt[3], gt[3] + gt[5] * ny))
    lon_min, lon_max = xs[0] + dx / 2, xs[1] - dx / 2
    lat_min, lat_max = ys[0] + dy / 2, ys[1] - dy / 2

    wkt = ds.GetProjection()
    if wkt:
        src = osr.SpatialReference()
        src.ImportFromWkt(wkt)
        if not src.IsGeographic():
            dst = osr.SpatialReference()
            dst.ImportFromEPSG(4326)
            dst.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            tr = osr.CoordinateTransformation(src, dst)
            corners = [
                tr.TransformPoint(x, y)[:2] for x in (lon_min, lon_max) for y in (lat_min, lat_max)
            ]
            lons = [c[0] for c in corners]
            lats = [c[1] for c in corners]
            lon_min, lon_max = min(lons), max(lons)
            lat_min, lat_max = min(lats), max(lats)
    return (lat_min, lon_min, lat_max, lon_max), (dx, dy)


def time_axis(ds):
    """Return (sorted_timestamps, calendar) for a dataset's CF time dimension."""
    md = ds.GetMetadata()
    for key, units in md.items():
        if not key.endswith("#units") or "since" not in units.lower():
            continue
        dim = key[: -len("#units")]
        raw = md.get(f"NETCDF_DIM_{dim}_VALUES")
        parsed = parse_time_units(units)
        if not raw or not parsed:
            continue
        per_unit, ref = parsed
        try:
            values = [float(v) for v in raw.strip("{} ").split(",") if v.strip()]
        except ValueError:
            continue
        if not values:
            continue
        stamps = sorted(ref + timedelta(seconds=v * per_unit) for v in values)
        calendar = md.get(f"{dim}#calendar", "").lower()
        return stamps, calendar
    return None


def median_step_hours(stamps):
    """Median spacing between consecutive timestamps, in hours (None if <2)."""
    diffs = sorted((stamps[i + 1] - stamps[i]).total_seconds() for i in range(len(stamps) - 1))
    diffs = [d for d in diffs if d > 0]
    if not diffs:
        return None
    mid = len(diffs) // 2
    med = diffs[mid] if len(diffs) % 2 else (diffs[mid - 1] + diffs[mid]) / 2
    return med / 3600.0


def inspect_netcdf(path):
    """Inspect a NetCDF file's spatial extent and time dimension via GDAL.

    :return: dict with 'extent' (lat_min, lon_min, lat_max, lon_max), 'cell'
             (dx, dy in degrees) and, when a time axis is present, 'time'
             (min_dt, max_dt), 'time_step_hours' and 'calendar'.
    :raises ValueError: if the file cannot be opened or has no geospatial grid.
    """
    extent = cell = time_info = None
    for ds in _datasets(path):
        gt = ds.GetGeoTransform(can_return_null=True)
        if gt is None or ds.RasterXSize < 2 or ds.RasterYSize < 2:
            continue  # non-spatial variable (time_bnds, crs, …)
        if extent is None:
            extent, cell = spatial_extent(ds, gt)
        if time_info is None:
            time_info = time_axis(ds)
        if extent is not None and time_info is not None:
            break

    if extent is None:
        raise ValueError("no geospatial grid found (missing latitude/longitude)")

    info = {"extent": extent, "cell": cell}
    if time_info:
        stamps, calendar = time_info
        info["time"] = (stamps[0], stamps[-1])
        info["time_step_hours"] = median_step_hours(stamps)
        info["calendar"] = calendar
    return info


def lon_within(e_lon_min, e_lon_max, lon):
    """True if a WGS84 longitude falls in [e_lon_min, e_lon_max] under either the
    -180..180 or 0..360 convention."""
    return any(e_lon_min <= cand <= e_lon_max for cand in (lon, lon + 360, lon - 360))


def covers(extent, lat_min, lon_min, lat_max, lon_max):
    e_lat_min, e_lon_min, e_lat_max, e_lon_max = extent
    return (
        e_lat_min <= lat_min <= e_lat_max
        and e_lat_min <= lat_max <= e_lat_max
        and lon_within(e_lon_min, e_lon_max, lon_min)
        and lon_within(e_lon_min, e_lon_max, lon_max)
    )


def check_coverage(info, map_coords, departure, forecast_hours, require_time):
    """Cheap checks against ``inspect_netcdf`` output.

    Returns (state, message, warn). state is True (valid) or False (invalid);
    message is a short detail/error line for the drop zone. The heavy file
    inspection has already happened; this only compares extents and time
    ranges, so it is safe to run inline (e.g. on a forecast change).

    :param info: an ``inspect_netcdf`` result dict.
    :param map_coords: route bounds (lat_min, lon_min, lat_max, lon_max) or None.
    :param departure: routing start datetime, or None.
    :param forecast_hours: forecast horizon in hours (added to ``departure``).
    :param require_time: require a time dimension covering the routing period.
    """
    extent = info["extent"]
    checks = []
    warns = []

    if map_coords:
        lat_min, lon_min, lat_max, lon_max = map_coords
        if not covers(extent, lat_min, lon_min, lat_max, lon_max):
            e_lat_min, e_lon_min, e_lat_max, e_lon_max = extent
            return (
                False,
                f"Spatial coverage [{e_lat_min:.2f}°, {e_lon_min:.2f}°, "
                f"{e_lat_max:.2f}°, {e_lon_max:.2f}°] does not cover "
                f"map [{lat_min}°, {lon_min}°, {lat_max}°, {lon_max}°]",
                False,
            )
        checks.append("spatial ✓")

    if require_time:
        if "time" not in info:
            return (False, "No time dimension found (required for weather data)", False)
        if departure:
            end = departure + timedelta(hours=forecast_hours)
            t_min, t_max = info["time"]
            if not (t_min <= departure <= t_max and t_min <= end <= t_max):
                return (
                    False,
                    f"Time coverage [{t_min:%Y-%m-%d %H:%M}, "
                    f"{t_max:%Y-%m-%d %H:%M}] does not cover routing period "
                    f"[{departure:%Y-%m-%d %H:%M}, {end:%Y-%m-%d %H:%M}]",
                    False,
                )
            checks.append("time ✓")

    detail = "  ".join(checks) if checks else "structure OK"
    if warns:
        return True, detail + "  ⚠ " + "; ".join(warns), True
    return True, detail, False


class InspectNetcdfTask(QgsTask):
    """Run the heavy ``inspect_netcdf`` off the UI thread.

    ``run`` executes on a worker thread and only calls the GUI-free
    ``inspect_netcdf`` (safe to call there); a raised error is captured rather
    than failing the task, since an unreadable file is a validation result, not
    a task failure. ``finished`` runs back on the main thread and emits ``done``
    with ``(info, error)`` for the page to render.
    """

    done = pyqtSignal(object, object)  # (info dict or None, exception or None)

    def __init__(self, path):
        super().__init__("Inspect NetCDF dataset", QgsTask.CanCancel)
        self.path = path
        self.info = None
        self.error = None

    def run(self):
        try:
            self.info = inspect_netcdf(self.path)
        except Exception as e:  # noqa: BLE001 — surfaced to the user as a result
            self.error = e
        return True

    def finished(self, _result):
        if not self.isCanceled():
            self.done.emit(self.info, self.error)
