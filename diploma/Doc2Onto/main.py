import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from dotenv import load_dotenv

from app.settings import ICON_PATH
from app.context import init_app_context
from ui.main_window import MainWindow


def main():
    load_dotenv()                 # Загрузка переменных среды из .env
    init_app_context()            # Инициализация глобального контекста приложения
    app = QApplication(sys.argv)  # Управляет жизненным циклом Qt-приложения

    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    window = MainWindow()  # Главное окно приложения
    window.show()          # Без этого вызова окно останется скрытым
    sys.exit(app.exec())   # Запускает цикл событий Qt


if __name__ == "__main__":
    main()
