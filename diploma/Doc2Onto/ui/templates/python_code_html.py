from html import escape

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer
from pygments.style import Style
from pygments.styles import get_style_by_name
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


# Аргумент ``style``: кастомный класс или имя встроенного стиля Pygments (например ``"one-dark"``).
StyleArg = str | type[Style]

_DEFAULT_STYLE: type[Style] = DarkModernLikeStyle


def _style_background(style: StyleArg) -> str:
    if isinstance(style, str):
        try:
            s = get_style_by_name(style)
            if getattr(s, "background_color", None):
                return s.background_color
        except Exception:
            pass
        return "#1e1e1e"
    return getattr(style, "background_color", None) or "#1e1e1e"


def _preview_css(style: StyleArg) -> str:
    """Фон страницы = фону стиля; плотный межстрочный интервал без «щелей» между span."""
    bg = _style_background(style)
    return f"""
html, body {{
  margin: 0;
  padding: 6px;
  background-color: {bg};
}}
div.highlight {{
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
}}
div.highlight pre {{
  margin: 0 !important;
  padding: 0 !important;
  border: none !important;
  line-height: 1.05;
  white-space: pre-wrap;
  word-wrap: break-word;
}}
div.highlight pre span {{
  background-color: transparent !important;
}}
"""


def python_code_to_preview_html(source: str, *, style: StyleArg = _DEFAULT_STYLE) -> str:
    """Полный HTML-документ для ``QTextBrowser``: подсветка синтаксиса Python."""
    fragment = highlight(
        source,
        PythonLexer(),
        HtmlFormatter(
            style=style,
            noclasses=True,
            nowrap=False,
            nobackground=True,
        ),
    )
    css = _preview_css(style)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>{css}</style>
</head>
<body>
{fragment}
</body>
</html>"""


def plain_message_to_preview_html(message: str) -> str:
    """Простой текст ошибки/подсказки (без разбора как Python), фон как у превью кода."""
    bg = _style_background(_DEFAULT_STYLE)
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"/></head>"
        f'<body style="margin:0;padding:6px;font-family:Consolas,\'Courier New\',monospace;'
        f'font-size:10pt;color:#858585;background-color:{bg};">'
        f"<pre style=\"margin:0;white-space:pre-wrap;\">{escape(message)}</pre>"
        "</body></html>"
    )
