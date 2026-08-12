from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
)

from ...config_wizard.ui.ui_kit import (
    COLOR_BORDER,
    COLOR_GRAY_BADGE,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_TEXT,
)
from ..styling.mesh_styler import color_ramp_for, is_wind_variable
from .color_bar import ColorBar
from .color_palette import ROUTE_COLOR, ROUTE_TINT, WEATHER_COLOR, WEATHER_TINT

# Accent per dataset identity, either a route or a weather variable.
_ACCENTS = {"route": (ROUTE_COLOR, ROUTE_TINT)}
_DEFAULT_ACCENT = (WEATHER_COLOR, WEATHER_TINT)

# Highlighting the selected card is done with a thicker border and a tint.
_MARGINS = (10, 8, 10, 8)
_MARGINS_SELECTED = (9, 7, 9, 7)


def _card_qss(accent, tint):
    return f"""
QFrame#LayerCard {{
    background: #ffffff;
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
}}
QFrame#LayerCard:hover {{ border: 1px solid {COLOR_MUTED}; }}
QFrame#LayerCard[selected="true"] {{
    background: {tint};
    border: 2px solid {accent};
}}
QLabel#LayerName {{ font-weight: 600; color: {COLOR_TEXT}; }}
QLabel#TypeBadge {{
    background: {COLOR_GRAY_BADGE};
    color: {COLOR_MUTED};
    border-radius: 3px;
    padding: 1px 6px;
    font-size: 10px;
}}
QLabel#RangeLabel {{ color: {COLOR_MUTED}; font-size: 10px; }}

QSlider::groove:horizontal {{
    height: 4px; border-radius: 2px; background: {COLOR_BORDER};
}}
QSlider::sub-page:horizontal {{
    height: 4px; border-radius: 2px; background: {COLOR_PRIMARY};
}}
QSlider::handle:horizontal {{
    width: 11px; height: 11px; margin: -5px 0; border-radius: 7px;
    background: #ffffff; border: 2px solid {COLOR_PRIMARY};
}}
"""


def _fmt(value):
    return f"{value:.4g}"


_BADGES = {"vector": "vectors", "scalar": "raster", "route": "vector"}


def _muted(text):
    label = QLabel(text)
    label.setObjectName("RangeLabel")
    return label


class LayerCard(QFrame):
    """One drawable layer: enable selected, name, type badge, and opacity slider."""

    toggled = pyqtSignal(bool)
    opacity_changed = pyqtSignal(float)

    def __init__(self, variable, parent=None):
        super().__init__(parent)
        self._variable = variable
        self.setObjectName("LayerCard")
        accent, tint = _ACCENTS.get(variable["kind"], _DEFAULT_ACCENT)
        self.setStyleSheet(_card_qss(accent, tint))
        self.setCursor(Qt.PointingHandCursor)
        self._build_ui()
        self._refresh_highlight()

    def _build_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(*_MARGINS)
        self._layout.setSpacing(6)

        # Toggling the highlights the card and shows the body with the opacity slider. The checkbox itself is hidden.
        self._check = QCheckBox(self)
        self._check.hide()
        self._check.toggled.connect(self._on_toggled)

        header = QHBoxLayout()
        header.setSpacing(8)

        name = QLabel(self._variable["name"])
        name.setObjectName("LayerName")
        name.setWordWrap(True)
        name.setToolTip(self._variable.get("raw_name", self._variable["name"]))
        header.addWidget(name, 1)

        badge = QLabel(_BADGES.get(self._variable["kind"], "raster"))
        badge.setObjectName("TypeBadge")
        header.addWidget(badge, 0, Qt.AlignTop)
        self._layout.addLayout(header)

        self._body = QFrame()
        body = QVBoxLayout(self._body)
        body.setContentsMargins(2, 0, 2, 0)
        body.setSpacing(4)

        ###### Disabled for now ######

        # if "vmin" in self._variable and "vmax" in self._variable:
        #     self._build_range(body)
        self._build_opacity(body)

        self._body.setVisible(False)
        self._layout.addWidget(self._body)

    def _build_range(self, body):
        """Min and max, with what the map paints between them shown in between.

        A scalar group gets the ramp itself as a strip; the body is only visible
        while the card is ticked, so the sidebar never stacks up gradients for
        layers that are not drawn.
        """
        if self._variable["kind"] == "scalar":
            ramp, middle = color_ramp_for(self._variable["name"])
            body.addWidget(ColorBar(ramp))
        else:
            middle = "wind barbs" if is_wind_variable(self._variable["name"]) else "arrows"

        unit = (self._variable.get("unit") or "").strip()
        row = QHBoxLayout()
        row.addWidget(_muted(_fmt(self._variable["vmin"])))
        row.addStretch()
        row.addWidget(_muted(" · ".join(part for part in (unit, middle) if part)))
        row.addStretch()
        row.addWidget(_muted(_fmt(self._variable["vmax"])))
        body.addLayout(row)

    def _build_opacity(self, body):
        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(6)
        opacity_row.addWidget(_muted("Opacity"))

        percent = self._variable.get("default_opacity", 75)
        self._opacity = QSlider(Qt.Horizontal)
        self._opacity.setRange(10, 100)
        self._opacity.setValue(percent)
        self._opacity.valueChanged.connect(self._on_opacity)
        opacity_row.addWidget(self._opacity, 1)

        self._opacity_label = _muted(f"{percent}%")
        self._opacity_label.setMinimumWidth(30)
        opacity_row.addWidget(self._opacity_label)
        body.addLayout(opacity_row)

    def mousePressEvent(self, event):
        """Anywhere on the card selects it; the slider keeps its own clicks."""
        if event.button() == Qt.LeftButton:
            self._check.toggle()
        super().mousePressEvent(event)

    def _refresh_highlight(self):
        is_selected = self._check.isChecked()
        self.setProperty("selected", "true" if is_selected else "false")
        self._layout.setContentsMargins(*(_MARGINS_SELECTED if is_selected else _MARGINS))
        self.style().unpolish(self)
        self.style().polish(self)

    def _on_toggled(self, checked):
        self._body.setVisible(checked)
        self._refresh_highlight()
        self.toggled.emit(checked)

    def _on_opacity(self, value):
        self._opacity_label.setText(f"{value}%")
        self.opacity_changed.emit(value / 100.0)

    def opacity(self):
        return self._opacity.value() / 100.0

    def is_checked(self):
        return self._check.isChecked()

    def set_checked(self, checked):
        self._check.setChecked(checked)

    def set_checked_silently(self, checked):
        """Untick without re-entering the toggle handler that is ticking us."""
        blocked = self._check.blockSignals(True)
        self._check.setChecked(checked)
        self._check.blockSignals(blocked)
        self._body.setVisible(checked)
        self._refresh_highlight()
