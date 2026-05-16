"""Светлая тема."""

from __future__ import annotations

from pygments.style import Style
from pygments.token import (
    Comment,
    Error,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Token,
)

from ui.themes.base import BaseAppTheme

# Светлая палитра (ориентир — VS Code Light+ / светлый редактор).
_STYLE_LIGHT_MODERN_LIKE = {
    Token: "#24292f",
    Error: "#cf222e",
    Comment: "#6a737d",
    Comment.Single: "#6a737d",
    Comment.Multiline: "#6a737d",
    Comment.Special: "#6a737d",
    Keyword: "#0550ae",
    Keyword.Constant: "#0550ae",
    Keyword.Declaration: "#0550ae",
    Keyword.Namespace: "#953800",
    Keyword.Pseudo: "#0550ae",
    Keyword.Type: "#0550ae",
    Name: "#24292f",
    Name.Attribute: "#0a3069",
    Name.Builtin: "#0550ae",
    Name.Builtin.Pseudo: "#0550ae",
    Name.Class: "#116329",
    Name.Decorator: "#953800",
    Name.Function: "#953800",
    Name.Exception: "#116329",
    Name.Namespace: "#116329",
    Name.Other: "#24292f",
    Name.Tag: "#0550ae",
    Name.Variable: "#0a3069",
    Name.Variable.Class: "#116329",
    Name.Variable.Global: "#0a3069",
    Name.Variable.Instance: "#0a3069",
    String: "#0a3069",
    String.Affix: "#0550ae",
    String.Char: "#0a3069",
    String.Doc: "#6a737d",
    String.Double: "#0a3069",
    String.Escape: "#0550ae",
    String.Interpol: "#0a3069",
    String.Single: "#0a3069",
    Number: "#0550ae",
    Number.Bin: "#0550ae",
    Number.Float: "#0550ae",
    Number.Hex: "#0550ae",
    Number.Integer: "#0550ae",
    Operator: "#24292f",
    Operator.Word: "#0550ae",
    Punctuation: "#24292f",
}


class LightModernLikeStyle(Style):
    """Подсветка Python для светлой темы приложения."""

    background_color = "#ffffff"
    highlight_color = "#cce5ff"
    styles = _STYLE_LIGHT_MODERN_LIKE


class LightTheme(BaseAppTheme):
    theme_id = "light"
    display_name = "Светлая"

    color_status_success = "#2e7d32"
    color_status_warning = "#f9a825"
    color_status_error = "#d32f2f"
    color_status_neutral = "#9e9e9e"

    color_window = "#f5f5f5"
    color_panel = "#ffffff"
    color_panel_inset = "#ececec"
    color_border = "#bdbdbd"

    color_text_primary = "#212121"
    color_text_muted = "#616161"
    color_text_subtle = "#757575"
    color_text_secondary = "#424242"
    color_text_dim = "#9e9e9e"
    color_text_disabled = "#9e9e9e"
    color_title_placeholder = "#757575"

    color_link_individual = "#1565c0"
    color_link_class = "#6a1b9a"

    color_info_accent = "#1976d2"
    color_on_error = "#ffffff"
    color_code_pre = "#37474f"
    color_delete_button = "#b71c1c"

    rgba_hint_banner_bg = "rgba(25,118,210,0.10)"
    rgba_subtle_panel_bg = "rgba(0,0,0,0.04)"
    rgba_subtle_panel_border = "rgba(0,0,0,0.12)"
    rgba_build_error_ctx_bg = "rgba(0,0,0,0.03)"
    rgba_build_error_ctx_border = "rgba(0,0,0,0.12)"

    code_plain_message_fg = "#6a737d"
    code_pygments_style = LightModernLikeStyle
