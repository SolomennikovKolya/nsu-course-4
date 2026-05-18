"""Тёмная тема."""

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

# Палитра ориентирована на VS Code «Dark Modern» / тёмный Cursor: фон редактора #1e1e1e и типичные акценты.
_STYLE_DARK_MODERN_LIKE = {
    Token: "#d4d4d4",
    Error: "#f44747",
    Comment: "#6a9955",
    Comment.Single: "#6a9955",
    Comment.Multiline: "#6a9955",
    Comment.Special: "#6a9955",
    Keyword: "#569cd6",
    Keyword.Constant: "#569cd6",
    Keyword.Declaration: "#569cd6",
    Keyword.Namespace: "#c586c0",
    Keyword.Pseudo: "#569cd6",
    Keyword.Type: "#569cd6",
    Name: "#d4d4d4",
    Name.Attribute: "#9cdcfe",
    Name.Builtin: "#569cd6",
    Name.Builtin.Pseudo: "#569cd6",
    Name.Class: "#4ec9b0",
    Name.Decorator: "#dcdcaa",
    Name.Function: "#dcdcaa",
    Name.Exception: "#4ec9b0",
    Name.Namespace: "#4ec9b0",
    Name.Other: "#d4d4d4",
    Name.Tag: "#569cd6",
    Name.Variable: "#9cdcfe",
    Name.Variable.Class: "#4ec9b0",
    Name.Variable.Global: "#9cdcfe",
    Name.Variable.Instance: "#9cdcfe",
    String: "#ce9178",
    String.Affix: "#569cd6",
    String.Char: "#ce9178",
    String.Doc: "#6a9955",
    String.Double: "#ce9178",
    String.Escape: "#d7ba7d",
    String.Interpol: "#9cdcfe",
    String.Single: "#ce9178",
    Number: "#b5cea8",
    Number.Bin: "#b5cea8",
    Number.Float: "#b5cea8",
    Number.Hex: "#b5cea8",
    Number.Integer: "#b5cea8",
    Operator: "#d4d4d4",
    Operator.Word: "#569cd6",
    Punctuation: "#d4d4d4",
}


class DarkModernLikeStyle(Style):
    """Синтаксис Python в духе Dark Modern (VS Code) / тёмной темы Cursor."""

    background_color = "#1e1e1e"
    highlight_color = "#264f78"
    styles = _STYLE_DARK_MODERN_LIKE


class DarkTheme(BaseAppTheme):
    theme_id = "dark"
    display_name = "Тёмная"

    color_status_success = "#4CAF50"
    color_status_warning = "#FFC107"
    color_status_error = "#FF5252"
    color_status_neutral = "#9e9e9e"

    color_window = "#2d2d2d"
    color_panel = "#383838"
    color_panel_inset = "#1e1e1e"
    color_border = "#555555"

    color_text_primary = "#ececec"
    color_text_muted = "#888888"
    color_text_subtle = "#aaaaaa"
    color_text_secondary = "#bbbbbb"
    color_text_dim = "#666666"
    color_text_disabled = "#808080"
    color_title_placeholder = "#8a8a8a"

    color_link_individual = "#90caf9"
    color_link_class = "#ce93d8"

    color_info_accent = "#5a8bd6"
    color_on_error = "#ffffff"
    color_delete_button = "#D32F2F"

    rgba_hint_banner_bg = "rgba(80,140,220,0.12)"
    rgba_subtle_panel_bg = "rgba(255,255,255,0.06)"
    rgba_subtle_panel_border = "rgba(255,255,255,0.10)"
    rgba_build_error_ctx_bg = "rgba(255,255,255,0.06)"
    rgba_build_error_ctx_border = "rgba(255,255,255,0.10)"

    code_plain_message_fg = "#858585"
    code_pygments_style = DarkModernLikeStyle
