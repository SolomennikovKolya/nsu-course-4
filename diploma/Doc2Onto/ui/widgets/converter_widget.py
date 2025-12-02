from PyQt6.QtWidgets import QWidget, QPushButton, QFileDialog, QVBoxLayout, QLabel
from modules.converter.converter import Converter


class ConverterWidget(QWidget):

    def __init__(self):
        super().__init__()

        self.converter = Converter()

        self.label = QLabel("Выберите документ для конвертации")
        self.button = QPushButton("Открыть файл")
        self.button.clicked.connect(self.open_file)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        self.setLayout(layout)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите документ",
            "",
            "Документы (*.pdf *.docx *.doc *.odt *.png *.jpg *.jpeg)"
        )
        if not path:
            return

        output = self.converter.process(path)
        self.label.setText(f"Конвертировано: {output}")
