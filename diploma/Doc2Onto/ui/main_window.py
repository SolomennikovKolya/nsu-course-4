from ui.tabs.documents.documents_tab import DocumentsTab
from PySide6.QtWidgets import QMainWindow, QTabWidget


class MainWindow(QMainWindow):
    """Главное окно приложения, содержащее вкладки для управления документами и шаблонами."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Doc2Onto")
        self.resize(900, 600)

        tabs = QTabWidget()                       # Виджет - контейнер для вкладок
        tabs.addTab(DocumentsTab(), "Documents")  # Вкладка для управления документами
        tabs.addTab(QTabWidget(), "Templates")    # Вкладка для управления шаблонами (пока пустая)

        self.setCentralWidget(tabs)  # Устанавливает созданный виджет с вкладками в качестве основного содержимого окна
