"""Page 2 — Algorithm selection & parameters.

The algorithm is chosen on this page; the parameter panel below switches to
match the selection.
"""

from qgis.PyQt.QtCore import QDateTime, Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
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
    ALGORITHM_OPTIONS,
    GENETIC_CROSSOVER_PATCHER_OPTIONS,
    GENETIC_INTENT_CROSSOVER,
    GENETIC_INTENT_OPTIONS,
    GENETIC_MUTATION_OPTIONS,
    GENETIC_MUTATION_SPEED_OPTIONS,
    GENETIC_MUTATION_WAYPOINT_OPTIONS,
    GENETIC_POPULATION_OPTIONS,
    GENETIC_REPAIR_OPTIONS,
    MINIMISATION_OPTIONS,
    PRUNE_GROUP_OPTIONS,
    SYMMETRY_AXIS_OPTIONS,
)
from ..ui.ui_kit import (
    COLOR_MUTED,
    COLOR_WARNING,
    StatusLine,
    collapsible,
    dspin,
    field_label,
    ispin,
    opt_label,
    page_header,
)

# Fixed stack position for each algorithm.
_ALGO_STACK = {
    "isofuel": 0,
    "genetic": 1,
    "gcr_slider": 2,
    "dijkstra": 3,
    "genetic_shortest_route": 4,
    "speedy_isobased": 5,
}

_ALGO_LABELS = dict(ALGORITHM_OPTIONS)

_ALGO_DESCRIPTIONS = {
    "isofuel": "Isochrone-based fuel optimisation over waypoints.",
    "genetic": "Multi-objective optimisation of waypoints and/or speed (fuel & arrival-time accuracy).",
    "gcr_slider": "Great-circle-route slider optimising distance.",
    "dijkstra": "Graph shortest-path optimising distance.",
    "genetic_shortest_route": "Genetic optimisation of the shortest route using the speedy-isobased boat model.",
    "speedy_isobased": "Testing-only isobased model using a constant speed.",
}

_INTENT_DESCRIPTIONS = {
    "waypoints": "Optimise the route geometry at a fixed schedule. Crossover and "
    "mutation are restricted to waypoint operators; only fuel "
    "consumption is optimised.",
    "speed_waypoints": "Optimise both the route geometry and the speed profile. "
    "Fuel consumption and/or arrival-time accuracy can be weighted.",
    "speed": "Optimise only the speed profile on a fixed route. Not yet "
    "implemented in the routing tool.",
}


def _combo(options):
    c = QComboBox()
    for val, lbl in options:
        c.addItem(lbl, val)
    return c


class AlgorithmPage(QWizardPage):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.status = None
        self._build_ui()

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

        status_wrap = QWidget()
        sw = QVBoxLayout(status_wrap)
        sw.setContentsMargins(28, 0, 28, 12)
        self.status = StatusLine()
        sw.addWidget(self.status)
        outer.addWidget(status_wrap)

        self.header_lbl = page_header(
            "Routing algorithm",
            "Choose a algorithm, its optimisation goal, then tune its parameters.",
        )
        root.addWidget(self.header_lbl)

        # Algorithm picker
        root.addWidget(field_label("Choose an algorithm"))
        self.algo_combo = QComboBox()
        for val, lbl in ALGORITHM_OPTIONS:
            self.algo_combo.addItem(lbl, val)
        self.algo_combo.currentIndexChanged.connect(self._on_algo_changed)
        root.addWidget(self.algo_combo)
        self.algo_desc = QLabel()
        self.algo_desc.setWordWrap(True)
        self.algo_desc.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        root.addWidget(self.algo_desc)

        # Stacked param panels — order matches _ALGO_STACK indices.
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_isofuel_page())  # 0
        self.stack.addWidget(self._build_genetic_page())  # 1
        self.stack.addWidget(self._build_gcr_slider_page())  # 2
        self.stack.addWidget(self._build_dijkstra_page())  # 3
        self.stack.addWidget(self._build_genetic_shortest_page())  # 4
        self.stack.addWidget(self._build_speedy_page())  # 5
        root.addWidget(self.stack)

        root.addStretch()

    # Per-algorithm panels

    def _build_isofuel_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        req = QGroupBox("Required parameters")
        form = QFormLayout(req)
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(8)
        self.iso_n_routes = ispin(val=1, mn=1)
        form.addRow(opt_label("Number of routes", "ISOCHRONE_NUMBER_OF_ROUTES"), self.iso_n_routes)
        v.addWidget(req)

        btn, box = collapsible("Advanced parameters")
        adv = QFormLayout(box)
        adv.setLabelAlignment(Qt.AlignRight)
        adv.setSpacing(8)
        self.iso_min_crit = _combo(MINIMISATION_OPTIONS)
        self.iso_max_steps = ispin(val=100)
        self.iso_prune_groups = _combo(PRUNE_GROUP_OPTIONS)
        self.iso_prune_half = ispin(val=91, mn=1, mx=180)
        self.iso_prune_segs = ispin(val=20, mn=1)
        self.iso_prune_sym = _combo(SYMMETRY_AXIS_OPTIONS)
        adv.addRow(
            opt_label("Minimisation criterion", "ISOCHRONE_MINIMISATION_CRITERION"),
            self.iso_min_crit,
        )
        adv.addRow(
            opt_label("Max routing steps", "ISOCHRONE_MAX_ROUTING_STEPS"), self.iso_max_steps
        )
        adv.addRow(opt_label("Prune groups", "ISOCHRONE_PRUNE_GROUPS"), self.iso_prune_groups)
        adv.addRow(
            opt_label("Prune sector half (°)", "ISOCHRONE_PRUNE_SECTOR_DEG_HALF"),
            self.iso_prune_half,
        )
        adv.addRow(opt_label("Prune segments", "ISOCHRONE_PRUNE_SEGMENTS"), self.iso_prune_segs)
        adv.addRow(
            opt_label("Prune symmetry axis", "ISOCHRONE_PRUNE_SYMMETRY_AXIS"), self.iso_prune_sym
        )
        v.addWidget(btn)
        v.addWidget(box)
        v.addStretch()
        return w

    def _build_genetic_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        # Intent selector —
        # 1. Waypoints-only
        # 2. Speed & waypoints
        # 3. Speed-only — not yet implemented.

        v.addWidget(field_label("Optimization Options"))
        self.gen_intent = QComboBox()
        for val, lbl in GENETIC_INTENT_OPTIONS:
            self.gen_intent.addItem(lbl, val)
        # "Speed only" is not yet implemented — show but disable it.
        speed_idx = self.gen_intent.findData("speed")
        if speed_idx >= 0:
            self.gen_intent.model().item(speed_idx).setEnabled(False)
        self.gen_intent.currentIndexChanged.connect(self._refresh_genetic_visibility)
        v.addWidget(self.gen_intent)
        self.gen_intent_desc = QLabel()
        self.gen_intent_desc.setWordWrap(True)
        self.gen_intent_desc.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        v.addWidget(self.gen_intent_desc)

        # Required parameters
        req = QGroupBox("Required parameters")
        req_form = QFormLayout(req)
        req_form.setLabelAlignment(Qt.AlignRight)
        req_form.setSpacing(8)
        self.gen_generations = ispin(val=20, mn=1)
        req_form.addRow(
            opt_label("Generations", "GENETIC_NUMBER_GENERATIONS"), self.gen_generations
        )
        v.addWidget(req)

        # Objective weights (contextual)
        self.gen_obj_box = QGroupBox("Objective weights")
        obj_form = QFormLayout(self.gen_obj_box)
        obj_form.setLabelAlignment(Qt.AlignRight)
        obj_form.setSpacing(8)
        self.gen_obj_fuel = dspin(val=1.5, mn=0, mx=100, dec=2)
        self.gen_obj_arrival = dspin(val=1.5, mn=0, mx=100, dec=2)
        self.gen_obj_fuel_lbl = opt_label("Fuel consumption weight")
        self.gen_obj_arrival_lbl = opt_label("Arrival-time weight")
        obj_form.addRow(self.gen_obj_fuel_lbl, self.gen_obj_fuel)
        obj_form.addRow(self.gen_obj_arrival_lbl, self.gen_obj_arrival)
        v.addWidget(self.gen_obj_box)

        # Schedule (waypoints-only mode)
        self.gen_sched_box = QGroupBox("Fix the schedule")
        sched_v = QVBoxLayout(self.gen_sched_box)
        sched_v.setSpacing(8)
        sched_hint = QLabel(
            "In waypoints-only mode the schedule is fixed either by a constant "
            "boat speed or by a target arrival time (the other value is left unset)."
        )
        sched_hint.setWordWrap(True)
        sched_hint.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        sched_v.addWidget(sched_hint)
        sched_form = QFormLayout()
        sched_form.setLabelAlignment(Qt.AlignRight)
        sched_form.setSpacing(8)
        self.gen_sched = QComboBox()
        self.gen_sched.addItem("Via speed", "via_speed")
        self.gen_sched.addItem("Via arrival time", "via_arrival")
        self.gen_sched.currentIndexChanged.connect(self._refresh_genetic_visibility)
        sched_form.addRow(opt_label("Fix via"), self.gen_sched)
        self.gen_sched_speed = dspin(val=6.17, suffix="m/s", mx=60, dec=3)
        self.gen_sched_speed_lbl = opt_label("Boat speed", "BOAT_SPEED")
        self.gen_sched_arrival = QDateTimeEdit()
        self.gen_sched_arrival.setDisplayFormat("dd/MM/yyyy - hh:mm AP")
        self.gen_sched_arrival.setCalendarPopup(True)
        self.gen_sched_arrival_lbl = opt_label("Arrival time", "ARRIVAL_TIME")
        sched_form.addRow(self.gen_sched_speed_lbl, self.gen_sched_speed)
        sched_form.addRow(self.gen_sched_arrival_lbl, self.gen_sched_arrival)
        sched_v.addLayout(sched_form)
        v.addWidget(self.gen_sched_box)

        # Speed + waypoints: both speed AND arrival time required.
        self.gen_sw_box = QGroupBox("Speed & arrival time")
        sw_form = QFormLayout(self.gen_sw_box)
        sw_form.setLabelAlignment(Qt.AlignRight)
        sw_form.setSpacing(8)
        self.gen_sw_speed = dspin(val=6.17, suffix="m/s", mx=60, dec=3)
        self.gen_sw_arrival = QDateTimeEdit()
        self.gen_sw_arrival.setDisplayFormat("dd/MM/yyyy - hh:mm AP")
        self.gen_sw_arrival.setCalendarPopup(True)
        sw_form.addRow(opt_label("Boat speed", "BOAT_SPEED"), self.gen_sw_speed)
        sw_form.addRow(opt_label("Arrival time", "ARRIVAL_TIME"), self.gen_sw_arrival)
        v.addWidget(self.gen_sw_box)

        # Speed only: just speed.
        self.gen_s_box = QGroupBox("Speed")
        s_form = QFormLayout(self.gen_s_box)
        s_form.setLabelAlignment(Qt.AlignRight)
        s_form.setSpacing(8)
        self.gen_s_speed = dspin(val=6.17, suffix="m/s", mx=60, dec=3)
        s_form.addRow(opt_label("Boat speed", "BOAT_SPEED"), self.gen_s_speed)
        v.addWidget(self.gen_s_box)

        # Advanced parameters
        btn, box = collapsible("Advanced parameters")
        adv = QFormLayout(box)
        adv.setLabelAlignment(Qt.AlignRight)
        adv.setSpacing(8)
        self.gen_offsprings = ispin(val=2, mn=1)
        self.gen_pop_size = ispin(val=20, mn=2)
        self.gen_mutation = QComboBox()  # populated per-intent in _refresh_genetic_visibility
        self.gen_pop_type = _combo(GENETIC_POPULATION_OPTIONS)
        self.gen_pop_type.currentIndexChanged.connect(self._refresh_genetic_visibility)
        self.gen_pop_path = QLineEdit()
        self.gen_pop_path.setPlaceholderText("GeoJSON path (only for from_geojson)")
        gen_pop_browse = QPushButton("Browse…")
        gen_pop_browse.clicked.connect(
            lambda: self._browse(self.gen_pop_path, "GeoJSON (*.geojson *.json)")
        )
        self.gen_pop_path_row = QWidget()
        pop_path_row = QHBoxLayout(self.gen_pop_path_row)
        pop_path_row.setContentsMargins(0, 0, 0, 0)
        pop_path_row.addWidget(self.gen_pop_path)
        pop_path_row.addWidget(gen_pop_browse)
        self.gen_pop_path_lbl = opt_label("Population path (GeoJSON)", "GENETIC_POPULATION_PATH")
        self.gen_repair = _combo(GENETIC_REPAIR_OPTIONS)
        self.gen_crossover_patcher = _combo(GENETIC_CROSSOVER_PATCHER_OPTIONS)
        self.gen_fix_seed = QCheckBox("Fix random seed (GENETIC_FIX_RANDOM_SEED)")
        adv.addRow(opt_label("Offsprings", "GENETIC_NUMBER_OFFSPRINGS"), self.gen_offsprings)
        adv.addRow(opt_label("Population size", "GENETIC_POPULATION_SIZE"), self.gen_pop_size)
        adv.addRow(opt_label("Mutation type", "GENETIC_MUTATION_TYPE"), self.gen_mutation)
        adv.addRow(opt_label("Population type", "GENETIC_POPULATION_TYPE"), self.gen_pop_type)
        adv.addRow(self.gen_pop_path_lbl, self.gen_pop_path_row)
        adv.addRow(opt_label("Repair strategy", "GENETIC_REPAIR_TYPE"), self.gen_repair)
        adv.addRow(
            opt_label("Crossover patcher", "GENETIC_CROSSOVER_PATCHER"), self.gen_crossover_patcher
        )
        adv.addRow(self.gen_fix_seed)
        v.addWidget(btn)
        v.addWidget(box)
        v.addStretch()
        return w

    def _build_gcr_slider_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        btn, box = collapsible("Advanced parameters")
        adv = QFormLayout(box)
        adv.setLabelAlignment(Qt.AlignRight)
        adv.setSpacing(8)
        self.gcr_angle_step = dspin(val=30, dec=1, suffix="°")
        self.gcr_distance_move = dspin(val=10000, dec=0, suffix="m")
        self.gcr_dynamic_params = QCheckBox("Dynamic parameters (GCR_SLIDER_DYNAMIC_PARAMETERS)")
        self.gcr_dynamic_params.setChecked(True)
        self.gcr_land_buffer = dspin(val=1000, dec=0, suffix="m")
        self.gcr_interpolate = QCheckBox("Interpolate (GCR_SLIDER_INTERPOLATE)")
        self.gcr_interpolate.setChecked(True)
        self.gcr_interp_dist = dspin(val=0.1, dec=3)
        self.gcr_interp_normalized = QCheckBox(
            "Normalized interpolation (GCR_SLIDER_INTERP_NORMALIZED)"
        )
        self.gcr_interp_normalized.setChecked(True)
        self.gcr_max_points = ispin(val=300, mn=1)
        self.gcr_threshold = dspin(val=10000, dec=0, suffix="m")
        adv.addRow(opt_label("Angle step", "GCR_SLIDER_ANGLE_STEP"), self.gcr_angle_step)
        adv.addRow(opt_label("Distance move", "GCR_SLIDER_DISTANCE_MOVE"), self.gcr_distance_move)
        adv.addRow(self.gcr_dynamic_params)
        adv.addRow(opt_label("Land buffer", "GCR_SLIDER_LAND_BUFFER"), self.gcr_land_buffer)
        adv.addRow(self.gcr_interpolate)
        adv.addRow(
            opt_label("Interpolation distance", "GCR_SLIDER_INTERP_DIST"), self.gcr_interp_dist
        )
        adv.addRow(self.gcr_interp_normalized)
        adv.addRow(opt_label("Max points", "GCR_SLIDER_MAX_POINTS"), self.gcr_max_points)
        adv.addRow(opt_label("Threshold", "GCR_SLIDER_THRESHOLD"), self.gcr_threshold)
        v.addWidget(btn)
        v.addWidget(box)
        v.addStretch()
        return w

    def _build_dijkstra_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        btn, box = collapsible("Advanced parameters")
        adv = QFormLayout(box)
        adv.setLabelAlignment(Qt.AlignRight)
        adv.setSpacing(8)
        self.dijk_neighbors = ispin(val=1, mn=1)
        self.dijk_step = ispin(val=1, mn=1)
        self.dijk_mask = QLineEdit()
        self.dijk_mask.setPlaceholderText("Auto (uses installed package path)")
        mask_browse = QPushButton("Browse…")
        mask_browse.clicked.connect(lambda: self._browse(self.dijk_mask, "NumPy (*.npz)"))
        mask_row = QHBoxLayout()
        mask_row.addWidget(self.dijk_mask)
        mask_row.addWidget(mask_browse)
        adv.addRow(opt_label("Num. neighbors", "DIJKSTRA_NOF_NEIGHBORS"), self.dijk_neighbors)
        adv.addRow(opt_label("Route save step", "DIJKSTRA_STEP"), self.dijk_step)
        adv.addRow(opt_label("Land mask file", "DIJKSTRA_MASK_FILE"), mask_row)
        v.addWidget(btn)
        v.addWidget(box)
        v.addStretch()
        return w

    def _build_genetic_shortest_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        note = QLabel("Note: Experimental algorithm, not fully implemented.")
        note.setTextFormat(Qt.RichText)
        note.setWordWrap(True)
        note.setStyleSheet(f"font-size: 12px; padding: 12px; color: {COLOR_MUTED};")
        v.addWidget(note)
        v.addStretch()
        return w

    def _build_speedy_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        note = QLabel("⚠  Speedy isobased is for testing only. No additional parameters.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {COLOR_WARNING}; font-size: 12px; padding: 12px;")
        v.addWidget(note)
        v.addStretch()
        return w

    # Helpers

    def _on_algo_changed(self, _idx):
        algo = self.algo_combo.currentData() or "isofuel"
        self.algo_desc.setText(_ALGO_DESCRIPTIONS.get(algo, ""))
        self.stack.setCurrentIndex(_ALGO_STACK.get(algo, 0))
        self._update_status()

    def _current_algo(self):
        return self.algo_combo.currentData() or "isofuel"

    def _update_status(self):
        if self.status is None:
            return  # still being constructed
        algo = self._current_algo()
        label = _ALGO_LABELS.get(algo, algo)
        self.status.set_ok(f"Algorithm configured — {label}")

    def _set_mutation_options(self, options):
        current = self.gen_mutation.currentData()
        self.gen_mutation.blockSignals(True)
        self.gen_mutation.clear()
        for val, lbl in options:
            self.gen_mutation.addItem(lbl, val)
        idx = self.gen_mutation.findData(current)
        self.gen_mutation.setCurrentIndex(idx if idx >= 0 else 0)
        self.gen_mutation.blockSignals(False)

    def _refresh_genetic_visibility(self, *_):
        intent = self.gen_intent.currentData() or "speed_waypoints"
        self.gen_intent_desc.setText(_INTENT_DESCRIPTIONS.get(intent, ""))

        # Objectives — show only the keys valid for the intent.
        show_fuel = intent in ("waypoints", "speed_waypoints")
        show_arrival = intent in ("speed_waypoints", "speed")
        self.gen_obj_fuel.setVisible(show_fuel)
        self.gen_obj_fuel_lbl.setVisible(show_fuel)
        self.gen_obj_arrival.setVisible(show_arrival)
        self.gen_obj_arrival_lbl.setVisible(show_arrival)

        # Per-intent schedule / speed sections.
        is_waypoints = intent == "waypoints"
        is_sw = intent == "speed_waypoints"
        is_speed = intent == "speed"
        self.gen_sched_box.setVisible(is_waypoints)
        via = self.gen_sched.currentData()
        self.gen_sched_speed.setVisible(is_waypoints and via == "via_speed")
        self.gen_sched_speed_lbl.setVisible(is_waypoints and via == "via_speed")
        self.gen_sched_arrival.setVisible(is_waypoints and via == "via_arrival")
        self.gen_sched_arrival_lbl.setVisible(is_waypoints and via == "via_arrival")
        self.gen_sw_box.setVisible(is_sw)
        self.gen_s_box.setVisible(is_speed)

        # Mutation options restricted to the intent's valid subset.
        if intent == "waypoints":
            self._set_mutation_options(GENETIC_MUTATION_WAYPOINT_OPTIONS)
        elif intent == "speed":
            self._set_mutation_options(GENETIC_MUTATION_SPEED_OPTIONS)
        else:
            self._set_mutation_options(GENETIC_MUTATION_OPTIONS)

        # Population path is only meaningful for the from_geojson population type.
        from_geojson = self.gen_pop_type.currentData() == "from_geojson"
        self.gen_pop_path_lbl.setVisible(from_geojson)
        self.gen_pop_path_row.setVisible(from_geojson)

        self._update_status()

    def _browse(self, line_edit, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, "Select file", line_edit.text(), file_filter)
        if path:
            line_edit.setText(path)

    def _find_combo_idx(self, combo, data_val):
        idx = combo.findData(data_val)
        return idx if idx >= 0 else 0

    # Config persistence
    def save_to_config(self):
        c = self.config
        c["ALGORITHM_TYPE"] = self.algo_combo.currentData()
        # Isofuel
        c["ISOCHRONE_NUMBER_OF_ROUTES"] = self.iso_n_routes.value()
        c["ISOCHRONE_MINIMISATION_CRITERION"] = self.iso_min_crit.currentData()
        c["ISOCHRONE_MAX_ROUTING_STEPS"] = self.iso_max_steps.value()
        c["ISOCHRONE_PRUNE_GROUPS"] = self.iso_prune_groups.currentData()
        c["ISOCHRONE_PRUNE_SECTOR_DEG_HALF"] = self.iso_prune_half.value()
        c["ISOCHRONE_PRUNE_SEGMENTS"] = self.iso_prune_segs.value()
        c["ISOCHRONE_PRUNE_SYMMETRY_AXIS"] = self.iso_prune_sym.currentData()
        # Genetic — derive forced params from the optimisation intent.
        intent = self.gen_intent.currentData() or "speed_waypoints"
        c["_GENETIC_INTENT"] = intent
        c["GENETIC_NUMBER_GENERATIONS"] = self.gen_generations.value()
        c["GENETIC_CROSSOVER_TYPE"] = GENETIC_INTENT_CROSSOVER.get(intent, "random")
        c["GENETIC_MUTATION_TYPE"] = self.gen_mutation.currentData()
        obj = {}
        if intent in ("waypoints", "speed_waypoints"):
            obj["fuel_consumption"] = self.gen_obj_fuel.value()
        if intent in ("speed_waypoints", "speed"):
            obj["arrival_time"] = self.gen_obj_arrival.value()
        c["GENETIC_OBJECTIVES"] = obj
        # Speed / arrival time per intent — all set here; Boat page never touches these for genetic.
        if intent == "waypoints":
            sched = self.gen_sched.currentData() or "via_speed"
            c["_GENETIC_SCHEDULE"] = sched
            if sched == "via_speed":
                c["BOAT_SPEED"] = self.gen_sched_speed.value()
                c["ARRIVAL_TIME"] = ""
            else:
                c["ARRIVAL_TIME"] = (
                    self.gen_sched_arrival.dateTime().toUTC().toString("yyyy-MM-ddTHH:mm") + "Z"
                )
        elif intent == "speed_waypoints":
            c["_GENETIC_SCHEDULE"] = "via_speed"
            c["BOAT_SPEED"] = self.gen_sw_speed.value()
            c["ARRIVAL_TIME"] = (
                self.gen_sw_arrival.dateTime().toUTC().toString("yyyy-MM-ddTHH:mm") + "Z"
            )
        else:  # speed
            c["_GENETIC_SCHEDULE"] = "via_speed"
            c["BOAT_SPEED"] = self.gen_s_speed.value()
            c["ARRIVAL_TIME"] = ""
        c["GENETIC_NUMBER_OFFSPRINGS"] = self.gen_offsprings.value()
        c["GENETIC_POPULATION_SIZE"] = self.gen_pop_size.value()
        c["GENETIC_POPULATION_TYPE"] = self.gen_pop_type.currentData()
        c["GENETIC_POPULATION_PATH"] = self.gen_pop_path.text()
        c["GENETIC_REPAIR_TYPE"] = self.gen_repair.currentData()
        c["GENETIC_CROSSOVER_PATCHER"] = self.gen_crossover_patcher.currentData()
        c["GENETIC_FIX_RANDOM_SEED"] = self.gen_fix_seed.isChecked()
        # GCR Slider
        c["GCR_SLIDER_ANGLE_STEP"] = self.gcr_angle_step.value()
        c["GCR_SLIDER_DISTANCE_MOVE"] = self.gcr_distance_move.value()
        c["GCR_SLIDER_DYNAMIC_PARAMETERS"] = self.gcr_dynamic_params.isChecked()
        c["GCR_SLIDER_LAND_BUFFER"] = self.gcr_land_buffer.value()
        c["GCR_SLIDER_INTERPOLATE"] = self.gcr_interpolate.isChecked()
        c["GCR_SLIDER_INTERP_DIST"] = self.gcr_interp_dist.value()
        c["GCR_SLIDER_INTERP_NORMALIZED"] = self.gcr_interp_normalized.isChecked()
        c["GCR_SLIDER_MAX_POINTS"] = self.gcr_max_points.value()
        c["GCR_SLIDER_THRESHOLD"] = self.gcr_threshold.value()
        # Dijkstra
        c["DIJKSTRA_NOF_NEIGHBORS"] = self.dijk_neighbors.value()
        c["DIJKSTRA_STEP"] = self.dijk_step.value()
        c["DIJKSTRA_MASK_FILE"] = self.dijk_mask.text()

    def initializePage(self):
        c = self.config
        # Restore algorithm picker first so _current_algo() is consistent.
        algo = c.get("ALGORITHM_TYPE", "isofuel")
        idx = self.algo_combo.findData(algo)
        self.algo_combo.blockSignals(True)
        self.algo_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.algo_combo.blockSignals(False)
        self._on_algo_changed(self.algo_combo.currentIndex())
        # Isofuel
        self.iso_n_routes.setValue(int(c.get("ISOCHRONE_NUMBER_OF_ROUTES") or 1))
        self.iso_min_crit.setCurrentIndex(
            self._find_combo_idx(
                self.iso_min_crit,
                c.get("ISOCHRONE_MINIMISATION_CRITERION", "squareddist_over_disttodest"),
            )
        )
        self.iso_max_steps.setValue(int(c.get("ISOCHRONE_MAX_ROUTING_STEPS") or 100))
        self.iso_prune_groups.setCurrentIndex(
            self._find_combo_idx(
                self.iso_prune_groups, c.get("ISOCHRONE_PRUNE_GROUPS", "larger_direction")
            )
        )
        self.iso_prune_half.setValue(int(c.get("ISOCHRONE_PRUNE_SECTOR_DEG_HALF") or 91))
        self.iso_prune_segs.setValue(int(c.get("ISOCHRONE_PRUNE_SEGMENTS") or 20))
        self.iso_prune_sym.setCurrentIndex(
            self._find_combo_idx(self.iso_prune_sym, c.get("ISOCHRONE_PRUNE_SYMMETRY_AXIS", "gcr"))
        )
        # Genetic — restore the optimisation intent (infer for legacy configs).
        intent = c.get("_GENETIC_INTENT")
        if not intent:
            cross = c.get("GENETIC_CROSSOVER_TYPE", "random")
            intent = {"waypoints": "waypoints", "speed": "speed"}.get(cross, "speed_waypoints")
        self.gen_intent.blockSignals(True)
        self.gen_intent.setCurrentIndex(self._find_combo_idx(self.gen_intent, intent))
        self.gen_intent.blockSignals(False)
        sched = c.get("_GENETIC_SCHEDULE", "via_speed")
        self.gen_sched.blockSignals(True)
        self.gen_sched.setCurrentIndex(self._find_combo_idx(self.gen_sched, sched))
        self.gen_sched.blockSignals(False)
        self.gen_generations.setValue(int(c.get("GENETIC_NUMBER_GENERATIONS") or 20))
        obj = c.get("GENETIC_OBJECTIVES") or {}
        self.gen_obj_fuel.setValue(float(obj.get("fuel_consumption", 1.5)))
        self.gen_obj_arrival.setValue(float(obj.get("arrival_time", 1.5)))
        raw_speed = float(c.get("BOAT_SPEED") or 6.17)
        self.gen_sched_speed.setValue(raw_speed)
        self.gen_sw_speed.setValue(raw_speed)
        self.gen_s_speed.setValue(raw_speed)
        arr_str = c.get("ARRIVAL_TIME", "")
        if arr_str:
            arr_dt = QDateTime.fromString(arr_str, "yyyy-MM-ddTHH:mmZ")
            if arr_dt.isValid():
                arr_dt.setTimeSpec(Qt.UTC)
                local_dt = arr_dt.toLocalTime()
                self.gen_sched_arrival.setDateTime(local_dt)
                self.gen_sw_arrival.setDateTime(local_dt)
            else:
                self.gen_sw_arrival.setDateTime(QDateTime.currentDateTime())
        else:
            self.gen_sched_arrival.setDateTime(QDateTime.currentDateTime())
            self.gen_sw_arrival.setDateTime(QDateTime.currentDateTime())
        self.gen_offsprings.setValue(int(c.get("GENETIC_NUMBER_OFFSPRINGS") or 2))
        self.gen_pop_size.setValue(int(c.get("GENETIC_POPULATION_SIZE") or 20))
        self.gen_pop_type.blockSignals(True)
        self.gen_pop_type.setCurrentIndex(
            self._find_combo_idx(self.gen_pop_type, c.get("GENETIC_POPULATION_TYPE", "isofuel"))
        )
        self.gen_pop_type.blockSignals(False)
        self.gen_pop_path.setText(c.get("GENETIC_POPULATION_PATH", ""))
        self.gen_repair.setCurrentIndex(
            self._find_combo_idx(self.gen_repair, c.get("GENETIC_REPAIR_TYPE", "waypoints_infill"))
        )
        self.gen_crossover_patcher.setCurrentIndex(
            self._find_combo_idx(
                self.gen_crossover_patcher, c.get("GENETIC_CROSSOVER_PATCHER", "isofuel")
            )
        )
        self.gen_fix_seed.setChecked(bool(c.get("GENETIC_FIX_RANDOM_SEED", False)))
        # Populate the mutation combo for the intent, then restore the saved value.
        self._refresh_genetic_visibility()
        self.gen_mutation.setCurrentIndex(
            self._find_combo_idx(self.gen_mutation, c.get("GENETIC_MUTATION_TYPE", "random"))
        )
        # GCR Slider
        self.gcr_angle_step.setValue(float(c.get("GCR_SLIDER_ANGLE_STEP") or 30))
        self.gcr_distance_move.setValue(float(c.get("GCR_SLIDER_DISTANCE_MOVE") or 10000))
        self.gcr_dynamic_params.setChecked(bool(c.get("GCR_SLIDER_DYNAMIC_PARAMETERS", True)))
        self.gcr_land_buffer.setValue(float(c.get("GCR_SLIDER_LAND_BUFFER") or 1000))
        self.gcr_interpolate.setChecked(bool(c.get("GCR_SLIDER_INTERPOLATE", True)))
        self.gcr_interp_dist.setValue(float(c.get("GCR_SLIDER_INTERP_DIST") or 0.1))
        self.gcr_interp_normalized.setChecked(bool(c.get("GCR_SLIDER_INTERP_NORMALIZED", True)))
        self.gcr_max_points.setValue(int(c.get("GCR_SLIDER_MAX_POINTS") or 300))
        self.gcr_threshold.setValue(float(c.get("GCR_SLIDER_THRESHOLD") or 10000))
        # Dijkstra
        self.dijk_neighbors.setValue(int(c.get("DIJKSTRA_NOF_NEIGHBORS") or 1))
        self.dijk_step.setValue(int(c.get("DIJKSTRA_STEP") or 1))
        self.dijk_mask.setText(c.get("DIJKSTRA_MASK_FILE", ""))
        self._update_status()
