"""

"""

import math
import random
from typing import Optional, Dict, Tuple


def bsgs(a: int, y: int, p: int) -> Optional[int]:
    """
    Алгоритм "шаг младенца, шаг великана" (baby-step giant-step) для дискретного логарифма.
    Решает уравнение a^x = y (mod p), где p - простое, a и p взаимно просты.
    Возвращает x (0 <= x < p) если решение существует, иначе - None.
    """

    a %= p
    y %= p

    # Крайние случаи
    if y == 1:
        return 0  # a^0 = 1
    if a == 0:
        if y == 0:
            return 1  # 0^0 = 1
        elif y == 1:
            return 0  # 0^1 = 0
        else:
            return None

    m = math.isqrt(p - 1) + 1  # step size, ≈ sqrt(group order)

    # Словарь, соответствующий шагам младенца (ряд y, y*a, y*a^2, ..., y*a^(m-1))
    # Ключ - y*a^j, значение - j
    baby_steps: Dict[int, int] = {}
    baby_value = y
    for j in range(m):
        if baby_value not in baby_steps:
            baby_steps[baby_value] = j
        baby_value = (baby_value * a) % p

    # Шаги великана. Ищем i: y*a^j = a^(i*m)
    a_m = pow(a, m, p)
    giant_value = a_m
    for i in range(1, m + 1):
        if giant_value in baby_steps:
            j = baby_steps[giant_value]
            x = i * m - j
            return x
        giant_value = (giant_value * a_m) % p

    return None


def demo():
    data = [
        {"a": 2, "y": 24322, "p": 30203},
        {"a": 2, "y": 21740, "p": 30323},
        {"a": 2, "y": 28620, "p": 30539},
        {"a": 2, "y": 16190, "p": 30803},
        {"a": 5, "y": 30994, "p": 31607}
    ]

    for sample in data:
        a, y, p = sample["a"], sample["y"], sample["p"]
        x = bsgs(a, y, p)
        print(f"\na = {a}, y = {y}, p = {p}, x = {x}")

        if not x:
            print("Решения нет")
        else:
            res = pow(a, x, p)
            if res == y:
                print(f"Проверка: a^x (mod p) = {res} = y")
            else:
                print(f"Проверка: a^x (mod p) = {res} != y")


if __name__ == "__main__":
    demo()
