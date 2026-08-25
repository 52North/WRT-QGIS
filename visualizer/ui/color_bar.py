"""A colour ramp drawn as a horizontal strip, plus its tick-mark axis.

Converting ``QgsColorRamp`` objects into a ``QLinearGradient``.
"""

import math

from qgis.PyQt.QtCore import QPointF, QRectF
from qgis.PyQt.QtGui import QBrush, QColor, QFontMetrics, QLinearGradient, QPainter, QPen
from qgis.PyQt.QtWidgets import QSizePolicy, QWidget

from ...config_wizard.ui.ui_kit import COLOR_BORDER, COLOR_MUTED

BAR_HEIGHT = 12
_RADIUS = 3
_STOPS = 24  # Number of stops to sample from the ramp.
_TICK_HEIGHT = 4
_TICK_LABEL_GAP = 2
_TICK_FONT_PX = 10


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


class TickAxis(QWidget):
    """Vertical tick marks above their value labels, aligned to fractions of the bar's width."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ticks = []  # list[tuple[float, str]] of (fraction, label text).
        font = self.font()
        font.setPixelSize(_TICK_FONT_PX)
        self.setFont(font)
        self.setFixedHeight(_TICK_HEIGHT + _TICK_LABEL_GAP + QFontMetrics(font).height())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_ticks(self, ticks):
        self._ticks = list(ticks)
        self.update()

    def required_width(self, gap=4):
        """Narrowest width at which every tick label clears its neighbours by ``gap`` px."""
        if len(self._ticks) < 2:
            return 0
        metrics = QFontMetrics(self.font())
        fractions = [fraction for fraction, _ in self._ticks]
        label_widths = [metrics.horizontalAdvance(text) for _, text in self._ticks]
        last_index = len(self._ticks) - 1

        needed = 0.0
        for i in range(last_index):
            fraction_span = fractions[i + 1] - fractions[i]
            if fraction_span <= 0:
                continue
            left_reach = label_widths[i] if i == 0 else label_widths[i] / 2
            right_reach = label_widths[i + 1] if i + 1 == last_index else label_widths[i + 1] / 2
            needed = max(needed, (left_reach + right_reach + gap) / fraction_span)
        return math.ceil(needed)

    def paintEvent(self, event):
        if not self._ticks:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(COLOR_MUTED), 1))

        width = self.width()
        metrics = QFontMetrics(painter.font())
        text_baseline = _TICK_HEIGHT + _TICK_LABEL_GAP + metrics.ascent()

        for fraction, text in self._ticks:
            x = fraction * width
            painter.drawLine(QPointF(x, 0), QPointF(x, _TICK_HEIGHT))

            text_width = metrics.horizontalAdvance(text)
            text_x = min(max(x - text_width / 2, 0), width - text_width)
            painter.drawText(QPointF(text_x, text_baseline), text)

        painter.end()
