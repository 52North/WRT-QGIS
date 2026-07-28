"""Page 3 — Boat configuration."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from ..core.defaults import (
    ALGO_BOAT_COMPAT,
    ALGO_BOAT_COMPAT_DEFAULT,
    BOAT_TYPE_OPTIONS,
)
from ..ui.ui_kit import (
    COLOR_MUTED,
    COLOR_WARNING,
    StatusLine,
    collapsible,
    dspin,
    field_label,
    ispin,
    join_terms,
    opt_label,
    page_header,
    req_label,
)

_BOAT_TYPE_LABELS = dict(BOAT_TYPE_OPTIONS)

# Fixed stack position per boat type — independent of the (filtered) combo order.
_BOAT_STACK = {
    "direct_power_method": 0,
    "CBT": 1,
    "speedy_isobased": 2,
}


def _compatible_boat_types(algo):
    """Boat types valid for the chosen algorithm (Page 1 picks algorithm first)."""
    return ALGO_BOAT_COMPAT.get(algo, ALGO_BOAT_COMPAT_DEFAULT)


# Every boat-related config key — cleared on save so only the active method contributes to the exported JSON.
BOAT_ALL_KEYS = [
    "BOAT_LENGTH",
    "BOAT_BREADTH",
    "BOAT_TYPE",
    "BOAT_SPEED",
    "BOAT_FUEL_RATE",
    "BOAT_HBR",
    "BOAT_SMCR_POWER",
    "BOAT_SMCR_SPEED",
    "BOAT_ROUGHNESS_DISTRIBUTION_LEVEL",
    "BOAT_ROUGHNESS_LEVEL",
    "BOAT_DRAUGHT_AFT",
    "BOAT_DRAUGHT_FORE",
    "BOAT_UNDER_KEEL_CLEARANCE",
    "BOAT_OVERLOAD_FACTOR",
    "BOAT_PROPULSION_EFFICIENCY",
    "BOAT_SPEED_MAX",
    "BOAT_AOD",
    "BOAT_AXV",
    "BOAT_AYV",
    "BOAT_CMC",
    "BOAT_HC",
    "BOAT_BS1",
    "BOAT_HS1",
    "BOAT_HS2",
    "BOAT_LS1",
    "BOAT_LS2",
    "BOAT_FACTOR_CALM_WATER",
    "BOAT_FACTOR_WAVE_FORCES",
    "BOAT_FACTOR_WIND_FORCES",
    "AIR_MASS_DENSITY",
    "COURSES_FILE",
]

ADV_KEYS = [
    ("dp_aod", "BOAT_AOD"),
    ("dp_axv", "BOAT_AXV"),
    ("dp_ayv", "BOAT_AYV"),
    ("dp_cmc", "BOAT_CMC"),
    ("dp_hc", "BOAT_HC"),
    ("dp_bs1", "BOAT_BS1"),
    ("dp_hs1", "BOAT_HS1"),
    ("dp_hs2", "BOAT_HS2"),
    ("dp_ls1", "BOAT_LS1"),
    ("dp_ls2", "BOAT_LS2"),
]


class BoatPage(QWizardPage):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.status = None
        self._build_ui()

    # UI construction
    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        scroll.setWidget(inner)
        root = QVBoxLayout(inner)
        root.setContentsMargins(28, 22, 28, 18)
        root.setSpacing(14)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # Status line pinned below the scroll area so it stays visible.
        status_wrap = QWidget()
        sw = QVBoxLayout(status_wrap)
        sw.setContentsMargins(28, 0, 28, 12)
        self.status = StatusLine()
        sw.addWidget(self.status)
        outer.addWidget(status_wrap)
        self.completeChanged.connect(self._update_status)

        root.addWidget(
            page_header(
                "Boat configuration",
                "Choose the boat type, then set the parameters for that method. "
                "Fields marked * are required.",
            )
        )

        # Boat type
        root.addWidget(field_label("Boat type", required=True))
        self.boat_type = QComboBox()
        self.boat_type.currentIndexChanged.connect(self._on_boat_type_changed)
        root.addWidget(self.boat_type)

        # Speed
        self.speed_label = field_label("Speed", required=True)
        root.addWidget(self.speed_label)
        self.speed_ms = dspin(val=6.17, suffix="m/s", mx=60, dec=3)
        speed_tip = "Typical merchant-ship cruising speed is around 7–12 m/s (≈14–23 knots)."
        self.speed_label.setToolTip(speed_tip)
        self.speed_ms.setToolTip(speed_tip)
        self.speed_ms.valueChanged.connect(self.completeChanged)
        root.addWidget(self.speed_ms)

        # Shown instead of the speed field for all genetic intents (speed is set on the Algorithm step).
        self.speed_note = QLabel(
            "Speed is configured in the Algorithm step for the genetic algorithm."
        )
        self.speed_note.setWordWrap(True)
        self.speed_note.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        root.addWidget(self.speed_note)

        # Per-type parameter stack
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_direct_power_panel())  # 0
        self.stack.addWidget(self._build_cbt_panel())  # 1
        self.stack.addWidget(self._build_speedy_panel())  # 2
        root.addWidget(self.stack)

        root.addStretch()
        self._update_status()

    def _maripower_advanced(self, prefix):
        """Shared advanced parameters for the CBT maripower method."""
        btn, box = collapsible("Advanced — hull & propulsion")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(8)

        setattr(self, f"{prefix}_draught_aft", dspin(val=10, suffix="m"))
        setattr(self, f"{prefix}_draught_fore", dspin(val=10, suffix="m"))
        setattr(self, f"{prefix}_roughness_dist", ispin(val=1, mn=1))
        setattr(self, f"{prefix}_roughness_lvl", ispin(val=1, mn=1))
        setattr(self, f"{prefix}_under_keel", dspin(val=20, suffix="m"))
        setattr(self, f"{prefix}_overload", dspin(val=0))
        setattr(self, f"{prefix}_prop_eff", dspin(val=0.63, dec=3))
        setattr(self, f"{prefix}_factor_calm", dspin(val=1.0, dec=3))
        setattr(self, f"{prefix}_factor_wave", dspin(val=1.0, dec=3))
        setattr(self, f"{prefix}_factor_wind", dspin(val=1.0, dec=3))

        form.addRow(
            opt_label("Draught aft", "Draught at rudder"), getattr(self, f"{prefix}_draught_aft")
        )
        form.addRow(
            opt_label("Draught fore", "Draught at forward perpendicular"),
            getattr(self, f"{prefix}_draught_fore"),
        )
        form.addRow(
            opt_label("Roughness distribution level"), getattr(self, f"{prefix}_roughness_dist")
        )
        form.addRow(opt_label("Roughness level"), getattr(self, f"{prefix}_roughness_lvl"))
        form.addRow(opt_label("Under-keel clearance"), getattr(self, f"{prefix}_under_keel"))
        form.addRow(opt_label("Overload factor"), getattr(self, f"{prefix}_overload"))
        form.addRow(
            opt_label("Propulsion efficiency", "Ideal conditions coefficient"),
            getattr(self, f"{prefix}_prop_eff"),
        )
        form.addRow(opt_label("Factor — calm water"), getattr(self, f"{prefix}_factor_calm"))
        form.addRow(opt_label("Factor — wave forces"), getattr(self, f"{prefix}_factor_wave"))
        form.addRow(opt_label("Factor — wind forces"), getattr(self, f"{prefix}_factor_wind"))
        return btn, box

    def _build_direct_power_panel(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        req = QGroupBox("Required — direct power method")
        form = QFormLayout(req)
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(8)
        self.dp_length = dspin(suffix="m")
        self.dp_breadth = dspin(suffix="m")
        self.dp_smcr_power = dspin(suffix="kW", mx=999999)
        self.dp_smcr_speed = dspin(dec=3, suffix="m/s")
        self.dp_fuel_rate = dspin(suffix="g/kWh", mx=9999)
        self.dp_hbr = dspin(suffix="m")
        for x in (
            self.dp_length,
            self.dp_breadth,
            self.dp_smcr_power,
            self.dp_smcr_speed,
            self.dp_fuel_rate,
            self.dp_hbr,
        ):
            x.valueChanged.connect(self.completeChanged)
        form.addRow(req_label("Length overall"), self.dp_length)
        form.addRow(req_label("Breadth"), self.dp_breadth)
        form.addRow(req_label("SMCR power"), self.dp_smcr_power)
        form.addRow(req_label("Avg. speed at SMCR"), self.dp_smcr_speed)
        form.addRow(req_label("Fuel rate"), self.dp_fuel_rate)
        form.addRow(req_label("Max height (HBR)"), self.dp_hbr)
        v.addWidget(req)

        btn, box = collapsible("Advanced — resistance & wind/area")
        adv = QFormLayout(box)
        adv.setLabelAlignment(Qt.AlignRight)
        adv.setSpacing(8)
        self.dp_draught_aft = dspin(val=10, suffix="m")
        self.dp_draught_fore = dspin(val=10, suffix="m")
        self.dp_roughness_dist = ispin(val=1, mn=1)
        self.dp_roughness_lvl = ispin(val=1, mn=1)
        self.dp_under_keel = dspin(val=20, suffix="m")
        self.dp_overload = dspin(val=0)
        self.dp_prop_eff = dspin(val=0.63, dec=3)
        self.dp_speed_max = dspin(suffix="m/s")
        self.dp_air_density = dspin(val=1.2225, dec=4, suffix="kg/m³")
        self.dp_factor_calm = dspin(val=1.0, dec=3)
        self.dp_factor_wave = dspin(val=1.0, dec=3)
        self.dp_factor_wind = dspin(val=1.0, dec=3)
        self.dp_aod = dspin(suffix="m²")
        self.dp_axv = dspin(suffix="m²")
        self.dp_ayv = dspin(suffix="m²")
        self.dp_cmc = dspin(suffix="m")
        self.dp_hc = dspin(suffix="m")
        self.dp_bs1 = dspin(suffix="m")
        self.dp_hs1 = dspin(suffix="m")
        self.dp_hs2 = dspin(suffix="m")
        self.dp_ls1 = dspin(suffix="m")
        self.dp_ls2 = dspin(suffix="m")

        adv.addRow(opt_label("Draught aft"), self.dp_draught_aft)
        adv.addRow(opt_label("Draught fore"), self.dp_draught_fore)
        adv.addRow(opt_label("Roughness distribution level"), self.dp_roughness_dist)
        adv.addRow(opt_label("Roughness level"), self.dp_roughness_lvl)
        adv.addRow(opt_label("Under-keel clearance"), self.dp_under_keel)
        adv.addRow(opt_label("Overload factor"), self.dp_overload)
        adv.addRow(opt_label("Propulsion efficiency"), self.dp_prop_eff)
        adv.addRow(opt_label("Max speed"), self.dp_speed_max)
        adv.addRow(opt_label("Air mass density"), self.dp_air_density)
        adv.addRow(opt_label("Factor — calm water"), self.dp_factor_calm)
        adv.addRow(opt_label("Factor — wave forces"), self.dp_factor_wave)
        adv.addRow(opt_label("Factor — wind forces"), self.dp_factor_wind)
        adv.addRow(QLabel("<b>Wind/area parameters</b>"))
        adv.addRow(opt_label("AOD (lateral area on deck)"), self.dp_aod)
        adv.addRow(opt_label("AXV (max transverse section)"), self.dp_axv)
        adv.addRow(opt_label("AYV (projected lateral area)"), self.dp_ayv)
        adv.addRow(opt_label("CMC (horiz. dist. midship → AYV)"), self.dp_cmc)
        adv.addRow(opt_label("HC (waterline → centre AYV)"), self.dp_hc)
        adv.addRow(opt_label("BS1"), self.dp_bs1)
        adv.addRow(opt_label("HS1"), self.dp_hs1)
        adv.addRow(opt_label("HS2"), self.dp_hs2)
        adv.addRow(opt_label("LS1"), self.dp_ls1)
        adv.addRow(opt_label("LS2"), self.dp_ls2)
        v.addWidget(btn)
        v.addWidget(box)
        v.addStretch()
        return w

    def _build_cbt_panel(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        req = QGroupBox("Required — CBT (maripower)")
        form = QFormLayout(req)
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(8)
        self.cbt_length = dspin(suffix="m")
        self.cbt_breadth = dspin(suffix="m")
        self.cbt_smcr_power = dspin(suffix="kW", mx=999999)
        self.cbt_smcr_speed = dspin(dec=3, suffix="m/s")
        self.cbt_fuel_rate = dspin(suffix="g/kWh", mx=9999)
        self.cbt_courses = QLineEdit()
        self.cbt_courses.setPlaceholderText("/path/to/courses.nc")
        self.cbt_courses.textChanged.connect(self.completeChanged)
        browse = QPushButton("Browse…")
        browse.clicked.connect(lambda: self._browse_file(self.cbt_courses, "NetCDF (*.nc)"))
        courses_row = QHBoxLayout()
        courses_row.addWidget(self.cbt_courses)
        courses_row.addWidget(browse)
        for x in (
            self.cbt_length,
            self.cbt_breadth,
            self.cbt_smcr_power,
            self.cbt_smcr_speed,
            self.cbt_fuel_rate,
        ):
            x.valueChanged.connect(self.completeChanged)
        form.addRow(req_label("Length overall"), self.cbt_length)
        form.addRow(req_label("Breadth"), self.cbt_breadth)
        form.addRow(req_label("SMCR power"), self.cbt_smcr_power)
        form.addRow(req_label("Avg. speed at SMCR"), self.cbt_smcr_speed)
        form.addRow(req_label("Fuel rate"), self.cbt_fuel_rate)
        form.addRow(req_label("Courses file"), courses_row)
        v.addWidget(req)

        btn, box = self._maripower_advanced("cbt")
        v.addWidget(btn)
        v.addWidget(box)
        v.addStretch()
        return w

    def _build_speedy_panel(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        note = QLabel(
            "Speedy isobased is for testing only. It uses the constant "
            "<b>Speed</b> above and needs no further parameters."
        )
        note.setTextFormat(Qt.RichText)
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {COLOR_WARNING}; font-size: 12px; padding: 12px;")
        v.addWidget(note)
        v.addStretch()
        return w

    # Behaviour
    def _on_boat_type_changed(self, idx):
        bt = self.boat_type.currentData()
        self.stack.setCurrentIndex(_BOAT_STACK.get(bt, 0))
        self.completeChanged.emit()

    def _populate_boat_types(self):
        """Restrict the boat-type combo to the types valid for the chosen algorithm."""
        algo = self.config.get("ALGORITHM_TYPE", "isofuel")
        allowed = _compatible_boat_types(algo)
        current = self.boat_type.currentData()
        self.boat_type.blockSignals(True)
        self.boat_type.clear()
        for val in allowed:
            self.boat_type.addItem(_BOAT_TYPE_LABELS.get(val, val), val)
        idx = self.boat_type.findData(current)
        self.boat_type.setCurrentIndex(idx if idx >= 0 else 0)
        self.boat_type.blockSignals(False)

    def _speed_hidden(self):
        """Speed is always configured on the Algorithm step for genetic — never asked here."""
        return self.config.get("ALGORITHM_TYPE") == "genetic"

    def _apply_speed_visibility(self):
        hidden = self._speed_hidden()
        self.speed_label.setVisible(not hidden)
        self.speed_ms.setVisible(not hidden)
        self.speed_note.setVisible(hidden)

    def _browse_file(self, line_edit, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, "Select file", line_edit.text(), file_filter)
        if path:
            line_edit.setText(path)

    def _missing_fields(self):
        """List the required fields not yet set, for the active boat type."""
        bt = self.boat_type.currentData()
        missing = []
        if not self._speed_hidden() and self.speed_ms.value() <= 0:
            missing.append("speed")
        if bt == "speedy_isobased":
            return missing
        if bt == "direct_power_method":
            if self.dp_length.value() <= 0:
                missing.append("length")
            if self.dp_breadth.value() <= 0:
                missing.append("breadth")
            if self.dp_smcr_power.value() <= 0:
                missing.append("SMCR power")
            if self.dp_smcr_speed.value() <= 0:
                missing.append("speed at SMCR")
            if self.dp_fuel_rate.value() <= 0:
                missing.append("fuel rate")
            if self.dp_hbr.value() <= 0:
                missing.append("max height (HBR)")
        elif bt == "CBT":
            if self.cbt_length.value() <= 0:
                missing.append("length")
            if self.cbt_breadth.value() <= 0:
                missing.append("breadth")
            if self.cbt_smcr_power.value() <= 0:
                missing.append("SMCR power")
            if self.cbt_smcr_speed.value() <= 0:
                missing.append("speed at SMCR")
            if self.cbt_fuel_rate.value() <= 0:
                missing.append("fuel rate")
            if not self.cbt_courses.text().strip():
                missing.append("courses file")
        return missing

    def _update_status(self):
        if self.status is None:
            return  # still being constructed
        missing = self._missing_fields()
        if not missing:
            self.status.set_ok("Boat type, dimensions & power parameters set")
        else:
            self.status.set_pending("Set " + join_terms(missing) + " to continue")

    def isComplete(self):
        bt = self.boat_type.currentData()
        if not self._speed_hidden() and self.speed_ms.value() <= 0:
            return False
        if bt == "speedy_isobased":
            return True
        if bt == "direct_power_method":
            return (
                self.dp_length.value() > 0
                and self.dp_breadth.value() > 0
                and self.dp_smcr_power.value() > 0
                and self.dp_smcr_speed.value() > 0
                and self.dp_fuel_rate.value() > 0
                and self.dp_hbr.value() > 0
            )
        if bt == "CBT":
            return (
                self.cbt_length.value() > 0
                and self.cbt_breadth.value() > 0
                and self.cbt_smcr_power.value() > 0
                and self.cbt_smcr_speed.value() > 0
                and self.cbt_fuel_rate.value() > 0
                and bool(self.cbt_courses.text().strip())
            )
        return True

    # Config persistence
    def save_to_config(self):
        c = self.config
        for key in BOAT_ALL_KEYS:
            c.pop(key, None)

        bt = self.boat_type.currentData()
        c["BOAT_TYPE"] = bt
        # In genetic waypoints-only "via arrival" mode the schedule is fixed by
        # arrival time, so BOAT_SPEED is left unset (the optimization page owns it).
        if not self._speed_hidden():
            c["BOAT_SPEED"] = self.speed_ms.value()

        if bt == "direct_power_method":
            c["BOAT_LENGTH"] = self.dp_length.value()
            c["BOAT_BREADTH"] = self.dp_breadth.value()
            self._save_direct(c)
        elif bt == "CBT":
            c["BOAT_LENGTH"] = self.cbt_length.value()
            c["BOAT_BREADTH"] = self.cbt_breadth.value()
            c["BOAT_SMCR_POWER"] = self.cbt_smcr_power.value()
            c["BOAT_SMCR_SPEED"] = self.cbt_smcr_speed.value()
            c["BOAT_FUEL_RATE"] = self.cbt_fuel_rate.value()
            c["COURSES_FILE"] = self.cbt_courses.text().strip()
            self._save_maripower(c, "cbt")
        # speedy_isobased: only the common fields above.

    def _save_direct(self, c):
        c["BOAT_SMCR_POWER"] = self.dp_smcr_power.value()
        c["BOAT_SMCR_SPEED"] = self.dp_smcr_speed.value()
        c["BOAT_FUEL_RATE"] = self.dp_fuel_rate.value()
        c["BOAT_HBR"] = self.dp_hbr.value()
        c["BOAT_DRAUGHT_AFT"] = self.dp_draught_aft.value()
        c["BOAT_DRAUGHT_FORE"] = self.dp_draught_fore.value()
        c["BOAT_ROUGHNESS_DISTRIBUTION_LEVEL"] = self.dp_roughness_dist.value()
        c["BOAT_ROUGHNESS_LEVEL"] = self.dp_roughness_lvl.value()
        c["BOAT_UNDER_KEEL_CLEARANCE"] = self.dp_under_keel.value()
        c["BOAT_OVERLOAD_FACTOR"] = self.dp_overload.value()
        c["BOAT_PROPULSION_EFFICIENCY"] = self.dp_prop_eff.value()
        c["BOAT_SPEED_MAX"] = self.dp_speed_max.value() or None
        c["AIR_MASS_DENSITY"] = self.dp_air_density.value()
        c["BOAT_FACTOR_CALM_WATER"] = self.dp_factor_calm.value()
        c["BOAT_FACTOR_WAVE_FORCES"] = self.dp_factor_wave.value()
        c["BOAT_FACTOR_WIND_FORCES"] = self.dp_factor_wind.value()
        for attr, key in ADV_KEYS:
            v = getattr(self, attr).value()
            c[key] = v if v > 0 else None

    def _save_maripower(self, c, p):
        c["BOAT_DRAUGHT_AFT"] = getattr(self, f"{p}_draught_aft").value()
        c["BOAT_DRAUGHT_FORE"] = getattr(self, f"{p}_draught_fore").value()
        c["BOAT_ROUGHNESS_DISTRIBUTION_LEVEL"] = getattr(self, f"{p}_roughness_dist").value()
        c["BOAT_ROUGHNESS_LEVEL"] = getattr(self, f"{p}_roughness_lvl").value()
        c["BOAT_UNDER_KEEL_CLEARANCE"] = getattr(self, f"{p}_under_keel").value()
        c["BOAT_OVERLOAD_FACTOR"] = getattr(self, f"{p}_overload").value()
        c["BOAT_PROPULSION_EFFICIENCY"] = getattr(self, f"{p}_prop_eff").value()
        c["BOAT_FACTOR_CALM_WATER"] = getattr(self, f"{p}_factor_calm").value()
        c["BOAT_FACTOR_WAVE_FORCES"] = getattr(self, f"{p}_factor_wave").value()
        c["BOAT_FACTOR_WIND_FORCES"] = getattr(self, f"{p}_factor_wind").value()

    def initializePage(self):
        c = self.config
        length_val = float(c.get("BOAT_LENGTH") or 0)
        breadth_val = float(c.get("BOAT_BREADTH") or 0)
        self.dp_length.setValue(length_val)
        self.dp_breadth.setValue(breadth_val)
        self.cbt_length.setValue(length_val)
        self.cbt_breadth.setValue(breadth_val)
        raw_speed = float(c.get("BOAT_SPEED") or 0)
        self.speed_ms.setValue(raw_speed if raw_speed else 6.17)

        # Direct power method
        self.dp_smcr_power.setValue(float(c.get("BOAT_SMCR_POWER") or 0))
        self.dp_smcr_speed.setValue(float(c.get("BOAT_SMCR_SPEED") or 0))
        self.dp_fuel_rate.setValue(float(c.get("BOAT_FUEL_RATE") or 0))
        self.dp_hbr.setValue(float(c.get("BOAT_HBR") or 0))
        self.dp_draught_aft.setValue(float(c.get("BOAT_DRAUGHT_AFT") or 10))
        self.dp_draught_fore.setValue(float(c.get("BOAT_DRAUGHT_FORE") or 10))
        self.dp_roughness_dist.setValue(int(c.get("BOAT_ROUGHNESS_DISTRIBUTION_LEVEL") or 1))
        self.dp_roughness_lvl.setValue(int(c.get("BOAT_ROUGHNESS_LEVEL") or 1))
        self.dp_under_keel.setValue(float(c.get("BOAT_UNDER_KEEL_CLEARANCE") or 20))
        self.dp_overload.setValue(float(c.get("BOAT_OVERLOAD_FACTOR") or 0))
        self.dp_prop_eff.setValue(float(c.get("BOAT_PROPULSION_EFFICIENCY") or 0.63))
        self.dp_air_density.setValue(float(c.get("AIR_MASS_DENSITY") or 1.2225))
        self.dp_factor_calm.setValue(float(c.get("BOAT_FACTOR_CALM_WATER") or 1))
        self.dp_factor_wave.setValue(float(c.get("BOAT_FACTOR_WAVE_FORCES") or 1))
        self.dp_factor_wind.setValue(float(c.get("BOAT_FACTOR_WIND_FORCES") or 1))
        for attr, key in ADV_KEYS:
            getattr(self, attr).setValue(float(c.get(key) or 0))

        # CBT (maripower)
        self.cbt_smcr_power.setValue(float(c.get("BOAT_SMCR_POWER") or 0))
        self.cbt_smcr_speed.setValue(float(c.get("BOAT_SMCR_SPEED") or 0))
        self.cbt_fuel_rate.setValue(float(c.get("BOAT_FUEL_RATE") or 0))
        self.cbt_draught_aft.setValue(float(c.get("BOAT_DRAUGHT_AFT") or 10))
        self.cbt_draught_fore.setValue(float(c.get("BOAT_DRAUGHT_FORE") or 10))
        self.cbt_roughness_dist.setValue(int(c.get("BOAT_ROUGHNESS_DISTRIBUTION_LEVEL") or 1))
        self.cbt_roughness_lvl.setValue(int(c.get("BOAT_ROUGHNESS_LEVEL") or 1))
        self.cbt_under_keel.setValue(float(c.get("BOAT_UNDER_KEEL_CLEARANCE") or 20))
        self.cbt_overload.setValue(float(c.get("BOAT_OVERLOAD_FACTOR") or 0))
        self.cbt_prop_eff.setValue(float(c.get("BOAT_PROPULSION_EFFICIENCY") or 0.63))
        self.cbt_factor_calm.setValue(float(c.get("BOAT_FACTOR_CALM_WATER") or 1))
        self.cbt_factor_wave.setValue(float(c.get("BOAT_FACTOR_WAVE_FORCES") or 1))
        self.cbt_factor_wind.setValue(float(c.get("BOAT_FACTOR_WIND_FORCES") or 1))
        self.cbt_courses.setText(c.get("COURSES_FILE", ""))

        # Boat type — restrict to the algorithm's compatible types, then restore.
        self._populate_boat_types()
        bt = c.get("BOAT_TYPE", "direct_power_method")
        idx = self.boat_type.findData(bt)
        if idx < 0:
            idx = 0
        self.boat_type.setCurrentIndex(idx)
        self.stack.setCurrentIndex(_BOAT_STACK.get(self.boat_type.currentData(), 0))
        self._apply_speed_visibility()
        self._update_status()
