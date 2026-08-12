"""Page validation — pages check their input when Next is pressed."""

from collections import namedtuple

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QAbstractSpinBox,
    QLineEdit,
    QScrollArea,
    QWizardPage,
)

from .ui_kit import set_field_error

FieldError = namedtuple("FieldError", "message widget")
FieldError.__new__.__defaults__ = (None,)


def _change_signal(widget):
    """The signal that says the user has started fixing this widget, if any."""
    if isinstance(widget, QLineEdit):
        return widget.textChanged
    if isinstance(widget, QAbstractSpinBox):
        return getattr(widget, "valueChanged", None)
    return None


class ValidatedPage(QWizardPage):
    """A wizard page that checks its input when Next is pressed.

    Override :meth:`validation_errors` to return a list of :class:`FieldError`;
    an empty list lets the wizard advance. On failure the page stays put, marks
    every offending field, lists the problems in its status line and jumps to
    the first one.

    Override :meth:`_update_status` for what the status line says when there is
    nothing wrong; the default is :attr:`STATUS_HINT`.
    """

    STATUS_HINT = "Fill in the required fields, then press Next"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._flagged = []  # (widget, signal, slot) for the marks currently painted
        self.status = None  # the page's StatusLine, once _build_ui has made one

    # Validation
    def validation_errors(self):
        """Problems that must be fixed before leaving this page. Pages override."""
        return []

    def validatePage(self):
        """QWizard's Next hook — the one and only place this page is checked."""
        errors = list(self.validation_errors())
        self.clear_errors()
        if not errors:
            self._update_status()
            return True
        self._show_errors(errors)
        return False

    def _show_errors(self, errors):
        if self.status is not None:
            self.status.set_error(" · ".join(error.message for error in errors))
        for error in errors:
            if error.widget is not None:
                self._flag(error.widget)
        first = next((error.widget for error in errors if error.widget is not None), None)
        if first is not None:
            self._reveal(first)
            first.setFocus(Qt.OtherFocusReason)

    def _update_status(self):
        """Status text shown when nothing is wrong. Pages with their own override this."""
        if self.status is not None:
            self.status.set_pending(self.STATUS_HINT)

    # Error marks
    def _flag(self, widget):
        """Mark a widget, and drop the mark as soon as the user edits it."""
        set_field_error(widget, True)
        signal = _change_signal(widget)
        if signal is None:
            self._flagged.append((widget, None, None))
            return

        def clear(*_args):
            self._unflag(widget)

        signal.connect(clear)
        self._flagged.append((widget, signal, clear))

    def _unflag(self, widget):
        for entry in [e for e in self._flagged if e[0] is widget]:
            set_field_error(widget, False)
            if entry[1] is not None:
                entry[1].disconnect(entry[2])
            self._flagged.remove(entry)
        if not self._flagged:
            # Last mark gone — the red summary would be describing nothing.
            self._update_status()

    def clear_errors(self):
        for widget, _signal, _slot in list(self._flagged):
            self._unflag(widget)

    # Getting the offending field in front of the user
    def _reveal(self, widget):
        """Expand whatever hides `widget`, then scroll it into view."""
        node = widget.parentWidget()
        while node is not None and node is not self:
            if not node.isVisible():
                # collapsible() and the Route page's advanced block hang a
                # set_expanded() on the container so the toggle arrow follows.
                expand = getattr(node, "set_expanded", None)
                if expand is not None:
                    expand(True)
                else:
                    node.setVisible(True)
            node = node.parentWidget()

        scroll = self.findChild(QScrollArea)
        if scroll is not None:
            # Deferred: an expanded section has no geometry until the layout runs.
            QTimer.singleShot(0, lambda: scroll.ensureWidgetVisible(widget, 50, 50))
