import os
import json
import requests
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
import feedparser

# --- Настройки ---
TOKEN = os.getenv("TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# --- Кеш ---
CACHE_FILE = "cache/psych_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data) if isinstance(data, list) else set()
        except Exception as e:
            print(f"Ошибка чтения кеша: {e}")
    return set()

def save_cache(cache_set):
    os.makedirs("cache", exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(cache_set), f, ensure_ascii=False, indent=2)

# --- Перевод ---
def translate_text(text):
    try:
        return GoogleTranslator(source='auto', target='ru').translate(text)
    except Exception as e:
        print(f"Ошибка перевода: {e}")
        return text

# --- RSS-источники по психологии ---
RSS_FEEDS = [
    {
        "url": "https://habr.com/ru/rss/search/?q=психология&target_type=posts&order=date",
        "name": "Habr: Психология"
    },
    {
        "url": "https://nplus1.ru/rss",
        "name": "N+1: Наука"
    },
    {
        "url": "https://tjournal.ru/rss",
        "name": "TJournal: Саморазвитие"
    },
    {
        "url": "https://www.reddit.com/r/Psychology.rss",
        "name": "Reddit: Psychology"
    },
    {
        "url": "https://www.psychologytoday.com/us/blog/the-athletes-way/rss2.xml",
        "name": "Psychology Today"
    }
]

# --- Ключевые слова ---
KEYWORDS = [
    'психология', 'терапия', 'мотивация', 'саморазвитие', 'тревожность',
    'депрессия', 'осознанность', 'коуч', 'психолог', 'mental health',
    'therapy', 'mindfulness', 'self-improvement', 'anxiety', 'depression'
]

# --- Отправка в Telegram ---
def send_message(chat_id, text, parse_mode='Markdown', disable_preview=False):
    if not chat_id:
        print("❌ chat_id не задан")
        return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": not disable_preview
        }
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print(f"✅ Сообщение отправлено в {chat_id}")
        else:
            print(f"❌ Ошибка отправки: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"❌ Ошибка при отправке: {e}")

# --- Поиск статей ---
def search_articles():
    articles = []
    from_date = datetime.now() - timedelta(days=3)

    for feed in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries:
                # Проверяем дату
                published = entry.get('published_parsed') or entry.get('updated_parsed')
                if published:
                    pub_date = datetime(*published[:6])
                    if pub_date < from_date:
                        continue

                title = entry.get('title', '').lower()
                summary = entry.get('summary', '').lower()

                # Фильтр по ключевым словам
                if any(kw.lower() in title or kw.lower() in summary for kw in KEYWORDS):
                    articles.append({
                        'title': entry.get('title', 'Без заголовка'),
                        'url': entry.get('link'),
                        'source': feed["name"]
                    })
        except Exception as e:
            print(f"Ошибка RSS {feed['name']}: {e}")

    return articles

# --- Основная функция ---
def main():
    print("🚀 Бот запущен (режим GitHub Actions)")
    try:
        seen_urls = load_cache()
        raw_articles = search_articles()
        print(f"Получено статей: {len(raw_articles)}")

        # Фильтруем дубли
        new_articles = [a for a in raw_articles if a.get('url') not in seen_urls]

        # Ограничиваем 20 новостями
        selected = new_articles[:20]
        print(f"Отправляем: {len(selected)} новостей")

        # --- Отправляем логику поиска ---
        logic_msg = "🔍 *Логика поиска:*\n\n"
        logic_msg += "Бот ищет посты и статьи по теме:\n"
        logic_msg += "• Психология\n"
        logic_msg += "• Терапия и саморазвитие\n"
        logic_msg += "• Мотивация и осознанность\n"
        logic_msg += "• Источники: Habr, N+1, Reddit, Psychology Today\n"
        logic_msg += "• Новости за последние 3 дня\n"
        logic_msg += "• Без дублей — с использованием кеша\n"

        if ADMIN_ID:
            try:
                admin_id_int = int(ADMIN_ID)
                send_message(admin_id_int, logic_msg, disable_preview=True)
            except ValueError:
                print(f"❌ ADMIN_ID '{ADMIN_ID}' не является числом")

        # --- Отправляем новости ---
        if selected:
            batch_size = 5
            msg = "📬 *Новости по психологии*\n\n"
            for i, art in enumerate(selected, 1):
                title_ru = translate_text(art['title'])
                source = art.get('source', 'Неизвестно')
                msg += f"📌 *{title_ru}*\n🌐 {source}\n🔗 {art['url']}\n\n"

                if i % batch_size == 0 or i == len(selected):
                    if ADMIN_ID:
                        try:
                            admin_id_int = int(ADMIN_ID)
                            send_message(admin_id_int, msg, disable_preview=False)
                        except ValueError:
                            print(f"❌ ADMIN_ID '{ADMIN_ID}' не является числом")
                    msg = ""
                    if i != len(selected):
                        msg = "\n"

            # Обновляем кеш
            for art in selected:
                url = art.get('url')
                if url:
                    seen_urls.add(url)
            save_cache(seen_urls)

        else:
            # Даже если новостей нет
            if ADMIN_ID:
                no_news_msg = "📭 *Новых статей по психологии пока нет.*\n"
                no_news_msg += "Следующий поиск — завтра в 18:00."
                send_message(int(ADMIN_ID), no_news_msg, disable_preview=False)

        print("✅ Рассылка завершена.")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)[:500]}"
        print(f"🔴 Ошибка: {error_msg}")
        if ADMIN_ID and TOKEN:
            send_message(ADMIN_ID, f"❌ Ошибка: `{error_msg}`")

# --- Запуск ---
if __name__ == "__main__":
    main()