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
    color_code_pre: str = ""
    color_delete_button: str = ""

    rgba_hint_banner_bg: str = ""
    rgba_subtle_panel_bg: str = ""
    rgba_subtle_panel_border: str = ""
    rgba_build_error_ctx_bg: str = ""
    rgba_build_error_ctx_border: str = ""

    code_plain_message_fg: str = ""
    code_pygments_style: type[Style]

    def color_for_severity_level(self, level: int) -> str:
        """Уровень предупреждения в UI: 0 — ок, 1 — внимание, 2+ — ошибка."""
        if level <= 0:
            return self.color_status_success
        if level == 1:
            return self.color_status_warning
        return self.color_status_error

    def color_for_doc_tree_kind(self, kind: str) -> str:
        """Тон строки в дереве документов (см. ``DocumentTreeKind``)."""
        if kind == "folder":
            return self.color_text_subtle
        if kind == "doc_complete":
            return self.color_status_success
        if kind == "doc_in_progress":
            return self.color_status_warning
        return self.color_text_primary

    def style_generator_header(self) -> str:
        return (
            "padding:8px 10px; "
            f"background:{self.rgba_hint_banner_bg}; "
            f"border-left:3px solid {self.color_info_accent}; "
            "border-radius:2px; "
            f"color:{self.color_text_secondary};"
        )

    def style_monospace_preview_panel(self) -> str:
        return (
            "padding:10px 12px; "
            f"background:{self.rgba_subtle_panel_bg}; "
            f"border:1px solid {self.rgba_subtle_panel_border}; "
            "border-radius:3px; "
            f"color:{self.color_text_secondary};"
        )

    def style_pipeline_widget(self) -> str:
        return (
            "padding:4px 8px; "
            f"background:{self.rgba_subtle_panel_bg}; "
            f"border:1px solid {self.rgba_subtle_panel_border}; "
            "border-radius:3px; "
            f"color:{self.color_text_secondary}; "
            "font-size:11px;"
        )

    def style_build_error_context_box(self) -> str:
        return (
            "padding:6px; "
            f"background:{self.rgba_build_error_ctx_bg}; "
            f"border:1px solid {self.rgba_build_error_ctx_border}; border-radius:3px;"
        )

    def style_build_error_header(self) -> str:
        return (
            f"background:{self.color_status_error}; color:{self.color_on_error}; "
            "padding:8px; border-radius:4px;"
        )

    def style_graph_error_banner(self) -> str:
        return f"background:{self.color_status_error}; color:{self.color_on_error}; padding:6px 10px;"

    def html_colored(self, text: str, color: str) -> str:
        """Обёрнуть текст в ``<span>`` с цветом темы."""
        return f'<span style="color:{color}">{text}</span>'

    def html_error(self, text: str) -> str:
        return self.html_colored(text, self.color_status_error)

    def html_warning(self, text: str) -> str:
        return self.html_colored(text, self.color_status_warning)

    def html_muted(self, text: str) -> str:
        return self.html_colored(text, self.color_text_muted)

    def html_subtle(self, text: str) -> str:
        return self.html_colored(text, self.color_text_subtle)

    def html_link_individual(self, text: str) -> str:
        return self.html_colored(text, self.color_link_individual)

    def html_link_class(self, text: str) -> str:
        return self.html_colored(text, self.color_link_class)

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
QLabel[role="monospace"]          {{ font-family: monospace; color: {self.color_text_muted}; }}

QLabel[severity="success"]  {{ color: {self.color_status_success}; font-weight: bold; }}
QLabel[severity="warning"]  {{ color: {self.color_status_warning}; font-weight: bold; }}
QLabel[severity="error"]    {{ color: {self.color_status_error}; font-weight: bold; }}
QLabel[severity="neutral"]  {{ color: {self.color_status_neutral}; }}
QLabel[severity="disabled"] {{ color: {self.color_text_disabled}; }}
"""
