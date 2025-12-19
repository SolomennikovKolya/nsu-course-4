from modules.converter.converter import Converter

from pathlib import Path
from lxml import etree  # type: ignore

DOCX_TEST_INP_PATH = "./tests/docs/Соломенников_Николай_Александрович_Прил 1_ИЗ на практику_Бакалавриат_ПИиКН_6 семестр.docx"
DOCX_TEST_OUT_PATH = "./tests/results/Соломенников_Николай_Александрович_Прил 1_ИЗ на практику_Бакалавриат_ПИиКН_6 семестр.xml"


def test_converter():
    test_inp_path = Path(DOCX_TEST_INP_PATH).resolve()
    test_out_path = Path(DOCX_TEST_OUT_PATH).resolve()

    try:
        converter = Converter()
        tree = converter.process(test_inp_path)

        # print(etree.tostring(tree, pretty_print=True, encoding="unicode", xml_declaration=False))
        tree.write(str(test_out_path), pretty_print=True, encoding="utf-8", xml_declaration=True)

    except Exception as e:
        print(f"Converter execution error: {e}")


if __name__ == "__main__":
    test_converter()
