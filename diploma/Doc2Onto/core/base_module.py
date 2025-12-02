from abc import ABC, abstractmethod


class BaseModule(ABC):
    """
    Базовый интерфейс для всех модулей системы.
    """

    @abstractmethod
    def process(self, *args, **kwargs):
        """
        Основной метод обработки.
        """
        pass
