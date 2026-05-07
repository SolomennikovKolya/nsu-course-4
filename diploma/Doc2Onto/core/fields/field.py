from core.fields.field_extractor import FieldExtractor
from core.fields.field_normalizer import FieldNormalizer
from core.fields.field_selector import FieldSelector


class Field:
    """Описание поля документа: что искать, как извлекать, как нормализовать."""

    def __init__(
        self,
        name: str,
        description: str,
        selector: FieldSelector,
        extractor: FieldExtractor,
        normalizer: FieldNormalizer,
    ):
        """
        Args:
            name: Уникальное имя поля (snake_case). Используется как ключ при
                построении триплетов и в LLM-payload.
            description: Осмысленное описание поля. Используется LLM-этапом
                Extractor для проверки соответствия извлечённого значения смыслу.
            selector: Где искать (поиск элемента UDDM, содержащего значение).
            extractor: Как извлекать (преобразование текста элемента в строку).
            normalizer: Как нормализовать (приведение строки к канонической форме
                + проверка корректности). Возвращает каноническую строку или
                None — поле в этом случае помечается как невалидное.
        """
        self.name: str = name
        self.description: str = description
        self.selector: FieldSelector = selector
        self.extractor: FieldExtractor = extractor
        self.normalizer: FieldNormalizer = normalizer
