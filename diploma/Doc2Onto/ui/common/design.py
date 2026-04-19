"""Общие константы оформления UI (тёмная тема)."""

# --- Основные семантические цвета (успех / внимание / ошибка) ---
UI_COLOR_GREEN = "#4CAF50"
UI_COLOR_YELLOW = "#FFC107"
UI_COLOR_RED = "#FF5252"
UI_COLOR_RED_DARK = "#D32F2F"
UI_COLOR_GRAY = "#9e9e9e"

# --- стили кнопок ---
DELETE_BUTTON_STYLE = f"""
QPushButton:hover {{
    background-color: {UI_COLOR_RED_DARK};
    color: white;
}}
"""
