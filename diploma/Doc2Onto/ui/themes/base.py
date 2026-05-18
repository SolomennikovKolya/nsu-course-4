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
QTabWidget::pane {{
    border: 1px solid {self.color_border};
    background: {self.color_window};
}}
QTabBar::tab {{
    background: {self.color_panel};
    color: {self.color_text_primary};
    padding: 6px 14px;
    border: 1px solid {self.color_border};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {self.color_window};
    font-weight: bold;
}}
QTabBar::tab:!selected {{
    color: {self.color_text_muted};
}}
QTreeWidget, QListWidget, QTableWidget {{
    background-color: {self.color_panel_inset};
    color: {self.color_text_primary};
    alternate-background-color: {self.color_panel};
    border: 1px solid {self.color_border};
    border-radius: 2px;
}}
QHeaderView::section {{
    background-color: {self.color_panel};
    color: {self.color_text_primary};
    padding: 4px;
    border: 1px solid {self.color_border};
}}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
    background-color: {self.color_panel_inset};
    color: {self.color_text_primary};
    border: 1px solid {self.color_border};
    border-radius: 2px;
    padding: 4px;
}}
QPushButton {{
    background-color: {self.color_panel};
    color: {self.color_text_primary};
    border: 1px solid {self.color_border};
    border-radius: 3px;
    padding: 5px 12px;
}}
QPushButton:disabled {{
    color: {self.color_text_disabled};
}}
QPushButton[role="delete"]:hover {{
    background-color: {self.color_delete_button};
    color: {self.color_on_error};
}}
QSplitter::handle {{
    background: {self.color_border};
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QToolTip {{
    background-color: {self.color_panel_inset};
    color: {self.color_text_primary};
    border: 1px solid {self.color_border};
}}

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
