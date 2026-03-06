from ui.main_window import MainWindow
import sys
from PySide6.QtWidgets import QApplication


def main():
    app = QApplication(sys.argv)  # Управляет жизненным циклом Qt-приложения, включая обработку событий, окна и ресурсы
    window = MainWindow()         # Главное окно приложения
    window.show()                 # Без этого вызова окно останется скрытым
    sys.exit(app.exec())          # Запускает цикл событий Qt


if __name__ == "__main__":
    main()
