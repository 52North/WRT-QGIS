"""Bottom-docked transport bar: one clock, one playback timer, both datasets."""

from qgis.PyQt.QtCore import Qt, QTimer, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...config_wizard.ui.ui_kit import COLOR_BORDER, COLOR_MUTED, COLOR_TEXT
from ..core.timeline import ROUTE, WEATHER
from .color_palette import (
    MONO_FAMILY,
    PROGRESS,
    ROUTE_COLOR,
    WEATHER_GRADIENT_END,
    WEATHER_GRADIENT_START,
)
from .timeline_bar import TimelineBar

_DATE_FORMAT = "yyyy-MM-dd"
_CLOCK_FORMAT = "HH:mm"
_AXIS_FORMAT = "MMM dd HH:mm"

_AXIS_TICKS = 5

# Dock height constraints
_MIN_DOCK_HEIGHT = 140
_MAX_DOCK_HEIGHT = 260

_QSS = f"""
QLabel#Date {{ font-family: {MONO_FAMILY}; font-size: 20px; font-weight: 600;
               color: {COLOR_TEXT}; }}
QLabel#Clock {{ font-family: {MONO_FAMILY}; font-size: 20px; font-weight: 600;
                color: {PROGRESS}; }}
QLabel#Zone, QLabel#Day {{ font-size: 11px; color: {COLOR_MUTED}; }}
QLabel#Axis, QLabel#Legend {{ font-family: {MONO_FAMILY}; font-size: 10px;
                              color: {COLOR_MUTED}; }}
QLabel#Context {{ font-size: 11px; color: {COLOR_MUTED}; }}
QPushButton#Loop {{ border: 1px solid {COLOR_BORDER}; border-radius: 6px;
                    padding: 4px 10px; font-size: 11px; }}
QPushButton#Loop:checked {{ border: 1px solid {PROGRESS}; background: #e7f0fd;
                            color: {PROGRESS}; font-weight: 600; }}
"""


def _swatch(color, gradient_end=None):
    chip = QLabel()
    chip.setFixedSize(16, 6)
    fill = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color}, stop:1 {gradient_end})"
        if gradient_end
        else color
    )
    chip.setStyleSheet(f"background: {fill}; border-radius: 3px;")
    return chip


class TimelineDock(QDockWidget):
    """Drives the shared clock. Emits the index into ``Timeline.steps``."""

    time_changed = pyqtSignal(int)

    def __init__(self, timeline, parent=None):
        super().__init__("Timeline", parent)
        self._timeline = timeline
        self._index = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)

        self.setMinimumHeight(_MIN_DOCK_HEIGHT)
        self.setMaximumHeight(_MAX_DOCK_HEIGHT)

        self._build_ui()
        self.refresh()

    # ui

    def _build_ui(self):
        root = QWidget()
        root.setStyleSheet(_QSS)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 9, 14, 11)
        layout.setSpacing(8)

        layout.addLayout(self._build_controls())
        layout.addLayout(self._build_axis())

        self._bar = TimelineBar(self._timeline)
        self._bar.step_changed.connect(self._on_bar_scrubbed)
        layout.addWidget(self._bar)

        layout.addLayout(self._build_legend())
        self.setWidget(root)

    def _build_controls(self):
        row = QHBoxLayout()
        row.setSpacing(10)

        self._transport = []
        transport = QHBoxLayout()
        transport.setSpacing(4)
        for text, tip, target in (("⏮", "First step", 0), ("⏭", "Last step", -1)):
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _, t=target: self._jump_to(t))
            self._transport.append(btn)
            transport.addWidget(btn)

        self._play_btn = QPushButton("▶  Play")
        self._play_btn.clicked.connect(self._toggle_play)
        transport.insertWidget(1, self._play_btn)
        row.addLayout(transport)

        self._date_label = QLabel("—")
        self._date_label.setObjectName("Date")
        self._clock_label = QLabel("")
        self._clock_label.setObjectName("Clock")
        zone = QLabel("UTC")
        zone.setObjectName("Zone")
        self._day_label = QLabel("")
        self._day_label.setObjectName("Day")
        for widget in (self._date_label, self._clock_label, zone, self._day_label):
            row.addWidget(widget, 0, Qt.AlignBottom)

        row.addStretch()

        self._context_label = QLabel("")
        self._context_label.setObjectName("Context")
        row.addWidget(self._context_label)

        self._loop_btn = QPushButton("🔁 Loop")
        self._loop_btn.setObjectName("Loop")
        self._loop_btn.setCheckable(True)
        self._loop_btn.setToolTip("Restart from the beginning instead of stopping")
        row.addWidget(self._loop_btn)

        row.addWidget(QLabel("ms/step:"))
        self._speed_spin = QSpinBox()
        self._speed_spin.setRange(50, 2000)
        self._speed_spin.setValue(400)
        self._speed_spin.setSuffix(" ms")
        self._speed_spin.valueChanged.connect(
            lambda v: self._timer.isActive() and self._timer.setInterval(v)
        )
        row.addWidget(self._speed_spin)
        return row

    def _build_axis(self):
        self._axis_row = QHBoxLayout()
        self._axis_row.setContentsMargins(10, 0, 10, 0)
        self._axis_labels = []
        for i in range(_AXIS_TICKS):
            label = QLabel("")
            label.setObjectName("Axis")
            align = (
                Qt.AlignLeft
                if i == 0
                else (Qt.AlignRight if i == _AXIS_TICKS - 1 else Qt.AlignHCenter)
            )
            label.setAlignment(align | Qt.AlignVCenter)
            self._axis_labels.append(label)
            self._axis_row.addWidget(label, 1)
        return self._axis_row

    def _build_legend(self):
        row = QHBoxLayout()
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(8)

        row.addWidget(_swatch(WEATHER_GRADIENT_START, WEATHER_GRADIENT_END))
        self._weather_legend = QLabel("")
        self._weather_legend.setObjectName("Legend")
        row.addWidget(self._weather_legend)

        row.addSpacing(12)
        row.addWidget(_swatch(ROUTE_COLOR))
        self._route_legend = QLabel("")
        self._route_legend.setObjectName("Legend")
        row.addWidget(self._route_legend)

        row.addStretch()
        sampling = QLabel("Sampling: nearest frame ≤ current time")
        sampling.setObjectName("Legend")
        row.addWidget(sampling)
        return row

    # state

    @property
    def index(self):
        return self._index

    def refresh(self):
        """Rebuild after a dataset was loaded or unloaded."""
        self.stop()
        steps = self._timeline.steps
        self._index = min(self._index, max(len(steps) - 1, 0))

        has_steps = len(steps) > 1
        self._play_btn.setEnabled(has_steps)
        for btn in self._transport:
            btn.setEnabled(has_steps)
        self._bar.setEnabled(bool(steps))

        stamps = self._timeline.axis_labels(_AXIS_TICKS)
        for i, label in enumerate(self._axis_labels):
            label.setText(stamps[i].toString(_AXIS_FORMAT) if i < len(stamps) else "")

        weather_count = self._timeline.count(WEATHER)
        route_count = self._timeline.count(ROUTE)
        self._weather_legend.setText(
            f"Weather coverage · {weather_count} frames"
            if weather_count
            else "Weather coverage · none loaded"
        )
        self._route_legend.setText(
            f"Route coverage · {route_count} waypoints"
            if route_count
            else "Route coverage · none loaded"
        )

        self._bar.refresh()
        self._sync_readout()

    def set_index(self, index):
        """Move the playhead without re-emitting (used to restore state)."""
        self._index = index
        self._bar.set_index(index)
        self._sync_readout()

    def _sync_readout(self):
        steps = self._timeline.steps
        if not steps:
            self._date_label.setText("—")
            self._clock_label.setText("")
            self._day_label.setText("")
            self._context_label.setText("")
            return

        stamp = steps[self._index]
        self._date_label.setText(stamp.toString(_DATE_FORMAT))
        self._clock_label.setText(stamp.toString(_CLOCK_FORMAT))
        day, total = self._timeline.day_of(stamp)
        self._day_label.setText(f"day {day} of {total}")

        route_index = self._timeline.index_at(ROUTE, stamp)
        route_count = self._timeline.count(ROUTE)
        if route_count and route_index is not None:
            self._context_label.setText(f"Waypoint {route_index + 1} / {route_count}")
        elif route_count:
            self._context_label.setText(f"Before waypoint 1 / {route_count}")
        else:
            self._context_label.setText("")

    # playback

    def _emit(self, index):
        self._index = index
        self._bar.set_index(index)
        self._sync_readout()
        self.time_changed.emit(index)

    def _on_bar_scrubbed(self, index):
        self._index = index
        self._sync_readout()
        self.time_changed.emit(index)

    def _last(self):
        return max(len(self._timeline.steps) - 1, 0)

    def _jump_to(self, target):
        self._emit(self._last() if target == -1 else 0)

    def _toggle_play(self):
        if self._timer.isActive():
            self.stop()
        else:
            if self._index >= self._last():
                self._emit(0)
            self._timer.start(self._speed_spin.value())
            self._play_btn.setText("⏸  Pause")

    def stop(self):
        if self._timer.isActive():
            self._timer.stop()
        self._play_btn.setText("▶  Play")

    def _on_timer_tick(self):
        if self._index >= self._last():
            if self._loop_btn.isChecked():
                self._emit(0)
            else:
                self.stop()
            return
        self._emit(self._index + 1)

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)
