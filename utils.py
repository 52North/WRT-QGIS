"""Shared QGIS helpers for the Weather Routing Tool plugin."""

from qgis.core import QgsProject, QgsRasterLayer


def ensure_openstreetmap_layer(plugin):
    """Ensure an OpenStreetMap basemap is present and active in the project."""
    project = QgsProject.instance()

    for layer in project.mapLayers().values():
        name = layer.name().strip().lower()
        source = layer.source().strip().lower()
        if "openstreetmap" in name or "openstreetmap" in source or "osm" in name:
            plugin.iface.setActiveLayer(layer)
            return layer

    osm_uri = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    osm_layer = QgsRasterLayer(osm_uri, "OpenStreetMap", "wms")

    if osm_layer.isValid():
        project.addMapLayer(osm_layer)
        plugin.iface.setActiveLayer(osm_layer)
        return osm_layer

    return None
