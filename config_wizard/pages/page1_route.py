"""Page 1 — Route: source, destination, waypoints, departure time, map bbox."""

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsFillSymbol,
    QgsGeometry,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsRuleBasedRenderer,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)
from qgis.gui import QgsVertexMarker
from qgis.PyQt.QtCore import QDateTime, Qt, QVariant
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import (
    QDateTimeEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from ..ui.map_tools import MapPointPicker, RectangleMapTool
from ..ui.ui_kit import (
    COLOR_GREEN,
    COLOR_MUTED,
    COLOR_ORANGE,
    COLOR_PRIMARY,
    COLOR_REQUIRED,
    LatLonField,
    StatusLine,
    addWaypoint,
    clear_button,
    coord_input,
    field_label,
    format_coords,
    in_range,
    make_badge,
    page_header,
    set_field_error,
)


class RoutePage(QWizardPage):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.waypoint_rows = []
        self._iface = getattr(parent, "iface", None)
        self._previous_map_tool = None
        self._active_field = None
        self._active_label = None
        self._pick_map_tool = None
        self._pick_marker = None
        # Memory point layer holding the labelled route markers
        self._marker_layer = None
        # Bounding-box state
        self._bbox_layer = None
        self._bbox_map_tool = None
        self._bbox_prev_tool = None
        self._setting_bbox = False  # True while filling the bbox fields programmatically
        self._bbox_auto = False  # True while the box auto-tracks the route (±2°)
        self.status = None
        self._build_ui()

        # Auto-derive the bounding box from the route by default.
        self._bbox_auto = True

        # Remove the map artifacts from the project when the wizard is closed.
        if parent is not None:
            parent.finished.connect(self._cleanup_map_artifacts)

    def _build_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        page_layout.addWidget(scroll, 1)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        scroll.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(28, 22, 28, 18)
        root.setSpacing(16)

        root.addWidget(
            page_header(
                "Route",
                "Set the source, destination, and departure time.",
            )
        )

        # Source / Destination
        self.src_field = LatLonField("S", COLOR_GREEN)
        self.dst_field = LatLonField("D", COLOR_ORANGE)
        self._wire_point(self.src_field, "source")
        self._wire_point(self.dst_field, "destination")

        sd_grid = QGridLayout()
        sd_grid.setHorizontalSpacing(28)
        sd_grid.setVerticalSpacing(6)
        sd_grid.addWidget(field_label("Source", required=True), 0, 0)
        sd_grid.addWidget(field_label("Destination", required=True), 0, 1)
        sd_grid.addWidget(self.src_field, 1, 0)
        sd_grid.addWidget(self.dst_field, 1, 1)
        sd_grid.setColumnStretch(0, 1)
        sd_grid.setColumnStretch(1, 1)
        root.addLayout(sd_grid)

        # Intermediate waypoints
        root.addWidget(field_label("Intermediate waypoints"))
        self.wp_container = QVBoxLayout()
        self.wp_container.setSpacing(8)
        root.addLayout(self.wp_container)

        self.add_row = addWaypoint()
        self.add_row.clicked.connect(self._on_add_waypoint_clicked)
        self.wp_container.addWidget(self.add_row)

        for wpt in self.config.get("INTERMEDIATE_WAYPOINTS", []):
            if len(wpt) == 2:
                field = self._add_waypoint()
                field.set_coords(float(wpt[0]), float(wpt[1]))

        # Departure time
        self.dep_dt, dep_widget = self._make_dt_field("D", COLOR_ORANGE, clearable=False)
        self.dep_dt.setDateTime(QDateTime.currentDateTime())

        t_grid = QGridLayout()
        t_grid.setHorizontalSpacing(28)
        t_grid.setVerticalSpacing(6)
        t_grid.addWidget(field_label("Departure Time", required=True), 0, 0)
        t_grid.addWidget(dep_widget, 1, 0)
        t_grid.setColumnStretch(0, 1)
        t_grid.setColumnStretch(1, 1)
        root.addLayout(t_grid)

        # Output route path
        root.addWidget(field_label("Output route path", required=True))
        self.route_path = QLineEdit(self.config.get("ROUTE_PATH", "/tmp"))
        self.route_path.setPlaceholderText("Directory where the route output will be written")
        self.route_path.textChanged.connect(lambda: self.completeChanged.emit())
        browse_btn = QPushButton("Browse…")
        browse_btn.setAutoDefault(False)
        browse_btn.clicked.connect(self.browse_route_path)
        rp_row = QHBoxLayout()
        rp_row.addWidget(self.route_path, 1)
        rp_row.addWidget(browse_btn)
        root.addLayout(rp_row)

        # Advanced (bbox)
        self.adv_toggle = QPushButton("▶  Advanced options")
        self.adv_toggle.setFlat(True)
        self.adv_toggle.setAutoDefault(False)
        self.adv_toggle.setDefault(False)
        self.adv_toggle.setCursor(Qt.PointingHandCursor)
        self.adv_toggle.setStyleSheet(
            "QPushButton { text-align: left; border: none; background: transparent;"
            f" padding: 4px 0; font-weight: 600; color: {COLOR_MUTED}; }}"
            "QPushButton:hover { background: transparent; color: " + COLOR_PRIMARY + "; }"
        )
        self.adv_toggle.clicked.connect(self.toggle_advanced)
        root.addWidget(self.adv_toggle)

        self.adv_widget = self.build_advanced()
        self.adv_widget.setVisible(False)
        root.addWidget(self.adv_widget)

        root.addStretch(1)

        # Status line — pinned below the scroll area so it stays visible.
        self.status = StatusLine()
        status_wrap = QWidget()
        status_row = QHBoxLayout(status_wrap)
        status_row.setContentsMargins(28, 6, 28, 12)
        status_row.addWidget(self.status)
        page_layout.addWidget(status_wrap)
        self._update_status()

    def build_advanced(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(8)

        hint = QLabel(
            "Routing bounding box — automatically covers the source, destination "
            "and waypoints with a ±2° margin. Draw on the map or type values to override."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        lay.addWidget(hint)

        self.bbox_draw_btn = QPushButton("✏  Draw on map")
        self.bbox_draw_btn.setAutoDefault(False)
        self.bbox_draw_btn.clicked.connect(self.start_bbox_draw)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.bbox_draw_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self.bbox_lat_min = coord_input("lat min", -90.0, 90.0)
        self.bbox_lon_min = coord_input("lon min", -180.0, 180.0)
        self.bbox_lat_max = coord_input("lat max", -90.0, 90.0)
        self.bbox_lon_max = coord_input("lon max", -180.0, 180.0)
        bbox_row = QHBoxLayout()
        for w in (self.bbox_lat_min, self.bbox_lon_min, self.bbox_lat_max, self.bbox_lon_max):
            w.textChanged.connect(self.on_bbox_changed)
            bbox_row.addWidget(w)
        lay.addLayout(bbox_row)

        self.bbox_msg = QLabel()
        self.bbox_msg.setWordWrap(True)
        self.bbox_msg.setStyleSheet(f"color: {COLOR_REQUIRED}; font-size: 11px;")
        self.bbox_msg.setVisible(False)
        lay.addWidget(self.bbox_msg)
        return box

    def _make_dt_field(self, badge_text, color, clearable):
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        badge = make_badge(badge_text, color)
        dt = QDateTimeEdit()
        dt.setDisplayFormat("dd/MM/yyyy - hh:mm AP")
        dt.setCalendarPopup(True)
        dt.setTimeSpec(Qt.LocalTime)
        dt.dateTimeChanged.connect(self._update_status)

        row.addWidget(badge)
        row.addWidget(dt, 1)

        if clearable:
            btn = clear_button("Clear arrival time")
            btn.clicked.connect(lambda: dt.setDateTime(dt.minimumDateTime()))
            row.addWidget(btn)
        else:
            spacer = QWidget()
            spacer.setFixedWidth(30)
            row.addWidget(spacer)
        return dt, container

    def toggle_advanced(self):
        visible = not self.adv_widget.isVisible()
        self.adv_widget.setVisible(visible)
        self.adv_toggle.setText(("▼" if visible else "▶") + "  Advanced options")

    # Point / waypoint wiring
    def _wire_point(self, field, label):
        field.pick_requested.connect(lambda: self._start_map_pick(field, label))
        field.action_clicked.connect(field.clear)
        field.changed.connect(self._on_field_changed)

    def _on_field_changed(self):
        self._update_status()
        self._refresh_marker_layer()
        # A route-derived (auto) bounding box tracks source/destination changes.
        if self._bbox_auto:
            self._derive_bbox_from_route(track=True)
        self.completeChanged.emit()

    def _on_add_waypoint_clicked(self):
        self._add_waypoint()

    def _add_waypoint(self, lat=None, lon=None):
        idx = len(self.waypoint_rows) + 1
        field = LatLonField(str(idx), COLOR_PRIMARY)
        field.pick_requested.connect(lambda f=field: self._start_map_pick(f, "waypoint"))
        field.changed.connect(self._on_field_changed)

        entry = {"field": field}
        self.waypoint_rows.append(entry)

        # Insert above the add-row placeholder.
        self.wp_container.insertWidget(self.wp_container.count() - 1, field)

        def remove():
            self.waypoint_rows.remove(entry)
            field.setParent(None)
            self._renumber_waypoints()
            self._refresh_marker_layer()
            if self._bbox_auto:
                self._derive_bbox_from_route(track=True)
            self._update_status()

        field.action_clicked.connect(remove)

        if lat is not None and lon is not None:
            field.set_coords(float(lat), float(lon))
        return field

    def _renumber_waypoints(self):
        for i, entry in enumerate(self.waypoint_rows):
            entry["field"].set_badge_text(i + 1)

    # Bounding-box validation
    def _bbox_state(self):
        """Classify the advanced bbox inputs: ('empty'|'partial'|'invalid'|'order'|'ok', msg)."""
        fields = (self.bbox_lat_min, self.bbox_lon_min, self.bbox_lat_max, self.bbox_lon_max)
        texts = [f.text().strip() for f in fields]
        if not any(texts):
            return ("empty", "")
        if not all(texts):
            return ("partial", "Enter all four bounding-box values, or leave them all blank.")
        if not (in_range(self.bbox_lat_min) and in_range(self.bbox_lat_max)):
            return ("invalid", "Latitudes must be numbers between −90 and 90.")
        if not (in_range(self.bbox_lon_min) and in_range(self.bbox_lon_max)):
            return ("invalid", "Longitudes must be numbers between −180 and 180.")
        lat_min, lon_min = float(texts[0]), float(texts[1])
        lat_max, lon_max = float(texts[2]), float(texts[3])
        if lat_min >= lat_max or lon_min >= lon_max:
            return (
                "order",
                "Min values must be smaller than max values (lat min < lat max, lon min < lon max).",
            )
        return ("ok", "")

    def on_bbox_changed(self):
        state, msg = self._bbox_state()
        # A hand-edit detaches the box from the route so it stops auto-tracking.
        if not self._setting_bbox:
            self._bbox_auto = False
        # Red-border any individual field that is non-empty and out of range.
        for f in (self.bbox_lat_min, self.bbox_lon_min, self.bbox_lat_max, self.bbox_lon_max):
            set_field_error(f, bool(f.text().strip()) and not in_range(f))
        self.bbox_msg.setText(msg)
        self.bbox_msg.setVisible(bool(msg))
        self._refresh_bbox_layer()
        self._update_status()
        self.completeChanged.emit()

    def browse_route_path(self):
        path = QFileDialog.getExistingDirectory(self, "Output route path", self.route_path.text())
        if path:
            self.route_path.setText(path)

    # Bounding box — fields, derive, draw, and preview layer
    def set_bbox_fields(self, lat_min, lon_min, lat_max, lon_max):
        """Fill the four bbox fields programmatically (without flipping auto-tracking)."""
        self._setting_bbox = True
        try:
            self.bbox_lat_min.setText(f"{lat_min:.4f}")
            self.bbox_lon_min.setText(f"{lon_min:.4f}")
            self.bbox_lat_max.setText(f"{lat_max:.4f}")
            self.bbox_lon_max.setText(f"{lon_max:.4f}")
        finally:
            self._setting_bbox = False
        self.on_bbox_changed()

    def _bbox_wgs84(self):
        """Current bbox as (lat_min, lon_min, lat_max, lon_max) if valid, else None."""
        if self._bbox_state()[0] != "ok":
            return None
        return (
            float(self.bbox_lat_min.text()),
            float(self.bbox_lon_min.text()),
            float(self.bbox_lat_max.text()),
            float(self.bbox_lon_max.text()),
        )

    def _route_bbox_bounds(self):
        """(lat_min, lon_min, lat_max, lon_max) padded ±2° around the source,
        destination and waypoints (clamped to valid ranges), or None if the
        route isn't defined yet."""
        src = self.src_field.get_coords()
        dst = self.dst_field.get_coords()
        if not (src and dst):
            return None
        points = [src, dst]
        for entry in self.waypoint_rows:
            coords = entry["field"].get_coords()
            if coords is not None:
                points.append(coords)
        buf = 2.0
        lats = [p[0] for p in points]
        lons = [p[1] for p in points]
        return (
            max(-90.0, min(lats) - buf),
            max(-180.0, min(lons) - buf),
            min(90.0, max(lats) + buf),
            min(180.0, max(lons) + buf),
        )

    def _derive_bbox_from_route(self, track):
        """Fill the bbox from the route ±2°. Returns False if the route isn't set."""
        bounds = self._route_bbox_bounds()
        if bounds is None:
            return False
        self.set_bbox_fields(*bounds)
        self._bbox_auto = track
        return True

    # Interactive draw on the map
    def start_bbox_draw(self):
        if self._iface is None:
            return

        window = self.window()
        if window is not None:
            window.hide()
        main_window = self._iface.mainWindow()
        main_window.raise_()
        main_window.activateWindow()

        canvas = self._iface.mapCanvas()
        self._bbox_prev_tool = canvas.mapTool()

        tool = RectangleMapTool(canvas)
        tool.rectangleConfirmed.connect(self._on_bbox_drawn)
        tool.cancelled.connect(self.finish_bbox_draw)
        canvas.setMapTool(tool)
        self._bbox_map_tool = tool

        # Seed with the existing box (if any) so the user can just adjust it.
        current = self._bbox_wgs84()
        if current is not None:
            lat_min, lon_min, lat_max, lon_max = current
            rect = QgsRectangle(lon_min, lat_min, lon_max, lat_max)
            tool.set_rectangle(self._rect_to_canvas(rect))

        self._iface.messageBar().pushInfo(
            "Weather Routing Tool",
            "Drag to draw the routing area; drag its edges/corners to adjust. "
            "Double-click or Enter to confirm, Esc to cancel.",
        )

    def _on_bbox_drawn(self, rect_canvas):
        """Confirm the drawn rectangle (canvas CRS) and commit it to the fields."""
        rect = self._rect_to_wgs84(rect_canvas)
        lat_min, lon_min = rect.yMinimum(), rect.xMinimum()
        lat_max, lon_max = rect.yMaximum(), rect.xMaximum()

        prompt = QMessageBox(self._iface.mainWindow())
        prompt.setIcon(QMessageBox.Question)
        prompt.setWindowTitle("Confirm bounding box")
        prompt.setWindowModality(Qt.ApplicationModal)
        prompt.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        prompt.setText(
            "Use this routing area?\n"
            f"lat {lat_min:.4f} … {lat_max:.4f}\n"
            f"lon {lon_min:.4f} … {lon_max:.4f}"
        )
        use_btn = prompt.addButton("Use this area", QMessageBox.AcceptRole)
        prompt.addButton("Keep adjusting", QMessageBox.RejectRole)
        prompt.setDefaultButton(use_btn)
        prompt.raise_()
        prompt.activateWindow()
        prompt.exec_()
        if prompt.clickedButton() is not use_btn:
            return  # stay in the draw tool for further adjustment

        self.set_bbox_fields(lat_min, lon_min, lat_max, lon_max)
        self._bbox_auto = False  # an explicitly drawn box does not track the route
        self.finish_bbox_draw()

    def finish_bbox_draw(self):
        if self._bbox_map_tool is None:
            return  # no draw session active
        if self._iface is not None:
            canvas = self._iface.mapCanvas()
            if self._bbox_prev_tool is not None:
                canvas.setMapTool(self._bbox_prev_tool)  # deactivates our tool (clears bands)
            self._iface.messageBar().clearWidgets()
        self._bbox_map_tool = None
        self._bbox_prev_tool = None
        self._restore_window()

    # -- CRS helpers --
    def _rect_to_canvas(self, rect_wgs84):
        return self._transform_rect(rect_wgs84, to_canvas=True)

    def _rect_to_wgs84(self, rect_canvas):
        return self._transform_rect(rect_canvas, to_canvas=False)

    def _transform_rect(self, rect, to_canvas):
        canvas_crs = self._iface.mapCanvas().mapSettings().destinationCrs()
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        src, dst = (wgs84, canvas_crs) if to_canvas else (canvas_crs, wgs84)
        if src == dst:
            return QgsRectangle(rect)
        transform = QgsCoordinateTransform(src, dst, QgsProject.instance())
        return transform.transformBoundingBox(rect)

    # -- preview polygon layer --
    def _refresh_bbox_layer(self):
        box = self._bbox_wgs84()
        if box is None:
            self._remove_bbox_layer()
            return
        lat_min, lon_min, lat_max, lon_max = box
        layer = self._ensure_bbox_layer()
        provider = layer.dataProvider()
        provider.truncate()
        feat = QgsFeature(layer.fields())
        feat.setGeometry(QgsGeometry.fromRect(QgsRectangle(lon_min, lat_min, lon_max, lat_max)))
        provider.addFeatures([feat])
        layer.triggerRepaint()

    def _ensure_bbox_layer(self):
        if self._bbox_layer is not None:
            return self._bbox_layer
        layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "WRT Routing Area", "memory")
        symbol = QgsFillSymbol.createSimple(
            {
                "color": "37,99,235,30",
                "outline_color": COLOR_PRIMARY,
                "outline_width": "0.5",
                "outline_style": "dash",
            }
        )
        layer.renderer().setSymbol(symbol)
        QgsProject.instance().addMapLayer(layer)
        self._bbox_layer = layer
        return layer

    def _remove_bbox_layer(self):
        if self._bbox_layer is not None:
            QgsProject.instance().removeMapLayer(self._bbox_layer.id())
            self._bbox_layer = None

    def _cleanup_map_artifacts(self):
        # Restore the map tool if a draw is mid-flight, but don't re-show the
        # (closing) wizard window like finish_bbox_draw would.
        if self._bbox_map_tool is not None and self._iface is not None:
            canvas = self._iface.mapCanvas()
            if self._bbox_prev_tool is not None:
                canvas.setMapTool(self._bbox_prev_tool)
            self._iface.messageBar().clearWidgets()
            self._bbox_map_tool = None
            self._bbox_prev_tool = None
        self._remove_bbox_layer()
        self._remove_marker_layer()

    # Status / completion
    def _update_status(self):
        if self.status is None:
            return  # still being constructed
        have_src = self.src_field.get_coords() is not None
        have_dst = self.dst_field.get_coords() is not None
        missing = []
        if not have_src:
            missing.append("source")
        if not have_dst:
            missing.append("destination")
        if missing:
            self.status.set_pending("Set " + " and ".join(missing) + " to continue")
            return
        bbox_state, bbox_msg = self._bbox_state()
        if bbox_state not in ("empty", "ok"):
            self.status.set_pending("Bounding box — " + bbox_msg)
            return
        self.status.set_ok("Source, destination & departure time set")

    def isComplete(self):
        return bool(
            self.src_field.get_coords() is not None
            and self.dst_field.get_coords() is not None
            and self.route_path.text().strip()
            and self._bbox_state()[0] in ("empty", "ok")
        )

    # Config persistence
    def save_to_config(self):
        src = self.src_field.get_coords()
        dst = self.dst_field.get_coords()
        if src and dst:
            self.config["DEFAULT_ROUTE"] = f"{src[0]},{src[1]},{dst[0]},{dst[1]}"

        self.config["DEPARTURE_TIME"] = (
            self.dep_dt.dateTime().toUTC().toString("yyyy-MM-ddTHH:mm") + "Z"
        )
        self.config["ROUTE_PATH"] = self.route_path.text()

        waypoints = []
        for entry in self.waypoint_rows:
            coords = entry["field"].get_coords()
            if coords is not None:
                waypoints.append([coords[0], coords[1]])
        self.config["INTERMEDIATE_WAYPOINTS"] = waypoints

        # Build bbox — prefer the field values when they form a valid box,
        # otherwise fall back to the route-derived ±2° box (never persist a
        # partial/invalid bbox).
        if self._bbox_state()[0] == "ok":
            self.config["DEFAULT_MAP"] = (
                f"{self.bbox_lat_min.text()},{self.bbox_lon_min.text()},"
                f"{self.bbox_lat_max.text()},{self.bbox_lon_max.text()}"
            )
        else:
            bounds = self._route_bbox_bounds()
            if bounds is not None:
                self.config["DEFAULT_MAP"] = "{},{},{},{}".format(*bounds)
            else:
                self.config["DEFAULT_MAP"] = ""

    def initializePage(self):
        route = self.config.get("DEFAULT_ROUTE", "")
        if route:
            parts = [p.strip() for p in route.split(",")]
            if len(parts) == 4:
                try:
                    self.src_field.set_coords(float(parts[0]), float(parts[1]))
                    self.dst_field.set_coords(float(parts[2]), float(parts[3]))
                except ValueError:
                    pass
        dep_str = self.config.get("DEPARTURE_TIME", "")
        if dep_str:
            utc_dt = QDateTime.fromString(dep_str, "yyyy-MM-ddTHH:mmZ")
            if utc_dt.isValid():
                utc_dt.setTimeSpec(Qt.UTC)
                self.dep_dt.setDateTime(utc_dt.toLocalTime())
        self.route_path.setText(self.config.get("ROUTE_PATH", "/tmp"))

        # Restore a previously-set bounding box into the fields (and its preview).
        bbox = self.config.get("DEFAULT_MAP", "")
        if bbox:
            parts = [p.strip() for p in bbox.split(",")]
            if len(parts) == 4:
                try:
                    self.set_bbox_fields(
                        float(parts[0]),
                        float(parts[1]),
                        float(parts[2]),
                        float(parts[3]),
                    )
                    self._bbox_auto = False
                except ValueError:
                    pass
        self._update_status()

    # Map picking
    def _start_map_pick(self, field, label):
        if self._iface is None:
            return

        self._active_field = field
        self._active_label = label

        window = self.window()
        if window is not None:
            window.hide()

        main_window = self._iface.mainWindow()
        main_window.raise_()
        main_window.activateWindow()

        canvas = self._iface.mapCanvas()
        self._previous_map_tool = canvas.mapTool()

        map_tool = MapPointPicker(canvas)
        map_tool.canvasClicked.connect(self._handle_map_click)
        canvas.setMapTool(map_tool)
        self._pick_map_tool = map_tool

        self._iface.messageBar().pushInfo(
            "Weather Routing Tool",
            f"Click on the map to set the {label} location. "
            "Drag to pan, scroll to zoom. Right-click to cancel.",
        )

    def _clear_pick_marker(self):
        if self._pick_marker is not None:
            canvas = self._iface.mapCanvas() if self._iface is not None else None
            if canvas is not None:
                canvas.scene().removeItem(self._pick_marker)
            self._pick_marker = None

    # Labelled route-marker layer
    def _collect_points(self):
        """(role, label, lat, lon) for every point field that has valid coords."""
        points = []
        src = self.src_field.get_coords()
        if src is not None:
            points.append(("source", "Source", src[0], src[1]))
        dst = self.dst_field.get_coords()
        if dst is not None:
            points.append(("destination", "Destination", dst[0], dst[1]))
        for i, entry in enumerate(self.waypoint_rows, start=1):
            coords = entry["field"].get_coords()
            if coords is not None:
                points.append(("waypoint", f"WP{i}", coords[0], coords[1]))
        return points

    def _refresh_marker_layer(self):
        """Rebuild the marker layer's features from the current field coordinates."""
        points = self._collect_points()
        if not points:
            self._remove_marker_layer()
            return

        layer = self._ensure_marker_layer()
        provider = layer.dataProvider()
        provider.truncate()  # drop existing features; we rebuild from scratch

        feats = []
        for role, label, lat, lon in points:
            feat = QgsFeature(layer.fields())
            feat.setAttributes([role, label])
            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
            feats.append(feat)
        provider.addFeatures(feats)
        layer.triggerRepaint()

    def _ensure_marker_layer(self):
        if self._marker_layer is not None:
            return self._marker_layer
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "WRT Route Points", "memory")
        provider = layer.dataProvider()
        provider.addAttributes(
            [
                QgsField("role", QVariant.String),
                QgsField("label", QVariant.String),
            ]
        )
        layer.updateFields()
        self._style_marker_layer(layer)
        QgsProject.instance().addMapLayer(layer)
        self._marker_layer = layer
        return layer

    def _style_marker_layer(self, layer):
        def rule(name, expr, color):
            symbol = QgsMarkerSymbol.createSimple(
                {
                    "name": "circle",
                    "size": "3.5",
                    "size_unit": "MM",
                    "color": color,
                    "outline_color": "white",
                    "outline_width": "0.4",
                }
            )
            r = QgsRuleBasedRenderer.Rule(symbol)
            r.setFilterExpression(expr)
            r.setLabel(name)
            return r

        root = QgsRuleBasedRenderer.Rule(None)
        root.appendChild(rule("Source", "\"role\" = 'source'", COLOR_GREEN))
        root.appendChild(rule("Destination", "\"role\" = 'destination'", COLOR_ORANGE))
        root.appendChild(rule("Waypoint", "\"role\" = 'waypoint'", COLOR_PRIMARY))
        layer.setRenderer(QgsRuleBasedRenderer(root))

        fmt = QgsTextFormat()
        font = QFont("Sans Serif", 9)
        font.setBold(True)
        fmt.setFont(font)
        buf = QgsTextBufferSettings()
        buf.setEnabled(True)
        buf.setSize(1.0)
        buf.setColor(QColor("white"))
        fmt.setBuffer(buf)

        pal = QgsPalLayerSettings()
        pal.fieldName = "label"
        pal.enabled = True
        pal.setFormat(fmt)
        pal.placement = QgsPalLayerSettings.AroundPoint
        pal.dist = 2.5
        pal.distUnits = QgsUnitTypes.RenderMillimeters
        layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
        layer.setLabelsEnabled(True)

    def _remove_marker_layer(self):
        self._clear_pick_marker()
        if self._marker_layer is not None:
            QgsProject.instance().removeMapLayer(self._marker_layer.id())
            self._marker_layer = None

    def _restore_window(self):
        window = self.window()
        if window is None:
            return
        window.show()
        window.raise_()
        window.activateWindow()

    def _finish_pick(self):
        """End the whole pick session: restore the previous tool and the wizard."""
        if self._iface is not None and self._previous_map_tool is not None:
            self._iface.mapCanvas().setMapTool(self._previous_map_tool)
        if self._iface is not None:
            self._iface.messageBar().clearWidgets()

        self._clear_pick_marker()
        self._restore_window()

        self._active_field = None
        self._active_label = None
        self._previous_map_tool = None
        self._pick_map_tool = None

    def _show_marker(self, canvas, point):
        self._clear_pick_marker()
        self._pick_marker = QgsVertexMarker(canvas)
        self._pick_marker.setCenter(point)
        self._pick_marker.setIconType(QgsVertexMarker.ICON_CROSS)
        self._pick_marker.setColor(Qt.red)
        self._pick_marker.setPenWidth(3)
        self._pick_marker.setIconSize(16)

    def _handle_map_click(self, point, button):
        if self._iface is None:
            return

        # Right-click aborts the entire pick and returns to the wizard.
        if button == Qt.RightButton:
            self._finish_pick()
            return

        canvas = self._iface.mapCanvas()
        point_wgs84 = point

        canvas_crs = canvas.mapSettings().destinationCrs()
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        if canvas_crs != wgs84:
            transform = QgsCoordinateTransform(canvas_crs, wgs84, QgsProject.instance())
            point_wgs84 = transform.transform(point)

        self._show_marker(canvas, point)

        lat = point_wgs84.y()
        lon = point_wgs84.x()

        prompt = QMessageBox(self._iface.mainWindow())
        prompt.setIcon(QMessageBox.Question)
        prompt.setWindowTitle("Confirm location")
        prompt.setWindowModality(Qt.ApplicationModal)
        prompt.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        label = self._active_label or "selected"
        prompt.setText(f"Use this location for the {label} point?\n{format_coords(lat, lon)}")
        use_btn = prompt.addButton("Use this location", QMessageBox.AcceptRole)
        prompt.addButton("Pick again", QMessageBox.RejectRole)
        prompt.setDefaultButton(use_btn)
        prompt.raise_()
        prompt.activateWindow()

        prompt.exec_()
        if prompt.clickedButton() is not use_btn:
            self._clear_pick_marker()
            return

        if self._active_field is not None:
            self._active_field.set_coords(lat, lon)

        self._finish_pick()
