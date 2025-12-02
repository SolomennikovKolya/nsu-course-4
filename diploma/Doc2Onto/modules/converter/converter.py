import pathlib
from core.base_module import BaseModule
from modules.converter.converters.docx_to_pdf import DocxToPdfConverter
from modules.converter.converters.image_to_pdf import ImageToPdfConverter
from modules.converter.converters.pdf_normalizer import PdfNormalizer


class Converter(BaseModule):
    """
    Высокоуровневый фасад для всего процесса приведения документов к PDF.
    """

    def __init__(self):
        self.docx_converter = DocxToPdfConverter()
        self.image_converter = ImageToPdfConverter()
        self.pdf_normalizer = PdfNormalizer()

    def process(self, input_path: str) -> str:
        """
        Преобразует входной документ в нормализованный PDF.
        Возвращает путь к нормализованному PDF.
        """

        input_path = pathlib.Path(input_path)
        suffix = input_path.suffix.lower()

        if suffix in (".doc", ".docx", ".odt"):
            pdf_path = self.docx_converter.convert(input_path)
        elif suffix in (".png", ".jpg", ".jpeg", ".tiff"):
            pdf_path = self.image_converter.convert(input_path)
        elif suffix == ".pdf":
            pdf_path = input_path
        else:
            raise ValueError(f"Unsupported format: {suffix}")

        normalized_pdf = self.pdf_normalizer.normalize(pdf_path)
        return str(normalized_pdf)
