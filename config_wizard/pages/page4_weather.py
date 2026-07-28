"""Page 4 — Weather & depth datasets"""

import os
from datetime import datetime

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from ..core.netcdf_validation import InspectNetcdfTask, check_coverage
from ..ui.ui_kit import (
    COLOR_BORDER,
    COLOR_FILE_ERROR,
    COLOR_FILE_OK,
    COLOR_INPUT_BORDER,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_PRIMARY_SOFT,
    COLOR_REQUIRED,
    COLOR_SIDEBAR_BG,
    COLOR_TEXT,
    COLOR_WARNING,
    StatusLine,
    opt_label,
    page_header,
)

# Drop-zone and badge background tints per validation state.
ZONE_BG_NEUTRAL = "#f8f9fb"
ZONE_BG_OK = "#eaf3e2"
ZONE_BG_ERR = "#fbeae3"
ZONE_BG_WARN = "#fdf2e2"
BADGE_BG_OPTIONAL = "#eceef1"
BADGE_BG_REQUIRED = "#fbe7e8"


# UI helpers
class FileField(QFrame):
    """A dataset card: a prominent drag-and-drop zone over a Browse/Clear row"""

    def __init__(
        self, title, placeholder, file_filter="NetCDF (*.nc)", optional=False, parent=None
    ):
        super().__init__(parent)
        self._filter = file_filter
        self._optional = optional
        self._last = (None, "", False)  # last (state, message, warn) for repaint

        self.setObjectName("DatasetCard")
        self.setStyleSheet(
            f"QFrame#DatasetCard {{ border: 1px solid {COLOR_INPUT_BORDER}; "
            f"border-radius: 10px; background: #ffffff; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Header: folder icon + title .......... state badge
        header = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(self.style().standardIcon(QStyle.SP_DirIcon).pixmap(18, 18))
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {COLOR_TEXT};")
        self.badge = QLabel()
        self.badge.setAlignment(Qt.AlignCenter)
        header.addWidget(icon)
        header.addWidget(title_lbl)
        header.addStretch()
        header.addWidget(self.badge)
        layout.addLayout(header)

        # Drop zone — the primary, visible drag target; click anywhere to browse.
        self.zone = QFrame()
        self.zone.setObjectName("DropZone")
        self.zone.setCursor(Qt.PointingHandCursor)
        self.zone.setMinimumHeight(56)
        self.zone.mousePressEvent = lambda _e: self._browse()
        zone_lay = QVBoxLayout(self.zone)
        zone_lay.setContentsMargins(14, 10, 14, 10)
        zone_lay.setSpacing(2)

        # Primary is a short single-line prompt / filename — no wrap so it can't
        # be clipped; the labels span the full zone width and centre their text.
        self.zone_primary = QLabel()
        self.zone_primary.setAlignment(Qt.AlignCenter)
        self.zone_secondary = QLabel()
        self.zone_secondary.setWordWrap(True)
        self.zone_secondary.setAlignment(Qt.AlignCenter)

        # Indeterminate loader shown only while a file is being validated.
        self.zone_progress = QProgressBar()
        self.zone_progress.setRange(0, 0)
        self.zone_progress.setTextVisible(False)
        self.zone_progress.setFixedHeight(6)
        self.zone_progress.setMaximumWidth(180)
        self.zone_progress.setVisible(False)
        self.zone_progress.setStyleSheet(
            f"QProgressBar {{ background: {COLOR_BORDER}; border: none; "
            f"border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background: {COLOR_PRIMARY}; "
            f"border-radius: 3px; }}"
        )

        # Let clicks on the labels fall through to the zone's browse handler.
        for w in (self.zone_primary, self.zone_secondary, self.zone_progress):
            w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        zone_lay.addStretch()
        zone_lay.addWidget(self.zone_primary)
        zone_lay.addWidget(self.zone_secondary)
        zone_lay.addWidget(self.zone_progress, 0, Qt.AlignHCenter)
        zone_lay.addStretch()
        layout.addWidget(self.zone)

        # Read-only path display + Clear (browsing happens by clicking the zone).
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(placeholder)
        self.path_edit.setReadOnly(True)
        self.path_edit.setStyleSheet(f"background: {COLOR_SIDEBAR_BG}; color: {COLOR_MUTED};")
        # Let file drops fall through to the card instead of the line edit
        # inserting the raw "file://…" URL as text.
        self.path_edit.setAcceptDrops(False)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.path_edit.clear)
        self.clear_btn.setEnabled(False)
        self.path_edit.textChanged.connect(lambda t: self.clear_btn.setEnabled(bool(t)))
        path_row.addWidget(self.path_edit)
        path_row.addWidget(self.clear_btn)
        layout.addLayout(path_row)

        self.setAcceptDrops(True)
        self.set_state(None)  # render the empty state

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select file", self.path_edit.text(), self._filter
        )
        if path:
            self.path_edit.setText(path)

    # Rendering
    def _paint_zone(self, border, bg):
        self.zone.setStyleSheet(
            f"QFrame#DropZone {{ border: 2px dashed {border}; "
            f"border-radius: 12px; background: {bg}; }}"
        )

    def _set_badge(self, text, color, bg):
        self.badge.setText(text)
        self.badge.setStyleSheet(
            f"background: {bg}; color: {color}; border-radius: 9px; "
            f"padding: 2px 10px; font-size: 11px; font-weight: 600;"
        )

    def set_loading(self, name):
        """Show the pending loader while the file is inspected off-thread."""
        self._set_badge("checking", COLOR_MUTED, BADGE_BG_OPTIONAL)
        self._paint_zone(COLOR_PRIMARY, ZONE_BG_NEUTRAL)
        self.zone_primary.setText(f"Validating {name}…")
        self.zone_primary.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px; font-weight: 600;")
        self.zone_secondary.setText("")
        self.zone_secondary.setVisible(False)
        self.zone_progress.setVisible(True)

    def set_state(self, state, message="", warn=False):
        """Render a validation outcome. state: True/False/None (no path)."""
        self._last = (state, message, warn)
        self.zone_progress.setVisible(False)
        path = self.path_edit.text().strip()
        name = os.path.basename(path) if path else ""
        size = (
            f"{os.path.getsize(path) / (1024 * 1024):.0f} MB"
            if path and os.path.isfile(path)
            else ""
        )

        if state is True:
            color = COLOR_WARNING if warn else COLOR_FILE_OK
            bg = ZONE_BG_WARN if warn else ZONE_BG_OK
            self._set_badge("warning" if warn else "valid", color, bg)
            self._paint_zone(color, bg)
            self.zone_primary.setText(name)
            self.zone_primary.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 700;")
            detail = " · ".join(p for p in ("NetCDF", size, message, "drop to replace") if p)
            self.zone_secondary.setText(detail)
            self.zone_secondary.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        elif state is False:
            self._set_badge("invalid", COLOR_FILE_ERROR, ZONE_BG_ERR)
            self._paint_zone(COLOR_FILE_ERROR, ZONE_BG_ERR)
            self.zone_primary.setText(name or "Invalid file")
            self.zone_primary.setStyleSheet(
                f"color: {COLOR_FILE_ERROR}; font-size: 13px; font-weight: 700;"
            )
            self.zone_secondary.setText(message or "File could not be validated")
            self.zone_secondary.setStyleSheet(f"color: {COLOR_FILE_ERROR}; font-size: 11px;")
        else:  # no path
            if self._optional:
                self._set_badge("optional", COLOR_MUTED, BADGE_BG_OPTIONAL)
            else:
                self._set_badge("required", COLOR_REQUIRED, BADGE_BG_REQUIRED)
            self._paint_zone(COLOR_BORDER, ZONE_BG_NEUTRAL)
            self.zone_primary.setText("Click to browse or drag & drop")
            self.zone_primary.setStyleSheet(
                f"color: {COLOR_TEXT}; font-size: 13px; font-weight: 600;"
            )
            self.zone_secondary.setText("")
            self.zone_secondary.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")

        # Hide the detail line when empty so the prompt centres vertically alone.
        self.zone_secondary.setVisible(bool(self.zone_secondary.text()))

    # Drag & drop
    @staticmethod
    def _drop_path(event):
        """Return the first local file path from a drag event, or None."""
        md = event.mimeData()
        if not md.hasUrls():
            return None
        for url in md.urls():
            local = url.toLocalFile()
            if local and os.path.isfile(local):
                return local
        return None

    def dragEnterEvent(self, event):
        if self._drop_path(event):
            event.acceptProposedAction()
            self._paint_zone(COLOR_PRIMARY, COLOR_PRIMARY_SOFT)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.set_state(*self._last)  # restore the pre-drag rendering

    def dropEvent(self, event):
        path = self._drop_path(event)
        if path:
            self.path_edit.setText(path)  # fires validation → repaints the zone
            event.acceptProposedAction()
        else:
            self.set_state(*self._last)

    def text(self):
        return self.path_edit.text()

    def setText(self, t):
        self.path_edit.setText(t)


class WeatherPage(QWizardPage):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._weather_valid = None  # None=no path, False=invalid, True=valid
        self._depth_valid = None
        self._weather_loading = False
        self._depth_loading = False
        self._tasks = {}  # field -> in-flight InspectNetcdfTask
        self._info = {}  # kind -> last inspect_netcdf() result (or None)
        self._info_path = {}  # kind -> path that _info was computed for
        self.status = None
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        scroll.setWidget(inner)
        root = QVBoxLayout(inner)
        root.setContentsMargins(28, 22, 28, 18)
        root.setSpacing(14)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        root.addWidget(
            page_header(
                "Weather & depth datasets",
                "Upload weather and bathymetry NetCDF files. "
                "Files are validated against your route before you proceed.",
            )
        )

        self.weather_field = FileField("Weather data", "/path/to/weather.nc")
        self.weather_field.path_edit.textChanged.connect(self._on_weather_changed)
        root.addWidget(self.weather_field)

        self.depth_field = FileField(
            "Bathymetry data",
            "/path/to/depth.nc",
            optional=True,
        )
        self.depth_field.path_edit.textChanged.connect(self._on_depth_changed)
        root.addWidget(self.depth_field)

        time_box = QGroupBox("Forecast time parameters")
        time_form = QFormLayout(time_box)
        time_form.setLabelAlignment(Qt.AlignRight)
        time_form.setSpacing(8)

        self.delta_time = QSpinBox()
        self.delta_time.setRange(1, 24)
        self.delta_time.setValue(3)
        self.delta_time.setSuffix("  h")
        self.delta_time.setToolTip("Time resolution of weather forecast (default: 3 h)")

        self.time_forecast = QSpinBox()
        self.time_forecast.setRange(1, 720)
        self.time_forecast.setValue(90)
        self.time_forecast.setSuffix("  h")
        self.time_forecast.setToolTip("Total forecast hours (default: 90 h)")
        # Re-check time coverage when the forecast horizon changes
        self.time_forecast.valueChanged.connect(self._on_forecast_changed)

        time_form.addRow(
            opt_label("Forecast time resolution", "DELTA_TIME_FORECAST"), self.delta_time
        )
        time_form.addRow(opt_label("Forecast horizon", "TIME_FORECAST"), self.time_forecast)
        root.addWidget(time_box)

        root.addStretch()

        # Status line pinned below the scroll area so it stays visible.
        status_wrap = QWidget()
        sw = QVBoxLayout(status_wrap)
        sw.setContentsMargins(28, 0, 28, 12)
        self.status = StatusLine()
        sw.addWidget(self.status)
        outer.addWidget(status_wrap)
        self._update_status()

    # Config helpers

    def _parse_map_coords(self):
        """Return (lat_min, lon_min, lat_max, lon_max) from config, or None."""
        val = self.config.get("DEFAULT_MAP", "")
        if not val:
            return None
        if isinstance(val, (list, tuple)) and len(val) == 4:
            try:
                return tuple(float(x) for x in val)
            except (ValueError, TypeError):
                return None
        if isinstance(val, str):
            parts = [p.strip() for p in val.split(",")]
            if len(parts) == 4:
                try:
                    return tuple(float(p) for p in parts)
                except ValueError:
                    return None
        return None

    def _parse_departure_time(self):
        """Return DEPARTURE_TIME as a naive datetime, or None."""
        val = self.config.get("DEPARTURE_TIME", "")
        if not val:
            return None
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                return datetime.strptime(val, "%Y-%m-%dT%H:%MZ")
            except ValueError:
                return None
        return None

    # Validation

    def _check_coverage(self, info, require_time):
        """Gather page state and run the pure coverage check against ``info``."""
        return check_coverage(
            info,
            self._parse_map_coords(),
            self._parse_departure_time(),
            self.time_forecast.value(),
            require_time,
        )

    def _validate_weather(self, path):
        self._begin_validate(self.weather_field, "weather", path, require_time=True)

    def _validate_depth(self, path):
        self._begin_validate(self.depth_field, "depth", path, require_time=False)

    def _begin_validate(self, field, kind, path, require_time):
        """Kick off validation for a field: cheap cases inline, file I/O async."""
        # Supersede any in-flight inspection for this field.
        old = self._tasks.pop(field, None)
        if old is not None:
            old.cancel()

        if not path:
            self._forget_info(kind)
            self._set_loading(kind, False)
            self._apply_result(field, kind, None, "", False)
            return
        if not os.path.isfile(path):
            self._forget_info(kind)
            self._set_loading(kind, False)
            self._apply_result(field, kind, False, "File not found", False)
            return

        # Reuse a cached inspection for the same path (e.g. re-selecting the same
        # file) — only the cheap coverage check runs, on the UI thread.
        if self._info_path.get(kind) == path and self._info.get(kind) is not None:
            self._set_loading(kind, False)
            state, msg, warn = self._check_coverage(self._info[kind], require_time)
            self._apply_result(field, kind, state, msg, warn)
            return

        # Inspect the file off the UI thread; show the loader meanwhile.
        self._set_loading(kind, True)
        field.set_loading(os.path.basename(path))
        task = InspectNetcdfTask(path)
        task.done.connect(
            lambda info, err, t=task: self._on_inspect_done(
                field, kind, path, require_time, t, info, err
            )
        )
        self._tasks[field] = task
        mgr = QgsApplication.taskManager()
        if mgr is not None:
            mgr.addTask(task)
        else:  # no task manager (e.g. outside QGIS) — run inline as a fallback
            task.run()
            task.done.emit(task.info, task.error)

    def _on_inspect_done(self, field, kind, path, require_time, task, info, error):
        """Main-thread completion handler for an InspectNetcdfTask."""
        if self._tasks.get(field) is not task:
            return  # superseded by a newer inspection
        self._tasks.pop(field, None)
        if field.text().strip() != path:
            return  # the path changed while we were inspecting
        self._set_loading(kind, False)
        if error is not None:
            self._forget_info(kind)
            self._apply_result(field, kind, False, str(error), False)
            return
        self._info[kind] = info
        self._info_path[kind] = path
        state, msg, warn = self._check_coverage(info, require_time)
        self._apply_result(field, kind, state, msg, warn)

    def _on_forecast_changed(self):
        """Re-check time coverage on a horizon change, reusing the cached
        inspection so a spinbox tick never re-opens the file or spawns a task."""
        path = self.weather_field.text().strip()
        if not path or self._weather_loading:
            return  # nothing loaded, or an in-flight load will use the new value
        if self._info_path.get("weather") == path and self._info.get("weather"):
            state, msg, warn = self._check_coverage(self._info["weather"], True)
            self._apply_result(self.weather_field, "weather", state, msg, warn)

    def _apply_result(self, field, kind, state, message, warn):
        """Render a result on the field and refresh page-level status/completion."""
        if kind == "weather":
            self._weather_valid = state
        else:
            self._depth_valid = state
        field.set_state(state, message, warn)
        self._update_status()
        self.completeChanged.emit()

    def _set_loading(self, kind, on):
        if kind == "weather":
            self._weather_loading = on
        else:
            self._depth_loading = on
        self._update_status()
        self.completeChanged.emit()

    def _forget_info(self, kind):
        self._info[kind] = None
        self._info_path[kind] = None

    def _update_status(self):
        if self.status is None:
            return  # still being constructed
        if self._weather_loading or self._depth_loading:
            self.status.set_pending("Validating datasets…")
            return
        depth_ok = self._depth_valid is True or self._depth_valid is None
        if self._weather_valid is True and depth_ok:
            if self._depth_valid is True:
                self.status.set_ok("Weather & depth datasets validated")
            else:
                self.status.set_ok("Weather dataset validated (no bathymetry)")
            return
        if self._weather_valid is not True:
            self.status.set_pending("Provide valid weather data to continue")
        else:
            self.status.set_pending(
                "Bathymetry file provided but invalid — fix or clear it to continue"
            )

    def _on_weather_changed(self, text):
        self._validate_weather(text.strip())

    def _on_depth_changed(self, text):
        self._validate_depth(text.strip())

    def isComplete(self):
        if self._weather_loading or self._depth_loading:
            return False
        depth_ok = self._depth_valid is True or self._depth_valid is None
        return self._weather_valid is True and depth_ok

    # Config persistence
    def save_to_config(self):
        self.config["WEATHER_DATA"] = self.weather_field.text().strip()
        self.config["DEPTH_DATA"] = self.depth_field.text().strip()
        self.config["DELTA_TIME_FORECAST"] = self.delta_time.value()
        self.config["TIME_FORECAST"] = self.time_forecast.value()

    def initializePage(self):
        self.weather_field.setText(self.config.get("WEATHER_DATA", ""))
        self.depth_field.setText(self.config.get("DEPTH_DATA", ""))
        self.delta_time.setValue(int(self.config.get("DELTA_TIME_FORECAST") or 3))
        self.time_forecast.setValue(int(self.config.get("TIME_FORECAST") or 90))
        # Validate any pre-filled paths (e.g. when user navigates back then forward)
        self._validate_weather(self.weather_field.text().strip())
        self._validate_depth(self.depth_field.text().strip())
