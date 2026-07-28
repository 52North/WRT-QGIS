"""Main QWizard — assembles all 6 pages with sidebar nav and progress bar.

Page order: Route → Algorithm → Boat → Weather & Depth → Constraints → Review.
"""

import copy

from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWizard,
)

from ..core.defaults import DEFAULTS
from ..pages.page1_route import RoutePage
from ..pages.page2_algorithm import AlgorithmPage
from ..pages.page3_boat import BoatPage
from ..pages.page4_weather import WeatherPage
from ..pages.page5_constraints import ConstraintsPage
from ..pages.page6_review import ReviewPage
from .ui_kit import (
    COLOR_BORDER,
    COLOR_GRAY_BADGE,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_PRIMARY_SOFT,
    COLOR_SIDEBAR_BG,
    COLOR_TEXT,
    GLOBAL_QSS,
)


class _StepRow(QFrame):
    """A single clickable navigation step: numbered badge + label."""

    clicked = pyqtSignal(int)

    def __init__(self, index, name, parent=None):
        super().__init__(parent)
        self._index = index
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("StepRow")

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(12)

        self.badge = QLabel(str(index + 1))
        self.badge.setFixedSize(26, 26)
        self.badge.setAlignment(Qt.AlignCenter)

        self.name = QLabel(name)
        self.name.setObjectName("StepName")

        row.addWidget(self.badge)
        row.addWidget(self.name, 1)
        self.set_active(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._index)
        super().mousePressEvent(event)

    def set_active(self, active):
        if active:
            self.setStyleSheet("QFrame#StepRow { background: #ffffff; border-radius: 8px; }")
            self.badge.setStyleSheet(
                f"background: {COLOR_PRIMARY}; color: white; border-radius: 13px;"
                "font-weight: 600; font-size: 12px;"
            )
            self.name.setStyleSheet(
                f"color: {COLOR_PRIMARY}; font-weight: 600; font-size: 13px; background: transparent;"
            )
        else:
            self.setStyleSheet(
                "QFrame#StepRow { background: transparent; border-radius: 8px; }"
                f"QFrame#StepRow:hover {{ background: {COLOR_PRIMARY_SOFT}; }}"
            )
            self.badge.setStyleSheet(
                f"background: {COLOR_GRAY_BADGE}; color: {COLOR_MUTED}; border-radius: 13px;"
                "font-weight: 600; font-size: 12px;"
            )
            self.name.setStyleSheet(
                f"color: {COLOR_MUTED}; font-size: 13px; background: transparent;"
            )


class _StepSidebar(QWidget):
    stepClicked = pyqtSignal(int)

    def __init__(self, steps, parent=None):
        super().__init__(parent)
        self._steps = steps

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 18, 14, 16)
        root.setSpacing(2)

        self.setMinimumWidth(210)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.setStyleSheet(
            f"_StepSidebar {{ background: {COLOR_SIDEBAR_BG}; border-right: 1px solid {COLOR_BORDER}; }}"
            f"QLabel#SidebarTitle {{ color: {COLOR_TEXT}; font-size: 16px; font-weight: 700; padding: 0 6px 14px 6px; }}"
            f"QLabel#SidebarProgressTitle {{ color: {COLOR_MUTED}; font-size: 11px; padding: 0 6px 4px 6px; }}"
            f"QLabel#SidebarProgressValue {{ color: {COLOR_MUTED}; font-size: 11px; padding: 6px 6px 0 6px; }}"
            f"QProgressBar {{ background: #e4e7ec; border: none; border-radius: 3px; height: 6px; }}"
            f"QProgressBar::chunk {{ background: {COLOR_PRIMARY}; border-radius: 3px; }}"
        )

        title = QLabel("WRT Configuration")
        title.setObjectName("SidebarTitle")
        title.setWordWrap(True)
        root.addWidget(title)

        self._rows = []
        for index, name in enumerate(self._steps):
            row = _StepRow(index, name)
            row.clicked.connect(self.stepClicked)
            self._rows.append(row)
            root.addWidget(row)

        root.addStretch(1)

        progress_title = QLabel("Progress")
        progress_title.setObjectName("SidebarProgressTitle")
        root.addWidget(progress_title)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, len(self._steps))
        self.progress.setFixedHeight(6)
        root.addWidget(self.progress)

        self.progress_lbl = QLabel()
        self.progress_lbl.setObjectName("SidebarProgressValue")
        root.addWidget(self.progress_lbl)

    def set_current_step(self, index):
        for i, row in enumerate(self._rows):
            row.set_active(i == index)
        self.progress.setValue(index + 1)
        self.progress_lbl.setText(f"Step {index + 1} of {len(self._steps)}")


class WRTConfigWizard(QWizard):
    def __init__(self, iface, parent=None, sidebar=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self._sidebar = sidebar
        self.config = copy.deepcopy(DEFAULTS)

        self.setWindowTitle("WRT Configuration Wizard")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setStyleSheet(
            "QWizard, QWizardPage { background: #ffffff; }"
            "QWidget#qt_wizard_titlelabel, QWidget#qt_wizard_subtitlelabel { background: #ffffff; }"
            "QPushButton:default:disabled {"
            "  background: #f3f4f6;"
            "  color: #9ca3af;"
            "  border: 1px solid #d1d5db;"
            "  font-weight: normal;"
            "  cursor: forbidden;"
            "}"
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setOption(QWizard.HaveHelpButton, False)
        self.setMinimumSize(740, 620)

        layout = self.layout()
        if layout is not None:
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

        self._page_by_id = {}
        self._page_ids = []
        self._skip_validation = False

        # Build pages
        self.page1 = RoutePage(self.config, self)  # Route
        self.page2 = AlgorithmPage(self.config)  # Algorithm
        self.page3 = BoatPage(self.config)  # Boat
        self.page4 = WeatherPage(self.config)  # Weather & Depth
        self.page5 = ConstraintsPage(self.config)  # Constraints

        data_pages = [self.page1, self.page2, self.page3, self.page4, self.page5]
        self.page6 = ReviewPage(self.config, data_pages)

        self._steps = [
            (self.page1.title(), self.page1),
            (self.page2.title(), self.page2),
            (self.page3.title(), self.page3),
            (self.page4.title(), self.page4),
            (self.page5.title(), self.page5),
            (self.page6.title(), self.page6),
        ]

        for _title, page in self._steps:
            page_id = self.addPage(page)
            self._page_ids.append(page_id)
            self._page_by_id[page_id] = page

        if self._sidebar is not None:
            self._sidebar.stepClicked.connect(self._on_sidebar_step_clicked)

        # Connect page changes to flush saves even when the user jumps steps.
        self.currentIdChanged.connect(self._on_page_changed)
        self._current_page_id = self.currentId()
        self._sync_sidebar()

        # Override button labels
        self.setButtonText(QWizard.NextButton, "Next →")
        self.setButtonText(QWizard.BackButton, "← Back")
        self.setButtonText(QWizard.FinishButton, "Close")
        self.setButtonText(QWizard.CancelButton, "Cancel")

    def _save_page(self, page_id):
        page = self._page_by_id.get(page_id)
        if page is None or not hasattr(page, "save_to_config"):
            return
        try:
            page.save_to_config()
        except Exception as e:
            QgsMessageLog.logMessage(
                f"save_to_config failed for {type(page).__name__}: {e}",
                "Weather Routing Tool",
                Qgis.Warning,
            )

    def _sync_sidebar(self):
        if self._sidebar is None:
            return
        current_id = self.currentId()
        index = self._page_ids.index(current_id) if current_id in self._page_by_id else 0
        self._sidebar.set_current_step(index)

    def _on_sidebar_step_clicked(self, target_index):
        current_id = self.currentId()
        if current_id in self._page_by_id:
            self._save_page(current_id)
        self._jump_to_step(target_index)

    def _jump_to_step(self, target_index):
        current_index = (
            self._page_ids.index(self.currentId()) if self.currentId() in self._page_by_id else 0
        )
        if target_index == current_index:
            return

        step = 1 if target_index > current_index else -1
        self._skip_validation = True
        try:
            guard = len(self._page_ids)
            while current_index != target_index and guard > 0:
                guard -= 1
                self.next() if step > 0 else self.back()
                new_index = (
                    self._page_ids.index(self.currentId())
                    if self.currentId() in self._page_by_id
                    else current_index
                )
                if new_index == current_index:
                    break
                current_index = new_index
        finally:
            self._skip_validation = False

    def _on_page_changed(self, page_id):
        """When navigating away from a data page, persist its values."""
        if self._current_page_id in self._page_by_id:
            self._save_page(self._current_page_id)
        self._current_page_id = page_id
        self._sync_sidebar()

    def validateCurrentPage(self):
        if self._skip_validation:
            return True
        return super().validateCurrentPage()

    AUTOPOPULATED_KEYS = frozenset({"DEPARTURE_TIME", "DEFAULT_MAP", "ROUTE_PATH"})

    def has_changes(self):
        """True if the user has entered anything meaningful beyond the defaults."""
        self._save_page(self.currentId())
        for key, default in DEFAULTS.items():
            if key.startswith("_") or key in self.AUTOPOPULATED_KEYS:
                continue
            if self.config.get(key) != default:
                return True
        return False

    def reject(self):
        """Close the wizard, prompting to discard if there are unsaved changes."""
        window = self.window()
        if window is not None and window is not self:
            window.close()
        else:
            super().reject()


class WRTConfigWindow(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface

        self.setWindowTitle("WRT Configuration Wizard")
        self.setStyleSheet("QDialog { background: #ffffff; }" + GLOBAL_QSS)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(820, 640)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = _StepSidebar(
            [
                "Route",
                "Algorithm",
                "Boat Details",
                "Weather & Depth",
                "Constraints",
                "Review & Export",
            ],
            self,
        )
        self.sidebar.setFixedWidth(250)
        self.sidebar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.wizard = WRTConfigWizard(iface, self, sidebar=self.sidebar)
        self.wizard.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.wizard.setWindowFlags(Qt.Widget)
        self.wizard.accepted.connect(self.accept)
        # Cancel/close is routed through a confirm dialog to avoid accidental loss of user input.

        root.addWidget(self.sidebar)
        root.addWidget(self.wizard, 1)

    def confirm_discard(self):
        """Return True if the wizard may close (nothing entered, or user confirms)."""
        if not self.wizard.has_changes():
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Confirm")
        box.setText(
            "The configuration you've entered will be lost.\n"
            "Are you sure you want to close the wizard?"
        )
        discard_btn = box.addButton("Discard", QMessageBox.DestructiveRole)
        keep_btn = box.addButton("Keep editing", QMessageBox.RejectRole)
        box.setDefaultButton(keep_btn)
        box.exec_()
        return box.clickedButton() is discard_btn

    def reject(self):
        # Escape key and the wizard's Cancel button land here.
        if self.confirm_discard():
            super().reject()

    def closeEvent(self, event):
        # Title-bar close / Alt+F4.
        if self.confirm_discard():
            event.accept()
            QDialog.reject(self)
        else:
            event.ignore()
