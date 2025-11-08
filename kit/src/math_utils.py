import random
from tabulate import tabulate
import hashlib


SMALL_PRIMES = [
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47,
    53, 59, 61, 67, 71, 73, 79, 83, 89, 97
]


def is_prime(n: int) -> bool:
    """Проверка простоты числа."""
    if n < 2:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def miller_rabin(n: int, k: int = 5) -> bool:
    """Вероятностный тест простоты Миллера–Рабина."""
    if n < 2:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0:
        return False

    # Представляем n-1 в виде 2^r * d
    r, d = 0, n - 1
    while d % 2 == 0:
        d //= 2
        r += 1

    # k раундов проверки
    for _ in range(k):
        a = random.randrange(2, n - 1)
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


def is_probably_prime(n: int, k: int = 5) -> bool:
    """
    Быстрая проверка делимости на малые простые + вероятностный тест простоты Миллера–Рабина.
    Работает не в 100% случаях, зато очень быстро. n — проверяемое число; 
    k — количество раундов проверки (чем больше, тем надёжнее).
    """
    if n < 2:
        return False
    for p in SMALL_PRIMES:
        if n == p:
            return True
        elif n % p == 0:
            return False
    return miller_rabin(n, k)


def generate_prime(bits: int = 1024) -> int:
    """Генерация большого простого числа с заданным колличеством битов."""
    while True:
        p = random.getrandbits(bits)  # Генерируем случайный набор битов
        p |= (1 << bits - 1) | 1      # Устанавливаем старший бит и младший бит в 1

        # В зависимости от желаемого размера простого числа, применяем разные алгоритмы
        # потому что при bits >= 50 детерминированный алгоритм проверки на простоту работает долго
        if bits < 50 and is_prime(p) or bits >= 50 and is_probably_prime(p):
            return p


def prime_factors(n: int, allow_duplicates: bool = False) -> list[int]:
    """Возвращает множество простых делителей числа n."""
    factors = list()
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)

    if allow_duplicates:
        return factors
    else:
        return list(set(factors))


def find_all_primitive_roots(p: int) -> list[int]:
    """
    Находит все примитивные (первообразные) корни g по модулю p.
    Ещё одно определение g - элемент, который порождает мультипликативной группы кольца вычетов по модулю p.
    Данное требование на g необходимо для стойкости системы Диффи–Хеллмана.
    В функции используется долгий, но детерминированный алгоритм. 
    """
    if not is_prime(p):
        raise ValueError("p должно быть простым.")

    phi = p - 1  # порядок мультипликативной группы
    factors = prime_factors(phi)
    generators = []

    # Достаточное условие: для всех простых делителей q числа p−1 выполняется:
    # g^((p-1)/q) != 1 (mod p)
    for g in range(2, p):
        if all(pow(g, phi // q, p) != 1 for q in factors):
            generators.append(g)
    return generators


def print_powers_table(p: int) -> None:
    """
    Выводит таблицу степеней g^k mod p с отметкой, является ли g примитивным.
    Можно визуально проверить, что функция find_all_primitive_roots работает правильно.
    """
    phi = p - 1
    headers = ["g"] + [f"g^{i}" for i in range(1, phi + 1)] + ["Генератор?"]
    table = []

    for g in range(2, p):
        powers = [pow(g, i, p) for i in range(1, phi + 1)]
        is_gen = "✅" if len(set(powers)) == phi else "❌"
        row = [g] + powers + [is_gen]
        table.append(row)

    print(f"\nТаблица степеней по модулю {p}")
    print(tabulate(table, headers=headers, tablefmt="minimal"))


def generate_safe_prime(bits: int = 1024) -> int:
    """
    Генерирует безопасное простое число p = 2q + 1. q - тоже простое.
    Алгоритм основан на вероятностях. Применяется, когда p должно быть очень большим.
    """
    while True:
        q = random.getrandbits(bits - 1)
        q |= (1 << (bits - 2)) | 1

        if is_probably_prime(q):
            p = 2 * q + 1
            if is_probably_prime(p):
                return p, q


def generate_primitive_root(p: int, q: int) -> int:
    """
    Находит безопасный первообразный корень по модулю p.
    Для корректности работы необходимо: p = 2q + 1 (p и q - простые).
    """
    while True:
        g = random.randrange(2, p - 1)
        if pow(g, 2, p) != 1 and pow(g, q, p) != 1:
            return g


def my_pow(base: int, exp: int, mod: int) -> int:
    """Своя реализация возведениия в степень."""
    result = 1
    base %= mod

    while exp > 0:
        if exp & 1:
            result = (result * base) % mod
        base = (base * base) % mod
        exp >>= 1
    return result


def gcd(a: int, b: int) -> int:
    """Вычисляет НОД(a, b) классическим алгоритмом Евклида."""
    while b != 0:
        a, b = b, a % b
    return abs(a)


def mod_inverse(a: int, m: int) -> int | None:
    """
    Вычисляет x = a^(-1) mod m, если обратный элемент существует.
    В противном случае возвращает None (обратного нет, когда gcd(a, m) != 1).
    """
    t, new_t = 0, 1
    r, new_r = m, a

    while new_r != 0:
        quotient = r // new_r
        t, new_t = new_t, t - quotient * new_t
        r, new_r = new_r, r - quotient * new_r

    if r > 1:
        return None
    if t < 0:
        t += m
    return t


def phi(n: int) -> int:
    """Вычисляет функцию Эйлера (количество чисел от 1 до n, которые взаимно просты с n)."""
    result = n
    i = 2
    while i * i <= n:
        if n % i == 0:
            while n % i == 0:
                n //= i
            result -= result // i
        i += 1
    if n > 1:
        result -= result // n
    return result


def int_hash(x: int) -> int:
    """Хеш числа через SHA-256 → целое."""
    h = hashlib.sha256(str(x).encode()).digest()
    return int.from_bytes(h, 'big')


if __name__ == "__main__":
    # print(generate_prime(100))
    # print(mod_inverse(27, 40))
    print(pow(5, 11, 23))
