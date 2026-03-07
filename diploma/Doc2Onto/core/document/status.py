from enum import Enum


class DocumentStatus(str, Enum):
    """Статусы обработки документа по ходу прохождения пайплайна."""

    UPLOADED = "uploaded"                        # 1. Документ загружен в систему
    UDDM_EXTRACTED = "uddm_extracted"            # 2. Извлечены данные в формате UDDM
    KNOWLEDGE_EXTRACTED = "knowledge_extracted"  # 3. Извлечены знания (триплеты)
    VALIDATED = "validated"                      # 4. Знания провалидированы
    ADDED_TO_MODEL = "added_to_model"            # 5. Документ добавлен в модель

    def __str__(self):
        return self.value

    def __int__(self):
        stages = {
            DocumentStatus.UPLOADED: 1,
            DocumentStatus.UDDM_EXTRACTED: 2,
            DocumentStatus.KNOWLEDGE_EXTRACTED: 3,
            DocumentStatus.VALIDATED: 4,
            DocumentStatus.ADDED_TO_MODEL: 5,
        }
        return stages[self]
