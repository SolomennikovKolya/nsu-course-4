from math_utils import gcd, mod_inverse, generate_safe_prime, generate_primitive_root, prime_factors
import random
from tabulate import tabulate


class ElGamalSigner:
    """
    Владелец сертификата ключа проверки электронной подписи Эль-Гамаля.
    p — большое простое число;
    g — первообразный корень по модулю p;
    x — секретный ключ;
    y = g^x mod p — открытый ключ.
    """

    def __init__(self, name: str, p: int = None, g: int = None, x: int = None):
        self.name = name

        if p != None and g != None:
            self.p = p
            self.g = g
        else:
            self.p, q = generate_safe_prime(20)
            self.g = generate_primitive_root(self.p, q)

        if x is None:
            self.x = random.randint(2, self.p - 2)
        else:
            self.x = x

        self.y = pow(self.g, self.x, self.p)

    def public_key(self):
        """Возвращает публичный ключ (p, g, y)."""
        return self.p, self.g, self.y

    def sign(self, m: int):
        """
        Подписание сообщения m (h(m) = m).
        1. Выбирается случайное k, взаимно простое с p-1.
        2. r = g^k mod p.
        3. s = k^{-1} * (m - x*r) mod (p-1).
        Подпись = (r, s)
        """
        while True:
            k = random.randint(2, self.p - 2)
            if gcd(k, self.p - 1) == 1:
                break

        r = pow(self.g, k, self.p)
        k_inv = mod_inverse(k, self.p - 1)
        s = (k_inv * (m - self.x * r)) % (self.p - 1)
        return r, s

    def verify(self, m: int, signature: tuple[int, int], public: tuple[int, int, int]) -> bool:
        """
        Проверка подписи (r, s).
        Проверяется равенство:
            y^r * r^s ≡ g^m (mod p)
        """
        p, g, y = public
        r, s = signature

        if not (0 < r < p):
            return False

        left = (pow(y, r, p) * pow(r, s, p)) % p
        right = pow(g, m, p)
        return left == right


def demo():
    print("\n=== ELGAMAL SIGNATURE DEMO ===\n")

    # Cоздаём пользователя
    user = ElGamalSigner("User", p=31259, g=2)

    headers = ["Участник", "Секретные ключи", "Публичные ключи"]
    table = [[user.name, f"x = {user.x}", f"p = {user.p}, g = {user.g}, y = {user.y}"]]
    print(tabulate(table, headers=headers, tablefmt="minimal") + "\n")

    # Тестовое сообщение с реальной подписью
    m_real = 500
    r, s = user.sign(m_real)
    ok = user.verify(m_real, (r, s), user.public_key())
    print(f"Проверка реальной подписи (m={m_real}, (r={r}, s={s})) ->", "VALID" if ok else "INVALID")

    # Поддельная подпись
    s_fake = (s + 1) % (user.p - 1)
    ok = user.verify(m_real, (r, s_fake), user.public_key())
    print(f"Проверка с поддельной подписью (m={m_real}, (r={r}, s={s_fake})) ->", "VALID" if ok else "INVALID")

    # Изменённое сообщение
    m_fake = m_real + 1
    ok = user.verify(m_fake, (r, s), user.public_key())
    print(f"Проверка с изменённым сообщением (m={m_fake}, (r={r}, s={s})) ->", "VALID" if ok else "INVALID")


if __name__ == "__main__":
    demo()

"""
=== ELGAMAL SIGNATURE DEMO ===

Участник    Секретные ключи    Публичные ключи
----------  -----------------  --------------------------
User        x = 21653          p = 31259, g = 2, y = 8325

Проверка реальной подписи (m=500, (r=6953, s=30179)) -> VALID
Проверка с поддельной подписью (m=500, (r=6953, s=30180)) -> INVALID
Проверка с изменённым сообщением (m=501, (r=6953, s=30179)) -> INVALID
"""
