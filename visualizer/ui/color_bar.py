"""A colour ramp drawn as a horizontal strip.

Converting ``QgsColorRamp`` objects into a ``QLinearGradient``.
"""

from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen
from qgis.PyQt.QtWidgets import QSizePolicy, QWidget

from ...config_wizard.ui.ui_kit import COLOR_BORDER

BAR_HEIGHT = 12
_RADIUS = 3
_STOPS = 24  # Number of stops to sample from the ramp.


class ColorBar(QWidget):
    def __init__(self, ramp=None, parent=None):
        super().__init__(parent)
        self._ramp = ramp
        self.setFixedHeight(BAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Dynamic width, fixed height.

    def set_ramp(self, ramp):
        self._ramp = ramp
        self.update()

    def paintEvent(self, event):
        if self._ramp is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        gradient = QLinearGradient(rect.left(), 0, rect.right(), 0)
        for step in range(_STOPS):
            fraction = step / (_STOPS - 1)
            gradient.setColorAt(fraction, self._ramp.color(fraction))

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(COLOR_BORDER), 1))
        painter.drawRoundedRect(rect, _RADIUS, _RADIUS)
        painter.end()

    def sizeHint(self):
        size = super().sizeHint()
        size.setHeight(BAR_HEIGHT)
        return size

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setWidth(40)
        hint.setHeight(BAR_HEIGHT)
        return hint
