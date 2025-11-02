from math_utils import find_all_primitive_roots, print_powers_table


p = int(input("Введите простое p: "))
gens = find_all_primitive_roots(p)

print(f"\nДопустимые g для p = {p}: {gens}")  # Для p = 11 ответ: 2, 6, 7, 8
print_powers_table(p)
