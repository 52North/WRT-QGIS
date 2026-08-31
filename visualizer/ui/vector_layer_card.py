from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QFrame, QHBoxLayout, QLabel, QSlider, QVBoxLayout

from ..styling.mesh_styler import color_ramp_for, is_wind_variable
from .axis_chip import AxisChip
from .layer_card import (
    _BADGES,
    _DEFAULT_ACCENT,
    _MARGINS,
    _MARGINS_SELECTED,
    _card_qss,
    _muted,
    _row_label,
)


class AxisProxy:
    """Adapts one axis of a VectorLayerCard to the LayerCard interface the panel expects."""

    def __init__(self, card, axis):
        self.widget = card
        self._card = card
        self._axis = axis

    def is_checked(self):
        return self._card.is_checked(self._axis)

    def set_checked(self, checked):
        self._card.set_checked(self._axis, checked)

    def set_checked_silently(self, checked):
        self._card.set_checked_silently(self._axis, checked)

    def opacity(self):
        return self._card.opacity()


class VectorLayerCard(QFrame):
    """A vector field's colourmap and arrows, ticked independently.

    Each chip is authoritative on its own state — there is no card-level tick to
    keep in sync with them, so one field's colourmap and another field's arrows
    can be on together without either chip having to evict the other's card.
    """

    colormap_toggled = pyqtSignal(bool)
    vectors_toggled = pyqtSignal(bool)
    opacity_changed = pyqtSignal(float)

    def __init__(self, variable, parent=None):
        super().__init__(parent)
        self._variable = variable
        self.setObjectName("LayerCard")
        accent, tint = _DEFAULT_ACCENT
        self.setStyleSheet(_card_qss(accent, tint))
        self.setCursor(Qt.PointingHandCursor)
        self._build_ui()
        self._refresh_highlight()

    def _build_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(*_MARGINS)
        self._layout.setSpacing(6)

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
        body.setContentsMargins(2, 2, 2, 0)
        body.setSpacing(6)
        self._build_axis_chips(body)
        self._build_opacity(body)
        self._body.setVisible(False)
        self._layout.addWidget(self._body)

    def _build_axis_chips(self, body):
        name = self._variable["name"]
        symbol = "wind barbs" if is_wind_variable(name) else "arrows"
        accent, tint = _DEFAULT_ACCENT
        _ramp, ramp_name = color_ramp_for(name)

        self._colormap = AxisChip(
            "Colourmap",
            f"Paint this field's magnitude as a colour-ramped surface ({ramp_name})",
            accent,
            tint,
        )
        self._vectors = AxisChip(
            "Vectors", f"Draw this field's direction as {symbol}", accent, tint
        )
        self._colormap.setChecked(False)
        self._vectors.setChecked(False)
        self._colormap.toggled.connect(self.colormap_toggled)
        self._colormap.toggled.connect(self._refresh_highlight)
        self._vectors.toggled.connect(self.vectors_toggled)
        self._vectors.toggled.connect(self._refresh_highlight)

        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self._colormap)
        row.addWidget(self._vectors)
        row.addStretch()
        body.addLayout(row)

    def _build_opacity(self, body):
        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(6)
        opacity_row.addWidget(_row_label("Opacity"))

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
        """Anywhere on the card toggles its arrows; the chips and slider keep their own clicks."""
        if event.button() == Qt.LeftButton:
            self._vectors.toggle()
        super().mousePressEvent(event)

    def _refresh_highlight(self):
        """Either chip lights the card up and reveals the opacity slider."""
        is_selected = self._colormap.isChecked() or self._vectors.isChecked()
        self.setProperty("selected", "true" if is_selected else "false")
        self._layout.setContentsMargins(*(_MARGINS_SELECTED if is_selected else _MARGINS))
        self._body.setVisible(is_selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def _on_opacity(self, value):
        self._opacity_label.setText(f"{value}%")
        self.opacity_changed.emit(value / 100.0)

    def opacity(self):
        return self._opacity.value() / 100.0

    def _chip(self, axis):
        return self._colormap if axis == "scalar" else self._vectors

    def is_checked(self, axis):
        return self._chip(axis).isChecked()

    def set_checked(self, axis, checked):
        self._chip(axis).setChecked(checked)

    def set_checked_silently(self, axis, checked):
        """Untick without re-entering the toggle handler that is evicting us."""
        chip = self._chip(axis)
        blocked = chip.blockSignals(True)
        chip.setChecked(checked)
        chip.blockSignals(blocked)
        self._refresh_highlight()
