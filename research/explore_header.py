"""
Поля плейлиста в шапке ответа browse.

Что делает скрипт:
   Читает сохранённый ответ browse (файл response_<ID>.json).
   Находит блок шапки по ключу secondSubtitle (в нём лежит число треков).
   Печатает пути и значения: название, владелец, обложка, строка с числом треков.

"""
import json
import sys
import re

if len(sys.argv) < 2:
    sys.exit("Укажите файл ответа. Пример: python research/explore_header.py response_PLHHFkCbk5F28.json")

with open(sys.argv[1], encoding="utf-8") as f:
    data = json.load(f)


def parents_with_key(node, wanted):
    """Находит словари, в которых есть ключ wanted."""
    if isinstance(node, dict):
        if wanted in node:
            yield node
        for value in node.values():
            yield from parents_with_key(value, wanted)
    elif isinstance(node, list):
        for value in node:
            yield from parents_with_key(value, wanted)


def leaves(node, path=""):
    """Отдаёт путь и значение каждого конечного элемента (строки, числа)."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from leaves(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from leaves(value, f"{path}[{index}]")
    else:
        yield path, node

def all_nodes(node, path=""):
    """Отдаёт путь, имя ключа и значение каждого элемента внутри словарей и списков."""
    if isinstance(node, dict):
        for key, value in node.items():
            current = f"{path}.{key}"
            yield current, key, value
            yield from all_nodes(value, current)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from all_nodes(value, f"{path}[{index}]")

WANTED = ("text", "url", "width", "height", "browseId", "playlistId")
SKIP = ("menu", "Button", "button") 

headers = list(parents_with_key(data, "secondSubtitle"))
print("Найдено блоков шапки:", len(headers))

if not headers:
    # Запасной режим: шапки с secondSubtitle нет (так у автоплейлиста альбома).
    print("Ключи верхнего уровня:", list(data.keys()))
    top_header = data.get("header")
    if top_header:
        print("Блок header:", list(top_header.keys()))
        for name, node in top_header.items():
            print(f"\n--- {name}: {list(node.keys()) if isinstance(node, dict) else type(node).__name__}")
            for path, value in leaves(node):
                key = path.rsplit(".", 1)[-1].split("[")[0]
                if key in WANTED and not any(word in path for word in SKIP):
                    print(f"{path} = {value}")

if headers:
    header = headers[0]
    print("Ключи блока шапки:", list(header.keys()))
    print()
    for path, value in leaves(header):
        key = path.rsplit(".", 1)[-1].split("[")[0]
        if key in WANTED and not any(word in path for word in SKIP):
            print(f"{path} = {value}")
else:
    print("Ключи верхнего уровня:", list(data.keys()))
 
    print("\n=== Ключи со словом 'header' (путь и ключи внутри) ===")
    found = 0
    for path, key, value in all_nodes(data):
        if re.search("header", key, re.IGNORECASE):
            inside = list(value.keys()) if isinstance(value, dict) else type(value).__name__
            print(f"{path} -> {inside}")
            found += 1
    if not found:
        print("(таких ключей нет)")
 
    print("\n=== Первые 10 названий (ключ title с текстом) ===")
    shown = 0
    for path, key, value in all_nodes(data):
        if key == "title" and isinstance(value, dict) and "runs" in value:
            text = "".join(run.get("text", "") for run in value["runs"])
            print(f"{path} = {text}")
            shown += 1
            if shown >= 10:
                break
    if not shown:
        print("(названий не найдено)")
 
    print("\n=== Первые 10 строк subtitle или strapline ===")
    shown = 0
    for path, key, value in all_nodes(data):
        if key in ("subtitle", "straplineTextOne", "secondSubtitle") and isinstance(value, dict) and "runs" in value:
            text = "".join(run.get("text", "") for run in value["runs"])
            print(f"{path} = {text}")
            shown += 1
            if shown >= 10:
                break
    if not shown:
        print("(строк не найдено)")