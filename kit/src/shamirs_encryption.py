import random
import math
from tabulate import tabulate
from math_utils import gcd, mod_inverse


class ShamirParticipant:
    """Участник шифра Шамира."""

    def __init__(self, name: str, p: int):
        self.name = name
        self.p = p
        self.phi = p - 1
        self.c, self.d = self._generate_key_pair()

    def _generate_key_pair(self) -> tuple[int, int]:
        """Генерация пары ключей (c, d), где c*d ≡ 1 mod (p-1)."""
        while True:
            c = random.randint(2, self.phi - 1)
            if gcd(c, self.phi) == 1:
                d = mod_inverse(c, self.phi)
                if d is not None:
                    return c, d

    def encrypt(self, msg: int) -> int:
        """Возведение сообщения в степень c по модулю p (шифрование)."""
        return pow(msg, self.c, self.p)

    def decrypt(self, msg: int) -> int:
        """Возведение в степень d по модулю p (снятие шифрования)."""
        return pow(msg, self.d, self.p)


def demo():
    p = 30803
    print(f"\np = {p}\n")

    # Создаём участников
    alice = ShamirParticipant("Алиса", p)
    bob = ShamirParticipant("Боб", p)

    # Исходное сообщение
    m = random.randint(2, p - 2)

    # Протокол обмена
    x1 = alice.encrypt(m)   # Алиса шифрует
    x2 = bob.encrypt(x1)    # Боб шифрует
    x3 = alice.decrypt(x2)  # Алиса снимает своё шифрование
    x4 = bob.decrypt(x3)    # Боб расшифровывает окончательно

    table = [[m, x1, x2, x3, x4]]
    headers = ["m", "x1", "x2", "x3", "x4"]
    print(tabulate(table, headers=headers, tablefmt="minimal"), end="\n\n")

    if x4 == m:
        print("Сообщение успешно восстановлено!")
    else:
        print("Ошибка: результат не совпадает с исходным сообщением.")


if __name__ == "__main__":
    demo()
