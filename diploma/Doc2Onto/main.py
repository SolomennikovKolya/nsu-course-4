import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)  # Управляет жизненным циклом Qt-приложения, включая обработку событий, окна и ресурсы

    icon_path = Path("resources/icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()         # Главное окно приложения
    window.show()                 # Без этого вызова окно останется скрытым
    sys.exit(app.exec())          # Запускает цикл событий Qt


if __name__ == "__main__":
    main()
