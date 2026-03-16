from enum import Enum


class DocumentStatus(str, Enum):
    """Статусы обработки документа по ходу прохождения пайплайна."""

    UPLOADED = "uploaded"                        # Документ загружен в систему
    UDDM_EXTRACTED = "uddm_extracted"            # Извлечены данные в формате UDDM
    CLASS_DETERMINED = "class_determined"        # Определен класс документа
    KNOWLEDGE_EXTRACTED = "knowledge_extracted"  # Извлечены знания (триплеты)
    VALIDATED = "validated"                      # Знания провалидированы
    ADDED_TO_MODEL = "added_to_model"            # Документ добавлен в модель

    def __str__(self):
        return self.value

    def __int__(self):
        stages = {
            DocumentStatus.UPLOADED: 1,
            DocumentStatus.UDDM_EXTRACTED: 2,
            DocumentStatus.CLASS_DETERMINED: 3,
            DocumentStatus.KNOWLEDGE_EXTRACTED: 4,
            DocumentStatus.VALIDATED: 5,
            DocumentStatus.ADDED_TO_MODEL: 6,
        }
        return stages[self]
