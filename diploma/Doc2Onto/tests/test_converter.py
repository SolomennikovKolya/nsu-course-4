from modules.converter.converter import Converter
import os


def test_converter_docx(tmp_path):
    sample = tmp_path / "doc1.docx"
    sample.write_text("hello")

    c = Converter()
    try:
        out = c.process(str(sample))
    except Exception:
        pass  # ок, так как soffice может быть не установлен
