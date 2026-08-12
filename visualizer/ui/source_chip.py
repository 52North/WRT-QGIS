"""One loaded file: name, coverage summary, and an unload button."""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout

from ...config_wizard.ui.ui_kit import COLOR_BORDER, COLOR_MUTED, COLOR_TEXT
from .color_palette import MONO_FAMILY
from .spinner import Spinner

_CHIP_QSS = """
QFrame#SourceChip {{
    background: #ffffff;
    border: 1px solid {border};
    border-left: 3px solid {accent};
    border-radius: 5px;
}}
QLabel#ChipName {{ font-size: 11px; font-weight: 600; color: {text}; }}
QLabel#ChipMeta {{ font-family: {mono}; font-size: 10px; color: {muted}; }}
QToolButton#ChipClose {{ border: none; color: {muted}; font-size: 12px; }}
QToolButton#ChipClose:hover {{ color: {text}; }}
"""

_STAMP_FORMAT = "MMM dd HH:mm"


def format_span(bounds):
    """Render a (first, last) QDateTime pair the way the design's chips do."""
    if bounds is None:
        return "no timestamps"
    first, last = bounds
    return f"{first.toString(_STAMP_FORMAT)} → {last.toString(_STAMP_FORMAT)} UTC"


def _chip_qss(accent):
    return _CHIP_QSS.format(
        border=COLOR_BORDER,
        accent=accent,
        text=COLOR_TEXT,
        muted=COLOR_MUTED,
        mono=MONO_FAMILY,
    )


class PendingChip(QFrame):
    """A placeholder for a dataset that is still loading, with a spinner and a message."""

    def __init__(self, filename, accent, message="Opening dataset…", parent=None):
        super().__init__(parent)
        self.setObjectName("SourceChip")
        self.setStyleSheet(_chip_qss(accent))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 7, 7, 7)
        layout.setSpacing(8)
        layout.addWidget(Spinner(accent), 0, Qt.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(1)
        name_label = QLabel(filename)
        name_label.setObjectName("ChipName")
        name_label.setToolTip(filename)
        meta_label = QLabel(message)
        meta_label.setObjectName("ChipMeta")
        text.addWidget(name_label)
        text.addWidget(meta_label)
        layout.addLayout(text, 1)


class SourceChip(QFrame):
    """Emits ``unloaded`` when the user dismisses this dataset."""

    unloaded = pyqtSignal()

    def __init__(self, icon, filename, meta, accent, parent=None):
        super().__init__(parent)
        self.setObjectName("SourceChip")
        self.setStyleSheet(_chip_qss(accent))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 7, 7, 7)
        layout.setSpacing(8)
        layout.addWidget(QLabel(icon), 0, Qt.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(1)
        self._name_label = QLabel(filename)
        self._name_label.setObjectName("ChipName")
        self._name_label.setToolTip(filename)
        self._meta_label = QLabel(meta)
        self._meta_label.setObjectName("ChipMeta")
        text.addWidget(self._name_label)
        text.addWidget(self._meta_label)
        layout.addLayout(text, 1)

        close = QToolButton()
        close.setObjectName("ChipClose")
        close.setText("✕")
        close.setToolTip("Unload this dataset")
        close.clicked.connect(self.unloaded.emit)
        layout.addWidget(close, 0, Qt.AlignTop)

    def set_meta(self, meta):
        self._meta_label.setText(meta)
