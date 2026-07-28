"""Shared UI toolkit — colours, global stylesheet, badges and the coordinate field."""

import os
import re

from qgis.PyQt.QtCore import QLocale, Qt, pyqtSignal
from qgis.PyQt.QtGui import QDoubleValidator
from qgis.PyQt.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# Check icon svg path
CHECK_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "check.svg")

# Palette
COLOR_BG = "#ffffff"
COLOR_SIDEBAR_BG = "#f6f7f9"
COLOR_PRIMARY = "#2563eb"
COLOR_PRIMARY_DARK = "#1d4ed8"
COLOR_PRIMARY_SOFT = "#e8f0fe"
COLOR_TEXT = "#1f2937"
COLOR_MUTED = "#6b7280"
COLOR_BORDER = "#e2e5ea"
COLOR_INPUT_BORDER = "#d1d5db"
COLOR_GREEN = "#34a853"
COLOR_ORANGE = "#e8835a"
COLOR_ARRIVAL = "#e8a05a"
COLOR_SUCCESS = "#1b873f"
COLOR_REQUIRED = "#e5484d"
COLOR_GRAY_BADGE = "#e5e7eb"
COLOR_WARNING = "#d97706"
COLOR_FILE_OK = "#3B6D11"
COLOR_FILE_ERROR = "#D85A30"


# Global stylesheet
GLOBAL_QSS = f"""
QWidget {{
    color: {COLOR_TEXT};
    font-size: 13px;
}}
QLineEdit, QDateTimeEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {{
    background: #ffffff;
    border: 1px solid {COLOR_INPUT_BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    color: {COLOR_TEXT};
    selection-background-color: {COLOR_PRIMARY};
    selection-color: #ffffff;
}}
QLineEdit:focus, QDateTimeEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {{
    border: 1px solid {COLOR_PRIMARY};
}}
QLineEdit:disabled, QDateTimeEdit:disabled {{
    background: #f3f4f6;
    color: {COLOR_MUTED};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    background: #ffffff;
    selection-background-color: {COLOR_PRIMARY_SOFT};
    selection-color: {COLOR_TEXT};
    outline: 0;
}}
QGroupBox {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    margin-top: 10px;
    padding: 16px 14px 12px 14px;
    font-weight: 600;
    color: {COLOR_TEXT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {COLOR_TEXT};
}}
QPushButton {{
    background: #ffffff;
    border: 1px solid {COLOR_INPUT_BORDER};
    border-radius: 8px;
    padding: 7px 16px;
    color: {COLOR_TEXT};
}}
QPushButton:hover {{ background: #f3f4f6; }}
QPushButton:pressed {{ background: #e9ebef; }}
QPushButton:default {{
    background: {COLOR_PRIMARY};
    color: #ffffff;
    border: 1px solid {COLOR_PRIMARY};
    font-weight: 600;
}}
QPushButton:default:hover {{ background: {COLOR_PRIMARY_DARK}; }}
QCheckBox {{ spacing: 8px; color: {COLOR_TEXT}; }}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border: 1px solid {COLOR_INPUT_BORDER};
    border-radius: 5px;
    background: #ffffff;
}}
QCheckBox::indicator:unchecked:hover {{
    border: 1px solid {COLOR_PRIMARY};
    background: {COLOR_PRIMARY_SOFT};
}}
QCheckBox::indicator:checked {{
    background: {COLOR_PRIMARY};
    border: 1px solid {COLOR_PRIMARY};
    image: url({CHECK_PATH});
}}
QCheckBox::indicator:checked:hover {{ background: {COLOR_PRIMARY_DARK}; border-color: {COLOR_PRIMARY_DARK}; }}
QCheckBox::indicator:disabled {{ background: #f3f4f6; border-color: {COLOR_BORDER}; }}
QCheckBox:disabled {{ color: {COLOR_MUTED}; }}

/* CheckCard — a selectable option row (see the CheckCard widget). */
QFrame#CheckCard {{
    border: 1px solid {COLOR_INPUT_BORDER};
    border-radius: 10px;
    background: #ffffff;
}}
QFrame#CheckCard:hover {{ border-color: {COLOR_PRIMARY}; background: #fafbff; }}
QFrame#CheckCard[checked="true"] {{ border: 1px solid {COLOR_PRIMARY}; background: {COLOR_PRIMARY_SOFT}; }}
QFrame#CheckCard[checked="true"]:hover {{ background: {COLOR_PRIMARY_SOFT}; }}
QLabel#CheckCardBox {{
    border: 1px solid {COLOR_INPUT_BORDER};
    border-radius: 6px;
    background: #ffffff;
    color: #ffffff;
    font-size: 13px; font-weight: 700;
}}
QFrame#CheckCard[checked="true"] QLabel#CheckCardBox {{
    background: {COLOR_PRIMARY}; border: 1px solid {COLOR_PRIMARY};
}}
QLabel#CheckCardTitle {{ font-size: 13px; font-weight: 600; color: {COLOR_TEXT}; background: transparent; }}
QLabel#CheckCardDesc {{ font-size: 11px; color: {COLOR_MUTED}; background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #cfd4dc; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #b6bcc6; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QLabel#PageTitle {{ font-size: 19px; font-weight: 700; color: {COLOR_TEXT}; }}
QLabel#PageSubtitle {{ font-size: 13px; color: {COLOR_MUTED}; }}
QLabel#SectionLabel {{ font-size: 12px; font-weight: 600; color: {COLOR_TEXT}; }}
QLabel#StatusOk {{ font-size: 13px; font-weight: 600; color: {COLOR_SUCCESS}; }}
QLabel#StatusPending {{ font-size: 13px; color: {COLOR_MUTED}; }}
QToolButton#ClearBtn {{
    border: 1px solid {COLOR_INPUT_BORDER};
    border-radius: 8px;
    background: #ffffff;
    color: {COLOR_MUTED};
    font-size: 13px;
    padding: 0;
}}
QToolButton#ClearBtn:hover {{ background: #fdecec; color: {COLOR_REQUIRED}; border-color: #f2b8b8; }}
QToolButton#PickBtn {{
    border: 1px solid {COLOR_INPUT_BORDER};
    border-radius: 8px;
    background: #ffffff;
    font-size: 14px;
    padding: 0;
}}
QToolButton#PickBtn:hover {{ background: {COLOR_PRIMARY_SOFT}; border-color: {COLOR_PRIMARY}; }}
"""


# Components
class ClickableLabel(QLabel):
    """A QLabel that emits ``clicked`` on a left-button press."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


def make_badge(text, color, diameter=26, clickable=False):
    """A circular coloured badge with white centred text."""
    lbl = ClickableLabel(str(text)) if clickable else QLabel(str(text))
    lbl.setFixedSize(diameter, diameter)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        f"background: {color}; color: white; border-radius: {diameter // 2}px;"
        f"font-weight: 600; font-size: 12px;"
    )
    if clickable:
        lbl.setCursor(Qt.PointingHandCursor)
        lbl.setToolTip("Click to pick this point on the map")
    return lbl


def make_dashed_badge(diameter=26):
    lbl = QLabel("+")
    lbl.setFixedSize(diameter, diameter)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        f"border: 1.5px dashed #b6bcc6; border-radius: {diameter // 2}px;"
        f"color: #9aa0aa; font-size: 16px; background: transparent;"
    )
    return lbl


class addWaypoint(QWidget):
    """The dashed '+ Click to add waypoint' placeholder row."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.badge = make_dashed_badge()
        self.hint = QLabel("Click to add waypoint")
        self.hint.setStyleSheet(
            f"color: {COLOR_MUTED}; border: 1px dashed #cfd4dc; border-radius: 8px;"
            "padding: 6px 10px; background: #fbfcfd;"
        )

        row.addWidget(self.badge)
        row.addWidget(self.hint, 1)
        # Phantom spacers matching the pick + clear buttons so rows stay aligned.
        for _ in range(2):
            spacer = QWidget()
            spacer.setFixedWidth(30)
            row.addWidget(spacer)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


def field_label(text, required=False):
    lbl = QLabel(f"{text} <span style='color:{COLOR_REQUIRED}'>*</span>" if required else text)
    lbl.setObjectName("SectionLabel")
    lbl.setTextFormat(Qt.RichText)
    return lbl


def clear_button(tooltip="Clear"):
    btn = QToolButton()
    btn.setObjectName("ClearBtn")
    btn.setText("✕")
    btn.setFixedSize(30, 30)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setToolTip(tooltip)
    return btn


def pick_button(tooltip="Pick this point from the map"):
    btn = QToolButton()
    btn.setObjectName("PickBtn")
    btn.setText("📍")
    btn.setFixedSize(30, 30)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setToolTip(tooltip)
    return btn


def page_header(title, subtitle):
    """Returns the in-content title + subtitle block used at the top of a page."""
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)

    title_lbl = QLabel(title)
    title_lbl.setObjectName("PageTitle")
    lay.addWidget(title_lbl)

    sub_lbl = QLabel(subtitle)
    sub_lbl.setObjectName("PageSubtitle")
    sub_lbl.setWordWrap(True)
    lay.addWidget(sub_lbl)
    return box


def hline():
    line = QWidget()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {COLOR_BORDER};")
    line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return line


def join_terms(items):
    """Join a list into readable prose: 'a', 'a and b', 'a, b and c'."""
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f" and {items[-1]}"


class CheckCard(QFrame):
    """A selectable option row — check indicator + title (+ optional description).

    Behaves like a QCheckBox (``isChecked`` / ``setChecked`` / ``toggled``) but
    renders as a whole-row clickable, highlightable card. Styling lives in
    GLOBAL_QSS under the ``CheckCard`` object names.
    """

    toggled = pyqtSignal(bool)

    def __init__(self, title, description="", parent=None):
        super().__init__(parent)
        self._checked = False
        self.setObjectName("CheckCard")
        self.setCursor(Qt.PointingHandCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(12)

        self._box = QLabel()
        self._box.setObjectName("CheckCardBox")
        self._box.setFixedSize(20, 20)
        self._box.setAlignment(Qt.AlignCenter)
        row.addWidget(self._box, 0, Qt.AlignTop)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        self._title = QLabel(title)
        self._title.setObjectName("CheckCardTitle")
        text_col.addWidget(self._title)
        if description:
            desc = QLabel(description)
            desc.setObjectName("CheckCardDesc")
            desc.setWordWrap(True)
            desc.setAttribute(Qt.WA_TransparentForMouseEvents)
            text_col.addWidget(desc)
        row.addLayout(text_col, 1)

        # Clicks anywhere on the card should reach the frame, not the labels.
        for w in (self._box, self._title):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)

        self._sync()

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        checked = bool(checked)
        if checked == self._checked:
            return
        self._checked = checked
        self._sync()
        self.toggled.emit(checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)

    def _sync(self):
        self.setProperty("checked", self._checked)
        self._box.setText("✓" if self._checked else "")
        # Re-polish so the property-based QSS (card + indicator) re-applies.
        for w in (self, self._box):
            w.style().unpolish(w)
            w.style().polish(w)


class StatusLine(QWidget):
    """A separator + status label pinned at the bottom of a wizard page.

    Use :meth:`set_ok` for a green '✓ …' confirmation and :meth:`set_pending`
    for a muted '• …' hint. Styling comes from the StatusOk / StatusPending
    object names in the global stylesheet.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(hline())
        self.label = QLabel()
        self.label.setWordWrap(True)
        lay.addWidget(self.label)

    def set_ok(self, text):
        self._apply("StatusOk", f"✓  {text}")

    def set_pending(self, text):
        self._apply("StatusPending", f"•  {text}")

    def _apply(self, object_name, text):
        self.label.setObjectName(object_name)
        self.label.setText(text)
        # Re-evaluate object-name based styling.
        self.label.style().unpolish(self.label)
        self.label.style().polish(self.label)


# Coordinate parsing / formatting
def parse_coords(text):
    """Parse ``lat, lon`` from free-form text.

    Accepts ``51.90°N, 4.00°E``, ``51.90, 4.00``, ``51.90 4.00`` and similar.
    Returns ``(lat, lon)`` floats or ``None`` if two numbers can't be found.
    """
    if not text or not text.strip():
        return None
    pairs = re.findall(r"([-+]?\d+(?:\.\d+)?)\s*([NSEWnsew])?", text)
    nums = []
    for num, hemi in pairs:
        if num == "":
            continue
        value = float(num)
        h = hemi.upper()
        if h in ("S", "W"):
            value = -abs(value)
        nums.append((value, h))
    if len(nums) < 2:
        return None

    lat = lon = None
    for value, h in nums:
        if h in ("N", "S") and lat is None:
            lat = value
        elif h in ("E", "W") and lon is None:
            lon = value
    if lat is None or lon is None:
        lat, lon = nums[0][0], nums[1][0]
    return (lat, lon)


def format_coords(lat, lon):
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{abs(lat):.2f}°{ns}, {abs(lon):.2f}°{ew}"


class CoordinateField(QWidget):
    """A badge + coordinate input + clear/remove button.

    Signals:
        pick_requested — the badge was clicked (start a map pick for this field).
        action_clicked — the trailing ✕ button was clicked (clear or remove).
        changed        — the text changed.
    """

    pick_requested = pyqtSignal()
    action_clicked = pyqtSignal()
    changed = pyqtSignal()

    def __init__(
        self, badge_text, badge_color, placeholder="Click map to add…", parent=None, show_pick=True
    ):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.badge = make_badge(badge_text, badge_color, clickable=True)
        self.badge.clicked.connect(self.pick_requested)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.textChanged.connect(self.changed)

        row.addWidget(self.badge)
        row.addWidget(self.edit, 1)

        if show_pick:
            self.pick_btn = pick_button()
            self.pick_btn.clicked.connect(self.pick_requested)
            row.addWidget(self.pick_btn)

        self.action_btn = clear_button()
        self.action_btn.clicked.connect(self.action_clicked)
        row.addWidget(self.action_btn)

    def set_badge_text(self, text):
        self.badge.setText(str(text))

    def set_coords(self, lat, lon):
        self.edit.setText(format_coords(lat, lon))

    def get_coords(self):
        return parse_coords(self.edit.text())

    def text(self):
        return self.edit.text()

    def setText(self, value):
        self.edit.setText(value)

    def clear(self):
        self.edit.clear()


def coord_input(placeholder, low, high):
    """A QLineEdit constrained to numbers in [low, high] with '.' as separator.

    The bounds are stored on the widget (``_lo`` / ``_hi``) so callers can do a
    strict range check — QDoubleValidator alone treats out-of-range values as
    'Intermediate' and still lets the user type them.
    """
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    validator = QDoubleValidator(low, high, 6)
    validator.setNotation(QDoubleValidator.StandardNotation)
    validator.setLocale(QLocale.c())  # force '.' as decimal separator
    edit.setValidator(validator)
    edit.setLocale(QLocale.c())
    edit.setMinimumWidth(0)
    edit._lo, edit._hi = low, high
    return edit


def set_field_error(widget, error):
    """Toggle a red error border on an input widget (e.g. out-of-range value)."""
    widget.setStyleSheet(f"QLineEdit {{ border: 1px solid {COLOR_REQUIRED}; }}" if error else "")


def in_range(edit):
    """True if a coord_input's text is a number within its [_lo, _hi] bounds.

    Empty text counts as out-of-range here (caller decides if empty is allowed).
    """
    txt = edit.text().strip()
    if not txt:
        return False
    try:
        v = float(txt)
    except ValueError:
        return False
    return edit._lo <= v <= edit._hi


# Shared form-field factories (used across the boat / weather / algorithm pages)
def bold_label(text, tip=""):
    """A bold label, optionally with a tooltip. Used for optional fields."""
    lbl = QLabel(f"<b>{text}</b>")
    lbl.setTextFormat(Qt.RichText)
    if tip:
        lbl.setToolTip(tip)
    return lbl


opt_label = bold_label


def req_label(text, tip=""):
    """A bold label with a trailing red asterisk marking a required field."""
    lbl = QLabel(f"<b>{text}</b> <span style='color:{COLOR_REQUIRED}'>*</span>")
    lbl.setTextFormat(Qt.RichText)
    if tip:
        lbl.setToolTip(tip)
    return lbl


def dspin(val=0.0, mn=0.0, mx=999999.0, dec=2, suffix=""):
    """A QDoubleSpinBox with sensible defaults and a fixed minimum width."""
    w = QDoubleSpinBox()
    w.setRange(mn, mx)
    w.setDecimals(dec)
    w.setValue(val)
    if suffix:
        w.setSuffix(f"  {suffix}")
    w.setMinimumWidth(160)
    return w


def ispin(val=0, mn=0, mx=999999):
    """A QSpinBox with a fixed minimum width."""
    w = QSpinBox()
    w.setRange(mn, mx)
    w.setValue(val)
    w.setMinimumWidth(160)
    return w


def collapsible(title):
    """A flat toggle button that shows/hides a returned (initially hidden) QGroupBox."""
    btn = QPushButton("▶  " + title)
    btn.setFlat(True)
    btn.setAutoDefault(False)
    btn.setDefault(False)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(
        "QPushButton { text-align: left; border: none; background: transparent;"
        f" padding: 4px 0; font-weight: 600; color: {COLOR_MUTED}; }}"
        f"QPushButton:hover {{ background: transparent; color: {COLOR_PRIMARY}; }}"
    )
    box = QGroupBox()
    box.setVisible(False)

    def toggle():
        vis = not box.isVisible()
        box.setVisible(vis)
        btn.setText(("▼" if vis else "▶") + "  " + title)

    btn.clicked.connect(toggle)
    return btn, box


class LatLonField(QWidget):
    """A badge + separate Latitude/Longitude inputs + pick/clear buttons."""

    pick_requested = pyqtSignal()
    action_clicked = pyqtSignal()
    changed = pyqtSignal()

    def __init__(self, badge_text, badge_color, parent=None, show_pick=True):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.badge = make_badge(badge_text, badge_color, clickable=True)
        self.badge.clicked.connect(self.pick_requested)

        self.lat = coord_input("e.g. 12.34", -90.0, 90.0)
        self.lat.setToolTip("−90 to 90")
        self.lon = coord_input("e.g. 77.56", -180.0, 180.0)
        self.lon.setToolTip("−180 to 180")
        self.lat.textChanged.connect(self._on_text_changed)
        self.lon.textChanged.connect(self._on_text_changed)

        # Persistent captions so the user can tell latitude from longitude even
        # once both inputs are filled (a placeholder would disappear).
        cap_css = (
            f"color: {COLOR_MUTED}; font-size: 10px; font-weight: 600; background: transparent;"
        )
        lat_cap = QLabel("Lat")
        lat_cap.setStyleSheet(cap_css)
        lon_cap = QLabel("Lon")
        lon_cap.setStyleSheet(cap_css)

        row.addWidget(self.badge)
        row.addWidget(lat_cap)
        row.addWidget(self.lat, 1)
        row.addWidget(lon_cap)
        row.addWidget(self.lon, 1)

        if show_pick:
            self.pick_btn = pick_button()
            self.pick_btn.clicked.connect(self.pick_requested)
            row.addWidget(self.pick_btn)

        self.action_btn = clear_button()
        self.action_btn.clicked.connect(self.action_clicked)
        row.addWidget(self.action_btn)

    def set_badge_text(self, text):
        self.badge.setText(str(text))

    def set_coords(self, lat, lon):
        self.lat.setText(f"{lat:.4f}")
        self.lon.setText(f"{lon:.4f}")

    def _on_text_changed(self):
        # Flag a red border on any non-empty, out-of-range value, then notify.
        for edit in (self.lat, self.lon):
            set_field_error(edit, bool(edit.text().strip()) and not in_range(edit))
        self.changed.emit()

    def get_coords(self):
        """Return (lat, lon) only if both are valid and within range, else None."""
        if not (in_range(self.lat) and in_range(self.lon)):
            return None
        return (float(self.lat.text()), float(self.lon.text()))

    def clear(self):
        self.lat.clear()
        self.lon.clear()
        set_field_error(self.lat, False)
        set_field_error(self.lon, False)
