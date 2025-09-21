import json
import os
import re
import time
from html import escape
from pathlib import Path
from typing import Dict, List, Set

import requests
from dotenv import load_dotenv

load_dotenv()

USE_PLAYWRIGHT = os.getenv("USE_PLAYWRIGHT", "true").lower() == "true"
if USE_PLAYWRIGHT:
    from playwright.sync_api import sync_playwright

CATALOG_URL = os.getenv("CATALOG_URL", "https://korobkavinyla.ru/catalog")
KOROBKA_SALE_URL = os.getenv("KOROBKA_SALE_URL", "https://korobkavinyla.ru/catalog?tfc_sort%5B771567999%5D=created:desc&tfc_quantity%5B771567999%5D=y&tfc_storepartuid%5B771567999%5D=Sale&tfc_div=:::")
VINYLTAP_URLS = os.getenv("VINYLTAP_URLS", "https://vinyltap.co.uk/collections/new-releases,https://vinyltap.co.uk/collections/upcoming-releases").split(",")
PLASTINKA_URL = os.getenv("PLASTINKA_URL", "https://plastinka.com/lp")
STATE_PATH = Path(os.getenv("STATE_PATH", "./state.json")).expanduser().resolve()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
REQUEST_TIMEOUT_SEC = 120
LOAD_MORE_MAX_CLICKS = 20
LOAD_MORE_WAIT_MS = 1200

# Интервалы мониторинга в часах
KOROBKA_MONITOR_INTERVAL_HOURS = int(os.getenv("KOROBKA_MONITOR_INTERVAL_HOURS", "3"))  # 3 часа для korobkavinyla.ru
VINYLTAP_MONITOR_INTERVAL_HOURS = int(os.getenv("VINYLTAP_MONITOR_INTERVAL_HOURS", "3"))  # 3 часа для vinyltap.co.uk
AVITO_MONITOR_INTERVAL_HOURS = int(os.getenv("AVITO_MONITOR_INTERVAL_HOURS", "6"))  # 6 часов для Авито
PLASTINKA_MONITOR_INTERVAL_HOURS = int(os.getenv("PLASTINKA_MONITOR_INTERVAL_HOURS", "6"))  # 6 часов для plastinka.com


def load_state() -> Set[str]:
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Поддержка старого формата (массив ID) и нового формата (объект с timestamp)
            if "known_ids" in data and isinstance(data["known_ids"], list):
                # Старый формат - массив строк
                return set(data["known_ids"])
            elif "known_items" in data and isinstance(data["known_items"], dict):
                # Новый формат - объект с timestamp
                return set(data["known_items"].keys())
            else:
                return set()
        except Exception:
            return set()
    return set()


def get_item_info(item_id: str) -> Dict:
    """Получить информацию о позиции из state.json"""
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "known_items" in data and item_id in data["known_items"]:
                    return data["known_items"][item_id]
        except Exception:
            pass
    return {}


def should_monitor_site(site_name: str, interval_hours: int) -> bool:
    """Проверить, нужно ли мониторить сайт сейчас"""
    from datetime import datetime, timedelta

    # Путь к файлу с временем последнего мониторинга
    last_check_file = STATE_PATH.parent / f"last_check_{site_name}.txt"

    if not last_check_file.exists():
        # Если файла нет, значит мониторим впервые
        return True

    try:
        with open(last_check_file, "r") as f:
            last_check_str = f.read().strip()
            last_check = datetime.fromisoformat(last_check_str)

        # Проверяем, прошло ли достаточно времени
        time_since_last = datetime.now() - last_check
        return time_since_last >= timedelta(hours=interval_hours)

    except Exception:
        # Если ошибка при чтении, мониторим
        return True


def update_last_check_time(site_name: str):
    """Обновить время последней проверки сайта"""
    from datetime import datetime

    last_check_file = STATE_PATH.parent / f"last_check_{site_name}.txt"
    with open(last_check_file, "w") as f:
        f.write(datetime.now().isoformat())


def load_avito_config() -> Dict:
    """Загрузить конфигурацию Авито"""
    config_path = STATE_PATH.parent / "avito_config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Возвращаем конфигурацию по умолчанию
    return {
        "search_queries": ["poets of the fall", "harry potter", "Снежная королева"],
        "base_url": "https://www.avito.ru/sankt_peterburg_i_lo",
        "category": "hobbi_i_otdyh/muzykalnye_instrumenty",
        "monitor_interval_hours": 6,
        "enabled": True
    }


def scrape_avito_with_playwright() -> List[Dict]:
    """Сканировать Авито на предмет виниловых пластинок"""
    config = load_avito_config()

    if not config.get("enabled", True):
        print("⏰ Авито: отключен в конфигурации")
        return []

    if not should_monitor_site("avito", config.get("monitor_interval_hours", 6)):
        print("⏰ Авито: пропуск (интервал 6 часов)")
        return []

    print("🔍 Сканирование Авито...")

    items = []
    search_queries = config.get("search_queries", [])
    base_url = config.get("base_url", "https://www.avito.ru/sankt_peterburg_i_lo")
    category = config.get("category", "kollektsionirovanie")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ru-RU",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        page = context.new_page()
        page.set_default_timeout(REQUEST_TIMEOUT_SEC * 1000)

        for query in search_queries:
            try:
                # Формируем URL для поиска
                search_url = f"{base_url}{category}?cd=1&q={query.replace(' ', '+')}"
                print(f"  Поиск: {query}")

                # Загружаем страницу
                page.goto(search_url, wait_until="load", timeout=REQUEST_TIMEOUT_SEC * 1000)
                time.sleep(2)

                # Извлекаем результаты
                js = """
                () => {
                  const items = [];
                  const listings = document.querySelectorAll('[data-marker="item"]');

                  for (const listing of listings) {
                    const titleEl = listing.querySelector('[data-marker="item-title"]');
                    const priceEl = listing.querySelector('[data-marker="item-price"]');
                    const linkEl = listing.querySelector('a[data-marker="item-title"]');

                    if (titleEl && linkEl) {
                      const title = titleEl.textContent.trim();
                      const price = priceEl ? priceEl.textContent.trim() : '';
                      const url = linkEl.href;

                      // Проверяем, что это виниловая пластинка
                      if (title.toLowerCase().includes('винил') ||
                          title.toLowerCase().includes('lp') ||
                          title.toLowerCase().includes('vinyl') ||
                          title.toLowerCase().includes('пластинка')) {
                        items.push({
                          id: url,
                          url: url,
                          title: title,
                          price: price,
                          query: arguments[0]
                        });
                      }
                    }
                  }

                  return items;
                }
                """

                query_items = page.evaluate(js, query)
                items.extend(query_items)
                print(f"    Найдено: {len(query_items)} позиций")

            except Exception as e:
                print(f"    Ошибка при поиске '{query}': {e}")
                continue

        browser.close()

    # Добавляем источник
    for item in items:
        item["source"] = "avito.ru"

    print(f"📦 Найдено {len(items)} позиций на Авито")
    update_last_check_time("avito")
    return items


def save_state(known_ids: Set[str], new_items: List[Dict] = None) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Загружаем существующие данные
    existing_data = {}
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "known_items" in data:
                    existing_data = data["known_items"]
                elif "known_ids" in data:
                    # Конвертируем старый формат в новый
                    for item_id in data["known_ids"]:
                        existing_data[item_id] = {"added_at": "unknown"}
        except Exception:
            pass

    # Добавляем новые элементы с timestamp
    if new_items:
        from datetime import datetime
        current_time = datetime.now().isoformat()
        for item in new_items:
            item_id = item.get("id", "")
            if item_id:
                existing_data[item_id] = {
                    "added_at": current_time,
                    "title": item.get("title", ""),
                    "source": item.get("source", "")
                }

    # Сохраняем в новом формате
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"known_items": existing_data}, f, ensure_ascii=False, indent=2)


def send_telegram(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram creds missing; skip notify")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=REQUEST_TIMEOUT_SEC,
        )
    except Exception as e:
        print(f"Failed to send Telegram: {e}")


    def validate_url(url: str) -> bool:
        """Валидация URL"""
        if not url or not isinstance(url, str):
            return False
        return url.startswith(('http://', 'https://')) and len(url) < 2048
    
    
def dedupe_keep_order(items: List[Dict]) -> List[Dict]:
    """Улучшенная дедупликация с нормализацией URL и логированием"""
    seen = set()
    out = []
    duplicates_count = 0
    
    for it in items:
        # Нормализуем URL для более надежной дедупликации
        url = it.get("url", "")
        if url:
            # Убираем параметры запроса и якоря
            normalized_url = url.split('?')[0].split('#')[0]
            # Убираем trailing slash
            normalized_url = normalized_url.rstrip('/')
        else:
            normalized_url = it.get("id", "")
        
        if normalized_url and normalized_url not in seen:
            seen.add(normalized_url)
            # Обновляем ID на нормализованный URL
            it["id"] = normalized_url
            out.append(it)
        else:
            duplicates_count += 1
            print(f"Дубликат найден: {normalized_url}")
    
    if duplicates_count > 0:
        print(f"Найдено {duplicates_count} дубликатов, удалено")
    
    return out


def advanced_deduplication(items: List[Dict]) -> List[Dict]:
    """Продвинутая дедупликация по содержимому и URL"""
    seen_urls = set()
    seen_content = set()
    out = []
    duplicates_count = 0
    
    for it in items:
        # Нормализуем URL
        url = it.get("url", "")
        if url:
            normalized_url = url.split('?')[0].split('#')[0].rstrip('/')
        else:
            normalized_url = it.get("id", "")
        
        # Создаем ключ содержимого для дополнительной проверки
        title = it.get("title", "").strip().lower()
        price = it.get("price", "").strip()
        
        # Нормализуем цену для сравнения (убираем валютные символы и дубли)
        normalized_price = price.lower()
        # Убираем валютные символы
        normalized_price = normalized_price.replace('€', '').replace('£', '').replace('$', '').replace('руб', '')
        normalized_price = normalized_price.replace('eur', '').replace('gbp', '').replace('usd', '')
        # Убираем лишние пробелы
        normalized_price = ' '.join(normalized_price.split())
        # Убираем дублированные части (если есть повторяющиеся числа)
        # Ищем повторяющиеся числа и убираем дубли
        numbers = re.findall(r'\d+\.?\d*', normalized_price)
        if len(numbers) > 1 and len(set(numbers)) == 1:  # Все числа одинаковые
            normalized_price = numbers[0]  # Берем только одно число
        
        content_key = f"{title}|{normalized_price}"
        
        # Проверяем дубликаты по URL и содержимому
        is_duplicate = False
        
        if normalized_url in seen_urls:
            is_duplicate = True
            print(f"Дубликат по URL: {normalized_url}")
        elif content_key in seen_content and content_key != "|":
            is_duplicate = True
            print(f"Дубликат по содержимому: {title}")
        
        if not is_duplicate:
            seen_urls.add(normalized_url)
            seen_content.add(content_key)
            it["id"] = normalized_url
            out.append(it)
        else:
            duplicates_count += 1
    
    if duplicates_count > 0:
        print(f"Найдено {duplicates_count} дубликатов (продвинутая проверка), удалено")
    
    return out


def extract_items_from_dom(page) -> List[Dict]:
    js = r"""
    () => {
      const anchors = Array.from(document.querySelectorAll('a'))
        .filter(a => a.href && a.href.includes('/catalog/') && a.textContent.trim().length > 0);

      const items = [];
      const seen = new Set();

      for (const a of anchors) {
        // Нормализуем URL: убираем параметры запроса и якоря, убираем trailing slash
        const url = a.href.split('?')[0].split('#')[0].replace(/\/$/, '');
        if (seen.has(url)) continue;
        seen.add(url);

        let title = a.textContent.trim();
        let el = a;
        for (let i = 0; i < 5 && el; i++) {
          if (el.querySelector) {
            const t = el.querySelector('h1,h2,h3,.title,.product-title,[class*="title"]');
            if (t && t.textContent.trim().length > 3) {
              title = t.textContent.trim();
              break;
            }
          }
          el = el.parentElement;
        }

        el = a;
        let price = '';
        for (let i = 0; i < 5 && el; i++) {
          if (el.querySelector) {
            const p = el.querySelector('.price,[class*="price"],[data-price]');
            if (p && p.textContent) {
              price = p.textContent.trim().replace(/\s+/g, ' ');
              break;
            }
          }
          el = el.parentElement;
        }

        items.push({
          id: url,
          url,
          title,
          price
        });
      }
      return items;
    }
    """
    items = page.evaluate(js)
    return dedupe_keep_order(items)


def safe_scrape(func, url: str) -> List[Dict]:
    try:
        return func(url)
    except Exception as e:
        print(f"Scrape failed for {url}: {e}")
        return []


def validate_message_format(message: str) -> bool:
    """
    Проверяет формат сообщения на соответствие ожидаемому формату:
    • Название - Цена - Ссылка
    """
    if not message or not message.strip():
        return False

    lines = message.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Пропускаем заголовки разделов
        if line.startswith('🎵') or line.startswith('🏠') or line.startswith('📦'):
            continue

        # Проверяем формат строки с товаром
        if line.startswith('- '):
            # Убираем "- " в начале
            content = line[2:].strip()

            # Проверяем наличие ссылки
            if '<a href=' not in content or '</a>' not in content:
                return False

            # Проверяем, что есть название и цена
            # Формат: <a href="url">название</a> — цена
            if ' — ' not in content:
                return False

            # Проверяем, что название не пустое
            title_start = content.find('>') + 1
            title_end = content.find('</a>')
            if title_start <= 1 or title_end <= title_start:
                return False

            title = content[title_start:title_end].strip()
            if not title or title == '(без названия)':
                return False

            # Проверяем цену на дублирование
            price_part = content[content.find(' — ') + 3:].strip()
            if price_part:
                # Проверяем на дублирование валютных символов
                currency_symbols = ['£', '€', '$', 'руб']
                for symbol in currency_symbols:
                    if price_part.count(symbol) > 1:
                        return False

                # Проверяем на дублирование EUR/GBP
                if price_part.count('EUR') > 1 or price_part.count('GBP') > 1:
                    return False

    return True


def chunk_messages(text: str, limit: int = 4096) -> List[str]:
    if len(text) <= limit:
        return [text]
    chunks: List[str] = []
    current = []
    current_len = 0
    for line in text.split("\n"):
        add_len = len(line) + 1
        if current_len + add_len > limit:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line) + 1
        else:
            current.append(line)
            current_len += add_len
    if current:
        chunks.append("\n".join(current))
    return chunks


def extract_vinyltap_from_dom(page) -> List[Dict]:
    js = r"""
    () => {
      const anchors = Array.from(document.querySelectorAll('a'))
        .filter(a => a.href && a.href.includes('/products/') && a.textContent.trim().length > 0);

      const items = [];
      const seen = new Set();

      for (const a of anchors) {
        // Нормализуем URL: убираем параметры запроса и якоря, убираем trailing slash
        const url = a.href.split('?')[0].split('#')[0].replace(/\/$/, '');
        if (seen.has(url)) continue;
        seen.add(url);

        let title = a.textContent.trim();
        let el = a;
        for (let i = 0; i < 5 && el; i++) {
          if (el.querySelector) {
            const t = el.querySelector('h1,h2,h3,.title,.product-title,[class*="title"],.card__heading');
            if (t && t.textContent.trim().length > 3) {
              title = t.textContent.trim();
              break;
            }
          }
          el = el.parentElement;
        }

        // ФИЛЬТРАЦИЯ: только виниловые пластинки (LP, Vinyl, 7 Inch, 12 Inch)
        const titleLower = title.toLowerCase();
        const isVinyl = titleLower.includes('lp') ||
                       titleLower.includes('vinyl') ||
                       titleLower.includes('7 inch') ||
                       titleLower.includes('12 inch') ||
                       titleLower.includes('7"') ||
                       titleLower.includes('12"') ||
                       (titleLower.includes('inch') && !titleLower.includes('cd') && !titleLower.includes('dvd'));

        // Исключаем CD, DVD, кассеты
        const isNotVinyl = titleLower.includes('cd') ||
                          titleLower.includes('dvd') ||
                          titleLower.includes('cassette') ||
                          titleLower.includes('tape');

        if (!isVinyl || isNotVinyl) {
          continue; // Пропускаем невиниловые товары
        }

        el = a;
        let price = '';
        for (let i = 0; i < 5 && el; i++) {
          if (el.querySelector) {
            const p = el.querySelector('.price,.money,[class*="price"]');
            if (p && p.textContent) {
              price = p.textContent.trim().replace(/\s+/g, ' ');
              // Очищаем цену от лишнего текста и дублирования
              price = price.replace(/Regular price\s*/gi, '')
                          .replace(/Sale price\s*/gi, '')
                          .replace(/Unit price\s*\/\s*per\s*/gi, '')
                          .replace(/\s+/g, ' ')
                          .trim();

              // Убираем дублирование цены (если есть повторяющиеся части)
              // Ищем символы валют: £, €, $, руб
              const currencySymbols = ['£', '€', '$', 'руб'];
              let foundCurrency = null;
              for (const symbol of currencySymbols) {
                if (price.includes(symbol)) {
                  foundCurrency = symbol;
                  break;
                }
              }

              if (foundCurrency) {
                // Разбиваем по символу валюты
                const priceParts = price.split(foundCurrency);
                if (priceParts.length > 2) {
                  // Берем только первую цену (часть до первого символа валюты + символ + часть после)
                  price = priceParts[0] + foundCurrency + priceParts[1];
                }

                // Дополнительная проверка на дублирование EUR/GBP
                if (price.includes('EUR') && price.includes('€')) {
                  // Убираем дублирование EUR после €
                  price = price.replace(/€([^€]*?)EUR\s*€\1EUR/g, '€$1EUR');
                  // Если все еще есть дублирование, берем только первую часть
                  if (price.includes('€') && price.split('€').length > 2) {
                    const parts = price.split('€');
                    price = parts[0] + '€' + parts[1];
                  }
                }
                
                // Аналогично для GBP
                if (price.includes('GBP') && price.includes('£')) {
                  price = price.replace(/£([^£]*?)GBP\s*£\1GBP/g, '£$1GBP');
                  if (price.includes('£') && price.split('£').length > 2) {
                    const parts = price.split('£');
                    price = parts[0] + '£' + parts[1];
                  }
                }
              }
              break;
            }
          }
          el = el.parentElement;
        }

        items.push({ id: url, url, title, price });
      }
      return items;
    }
    """
    items = page.evaluate(js)
    return dedupe_keep_order(items)


def scrape_with_playwright() -> List[Dict]:
    all_items = []
    urls = [CATALOG_URL, KOROBKA_SALE_URL]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ru-RU",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        page = context.new_page()
        page.set_default_timeout(REQUEST_TIMEOUT_SEC * 1000)

        for url in urls:
            try:
                section_name = "каталог" if "Sale" not in url else "скидки"
                print(f"  Сканирование {section_name}: {url}")

                # Пытаемся загрузить страницу с повторными попытками
                for attempt in range(3):
                    try:
                        page.goto(url, wait_until="load", timeout=REQUEST_TIMEOUT_SEC * 1000)
                        break
                    except Exception as e:
                        print(f"    Попытка {attempt + 1} загрузки неудачна: {e}")
                        if attempt < 2:
                            time.sleep(2)
                        else:
                            print(f"    Не удалось загрузить {section_name} после 3 попыток")
                            continue
            except Exception as e:
                print(f"    Ошибка при обработке {section_name}: {e}")
                continue

        time.sleep(1.2)

        clicks = 0
        while clicks < LOAD_MORE_MAX_CLICKS:
            btn = page.locator("text=Load more").or_(page.locator("text=Загрузить ещё")).or_(page.locator("text=Показать ещё"))
            if btn.count() == 0:
                break
            try:
                btn.first.scroll_into_view_if_needed()
                btn.first.click()
                clicks += 1
                page.wait_for_timeout(LOAD_MORE_WAIT_MS)
            except Exception:
                break

            items = extract_items_from_dom(page)
            print(f"    Найдено: {len(items)} позиций")
            all_items.extend(items)

        browser.close()

        # Добавляем источник
        for item in all_items:
            item["source"] = "korobkavinyla.ru"

        return all_items


def scrape_plastinka_with_playwright() -> List[Dict]:
    """Сканировать plastinka.com на предмет виниловых пластинок"""
    if not should_monitor_site("plastinka", PLASTINKA_MONITOR_INTERVAL_HOURS):
        print("⏰ plastinka.com: пропуск (интервал 6 часов)")
        return []

    print("🔍 Сканирование plastinka.com...")
    all_items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ru-RU",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        page = context.new_page()
        page.set_default_timeout(REQUEST_TIMEOUT_SEC * 1000)

        try:
            print(f"  Сканирование: {PLASTINKA_URL}")

            # Пытаемся загрузить страницу с повторными попытками
            for attempt in range(3):
                try:
                    page.goto(PLASTINKA_URL, wait_until="load", timeout=REQUEST_TIMEOUT_SEC * 1000)
                    break
                except Exception as e:
                    print(f"    Попытка {attempt + 1} загрузки неудачна: {e}")
                    if attempt < 2:
                        time.sleep(2)
                    else:
                        print("    Не удалось загрузить plastinka.com после 3 попыток")
                        continue

            time.sleep(1.2)

            # Попробуем нажать кнопку подгрузки, если есть
            try:
                for _ in range(3):
                    btn = page.locator("text=Load more").or_(page.locator("text=Загрузить ещё")).or_(page.locator("text=Показать ещё"))
                    if btn.count() == 0:
                        break
                    btn.first.scroll_into_view_if_needed()
                    btn.first.click()
                    page.wait_for_timeout(LOAD_MORE_WAIT_MS)
            except Exception as e:
                print(f"    Ошибка при нажатии кнопки 'Load more': {e}")

            try:
                items = extract_plastinka_from_dom(page)
                print(f"    Найдено: {len(items)} позиций")
                all_items.extend(items)
            except Exception as e:
                print(f"    Ошибка при извлечении данных: {e}")

        except Exception as e:
            print(f"    Ошибка при сканировании plastinka.com: {e}")

        browser.close()

        # Добавляем источник
        for item in all_items:
            item["source"] = "plastinka.com"

        return all_items


def extract_plastinka_from_dom(page) -> List[Dict]:
    """Извлекает данные о товарах с plastinka.com"""
    js = r"""
    () => {
      const anchors = Array.from(document.querySelectorAll('a'))
        .filter(a => a.href && (a.href.includes('/product/') || a.href.includes('/lp/')) && a.textContent.trim().length > 0);

      const items = [];
      const seen = new Set();

      for (const a of anchors) {
        // Нормализуем URL: убираем параметры запроса и якоря, убираем trailing slash
        const url = a.href.split('?')[0].split('#')[0].replace(/\/$/, '');
        if (seen.has(url)) continue;
        seen.add(url);

        let title = a.textContent.trim();
        let el = a;
        
        // Ищем название в самом элементе и его ближайших родителях
        let currentEl = a;
        for (let i = 0; i < 3 && currentEl; i++) {
          if (currentEl.querySelector) {
            // Ищем различные селекторы для названий в текущем элементе
            const titleSelectors = [
              '.t-store__prod-snippet__title',
              '.t-store__prod-snippet__title a',
              '.t-store__prod-snippet__title span',
              '.t-store__prod-snippet__title div',
              'h1,h2,h3,h4,h5,h6',
              '.title,.product-title,[class*="title"]',
              '.t-store__prod-snippet__title-wrapper',
              '.t-store__prod-snippet__title-wrapper a',
              '.t-store__prod-snippet__title-wrapper span'
            ];
            
            for (const selector of titleSelectors) {
              const t = currentEl.querySelector(selector);
              if (t && t.textContent && t.textContent.trim().length > 3) {
                const foundTitle = t.textContent.trim();
                // Проверяем, что это не просто год или короткий текст
                if (foundTitle.length > title.length && !foundTitle.match(/^\\d{2,4}$/)) {
                  title = foundTitle;
                  break;
                }
              }
            }
            
            // Также проверяем атрибуты title и alt
            if (currentEl.title && currentEl.title.trim().length > title.length) {
              title = currentEl.title.trim();
            }
            if (currentEl.alt && currentEl.alt.trim().length > title.length) {
              title = currentEl.alt.trim();
            }
          }
          currentEl = currentEl.parentElement;
        }
        
        // Если название все еще короткое, пытаемся извлечь из URL
        if (title.length < 10 && a.href) {
          const urlParts = a.href.split('/');
          const lastPart = urlParts[urlParts.length - 1];
          if (lastPart && lastPart.includes('-')) {
            const urlTitle = lastPart.replace(/-/g, ' ').replace(/\\d+/g, '').trim();
            if (urlTitle.length > title.length) {
              title = urlTitle;
            }
          }
        }
        
        // Дополнительная проверка: если название слишком общее, пытаемся найти уникальные элементы
        if (title.length < 15 || title.includes('Boccherini/Bach')) {
          // Ищем уникальные элементы в соседних элементах
          const parent = a.parentElement;
          if (parent) {
            const siblings = Array.from(parent.children);
            for (const sibling of siblings) {
              if (sibling !== a && sibling.textContent) {
                const siblingText = sibling.textContent.trim();
                if (siblingText.length > title.length && 
                    !siblingText.toLowerCase().includes('руб') &&
                    !siblingText.toLowerCase().includes('купить') &&
                    !siblingText.toLowerCase().includes('в корзину')) {
                  title = siblingText;
                  break;
                }
              }
            }
          }
        }

        let price = '';
        let originalPrice = '';
        let discountPrice = '';
        el = a;
        for (let i = 0; i < 5 && el; i++) {
          if (el.querySelector) {
            // Ищем цену со скидкой
            const discountEl = el.querySelector('.t-store__prod-snippet__price, .price, .money, [class*="price"]');
            if (discountEl && discountEl.textContent) {
              const priceText = discountEl.textContent.trim();
              
              // Проверяем, есть ли две цены (оригинальная и со скидкой)
              const priceMatch = priceText.match(/(\d+[\s,]*\d*)\s*руб\.?\s*(\d+[\s,]*\d*)\s*руб\.?/);
              if (priceMatch) {
                originalPrice = priceMatch[1].replace(/\s/g, '') + ' руб.';
                discountPrice = priceMatch[2].replace(/\s/g, '') + ' руб.';
                price = `${originalPrice} → ${discountPrice}`;
              } else {
                price = priceText.replace(/\s+/g, ' ');
              }
              break;
            }
          }
          el = el.parentElement;
        }

        // Фильтруем элементы меню и навигации
        if (title && title.length > 3 && 
            !title.toLowerCase().includes('меню') && 
            !title.toLowerCase().includes('каталог') &&
            !title.toLowerCase().includes('главная') &&
            !title.toLowerCase().includes('контакты') &&
            !title.toLowerCase().includes('style/') &&
            !title.toLowerCase().includes('интересный выбор') &&
            !title.toLowerCase().includes('новые поступления') &&
            !title.toLowerCase().includes('оригинальный винил') &&
            !title.toLowerCase().includes('подарочные издания') &&
            !title.toLowerCase().includes('record store day') &&
            !url.includes('/style/') &&
            url.includes('/item/')) {  // Только товары
          items.push({
            id: url,
            url: url,
            title: title,
            price: price
          });
        }
      }

      return items;
    }
    """
    return page.evaluate(js)


def scrape_vinyltap_with_playwright() -> List[Dict]:
    all_items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="en-GB",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.9,en-US;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        page = context.new_page()
        page.set_default_timeout(REQUEST_TIMEOUT_SEC * 1000)

        for url in VINYLTAP_URLS:
            try:
                print(f"  Сканирование: {url}")
                
                # Пытаемся загрузить страницу с повторными попытками
                for attempt in range(3):
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT_SEC * 1000)
                        break
                    except Exception as e:
                        print(f"    Попытка {attempt + 1} загрузки неудачна: {e}")
                        if attempt < 2:
                            time.sleep(2)
                        else:
                            print(f"    Не удалось загрузить {url} после 3 попыток")
                            continue
                
                time.sleep(1.2)

                # Попробуем нажать кнопку подгрузки, если есть
                try:
                    for _ in range(3):
                        btn = page.locator("text=Load more").or_(page.locator("text=Show more")).or_(page.locator("text=More"))
                        if btn.count() == 0:
                            break
                        btn.first.scroll_into_view_if_needed()
                        btn.first.click()
                        page.wait_for_timeout(LOAD_MORE_WAIT_MS)
                except Exception as e:
                    print(f"    Ошибка при нажатии кнопки 'Load more': {e}")

                try:
                    items = extract_vinyltap_from_dom(page)
                    print(f"    Найдено: {len(items)} позиций")
                    all_items.extend(items)
                except Exception as e:
                    print(f"    Ошибка при извлечении данных: {e}")

            except Exception as e:
                print(f"    Ошибка при сканировании {url}: {e}")
                continue

            browser.close()
        
        # Добавляем источник
        for item in all_items:
            item["source"] = "vinyltap.co.uk"

        return all_items


def main():
    print("🎵 Запуск монитора виниловых пластинок...")
    known = load_state()
    print(f"📚 Загружено {len(known)} известных позиций из состояния")

    items: List[Dict] = []
    if USE_PLAYWRIGHT:
        # Проверяем, нужно ли мониторить korobkavinyla.ru
        if should_monitor_site("korobkavinyla", KOROBKA_MONITOR_INTERVAL_HOURS):
            print("🔍 Сканирование korobkavinyla.ru...")
            korobka_items = scrape_with_playwright()
            print(f"📦 Найдено {len(korobka_items)} позиций на korobkavinyla.ru")
            items.extend(korobka_items)
            update_last_check_time("korobkavinyla")
        else:
            print("⏰ korobkavinyla.ru: пропуск (интервал 24 часа)")
            korobka_items = []
        
        # Проверяем, нужно ли мониторить vinyltap.co.uk
        if should_monitor_site("vinyltap", VINYLTAP_MONITOR_INTERVAL_HOURS):
            print("🔍 Сканирование vinyltap.co.uk...")
            vinyltap_items = scrape_vinyltap_with_playwright()
            print(f"📦 Найдено {len(vinyltap_items)} позиций на vinyltap.co.uk")
            items.extend(vinyltap_items)
            update_last_check_time("vinyltap")
        else:
            print("⏰ vinyltap.co.uk: пропуск (интервал 3 часа)")
            vinyltap_items = []

        # Проверяем, нужно ли мониторить Авито
        avito_items = scrape_avito_with_playwright()
        items.extend(avito_items)

        # Проверяем, нужно ли мониторить plastinka.com
        plastinka_items = scrape_plastinka_with_playwright()
        items.extend(plastinka_items)
    else:
        items = []

    print(f"🔄 Дедупликация {len(items)} позиций...")
    items = advanced_deduplication(items)
    print(f"✅ После дедупликации: {len(items)} уникальных позиций")

    current_ids = {it["id"] for it in items}
    new_ids = [it for it in items if it["id"] not in known]
    
    print(f"🆕 Найдено {len(new_ids)} новых позиций из {len(items)} общих")

    if new_ids:
        lines = ["Новые позиции:"]
        kor_items = [it for it in new_ids if it.get("source") == "korobkavinyla.ru"]
        tap_items = [it for it in new_ids if it.get("source") == "vinyltap.co.uk"]
        avito_items = [it for it in new_ids if it.get("source") == "avito.ru"]

        if kor_items:
            lines.append("🎵 korobkavinyla.ru:")
            for it in kor_items:
                title = it.get('title', '(без названия)')
                price = f" — {it['price']}" if it.get('price') else ''
                url = it['url']
                safe_title = escape(title)
                lines.append(f"- <a href=\"{url}\">{safe_title}</a>{price}")

        if tap_items:
            lines.append("🎵 vinyltap.co.uk:")
            for it in tap_items:
                title = it.get('title', '(без названия)')
                price = it.get('price', '')

                # Исправляем валюту для vinyltap.co.uk (должна быть £, а не €)
                if price and '€' in price:
                    # Заменяем € на £ для vinyltap.co.uk
                    price = price.replace('€', '£')
                    # Убираем EUR и заменяем на GBP
                    price = price.replace('EUR', 'GBP')

                price_str = f" — {price}" if price else ''
                url = it['url']
                safe_title = escape(title)
                lines.append(f"- <a href=\"{url}\">{safe_title}</a>{price_str}")

        if avito_items:
            lines.append("🏠 Авито:")
            for it in avito_items:
                title = it.get('title', '(без названия)')
                price = f" — {it['price']}" if it.get('price') else ''
                url = it['url']
                query = it.get('query', '')
                query_info = f" (поиск: {query})" if query else ''
                safe_title = escape(title)
                lines.append(f"- <a href=\"{url}\">{safe_title}</a>{price}{query_info}")

        if plastinka_items:
            lines.append("💿 plastinka.com:")
            for it in plastinka_items:
                title = it.get('title', '(без названия)')
                price = it.get('price', '')
                
                # Форматируем цену для скидок
                if price and '→' in price:
                    # Цена со скидкой: показываем с эмодзи
                    price_str = f" — 💰 {price}"
                elif price:
                    price_str = f" — {price}"
                else:
                    price_str = ''
                
                url = it['url']
                safe_title = escape(title)
                lines.append(f"- <a href=\"{url}\">{safe_title}</a>{price_str}")

        message = "\n".join(lines)
        print(f"📤 Отправка {len(new_ids)} новых позиций в Telegram...")
        for chunk in chunk_messages(message):
            send_telegram(chunk)
        
        # Обновляем состояние только с новыми ID
        updated_known = known.union(current_ids)
        save_state(updated_known, new_ids)
        print(f"💾 Состояние обновлено: {len(updated_known)} известных позиций")
        print(f"✅ Найдено новых: {len(new_ids)}")
    else:
        print("ℹ️ Новых позиций не найдено.")


if __name__ == "__main__":
    main()
