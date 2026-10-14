"""

Что делает скрипт:
  Читает файл ответа, который сохранил explore_response.py.
  Находит все строки вида "<число> songs / tracks / videos".
  Для каждой печатает текст вокруг, чтобы понять, к чему относится число.

"""
import re
import sys

if len(sys.argv) < 2:
    sys.exit("Укажите файл ответа. Пример: python research/find_counts.py response_PLHHFkCbk5F28.json")

with open(sys.argv[1], encoding="utf-8") as f:
    text = f.read()

pattern = re.compile(r"\d+ (?:songs?|tracks?|videos?)")
matches = list(pattern.finditer(text))

for match in matches:
    start = max(0, match.start() - 150)  
    print(f"позиция {match.start()}: ...{text[start:match.end() + 40]}")
    print()

print("Всего совпадений:", len(matches))