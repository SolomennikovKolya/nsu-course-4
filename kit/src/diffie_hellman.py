import random
import math
from math_utils import generate_safe_prime, generate_primitive_root


class DiffieHellman:
    def __init__(self, p=None, g=None, private_key=None):
        """
        Инициализация параметров системы Диффи-Хеллмана (от них зависит стойкость):
        p - большое простое число (модуль);
        g - первообразный корень по модулю p (генератор);
        public_key - открытый ключ;
        private_key - секретный ключ.
        """
        if p is None or g is None:
            self.p, q = generate_safe_prime(10)
            self.g = generate_primitive_root(self.p, q)
        else:
            self.p = p
            self.g = g

        self.private_key = self._generate_private_key() if private_key is None else private_key
        self.public_key = self._calculate_public_key()

    def _generate_private_key(self):
        """Генерация секретного ключа."""
        return random.randint(2, self.p - 2)

    def _calculate_public_key(self):
        """Вычисление публичного ключа."""
        return pow(self.g, self.private_key, self.p)

    def generate_shared_secret(self, other_public_key):
        """Вычисление общего секрета."""
        return pow(other_public_key, self.private_key, self.p)
