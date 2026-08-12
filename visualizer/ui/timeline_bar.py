"""The scrubbable track: two coverage lanes and a shared playhead on one UTC axis."""

from qgis.PyQt.QtCore import QRectF, Qt, pyqtSignal
from qgis.PyQt.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen
from qgis.PyQt.QtWidgets import QSizePolicy, QWidget

from ..core.timeline import ROUTE, WEATHER
from .color_palette import (
    HATCH_LIGHT,
    PLAYHEAD,
    PROGRESS,
    ROUTE_COLOR,
    TRACK_BG,
    WEATHER_GRADIENT_END,
    WEATHER_GRADIENT_START,
)

# Vertical layout, weather timeline on top & route timeline on bottom.
_WEATHER_Y = 4
_TRACK_Y = 15
_ROUTE_Y = 22
_LANE_H = 7
_TRACK_H = 4
_PLAYHEAD_TOP = 0
_PLAYHEAD_BOTTOM = 33
_KNOB_R = 8
_KNOB_CY = _TRACK_Y + _TRACK_H / 2
_HEIGHT = 40

# Room either side so the knob is not clipped at the ends of the span.
_PAD = _KNOB_R + 2


class TimelineBar(QWidget):
    """Paints the coverage lanes and emits the step the user scrubs to."""

    step_changed = pyqtSignal(int)

    def __init__(self, timeline, parent=None):
        super().__init__(parent)
        self._timeline = timeline
        self._index = 0
        self.setMinimumHeight(_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)

    def set_index(self, index):
        if index != self._index:
            self._index = index
            self.update()

    def refresh(self):
        """Re-read the timeline after a dataset was loaded or unloaded."""
        self._index = min(self._index, max(len(self._timeline.steps) - 1, 0))
        self.update()

    # geometry

    def _track_width(self):
        return max(self.width() - 2 * _PAD, 1)

    def _to_x(self, fraction):
        return _PAD + fraction * self._track_width()

    def _to_fraction(self, x):
        return min(max((x - _PAD) / self._track_width(), 0.0), 1.0)

    def _nearest_step(self, fraction):
        steps = self._timeline.steps
        if not steps:
            return None
        best, best_gap = 0, None
        for i in range(len(steps)):
            gap = abs(self._timeline.step_fraction(i) - fraction)
            if best_gap is None or gap < best_gap:
                best, best_gap = i, gap
        return best

    # painting

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        self._paint_base_track(painter)
        self._paint_weather_lane(painter)
        self._paint_route_lane(painter)

        if not self._timeline.is_empty:
            self._paint_progress(painter)
            self._paint_playhead(painter)
        painter.end()

    def _paint_base_track(self, painter):
        painter.setBrush(QColor(TRACK_BG))
        painter.drawRoundedRect(QRectF(_PAD, _TRACK_Y, self._track_width(), _TRACK_H), 2, 2)

    def _paint_weather_lane(self, painter):
        coverage = self._timeline.coverage(WEATHER)
        if coverage is None:
            return
        left, right = self._to_x(coverage[0]), self._to_x(coverage[1])
        rect = QRectF(left, _WEATHER_Y, max(right - left, 2), _LANE_H)

        gradient = QLinearGradient(rect.left(), 0, rect.right(), 0)
        gradient.setColorAt(0, QColor(WEATHER_GRADIENT_START))
        gradient.setColorAt(1, QColor(WEATHER_GRADIENT_END))
        painter.setOpacity(0.85)
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(rect, 3, 3)
        painter.setOpacity(1.0)

    def _paint_route_lane(self, painter):
        coverage = self._timeline.coverage(ROUTE)
        if coverage is None:
            return
        left, right = self._to_x(coverage[0]), self._to_x(coverage[1])

        # Time the route does not cover reads as "weather-only window".
        self._paint_gaps(painter, left, right)

        rect = QRectF(left, _ROUTE_Y, max(right - left, 2), _LANE_H)
        painter.setOpacity(0.9)
        painter.setBrush(QColor(ROUTE_COLOR))
        painter.drawRoundedRect(rect, 3, 3)
        painter.setOpacity(1.0)

        # One tick per waypoint, so irregular spacing is visible at a glance.
        painter.setPen(QPen(QColor(0, 0, 0, 82), 1))
        for fraction in self._timeline.tick_fractions(ROUTE):
            x = self._to_x(fraction)
            painter.drawLine(int(x), _ROUTE_Y + 1, int(x), _ROUTE_Y + _LANE_H - 1)
        painter.setPen(Qt.NoPen)

    def _paint_gaps(self, painter, left, right):
        hatch = QBrush(QColor(HATCH_LIGHT), Qt.BDiagPattern)
        painter.setBrush(hatch)
        if left > _PAD:
            painter.drawRoundedRect(QRectF(_PAD, _ROUTE_Y, left - _PAD, _LANE_H), 3, 3)
        end = _PAD + self._track_width()
        if right < end:
            painter.drawRoundedRect(QRectF(right, _ROUTE_Y, end - right, _LANE_H), 3, 3)

    def _paint_progress(self, painter):
        x = self._to_x(self._timeline.step_fraction(self._index))
        painter.setBrush(QColor(PROGRESS))
        painter.drawRoundedRect(QRectF(_PAD, _TRACK_Y, max(x - _PAD, 0), _TRACK_H), 2, 2)

    def _paint_playhead(self, painter):
        x = self._to_x(self._timeline.step_fraction(self._index))
        painter.setBrush(QColor(PLAYHEAD))
        painter.drawRect(QRectF(x - 1, _PLAYHEAD_TOP, 2, _PLAYHEAD_BOTTOM))

        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor(PLAYHEAD), 3))
        painter.drawEllipse(QRectF(x - _KNOB_R, _KNOB_CY - _KNOB_R, 2 * _KNOB_R, 2 * _KNOB_R))
        painter.setPen(Qt.NoPen)

    # interaction

    def _scrub_to(self, x):
        index = self._nearest_step(self._to_fraction(x))
        if index is not None and index != self._index:
            self._index = index
            self.update()
            self.step_changed.emit(index)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._scrub_to(event.pos().x())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._scrub_to(event.pos().x())

    def keyPressEvent(self, event):
        deltas = {Qt.Key_Left: -1, Qt.Key_Right: 1, Qt.Key_Home: None, Qt.Key_End: None}
        if event.key() not in deltas:
            super().keyPressEvent(event)
            return
        last = max(len(self._timeline.steps) - 1, 0)
        if event.key() == Qt.Key_Home:
            index = 0
        elif event.key() == Qt.Key_End:
            index = last
        else:
            index = min(max(self._index + deltas[event.key()], 0), last)
        if index != self._index:
            self._index = index
            self.update()
            self.step_changed.emit(index)
