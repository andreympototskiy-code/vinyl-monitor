# Vinyl Monitor

Автоматический мониторинг виниловых пластинок с уведомлениями в Telegram.

## 🎵 Возможности

- **Мониторинг korobkavinyla.ru**: каталог и раздел со скидками
- **Мониторинг vinyltap.co.uk**: новые и предстоящие релизы
- **Мониторинг Авито**: поиск по ключевым словам
- **Дедупликация**: исключение повторяющихся позиций
- **Уведомления в Telegram**: мгновенные уведомления о новых поступлениях
- **Гибкие интервалы**: разные интервалы мониторинга для разных сайтов

## 🚀 Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd vinyl-monitor
```

2. Создайте виртуальное окружение:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Установите браузеры Playwright:
```bash
playwright install chromium
```

5. Настройте переменные окружения:
```bash
cp .env.example .env
# Отредактируйте .env файл
```

## ⚙️ Конфигурация

### Переменные окружения (.env)

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
CATALOG_URL=https://korobkavinyla.ru/catalog
KOROBKA_SALE_URL=https://korobkavinyla.ru/catalog?tfc_sort%5B771567999%5D=created:desc&tfc_quantity%5B771567999%5D=y&tfc_storepartuid%5B771567999%5D=Sale&tfc_div=:::
VINYLTAP_URLS=https://vinyltap.co.uk/collections/new-releases,https://vinyltap.co.uk/collections/upcoming-releases
STATE_PATH=/path/to/state.json
USE_PLAYWRIGHT=true
```

### Конфигурация Авито (avito_config.json)

```json
{
  "search_queries": [
    "poets of the fall lp",
    "harry potter lp",
    "Снежная королева lp",
    "beatles vinyl"
  ],
  "base_url": "https://www.avito.ru/sankt_peterburg_i_lo/",
  "category": "kollektsionirovanie",
  "monitor_interval_hours": 6,
  "enabled": true
}
```

## 🎯 Использование

### Запуск мониторинга

```bash
python3 vinyl_monitor.py
```

### Управление поисковыми запросами Авито

```bash
python3 manage_avito.py
```

## 📊 Интервалы мониторинга

- **korobkavinyla.ru**: каждые 24 часа
- **vinyltap.co.uk**: каждые 3 часа
- **Авито**: каждые 6 часов

## 🧪 Тестирование

Запуск тестов:
```bash
pytest tests/ -v
```

Проверка стиля кода:
```bash
flake8 .
```

Запуск с покрытием кода:
```bash
pytest tests/ --cov=vinyl_monitor --cov-report=html
```

## 📁 Структура проекта

```
vinyl-monitor/
├── .github/
│   └── workflows/
│       └── tests.yml          # CI/CD pipeline
├── tests/
│   ├── __init__.py
│   └── test_vinyl_monitor.py  # Тесты
├── vinyl_monitor.py           # Основной модуль
├── manage_avito.py            # Управление Авито
├── avito_config.json          # Конфигурация Авито
├── state.json                 # Состояние мониторинга
├── requirements.txt           # Зависимости
├── pytest.ini               # Конфигурация pytest
├── .flake8                   # Конфигурация flake8
└── README.md                 # Документация
```

## 🔧 CI/CD

Проект настроен для автоматического тестирования через GitHub Actions:

- **Проверка стиля кода** (flake8)
- **Запуск тестов** (pytest)
- **Покрытие кода** (pytest-cov)
- **Установка браузеров Playwright**

## 📝 Логирование

Все действия логируются в консоль:
- Количество найденных позиций
- Результаты дедупликации
- Статус отправки уведомлений
- Ошибки и предупреждения

## 🛠️ Разработка

### Добавление новых сайтов

1. Создайте функцию скрапинга в `vinyl_monitor.py`
2. Добавьте вызов в функцию `main()`
3. Напишите тесты для новой функциональности
4. Обновите документацию

### Добавление новых тестов

```python
def test_new_functionality():
    """Описание теста"""
    # Arrange
    # Act
    # Assert
    pass
```

## 📄 Лицензия

MIT License

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для новой функции
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи
2. Убедитесь в правильности конфигурации
3. Проверьте доступность сайтов
4. Создайте Issue в репозитории
# Vinyl Monitor - Automated Testing


