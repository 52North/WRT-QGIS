"""A colour ramp legend floating over the map canvas."""

from qgis.PyQt.QtCore import QEvent, Qt
from qgis.PyQt.QtGui import QFontMetrics
from qgis.PyQt.QtWidgets import QFrame, QLabel, QVBoxLayout

from ...config_wizard.ui.ui_kit import COLOR_BORDER, COLOR_TEXT
from .color_bar import ColorBar, TickAxis

# Distance from the canvas corner, and the floor/ceiling the box never shrinks/grows past.
_MARGIN = 12
_MIN_WIDTH = 190
_MAX_WIDTH = 420

# Fractions along the ramp (0=vmin, 1=vmax) that get a tick label under the bar.
_TICK_FRACTIONS = (0, 0.25, 0.5, 0.75, 1)


def _fmt(value):
    return f"{value:.4g}"


def _elided(label, text, max_width):
    """Elide ``text`` to fit within ``max_width`` px, keeping the full text as a tooltip."""
    metrics = QFontMetrics(label.font())
    label.setText(metrics.elidedText(text, Qt.ElideMiddle, max_width))
    label.setToolTip(text)


_LEGEND_QSS = f"""
QFrame#MapLegend {{
    background: rgba(255, 255, 255, 235);
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
}}
QLabel#LegendTitle {{ font-size: 11px; font-weight: 600; color: {COLOR_TEXT}; }}
"""


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

        self._ticks = TickAxis()
        layout.addWidget(self._ticks)

    def show_variable(self, variable, ramp):
        unit = (variable.get("unit") or "").strip()
        title = f"{variable['name']} ({unit})" if unit else variable["name"]

        self._bar.set_ramp(ramp)

        vmin, vmax = variable["vmin"], variable["vmax"]
        self._ticks.set_ticks(
            (fraction, _fmt(vmin + (vmax - vmin) * fraction)) for fraction in _TICK_FRACTIONS
        )

        self._fit_width(title)

        self.show()
        self.raise_()
        self._reposition()

    def _fit_width(self, title):
        """Widen the box to fit every tick label, capped at ``_MAX_WIDTH`` and the canvas edge."""
        margins = self.layout().contentsMargins()
        padding = margins.left() + margins.right()
        needed = self._ticks.required_width() + padding
        ceiling = min(_MAX_WIDTH, max(_MIN_WIDTH, self._canvas.width() - 2 * _MARGIN))
        width = max(_MIN_WIDTH, min(needed, ceiling))
        self.setFixedWidth(width)
        _elided(self._title, title, width - padding)

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
