"""Аккуратный заголовок с inline-редактированием."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.settings import SPACING
from ui.common.qss import set_role


class EditableTitleWidget(QWidget):
    """
    Заголовок с inline-редактированием.

    - По кнопке ✎ переходит в режим редактирования.
    - Enter / потеря фокуса — сохранить.
    - Escape — отменить изменения.
    """

    committed = Signal(str)
    cancelled = Signal()

    def __init__(self, *, placeholder: str = ""):
        super().__init__()
        self._placeholder = placeholder
        self._value: str = ""
        self._editing = False
        self._frozen_height: int | None = None
        self._build_ui()

    def value(self) -> str:
        return self._value

    def set_value(self, value: str | None):
        self._value = (value or "").strip()
        if self._editing:
            self._edit.setText(self._value)
        self._apply_label()

    def set_enabled_editing(self, enabled: bool):
        self._edit_btn.setVisible(enabled)
        self._edit_btn.setEnabled(enabled)

    def setToolTip(self, tip: str):  # type: ignore[override]
        super().setToolTip(tip)
        self._edit.setToolTip(tip)

    def start_edit(self):
        if not self._edit_btn.isEnabled():
            return
        self._freeze_current_height()
        self._editing = True
        self._edit.blockSignals(True)
        self._edit.setText(self._value)
        self._edit.blockSignals(False)
        self._stack.setCurrentIndex(1)
        self._edit.setFocus(Qt.FocusReason.OtherFocusReason)
        self._edit.selectAll()

    def cancel_edit(self):
        if not self._editing:
            return
        self._editing = False
        self._stack.setCurrentIndex(0)
        self._unfreeze_height_later()
        self._apply_label()
        self.cancelled.emit()

    def _on_return_pressed(self):
        self._commit(self._edit.text())

    def _on_editing_finished(self):
        # editingFinished вызывается и при Escape (через потерю фокуса),
        # но Escape мы перехватываем в keyPressEvent у QLineEdit ниже.
        if self._editing:
            self._commit(self._edit.text())

    def _commit(self, new_value: str):
        new_value = (new_value or "").strip()
        if not new_value:
            self.cancel_edit()
            return
        self._value = new_value
        self._editing = False
        self._stack.setCurrentIndex(0)
        self._unfreeze_height_later()
        self._apply_label()
        self.committed.emit(new_value)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root.addWidget(self._stack)

        view = QWidget()
        view_layout = QHBoxLayout(view)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(SPACING)

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        view_layout.addWidget(self._label, 1)

        self._edit_btn = QToolButton()
        self._edit_btn.setText("✏")
        self._edit_btn.setFixedWidth(32)
        self._edit_btn.setToolTip("Переименовать")
        set_role(self._edit_btn, "glyph")
        self._edit_btn.clicked.connect(self.start_edit)
        view_layout.addWidget(self._edit_btn, 0, Qt.AlignmentFlag.AlignTop)

        edit = QWidget()
        edit_layout = QHBoxLayout(edit)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(SPACING)

        self._edit = _EscapeAwareLineEdit()
        self._edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Убираем «странные» внутренние отступы — визуально ближе к заголовку.
        self._edit.setStyleSheet("QLineEdit { padding: 0px; margin: 0px; }")
        self._edit.returnPressed.connect(self._on_return_pressed)
        self._edit.editingFinished.connect(self._on_editing_finished)
        self._edit.escape_pressed.connect(self.cancel_edit)
        edit_layout.addWidget(self._edit, 1)

        self._stack.addWidget(view)
        self._stack.addWidget(edit)

        self._apply_label()

    def _apply_label(self):
        if self._value:
            self._label.setText(self._value)
            set_role(self._label, "heading")
        else:
            self._label.setText(self._placeholder)
            set_role(self._label, "heading-placeholder")

    def _freeze_current_height(self):
        # При переходе в edit-mode фиксируем высоту: иначе QLabel с wordWrap и QLineEdit
        # имеют разные sizeHint, и интерфейс «прыгает» на длинном заголовке.
        if self._frozen_height is not None:
            return
        self._frozen_height = self.height() if self.height() > 0 else self.sizeHint().height()
        self.setMinimumHeight(self._frozen_height)
        self.setMaximumHeight(self._frozen_height)

    def _unfreeze_height_later(self):
        if self._frozen_height is None:
            return

        def _do():
            self._frozen_height = None
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(0)
            self.updateGeometry()

        QTimer.singleShot(0, _do)


class _EscapeAwareLineEdit(QLineEdit):
    """QLineEdit, который отдаёт Escape наружу (не коммитит)."""

    escape_pressed = Signal()

    def keyPressEvent(self, event: QKeyEvent):  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)
