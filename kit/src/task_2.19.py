from math_utils import my_pow, gcd, mod_inverse


print("Возведение в степень по модулю:")
print("2^10 mod 11 =", my_pow(2, 10, 11))

print("\nНОД:")
print("gcd(48, 18) =", gcd(48, 18))

print("\nОбратный элемент по модулю:")
print("5^(-1) mod 11 =", mod_inverse(5, 11))
