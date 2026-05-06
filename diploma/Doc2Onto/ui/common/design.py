"""Общие константы оформления UI (тёмная тема)."""

# --- Основные семантические цвета (успех / внимание / ошибка) ---
UI_COLOR_GREEN = "#4CAF50"
UI_COLOR_YELLOW = "#FFC107"
UI_COLOR_RED = "#FF5252"
UI_COLOR_RED_DARK = "#D32F2F"
UI_COLOR_GRAY = "#9e9e9e"

# --- Тектовые и ссылочные цвета ---
UI_COLOR_TEXT_MUTED = "#888"
UI_COLOR_TEXT_SUBTLE = "#aaa"
UI_COLOR_TEXT_SECONDARY = "#bbb"
UI_COLOR_TEXT_DIM = "#666"
UI_COLOR_LINK_INDIVIDUAL = "#90caf9"
UI_COLOR_LINK_CLASS = "#ce93d8"

# --- стили кнопок ---
DELETE_BUTTON_STYLE = f"""
QPushButton:hover {{
    background-color: {UI_COLOR_RED_DARK};
    color: white;
}}
"""

# --- размеры ---
MAIN_WINDOW_W = 1200
MAIN_WINDOW_H = 800
MIN_LEFT_PANEL_WIDTH = 300
SPLITTER_RATIO_SIZES = [400, 900]
