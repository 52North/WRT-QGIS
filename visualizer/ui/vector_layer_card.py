"""One chip for a vector field: arrows and colour ramp, ticked independently."""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QSlider, QVBoxLayout

from ..styling.mesh_styler import is_wind_variable
from .layer_card import _DEFAULT_ACCENT, _MARGINS, _MARGINS_SELECTED, _card_qss, _muted

COLORMAP_LABEL = "Colormap"


class AxisProxy:
    """Adapts one axis of a VectorLayerCard to the LayerCard interface."""

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
    """A vector field's arrows and its colour ramp, as two independent ticks.

    Both ticks drive the same dataset group: QGIS paints a vector group's
    magnitude when it is picked as the active scalar group, so the colour ramp
    needs no second group behind it. The arrows lead because they are what a
    click anywhere on the chip turns on.
    """

    colormap_toggled = pyqtSignal(bool)
    vectors_toggled = pyqtSignal(bool)
    opacity_changed = pyqtSignal(float)

    def __init__(self, variable, parent=None):
        super().__init__(parent)
        self._variable = variable
        self._is_wind = is_wind_variable(variable["name"])
        self.setObjectName("LayerCard")
        accent, tint = _DEFAULT_ACCENT
        self.setStyleSheet(_card_qss(accent, tint))
        self.setCursor(Qt.PointingHandCursor)
        self._build_ui()
        self._refresh_highlight()

    @property
    def vectors_label(self):
        """Barbs are the meteorological convention for wind, arrows for the rest."""
        return "Barbs" if self._is_wind else "Arrows"

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

        badge = QLabel("vectors")
        badge.setObjectName("TypeBadge")
        header.addWidget(badge, 0, Qt.AlignTop)
        self._layout.addLayout(header)

        self._checks = {}
        ticks = QHBoxLayout()
        ticks.setSpacing(14)
        for axis, label in (("vector", self.vectors_label), ("scalar", COLORMAP_LABEL)):
            check = QCheckBox(label)
            check.setCursor(Qt.PointingHandCursor)
            check.toggled.connect(lambda checked, a=axis: self._on_toggled(a, checked))
            ticks.addWidget(check)
            self._checks[axis] = check
        ticks.addStretch()
        self._layout.addLayout(ticks)

        self._body = QFrame()
        body = QVBoxLayout(self._body)
        body.setContentsMargins(2, 0, 2, 0)
        body.setSpacing(4)
        self._build_opacity(body)
        self._body.setVisible(False)
        self._layout.addWidget(self._body)

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
        """Anywhere on the chip toggles its vectors; the ticks and slider keep their own clicks."""
        if event.button() == Qt.LeftButton:
            self._checks["vector"].toggle()
        super().mousePressEvent(event)

    def _refresh_highlight(self):
        """Either tick lights the chip up and reveals the opacity slider."""
        is_selected = any(check.isChecked() for check in self._checks.values())
        self.setProperty("selected", "true" if is_selected else "false")
        self._layout.setContentsMargins(*(_MARGINS_SELECTED if is_selected else _MARGINS))
        self._body.setVisible(is_selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def _on_toggled(self, axis, checked):
        self._refresh_highlight()
        if axis == "scalar":
            self.colormap_toggled.emit(checked)
        else:
            self.vectors_toggled.emit(checked)

    def _on_opacity(self, value):
        self._opacity_label.setText(f"{value}%")
        self.opacity_changed.emit(value / 100.0)

    def opacity(self):
        return self._opacity.value() / 100.0

    def is_checked(self, axis):
        return self._checks[axis].isChecked()

    def set_checked(self, axis, checked):
        self._checks[axis].setChecked(checked)

    def set_checked_silently(self, axis, checked):
        """Untick without re-entering the toggle handler that is ticking us."""
        check = self._checks[axis]
        blocked = check.blockSignals(True)
        check.setChecked(checked)
        check.blockSignals(blocked)
        self._refresh_highlight()
