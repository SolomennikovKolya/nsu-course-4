from core.uddm.uddm import *
from app.modules.converter.reverse.base import BaseReverseConverter


class UDDMToTree(BaseReverseConverter):

    def convert(self, uddm: UDDM) -> str:
        """Преобразует UDDM в древовидное текстовое представление."""
        lines: List[str] = []

        for i, b in enumerate(uddm.blocks):
            is_last = i == len(uddm.blocks) - 1
            self._walk_block(lines, b, "", is_last)

        return "DOCUMENT\n" + "\n".join(lines)

    def _walk_block(self, lines: List[str], block: Block, prefix: str, is_last: bool):
        branch = "└── " if is_last else "├── "
        next_prefix = prefix + ("    " if is_last else "│   ")

        if isinstance(block, Text):
            lines.append(f"{prefix}{branch}TEXT")

            for i, p in enumerate(block.paragraphs):
                last = i == len(block.paragraphs) - 1
                sub_branch = "└── " if last else "├── "
                lines.append(f"{next_prefix}{sub_branch}p: {p.text}")

        elif isinstance(block, ListBlock):
            lines.append(f"{prefix}{branch}LIST")

            for i, item in enumerate(block.items):
                item_last = i == len(block.items) - 1
                item_branch = "└── " if item_last else "├── "
                lines.append(f"{next_prefix}{item_branch}ITEM")

                item_prefix = next_prefix + ("    " if item_last else "│   ")

                for j, b in enumerate(item.blocks):
                    last = j == len(item.blocks) - 1
                    self._walk_block(lines, b, item_prefix, last)

        elif isinstance(block, Table):
            lines.append(f"{prefix}{branch}TABLE")

            for i, row in enumerate(block.rows):
                row_last = i == len(block.rows) - 1
                row_branch = "└── " if row_last else "├── "
                lines.append(f"{next_prefix}{row_branch}ROW")

                row_prefix = next_prefix + ("    " if row_last else "│   ")

                for j, cell in enumerate(row.cells):
                    cell_last = j == len(row.cells) - 1
                    cell_branch = "└── " if cell_last else "├── "
                    lines.append(f"{row_prefix}{cell_branch}CELL")

                    cell_prefix = row_prefix + ("    " if cell_last else "│   ")

                    for k, b in enumerate(cell.blocks):
                        last = k == len(cell.blocks) - 1
                        self._walk_block(lines, b, cell_prefix, last)


# class UDDMToTree(BaseReverseConverter):

#     def convert(self, uddm: UDDM) -> str:
#         """Преобразует UDDM в древовидное представление."""
#         lines: List[str] = []

#         for b in uddm.blocks:
#             self._walk_block(lines, b)

#         return "\n".join(lines)

#     def _walk_block(self, lines: List[str], block: Block, indent=0):
#         prefix = "  " * indent

#         if isinstance(block, Text):
#             lines.append(f"{prefix}TEXT")
#             for p in block.paragraphs:
#                 lines.append(f"{prefix}  p: {p.text}")

#         elif isinstance(block, ListBlock):
#             lines.append(f"{prefix}LIST")
#             for item in block.items:
#                 lines.append(f"{prefix}  ITEM")
#                 for b in item.blocks:
#                     self._walk_block(lines, b, indent + 2)

#         elif isinstance(block, Table):
#             lines.append(f"{prefix}TABLE")
#             for row in block.rows:
#                 lines.append(f"{prefix}  ROW")
#                 for cell in row.cells:
#                     lines.append(f"{prefix}    CELL")
#                     for b in cell.blocks:
#                         self._walk_block(lines, b, indent + 3)
