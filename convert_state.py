#!/usr/bin/env python3
import json
from datetime import datetime


def convert_state():
    """Конвертирует state.json из старого формата в новый"""

    # Читаем старый файл
    with open('state.json', 'r') as f:
        data = json.load(f)

    old_ids = data.get('known_ids', [])
    print(f'Найдено {len(old_ids)} позиций в старом формате')

    # Создаем новый формат
    new_data = {
        "known_items": {}
    }

    current_time = datetime.now().isoformat()

    for item_id in old_ids:
        if item_id.startswith('http'):
            # Определяем источник
            if 'korobkavinyla.ru' in item_id:
                source = 'korobkavinyla.ru'
            elif 'vinyltap.co.uk' in item_id:
                source = 'vinyltap.co.uk'
            else:
                source = 'unknown'

            new_data["known_items"][item_id] = {
                "added_at": current_time,
                "title": "",
                "source": source
            }

    # Сохраняем в новом формате
    with open('state.json', 'w') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f'✅ Конвертировано {len(new_data["known_items"])} позиций в новый формат')


if __name__ == '__main__':
    convert_state()
