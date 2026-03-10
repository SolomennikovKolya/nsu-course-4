from PySide6.QtWidgets import QMainWindow, QTabWidget

from ui.tabs.documents.documents_tab import DocumentsTab
from ui.tabs.templates.templates_tab import TemplatesTab


class MainWindow(QMainWindow):
    """Главное окно приложения, содержащее вкладки для управления документами и шаблонами."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Doc2Onto")
        self.resize(900, 600)

        # Вкладки
        self.tabs = QTabWidget()

        self.documents_tab = DocumentsTab()
        self.tabs.addTab(self.documents_tab, "Документы")

        self.templates_tab = TemplatesTab()
        self.tabs.addTab(self.templates_tab, "Шаблоны")

        self.setCentralWidget(self.tabs)

        # Сигналы
        self.tabs.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        if self.tabs.widget(index) is self.documents_tab:
            self.documents_tab.refresh_templates()
