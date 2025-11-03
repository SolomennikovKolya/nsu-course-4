import random
from math_utils import gcd, mod_inverse
from tabulate import tabulate


class MentalPokerPlayer:
    """Участник протокола 'Ментальный покер'."""

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

    def encrypt(self, value: int) -> int:
        """Шифрует значение (возведение в степень c mod p)."""
        return pow(value, self.c, self.p)

    def decrypt(self, value: int) -> int:
        """Расшифровывает значение (возведение в степень d mod p)."""
        return pow(value, self.d, self.p)


def demo():
    print("\n=== Mental poker DEMO ===\n")

    # Общие параметры
    p = 30803
    deck = [5, 7, 14]
    print(f"Общий модуль p = {p}")
    print(f"Колода (закодированные карты): {deck}\n")

    # Создаём участников
    alice = MentalPokerPlayer("Алиса", p)
    bob = MentalPokerPlayer("Боб", p)

    headers = ["Участник", "Секретные ключи", "Публичные ключи"]
    table = [
        [alice.name, f"c = {alice.c}, d = {alice.d}"],
        [bob.name, f"c = {bob.c}, d = {bob.d}"],
    ]
    print(tabulate(table, headers=headers, tablefmt="minimal"), "\n")

    # Процесс раздачи карт

    deck = [alice.encrypt(x) for x in deck]
    print(f"Алиса шифрует карты: {deck}")

    random.shuffle(deck)
    print(f"Алиса перемешивает карты и отправляет Бобу: {deck}")

    alice_card_enc = random.choice(deck)
    print(f"Боб выбирает случайную карту и отправляет Алисе: {alice_card_enc}")

    alice_card = alice.decrypt(alice_card_enc)
    print(f"Алиса получила карту: {alice_card}")

    deck.remove(alice_card_enc)
    deck = [bob.encrypt(x) for x in deck]
    print(f"Боб шифрует оставшиеся карты: {deck}")

    random.shuffle(deck)
    print(f"Боб перемешивает карты и отправляет Алисе: {deck}")

    bob_card_enc_enc = random.choice(deck)
    print(f"Алиса выбирает случайную карту: {bob_card_enc_enc}")

    bob_card_enc = alice.decrypt(bob_card_enc_enc)
    print(f"Алиса снимает свою шифрацию с карты и отправляет Бобу: {bob_card_enc}")

    bob_card = bob.decrypt(bob_card_enc)
    print(f"Боб получил карту: {bob_card}")


if __name__ == "__main__":
    demo()

"""
Пример вывода:

=== Mental poker DEMO ===

Общий модуль p = 30803
Колода (закодированные карты): [5, 7, 14]

Участник    Секретные ключи
----------  -------------------
Алиса       c = 28831, d = 8267
Боб         c = 3439, d = 12817

Алиса шифрует карты: [19404, 23628, 3803]
Алиса перемешивает карты и отправляет Бобу: [19404, 3803, 23628]
Боб выбирает случайную карту и отправляет Алисе: 3803
Алиса получила карту: 14
Боб шифрует оставшиеся карты: [28808, 19733]
Боб перемешивает карты и отправляет Алисе: [28808, 19733]
Алиса выбирает случайную карту: 28808
Алиса снимает свою шифрацию с карты и отправляет Бобу: 15308
Боб получил карту: 5
"""
