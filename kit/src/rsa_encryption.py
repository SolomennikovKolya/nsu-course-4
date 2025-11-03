from math_utils import gcd, mod_inverse, generate_prime
import random
from tabulate import tabulate


class RSAParticipant:
    """Участник шифра RSA."""

    def __init__(self, name: str, p: int = None, q: int = None, d: int = None):
        # Общая информация:
        self.name = name

        # Секретные ключи:
        if p != None and q != None:
            self.p = p
            self.q = q
        else:
            self.p = generate_prime(20)
            self.q = generate_prime(20)
            while self.q == self.p:
                self.q = generate_prime(20)
        self.phi = (self.p - 1) * (self.q - 1)
        d = d if d != None else self._generate_d()
        self.c = mod_inverse(d, self.phi)

        # Открытые ключи:
        self.n = self.p * self.q
        self.d = d

    def _generate_d(self) -> int:
        """Выбирает d такой, что gcd(d, phi) = 1."""
        while True:
            d = random.randint(2, self.phi - 1)
            if gcd(d, self.phi) == 1:
                return d

    def public_key(self) -> tuple[int, int]:
        """Публичный ключ (n, d)."""
        return self.n, self.d

    def encrypt(self, msg: int, recipient_public: tuple[int, int]) -> int:
        """Шифрование сообщения msg для получателя."""
        n, d = recipient_public
        return pow(msg, d, n)

    def decrypt(self, cipher: int) -> int:
        """Расшифровка шифртекста."""
        return pow(cipher, self.c, self.n)


def demo():
    print("\n=== RSA DEMO ===\n")

    # Создаём участников
    alice = RSAParticipant("Алиса", 131, 227, 3)
    bob = RSAParticipant("Боб", 113, 281, 3)

    headers = ["Участник", "Секретные ключи", "Публичные ключи"]
    table = [
        ["Алиса", f"p = {alice.p}, q = {alice.q}, c = {alice.c}", f"n = {alice.n}, d = {alice.d}"],
        ["Боб", f"p = {bob.p}, q = {bob.q}, c = {bob.c}", f"n = {bob.n}, d = {bob.d}"]
    ]
    print(tabulate(table, headers=headers, tablefmt="minimal") + "\n")

    # Протокол обмена
    m = random.randint(2, min(alice.n, bob.n) - 1)
    cipher = alice.encrypt(m, bob.public_key())  # Алиса шифрует сообщение для Боба
    decrypted = bob.decrypt(cipher)              # Боб расшифровывает

    headers = ["m", "cipher", "decrypted"]
    table = [[m, cipher, decrypted]]
    print("\n" + tabulate(table, headers=headers, tablefmt="minimal"), end="\n\n")

    if decrypted == m:
        print("Сообщение успешно расшифровано!")
    else:
        print("Ошибка: результат не совпадает с исходным сообщением.")


if __name__ == "__main__":
    demo()

"""
Пример вывода:

=== RSA DEMO ===

Участник    Секретные ключи              Публичные ключи
----------  ---------------------------  -----------------
Алиса       p = 131, q = 227, c = 19587  n = 29737, d = 3
Боб         p = 113, q = 281, c = 20907  n = 31753, d = 3


    m    cipher    decrypted
-----  --------  -----------
21832     31038        21832

Сообщение успешно расшифровано!
"""
