from pathlib import Path
import fitz  # (PyMuPDF)


class PdfNormalizer:

    def normalize(self, input_path: Path) -> Path:
        """
        Нормализация PDF (например, пересохранение,
        чтобы убрать мусорные структуры).
        """
        output_path = input_path.with_name(input_path.stem + "_normalized.pdf")

        doc = fitz.open(str(input_path))
        doc.save(str(output_path), garbage=4, deflate=True)
        doc.close()

        return output_path
