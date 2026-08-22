"""Chip switches for the two renderer axes of a vector field."""

from qgis.PyQt.QtCore import QRectF, QSize, Qt
from qgis.PyQt.QtGui import QBrush, QColor, QPainter, QPen
from qgis.PyQt.QtWidgets import QAbstractButton

from ...config_wizard.ui.ui_kit import COLOR_MUTED, COLOR_TEXT

CHIP_HEIGHT = 22

_RADIUS = 11
_PAD_H = 12
_FONT_SIZE = 11

_OFF_BG = "#f1f3f5"
_OFF_BG_HOVER = "#e5e9ed"
_LOCKED_BORDER_ALPHA = 110


class AxisChip(QAbstractButton):
    """A checkable pill that says which renderer axis it draws."""

    def __init__(self, text, tooltip, accent, tint, parent=None):
        super().__init__(parent)
        self._accent = accent
        self._tint = tint
        self._is_hovered = False
        self._is_locked = False
        self._tooltip = tooltip
        self._locked_tooltip = f"{tooltip}\n\nKept on: untick the layer to stop drawing it."

        self.setText(text)
        self.setCheckable(True)
        self.setChecked(True)
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedHeight(CHIP_HEIGHT)

        font = self.font()
        font.setPixelSize(_FONT_SIZE)
        self.setFont(font)

    def set_locked(self, is_locked):
        """Pin the chip on without dimming it — a dim chip reads as an axis that is off."""
        if is_locked == self._is_locked:
            return
        self._is_locked = is_locked
        self.setEnabled(not is_locked)
        self.setCursor(Qt.ArrowCursor if is_locked else Qt.PointingHandCursor)
        self.setToolTip(self._locked_tooltip if is_locked else self._tooltip)
        self._is_hovered = False
        self.update()

    def sizeHint(self):
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        return QSize(text_width + 2 * _PAD_H, CHIP_HEIGHT)

    def minimumSizeHint(self):
        return self.sizeHint()

    def enterEvent(self, event):
        if not self._is_locked:
            self._is_hovered = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._paint_pill(painter)
        self._paint_text(painter)
        painter.end()

    def _paint_pill(self, painter):
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self.isChecked():
            fill = QColor(self._tint)
            border = QColor(self._accent)
            if self._is_locked:
                border.setAlpha(_LOCKED_BORDER_ALPHA)
        else:
            fill = QColor(_OFF_BG_HOVER if self._is_hovered else _OFF_BG)
            border = QColor(fill)
        if self.isDown():
            fill = fill.darker(106)
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(rect, _RADIUS, _RADIUS)

    def _paint_text(self, painter):
        if self.isChecked():
            color = QColor(self._accent)
        else:
            color = QColor(COLOR_TEXT if self._is_hovered else COLOR_MUTED)
        painter.setPen(QPen(color))
        painter.drawText(QRectF(self.rect()), Qt.AlignCenter, self.text())
