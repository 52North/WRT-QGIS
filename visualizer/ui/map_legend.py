"""A colour ramp legend floating over the map canvas."""

from qgis.PyQt.QtCore import QEvent, Qt
from qgis.PyQt.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ...config_wizard.ui.ui_kit import COLOR_BORDER, COLOR_MUTED, COLOR_TEXT
from .color_bar import ColorBar

# Distance from the canvas corner, and the floor the box never shrinks past.
_MARGIN = 12
_MIN_WIDTH = 150

_LEGEND_QSS = f"""
QFrame#MapLegend {{
    background: rgba(255, 255, 255, 235);
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
}}
QLabel#LegendTitle {{ font-size: 11px; font-weight: 600; color: {COLOR_TEXT}; }}
QLabel#LegendTick {{ font-size: 10px; color: {COLOR_MUTED}; }}
"""


def _fmt(value):
    return f"{value:.4g}"


class MapColorbarLegend(QFrame):
    def __init__(self, canvas):
        super().__init__(canvas)
        self._canvas = canvas
        self.setObjectName("MapLegend")
        self.setAttribute(Qt.WA_StyledBackground, True)  # QSS backgrounds are ignored without this.
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(_LEGEND_QSS)
        self._build_ui()
        self.hide()
        canvas.installEventFilter(self)

    def _build_ui(self):
        self.setMinimumWidth(_MIN_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self._title = QLabel()
        self._title.setObjectName("LegendTitle")
        layout.addWidget(self._title)

        self._bar = ColorBar()
        layout.addWidget(self._bar)

        ticks = QHBoxLayout()
        self._low = QLabel()
        self._low.setObjectName("LegendTick")
        self._high = QLabel()
        self._high.setObjectName("LegendTick")
        ticks.addWidget(self._low)
        ticks.addStretch()
        ticks.addWidget(self._high)
        layout.addLayout(ticks)

    def show_variable(self, variable, ramp):
        unit = (variable.get("unit") or "").strip()
        self._title.setText(f"{variable['name']} ({unit})" if unit else variable["name"])
        self._bar.set_ramp(ramp)
        self._low.setText(_fmt(variable["vmin"]))
        self._high.setText(_fmt(variable["vmax"]))
        self.show()
        self.raise_()
        self._reposition()

    def eventFilter(self, watched, event):
        if watched is self._canvas and event.type() == QEvent.Resize:
            self._reposition()
        return super().eventFilter(watched, event)

    def _reposition(self):
        self.adjustSize()
        self.move(
            max(_MARGIN, self._canvas.width() - self.width() - _MARGIN),
            max(_MARGIN, self._canvas.height() - self.height() - _MARGIN),
        )

    def detach(self):
        """Leave the canvas cleanly when the sidebar is closed."""
        self._canvas.removeEventFilter(self)
        self.hide()
        self.setParent(None)
        self.deleteLater()
