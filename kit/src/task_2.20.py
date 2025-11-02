from diffie_hellman import DiffieHellman


print("Алгоритм Диффи-Хеллмана - обмен ключами\n")

# Создаем участников обмена
alice = DiffieHellman(p=30803, g=2)
bob = DiffieHellman(p=alice.p, g=alice.g)

print(f"Параметры:")
print(f"p: {alice.p}")
print(f"g: {alice.g}")
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
print(f"Алиса вычислила: {alice_secret}")  # 9317
print(f"Боб вычислил: {bob_secret}")       # 9317
print()

# Проверка совпадения секретов
if alice_secret == bob_secret:
    print("Обмен ключами прошел успешно! Секреты совпадают.")
else:
    print("Ошибка! Секреты не совпадают.")
