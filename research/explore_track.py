"""

Что делает скрипт:
   Читает сохранённый ответ browse (файл response_<ID>.json).
   Для первой записи списка печатает пути и значения: тексты, идентификаторы, обложки.
   Для каждой записи печатает короткую строку: номер, videoId, тип видео, первые тексты.

"""
import json
import sys

if len(sys.argv) < 2:
    sys.exit("Укажите файл ответа. Пример: python research/explore_track.py response_PLHHFkCbk5F28.json")

with open(sys.argv[1], encoding="utf-8") as f:
    data = json.load(f)


def find_items(node):
    """Находит все записи списка (musicResponsiveListItemRenderer)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "musicResponsiveListItemRenderer":
                yield value
            else:
                yield from find_items(value)
    elif isinstance(node, list):
        for value in node:
            yield from find_items(value)


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


WANTED = ("text", "videoId", "playlistId", "browseId", "musicVideoType", "url", "width", "height")

items = list(find_items(data))
print("Записей:", len(items))
if not items:
    
    sys.exit("Записей списка нет. Разбирать нечего.")

print("\n=== Первая запись: пути и значения ===")
for path, value in leaves(items[0]):
    key = path.rsplit(".", 1)[-1].split("[")[0]
    if key in WANTED:
        print(f"{path} = {value}")

print("\n=== Все записи кратко ===")
for number, item in enumerate(items, start=1):
    pairs = list(leaves(item))
    video_id = next((v for p, v in pairs if p.endswith(".videoId")), None)
    video_type = next((v for p, v in pairs if p.endswith(".musicVideoType")), None)
    texts = [v for p, v in pairs if p.endswith(".text")][:4]
    print(f"{number:3d} {video_id} {video_type} {texts}")

print("\n=== Записи, у которых колонка артиста состоит из нескольких частей ===")
for number, item in enumerate(items, start=1):
    columns = item.get("flexColumns", [])
    if len(columns) > 1:
        runs = columns[1]["musicResponsiveListItemFlexColumnRenderer"].get("text", {}).get("runs", [])
        if len(runs) > 1:
            print(number, [run.get("text") for run in runs])

print("\n=== Сколько записей каждого типа ===")
from collections import Counter  
types = Counter(next((v for p, v in leaves(item) if p.endswith(".musicVideoType")), None) for item in items)
for video_type, count in types.most_common():
    print(f"{count:4d}  {video_type}")