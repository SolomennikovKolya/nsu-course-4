"""Базовая тема оформления: токены и вспомогательные стили для Qt и HTML."""

from __future__ import annotations

from pygments.style import Style


class BaseAppTheme:
    """
    Набор токенов UI. Конкретные темы — подклассы с заданными на уровне класса
    строковыми константами (цвета в формате #rrggbb или rgba(...)).
    """

    theme_id: str = ""
    display_name: str = ""

    color_status_success: str = ""
    color_status_warning: str = ""
    color_status_error: str = ""
    color_status_neutral: str = ""

    color_window: str = ""
    color_panel: str = ""
    color_panel_inset: str = ""
    color_border: str = ""

    color_text_primary: str = ""
    color_text_muted: str = ""
    color_text_subtle: str = ""
    color_text_secondary: str = ""
    color_text_dim: str = ""
    color_text_disabled: str = ""
    color_title_placeholder: str = ""

    color_link_individual: str = ""
    color_link_class: str = ""

    color_accent: str = ""          # фокус инпутов, индикатор активной вкладки, hover сплиттера
    color_panel_hover: str = ""     # hover у кнопок / неактивных вкладок
    color_panel_pressed: str = ""   # pressed у кнопок
    color_selection_bg: str = ""    # подсветка выделенной строки в tree/list/table

    color_info_accent: str = ""
    color_on_error: str = ""
    color_delete_button: str = ""

    rgba_hint_banner_bg: str = ""
    rgba_subtle_panel_bg: str = ""
    rgba_subtle_panel_border: str = ""
    rgba_build_error_ctx_bg: str = ""
    rgba_build_error_ctx_border: str = ""

    code_plain_message_fg: str = ""
    code_pygments_style: type[Style]

    def color_for_item_kind(self, kind: str) -> str | None:
        """Цвет foreground для элементов QTreeWidget/QTableWidget по семантической роли.

        Используется ``ThemedItemDelegate`` (``ui.common.item_delegate``).
        ``None`` означает «не переопределять — взять цвет темы по умолчанию».
        """
        return {
            # Ссылки на узлы онтологии
            "link_individual": self.color_link_individual,
            "link_class": self.color_link_class,
            # Уровни (success/warning/error/neutral)
            "severity_success": self.color_status_success,
            "severity_warning": self.color_status_warning,
            "severity_error": self.color_status_error,
            "severity_neutral": self.color_status_neutral,
            # Тон
            "subtle": self.color_text_subtle,
            "muted": self.color_text_muted,
            "dim": self.color_text_dim,
        }.get(kind)

    def global_application_stylesheet(self) -> str:
        """Глобальная таблица стилей для QApplication.

        Помимо базового оформления виджетов содержит property-селекторы для
        семантической раскраски лейблов (см. ``ui/common/qss.py``):
            QLabel[role="muted"], QLabel[role="subtle"], QLabel[role="placeholder"],
            QLabel[role="monospace"], QLabel[role="title"],
            QLabel[severity="success" | "warning" | "error" | "neutral" | "disabled"].
        """
        return f"""
QMainWindow, QWidget {{
    background-color: {self.color_window};
    color: {self.color_text_primary};
}}

/* --- Вкладки: flat, с accent-индикатором снизу. Ширина не меняется при выделении. --- */
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {self.color_border};
    background: {self.color_window};
}}
QTabBar {{
    qproperty-drawBase: 0;
}}
QTabBar::tab {{
    background: transparent;
    color: {self.color_text_muted};
    padding: 9px 18px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
    min-width: 80px;
}}
QTabBar::tab:hover:!selected {{
    color: {self.color_text_primary};
    background: {self.color_panel_hover};
}}
QTabBar::tab:selected {{
    color: {self.color_text_primary};
    border-bottom: 2px solid {self.color_accent};
}}

/* --- Списки/деревья/таблицы --- */
QTreeWidget, QListWidget, QTableWidget {{
    background-color: {self.color_panel_inset};
    color: {self.color_text_primary};
    alternate-background-color: {self.color_panel};
    border: 1px solid {self.color_border};
    border-radius: 4px;
    outline: 0;
}}
QTreeView::item, QListView::item, QTableView::item {{
    padding: 4px 6px;
}}
QTreeView::item:hover, QListView::item:hover, QTableView::item:hover {{
    background: {self.color_panel_hover};
}}
QTreeView::item:selected, QListView::item:selected, QTableView::item:selected,
QTreeView::item:selected:active, QListView::item:selected:active, QTableView::item:selected:active {{
    background: {self.color_selection_bg};
    color: {self.color_text_primary};
}}
QHeaderView::section {{
    background-color: {self.color_panel};
    color: {self.color_text_primary};
    padding: 5px 8px;
    border: none;
    border-right: 1px solid {self.color_border};
    border-bottom: 1px solid {self.color_border};
}}

/* --- Поля ввода: фокус выделяется accent-границей --- */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
    background-color: {self.color_panel_inset};
    color: {self.color_text_primary};
    border: 1px solid {self.color_border};
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: {self.color_selection_bg};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {self.color_accent};
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled {{
    color: {self.color_text_disabled};
    background-color: {self.color_panel};
}}

/* --- Кнопки: hover/pressed/disabled --- */
QPushButton, QToolButton {{
    background-color: {self.color_panel};
    color: {self.color_text_primary};
    border: 1px solid {self.color_border};
    border-radius: 4px;
    padding: 6px 14px;
}}
QPushButton:hover, QToolButton:hover {{
    background-color: {self.color_panel_hover};
    border-color: {self.color_accent};
}}
QPushButton:pressed, QToolButton:pressed {{
    background-color: {self.color_panel_pressed};
}}
QPushButton:disabled, QToolButton:disabled {{
    color: {self.color_text_disabled};
    background-color: {self.color_panel};
    border-color: {self.color_border};
}}
QPushButton[role="delete"]:hover {{
    background-color: {self.color_delete_button};
    border-color: {self.color_delete_button};
    color: {self.color_on_error};
}}

/* --- Глиф-кнопки (✎, ⚙ и т.п.): крупнее и с предсказуемым шрифтом --- */
QToolButton[role="glyph"], QPushButton[role="glyph"] {{
    font-family: "Segoe UI Symbol", "DejaVu Sans", sans-serif;
    font-size: 15px;
    padding: 4px 8px;
}}

/* --- Сплиттер: тонкая полоска, на hover — accent --- */
QSplitter::handle {{
    background: {self.color_border};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}
QSplitter::handle:hover {{
    background: {self.color_accent};
}}

/* --- QGroupBox: видимая рамка + заголовок поверх рамки --- */
QGroupBox {{
    border: 1px solid {self.color_border};
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px;
    padding-top: 14px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    background: {self.color_window};
    color: {self.color_text_primary};
}}

/* --- Прочее --- */
QScrollArea {{
    border: none;
    background: transparent;
}}
QToolTip {{
    background-color: {self.color_panel_inset};
    color: {self.color_text_primary};
    border: 1px solid {self.color_border};
    padding: 4px 6px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {self.color_border};
    border-radius: 3px;
    min-height: 24px;
    min-width: 24px;
}}
QScrollBar::handle:hover {{
    background: {self.color_text_muted};
}}
QScrollBar::add-line, QScrollBar::sub-line {{ background: none; border: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

/* --- семантические лейблы (выставляются через ui.common.qss.set_role/set_severity) --- */
QLabel[role="muted"]              {{ color: {self.color_text_muted}; }}
QLabel[role="subtle"]             {{ color: {self.color_text_subtle}; }}
QLabel[role="secondary"]          {{ color: {self.color_text_secondary}; }}
QLabel[role="dim"]                {{ color: {self.color_text_dim}; }}
QLabel[role="placeholder"]        {{ color: {self.color_title_placeholder}; }}
QLabel[role="title"]              {{ font-size: 18px; font-weight: bold; }}
QLabel[role="heading"]            {{ font-size: 16px; font-weight: bold; }}
QLabel[role="heading-placeholder"]{{ font-size: 16px; font-weight: bold; color: {self.color_title_placeholder}; }}
QLabel[role="monospace"], QTextEdit[role="monospace"], QPlainTextEdit[role="monospace"] {{
    font-family: monospace;
}}
QLabel[role="iri"]                {{ font-family: monospace; color: {self.color_text_muted}; }}

QLabel[severity="success"]  {{ color: {self.color_status_success}; font-weight: bold; }}
QLabel[severity="warning"]  {{ color: {self.color_status_warning}; font-weight: bold; }}
QLabel[severity="error"]    {{ color: {self.color_status_error}; font-weight: bold; }}
QLabel[severity="neutral"]  {{ color: {self.color_status_neutral}; }}
QLabel[severity="disabled"] {{ color: {self.color_text_disabled}; }}

/* --- блочные стили (баннеры, информационные панели, контейнеры ошибок) --- */
QLabel[role="info-banner"], QFrame[role="info-banner"] {{
    padding: 8px 10px;
    background: {self.rgba_hint_banner_bg};
    border-left: 3px solid {self.color_info_accent};
    border-radius: 2px;
    color: {self.color_text_secondary};
}}
QLabel[role="subtle-panel"], QFrame[role="subtle-panel"], QTextEdit[role="subtle-panel"], QPlainTextEdit[role="subtle-panel"] {{
    padding: 10px 12px;
    background: {self.rgba_subtle_panel_bg};
    border: 1px solid {self.rgba_subtle_panel_border};
    border-radius: 3px;
    color: {self.color_text_secondary};
}}
QLabel[role="pipeline-info"] {{
    padding: 4px 8px;
    background: {self.rgba_subtle_panel_bg};
    border: 1px solid {self.rgba_subtle_panel_border};
    border-radius: 3px;
    color: {self.color_text_secondary};
    font-size: 11px;
}}
QFrame[role="error-context"] {{
    padding: 6px;
    background: {self.rgba_build_error_ctx_bg};
    border: 1px solid {self.rgba_build_error_ctx_border};
    border-radius: 3px;
}}
QLabel[role="error-header"] {{
    background: {self.color_status_error};
    color: {self.color_on_error};
    padding: 8px;
    border-radius: 4px;
}}
QFrame[role="error-banner"], QLabel[role="error-banner"] {{
    background: {self.color_status_error};
    color: {self.color_on_error};
    padding: 6px 10px;
}}

/* --- акцентные/прочие лейблы --- */
QLabel[role="override-badge"] {{ color: {self.color_link_individual}; font-weight: bold; font-size: 10px; }}
QLabel[role="bold"]           {{ font-weight: bold; }}
QLabel[role="bold-medium"]    {{ font-weight: bold; font-size: 13px; }}
QLabel[role="muted-italic"]   {{ color: {self.color_text_muted}; font-style: italic; }}
QLabel[role="secondary-soft"] {{ color: {self.color_text_secondary}; }}

/* --- цветные стрипы (вертикальный индикатор слева у строки) --- */
QFrame[role="stripe"]                       {{ border-radius: 1px; background-color: transparent; }}
QFrame[role="stripe"][severity="success"]   {{ background-color: {self.color_status_success}; }}
QFrame[role="stripe"][severity="warning"]   {{ background-color: {self.color_status_warning}; }}
QFrame[role="stripe"][severity="error"]     {{ background-color: {self.color_status_error}; }}
QFrame[role="stripe"][severity="neutral"]   {{ background-color: {self.color_status_neutral}; }}
QFrame[role="stripe"][severity="link"]      {{ background-color: {self.color_link_individual}; }}

/* --- сам триплет в списке: «выключенное» состояние --- */
QFrame[role="triple-item"][muted="true"] {{
    background: {self.color_panel_inset};
    color: {self.color_text_muted};
}}
"""
