#!/usr/bin/env python3
"""
Тестовый скрипт для проверки доступности Авито с новым User-Agent
"""

import requests
import time
from playwright.sync_api import sync_playwright

def test_avito_with_requests():
    """Тестируем Авито через requests"""
    print('🔍 Тестируем Авито через requests...')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        response = requests.get('https://www.avito.ru/sankt_peterburg_i_lo/kollektsionirovanie', 
                              headers=headers, timeout=15)
        
        print(f'📊 HTTP статус: {response.status_code}')
        
        if response.status_code == 200:
            print('✅ Авито доступен с новым User-Agent!')
            return True
        elif response.status_code == 403:
            print('❌ Все еще заблокирован (403 Forbidden)')
        elif response.status_code == 429:
            print('⚠️ Слишком много запросов (429 Too Many Requests)')
        else:
            print(f'⚠️ Неожиданный статус: {response.status_code}')
            
        return False
        
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        return False

def test_avito_with_playwright():
    """Тестируем Авито через Playwright"""
    print('🔍 Тестируем Авито через Playwright...')
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                locale="ru-RU",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                }
            )
            page = context.new_page()
            page.set_default_timeout(30000)
            
            # Тестируем простой поиск
            search_url = "https://www.avito.ru/sankt_peterburg_i_lo/kollektsionirovanie?cd=1&q=vinyl"
            print(f'  Переходим на: {search_url}')
            
            page.goto(search_url, wait_until="load", timeout=30000)
            time.sleep(5)
            
            # Проверяем, что страница загрузилась
            title = page.title()
            print(f'  Заголовок страницы: {title}')
            
            if "Доступ ограничен" in title or "проблема с IP" in title:
                print('❌ Авито все еще блокирует доступ')
                return False
            else:
                print('✅ Авито доступен через Playwright!')
                return True
                
    except Exception as e:
        print(f'❌ Ошибка Playwright: {e}')
        return False

if __name__ == "__main__":
    print('🚀 Тестирование доступности Авито с новым User-Agent\n')
    
    # Тест 1: requests
    requests_ok = test_avito_with_requests()
    print()
    
    # Тест 2: Playwright
    playwright_ok = test_avito_with_playwright()
    print()
    
    # Итог
    if requests_ok or playwright_ok:
        print('🎉 Авито доступен! Новый User-Agent работает.')
    else:
        print('😞 Авито все еще заблокирован. Нужны дополнительные меры.')

