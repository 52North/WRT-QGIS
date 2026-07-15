import json
import math

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayer,
)

_SENTINEL = -99


def _no_data(v):
    """Return None if v equals the WRT sentinel (-99/-99.0), else return float(v)."""
    if v is None:
        return None
    try:
        fv = float(v)
        return None if fv == _SENTINEL else fv
    except (TypeError, ValueError):
        return None


def _nested_value(props, key):
    """Extract the scalar value from a nested {value: ..., unit: ...} property dict."""
    raw = props.get(key)
    if isinstance(raw, dict):
        return raw.get("value")
    return raw


def _initial_bearing(lat1, lon1, lat2, lon2):
    """Great-circle initial bearing (degrees, 0–360, 0=North clockwise) from point 1 to point 2."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


class RouteLoader:
    def __init__(self, geojson_path):
        with open(geojson_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self._waypoints = self._parse(data)

    def _parse(self, data):
        waypoints = []
        for feat in data.get("features", []):
            coords = feat["geometry"]["coordinates"]
            lon, lat = float(coords[0]), float(coords[1])
            props = feat["properties"]

            u = _no_data(_nested_value(props, "u_wind_speed"))
            v = _no_data(_nested_value(props, "v_wind_speed"))
            wind_speed = math.sqrt(u ** 2 + v ** 2) if (u is not None and v is not None) else None

            waypoints.append({
                "id": feat.get("id", len(waypoints)),
                "lon": lon,
                "lat": lat,
                "time": props.get("time", ""),
                "speed": _no_data(_nested_value(props, "speed")),
                "engine_power": _no_data(_nested_value(props, "engine_power")),
                "fuel_consumption": _no_data(_nested_value(props, "fuel_consumption")),
                "wave_height": _no_data(_nested_value(props, "wave_height")),
                "wind_speed": wind_speed,
                "bearing": 0.0,
            })

        for i in range(len(waypoints) - 1):
            wp, nxt = waypoints[i], waypoints[i + 1]
            if (nxt["lat"], nxt["lon"]) == (wp["lat"], wp["lon"]):
                # Duplicate waypoint: keep heading instead of snapping north
                wp["bearing"] = waypoints[i - 1]["bearing"] if i > 0 else 0.0
            else:
                wp["bearing"] = _initial_bearing(wp["lat"], wp["lon"], nxt["lat"], nxt["lon"])
        if len(waypoints) > 1:
            waypoints[-1]["bearing"] = waypoints[-2]["bearing"]

        return waypoints

    @property
    def waypoints(self):
        return self._waypoints

    def build_line_layer(self):
        layer = QgsVectorLayer("LineString?crs=EPSG:4326", "WRT Route", "memory")
        feat = QgsFeature()
        feat.setGeometry(
            QgsGeometry.fromPolylineXY(
                [QgsPointXY(wp["lon"], wp["lat"]) for wp in self._waypoints]
            )
        )
        layer.dataProvider().addFeature(feat)
        layer.updateExtents()
        return layer

    def build_markers_layer(self):
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "WRT Route Markers", "memory")
        dp = layer.dataProvider()
        dp.addAttributes([
            QgsField("role", QVariant.String),
            QgsField("label", QVariant.String),
        ])
        layer.updateFields()
        pairs = [
            (self._waypoints[0],  "source",      "Source"),
            (self._waypoints[-1], "destination", "Destination"),
        ]
        feats = []
        for wp, role, label in pairs:
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(wp["lon"], wp["lat"])))
            f.setAttributes([role, label])
            feats.append(f)
        dp.addFeatures(feats)
        layer.updateExtents()
        return layer

    def build_point_layer(self):
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "WRT Waypoints", "memory")
        dp = layer.dataProvider()
        dp.addAttributes([
            QgsField("id", QVariant.Int),
            QgsField("time", QVariant.String),
            QgsField("speed", QVariant.Double),
            QgsField("power", QVariant.Double),
            QgsField("fuel", QVariant.Double),
            QgsField("wave_h", QVariant.Double),
            QgsField("wind_spd", QVariant.Double),
            QgsField("bearing", QVariant.Double),
        ])
        layer.updateFields()

        feats = []
        for wp in self._waypoints:
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(wp["lon"], wp["lat"])))
            f.setAttributes([
                wp["id"],
                wp["time"],
                wp["speed"],
                wp["engine_power"],
                wp["fuel_consumption"],
                wp["wave_height"],
                wp["wind_speed"],
                wp["bearing"],
            ])
            feats.append(f)
        dp.addFeatures(feats)
        layer.updateExtents()
        return layer

    def build_boat_layer(self):
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "WRT Boat", "memory")
        dp = layer.dataProvider()
        dp.addAttributes([QgsField("bearing", QVariant.Double)])
        layer.updateFields()

        wp = self._waypoints[0]
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(wp["lon"], wp["lat"])))
        f.setAttributes([wp["bearing"]])
        dp.addFeature(f)
        layer.updateExtents()
        return layer
