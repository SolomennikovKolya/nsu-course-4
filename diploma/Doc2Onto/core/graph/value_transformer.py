import hashlib
from typing import Dict, Callable


ValueTransformResult = Dict[str, str]
ValueTransformFunc = Callable[[str], ValueTransformResult]


class ValueTransformer:
    """
    Класс - утилита для преобразования значений полей шаблона в данные, 
    пригодные для использования в IRI. Предназначен для упрощения написания кода шаблона 
    и согласования с соглашениями хранения знаний в онтологической модели.
    """

    @staticmethod
    def person(value: str) -> ValueTransformResult:
        """
        Итоговый словарь:
        - "first_name" - имя
        - "middle_name" - отчество
        - "last_name" - фамилия
        - "name" - полное ФИО
        - "hash" - хэш, определяющий личность
        """
        parts = value.split()
        if len(parts) < 2:
            raise ValueError("ФИО должно содержать не менее двух частей")

        last = parts[0]
        first = parts[1]
        middle = parts[2] if len(parts) > 2 else None
        norm = " ".join(parts).lower()

        return {
            "last_name": last,
            "first_name": first,
            "middle_name": middle,
            "name": value,
            "hash": "person_" + ValueTransformer._hash(norm),
        }

    @staticmethod
    def email(value: str) -> ValueTransformResult:
        """
        Итоговый словарь:
        - "local" - локальная часть email
        - "domain" - доменная часть email
        - "email" - полное значение email
        - "hash" - хэш, определяющий email
        """
        parts = value.split("@")
        if len(parts) != 2:
            raise ValueError("Email должен содержать ровно 2 части, разделенные символом '@'")

        local, domain = parts

        return {
            "local": local,
            "domain": domain,
            "email": value.lower(),
            "hash": "email_" + ValueTransformer._hash(value.lower())
        }

    @staticmethod
    def date(value: str) -> ValueTransformResult:
        """..."""
        raise NotImplementedError()

    @staticmethod
    def telephone(value: str) -> ValueTransformResult:
        """..."""
        raise NotImplementedError()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha1(value.encode()).hexdigest()[:12]
