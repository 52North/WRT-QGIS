"""Page 6 — Review & export: JSON preview and save-to-file."""

import json
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWizardPage,
)

from ..core.defaults import DEFAULT_ALGORITHM, INTERNAL_KEYS
from ..ui.ui_kit import StatusLine, join_terms, page_header

# Exported json is grouped by page.

# Page 1 — route definition (keys from WRT config.py).
_ROUTE_KEYS = (
    "DEFAULT_ROUTE",
    "DEFAULT_MAP",
    "DEPARTURE_TIME",
    "ARRIVAL_TIME",
    "INTERMEDIATE_WAYPOINTS",
    "ROUTE_PATH",
    "ROUTE_POSTPROCESSING",
    "ROUTING_STEPS",
)

# Page 2 — algorithm. Extra keys only meaningful for a specific algorithm.
_ALGO_KEYS = {
    "dijkstra": (
        "DIJKSTRA_NOF_NEIGHBORS",
        "DIJKSTRA_STEP",
        "DIJKSTRA_MASK_FILE",
    ),
    "gcr_slider": (
        "GCR_SLIDER_ANGLE_STEP",
        "GCR_SLIDER_DISTANCE_MOVE",
        "GCR_SLIDER_DYNAMIC_PARAMETERS",
        "GCR_SLIDER_LAND_BUFFER",
        "GCR_SLIDER_INTERPOLATE",
        "GCR_SLIDER_INTERP_DIST",
        "GCR_SLIDER_INTERP_NORMALIZED",
        "GCR_SLIDER_MAX_POINTS",
        "GCR_SLIDER_THRESHOLD",
    ),
    "genetic": (
        "GENETIC_POPULATION_TYPE",
        "GENETIC_POPULATION_PATH",
        "GENETIC_POPULATION_SIZE",
        "GENETIC_NUMBER_GENERATIONS",
        "GENETIC_NUMBER_OFFSPRINGS",
        "GENETIC_MUTATION_TYPE",
        "GENETIC_CROSSOVER_TYPE",
        "GENETIC_CROSSOVER_PATCHER",
        "GENETIC_REPAIR_TYPE",
        "GENETIC_OBJECTIVES",
        "GENETIC_FIX_RANDOM_SEED",
    ),
    "isofuel": (
        "ISOCHRONE_MAX_ROUTING_STEPS",
        "ISOCHRONE_NUMBER_OF_ROUTES",
        "ISOCHRONE_MINIMISATION_CRITERION",
        "ISOCHRONE_PRUNE_GROUPS",
        "ISOCHRONE_PRUNE_SECTOR_DEG_HALF",
        "ISOCHRONE_PRUNE_SEGMENTS",
        "ISOCHRONE_PRUNE_SYMMETRY_AXIS",
        "DELTA_FUEL",
        "ROUTER_HDGS_INCREMENTS_DEG",
        "ROUTER_HDGS_SEGMENTS",
    ),
}
_ALGO_KEYS["genetic_shortest_route"] = _ALGO_KEYS["genetic"]
_ALGO_KEYS["speedy_isobased"] = _ALGO_KEYS["isofuel"]

# Page 3 — boat.
_BOAT_KEYS = (
    "BOAT_TYPE",
    "BOAT_SPEED",
    "BOAT_SPEED_BOUNDARIES",
    # Mandatory in ShipConfig — page 3 marks these required.
    "BOAT_LENGTH",
    "BOAT_BREADTH",
    "BOAT_HBR",
    "BOAT_SMCR_POWER",
    "BOAT_SMCR_SPEED",
    "BOAT_FUEL_RATE",
    # Optional hull / propulsion parameters.
    "BOAT_DRAUGHT_AFT",
    "BOAT_DRAUGHT_FORE",
    "BOAT_UNDER_KEEL_CLEARANCE",
    "BOAT_ROUGHNESS_LEVEL",
    "BOAT_ROUGHNESS_DISTRIBUTION_LEVEL",
    "BOAT_OVERLOAD_FACTOR",
    "BOAT_PROPULSION_EFFICIENCY",
    "BOAT_FACTOR_CALM_WATER",
    "BOAT_FACTOR_WAVE_FORCES",
    "BOAT_FACTOR_WIND_FORCES",
    # Wind-resistance geometry.
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
    "AIR_MASS_DENSITY",
)

# Page 4 — datasets and forecast window.
_DATASET_KEYS = (
    "WEATHER_DATA",
    "DEPTH_DATA",
    "COURSES_FILE",
    "TIME_FORECAST",
    "DELTA_TIME_FORECAST",
)

# Page 5 — constraints.
_CONSTRAINT_KEYS = ("CONSTRAINTS_LIST",)

# These algorithms have no weather/depth data pipeline.
_NO_WEATHER_ALGOS = frozenset({"dijkstra", "gcr_slider"})


def _export_sections(algo):
    """Ordered key groups for the export, in wizard-page order."""
    return (
        _ROUTE_KEYS,
        ("ALGORITHM_TYPE",) + _ALGO_KEYS.get(algo, ()),
        _BOAT_KEYS,
        _DATASET_KEYS,
        _CONSTRAINT_KEYS,
    )


def _dump_grouped(export, algo):
    """Serialise the export with a blank line between sections."""
    blocks = []
    for keys in _export_sections(algo):
        lines = [f"  {json.dumps(key)}: {json.dumps(export[key])}" for key in keys if key in export]
        if lines:
            blocks.append(",\n".join(lines))
    if not blocks:
        return "{}"
    return "{\n" + ",\n\n".join(blocks) + "\n}"


def _build_export(config):
    """Build the WRT-compatible config dict, containing only keys known to WRT.

    Keys come from both of WRT's models: Config (routing) and ShipConfig (boat), and
    are inserted in the order given by _export_sections().
    """
    algo = config.get("ALGORITHM_TYPE", DEFAULT_ALGORITHM)

    drop = set(INTERNAL_KEYS)
    # dijkstra/gcr_slider have no weather/depth pipeline.
    if algo in _NO_WEATHER_ALGOS:
        drop |= {"WEATHER_DATA", "DEPTH_DATA", "DELTA_TIME_FORECAST", "TIME_FORECAST"}
    if algo == "genetic":
        # Genetic waypoints-only: exactly one of BOAT_SPEED/ARRIVAL_TIME is used.
        if config.get("_GENETIC_INTENT") == "waypoints":
            if config.get("_GENETIC_SCHEDULE") == "via_arrival":
                drop.add("BOAT_SPEED")
            else:
                drop.add("ARRIVAL_TIME")
    else:
        # Non-genetic algorithms
        drop |= {"ARRIVAL_TIME", "BOAT_SPEED_BOUNDARIES"}

    derived = {}
    route_path = config.get("ROUTE_PATH")
    if route_path:
        # Only the CBT boat panel asks for a courses file; every other type gets one derived.
        if not config.get("COURSES_FILE"):
            derived["COURSES_FILE"] = os.path.join(route_path, "courses_route.nc")
        # Bathymetry is optional in the wizard.
        if not config.get("DEPTH_DATA") and algo not in _NO_WEATHER_ALGOS:
            derived["DEPTH_DATA"] = os.path.join(route_path, "depth_data.nc")
    if derived:
        config = {**config, **derived}

    out = {}
    for keys in _export_sections(algo):
        for key in keys:
            if key in drop:
                continue
            val = config.get(key)
            if val is None or val == "" or val == []:
                continue
            # config.py expects DEFAULT_ROUTE / DEFAULT_MAP as a list of 4 floats.
            if key in ("DEFAULT_ROUTE", "DEFAULT_MAP") and isinstance(val, str):
                try:
                    val = [float(x.strip()) for x in val.split(",")]
                except (ValueError, AttributeError):
                    continue
            # config.py expects GENETIC_REPAIR_TYPE as List[str], not a bare string.
            if key == "GENETIC_REPAIR_TYPE" and isinstance(val, str):
                val = [val]
            # Compact whole-number floats to int for cleaner JSON.
            if isinstance(val, float) and val == int(val):
                val = int(val)
            out[key] = val
    return out


class ReviewPage(QWizardPage):
    def __init__(self, config, pages, parent=None):
        super().__init__(parent)
        self.config = config
        self.pages = pages  # list of page objects with save_to_config()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 18)
        root.setSpacing(12)

        root.addWidget(
            page_header(
                "Review & export",
                "Review the generated configuration below. "
                "Copy it or save it to a JSON file to use with the WRT CLI.",
            )
        )

        # Summary labels
        self.summary_lbl = QLabel()
        self.summary_lbl.setTextFormat(Qt.RichText)
        self.summary_lbl.setWordWrap(True)
        root.addWidget(self.summary_lbl)

        # JSON preview
        json_box = QGroupBox("Generated config.json")
        json_layout = QVBoxLayout(json_box)
        self.json_edit = QTextEdit()
        self.json_edit.setReadOnly(False)
        mono = QFont("Courier New", 9)
        mono.setStyleHint(QFont.Monospace)
        self.json_edit.setFont(mono)
        self.json_edit.setMinimumHeight(280)
        json_layout.addWidget(self.json_edit)
        root.addWidget(json_box)

        # Buttons
        btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy to clipboard")
        copy_btn.clicked.connect(self._copy)
        save_btn = QPushButton("💾  Save as JSON…")
        save_btn.clicked.connect(self._save)
        save_btn.setDefault(True)
        cli_lbl = QLabel(
            '<span style="color:gray;font-size:11px;">CLI usage: '
            "<tt>python3 WeatherRoutingTool/cli.py -f /path/to/config.json</tt></span>"
        )
        cli_lbl.setTextFormat(Qt.RichText)
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)
        root.addWidget(cli_lbl)

        self.status = StatusLine()
        root.addWidget(self.status)

    STEP_NAMES = [
        "Route",
        "Algorithm",
        "Boat Details",
        "Weather & depth",
        "Constraints",
    ]

    def _update_status(self):
        assert len(self.pages) == len(self.STEP_NAMES), "page/name list mismatch"
        incomplete = [
            name
            for page, name in zip(self.pages, self.STEP_NAMES, strict=True)
            if hasattr(page, "validation_errors") and page.validation_errors()
        ]
        if incomplete:
            self.status.set_pending(
                "Some required fields are missing on: " + join_terms(incomplete)
            )
        else:
            self.status.set_ok("Configuration ready to export")

    def initializePage(self):
        # Flush all pages
        for page in self.pages:
            page.save_to_config()

        algo = self.config.get("ALGORITHM_TYPE", DEFAULT_ALGORITHM)
        export = _build_export(self.config)
        self.json_edit.setPlainText(_dump_grouped(export, algo))

        self._update_status()

        # Summary
        route = self.config.get("DEFAULT_ROUTE", "—")
        algo = self.config.get("ALGORITHM_TYPE", "—")
        weather = os.path.basename(self.config.get("WEATHER_DATA", "")) or "—"
        depth = os.path.basename(self.config.get("DEPTH_DATA", "")) or "—"
        constraints = ", ".join(self.config.get("CONSTRAINTS_LIST", [])) or "none"
        self.summary_lbl.setText(
            f"<b>Route:</b> {route}<br>"
            f"<b>Algorithm:</b> {algo}<br>"
            f"<b>Weather:</b> {weather} &nbsp; <b>Depth:</b> {depth}<br>"
            f"<b>Constraints:</b> {constraints}"
        )

    def _get_json(self):
        return self.json_edit.toPlainText()

    def _copy(self):
        from qgis.PyQt.QtWidgets import QApplication

        QApplication.clipboard().setText(self._get_json())
        QMessageBox.information(self, "Copied", "Configuration JSON copied to clipboard.")

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save WRT configuration", "config.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            # Validate JSON before writing
            json.loads(self._get_json())
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._get_json())
            QMessageBox.information(
                self,
                "Saved",
                f"Configuration saved to:\n{path}\n\n"
                f"Run with:\npython3 WeatherRoutingTool/cli.py -f {path}",
            )
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Invalid JSON", f"The JSON is invalid:\n{e}")
        except OSError as e:
            QMessageBox.critical(self, "Save failed", str(e))
