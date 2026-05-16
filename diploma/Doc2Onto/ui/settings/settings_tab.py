from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.context import get_theme_manager


class SettingsTab(QWidget):
    """Настройки приложения (тема оформления и далее — по мере необходимости)."""

    def __init__(self):
        super().__init__()
        self._tm = get_theme_manager()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        appearance = QGroupBox("Оформление")
        form = QFormLayout(appearance)

        self._theme_combo = QComboBox()
        for tid, title in self._tm.available_themes():
            self._theme_combo.addItem(title, tid)
        self._sync_combo()

        self._theme_combo.currentIndexChanged.connect(self._on_theme_combo_changed)
        form.addRow(QLabel("Тема интерфейса:"), self._theme_combo)

        root.addWidget(appearance)
        root.addStretch(1)

    def _sync_combo(self):
        tid = self._tm.theme_id
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == tid:
                self._theme_combo.blockSignals(True)
                self._theme_combo.setCurrentIndex(i)
                self._theme_combo.blockSignals(False)
                return

    def _on_theme_combo_changed(self, _index: int):
        tid = self._theme_combo.currentData()
        if not isinstance(tid, str):
            return
        self._tm.set_theme_id(tid, persist=True)

    def apply_external_theme_change(self):
        """Синхронизировать комбобокс, если тему сменили извне (на будущее)."""
        self._sync_combo()
