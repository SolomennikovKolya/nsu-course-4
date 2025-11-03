from math_utils import generate_safe_prime, generate_primitive_root
import random
from tabulate import tabulate


class ElGamalParticipant:
    """Участник шифра Эль-Гамаля."""

    def __init__(self, name: str, p: int = None, g: int = None, c: int = None):
        # Общая информация:
        self.name = name
        if p != None and g != None:
            self.p = p
            self.g = g
        else:
            self.p, q = generate_safe_prime(20)
            self.g = generate_primitive_root(self.p, q)

        # Секретные ключи:
        self.c = c if c != None else random.randint(2, self.p - 2)

        # Открытые ключи:
        self.d = pow(self.g, self.c, self.p)

    def public_key(self) -> tuple[int, int, int]:
        """Возвращает публичный ключ d."""
        return self.d

    def encrypt(self, msg: int, recipient_public_key: int) -> tuple[int, int]:
        """
        Шифрование сообщения msg для получателя.
        recipient_public_key — публичный ключ получателя.
        Возвращает пару (r, e).
        """
        k = random.randint(2, self.p - 2)
        r = pow(self.g, k, self.p)
        e = (msg * pow(recipient_public_key, k, self.p)) % self.p
        return r, e

    def decrypt(self, cipher: tuple[int, int]) -> int:
        """Расшифровка полученной пары (r, e)."""
        r, e = cipher
        return (e * pow(r, self.p - 1 - self.c, self.p)) % self.p


def demo():
    print("\n=== El-Gamal encryption DEMO ===\n")

    # Создаём участников
    alice = ElGamalParticipant("Алиса", 30803, 2)
    bob = ElGamalParticipant("Боб", alice.p, alice.g)

    print(f"p = {alice.p}, g = {alice.g}\n")
    headers = ["Участник", "Секретные ключи", "Публичные ключи"]
    table = [["Алиса", f"c = {alice.c}", f"d = {alice.d}"],
             ["Боб", f"c = {bob.c}", f"d = {bob.d}"]]
    print(tabulate(table, headers=headers, tablefmt="minimal") + "\n")

    # Протокол обмена
    m = random.randint(2, alice.p - 2)
    cipher = alice.encrypt(m, bob.public_key())  # Алиса шифрует сообщение для Боба
    decrypted = bob.decrypt(cipher)              # Боб расшифровывает

    headers = ["m", "r", "e", "m'"]
    table = [[m, cipher[0], cipher[1], decrypted]]
    print(tabulate(table, headers=headers, tablefmt="minimal"), end="\n\n")

    if decrypted == m:
        print("Сообщение успешно расшифровано!")
    else:
        print("Ошибка: результат не совпадает с исходным сообщением.")


if __name__ == "__main__":
    demo()

"""
Пример вывода:

=== El-Gamal cipher DEMO ===

p = 30803, g = 2

Участник    Секретные ключи    Публичные ключи
----------  -----------------  -----------------
Алиса       c = 26417          d = 17451
Боб         c = 15096          d = 2518

    m      r     e     m'
-----  -----  ----  -----
14663  10654  9534  14663

Сообщение успешно расшифровано!
"""
