from diffie_hellman import DiffieHellman


data = [
    {"p": 23, "g": 5, "priv_A": 5, "priv_B": 7},
    {"p": 19, "g": 2, "priv_A": 5, "priv_B": 7},
    {"p": 23, "g": 7, "priv_A": 3, "priv_B": 4},
    {"p": 17, "g": 3, "priv_A": 10, "priv_B": 5},
    {"p": 19, "g": 10, "priv_A": 4, "priv_B": 8}
]

for sample in data:
    alice = DiffieHellman(p=sample["p"], g=sample["g"], private_key=sample["priv_A"])
    bob = DiffieHellman(p=sample["p"], g=sample["g"], private_key=sample["priv_B"])

    alice_key = alice.generate_shared_secret(bob.public_key)
    bob_key = bob.generate_shared_secret(alice.public_key)

    if alice_key == bob_key:
        print(f"Обмен ключами прошел успешно! Общий ключ: {alice_key}")
    else:
        print(f"Ошибка! Секретные ключи не совпадают: {alice_key}, {bob_key}")
