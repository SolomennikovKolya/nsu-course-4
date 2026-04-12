from typing import List

from core.uddm import *
from modules.converter.reverse.base import BaseReverseConverter


class UDDMToMarkdown(BaseReverseConverter):

    def convert(self, uddm: UDDM) -> str:
        """Преобразует UDDM в Markdown."""
        lines: List[str] = []

        for block in uddm.root:
            self._walk_block(lines, block)

        return "\n".join(lines)

    def _walk_block(self, lines: List[str], block: Block, indent: int = 0):
        prefix = "  " * indent

        if isinstance(block, Text):
            for p in block.paragraphs:
                text = p.text.strip()
                if text:
                    lines.append(f"{prefix}{text}")
            lines.append("")

        elif isinstance(block, ListBlock):
            item_num = 1

            for item in block.items:
                first = True

                for sub_block in item.blocks:
                    if isinstance(sub_block, Text):
                        for p in sub_block.paragraphs:
                            text = p.text.strip()
                            if text:
                                if first:
                                    lines.append(f"{prefix}{item_num}. {text}")
                                    item_num += 1
                                    first = False
                                else:
                                    lines.append(f"{prefix}  {text}")
                    else:
                        if first:
                            lines.append(f"{prefix}{item_num}. ")
                            item_num += 1
                            first = False
                        self._walk_block(lines, sub_block, indent + 1)

            lines.append("")

        elif isinstance(block, Table):
            table_lines = []

            for row_idx, row in enumerate(block.rows):
                row_cells = []

                for cell in row.cells:
                    cell_text_parts = []

                    # Используем фильтрацию через isinstance для Text блоков в ячейке
                    for sub_block in cell.blocks:
                        if isinstance(sub_block, Text):
                            for p in sub_block.paragraphs:
                                if p.text.strip():
                                    cell_text_parts.append(p.text.strip())

                    cell_text = " ".join(cell_text_parts)
                    row_cells.append(cell_text)

                table_lines.append("| " + " | ".join(row_cells) + " |")

                # header separator
                if row_idx == 0:
                    table_lines.append(
                        "| " + " | ".join(["---"] * len(row_cells)) + " |"
                    )

            lines.extend(table_lines)
            lines.append("")
