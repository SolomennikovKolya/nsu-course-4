import subprocess
from pathlib import Path


class DocxToPdfConverter:

    def convert(self, input_path: Path) -> Path:
        """
        Конвертация DOCX -> PDF с использованием LibreOffice в headless режиме.
        """
        output_path = input_path.with_suffix(".pdf")

        subprocess.run([
            "soffice", "--headless", "--convert-to", "pdf",
            str(input_path), "--outdir", str(input_path.parent)
        ], check=True)

        return output_path
