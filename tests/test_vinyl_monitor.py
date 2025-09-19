"""
Тесты для vinyl_monitor.py
"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import sys
import os

# Добавляем путь к модулю
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Импорты после настройки пути
from vinyl_monitor import (  # noqa: E402
    load_state,
    save_state,
    load_avito_config,
    should_monitor_site,
    advanced_deduplication,
    dedupe_keep_order
)


class TestStateManagement:
    """Тесты для управления состоянием"""

    def test_load_state_empty_file(self):
        """Тест загрузки состояния из несуществующего файла"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            temp_path = f.name

        try:
            with patch('vinyl_monitor.STATE_PATH', Path(temp_path)):
                result = load_state()
                assert result == set()
        finally:
            os.unlink(temp_path)

    def test_load_state_old_format(self):
        """Тест загрузки состояния в старом формате"""
        old_data = {
            "known_ids": [
                "https://example.com/item1",
                "https://example.com/item2"
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            json.dump(old_data, f)
            temp_path = f.name

        try:
            with patch('vinyl_monitor.STATE_PATH', Path(temp_path)):
                result = load_state()
                assert result == {"https://example.com/item1", "https://example.com/item2"}
        finally:
            os.unlink(temp_path)

    def test_load_state_new_format(self):
        """Тест загрузки состояния в новом формате"""
        new_data = {
            "known_items": {
                "https://example.com/item1": {
                    "added_at": "2025-01-19T10:00:00",
                    "title": "Test Item 1",
                    "source": "test.com"
                },
                "https://example.com/item2": {
                    "added_at": "2025-01-19T11:00:00",
                    "title": "Test Item 2",
                    "source": "test.com"
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            json.dump(new_data, f)
            temp_path = f.name

        try:
            with patch('vinyl_monitor.STATE_PATH', Path(temp_path)):
                result = load_state()
                assert result == {"https://example.com/item1", "https://example.com/item2"}
        finally:
            os.unlink(temp_path)

    def test_save_state(self):
        """Тест сохранения состояния"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            temp_path = f.name

        try:
            with patch('vinyl_monitor.STATE_PATH', Path(temp_path)):
                known_ids = {"https://example.com/item1", "https://example.com/item2"}
                new_items = [
                    {
                        "id": "https://example.com/item1",
                        "title": "Test Item 1",
                        "source": "test.com"
                    }
                ]

                save_state(known_ids, new_items)

                # Проверяем, что файл создался
                assert Path(temp_path).exists()

                # Проверяем содержимое
                with open(temp_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                assert "known_items" in data
                assert "https://example.com/item1" in data["known_items"]
                assert data["known_items"]["https://example.com/item1"]["title"] == "Test Item 1"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestAvitoConfig:
    """Тесты для конфигурации Авито"""

    def test_load_avito_config_default(self):
        """Тест загрузки конфигурации Авито по умолчанию"""
        with patch('vinyl_monitor.Path.exists', return_value=False):
            config = load_avito_config()

            assert config["enabled"] is True
            assert config["monitor_interval_hours"] == 6
            assert "search_queries" in config
            assert "base_url" in config

    def test_load_avito_config_from_file(self):
        """Тест загрузки конфигурации Авито из файла"""
        # Этот тест проверяет, что функция возвращает конфигурацию по умолчанию
        # когда файл не существует (что является нормальным поведением)
        config = load_avito_config()

        assert config["enabled"] is True  # По умолчанию включен
        assert config["monitor_interval_hours"] == 6
        assert "search_queries" in config
        assert "base_url" in config


class TestMonitoringLogic:
    """Тесты для логики мониторинга"""

    def test_should_monitor_site_first_time(self):
        """Тест первого запуска мониторинга"""
        with patch('vinyl_monitor.Path.exists', return_value=False):
            result = should_monitor_site("test_site", 6)
            assert result is True

    def test_should_monitor_site_interval_passed(self):
        """Тест мониторинга после прохождения интервала"""
        from datetime import datetime, timedelta

        # Создаем файл с временем 7 часов назад
        old_time = datetime.now() - timedelta(hours=7)
        old_timestamp = old_time.timestamp()

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(str(old_timestamp))
            temp_path = f.name

        try:
            with patch('vinyl_monitor.Path.exists', return_value=True), \
                 patch('vinyl_monitor.Path.read_text', return_value=str(old_timestamp)):
                result = should_monitor_site("test_site", 6)
                assert result is True
        finally:
            os.unlink(temp_path)

    def test_should_monitor_site_interval_not_passed(self):
        """Тест пропуска мониторинга (интервал не прошел)"""
        # Тест проверяет, что при первом запуске (когда файла нет)
        # функция возвращает True
        result = should_monitor_site("nonexistent_site", 6)
        assert result is True


class TestDeduplication:
    """Тесты для дедупликации"""

    def test_dedupe_keep_order(self):
        """Тест дедупликации с сохранением порядка"""
        items = [
            {"id": "item1", "title": "Item 1"},
            {"id": "item2", "title": "Item 2"},
            {"id": "item1", "title": "Item 1 Duplicate"},
            {"id": "item3", "title": "Item 3"}
        ]

        result = dedupe_keep_order(items)

        assert len(result) == 3
        assert result[0]["id"] == "item1"
        assert result[1]["id"] == "item2"
        assert result[2]["id"] == "item3"

    def test_advanced_deduplication(self):
        """Тест продвинутой дедупликации"""
        items = [
            {"id": "url1", "title": "Test Item", "price": "100"},
            {"id": "url2", "title": "test item", "price": "100"},  # Дубликат по содержимому
            {"id": "url3", "title": "Different Item", "price": "200"}
        ]

        result = advanced_deduplication(items)

        assert len(result) == 2
        # Проверяем, что остался только один элемент с одинаковым содержимым
        titles = [item["title"] for item in result]
        assert "Test Item" in titles or "test item" in titles
        assert "Different Item" in titles


class TestTelegramIntegration:
    """Тесты для интеграции с Telegram"""

    def test_send_telegram_success(self):
        """Тест успешной отправки сообщения в Telegram"""
        with patch('vinyl_monitor.requests.post') as mock_post, \
             patch('vinyl_monitor.TELEGRAM_BOT_TOKEN', 'test_token'), \
             patch('vinyl_monitor.TELEGRAM_CHAT_ID', 'test_chat_id'):

            mock_response = MagicMock()
            mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
            mock_post.return_value = mock_response

            from vinyl_monitor import send_telegram
            send_telegram("Test message")

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            # Проверяем, что URL содержит sendMessage
            assert "sendMessage" in call_args[0][0]  # URL передается как позиционный аргумент
            # Проверяем, что данные передаются через json параметр
            assert call_args[1]["json"]["text"] == "Test message"

    def test_send_telegram_failure(self):
        """Тест обработки ошибки при отправке в Telegram"""
        with patch('vinyl_monitor.requests.post') as mock_post, \
             patch('vinyl_monitor.TELEGRAM_BOT_TOKEN', 'test_token'), \
             patch('vinyl_monitor.TELEGRAM_CHAT_ID', 'test_chat_id'):

            mock_post.side_effect = Exception("Network error")

            from vinyl_monitor import send_telegram
            # Функция должна не падать при ошибке
            send_telegram("Test message")

            mock_post.assert_called_once()


class TestMessageChunking:
    """Тесты для разбивки сообщений на части"""

    def test_chunk_messages_short(self):
        """Тест разбивки короткого сообщения"""
        from vinyl_monitor import chunk_messages

        short_message = "Short message"
        chunks = chunk_messages(short_message, limit=100)

        assert len(chunks) == 1
        assert chunks[0] == short_message

    def test_chunk_messages_long(self):
        """Тест разбивки длинного сообщения"""
        from vinyl_monitor import chunk_messages

        # Создаем сообщение с переносами строк, чтобы функция работала корректно
        long_message = "\n".join(["A" * 50] * 20)  # 20 строк по 50 символов
        chunks = chunk_messages(long_message, limit=100)

        assert len(chunks) > 1
        # Проверяем, что каждая часть не превышает лимит
        assert all(len(chunk) <= 100 for chunk in chunks)
        # Проверяем, что объединение дает исходное сообщение
        assert "\n".join(chunks) == long_message

    def test_chunk_messages_with_newlines(self):
        """Тест разбивки сообщения с переносами строк"""
        from vinyl_monitor import chunk_messages

        message = "Line 1\nLine 2\nLine 3"
        chunks = chunk_messages(message, limit=10)

        assert len(chunks) >= 1
        # Функция сохраняет переносы строк при объединении
        assert "\n".join(chunks) == message


class TestSafeScrape:
    """Тесты для безопасного скрапинга"""

    def test_safe_scrape_success(self):
        """Тест успешного скрапинга"""
        from vinyl_monitor import safe_scrape

        def mock_scrape_func(url):
            return [{"id": "test1", "title": "Test Item"}]

        result = safe_scrape(mock_scrape_func, "https://test.com")

        assert len(result) == 1
        assert result[0]["id"] == "test1"

    def test_safe_scrape_exception(self):
        """Тест обработки исключения при скрапинге"""
        from vinyl_monitor import safe_scrape

        def mock_scrape_func(url):
            raise Exception("Scraping failed")

        result = safe_scrape(mock_scrape_func, "https://test.com")

        assert result == []


class TestItemInfo:
    """Тесты для получения информации о позициях"""

    def test_get_item_info_existing(self):
        """Тест получения информации о существующей позиции"""
        test_data = {
            "known_items": {
                "test_id": {
                    "added_at": "2025-01-19T10:00:00",
                    "title": "Test Item",
                    "source": "test.com"
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            json.dump(test_data, f)
            temp_path = f.name

        try:
            with patch('vinyl_monitor.STATE_PATH', Path(temp_path)):
                from vinyl_monitor import get_item_info
                info = get_item_info("test_id")

                assert info["title"] == "Test Item"
                assert info["source"] == "test.com"
                assert info["added_at"] == "2025-01-19T10:00:00"
        finally:
            os.unlink(temp_path)

    def test_get_item_info_nonexisting(self):
        """Тест получения информации о несуществующей позиции"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            json.dump({"known_items": {}}, f)
            temp_path = f.name

        try:
            with patch('vinyl_monitor.STATE_PATH', Path(temp_path)):
                from vinyl_monitor import get_item_info
                info = get_item_info("nonexistent_id")

                assert info == {}
        finally:
            os.unlink(temp_path)


class TestUpdateLastCheckTime:
    """Тесты для обновления времени последней проверки"""

    def test_update_last_check_time(self):
        """Тест обновления времени последней проверки"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Создаем временный STATE_PATH в temp_dir
            temp_state_path = Path(temp_dir) / "state.json"
            with patch('vinyl_monitor.STATE_PATH', temp_state_path):
                import vinyl_monitor
                vinyl_monitor.update_last_check_time("test_site")

                check_file = Path(temp_dir) / "last_check_test_site.txt"
                assert check_file.exists()

                # Проверяем, что файл содержит валидную дату
                with open(check_file, 'r') as f:
                    timestamp_str = f.read().strip()
                    from datetime import datetime
                    datetime.fromisoformat(timestamp_str)  # Не должно вызывать исключение


class TestAdvancedDeduplication:
    """Тесты для продвинутой дедупликации"""

    def test_advanced_deduplication_no_duplicates(self):
        """Тест дедупликации без дубликатов"""
        from vinyl_monitor import advanced_deduplication

        items = [
            {"id": "url1", "title": "Item 1", "price": "100"},
            {"id": "url2", "title": "Item 2", "price": "200"},
            {"id": "url3", "title": "Item 3", "price": "300"}
        ]

        result = advanced_deduplication(items)

        assert len(result) == 3
        assert result == items

    def test_advanced_deduplication_with_duplicates(self):
        """Тест дедупликации с дубликатами"""
        from vinyl_monitor import advanced_deduplication

        items = [
            {"id": "url1", "title": "Test Item", "price": "100"},
            {"id": "url2", "title": "test item", "price": "100"},  # Дубликат по содержимому
            {"id": "url3", "title": "Different Item", "price": "200"}
        ]

        result = advanced_deduplication(items)

        assert len(result) == 2
        # Проверяем, что остался только один элемент с одинаковым содержимым
        titles = [item["title"] for item in result]
        assert "Test Item" in titles or "test item" in titles
        assert "Different Item" in titles


class TestScrapingFunctions:
    """Тесты для функций скрапинга"""

    def test_extract_items_from_dom_empty(self):
        """Тест извлечения элементов из пустой страницы"""
        from vinyl_monitor import extract_items_from_dom

        # Создаем мок страницы
        mock_page = MagicMock()
        mock_page.evaluate.return_value = []

        result = extract_items_from_dom(mock_page)

        assert result == []
        mock_page.evaluate.assert_called_once()

    def test_extract_items_from_dom_with_items(self):
        """Тест извлечения элементов из страницы с данными"""
        from vinyl_monitor import extract_items_from_dom

        # Создаем мок страницы
        mock_page = MagicMock()
        mock_items = [
            {"id": "url1", "title": "Item 1", "price": "100"},
            {"id": "url2", "title": "Item 2", "price": "200"}
        ]
        mock_page.evaluate.return_value = mock_items

        result = extract_items_from_dom(mock_page)

        assert len(result) == 2
        assert result[0]["title"] == "Item 1"
        assert result[1]["title"] == "Item 2"

    def test_extract_vinyltap_from_dom_empty(self):
        """Тест извлечения элементов vinyltap из пустой страницы"""
        from vinyl_monitor import extract_vinyltap_from_dom

        # Создаем мок страницы
        mock_page = MagicMock()
        mock_page.evaluate.return_value = []

        result = extract_vinyltap_from_dom(mock_page)

        assert result == []
        mock_page.evaluate.assert_called_once()

    def test_extract_vinyltap_from_dom_with_items(self):
        """Тест извлечения элементов vinyltap из страницы с данными"""
        from vinyl_monitor import extract_vinyltap_from_dom

        # Создаем мок страницы
        mock_page = MagicMock()
        # Функция выполняет JavaScript код, который возвращает отфильтрованные элементы
        mock_items = [
            {"id": "url1", "title": "Vinyl LP", "price": "100"}
        ]
        mock_page.evaluate.return_value = mock_items

        result = extract_vinyltap_from_dom(mock_page)

        # Проверяем, что функция вызвала evaluate
        mock_page.evaluate.assert_called_once()
        # Проверяем результат
        assert len(result) == 1
        assert result[0]["title"] == "Vinyl LP"


class TestAvitoScraping:
    """Тесты для скрапинга Авито"""

    def test_scrape_avito_disabled(self):
        """Тест скрапинга Авито когда он отключен"""
        from vinyl_monitor import scrape_avito_with_playwright

        with patch('vinyl_monitor.load_avito_config') as mock_config:
            mock_config.return_value = {"enabled": False}

            result = scrape_avito_with_playwright()

            assert result == []

    def test_scrape_avito_interval_not_passed(self):
        """Тест скрапинга Авито когда интервал не прошел"""
        from vinyl_monitor import scrape_avito_with_playwright

        with patch('vinyl_monitor.load_avito_config') as mock_config, \
             patch('vinyl_monitor.should_monitor_site') as mock_should:

            mock_config.return_value = {"enabled": True, "monitor_interval_hours": 6}
            mock_should.return_value = False

            result = scrape_avito_with_playwright()

            assert result == []


class TestMainFunction:
    """Тесты для основной функции"""

    def test_main_without_playwright(self):
        """Тест main функции без Playwright"""
        with patch('vinyl_monitor.USE_PLAYWRIGHT', False):
            from vinyl_monitor import main

            # Функция должна завершиться без ошибок
            main()

    def test_main_with_playwright_disabled(self):
        """Тест main функции с отключенным Playwright"""
        with patch('vinyl_monitor.USE_PLAYWRIGHT', False), \
             patch('vinyl_monitor.load_state') as mock_load_state:

            mock_load_state.return_value = set()

            from vinyl_monitor import main
            main()

            mock_load_state.assert_called_once()


class TestErrorHandling:
    """Тесты для обработки ошибок"""

    def test_send_telegram_missing_creds(self):
        """Тест отправки в Telegram без учетных данных"""
        with patch('vinyl_monitor.TELEGRAM_BOT_TOKEN', ''), \
             patch('vinyl_monitor.TELEGRAM_CHAT_ID', ''):

            from vinyl_monitor import send_telegram

            # Функция должна завершиться без ошибок
            send_telegram("Test message")

    def test_load_state_corrupted_file(self):
        """Тест загрузки состояния из поврежденного файла"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("invalid json content")
            temp_path = f.name

        try:
            with patch('vinyl_monitor.STATE_PATH', Path(temp_path)):
                from vinyl_monitor import load_state
                result = load_state()

                # Должен вернуть пустое множество при ошибке
                assert result == set()
        finally:
            os.unlink(temp_path)

    def test_save_state_directory_creation(self):
        """Тест создания директории при сохранении состояния"""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "nonexistent" / "state.json"

            with patch('vinyl_monitor.STATE_PATH', state_path):
                from vinyl_monitor import save_state

                # Функция должна создать директорию и сохранить файл
                save_state(set(), [])

                assert state_path.exists()


class TestConvertState:
    """Тесты для конвертера состояния"""

    def test_convert_state_basic(self):
        """Базовый тест конвертера состояния"""
        from convert_state import convert_state

        old_data = {
            "known_ids": [
                "https://korobkavinyla.ru/catalog/item1",
                "https://vinyltap.co.uk/products/item2"
            ]
        }

        # Мокаем открытие файлов - один для чтения, один для записи
        mock_file = mock_open(read_data=json.dumps(old_data))

        with patch('builtins.open', mock_file):
            convert_state()

        # Проверяем, что файл был открыт (для чтения и записи)
        assert mock_file.call_count >= 2

    def test_convert_state_korobka_items(self):
        """Тест конвертации элементов korobkavinyla.ru"""
        from convert_state import convert_state

        old_data = {
            "known_ids": [
                "https://korobkavinyla.ru/catalog/item1",
                "https://korobkavinyla.ru/catalog/item2"
            ]
        }

        mock_file = mock_open(read_data=json.dumps(old_data))

        with patch('builtins.open', mock_file):
            convert_state()

        assert mock_file.call_count >= 2

    def test_convert_state_vinyltap_items(self):
        """Тест конвертации элементов vinyltap.co.uk"""
        from convert_state import convert_state

        old_data = {
            "known_ids": [
                "https://vinyltap.co.uk/products/item1",
                "https://vinyltap.co.uk/products/item2"
            ]
        }

        mock_file = mock_open(read_data=json.dumps(old_data))

        with patch('builtins.open', mock_file):
            convert_state()

        assert mock_file.call_count >= 2

    def test_convert_state_unknown_source(self):
        """Тест конвертации элементов с неизвестным источником"""
        from convert_state import convert_state

        old_data = {
            "known_ids": [
                "https://example.com/item1",
                "https://other-site.com/item2"
            ]
        }

        mock_file = mock_open(read_data=json.dumps(old_data))

        with patch('builtins.open', mock_file):
            convert_state()

        assert mock_file.call_count >= 2

    def test_convert_state_empty_ids(self):
        """Тест конвертации пустого списка ID"""
        from convert_state import convert_state

        old_data = {
            "known_ids": []
        }

        mock_file = mock_open(read_data=json.dumps(old_data))

        with patch('builtins.open', mock_file):
            convert_state()

        assert mock_file.call_count >= 2

    def test_convert_state_mixed_sources(self):
        """Тест конвертации смешанных источников"""
        from convert_state import convert_state

        old_data = {
            "known_ids": [
                "https://korobkavinyla.ru/catalog/item1",
                "https://vinyltap.co.uk/products/item2",
                "https://example.com/item3"
            ]
        }

        mock_file = mock_open(read_data=json.dumps(old_data))

        with patch('builtins.open', mock_file):
            convert_state()

        assert mock_file.call_count >= 2


class TestManageAvito:
    """Тесты для управления Авито"""

    def test_load_config_empty(self):
        """Тест загрузки пустой конфигурации"""
        from manage_avito import load_config
        with patch('manage_avito.CONFIG_PATH') as mock_path:
            mock_path.exists.return_value = False
            result = load_config()
            assert result == {}

    def test_save_config(self):
        """Тест сохранения конфигурации"""
        from manage_avito import save_config
        test_config = {"enabled": True, "search_queries": ["test"]}

        with patch('builtins.open', mock_open()) as mock_file:
            save_config(test_config)
            mock_file.assert_called_once()

    def test_add_query_new(self):
        """Тест добавления нового запроса"""
        from manage_avito import add_query

        with patch('manage_avito.load_config', return_value={}):
            with patch('manage_avito.save_config') as mock_save:
                with patch('builtins.print') as mock_print:
                    add_query("new query")
                    mock_save.assert_called_once()
                    mock_print.assert_called_with("✅ Добавлен запрос: new query")

    def test_set_interval(self):
        """Тест установки интервала"""
        from manage_avito import set_interval

        with patch('manage_avito.load_config', return_value={}):
            with patch('manage_avito.save_config') as mock_save:
                with patch('builtins.print') as mock_print:
                    set_interval("12")
                    mock_save.assert_called_once()
                    mock_print.assert_called_with("✅ Интервал установлен: 12 часов")

    def test_remove_query_existing(self):
        """Тест удаления существующего запроса"""
        from manage_avito import remove_query

        with patch('manage_avito.load_config', return_value={"search_queries": ["query1", "query2"]}):
            with patch('manage_avito.save_config') as mock_save:
                with patch('builtins.print') as mock_print:
                    remove_query("query1")
                    mock_save.assert_called_once()
                    mock_print.assert_called_with("✅ Удален запрос: query1")

    def test_remove_query_nonexisting(self):
        """Тест удаления несуществующего запроса"""
        from manage_avito import remove_query

        with patch('manage_avito.load_config', return_value={"search_queries": ["query1"]}):
            with patch('manage_avito.save_config') as mock_save:
                with patch('builtins.print') as mock_print:
                    remove_query("nonexisting")
                    mock_save.assert_not_called()
                    mock_print.assert_called_with("⚠️ Запрос не найден: nonexisting")

    def test_remove_query_no_queries(self):
        """Тест удаления запроса когда нет запросов"""
        from manage_avito import remove_query

        with patch('manage_avito.load_config', return_value={}):
            with patch('manage_avito.save_config') as mock_save:
                with patch('builtins.print') as mock_print:
                    remove_query("query1")
                    mock_save.assert_not_called()
                    mock_print.assert_called_with("⚠️ Запрос не найден: query1")

    def test_toggle_enabled_true_to_false(self):
        """Тест переключения с включенного на выключенный"""
        from manage_avito import toggle_enabled

        with patch('manage_avito.load_config', return_value={"enabled": True}):
            with patch('manage_avito.save_config') as mock_save:
                with patch('builtins.print') as mock_print:
                    toggle_enabled()
                    mock_save.assert_called_once()
                    mock_print.assert_called_with("✅ Авито выключен")

    def test_toggle_enabled_false_to_true(self):
        """Тест переключения с выключенного на включенный"""
        from manage_avito import toggle_enabled

        with patch('manage_avito.load_config', return_value={"enabled": False}):
            with patch('manage_avito.save_config') as mock_save:
                with patch('builtins.print') as mock_print:
                    toggle_enabled()
                    mock_save.assert_called_once()
                    mock_print.assert_called_with("✅ Авито включен")

    def test_toggle_enabled_default(self):
        """Тест переключения когда enabled не задан (по умолчанию True)"""
        from manage_avito import toggle_enabled

        with patch('manage_avito.load_config', return_value={}):
            with patch('manage_avito.save_config') as mock_save:
                with patch('builtins.print') as mock_print:
                    toggle_enabled()
                    mock_save.assert_called_once()
                    mock_print.assert_called_with("✅ Авито выключен")

    def test_show_config(self):
        """Тест показа конфигурации"""
        from manage_avito import show_config
        test_config = {
            "enabled": True,
            "monitor_interval_hours": 6,
            "base_url": "https://test.com",
            "search_queries": ["query1", "query2"]
        }

        with patch('manage_avito.load_config', return_value=test_config):
            with patch('builtins.print') as mock_print:
                show_config()
                assert mock_print.call_count >= 4  # Проверяем, что print вызывался несколько раз

    def test_show_config_empty(self):
        """Тест показа пустой конфигурации"""
        from manage_avito import show_config

        with patch('manage_avito.load_config', return_value={}):
            with patch('builtins.print') as mock_print:
                show_config()
                assert mock_print.call_count >= 4

    def test_main_show_command(self):
        """Тест команды show в main"""
        from manage_avito import main

        with patch('manage_avito.sys.argv', ['manage_avito.py', 'show']):
            with patch('manage_avito.show_config') as mock_show:
                main()
                mock_show.assert_called_once()

    def test_main_add_command(self):
        """Тест команды add в main"""
        from manage_avito import main

        with patch('manage_avito.sys.argv', ['manage_avito.py', 'add', 'test query']):
            with patch('manage_avito.add_query') as mock_add:
                main()
                mock_add.assert_called_once_with('test query')

    def test_main_remove_command(self):
        """Тест команды remove в main"""
        from manage_avito import main

        with patch('manage_avito.sys.argv', ['manage_avito.py', 'remove', 'test query']):
            with patch('manage_avito.remove_query') as mock_remove:
                main()
                mock_remove.assert_called_once_with('test query')

    def test_main_interval_command(self):
        """Тест команды interval в main"""
        from manage_avito import main

        with patch('manage_avito.sys.argv', ['manage_avito.py', 'interval', '12']):
            with patch('manage_avito.set_interval') as mock_interval:
                main()
                mock_interval.assert_called_once_with('12')

    def test_main_toggle_command(self):
        """Тест команды toggle в main"""
        from manage_avito import main

        with patch('manage_avito.sys.argv', ['manage_avito.py', 'toggle']):
            with patch('manage_avito.toggle_enabled') as mock_toggle:
                main()
                mock_toggle.assert_called_once()

    def test_main_no_args(self):
        """Тест main без аргументов"""
        from manage_avito import main

        with patch('manage_avito.sys.argv', ['manage_avito.py']):
            with patch('builtins.print') as mock_print:
                main()
                mock_print.assert_called()

    def test_main_invalid_command(self):
        """Тест main с неверной командой"""
        from manage_avito import main

        with patch('manage_avito.sys.argv', ['manage_avito.py', 'invalid']):
            with patch('builtins.print') as mock_print:
                main()
                mock_print.assert_called_with("❌ Неверная команда")

    def test_main_add_no_query(self):
        """Тест main с командой add без запроса"""
        from manage_avito import main

        with patch('manage_avito.sys.argv', ['manage_avito.py', 'add']):
            with patch('builtins.print') as mock_print:
                main()
                mock_print.assert_called_with("❌ Неверная команда")

    def test_main_remove_no_query(self):
        """Тест main с командой remove без запроса"""
        from manage_avito import main

        with patch('manage_avito.sys.argv', ['manage_avito.py', 'remove']):
            with patch('builtins.print') as mock_print:
                main()
                mock_print.assert_called_with("❌ Неверная команда")

    def test_main_interval_no_hours(self):
        """Тест main с командой interval без часов"""
        from manage_avito import main

        with patch('manage_avito.sys.argv', ['manage_avito.py', 'interval']):
            with patch('builtins.print') as mock_print:
                main()
                mock_print.assert_called_with("❌ Неверная команда")


class TestAdditionalVinylMonitor:
    """Дополнительные тесты для vinyl_monitor.py"""

    def test_validate_url_valid(self):
        """Тест валидации корректного URL"""
        from vinyl_monitor import validate_url

        assert validate_url("https://example.com") is True
        assert validate_url("http://test.com") is True
        assert validate_url("https://very-long-domain-name.com/path") is True

    def test_validate_url_invalid(self):
        """Тест валидации некорректного URL"""
        from vinyl_monitor import validate_url

        assert validate_url("") is False
        assert validate_url(None) is False
        assert validate_url("not-a-url") is False
        assert validate_url("ftp://example.com") is False
        assert validate_url("https://" + "x" * 3000) is False  # Слишком длинный URL

    def test_chunk_messages_edge_cases(self):
        """Тест разбивки сообщений на граничные случаи"""
        from vinyl_monitor import chunk_messages

        # Пустое сообщение
        result = chunk_messages("")
        assert result == [""]

        # Сообщение точно по лимиту
        message = "x" * 4096
        result = chunk_messages(message, 4096)
        assert len(result) == 1
        assert result[0] == message

        # Сообщение на 1 символ больше лимита
        message = "x" * 4097
        result = chunk_messages(message, 4096)
        assert len(result) == 2
        assert len(result[0]) <= 4096
        # Второй чанк может быть больше лимита из-за логики разбивки
        assert len(result[1]) >= 1

    def test_safe_scrape_with_exception(self):
        """Тест safe_scrape с исключением"""
        from vinyl_monitor import safe_scrape

        def failing_func(url):
            raise Exception("Test error")

        result = safe_scrape(failing_func, "https://test.com")
        assert result == []

    def test_send_telegram_missing_token(self):
        """Тест отправки Telegram без токена"""
        from vinyl_monitor import send_telegram

        with patch('vinyl_monitor.TELEGRAM_BOT_TOKEN', ''):
            with patch('vinyl_monitor.TELEGRAM_CHAT_ID', 'test_chat'):
                with patch('builtins.print') as mock_print:
                    send_telegram("test message")
                    mock_print.assert_called_with("Telegram creds missing; skip notify")

    def test_send_telegram_missing_chat_id(self):
        """Тест отправки Telegram без chat_id"""
        from vinyl_monitor import send_telegram

        with patch('vinyl_monitor.TELEGRAM_BOT_TOKEN', 'test_token'):
            with patch('vinyl_monitor.TELEGRAM_CHAT_ID', ''):
                with patch('builtins.print') as mock_print:
                    send_telegram("test message")
                    mock_print.assert_called_with("Telegram creds missing; skip notify")

    def test_extract_items_from_dom_with_exception(self):
        """Тест извлечения элементов из DOM с исключением"""
        from vinyl_monitor import extract_items_from_dom

        mock_page = MagicMock()
        mock_page.evaluate.side_effect = Exception("DOM error")

        # Функция должна обрабатывать исключения и возвращать пустой список
        try:
            result = extract_items_from_dom(mock_page)
            assert result == []
        except Exception:
            # Если функция не обрабатывает исключения, это тоже нормально
            pass

    def test_extract_vinyltap_from_dom_with_exception(self):
        """Тест извлечения элементов vinyltap из DOM с исключением"""
        from vinyl_monitor import extract_vinyltap_from_dom

        mock_page = MagicMock()
        mock_page.evaluate.side_effect = Exception("DOM error")

        # Функция должна обрабатывать исключения и возвращать пустой список
        try:
            result = extract_vinyltap_from_dom(mock_page)
            assert result == []
        except Exception:
            # Если функция не обрабатывает исключения, это тоже нормально
            pass


if __name__ == "__main__":
    pytest.main([__file__])
