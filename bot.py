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

# --- Источники: 5 русскоязычных, 5 англоязычных ---
SOURCES = [
    # 🇷🇺 Русскоязычные
    {"url": "https://habr.com/ru/rss/search/?q=психология&target_type=posts&order=date", "name": "Habr: Психология", "lang": "ru"},
    {"url": "https://nplus1.ru/rss", "name": "N+1: Наука", "lang": "ru"},
    {"url": "https://tjournal.ru/rss", "name": "TJournal: Саморазвитие", "lang": "ru"},
    {"url": "https://vc.ru/search/rss?query=психология", "name": "VC.ru: Психология", "lang": "ru"},
    {"url": "https://arzamas.academy/courses?rss", "name": "Arzamas: Психология", "lang": "ru"},

    # 🌍 Англоязычные
    {"url": "https://www.reddit.com/r/Psychology.rss", "name": "Reddit: Psychology", "lang": "en"},
    {"url": "https://www.psychologytoday.com/us/blog/the-athletes-way/rss2.xml", "name": "Psychology Today", "lang": "en"},
    {"url": "https://rss.sciencedaily.com/mind_brain/psychology.xml", "name": "ScienceDaily: Psychology", "lang": "en"},
    {"url": "https://www.sciencenews.org/category/psychology/feed", "name": "ScienceNews: Psychology", "lang": "en"},
    {"url": "https://theconversation.com/health/rss", "name": "The Conversation: Health", "lang": "en"}
]

# --- Ключевые слова ---
KEYWORDS = [
    'психология', 'терапия', 'мотивация', 'саморазвитие', 'тревожность',
    'депрессия', 'осознанность', 'коуч', 'психолог', 'mental health',
    'therapy', 'mindfulness', 'self-improvement', 'anxiety', 'depression',
    'counseling', 'psychotherapy', 'wellbeing', 'emotional health'
]

# --- Отправка в Telegram ---
def send_message(chat_id, text, parse_mode=None, disable_preview=False):
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

# --- Поиск статей за 7 дней ---
def search_articles():
    articles = []
    from_date = datetime.now() - timedelta(days=7)  # 1 неделя

    for src in SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            if feed.bozo:
                print(f"⚠️ RSS {src['name']} повреждён")
                continue

            for entry in feed.entries:
                # Проверяем дату
                published = entry.get('published_parsed') or entry.get('updated_parsed')
                if not published:
                    continue
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
                        'source': src["name"],
                        'lang': src["lang"],
                        'published': pub_date.isoformat()
                    })
        except Exception as e:
            print(f"❌ Ошибка RSS {src['name']}: {e}")

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

        if not selected:
            print("Нет новых новостей для отправки.")
            if ADMIN_ID:
                try:
                    admin_id_int = int(ADMIN_ID)
                    send_message(admin_id_int, "📭 Новых статей по психологии пока нет.", disable_preview=True)
                except ValueError:
                    print(f"❌ ADMIN_ID '{ADMIN_ID}' не является числом")
            return

        # Отправляем порциями по 5
        batch_size = 5
        msg = "📬 *Дайджест по психологии (последние 7 дней)*\n\n"
        for i, art in enumerate(selected, 1):
            title = art['title']
            if art['lang'] == 'en':
                title = translate_text(title)
            source = art.get('source', 'Неизвестно')
            msg += f"📌 {title}\n🌐 {source}\n🔗 {art['url']}\n\n"

            if i % batch_size == 0 or i == len(selected):
                if ADMIN_ID:
                    try:
                        admin_id_int = int(ADMIN_ID)
                        send_message(admin_id_int, msg, parse_mode=None, disable_preview=False)
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

        print("✅ Рассылка завершена.")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)[:500]}"
        print(f"🔴 Ошибка: {error_msg}")
        if ADMIN_ID and TOKEN:
            send_message(ADMIN_ID, f"❌ Ошибка: `{error_msg}`", parse_mode=None)

# --- Запуск ---
if __name__ == "__main__":
    main()
