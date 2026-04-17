from PySide6.QtWidgets import QMainWindow, QTabWidget

from ui.documents.main_tab import DocumentsTab
from ui.templates.temps_tab import TemplatesTab


class MainWindow(QMainWindow):
    """Главное окно приложения, содержащее вкладки для управления документами и шаблонами."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Doc2Onto")
        self.resize(900, 600)

        # Вкладки
        self._tabs = QTabWidget()

        self._docs_tab = DocumentsTab()
        self._tabs.addTab(self._docs_tab, "Документы")

        self._temps_tab = TemplatesTab()
        self._tabs.addTab(self._temps_tab, "Шаблоны")

        self.setCentralWidget(self._tabs)

        # Сигналы
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._temps_tab.templates_changed.connect(self._docs_tab.refresh_templates)

    def _on_tab_changed(self, index):
        if self._tabs.widget(index) is self._docs_tab:
            self._docs_tab.refresh_templates()
