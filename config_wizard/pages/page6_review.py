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

from ..core.defaults import INTERNAL_KEYS
from ..ui.ui_kit import StatusLine, join_terms, page_header

# Keys from WRT config.py valid for all algorithms.
_UNIVERSAL_KEYS = frozenset(
    {
        "ALGORITHM_TYPE",
        "ARRIVAL_TIME",
        "BOAT_TYPE",
        "BOAT_SPEED",
        "BOAT_SPEED_BOUNDARIES",
        "CONSTRAINTS_LIST",
        "DEFAULT_MAP",
        "DEFAULT_ROUTE",
        "DELTA_FUEL",
        "DELTA_TIME_FORECAST",
        "DEPARTURE_TIME",
        "INTERMEDIATE_WAYPOINTS",
        "ROUTER_HDGS_INCREMENTS_DEG",
        "ROUTER_HDGS_SEGMENTS",
        "ROUTE_PATH",
        "ROUTE_POSTPROCESSING",
        "ROUTING_STEPS",
        "TIME_FORECAST",
        "COURSES_FILE",
        "DEPTH_DATA",
        "WEATHER_DATA",
    }
)

# Extra keys only meaningful for a specific algorithm.
_ALGO_KEYS = {
    "dijkstra": frozenset(
        {
            "DIJKSTRA_MASK_FILE",
            "DIJKSTRA_NOF_NEIGHBORS",
            "DIJKSTRA_STEP",
        }
    ),
    "gcr_slider": frozenset(
        {
            "GCR_SLIDER_ANGLE_STEP",
            "GCR_SLIDER_DISTANCE_MOVE",
            "GCR_SLIDER_DYNAMIC_PARAMETERS",
            "GCR_SLIDER_INTERPOLATE",
            "GCR_SLIDER_INTERP_DIST",
            "GCR_SLIDER_INTERP_NORMALIZED",
            "GCR_SLIDER_LAND_BUFFER",
            "GCR_SLIDER_MAX_POINTS",
            "GCR_SLIDER_THRESHOLD",
        }
    ),
    "genetic": frozenset(
        {
            "GENETIC_CROSSOVER_PATCHER",
            "GENETIC_CROSSOVER_TYPE",
            "GENETIC_FIX_RANDOM_SEED",
            "GENETIC_MUTATION_TYPE",
            "GENETIC_NUMBER_GENERATIONS",
            "GENETIC_NUMBER_OFFSPRINGS",
            "GENETIC_OBJECTIVES",
            "GENETIC_POPULATION_PATH",
            "GENETIC_POPULATION_SIZE",
            "GENETIC_POPULATION_TYPE",
            "GENETIC_REPAIR_TYPE",
        }
    ),
    "isofuel": frozenset(
        {
            "ISOCHRONE_MAX_ROUTING_STEPS",
            "ISOCHRONE_MINIMISATION_CRITERION",
            "ISOCHRONE_NUMBER_OF_ROUTES",
            "ISOCHRONE_PRUNE_GROUPS",
            "ISOCHRONE_PRUNE_SECTOR_DEG_HALF",
            "ISOCHRONE_PRUNE_SEGMENTS",
            "ISOCHRONE_PRUNE_SYMMETRY_AXIS",
        }
    ),
}
_ALGO_KEYS["genetic_shortest_route"] = _ALGO_KEYS["genetic"]
_ALGO_KEYS["speedy_isobased"] = _ALGO_KEYS["isofuel"]

# These algorithms have no weather/depth data pipeline.
_NO_WEATHER_ALGOS = frozenset({"dijkstra", "gcr_slider"})


def _build_export(config):
    """Build the WRT-compatible config dict, containing only keys known to config.py."""
    algo = config.get("ALGORITHM_TYPE", "isofuel")
    allowed = _UNIVERSAL_KEYS | _ALGO_KEYS.get(algo, frozenset())

    drop = set(INTERNAL_KEYS)
    # dijkstra/gcr_slider have no weather/depth pipeline.
    if algo in _NO_WEATHER_ALGOS:
        drop |= {"WEATHER_DATA", "DEPTH_DATA", "DELTA_TIME_FORECAST", "TIME_FORECAST"}
    # Genetic waypoints-only: exactly one of BOAT_SPEED/ARRIVAL_TIME is used.
    if algo == "genetic" and config.get("_GENETIC_INTENT") == "waypoints":
        if config.get("_GENETIC_SCHEDULE") == "via_arrival":
            drop.add("BOAT_SPEED")
        else:
            drop.add("ARRIVAL_TIME")

    out = {}
    for key in allowed:
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
            if hasattr(page, "isComplete") and not page.isComplete()
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

        export = _build_export(self.config)
        json_str = json.dumps(export, indent=2)
        self.json_edit.setPlainText(json_str)

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
