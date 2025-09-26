import random
import math


class DiffieHellman:
    def __init__(self, p=None, g=None):
        """
        Инициализация параметров Диффи-Хеллмана
        p - большое простое число (модуль)
        g - первообразный корень по модулю p (генератор)
        """
        if p is None or g is None:
            # Используем стандартные параметры из RFC 3526
            self.p = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF
            self.g = 2
        else:
            self.p = p
            self.g = g

        # Генерируем секретный ключ
        self.private_key = self._generate_private_key()
        # Вычисляем публичный ключ
        self.public_key = self._calculate_public_key()

    def _generate_private_key(self):
        """Генерация секретного ключа (случайное число от 2 до p-2)"""
        return random.randint(2, self.p - 2)

    def _calculate_public_key(self):
        """Вычисление публичного ключа: A = g^a mod p"""
        return pow(self.g, self.private_key, self.p)

    def generate_shared_secret(self, other_public_key):
        """Вычисление общего секрета: s = B^a mod p"""
        return pow(other_public_key, self.private_key, self.p)


def is_prime(n, k=5):
    """Проверка числа на простоту с помощью теста Миллера-Рабина"""
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0:
        return False

    # Записываем n-1 в виде d*2^r
    d = n - 1
    r = 0
    while d % 2 == 0:
        d //= 2
        r += 1

    # Проводим k тестов
    for _ in range(k):
        a = random.randint(2, n - 2)
        x = pow(a, d, n)

        if x == 1 or x == n - 1:
            continue

        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False

    return True


def generate_prime(bits=1024):
    """Генерация большого простого числа"""
    while True:
        # Генерируем случайное нечетное число
        p = random.getrandbits(bits)
        p |= (1 << bits - 1) | 1  # Устанавливаем старший бит и младший бит

        if is_prime(p):
            return p


def find_primitive_root(p):
    """Поиск первообразного корня по модулю p"""
    if p == 2:
        return 1

    # Факторизуем p-1
    phi = p - 1
    factors = prime_factors(phi)

    # Проверяем кандидатов
    for g in range(2, p):
        if all(pow(g, phi // factor, p) != 1 for factor in factors):
            return g
    return None


def prime_factors(n):
    """Разложение числа на простые множители"""
    factors = set()
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.add(d)
            n //= d
        d += 1
    if n > 1:
        factors.add(n)
    return factors

# Пример использования


def main():
    print("Алгоритм Диффи-Хеллмана - обмен ключами")
    print("=" * 50)

    # Создаем участников обмена
    alice = DiffieHellman()
    bob = DiffieHellman(p=alice.p, g=alice.g)

    print(f"Параметры:")
    print(f"p (модуль): {alice.p}")
    print(f"g (генератор): {alice.g}")
    print()

    print("Секретные ключи:")
    print(f"Алиса: {alice.private_key}")
    print(f"Боб: {bob.private_key}")
    print()

    print("Публичные ключи:")
    print(f"Алиса: {alice.public_key}")
    print(f"Боб: {bob.public_key}")
    print()

    # Обмен публичными ключами и вычисление общего секрета
    alice_secret = alice.generate_shared_secret(bob.public_key)
    bob_secret = bob.generate_shared_secret(alice.public_key)

    print("Общие секреты:")
    print(f"Алиса вычислила: {alice_secret}")
    print(f"Боб вычислил: {bob_secret}")
    print()

    # Проверка совпадения секретов
    if alice_secret == bob_secret:
        print("✅ Обмен ключами прошел успешно! Секреты совпадают.")
    else:
        print("❌ Ошибка! Секреты не совпадают.")


if __name__ == "__main__":
    main()
