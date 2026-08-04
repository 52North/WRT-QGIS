"""A value distribution drawn as bars, painted the way ``ColorBar`` is."""

from qgis.PyQt.QtCore import QRectF, Qt
from qgis.PyQt.QtGui import QBrush, QColor, QPainter, QPen
from qgis.PyQt.QtWidgets import QSizePolicy, QToolTip, QWidget

from ...config_wizard.ui.ui_kit import COLOR_BORDER, COLOR_PRIMARY

HISTOGRAM_HEIGHT = 64
_RADIUS = 3
_PADDING = 4
_BAR_GAP = 1.0
_MIN_BAR = 1.0  # a bin with cells in it never disappears entirely


class Histogram(QWidget):
    """Bars sized by cell count, tinted by where their values sit in the ramp."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._counts = []
        self._edges = []
        self._ramp = None
        self._ramp_range = None
        self.setFixedHeight(HISTOGRAM_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)

    def set_data(self, counts, edges, ramp=None, ramp_range=None):
        """``ramp_range`` is the whole-file (vmin, vmax) the map is painted with."""
        self._counts = list(counts)
        self._edges = list(edges)
        self._ramp = ramp
        self._ramp_range = ramp_range
        self.update()

    def clear(self):
        self.set_data([], [])

    # painting

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(QPen(QColor(COLOR_BORDER), 1))
        painter.drawRoundedRect(frame, _RADIUS, _RADIUS)

        if not self._counts:
            painter.end()
            return

        plot = self._plot_rect(frame)
        peak = max(self._counts) or 1
        slot_width = plot.width() / len(self._counts)
        painter.setPen(Qt.NoPen)
        for slot, count in enumerate(self._counts):
            if count <= 0:
                continue
            height = max(plot.height() * count / peak, _MIN_BAR)
            bar = QRectF(
                plot.left() + slot * slot_width,
                plot.bottom() - height,
                max(slot_width - _BAR_GAP, 1.0),
                height,
            )
            painter.setBrush(QBrush(self._bar_color(slot)))
            painter.drawRect(bar)
        painter.end()

    def _plot_rect(self, frame):
        return frame.adjusted(_PADDING, _PADDING, -_PADDING, -_PADDING)

    def _bar_color(self, slot):
        """Tint a bar by where its own values sit in the whole-file range."""
        if self._ramp is None or self._ramp_range is None:
            return QColor(COLOR_PRIMARY)
        low, high = self._ramp_range
        if high <= low:
            return self._ramp.color(0.5)
        centre = (self._edges[slot] + self._edges[slot + 1]) / 2.0
        fraction = (centre - low) / (high - low)
        return self._ramp.color(min(max(fraction, 0.0), 1.0))

    # hover

    def mouseMoveEvent(self, event):
        slot = self._slot_at(event.pos().x())
        if slot is None:
            QToolTip.hideText()
            return
        low, high = self._edges[slot], self._edges[slot + 1]
        QToolTip.showText(
            event.globalPos(),
            f"{low:.4g} – {high:.4g}\n{self._counts[slot]:,} cells",
            self,
        )

    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)

    def _slot_at(self, x_position):
        if not self._counts or len(self._edges) < 2:
            return None
        plot = self._plot_rect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
        if not plot.left() <= x_position <= plot.right():
            return None
        slot = int((x_position - plot.left()) / (plot.width() / len(self._counts)))
        return min(max(slot, 0), len(self._counts) - 1)

    # sizing

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(HISTOGRAM_HEIGHT)
        return hint

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setWidth(80)
        hint.setHeight(HISTOGRAM_HEIGHT)
        return hint
