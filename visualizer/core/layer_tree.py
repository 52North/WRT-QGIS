"""QGIS layer tree utilities

Basically places the route json over weather NetCDF dataset in the QGIS layer tree.
Reorders the layers so that the route is always on top of the weather data.
"""

import contextlib

from qgis.core import QgsProject


def add_on_top(layers):
    """Register ``layers`` and stack them at the top of the tree."""

    project = QgsProject.instance()
    root = project.layerTreeRoot()
    for layer in layers:
        project.addMapLayer(layer, False)
        root.insertLayer(0, layer)


def raise_to_top(layers):
    """Reorder already-registered ``layers`` at the top, bottom of the list first."""

    root = QgsProject.instance().layerTreeRoot()
    for layer in layers:
        node = root.findLayer(layer.id())
        if node is None:
            continue
        parent = node.parent() or root
        clone = node.clone()
        root.insertChildNode(0, clone)
        parent.removeChildNode(node)


def set_visible(layers, is_visible):
    """Tick or untick ``layers`` in the Layers panel."""
    root = QgsProject.instance().layerTreeRoot()
    for layer in layers:
        node = root.findLayer(layer.id())
        if node is not None:
            node.setItemVisibilityChecked(is_visible)


def connect_visibility(layers, slot):
    """Call ``slot`` whenever one of ``layers`` is ticked or unticked in the tree.

    Returns the (node, slot) pairs so the caller can disconnect them before the
    layers go away.
    """
    root = QgsProject.instance().layerTreeRoot()
    connections = []
    for layer in layers:
        node = root.findLayer(layer.id())
        if node is None:
            continue
        node.visibilityChanged.connect(slot)
        connections.append((node, slot))
    return connections


def disconnect_visibility(connections):
    for node, slot in connections:
        # The node may already be gone, taken down with its layer.
        with contextlib.suppress(RuntimeError, TypeError):
            node.visibilityChanged.disconnect(slot)
