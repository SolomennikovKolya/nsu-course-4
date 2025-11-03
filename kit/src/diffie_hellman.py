from math_utils import generate_safe_prime, generate_primitive_root
import random
from tabulate import tabulate


class DiffieHellman:
    """Участник схемы Диффи-Хеллмана."""

    def __init__(self, p: int = None, g: int = None, x: int = None):
        # Общая информация:
        if p != None and g != None:
            self.p = p
            self.g = g
        else:
            self.p, q = generate_safe_prime(10)
            self.g = generate_primitive_root(self.p, q)

        # Секретные ключи:
        self.x = x if x != None else self._generate_private_key()

        # Открытые ключи:
        self.y = self._calculate_public_key()

    def _generate_private_key(self):
        """Генерация секретного ключа."""
        return random.randint(2, self.p - 2)

    def _calculate_public_key(self):
        """Вычисление публичного ключа."""
        return pow(self.g, self.x, self.p)

    def generate_shared_secret(self, other_public_key):
        """Вычисление общего секрета."""
        return pow(other_public_key, self.x, self.p)


def demo():
    print("\n=== Diffie-Hellman algorithm DEMO ===\n")

    # Создаем участников обмена
    alice = DiffieHellman(30803, 2)
    bob = DiffieHellman(alice.p, alice.g)

    print(f"p = {alice.p}, g = {alice.g}\n")
    headers = ["Участник", "Секретные ключи", "Публичные ключи"]
    table = [
        ["Алиса", f"x = {alice.x}", f"y = {alice.y}"],
        ["Боб", f"x = {bob.x}", f"y = {bob.y}"]
    ]
    print(tabulate(table, headers=headers, tablefmt="minimal") + "\n")

    # Обмен публичными ключами и вычисление общего секрета
    alice_secret = alice.generate_shared_secret(bob.y)
    bob_secret = bob.generate_shared_secret(alice.y)

    print(f"Алиса вычислила: {alice_secret}")
    print(f"Боб вычислил: {bob_secret}")
    print()

    if alice_secret == bob_secret:
        print("Обмен ключами прошел успешно! Секреты совпадают.")
    else:
        print("Ошибка! Секреты не совпадают.")


if __name__ == "__main__":
    demo()

"""
=== Diffie-Hellman algorithm DEMO ===

p = 30803, g = 2

Участник    Секретные ключи    Публичные ключи
----------  -----------------  -----------------
Алиса       x = 13992          y = 4776
Боб         x = 22471          y = 30188

Алиса вычислила: 14721
Боб вычислил: 14721

Обмен ключами прошел успешно! Секреты совпадают.
"""
