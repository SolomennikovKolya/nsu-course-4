from html import escape

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer
from pygments.style import Style
from pygments.styles import get_style_by_name


# Аргумент ``style``: кастомный класс или имя встроенного стиля Pygments (например ``"one-dark"``)
StyleArg = str | type[Style]


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


def python_code_to_preview_html(source: str, *, style: StyleArg) -> str:
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


def plain_message_to_preview_html(
    message: str,
    *,
    style: StyleArg,
    message_color: str = "#858585",
) -> str:
    """Простой текст ошибки/подсказки (без разбора как Python), фон как у превью кода."""
    bg = _style_background(style)
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"/></head>"
        f'<body style="margin:0;padding:6px;font-family:Consolas,\'Courier New\',monospace;'
        f"font-size:10pt;color:{message_color};background-color:{bg};\">"
        f"<pre style=\"margin:0;white-space:pre-wrap;\">{escape(message)}</pre>"
        "</body></html>"
    )
