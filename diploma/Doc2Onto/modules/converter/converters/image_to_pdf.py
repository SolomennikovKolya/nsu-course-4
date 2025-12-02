from pathlib import Path
from PIL import Image


class ImageToPdfConverter:

    def convert(self, input_path: Path) -> Path:
        """
        Простейший PNG/JPG→PDF (без OCR).
        """
        output_path = input_path.with_suffix(".pdf")
        img = Image.open(input_path)
        img.convert("RGB").save(output_path)
        return output_path
