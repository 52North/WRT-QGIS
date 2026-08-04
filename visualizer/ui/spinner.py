"""A small painted busy indicator."""

from qgis.PyQt.QtCore import QRectF, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QPainter, QPen
from qgis.PyQt.QtWidgets import QWidget

SPINNER_SIZE = 14

_INTERVAL_MS = 60
_STEP_DEGREES = 30
# Qt angles are in sixteenths of a degree, measured counter-clockwise.
_SIXTEENTHS = 16
_ARC_SPAN = -270 * _SIXTEENTHS
_PEN_WIDTH = 2.0


class Spinner(QWidget):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._angle = 0
        self.setFixedSize(SPINNER_SIZE, SPINNER_SIZE)

        self._timer = QTimer(self)
        self._timer.setInterval(_INTERVAL_MS)
        self._timer.timeout.connect(self._advance)

    def _advance(self):
        # Qt measures counter-clockwise, so subtracting spins the usual way.
        self._angle = (self._angle - _STEP_DEGREES) % 360
        self.update()

    def showEvent(self, event):
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        inset = _PEN_WIDTH / 2 + 0.5
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        pen = QPen(self._color, _PEN_WIDTH)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, self._angle * _SIXTEENTHS, _ARC_SPAN)
        painter.end()
