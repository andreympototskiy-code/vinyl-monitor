#!/usr/bin/env python3
"""
Дополнительные сайты для мониторинга виниловых пластинок
"""

import os
import time
from pathlib import Path
from typing import Dict, List
from playwright.sync_api import sync_playwright

# Новые URL
PLASTINKA_URL = os.getenv("PLASTINKA_URL", "https://plastinka.com/lp")
VINYLFAMILY_SALE_URL = os.getenv("VINYLFAMILY_SALE_URL", "https://vinylfamily.shop/catalog")

# Интервалы мониторинга
PLASTINKA_MONITOR_INTERVAL_HOURS = int(os.getenv("PLASTINKA_MONITOR_INTERVAL_HOURS", "6"))
VINYLFAMILY_MONITOR_INTERVAL_HOURS = int(os.getenv("VINYLFAMILY_MONITOR_INTERVAL_HOURS", "6"))

# Параметры
REQUEST_TIMEOUT_SEC = 120
LOAD_MORE_WAIT_MS = 1200


def should_monitor_site(site_name: str, interval_hours: int) -> bool:
    """Проверяет, нужно ли мониторить сайт на основе интервала"""
    last_check_file = Path(f"last_check_{site_name}.txt")
    
    if not last_check_file.exists():
        return True  # Первый запуск
    
    try:
        with open(last_check_file, "r", encoding="utf-8") as f:
            last_check_str = f.read().strip()
        
        from datetime import datetime, timedelta
        last_check = datetime.fromisoformat(last_check_str)
        now = datetime.now()
        
        time_since_last = now - last_check
        hours_since_last = time_since_last.total_seconds() / 3600
        
        return hours_since_last >= interval_hours
    except Exception:
        return True  # При ошибке мониторим


def update_last_check_time(site_name: str):
    """Обновляет время последней проверки сайта"""
    from datetime import datetime
    
    last_check_file = Path(f"last_check_{site_name}.txt")
    last_check_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(last_check_file, "w", encoding="utf-8") as f:
        f.write(datetime.now().isoformat())


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
        for (let i = 0; i < 5 && el; i++) {
          if (el.querySelector) {
            const t = el.querySelector('h1,h2,h3,.title,.product-title,[class*="title"],.t-store__prod-snippet__title');
            if (t && t.textContent.trim().length > 3) {
              title = t.textContent.trim();
              break;
            }
          }
          el = el.parentElement;
        }

        let price = '';
        el = a;
        for (let i = 0; i < 5 && el; i++) {
          if (el.querySelector) {
            const p = el.querySelector('.price,.money,[class*="price"],.t-store__prod-snippet__price');
            if (p && p.textContent) {
              price = p.textContent.trim().replace(/\s+/g, ' ');
              break;
            }
          }
          el = el.parentElement;
        }

        if (title && title.length > 3) {
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


def extract_vinylfamily_from_dom(page) -> List[Dict]:
    """Извлекает данные о товарах с vinylfamily.shop"""
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
            const t = el.querySelector('h1,h2,h3,.title,.product-title,[class*="title"],.t-store__prod-snippet__title');
            if (t && t.textContent.trim().length > 3) {
              title = t.textContent.trim();
              break;
            }
          }
          el = el.parentElement;
        }

        let price = '';
        el = a;
        for (let i = 0; i < 5 && el; i++) {
          if (el.querySelector) {
            const p = el.querySelector('.price,.money,[class*="price"],.t-store__prod-snippet__price');
            if (p && p.textContent) {
              price = p.textContent.trim().replace(/\s+/g, ' ');
              break;
            }
          }
          el = el.parentElement;
        }

        if (title && title.length > 3) {
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
                        print(f"    Не удалось загрузить plastinka.com после 3 попыток")
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


def scrape_vinylfamily_with_playwright() -> List[Dict]:
    """Сканировать vinylfamily.shop на предмет виниловых пластинок"""
    if not should_monitor_site("vinylfamily", VINYLFAMILY_MONITOR_INTERVAL_HOURS):
        print("⏰ vinylfamily.shop: пропуск (интервал 6 часов)")
        return []

    print("🔍 Сканирование vinylfamily.shop...")
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
            print(f"  Сканирование: {VINYLFAMILY_SALE_URL}")

            # Пытаемся загрузить страницу с повторными попытками
            for attempt in range(3):
                try:
                    page.goto(VINYLFAMILY_SALE_URL, wait_until="load", timeout=REQUEST_TIMEOUT_SEC * 1000)
                    break
                except Exception as e:
                    print(f"    Попытка {attempt + 1} загрузки неудачна: {e}")
                    if attempt < 2:
                        time.sleep(2)
                    else:
                        print(f"    Не удалось загрузить vinylfamily.shop после 3 попыток")
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
                items = extract_vinylfamily_from_dom(page)
                print(f"    Найдено: {len(items)} позиций")
                all_items.extend(items)
            except Exception as e:
                print(f"    Ошибка при извлечении данных: {e}")

        except Exception as e:
            print(f"    Ошибка при сканировании vinylfamily.shop: {e}")

        browser.close()

        # Добавляем источник
        for item in all_items:
            item["source"] = "vinylfamily.shop"

        return all_items


if __name__ == "__main__":
    print("🚀 Тестирование новых сайтов\n")
    
    # Тестируем plastinka.com
    print("📦 Тестируем plastinka.com:")
    plastinka_items = scrape_plastinka_with_playwright()
    print(f"Найдено позиций: {len(plastinka_items)}")
    if plastinka_items:
        for i, item in enumerate(plastinka_items[:3]):
            print(f"  {i+1}. {item.get('title', 'Без названия')} - {item.get('price', 'Без цены')}")
    
    print()
    
    # Тестируем vinylfamily.shop
    print("📦 Тестируем vinylfamily.shop:")
    vinylfamily_items = scrape_vinylfamily_with_playwright()
    print(f"Найдено позиций: {len(vinylfamily_items)}")
    if vinylfamily_items:
        for i, item in enumerate(vinylfamily_items[:3]):
            print(f"  {i+1}. {item.get('title', 'Без названия')} - {item.get('price', 'Без цены')}")
