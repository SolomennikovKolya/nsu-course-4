import sys

from dotenv import load_dotenv
from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.context import get_theme_manager, init_app_context
from app.settings import ICON_PATH
from ui.main_window import MainWindow


def _install_ru_translator(app: QApplication) -> None:
    """Подключить встроенный русский перевод Qt (Cancel/Yes/No/OK и т.п.)."""
    translator = QTranslator(app)
    qt_translations = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(QLocale("ru_RU"), "qtbase", "_", qt_translations):
        app.installTranslator(translator)


def main():
    load_dotenv()                 # Загрузка переменных среды из .env
    init_app_context()            # Инициализация глобального контекста приложения
    app = QApplication(sys.argv)  # Управляет жизненным циклом Qt-приложения

    _install_ru_translator(app)
    get_theme_manager().attach_application(app)
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    window = MainWindow()  # Главное окно приложения
    window.show()          # Без этого вызова окно останется скрытым
    sys.exit(app.exec())   # Запускает цикл событий Qt


if __name__ == "__main__":
    main()
