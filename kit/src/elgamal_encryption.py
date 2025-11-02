import random
from tabulate import tabulate


class ElGamalParticipant:
    """Участник шифра Эль-Гамаля."""

    def __init__(self, name: str, p: int, g: int, c: int = None):
        self.name = name
        self.p = p
        self.g = g
        self.c = random.randint(2, p - 2) if c is None else c  # секретный ключ
        self.d = pow(g, self.c, p)                             # открытый ключ

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

    def decrypt(self, encryption: tuple[int, int]) -> int:
        """Расшифровка полученной пары (r, e)."""
        r, e = encryption
        return (e * pow(r, self.p - 1 - self.c, self.p)) % self.p


def demo():
    p = 30803
    g = 2
    print(f"\np = {p}, g = {g}\n")

    # Создаём участников
    alice = ElGamalParticipant("Алиса", p, g)
    bob = ElGamalParticipant("Боб", p, g)

    print(f"Алиса: c = {alice.c}, d = {alice.d}")
    print(f"Боб:   c = {bob.c}, d = {bob.d}")

    # Исходное сообщение
    m = random.randint(2, p - 2)

    # Алиса шифрует сообщение для Боба
    encryption = alice.encrypt(m, bob.public_key())

    # Боб расшифровывает
    decrypted = bob.decrypt(encryption)

    table = [[m, encryption[0], encryption[1], decrypted]]
    headers = ["m", "r", "e", "m'"]
    print("\n" + tabulate(table, headers=headers, tablefmt="minimal"), end="\n\n")

    if decrypted == m:
        print("Сообщение успешно расшифровано!")
    else:
        print("Ошибка: результат не совпадает с исходным сообщением.")


if __name__ == "__main__":
    demo()
