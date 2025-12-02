from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from ui.widgets.converter_widget import ConverterWidget


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Knowledge Extraction System")

        central = QWidget()
        layout = QVBoxLayout(central)

        self.converter_widget = ConverterWidget()
        layout.addWidget(self.converter_widget)

        self.setCentralWidget(central)
