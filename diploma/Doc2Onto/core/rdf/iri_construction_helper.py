import hashlib
from typing import Optional, Dict


class IRIConstructionHelper:
    """
    Класс - утилита для преобразования значений полей шаблона в данные, 
    пригодные для использования в IRI. Предназначен для упрощения написания кода шаблона 
    и согласования с соглашениями хранения знаний в онтологической модели.
    """

    @staticmethod
    def person(value: Optional[str], fix_case: bool = True) -> Dict[str, str]:
        """
        Пытается привести значение к нормализованному виду ФИО.
        При необходимости исправляет падеж ФИО.

        Возвращает словарь с ключами:
        - "first_name" - имя
        - "middle_name" - отчество
        - "last_name" - фамилия
        - "full_name" - полное имя
        - "hash" - хэш, определяющий личность
        """
        pass

    @staticmethod
    def date(value: Optional[str]) -> Dict[str, str]:
        """..."""
        pass

    @staticmethod
    def telephone(value: Optional[str]) -> Dict[str, str]:
        """..."""
        pass

    @staticmethod
    def email(value: Optional[str]) -> Dict[str, str]:
        """..."""
        pass

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha1(value.encode()).hexdigest()[:12]
