import os

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsGeometry, QgsPointXY, QgsProject

SAILBOAT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "sailboat.svg")
FLAG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "flag.svg")

_STAT_FIELDS = [
    ("speed",            "Speed",             "m/s"),
    ("engine_power",     "Engine Power",      "kW"),
    ("fuel_consumption", "Fuel Consumption",  "t/h"),
]

_ADVANCED_STAT_FIELDS = [
    ("wave_height",      "Wave Height",       "m"),
    ("wind_speed",       "Wind Speed",        "m/s"),
]

class RouteVisualizerPanel(QDockWidget):
    def __init__(self, iface):
        super().__init__("WRT Route Visualizer")
        self.iface = iface
        self._waypoints = []
        self._line_layer = None
        self._point_layer = None
        self._markers_layer = None
        self._boat_layer = None
        self._boat_fid = None
        self._boat_bearing_idx = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)

        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # Load button
        load_btn = QPushButton("Load Route GeoJSON…")
        load_btn.clicked.connect(self._load_route)
        layout.addWidget(load_btn)

        # Progress / timestamp labels
        self._progress_label = QLabel("No route loaded")
        self._time_label = QLabel("")
        self._time_label.setStyleSheet("color: gray;")
        layout.addWidget(self._progress_label)
        layout.addWidget(self._time_label)

        # Slider
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setEnabled(False)
        self._slider.setTickPosition(QSlider.TicksBelow)
        self._slider.setTickInterval(1)
        self._slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self._slider)

        # Playback controls
        ctrl = QHBoxLayout()
        self._play_btn = QPushButton("▶  Play")
        self._play_btn.setEnabled(False)
        self._play_btn.clicked.connect(self._toggle_play)
        ctrl.addWidget(self._play_btn)

        ctrl.addWidget(QLabel("ms/step:"))
        self._speed_spin = QSpinBox()
        self._speed_spin.setRange(50, 2000)
        self._speed_spin.setValue(400)
        self._speed_spin.setSuffix(" ms")
        self._speed_spin.valueChanged.connect(
            lambda v: self._timer.isActive() and self._timer.setInterval(v)
        )
        ctrl.addWidget(self._speed_spin)
        layout.addLayout(ctrl)

        # Stats panel
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.StyledPanel)
        grid = QGridLayout(stats_frame)
        grid.setSpacing(4)

        self._stat_value_labels = {}
        for row, (key, title, unit) in enumerate(_STAT_FIELDS):
            grid.addWidget(QLabel(f"<b>{title}</b>"), row, 0)
            val_lbl = QLabel("—")
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._stat_value_labels[key] = (val_lbl, unit)
            grid.addWidget(val_lbl, row, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        base = len(_STAT_FIELDS)
        grid.addWidget(sep, base, 0, 1, 2)

        for i, (label, key) in enumerate([("Latitude", "lat"), ("Longitude", "lon")]):
            grid.addWidget(QLabel(f"<b>{label}</b>"), base + 1 + i, 0)
            lbl = QLabel("—")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            setattr(self, f"_{key}_label", lbl)
            grid.addWidget(lbl, base + 1 + i, 1)

        layout.addWidget(stats_frame)

        # Advanced (collapsible) stats
        self._advanced_btn = QToolButton()
        self._advanced_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._advanced_btn.setArrowType(Qt.RightArrow)
        self._advanced_btn.setText("Advanced")
        self._advanced_btn.setCheckable(True)
        self._advanced_btn.setChecked(False)
        self._advanced_btn.setStyleSheet("QToolButton { border: none; }")
        self._advanced_btn.clicked.connect(self._toggle_advanced)
        layout.addWidget(self._advanced_btn)

        self._advanced_frame = QFrame()
        self._advanced_frame.setFrameShape(QFrame.StyledPanel)
        adv_grid = QGridLayout(self._advanced_frame)
        adv_grid.setSpacing(4)
        for row, (key, title, unit) in enumerate(_ADVANCED_STAT_FIELDS):
            adv_grid.addWidget(QLabel(f"<b>{title}</b>"), row, 0)
            val_lbl = QLabel("—")
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._stat_value_labels[key] = (val_lbl, unit)
            adv_grid.addWidget(val_lbl, row, 1)
        self._advanced_frame.setVisible(False)
        layout.addWidget(self._advanced_frame)

        layout.addStretch()
        self.setWidget(root)

    def _toggle_advanced(self, checked):
        self._advanced_frame.setVisible(checked)
        self._advanced_btn.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    def _load_route(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open WRT Route GeoJSON",
            "",
            "GeoJSON / JSON (*.json *.geojson);;All files (*)",
        )
        if not path:
            return

        # Stop any running animation
        if self._timer.isActive():
            self._timer.stop()
            self._play_btn.setText("▶  Play")

        # Remove previously loaded layers
        self.clear_layers()

        try:
            from ..core.route_loader import RouteLoader
            from ..styling.route_styler import (
                style_boat_marker,
                style_markers_layer,
                style_route_line,
            )

            project = QgsProject.instance()
            loader = RouteLoader(path)
            self._waypoints = loader.waypoints

            self._line_layer = loader.build_line_layer()
            self._point_layer = loader.build_point_layer()
            self._markers_layer = loader.build_markers_layer()
            self._boat_layer = loader.build_boat_layer()

            # Point layer added first so it sits beneath the styled route/boat,
            # but its per-waypoint attributes stay clickable via Identify.
            project.addMapLayer(self._point_layer)
            project.addMapLayer(self._line_layer)
            project.addMapLayer(self._markers_layer)
            project.addMapLayer(self._boat_layer)

            style_route_line(self._line_layer)
            style_markers_layer(self._markers_layer, FLAG_PATH)
            style_boat_marker(self._boat_layer, SAILBOAT_PATH)

            # Cache boat feature id and the bearing field index (by name)
            for f in self._boat_layer.getFeatures():
                self._boat_fid = f.id()
                break
            self._boat_bearing_idx = self._boat_layer.fields().indexOf("bearing")

            n = len(self._waypoints)
            self._slider.setRange(0, n - 1)
            self._slider.setTickInterval(1)
            self._slider.setValue(0)
            self._slider.setEnabled(True)
            self._play_btn.setEnabled(True)
            self._progress_label.setText(f"Waypoint 1 / {n}")
            self._update_stats(self._waypoints[0])

            # Zoom canvas to route extent
            canvas = self.iface.mapCanvas()
            ext = self._line_layer.extent()
            ext.scale(1.1)
            canvas.setExtent(ext)
            canvas.refresh()

        except Exception as exc:
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Route load error", str(exc))

    def _on_slider_changed(self, idx):
        if not self._waypoints:
            return
        wp = self._waypoints[idx]
        n = len(self._waypoints)
        self._progress_label.setText(f"Waypoint {idx + 1} / {n}")
        self._time_label.setText(wp.get("time", ""))
        self._move_boat(wp)
        self._update_stats(wp)

    def _move_boat(self, wp):
        layer = self._boat_layer
        if layer is None or self._boat_fid is None:
            return
        # Update the boat feature's geometry and bearing attribute in the layer's data provider
        dp = layer.dataProvider()
        dp.changeGeometryValues(
            {self._boat_fid: QgsGeometry.fromPointXY(QgsPointXY(wp["lon"], wp["lat"]))}
        )
        if self._boat_bearing_idx is not None and self._boat_bearing_idx >= 0:
            dp.changeAttributeValues(
                {self._boat_fid: {self._boat_bearing_idx: wp["bearing"]}}
            )
        layer.triggerRepaint()

    def _toggle_play(self):
        if self._timer.isActive():
            self._timer.stop()
            self._play_btn.setText("▶  Play")
        else:
            if self._slider.value() >= len(self._waypoints) - 1:
                self._slider.setValue(0)
            self._timer.start(self._speed_spin.value())
            self._play_btn.setText("⏸  Pause")

    def _on_timer_tick(self):
        current = self._slider.value()
        if current >= len(self._waypoints) - 1:
            self._timer.stop()
            self._play_btn.setText("▶  Play")
            return
        self._slider.setValue(current + 1)

    def _update_stats(self, wp):
        for key, (lbl, unit) in self._stat_value_labels.items():
            val = wp.get(key)
            if val is None:
                lbl.setText("—")
            else:
                lbl.setText(f"{val:.4g} {unit}")
        self._lat_label.setText(f"{wp['lat']:.6f} °")
        self._lon_label.setText(f"{wp['lon']:.6f} °")

    def clear_layers(self):
        project = QgsProject.instance()
        for layer in (self._line_layer, self._point_layer, self._markers_layer, self._boat_layer):
            if layer is not None and layer.id() in project.mapLayers():
                project.removeMapLayer(layer.id())
        self._line_layer = self._point_layer = self._markers_layer = self._boat_layer = None
        self._boat_fid = None
        self._boat_bearing_idx = None

    def closeEvent(self, event):
        if self._timer.isActive():
            self._timer.stop()
        self.clear_layers()
        super().closeEvent(event)
