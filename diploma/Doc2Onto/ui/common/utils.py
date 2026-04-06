from PySide6.QtWidgets import QMessageBox, QWidget


def show_info_dialog(parent: QWidget, message: str, title: str = " "):
    QMessageBox.information(parent, title, message)


def show_warning_dialog(parent: QWidget, message: str, title: str = " "):
    QMessageBox.warning(parent, title, message)


def show_error_dialog(parent: QWidget, message: str, title: str = " "):
    QMessageBox.critical(parent, title, message)
