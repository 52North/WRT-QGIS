"""Custom QGIS map tools used by the config wizard."""

from qgis.core import QgsGeometry, QgsPointXY, QgsRectangle, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsMapToolEmitPoint, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor


class MapPointPicker(QgsMapToolEmitPoint):
    """Emit-point tool that lets the user drag to pan the map before clicking.

    A left press followed by a drag pans the canvas; a left click emits a point.
    """

    _DRAG_THRESHOLD = 6  # pixels of movement before a press counts as a pan

    def __init__(self, canvas):
        super().__init__(canvas)
        self._canvas = canvas
        self._press_pos = None
        self._panning = False

    def canvasPressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.pos()
            self._panning = False

    def canvasMoveEvent(self, event):
        if self._press_pos is None:
            return
        if not self._panning and (
            (event.pos() - self._press_pos).manhattanLength() >= self._DRAG_THRESHOLD
        ):
            self._panning = True
        if self._panning:
            self._canvas.panAction(event)

    def canvasReleaseEvent(self, event):
        if self._panning:
            self._canvas.panActionEnd(event.pos())
            self._press_pos = None
            self._panning = False
            return
        self._press_pos = None
        self.canvasClicked.emit(self.toMapCoordinates(event.pos()), event.button())


class RectangleMapTool(QgsMapTool):
    """Draw a rectangle by dragging, then fine-tune it by dragging its edges/corners.

    Interaction:
      * drag on empty space  → rubber-band a new rectangle
      * drag an edge/corner  → resize that side
      * double-click / Enter → confirm
      * Escape / right-click → cancel
    """

    rectangleConfirmed = pyqtSignal(object)  # QgsRectangle (canvas CRS)
    cancelled = pyqtSignal()

    _DRAG_THRESHOLD = 4  # px before a press becomes a new-rectangle drag
    _HANDLE_TOL = 10  # px hit-radius around an edge/corner handle

    # handle key → which rectangle bounds it moves ('xmin'/'xmax' via point.x, 'ymin'/'ymax' via point.y)
    _HANDLE_BOUNDS = {
        "ll": ("xmin", "ymin"),
        "lr": ("xmax", "ymin"),
        "ul": ("xmin", "ymax"),
        "ur": ("xmax", "ymax"),
        "l": ("xmin",),
        "r": ("xmax",),
        "b": ("ymin",),
        "t": ("ymax",),
    }

    def __init__(self, canvas):
        super().__init__(canvas)
        self._canvas = canvas
        self._rect = None  # QgsRectangle in canvas CRS
        self._press_pos = None
        self._drawing = False
        self._start = None
        self._active_handle = None

        self._band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self._band.setColor(QColor(37, 99, 235))
        self._band.setFillColor(QColor(37, 99, 235, 40))
        self._band.setWidth(2)

        self._handle_band = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
        self._handle_band.setIcon(QgsRubberBand.ICON_BOX)
        self._handle_band.setIconSize(9)
        self._handle_band.setColor(QColor(37, 99, 235))
        self._handle_band.setWidth(2)

    def set_rectangle(self, rect):
        """Seed the tool with an existing rectangle (canvas CRS) for editing."""
        self._rect = QgsRectangle(rect)
        self._update_bands()

    def _handle_points(self):
        r = self._rect
        xmid = (r.xMinimum() + r.xMaximum()) / 2.0
        ymid = (r.yMinimum() + r.yMaximum()) / 2.0
        return {
            "ll": QgsPointXY(r.xMinimum(), r.yMinimum()),
            "lr": QgsPointXY(r.xMaximum(), r.yMinimum()),
            "ul": QgsPointXY(r.xMinimum(), r.yMaximum()),
            "ur": QgsPointXY(r.xMaximum(), r.yMaximum()),
            "l": QgsPointXY(r.xMinimum(), ymid),
            "r": QgsPointXY(r.xMaximum(), ymid),
            "b": QgsPointXY(xmid, r.yMinimum()),
            "t": QgsPointXY(xmid, r.yMaximum()),
        }

    def _handle_at(self, pos):
        if self._rect is None:
            return None
        best, best_d = None, self._HANDLE_TOL
        for key, pt in self._handle_points().items():
            d = (self.toCanvasCoordinates(pt) - pos).manhattanLength()
            if d <= best_d:
                best, best_d = key, d
        return best

    def _resize(self, handle, point):
        xmin, xmax = self._rect.xMinimum(), self._rect.xMaximum()
        ymin, ymax = self._rect.yMinimum(), self._rect.yMaximum()
        for bound in self._HANDLE_BOUNDS[handle]:
            if bound == "xmin":
                xmin = point.x()
            elif bound == "xmax":
                xmax = point.x()
            elif bound == "ymin":
                ymin = point.y()
            elif bound == "ymax":
                ymax = point.y()
        rect = QgsRectangle(xmin, ymin, xmax, ymax)
        rect.normalize()
        self._rect = rect

    def _update_bands(self):
        if self._rect is None:
            self._band.reset(QgsWkbTypes.PolygonGeometry)
            self._handle_band.reset(QgsWkbTypes.PointGeometry)
            return
        self._band.setToGeometry(QgsGeometry.fromRect(self._rect), None)
        self._handle_band.reset(QgsWkbTypes.PointGeometry)
        for pt in self._handle_points().values():
            self._handle_band.addPoint(pt)

    def canvasPressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.cancelled.emit()
            return
        if event.button() != Qt.LeftButton:
            return
        self._press_pos = event.pos()
        self._drawing = False
        self._active_handle = self._handle_at(event.pos())

    def canvasMoveEvent(self, event):
        if self._press_pos is None:
            return
        point = self.toMapCoordinates(event.pos())
        if self._active_handle:
            self._resize(self._active_handle, point)
            self._update_bands()
            return
        if not self._drawing and (
            (event.pos() - self._press_pos).manhattanLength() >= self._DRAG_THRESHOLD
        ):
            self._drawing = True
            self._start = self.toMapCoordinates(self._press_pos)
        if self._drawing:
            rect = QgsRectangle(self._start, point)
            rect.normalize()
            self._rect = rect
            self._update_bands()

    def canvasReleaseEvent(self, event):
        self._press_pos = None
        self._drawing = False
        self._active_handle = None

    def canvasDoubleClickEvent(self, event):
        self._confirm()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._confirm()
        elif event.key() == Qt.Key_Escape:
            self.cancelled.emit()

    def _confirm(self):
        if self._rect is not None and self._rect.width() > 0 and self._rect.height() > 0:
            self.rectangleConfirmed.emit(QgsRectangle(self._rect))

    def deactivate(self):
        self._band.reset(QgsWkbTypes.PolygonGeometry)
        self._handle_band.reset(QgsWkbTypes.PointGeometry)
        super().deactivate()
