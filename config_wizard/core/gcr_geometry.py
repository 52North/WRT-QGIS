"""Great-circle and rhumb-line route geometry."""

import math

EARTH_RADIUS_KM = 6371.0088  # IUGG mean radius
KM_PER_NAUTICAL_MILE = 1.852  # international definition


def km_to_nm(km):
    return km / KM_PER_NAUTICAL_MILE


def _isometric_lat(phi_rad):
    return math.log(math.tan(math.pi / 4 + phi_rad / 2))


def great_circle_distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two WGS84 points, in kilometres."""

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def rhumb_line_distance_km(lat1, lon1, lat2, lon2):
    """Constant-bearing (loxodrome) distance between two WGS84 points, in kilometres."""

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlam = math.radians(lon2 - lon1)
    if dlam > math.pi:
        dlam -= 2 * math.pi
    elif dlam < -math.pi:
        dlam += 2 * math.pi

    dpsi = _isometric_lat(phi2) - _isometric_lat(phi1)
    q = dphi / dpsi if abs(dpsi) > 1e-12 else math.cos(phi1)
    return math.hypot(dphi, q * dlam) * EARTH_RADIUS_KM


def great_circle_points(lat1, lon1, lat2, lon2, num_points=100):
    """Points along the great-circle path from (lat1, lon1) to (lat2, lon2)."""

    phi1, lam1 = math.radians(lat1), math.radians(lon1)
    phi2, lam2 = math.radians(lat2), math.radians(lon2)

    x1, y1, z1 = math.cos(phi1) * math.cos(lam1), math.cos(phi1) * math.sin(lam1), math.sin(phi1)
    x2, y2, z2 = math.cos(phi2) * math.cos(lam2), math.cos(phi2) * math.sin(lam2), math.sin(phi2)

    angular_dist = math.acos(max(-1.0, min(1.0, x1 * x2 + y1 * y2 + z1 * z2)))
    if angular_dist < 1e-12:  # coincident endpoints
        return [(lat1, lon1), (lat2, lon2)]

    points = []
    for i in range(num_points + 1):
        f = i / num_points
        a = math.sin((1 - f) * angular_dist) / math.sin(angular_dist)
        b = math.sin(f * angular_dist) / math.sin(angular_dist)
        x = a * x1 + b * x2
        y = a * y1 + b * y2
        z = a * z1 + b * z2
        points.append(
            (math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x)))
        )
    return points


def rhumb_line_points(lat1, lon1, lat2, lon2, num_points=100):
    """Points along the constant-bearing (loxodrome) path from source to destination."""

    phi1, lam1 = math.radians(lat1), math.radians(lon1)
    phi2 = math.radians(lat2)

    dlam = math.radians(lon2 - lon1)
    if dlam > math.pi:
        dlam -= 2 * math.pi
    elif dlam < -math.pi:
        dlam += 2 * math.pi

    psi1 = _isometric_lat(phi1)
    dpsi = _isometric_lat(phi2) - psi1

    points = []
    for i in range(num_points + 1):
        f = i / num_points
        phi = phi1 + f * (phi2 - phi1)
        psi = _isometric_lat(phi)
        lam = lam1 + (psi - psi1) * dlam / dpsi if abs(dpsi) > 1e-12 else lam1 + f * dlam
        lon_deg = math.degrees(lam)
        lon_deg = ((lon_deg + 180) % 360) - 180  # internal wrap to [-180, 180]
        points.append((math.degrees(phi), lon_deg))
    return points


def split_at_antimeridian(points):
    """Break a (lat, lon) polyline into segments wherever it crosses ±180°.

    Returns a list of segments, each of which is a list of (lat, lon) tuples.
    """
    if not points:
        return []

    segments = [[points[0]]]
    for (lat1, lon1), (lat2, lon2) in zip(points, points[1:], strict=False):
        raw_dlon = lon2 - lon1
        if raw_dlon > 180:
            lon2_unwrapped, boundary = lon2 - 360, -180.0
        elif raw_dlon < -180:
            lon2_unwrapped, boundary = lon2 + 360, 180.0
        else:
            segments[-1].append((lat2, lon2))
            continue

        span = lon2_unwrapped - lon1
        f = (boundary - lon1) / span if span else 0.0
        lat_cross = lat1 + f * (lat2 - lat1)
        segments[-1].append((lat_cross, boundary))
        segments.append([(lat_cross, -boundary), (lat2, lon2)])
    return segments
