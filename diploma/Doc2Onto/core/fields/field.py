from core.fields.field_selector import FieldSelector
from core.fields.field_extractor import FieldExtractor
from core.fields.field_validator import FieldValidator


class Field:
    """Содержит описание поля документа и информацию о том, как его извлекать и валидировать."""

    def __init__(
        self,
        name: str,
        description: str,
        selector: FieldSelector,
        extractor: FieldExtractor,
        validator: FieldValidator,
    ):
        """
        Args:
            name: Уникальное название поля, используемое в дальнейшем при построении триплетов
            description: Осмысленное исчерпывающее описание. Используется для извлечения и валидации поля с использованием LLM
            selector: Где искать? (поиск текста, содержащего значение поля)
            extractor: Как извлекать? (логика извлечения значения поля из текста, найденного селектором)
            validator: Как валидировать? (правила проверки корректности извлечённого значения поля)
        """
        self.name: str = name
        self.description: str = description
        self.selector: FieldSelector = selector
        self.extractor: FieldExtractor = extractor
        self.validator: FieldValidator = validator
