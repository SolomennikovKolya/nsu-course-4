from core.uddm import *
from modules.converter.reverse.base import BaseReverseConverter


HTML_TEMPLATE = """
<html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: sans-serif; }}
            table {{ border-collapse: collapse; margin: 10px 0; }}
            td {{ padding: 5px; }}
        </style>
    </head>
    <body>
        {body}
    </body>
</html>
"""


class UDDMToHTML(BaseReverseConverter):

    def convert(self, uddm: UDDM) -> str:
        """Преобразует UDDM в HTML."""
        body = "".join(self._render_block(b) for b in uddm.root)
        return HTML_TEMPLATE.format(body=body)

    def _render_block(self, block: Block) -> str:
        if isinstance(block, Text):
            return "".join(f"<p>{p.text}</p>" for p in block.paragraphs)

        if isinstance(block, ListBlock):
            items = "".join(
                f"<li>{''.join(self._render_block(b) for b in item.blocks)}</li>"
                for item in block.items
            )
            return f"<ul>{items}</ul>"

        if isinstance(block, Table):
            rows_html = ""
            for row in block.rows:
                cells_html = ""
                for cell in row.cells:
                    content = "".join(self._render_block(b) for b in cell.blocks)
                    cells_html += f"<td>{content}</td>"
                rows_html += f"<tr>{cells_html}</tr>"
            return f"<table border='1'>{rows_html}</table>"

        return ""
