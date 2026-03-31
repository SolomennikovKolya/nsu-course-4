import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from app.context import init_app_context
from ui.main_window import MainWindow


def main():
    init_app_context()            # Инициализация глобального контекста приложения
    app = QApplication(sys.argv)  # Управляет жизненным циклом Qt-приложения

    icon_path = Path("resources/icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()  # Главное окно приложения
    window.show()          # Без этого вызова окно останется скрытым
    sys.exit(app.exec())   # Запускает цикл событий Qt


if __name__ == "__main__":
    main()
