import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QCursor, QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu

from .utils import ensure_openstreetmap_layer
from .config_wizard.ui.wizard import WRTConfigWindow
from .route_visualizer.ui.route_panel import RouteVisualizerPanel



class WRTPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.config_action = None
        self.visualize_action = None
        self._window = None
        self._dock = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self.action = QAction(icon, "Weather Routing Tool", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)

        self.config_action = QAction(icon, "Config Wizard", self.iface.mainWindow())
        self.config_action.triggered.connect(self.open_config_wizard)
        
        self.visualize_action = QAction(icon, "Route Visualizer", self.iface.mainWindow())
        self.visualize_action.triggered.connect(self.toggle_route_visualizer)

        self.iface.addPluginToMenu("Weather Routing Tool", self.config_action)
        self.iface.addPluginToMenu("Weather Routing Tool", self.visualize_action)

    def unload(self):
        if self._dock is not None:
            self.iface.removeDockWidget(self._dock)
            self._dock.deleteLater()
            self._dock = None
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

    def toggle_route_visualizer(self):
        ensure_openstreetmap_layer(self)
        if self._dock is None:
            self._dock = RouteVisualizerPanel(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self._dock)
        elif self._dock.isVisible():
            self._dock.close()  # fires closeEvent: stops playback and removes layers
        else:
            self._dock.setVisible(True)
