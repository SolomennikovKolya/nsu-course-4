import random
from tabulate import tabulate
from math_utils import gcd, mod_inverse, is_prime


def generate_prime(start=1000, end=5000) -> int:
    """Генерация случайного простого числа"""
    while True:
        n = random.randint(start, end)
        if is_prime(n):
            return n


class RSAParticipant:
    """Участник шифра RSA."""

    def __init__(self, name: str):
        self.name = name
        self.p = generate_prime()
        self.q = generate_prime()
        while self.q == self.p:
            self.q = generate_prime()
        self.n = self.p * self.q
        self.phi = (self.p - 1) * (self.q - 1)
        self.e, self.d = self._generate_key_pair()
        print(f"{self.name}: p={self.p}, q={self.q}, e={self.e}, d={self.d}, n={self.n}")

    def _generate_key_pair(self) -> tuple[int, int]:
        """Выбирает e, d такие, что e*d ≡ 1 (mod phi)"""
        while True:
            e = random.randint(2, self.phi - 1)
            if gcd(e, self.phi) == 1:
                d = mod_inverse(e, self.phi)
                if d is not None:
                    return e, d

    def public_key(self) -> tuple[int, int]:
        """Публичный ключ (e, n)"""
        return self.e, self.n

    def encrypt(self, msg: int, recipient_public: tuple[int, int]) -> int:
        """Шифрование сообщения msg для получателя."""
        e, n = recipient_public
        c = pow(msg, e, n)
        print(f"{self.name} шифрует сообщение {msg} → {c}")
        return c

    def decrypt(self, cipher: int) -> int:
        """Расшифровка шифртекста."""
        m = pow(cipher, self.d, self.n)
        print(f"{self.name} расшифровывает {cipher} → {m}")
        return m


def demo():
    print("\n=== RSA DEMO ===\n")

    # Создаём участников
    alice = RSAParticipant("Алиса")
    bob = RSAParticipant("Боб")

    # Исходное сообщение
    m = random.randint(2, min(alice.n, bob.n) - 1)

    # Алиса шифрует сообщение для Боба
    cipher = alice.encrypt(m, bob.public_key())

    # Боб расшифровывает
    decrypted = bob.decrypt(cipher)

    # Табличный вывод
    table = [[m, cipher, decrypted]]
    headers = ["m", "cipher", "decrypted"]
    print("\n" + tabulate(table, headers=headers, tablefmt="minimal"), end="\n\n")

    if decrypted == m:
        print("Сообщение успешно расшифровано!")
    else:
        print("Ошибка: результат не совпадает с исходным сообщением.")


if __name__ == "__main__":
    demo()
