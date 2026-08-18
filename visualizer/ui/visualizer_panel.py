"""The Data Visualizer dock: sources, layers, and the per-instant readouts."""

import os

from qgis.core import (
    QgsApplication,
    QgsDateTimeRange,
    QgsGeometry,
    QgsLayerTreeLayer,
    QgsPointXY,
    QgsProject,
)
from qgis.PyQt import sip
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...config_wizard.ui.ui_kit import COLOR_MUTED, collapsible
from ..core import layer_tree
from ..core.timeline import ROUTE, WEATHER
from ..styling.mesh_styler import color_ramp_for
from .color_palette import (
    MONO_FAMILY,
    ROUTE_COLOR,
    ROUTE_TINT,
    ROUTE_TINT_BORDER,
    WEATHER_COLOR,
)
from .layer_card import LayerCard
from .map_legend import MapColorbarLegend
from .readout import SEPARATOR, StatCard, format_value
from .region_stats import RegionStatsSection
from .source_chip import PendingChip, SourceChip, format_span
from .vector_layer_card import AxisProxy, VectorLayerCard

FLAG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "flag.svg")
BOAT_PUCK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "resources", "boat_puck.svg"
)

WEATHER_LAYER_NAME = "WRT Weather data"

# Dock width contraints
_MIN_DOCK_WIDTH = 400
_MAX_DOCK_WIDTH = 500

# Route layer contains the line, the waypoints, the flags and the boat; the four layers are stacked in this order.
_ROUTE_CARD = {
    "index": ROUTE,
    "kind": "route",
    "name": "Route track",
    "default_opacity": 100,
}

_VESSEL_FIELDS = [
    ("speed", "Speed", "m/s"),
    ("engine_power", "Engine pwr", "kW"),
    ("fuel_consumption", "Fuel", "t/h"),
    ("bearing", "Heading", "°"),
]

_SECTION_QSS = f"""
QLabel#Section {{ font-size: 10px; font-weight: 600; letter-spacing: 0.5px;
                  color: {COLOR_MUTED}; }}
QLabel#Hint {{ font-size: 10px; color: {COLOR_MUTED}; }}
QLabel#TimePill {{ font-family: {MONO_FAMILY}; font-size: 10px; font-weight: 600;
                   color: {WEATHER_COLOR}; background: #e7f0fd;
                   border-radius: 4px; padding: 2px 6px; }}
"""


def _section(text):
    label = QLabel(text.upper())
    label.setObjectName("Section")
    return label


def _resolve(index, sequence):
    """An index only counts while it still addresses something in ``sequence``.

    Resolve timestamps to the route or weather dataset, but if the dataset is unloaded
    the index is no longer valid and must be ignored.
    """
    if index is None or not 0 <= index < len(sequence):
        return None
    return index


class VisualizerPanel(QDockWidget):
    # A dataset was loaded or unloaded; the timeline dock must re-read the clock.
    sources_changed = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, iface, timeline, parent=None):
        super().__init__("Data Visualizer", parent)
        self.iface = iface
        self._timeline = timeline

        self._waypoints = []
        self._route_layers = []
        self._boat_layer = None
        self._boat_fid = None
        self._boat_bearing_idx = None
        self._route_chip = None

        self._mesh_loader = None
        self._mesh_layer = None
        self._mesh_task = None
        self._weather_chip = None
        self._pending_chip = None
        self._cards = {}
        self._active = {"scalar": None, "vector": None}

        self._route_index = None
        self._weather_index = None

        self._tree_connections = []
        self._is_syncing = False

        self._legend = None
        self._advanced_box = None
        self._region_stats = None

        self.setMinimumWidth(_MIN_DOCK_WIDTH)
        self.setMaximumWidth(_MAX_DOCK_WIDTH)

        self._build_ui()

    # UI

    def _build_ui(self):
        root = QWidget()
        root.setStyleSheet(_SECTION_QSS)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(12, 12, 12, 14)
        layout.setSpacing(14)

        layout.addWidget(self._build_sources())
        layout.addWidget(self._build_layers())
        layout.addWidget(self._build_readouts())

        self._build_advanced(layout)

        layout.addStretch()
        scroll.setWidget(host)
        outer.addWidget(scroll)
        self.setWidget(root)

    def _build_advanced(self, layout):
        advanced_btn, advanced_box = collapsible("Advanced")
        # Collapsible returns a box that is hidden by default.
        box_layout = QVBoxLayout(advanced_box)
        box_layout.setContentsMargins(6, 6, 6, 6)
        box_layout.setSpacing(7)
        box_layout.addWidget(_section("Region statistics"))

        self._region_stats = RegionStatsSection(self.iface)
        box_layout.addWidget(self._region_stats)
        self._advanced_box = advanced_box

        # Take care of the toggle button's text and the box's visibility in one place.
        advanced_btn.clicked.connect(
            lambda: self._region_stats.set_collapsed(not advanced_box.isVisible())
        )
        layout.addWidget(advanced_btn)
        layout.addWidget(advanced_box)

    def _build_sources(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        layout.addWidget(_section("Data sources"))

        self._route_btn = QPushButton("🚢  Load Route (GeoJSON)…")
        self._route_btn.clicked.connect(self._load_route)
        layout.addWidget(self._route_btn)

        self._weather_btn = QPushButton("🌊  Load Weather (NetCDF)…")
        self._weather_btn.clicked.connect(self._load_weather)
        layout.addWidget(self._weather_btn)

        self._chips_layout = QVBoxLayout()
        self._chips_layout.setSpacing(6)
        layout.addLayout(self._chips_layout)

        self._status_label = QLabel("No dataset loaded")
        self._status_label.setObjectName("Hint")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)
        return box

    def _build_layers(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        self._layers_label = _section("Available layers")
        self._layers_label.setVisible(False)
        layout.addWidget(self._layers_label)

        self._hint_label = QLabel(
            "One surface and one vector field at a time. A vector field can show both at once."
        )
        self._hint_label.setObjectName("Hint")
        self._hint_label.setWordWrap(True)
        self._hint_label.setVisible(False)
        layout.addWidget(self._hint_label)

        self._cards_layout = QVBoxLayout()
        self._cards_layout.setSpacing(6)
        layout.addLayout(self._cards_layout)
        return box

    def _build_readouts(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        header = QHBoxLayout()
        header.addWidget(_section("Current parameters"))
        header.addStretch()
        self._time_pill = QLabel("—")
        self._time_pill.setObjectName("TimePill")
        header.addWidget(self._time_pill)
        layout.addLayout(header)

        self._vessel_card = StatCard("Vessel", ROUTE_COLOR, ROUTE_TINT, ROUTE_TINT_BORDER)
        layout.addWidget(self._vessel_card)

        self._refresh_vessel_card()
        return box

    # sources

    def _add_chip(self, icon, path, meta, accent, on_unload):
        chip = SourceChip(icon, os.path.basename(path), meta, accent)
        chip.unloaded.connect(on_unload)
        self._chips_layout.addWidget(chip)
        return chip

    def _drop_chip(self, chip):
        if chip is not None:
            self._chips_layout.removeWidget(chip)
            chip.deleteLater()

    def _load_route(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open WRT Route GeoJSON",
            "",
            "GeoJSON / JSON (*.json *.geojson);;All files (*)",
        )
        if not path:
            return

        self.unload_route()
        try:
            self._build_route_layers(path)
        except Exception as exc:
            QMessageBox.critical(self, "Route load error", str(exc))
            self.unload_route()
            return

        self._timeline.set_stamps(ROUTE, [wp["datetime"] for wp in self._waypoints])
        bounds = self._timeline.bounds(ROUTE)
        self._route_chip = self._add_chip(
            "🚢",
            path,
            f"{len(self._waypoints)} wpts · {format_span(bounds)}",
            ROUTE_COLOR,
            self.unload_route,
        )
        self._add_card(_ROUTE_CARD, checked=True)
        self._zoom_to(self._route_layers[0])
        self._on_sources_changed()

    def _build_route_layers(self, path):
        from ..core.route_loader import RouteLoader
        from ..styling.route_styler import (
            style_boat_marker,
            style_markers_layer,
            style_route_line,
        )

        loader = RouteLoader(path)
        self._waypoints = loader.waypoints

        line_layer = loader.build_line_layer()
        point_layer = loader.build_point_layer()
        markers_layer = loader.build_markers_layer()
        self._boat_layer = loader.build_boat_layer()

        # The whole stack goes above the weather mesh and any basemap.
        self._route_layers = [point_layer, line_layer, markers_layer, self._boat_layer]
        layer_tree.add_on_top(self._route_layers)
        self._rewatch_visibility()

        style_route_line(line_layer)
        style_markers_layer(markers_layer, FLAG_PATH)
        style_boat_marker(self._boat_layer, BOAT_PUCK_PATH)

        # Cache boat feature id and the bearing field index (by name)
        for boat_feature in self._boat_layer.getFeatures():
            self._boat_fid = boat_feature.id()
            break
        self._boat_bearing_idx = self._boat_layer.fields().indexOf("bearing")

    def _load_weather(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open weather NetCDF", "", "NetCDF (*.nc);;All files (*)"
        )
        if not path:
            return

        self.unload_weather()

        from ..core.mesh_loader import LoadWeatherMeshTask

        self._set_loading(True, path)
        self._mesh_task = LoadWeatherMeshTask(path)
        self._mesh_task.done.connect(self._on_weather_loaded)
        QgsApplication.taskManager().addTask(self._mesh_task)

    def _set_loading(self, is_loading, path=None):
        """Hold the dataset's place in the chip list while its file is read."""
        self._weather_btn.setEnabled(not is_loading)
        if is_loading:
            self._pending_chip = PendingChip(os.path.basename(path), WEATHER_COLOR)
            self._chips_layout.addWidget(self._pending_chip)
            self._status_label.setText("Opening dataset…")
        else:
            self._drop_chip(self._pending_chip)
            self._pending_chip = None

    def _on_weather_loaded(self, loader, exc):
        self._mesh_task = None
        self._set_loading(False)
        if exc is not None or loader is None:
            QMessageBox.critical(
                self, "Weather data load error", str(exc) if exc else "Unknown error"
            )
            self._on_sources_changed()
            return

        self._mesh_loader = loader
        self._mesh_layer = loader.layer
        self._mesh_layer.setName(WEATHER_LAYER_NAME)

        # Nothing is active yet, so the layer starts blank.
        from ..styling.mesh_styler import clear

        clear(self._mesh_layer, "scalar")
        clear(self._mesh_layer, "vector")
        layer_tree.add_on_top([self._mesh_layer])
        # Reordering the route layers above the mesh layers.
        layer_tree.raise_to_top(self._route_layers)
        self._rewatch_visibility()

        self._timeline.set_stamps(WEATHER, loader.timestamps)
        bounds = self._timeline.bounds(WEATHER)
        self._weather_chip = self._add_chip(
            "🌊",
            loader.path,
            f"{len(loader.timestamps)} frames · {format_span(bounds)}",
            WEATHER_COLOR,
            self.unload_weather,
        )
        for i, variable in enumerate(loader.variables):
            if variable["kind"] == "vector":
                self._add_vector_card(variable, checked_vectors=(i == 0))
            else:
                self._add_card(variable, checked=(i == 0))
        self._region_stats.set_source(self._mesh_layer, self._mesh_loader)
        if not self._route_layers:
            self._zoom_to(self._mesh_layer)
        self._on_sources_changed()

    def unload_route(self):
        layer_tree.disconnect_visibility(self._tree_connections)
        self._tree_connections = []
        project = QgsProject.instance()
        for layer in self._route_layers:
            if not sip.isdeleted(layer) and layer.id() in project.mapLayers():
                project.removeMapLayer(layer.id())
        self._route_layers = []
        self._boat_layer = None
        self._boat_fid = None
        self._boat_bearing_idx = None
        self._waypoints = []
        # Resolve the timeline to nothing, so the vessel card shows "before start" rather than stale data.
        self._timeline.clear(ROUTE)
        self._route_index = None
        self._drop_chip(self._route_chip)
        self._route_chip = None
        self._drop_card((ROUTE, "route"))
        self._rewatch_visibility()
        self._on_sources_changed()

    def unload_weather(self):
        layer_tree.disconnect_visibility(self._tree_connections)
        self._tree_connections = []
        project = QgsProject.instance()
        if (
            self._mesh_layer is not None
            and not sip.isdeleted(self._mesh_layer)
            and self._mesh_layer.id() in project.mapLayers()
        ):
            project.removeMapLayer(self._mesh_layer.id())
        self._mesh_layer = None
        self._mesh_loader = None
        # Resolve the timeline to nothing, so the weather card shows "before start" rather than stale data.
        self._timeline.clear(WEATHER)
        self._weather_index = None
        self._active = {"scalar": None, "vector": None}
        self._region_stats.set_source(None, None)
        self._drop_chip(self._weather_chip)
        self._weather_chip = None
        for key in [k for k in self._cards if k[0] != ROUTE]:
            self._drop_card(key)
        self._rewatch_visibility()
        self._sync_legend()
        self._on_sources_changed()

    def _on_sources_changed(self):
        has_cards = bool(self._cards)
        self._layers_label.setVisible(has_cards)
        self._hint_label.setVisible(self._mesh_layer is not None)

        parts = []
        if self._waypoints:
            parts.append(f"{len(self._waypoints)} waypoints")
        if self._mesh_loader is not None:
            parts.append(f"{len(self._mesh_loader.variables)} weather variables")
            parts.append(f"{len(self._mesh_loader.timestamps)} time steps")
        self._status_label.setText(" · ".join(parts) if parts else "No dataset loaded")
        self.sources_changed.emit()

    # layers

    def _add_card(self, variable, checked=False):
        card = LayerCard(variable)
        card.toggled.connect(lambda on, v=variable: self._on_card_toggled(v, on))
        card.opacity_changed.connect(lambda value, v=variable: self._on_opacity_changed(v, value))
        self._cards[(variable["index"], variable["kind"])] = card
        self._cards_layout.addWidget(card)
        if checked:
            card.set_checked(True)

    def _add_vector_card(self, variable, checked_vectors=False):
        """A vector field's two ticks, both driving the same dataset group."""
        card = VectorLayerCard(variable)
        card.colormap_toggled.connect(
            lambda on, v=variable: self._on_card_toggled(v, on, axis="scalar")
        )
        card.vectors_toggled.connect(
            lambda on, v=variable: self._on_card_toggled(v, on, axis="vector")
        )
        card.opacity_changed.connect(
            lambda value, v=variable: self._on_vector_opacity_changed(v, value)
        )
        for axis in ("scalar", "vector"):
            self._cards[(variable["index"], axis)] = AxisProxy(card, axis)
        self._cards_layout.addWidget(card)
        if checked_vectors:
            card.set_checked("vector", True)

    def _on_vector_opacity_changed(self, variable, value):
        """One slider, both axes — whichever of them is actually drawn."""
        self._on_opacity_changed(variable, value, axis="scalar")
        self._on_opacity_changed(variable, value, axis="vector")

    def _drop_card(self, key):
        card = self._cards.pop(key, None)
        if card is None:
            return
        # A vector chip is held under both of its axes; the first drop takes the
        # widget away and the second finds it already gone.
        widget = getattr(card, "widget", card)
        if sip.isdeleted(widget):
            return
        self._cards_layout.removeWidget(widget)
        widget.deleteLater()

    def _on_card_toggled(self, variable, enabled, axis=None):
        """``axis`` lets a card drive an axis other than the variable's own kind.

        A vector chip's colormap tick paints the group's magnitude through the
        scalar axis, even though the group itself is vector-kind.
        """
        axis = axis or variable["kind"]
        if axis == "route":
            opacity = self._cards[(ROUTE, "route")].opacity()
            for layer in self._route_layers:
                layer.setOpacity(opacity)
                layer.triggerRepaint()
            self._set_tree_visible(self._route_layers, enabled)
            return

        if self._mesh_layer is None:
            return
        # A variable can only draw if the mesh layer itself is ticked.
        if enabled:
            self._set_tree_visible([self._mesh_layer], True)
        from ..styling.mesh_styler import apply_scalar, apply_vector, clear

        if not enabled:
            if self._active[axis] == variable["index"]:
                self._active[axis] = None
                clear(self._mesh_layer, axis)
            self._sync_legend()
            self._region_stats.set_variables(self._active_variables())
            return

        # One group per axis: drop whatever was showing there.
        previous = self._active[axis]
        if previous is not None and previous != variable["index"]:
            card = self._cards.get((previous, axis))
            if card is not None:
                card.set_checked_silently(False)

        self._active[axis] = variable["index"]
        apply_fn = apply_scalar if axis == "scalar" else apply_vector
        apply_fn(self._mesh_layer, variable, self._cards[(variable["index"], axis)].opacity())
        self._sync_legend()
        self._region_stats.set_variables(self._active_variables())

    def _on_opacity_changed(self, variable, value, axis=None):
        axis = axis or variable["kind"]
        if axis == "route":
            for layer in self._route_layers:
                layer.setOpacity(value)
                layer.triggerRepaint()
            return
        if self._mesh_layer is None or self._active[axis] != variable["index"]:
            return
        from ..styling.mesh_styler import apply_scalar, apply_vector

        apply_fn = apply_scalar if axis == "scalar" else apply_vector
        apply_fn(self._mesh_layer, variable, value)

    # map legend

    def _active_variable(self, kind):
        """The variable dict behind the group currently drawn on one axis."""
        index = self._active[kind]
        if self._mesh_loader is None or index is None:
            return None
        return next(
            (variable for variable in self._mesh_loader.variables if variable["index"] == index),
            None,
        )

    def _active_scalar(self):
        return self._active_variable("scalar")

    def _active_variables(self):
        """Both drawn groups, scalar first — what the region statistics shows.

        A vector field ticked on both axes is one group, so it is listed once.
        """
        drawn = (self._active_variable("scalar"), self._active_variable("vector"))
        seen = set()
        variables = []
        for variable in drawn:
            if variable is None or variable["index"] in seen:
                continue
            seen.add(variable["index"])
            variables.append(variable)
        return variables

    def _sync_legend(self):
        """Mirror the drawn scalar group onto the canvas legend, or take it down."""
        variable = self._active_scalar()
        if variable is None:
            if self._legend is not None:
                self._legend.hide()
            return
        if self._legend is None:
            self._legend = MapColorbarLegend(self.iface.mapCanvas())
        ramp, _ = color_ramp_for(variable["name"])
        self._legend.show_variable(variable, ramp)

    # tree sync

    def _rewatch_visibility(self):
        """Re-subscribe after layers are added, re-stacked or dropped.

        ``raise_to_top`` swaps a node for a clone, so connections made earlier
        point at nodes that have left the tree.
        """
        layer_tree.disconnect_visibility(self._tree_connections)
        watched = list(self._route_layers)
        if self._mesh_layer is not None:
            watched.append(self._mesh_layer)
        self._tree_connections = layer_tree.connect_visibility(watched, self._on_tree_visibility)

    def _set_tree_visible(self, layers, is_visible):
        """Tick layers in the Layers panel without it echoing back to the cards."""
        self._is_syncing = True
        try:
            layer_tree.set_visible(layers, is_visible)
        finally:
            self._is_syncing = False

    def _on_tree_visibility(self, node):
        """A layer was ticked or unticked in the QGIS Layers panel; follow it."""
        if self._is_syncing or not isinstance(node, QgsLayerTreeLayer):
            return
        is_visible = node.itemVisibilityChecked()

        if self._mesh_layer is not None and node.layerId() == self._mesh_layer.id():
            # Hiding the mesh leaves no axis on screen, so no variable is active.
            if not is_visible:
                for card in [c for k, c in self._cards.items() if k[0] != ROUTE]:
                    if card.is_checked():
                        card.set_checked(False)
            return

        # The four route layers are one card, so any of them drags the rest along.
        route_card = self._cards.get((ROUTE, "route"))
        if route_card is not None and route_card.is_checked() != is_visible:
            route_card.set_checked_silently(is_visible)
            self._set_tree_visible(self._route_layers, is_visible)

    def _zoom_to(self, layer):
        canvas = self.iface.mapCanvas()
        extent = canvas.mapSettings().layerExtentToOutputExtent(layer, layer.extent())
        if extent.isEmpty():
            return
        extent.scale(1.1)
        canvas.setExtent(extent)
        canvas.refresh()

    # clock

    def on_time_changed(self, step_index):
        """Resolve one shared instant onto each dataset independently."""
        steps = self._timeline.steps
        if not steps:
            return
        stamp = steps[min(step_index, len(steps) - 1)]
        self._time_pill.setText(stamp.toString("HH:mm 'UTC'"))

        # Resolve the timeline's index into the route and weather datasets, if any.
        self._route_index = _resolve(self._timeline.index_at(ROUTE, stamp), self._waypoints)
        if self._route_index is not None:
            self._move_boat(self._waypoints[self._route_index])

        timestamps = self._mesh_loader.timestamps if self._mesh_loader is not None else []
        self._weather_index = _resolve(self._timeline.index_at(WEATHER, stamp), timestamps)
        if self._weather_index is not None:
            frame = timestamps[self._weather_index]
            if frame.isValid():
                # Mesh layers pick their timestep from the canvas temporal range.
                self.iface.mapCanvas().setTemporalRange(QgsDateTimeRange(frame, frame))
        self._region_stats.set_frame(self._weather_index)

        self._refresh_vessel_card()

    def snap_boat_to_route_start(self):
        if self._waypoints:
            self._route_index = 0
            self._move_boat(self._waypoints[0])

    def snap_boat_to_route_end(self):
        if self._waypoints:
            self._route_index = len(self._waypoints) - 1
            self._move_boat(self._waypoints[-1])

    def _move_boat(self, waypoint):
        layer = self._boat_layer
        if layer is None or self._boat_fid is None:
            return
        # Update the boat feature's geometry and bearing attribute in the layer's data provider.
        data_provider = layer.dataProvider()
        data_provider.changeGeometryValues(
            {self._boat_fid: QgsGeometry.fromPointXY(QgsPointXY(waypoint["lon"], waypoint["lat"]))}
        )
        if self._boat_bearing_idx is not None and self._boat_bearing_idx >= 0:
            data_provider.changeAttributeValues(
                {self._boat_fid: {self._boat_bearing_idx: waypoint["bearing"]}}
            )
        layer.triggerRepaint()

    # readouts

    def _refresh_vessel_card(self):
        if self._route_index is None:
            self._vessel_card.set_title("Vessel")
            self._vessel_card.set_rows(
                [("Route", "not loaded" if not self._waypoints else "before start")]
            )
            return

        waypoint = self._waypoints[self._route_index]
        self._vessel_card.set_title(f"Vessel · WP {self._route_index + 1}")
        rows = [
            (title, format_value(waypoint.get(key), unit)) for key, title, unit in _VESSEL_FIELDS
        ]
        rows.append(SEPARATOR)
        rows.append(("Lat", f"{waypoint['lat']:.4f}°"))
        rows.append(("Lon", f"{waypoint['lon']:.4f}°"))
        self._vessel_card.set_rows(rows)

    # teardown

    def clear_layers(self):
        try:
            self.unload_route()
            self.unload_weather()
        finally:
            # Unload the region stats and legend before the panel is destroyed,
            # Safety check
            if self._region_stats is not None:
                self._region_stats.teardown()
            if self._legend is not None:
                self._legend.detach()
                self._legend = None

    def closeEvent(self, event):
        self.clear_layers()
        self.closed.emit()
        super().closeEvent(event)
