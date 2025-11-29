import os


# --- OTP для обычных строк ---

def xor_bytes(a: bytes, b: bytes) -> bytes:
    """XOR двух байтовых строк одинаковой длины."""
    return bytes(x ^ y for x, y in zip(a, b))


def otp_encrypt(message: bytes, key: bytes = None) -> tuple[bytes, bytes]:
    """
    Шифр Вернама:
    Возвращает (ciphertext, key).
    Ключ генерируется случайно и используется один раз.
    """
    if not key:
        key = os.urandom(len(message))
    elif isinstance(key, str):
        key, _ = str_bits_to_bytes(key)
    cipher = xor_bytes(message, key)
    return cipher, key


def otp_decrypt(cipher: bytes, key: bytes) -> bytes:
    """Расшифровка OTP: просто XOR с тем же ключом."""
    return xor_bytes(cipher, key)


# --- OTP для битовых строк ---

def str_bits_to_bytes(bits: str) -> bytes:
    """
    Преобразует строку вида '101101' в байты.
    Дополняет до полного байта нулями слева.
    """
    if not all(c in '01' for c in bits):
        raise ValueError("Строка должна содержать только 0 и 1")

    # Дополняем до кратности 8
    padding = (8 - len(bits) % 8) % 8
    bits = "0" * padding + bits

    # Разбиваем по 8 бит и преобразуем
    return bytes(int(bits[i:i+8], 2) for i in range(0, len(bits), 8)), padding


def bytes_to_str_bits(data: bytes, padding: int = 0) -> str:
    """
    Превращает байты обратно в строку бит.
    Убирает ведущие нули, добавленный при кодировании.
    """
    bit_string = ''.join(f'{byte:08b}' for byte in data)
    return bit_string[padding:]


def otp_encrypt_bits(bitstring: str, key=None):
    data, padding = str_bits_to_bytes(bitstring)
    if not key:
        key = os.urandom(len(data))
    elif isinstance(key, str):
        key, _ = str_bits_to_bytes(key)
    cipher = xor_bytes(data, key)
    return cipher, key, padding


def otp_decrypt_bits(cipher: bytes, key: bytes, padding: int) -> str:
    data = xor_bytes(cipher, key)
    return bytes_to_str_bits(data, padding)


def demo():
    print("=== Демонстрация шифра Вернама (One-Time Pad) ===\n")

    msg_text = "HELLO, VERNAM!"
    message = msg_text.encode("utf-8")
    print(f"Оригинал:       {message}")

    # Шифрование
    cipher, key = otp_encrypt(message)
    print(f"Ключ (hex):     {key.hex()}")
    print(f"Шифртекст:      {cipher.hex()}")

    # Дешифрование
    decrypted = otp_decrypt(cipher, key)
    print(f"Дешифровка:     {decrypted}")
    print(f"Строка:         {decrypted.decode('utf-8')}")


def demo_bits():
    print("=== OTP для битовых строк ===\n")

    message_bits = "1001101011"
    print(f"Битовая строка: {message_bits}")

    cipher, key, padding = otp_encrypt_bits(message_bits)
    print(f"Ключ:           {bytes_to_str_bits(key, padding)}")
    print(f"Шифртекст:      {bytes_to_str_bits(cipher, padding)}")

    decrypted = otp_decrypt_bits(cipher, key, padding)
    print(f"Дешифровка:     {decrypted}")


def test_bits_encrypt():
    data = [
        {"m": "1001101011", "k": "0110100101"},
        {"m": "0011101001", "k": "1100011100"},
        {"m": "1000011100", "k": "1001011010"},
        {"m": "0011100010", "k": "0110111001"},
        {"m": "1001101011", "k": "1000111010"},
    ]
    letter = 'а'

    for sample in data:
        m, k = sample["m"], sample["k"]
        cipher, _, padding = otp_encrypt_bits(m, k)
        print(f"{letter}. {m} xor {k} = {bytes_to_str_bits(cipher, padding)}")

        letter = chr(ord(letter) + 1)


if __name__ == "__main__":
    # demo()
    # demo_bits()
    test_bits_encrypt()

"""
а. 1001101011 xor 0110100101 = 1111001110
б. 0011101001 xor 1100011100 = 1111110101
в. 1000011100 xor 1001011010 = 0001000110
г. 0011100010 xor 0110111001 = 0101011011
д. 1001101011 xor 1000111010 = 0001010001
"""
