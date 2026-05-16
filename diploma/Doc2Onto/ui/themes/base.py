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

    def delete_button_style(self) -> str:
        return (
            "QPushButton:hover { "
            f"background-color: {self.color_delete_button}; "
            f"color: {self.color_on_error}; "
            "}"
        )

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
        return (
            f"background:{self.color_status_error}; color:{self.color_on_error}; padding:6px 10px;"
        )

    def global_application_stylesheet(self) -> str:
        """Глобальная таблица стилей для QApplication."""
        w, p, pi = self.color_window, self.color_panel, self.color_panel_inset
        b = self.color_border
        t = self.color_text_primary
        tm = self.color_text_muted
        return f"""
QMainWindow, QWidget {{
    background-color: {w};
    color: {t};
}}
QTabWidget::pane {{
    border: 1px solid {b};
    background: {w};
}}
QTabBar::tab {{
    background: {p};
    color: {t};
    padding: 6px 14px;
    border: 1px solid {b};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {w};
    font-weight: bold;
}}
QTabBar::tab:!selected {{
    color: {tm};
}}
QTreeWidget, QListWidget, QTableWidget {{
    background-color: {pi};
    color: {t};
    alternate-background-color: {p};
    border: 1px solid {b};
    border-radius: 2px;
}}
QHeaderView::section {{
    background-color: {p};
    color: {t};
    padding: 4px;
    border: 1px solid {b};
}}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
    background-color: {pi};
    color: {t};
    border: 1px solid {b};
    border-radius: 2px;
    padding: 4px;
}}
QPushButton {{
    background-color: {p};
    color: {t};
    border: 1px solid {b};
    border-radius: 3px;
    padding: 5px 12px;
}}
QPushButton:disabled {{
    color: {self.color_text_disabled};
}}
QSplitter::handle {{
    background: {b};
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QToolTip {{
    background-color: {pi};
    color: {t};
    border: 1px solid {b};
}}
"""
