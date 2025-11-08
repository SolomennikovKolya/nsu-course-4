from __future__ import annotations
from math_utils import gcd, mod_inverse, int_hash
from rsa_signature import RSASigner
import random
from tabulate import tabulate


class Bank(RSASigner):
    def __init__(self, name="Bank"):
        super().__init__(name)
        self.spent = set()  # Использованные серийные номера

    def blind_sign(self, blinded_msg: int) -> int:
        """Подписывает сообщение."""
        # Здесь со счёта клиента должны списаться деньги
        return self.sign(blinded_msg)

    def redeem(self, serial: int, sig: int) -> bool:
        """Проверяет подпись и факт повторного использования."""
        h = int_hash(serial) % self.n
        if not RSASigner.verify(h, sig, self.public_key()):
            print(f"[Bank] Ошибка: Подпись купюры <{serial}, {sig}> недействительна")
            return False
        if serial in self.spent:
            print(f"[Bank] Ошибка: Купюра <{serial}, {sig}> уже использована")
            return False
        self.spent.add(serial)
        print(f"[Bank] Купюра <{serial}, {sig}> принята")
        # Здесь на счёт продавца должны зачислиться деньги
        return True


class Client:
    def __init__(self, name="Client"):
        self.name = name
        self.wallet = []  # Подписанные купюры (можно использовать)

    def get_signed_coin(self, bank: Bank):
        """Получает подписанную купюру."""
        serial = random.getrandbits(40)
        h = int_hash(serial) % bank.n

        # Выбираем случайное w (взаимно простое с n)
        while True:
            w = random.randrange(2, bank.n - 1)
            if gcd(w, bank.n) == 1:
                break
        w_inv = mod_inverse(w, bank.n)

        blinded = (h * pow(w, bank.d, bank.n)) % bank.n  # Ослепляем
        signed_blinded = bank.blind_sign(blinded)        # Банк делает слепую подпись
        sig = (signed_blinded * w_inv) % bank.n          # Распрямляем

        # Проверяем корректность подписи
        if not RSASigner.verify(h, sig, bank.public_key()):
            raise RuntimeError("Ошибка: Распрямлённая подпись невалидна.")

        self.wallet.append((serial, sig))
        print(f"[{self.name}] Получена анонимная купюра <{serial}, {sig}>")
        return serial, sig

    def pay(self, merchant: Merchant, coin_index=0):
        """Передаёт купюру магазину."""
        serial, sig = self.wallet.pop(coin_index)
        merchant.receive(serial, sig, self)


class Merchant:
    def __init__(self, name="Merchant"):
        self.name = name
        self.coins = []

    def receive(self, serial: int, sig: int, client: Client):
        """Получает купюру от клиента."""
        print(f"[{self.name}] Получена купюра <{serial}, {sig}> от {client.name}")
        self.coins.append((serial, sig))

    def redeem(self, bank: Bank):
        """Отправляет купюры в банк для выкупа."""
        for serial, sig in list(self.coins):
            bank.redeem(serial, sig)
            self.coins.remove((serial, sig))


def demo():
    print("\n=== E-CASH DEMO ===\n")

    bank = Bank("Bank")
    alice = Client("Alice")
    shop = Merchant("Shop")

    headers = ["Участник", "Секретные ключи", "Публичные ключи"]
    table = [[bank.name, f"p = {bank.p}, q = {bank.q}, c = {bank.c}", f"n = {bank.n}, d = {bank.d}"]]
    print(tabulate(table, headers=headers, tablefmt="minimal"))

    print("\nПроцесс покупки:")
    serial, sig = alice.get_signed_coin(bank)  # Клиент получает подписанную купюру от банка
    alice.pay(shop)                            # Клиент отдаёт купюру магазину
    shop.redeem(bank)                          # Магазин сдаёт купюру в банк

    print("\nПопытка повторного использования:")
    shop.receive(serial, sig, alice)
    shop.redeem(bank)


if __name__ == "__main__":
    demo()

"""
=== E-CASH DEMO ===

Участник    Секретные ключи                           Публичные ключи
----------  ----------------------------------------  ----------------------------------
Bank        p = 983771, q = 678641, c = 612060030369  n = 667627335211, d = 414080040129

Процесс покупки:
[Alice] Получена анонимная купюра <437424897849, 120352931330>
[Shop] Получена купюра <437424897849, 120352931330> от Alice
[Bank] Купюра <437424897849, 120352931330> принята

Попытка повторного использования:
[Shop] Получена купюра <437424897849, 120352931330> от Alice
[Bank] Ошибка: Купюра <437424897849, 120352931330> уже использована
"""
