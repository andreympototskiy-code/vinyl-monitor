import json
import os
import time
from pathlib import Path
from typing import List, Dict, Set

from dotenv import load_dotenv
import requests
from html import escape

load_dotenv()

USE_PLAYWRIGHT = os.getenv("USE_PLAYWRIGHT", "true").lower() == "true"
if USE_PLAYWRIGHT:
    from playwright.sync_api import sync_playwright

CATALOG_URL = os.getenv("CATALOG_URL", "https://korobkavinyla.ru/catalog")
VINYLTAP_URL = os.getenv("VINYLTAP_URL", "https://vinyltap.co.uk/collections/new-arrivals")
STATE_PATH = Path(os.getenv("STATE_PATH", "./state.json")).expanduser().resolve()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
REQUEST_TIMEOUT_SEC = 60
LOAD_MORE_MAX_CLICKS = 20
LOAD_MORE_WAIT_MS = 1200


def load_state() -> Set[str]:
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data.get("known_ids", []))
        except Exception:
            return set()
    return set()


def save_state(known_ids: Set[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"known_ids": sorted(known_ids)}, f, ensure_ascii=False, indent=2)


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


def dedupe_keep_order(items: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for it in items:
        key = it.get("id") or it.get("url")
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


def extract_items_from_dom(page) -> List[Dict]:
    js = r"""
    () => {
      const anchors = Array.from(document.querySelectorAll('a'))
        .filter(a => a.href && a.href.includes('/catalog/') && a.textContent.trim().length > 0);

      const items = [];
      const seen = new Set();

      for (const a of anchors) {
        const url = a.href.split('#')[0];
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
              price = p.textContent.trim().replace(/\s+/g,' ');
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
        const url = a.href.split('#')[0];
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

        el = a;
        let price = '';
        for (let i = 0; i < 5 && el; i++) {
          if (el.querySelector) {
            const p = el.querySelector('.price,.money,[class*="price"]');
            if (p && p.textContent) {
              price = p.textContent.trim().replace(/\s+/g,' ');
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


def scrape_with_playwright(url: str) -> List[Dict]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="ru-RU")
        page = context.new_page()
        page.set_default_timeout(REQUEST_TIMEOUT_SEC * 1000)
        page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT_SEC * 1000)
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
        context.close()
        browser.close()
        for it in items:
            it["source"] = "korobkavinyla.ru"
        return items


def scrape_vinyltap_with_playwright(url: str) -> List[Dict]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="en-GB")
        page = context.new_page()
        page.set_default_timeout(REQUEST_TIMEOUT_SEC * 1000)
        for _ in range(2):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT_SEC * 1000)
                break
            except Exception:
                time.sleep(2)
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
        except Exception:
            pass

        items = extract_vinyltap_from_dom(page)
        context.close()
        browser.close()
        for it in items:
            it["source"] = "vinyltap.co.uk"
        return items


def main():
    known = load_state()

    items: List[Dict] = []
    if USE_PLAYWRIGHT:
        items.extend(safe_scrape(scrape_with_playwright, CATALOG_URL))
        items.extend(safe_scrape(scrape_vinyltap_with_playwright, VINYLTAP_URL))
    else:
        items = []

    items = dedupe_keep_order(items)

    current_ids = {it["id"] for it in items}
    new_ids = [it for it in items if it["id"] not in known]

    if new_ids:
        lines = ["Новые позиции:"]
        kor_items = [it for it in new_ids if it.get("source") == "korobkavinyla.ru"]
        tap_items = [it for it in new_ids if it.get("source") == "vinyltap.co.uk"]

        if kor_items:
            lines.append("korobkavinyla.ru:")
            for it in kor_items:
                title = it.get('title','(без названия)')
                price = f" — {it['price']}" if it.get('price') else ''
                url = it['url']
                safe_title = escape(title)
                lines.append(f"- <a href=\"{url}\">{safe_title}</a>{price}")

        if tap_items:
            lines.append("vinyltap.co.uk:")
            for it in tap_items:
                title = it.get('title','(без названия)')
                price = f" — {it['price']}" if it.get('price') else ''
                url = it['url']
                safe_title = escape(title)
                lines.append(f"- <a href=\"{url}\">{safe_title}</a>{price}")

        message = "\n".join(lines)
        for chunk in chunk_messages(message):
            send_telegram(chunk)
        save_state(known.union(current_ids))
        print(f"Найдено новых: {len(new_ids)}")
    else:
        print("Новых позиций не найдено.")


if __name__ == "__main__":
    main()
