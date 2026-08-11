import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QCursor, QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu

from .config_wizard.ui.wizard import WRTConfigWindow
from .utils import ensure_openstreetmap_layer
from .visualizer.core.timeline import Timeline
from .visualizer.ui.timeline_dock import TimelineDock
from .visualizer.ui.visualizer_panel import VisualizerPanel


class WRTPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.config_action = None
        self.visualize_action = None
        self._window = None
        self._panel = None
        self._timeline_dock = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self.action = QAction(icon, "Weather Routing Tool", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)

        self.config_action = QAction(icon, "Config Wizard", self.iface.mainWindow())
        self.config_action.triggered.connect(self.open_config_wizard)

        self.visualize_action = QAction(icon, "Data Visualizer", self.iface.mainWindow())
        self.visualize_action.triggered.connect(self.toggle_visualizer)

        self.iface.addPluginToMenu("Weather Routing Tool", self.config_action)
        self.iface.addPluginToMenu("Weather Routing Tool", self.visualize_action)

    def unload(self):
        if self._panel is not None:
            self._panel.clear_layers()
        for dock in (self._timeline_dock, self._panel):
            if dock is not None:
                self.iface.removeDockWidget(dock)
                dock.deleteLater()
        self._timeline_dock = None
        self._panel = None
        if self.config_action is not None:
            self.iface.removePluginMenu("Weather Routing Tool", self.config_action)
        if self.visualize_action is not None:
            self.iface.removePluginMenu("Weather Routing Tool", self.visualize_action)
        if self.action is not None:
            self.iface.removeToolBarIcon(self.action)

    def run(self):
        menu = QMenu(self.iface.mainWindow())
        menu.addAction(self.config_action)
        menu.addAction(self.visualize_action)
        menu.exec_(QCursor.pos())

    def open_config_wizard(self):
        ensure_openstreetmap_layer(self)
        self._window = WRTConfigWindow(self.iface)
        self._window.setModal(False)
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def toggle_visualizer(self):
        """The sidebar and the timeline are one tool, so they show and hide together."""
        ensure_openstreetmap_layer(self)
        if self._panel is None:
            self._build_visualizer()
        elif self._panel.isVisible():
            # closeEvent on each: stops playback and removes the loaded layers.
            self._panel.close()
            self._timeline_dock.close()
        else:
            self._panel.setVisible(True)
            self._timeline_dock.setVisible(True)

    def _build_visualizer(self):
        timeline = Timeline()
        self._panel = VisualizerPanel(self.iface, timeline)
        self._timeline_dock = TimelineDock(timeline)

        self._timeline_dock.time_changed.connect(self._panel.on_time_changed)
        self._timeline_dock.first_frame_requested.connect(self._panel.snap_boat_to_route_start)
        self._timeline_dock.last_frame_requested.connect(self._panel.snap_boat_to_route_end)
        self._panel.closed.connect(self._timeline_dock.close)
        self._panel.sources_changed.connect(self._on_sources_changed)

        self.iface.addDockWidget(Qt.RightDockWidgetArea, self._panel)
        self.iface.addDockWidget(Qt.BottomDockWidgetArea, self._timeline_dock)

    def _on_sources_changed(self):
        """Re-read the clock, then replay the current instant onto both datasets."""
        self._timeline_dock.refresh()
        self._panel.on_time_changed(self._timeline_dock.index)
