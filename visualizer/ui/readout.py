"""The two "Current parameters" cards: vessel state and weather at the vessel."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...config_wizard.ui.ui_kit import COLOR_BORDER, COLOR_MUTED, COLOR_TEXT
from .color_palette import MONO_FAMILY

SEPARATOR = "—separator—"

EMPTY = "—"

_CARD_QSS = """
QFrame#StatCard {{
    background: #ffffff;
    border: 1px solid {border};
    border-radius: 6px;
}}
QWidget#StatHeader {{
    background: {tint};
    border-bottom: 1px solid {tint_border};
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QLabel#StatTitle {{ font-size: 10px; font-weight: 600; color: {accent}; }}
QLabel#StatKey {{ font-size: 11px; color: {muted}; }}
QLabel#StatValue {{ font-family: {mono}; font-size: 11px; font-weight: 600;
                    color: {text}; }}
"""


def format_value(value, unit="", digits=4):
    """Render a measurement, or an em dash when it is missing."""
    if value is None:
        return EMPTY
    return f"{value:.{digits}g} {unit}".strip()


class _Row(QWidget):
    """A key/value line that can also render as a separator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._key = QLabel()
        self._key.setObjectName("StatKey")
        self._value = QLabel()
        self._value.setObjectName("StatValue")
        self._value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._line = QFrame()
        self._line.setFrameShape(QFrame.HLine)
        self._line.setFrameShadow(QFrame.Plain)
        self._line.setFixedHeight(1)

        layout.addWidget(self._key)
        layout.addStretch()
        layout.addWidget(self._value)
        layout.addWidget(self._line, 1)

    def show_pair(self, key, value):
        self._line.setVisible(False)
        self._key.setVisible(True)
        self._value.setVisible(True)
        self._key.setText(key)
        self._value.setText(value)

    def show_separator(self):
        self._key.setVisible(False)
        self._value.setVisible(False)
        self._line.setVisible(True)


class StatCard(QFrame):
    """A tinted-header card whose rows are rebuilt on every clock tick."""

    def __init__(self, title, accent, tint, tint_border, parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setStyleSheet(
            _CARD_QSS.format(
                border=COLOR_BORDER,
                tint=tint,
                tint_border=tint_border,
                accent=accent,
                muted=COLOR_MUTED,
                text=COLOR_TEXT,
                mono=MONO_FAMILY,
            )
        )
        self._rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("StatHeader")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(9, 6, 9, 6)
        header_row.setSpacing(6)

        dot = QLabel()
        dot.setFixedSize(7, 7)
        dot.setStyleSheet(f"background: {accent}; border-radius: 3px;")
        header_row.addWidget(dot)

        self._title = QLabel(title)
        self._title.setObjectName("StatTitle")
        header_row.addWidget(self._title, 1)
        layout.addWidget(header)

        body = QWidget()
        self._body = QVBoxLayout(body)
        self._body.setContentsMargins(9, 8, 9, 8)
        self._body.setSpacing(5)
        layout.addWidget(body)

    def set_title(self, title):
        self._title.setText(title)

    def set_rows(self, rows):
        """Show ``rows`` — (key, value) pairs, or SEPARATOR — reusing widgets."""
        while len(self._rows) < len(rows):
            row = _Row()
            self._rows.append(row)
            self._body.addWidget(row)

        for row, spec in zip(self._rows, rows, strict=False):
            row.setVisible(True)
            if spec is SEPARATOR:
                row.show_separator()
            else:
                row.show_pair(*spec)

        for row in self._rows[len(rows) :]:
            row.setVisible(False)
