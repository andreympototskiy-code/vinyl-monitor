#!/usr/bin/env python3
"""
Скрипт для управления конфигурацией мониторинга Авито
"""
import json
import sys
from pathlib import Path

CONFIG_PATH = Path("avito_config.json")

def load_config():
    """Загрузить конфигурацию"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(config):
    """Сохранить конфигурацию"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def show_config():
    """Показать текущую конфигурацию"""
    config = load_config()
    print("📋 Текущая конфигурация Авито:")
    print(f"  Включен: {config.get('enabled', True)}")
    print(f"  Интервал: {config.get('monitor_interval_hours', 6)} часов")
    print(f"  Базовый URL: {config.get('base_url', 'https://www.avito.ru/sankt_peterburg_i_lo')}")
    print(f"  Поисковые запросы:")
    for i, query in enumerate(config.get('search_queries', []), 1):
        print(f"    {i}. {query}")

def add_query(query):
    """Добавить поисковый запрос"""
    config = load_config()
    if 'search_queries' not in config:
        config['search_queries'] = []
    
    if query not in config['search_queries']:
        config['search_queries'].append(query)
        save_config(config)
        print(f"✅ Добавлен запрос: {query}")
    else:
        print(f"⚠️ Запрос уже существует: {query}")

def remove_query(query):
    """Удалить поисковый запрос"""
    config = load_config()
    if 'search_queries' in config and query in config['search_queries']:
        config['search_queries'].remove(query)
        save_config(config)
        print(f"✅ Удален запрос: {query}")
    else:
        print(f"⚠️ Запрос не найден: {query}")

def set_interval(hours):
    """Установить интервал мониторинга"""
    config = load_config()
    config['monitor_interval_hours'] = int(hours)
    save_config(config)
    print(f"✅ Интервал установлен: {hours} часов")

def toggle_enabled():
    """Переключить включение/выключение"""
    config = load_config()
    current = config.get('enabled', True)
    config['enabled'] = not current
    save_config(config)
    status = "включен" if config['enabled'] else "выключен"
    print(f"✅ Авито {status}")

def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python manage_avito.py show                    - показать конфигурацию")
        print("  python manage_avito.py add <запрос>            - добавить поисковый запрос")
        print("  python manage_avito.py remove <запрос>         - удалить поисковый запрос")
        print("  python manage_avito.py interval <часы>         - установить интервал")
        print("  python manage_avito.py toggle                  - включить/выключить")
        return
    
    command = sys.argv[1]
    
    if command == "show":
        show_config()
    elif command == "add" and len(sys.argv) > 2:
        add_query(sys.argv[2])
    elif command == "remove" and len(sys.argv) > 2:
        remove_query(sys.argv[2])
    elif command == "interval" and len(sys.argv) > 2:
        set_interval(sys.argv[2])
    elif command == "toggle":
        toggle_enabled()
    else:
        print("❌ Неверная команда")

if __name__ == "__main__":
    main()
