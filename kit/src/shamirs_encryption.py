from math_utils import gcd, mod_inverse, generate_prime
import random
from tabulate import tabulate


class ShamirParticipant:
    """Участник шифра Шамира."""

    def __init__(self, name: str, p: int = None):
        # Общая информация:
        self.name = name
        self.p = p if p != None else generate_prime(20)
        self.phi = self.p - 1

        # Секретные ключи:
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
    print("\n=== Shamir's encryption DEMO ===\n")

    # Создаём участников
    alice = ShamirParticipant("Алиса", 30803)
    bob = ShamirParticipant("Боб", alice.p)

    print(f"p = {alice.p}\n")
    headers = ["Участник", "Секретные ключи"]
    table = [
        ["Алиса", f"c = {alice.c}, d = {alice.d}"],
        ["Боб", f"c = {bob.c}, d = {bob.d}"]
    ]
    print(tabulate(table, headers=headers, tablefmt="minimal") + "\n")

    # Протокол обмена
    m = random.randint(2, alice.p - 2)
    x1 = alice.encrypt(m)   # Алиса шифрует
    x2 = bob.encrypt(x1)    # Боб шифрует
    x3 = alice.decrypt(x2)  # Алиса снимает своё шифрование
    x4 = bob.decrypt(x3)    # Боб расшифровывает окончательно

    headers = ["m", "x1", "x2", "x3", "x4"]
    table = [[m, x1, x2, x3, x4]]
    print(tabulate(table, headers=headers, tablefmt="minimal"), end="\n\n")

    if x4 == m:
        print("Сообщение успешно восстановлено!")
    else:
        print("Ошибка: результат не совпадает с исходным сообщением.")


if __name__ == "__main__":
    demo()

"""
=== Shamir's encryption DEMO ===

p = 30803

Участник    Секретные ключи
----------  -------------------
Алиса       c = 21715, d = 2627
Боб         c = 24915, d = 5881

    m     x1     x2    x3     x4
-----  -----  -----  ----  -----
16181  26172  26463  1982  16181

Сообщение успешно восстановлено!
"""
