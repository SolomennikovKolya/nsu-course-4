from PySide6.QtWidgets import QMainWindow, QTabWidget

from ui.tabs.documents.documents_tab import DocumentsTab
from ui.tabs.templates.templates_tab import TemplatesTab


class MainWindow(QMainWindow):
    """Главное окно приложения, содержащее вкладки для управления документами и шаблонами."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Doc2Onto")
        self.resize(900, 600)

        tabs = QTabWidget()                       # Контейнер для вкладок
        tabs.addTab(DocumentsTab(), "Документы")  # Вкладка для управления документами
        tabs.addTab(TemplatesTab(), "Шаблоны")    # Вкладка для управления шаблонами

        self.setCentralWidget(tabs)  # Устанавливает созданный виджет с вкладками в качестве основного содержимого окна
