from math_utils import gcd, mod_inverse, generate_prime, prime_factors
import random
from tabulate import tabulate


class RSASigner:
    """
    Владелец сертификата ключа проверки электронной подписи RSA.
    p, q - секретные простые числа;
    c — секретное число, обратное экспоненте d по модулю N;
    n - публичный модуль, равный p*q;
    d - публичная экспонента такая, взаимно простая с phi(n).
    """

    def __init__(self, name: str, p: int = None, q: int = None, d: int = None, n: int = None):
        self.name = name

        if p is not None and q is not None:
            # если заданы p и q — используем их
            self.p = p
            self.q = q
            self.n = p * q
            self.phi = (p - 1) * (q - 1)
        elif n is not None:
            # если дано n — попытаемся факторизовать (для маленьких n это ок)
            self.n = n
            factors = prime_factors(n)
            if (len(factors) != 2 or factors[0] == factors[1]):
                raise ValueError("Не удалось факторизовать n; передайте p и q явно.")
            self.p = factors[0]
            self.q = factors[1]
            self.phi = (self.p - 1) * (self.q - 1)
        else:
            # если ничего не задано, генерируем p и q автоматическая
            self.p = generate_prime(20)
            self.q = generate_prime(20)
            while self.q == self.p:
                self.q = generate_prime(20)

        self.n = self.p * self.q
        self.phi = (self.p - 1) * (self.q - 1)

        if d is not None:
            if gcd(d, self.phi) != 1:
                raise ValueError("Экспонента d должна быть взаимно проста с phi(n).")
            self.d = d
        else:
            while True:
                d = random.randint(2, self.phi - 1)
                if gcd(d, self.phi) == 1:
                    self.d = d
        self.c = mod_inverse(self.d, self.phi)

    def public_key(self) -> tuple[int, int]:
        """Возвращает публичный ключ (n, d)."""
        return self.n, self.d

    def sign(self, m: int) -> int:
        """Подпись сообщения m (предполагается, что m = h(m) - хэш)"""
        return pow(m, self.c, self.n)

    def verify(self, m: int, x: int, public: tuple[int, int]) -> bool:
        """Проверка подписи. 
        m - сообщение; 
        x - подпись; 
        public = (n, d) - публичные ключи"""
        n, d = public
        m2 = pow(x, d, n)
        print(m2)
        return m2 == m


def demo():
    print("\n=== RSA SIGNATURE DEMO ===\n")

    # Cоздаём пользователя
    user = RSASigner("User", n=52891, d=3)

    headers = ["Участник", "Секретные ключи", "Публичные ключи"]
    table = [[user.name, f"p = {user.p}, q = {user.q}, c = {user.c}", f"n = {user.n}, d = {user.d}"]]
    print(tabulate(table, headers=headers, tablefmt="minimal") + "\n")

    # Проверка подлинного сообщения с реальной подписью
    m_real = 500
    x_real = user.sign(m_real)
    ok = user.verify(m_real, x_real, user.public_key())
    print(f"Проверка реальной подписки (m={m_real}, x={x_real}) ->", "VALID" if ok else "INVALID")

    # Демонстрация того, что изменение подписи ломает проверку
    x_fake = x_real + 1
    ok = user.verify(m_real, x_fake, user.public_key())
    print(f"Проверка с поддельной подписью (m={m_real}, x={x_fake}) ->", "VALID" if ok else "INVALID")

    # Демонстрация того, что изменение сообщения ломает проверку
    m_fake = m_real + 1
    ok = user.verify(m_fake, x_real, user.public_key())
    print(f"Проверка с изменённым сообщением (m={m_fake}, x={x_real}) ->", "VALID" if ok else "INVALID")


if __name__ == "__main__":
    demo()

"""
=== RSA SIGNATURE DEMO ===

Участник    Секретные ключи              Публичные ключи
----------  ---------------------------  -----------------
User        p = 233, q = 227, c = 34955  n = 52891, d = 3

Проверка реальной подписки (m=500, x=46514) -> VALID
Проверка с поддельной подписью (m=500, x=46515) -> INVALID
Проверка с изменённым сообщением (m=501, x=46514) -> INVALID
"""
