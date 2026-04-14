from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer
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


class EditableTitleWidget(QWidget):
    """
    Аккуратный заголовок с inline-редактированием.

    - По кнопке ✎ переходит в режим редактирования.
    - Enter / потеря фокуса — сохранить.
    - Escape — отменить изменения.
    """

    committed = Signal(str)  # новое значение
    cancelled = Signal()

    def __init__(
        self,
        *,
        placeholder: str = "",
        title_style: str = "font-size:16px;font-weight:bold;",
        subdued_style: str = "color:#8a8a8a;",
    ) -> None:
        super().__init__()
        self._placeholder = placeholder
        self._title_style = title_style
        self._subdued_style = subdued_style
        self._value: str = ""
        self._editing = False
        self._frozen_height: Optional[int] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root.addWidget(self._stack)

        # ---- view mode ----
        view = QWidget()
        view_layout = QHBoxLayout(view)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(6)

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        view_layout.addWidget(self._label, 1)

        self._edit_btn = QToolButton()
        self._edit_btn.setText("✎")
        self._edit_btn.setToolTip("Переименовать")
        self._edit_btn.clicked.connect(self.start_edit)
        view_layout.addWidget(self._edit_btn, 0, Qt.AlignmentFlag.AlignTop)

        # ---- edit mode ----
        edit = QWidget()
        edit_layout = QHBoxLayout(edit)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(6)

        self._edit = _EscapeAwareLineEdit()
        self._edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Убираем «странные» внутренние отступы и делаем визуально ближе к заголовку.
        self._edit.setStyleSheet("QLineEdit { padding: 0px; margin: 0px; }")
        self._edit.returnPressed.connect(self._commit_from_editor)
        self._edit.editingFinished.connect(self._commit_from_focus_out)
        self._edit.escape_pressed.connect(self.cancel_edit)
        edit_layout.addWidget(self._edit, 1)

        self._stack.addWidget(view)
        self._stack.addWidget(edit)

        self._apply_label()

    def value(self) -> str:
        return self._value

    def set_value(self, value: Optional[str]) -> None:
        self._value = (value or "").strip()
        if self._editing:
            self._edit.setText(self._value)
        self._apply_label()

    def set_enabled_editing(self, enabled: bool) -> None:
        self._edit_btn.setVisible(enabled)
        self._edit_btn.setEnabled(enabled)

    def start_edit(self) -> None:
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

    def cancel_edit(self) -> None:
        if not self._editing:
            return
        self._editing = False
        self._stack.setCurrentIndex(0)
        self._unfreeze_height_later()
        self._apply_label()
        self.cancelled.emit()

    def _commit_from_editor(self) -> None:
        self._commit(self._edit.text())

    def _commit_from_focus_out(self) -> None:
        # editingFinished вызывается и при Escape (через потерю фокуса),
        # но Escape мы перехватываем в keyPressEvent у QLineEdit ниже.
        if self._editing:
            self._commit(self._edit.text())

    def _commit(self, new_value: str) -> None:
        new_value = (new_value or "").strip()
        if not new_value:
            # пустое имя — просто отмена (визуально мягче, чем ошибка)
            self.cancel_edit()
            return
        self._value = new_value
        self._editing = False
        self._stack.setCurrentIndex(0)
        self._unfreeze_height_later()
        self._apply_label()
        self.committed.emit(new_value)

    def _apply_label(self) -> None:
        if self._value:
            self._label.setText(self._value)
            self._label.setStyleSheet(self._title_style)
        else:
            self._label.setText(self._placeholder)
            self._label.setStyleSheet(f"{self._title_style}{self._subdued_style}")

    def _freeze_current_height(self) -> None:
        """
        При переходе в edit-mode фиксируем высоту виджета, иначе QLabel с wordWrap и QLineEdit
        имеют разные sizeHint (особенно при длинном/многострочном заголовке) и интерфейс «прыгает».
        """
        if self._frozen_height is not None:
            return
        self._frozen_height = self.height() if self.height() > 0 else self.sizeHint().height()
        self.setMinimumHeight(self._frozen_height)
        self.setMaximumHeight(self._frozen_height)

    def _unfreeze_height_later(self) -> None:
        """Снимаем фиксацию высоты после обновления лейаута/переносов текста."""
        if self._frozen_height is None:
            return

        def _do() -> None:
            self._frozen_height = None
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(0)
            self.updateGeometry()

        QTimer.singleShot(0, _do)


class _EscapeAwareLineEdit(QLineEdit):
    """QLineEdit, который отдаёт Escape наружу (не коммитит)."""

    escape_pressed = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)
