from pathlib import Path
import sys
import os
import feedparser
import tomllib
import httpx
import sqlite3
import math
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# config
def get_app_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home()
    app_dir = base / ".briefd"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir

APP_DIR = get_app_dir()
DB_PATH = APP_DIR / "briefd.db" 
CONFIG_PATH = APP_DIR / "config.toml"

def load_config(path=CONFIG_PATH):
    with open(path, "rb") as f:
        return tomllib.load(f)

def save_display_pref(key: str, value):
    config = load_config()
    if "display" not in config:
        config["display"] = {}
    config["display"][key] = value

    import tomli_w                      # tomllib is readonly :(
    with open(CONFIG_PATH, "wb") as f:
        tomli_w.dump(config, f)

def load_display_pref(key: str, default=None):
    config = load_config()
    return config.get("display", {}).get(key, default)

# database
def get_db() -> sqlite3.Connection:
    first_run = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if first_run:
        init_db(conn)
    return conn

def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            source TEXT,
            category TEXT,
            summary TEXT,
            published TEXT,
            read INTEGER DEFAULT 0,
            relevance REAL DEFAULT 0.0,
            fetched_at TEXT
        )
    """)
    conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS topic_scores (
            topic TEXT PRIMARY KEY,
            score REAL DEFAULT 0.0,
            interactions INTEGER DEFAULT 0,
            last_interaction TEXT
        )
    """)
    conn.commit()

def save_articles(conn, articles: list[dict]):
    for a in articles:
        conn.execute("""
            INSERT OR IGNORE INTO articles
            (id, title, url, source, category, summary, published, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            a["id"], a["title"], a["url"], a["source"],
            a["category"], a["summary"], a["published"],
            datetime.now().isoformat()
        ))
    conn.commit()

def load_cached_articles(conn, max_age_hours: int = 72) -> list[dict]:
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    rows = conn.execute("""
        SELECT * FROM articles
        WHERE fetched_at > ?
        GROUP BY url
        ORDER BY published DESC
    """, (cutoff,)).fetchall()
    articles = [dict(row) for row in rows]

    for a in articles:
        a["relevance"] = score_article(conn, a)
    articles.sort(key=lambda a: a["relevance"], reverse=True)
    return articles

def mark_as_read(conn, article_id: str):
    conn.execute("UPDATE articles SET read = 1 WHERE id = ?", (article_id,))
    conn.commit()

def mark_all_read(conn):
    conn.execute("UPDATE articles SET read = 1")
    conn.commit()

def clear_topic_scores(conn):
    conn.execute("DELETE FROM topic_scores")
    conn.commit()

# fetching
def fetch_all(sources: list[dict], conn, force: bool = False) -> list[dict]:
    if not force:
        cached = load_cached_articles(conn)
        if cached:
            return cached
    
    all_articles = []
    for source in sources:
        if not source.get("enabled", True):
            continue
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries:
                all_articles.append({
                    "id": entry.get("id", entry.link),
                    "title": entry.title,
                    "url": entry.link,
                    "source": source["name"],
                    "category": source["category"],
                    "summary": entry.get("summary", ""),
                    "published": entry.get("published", datetime.now().isoformat()),
                    "read": 0,
                    "relevance": 0.0
                })
        except Exception as e:
            print(f"Failed to fetch {source['name']}: {e}")
            continue
    
    if all_articles:
        save_articles(conn, all_articles)
    return all_articles

def fetch_article_content(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}         # Hopefully any sites won't block the bot with this?
        response = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        soup = BeautifulSoup(response.text, "html.parser")

        # remove shit
        for tag in soup(["script", "style", "nav", "footer", "aside", "iframe"]):
            tag.decompose()
        
        # get rid of <article> and/or <p> tags
        article = soup.find("article")
        if article:
            paragraphs = article.find_all("p")
        else:
            paragraphs = soup.find_all("p")
        
        text = "\n\n".join(p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 50) # stripped fully naked
        return text if text else "Could not get article content."
    except Exception as e:
        return f"Failed to fetch article: {e}"

def get_digest(conn, limit: int = 10) -> list[dict]:
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    rows = conn.execute("""
        SELECT * FROM articles
        WHERE fetched_at > ?
        ORDER BY published DESC
    """, (cutoff,)).fetchall()
    articles = [dict(row) for row in rows]
    for a in articles:
        a["relevance"] = score_article(conn, a)
    articles.sort(key=lambda a: a["relevance"], reverse=True)
    return articles[:limit]

# topics
def extract_topics(title: str, summary: str) -> list[str]:
    stopwords = {"the", "a", "an", "is", "in", "on", "at", "to", "for", 
                 "of", "and", "or", "but", "with", "after", "before"}
    text = f"{title} {summary}".lower()
    words = [w.strip(".,!?\"'") for w in text.split()]
    return list(set(w for w in words if len(w) > 3 and w not in stopwords))

def update_topic_scores(conn, article: dict, liked: bool):
    topics = extract_topics(article["title"], article["summary"])
    delta = 1.0 if liked else -1.0
    now = datetime.now().isoformat()
    for topic in topics:
        conn.execute("""
            INSERT INTO topic_scores (topic, score, interactions, last_interaction)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(topic) DO UPDATE SET
                score = score + ?,
                interactions = interactions + 1,
                last_interaction = ?
        """, (topic, delta, now, delta, now))
    conn.commit()

def decayed_score(score: float, last_interaction: str, half_life_days: int = 30) -> float:
    if not last_interaction:
        return score
    last = datetime.fromisoformat(last_interaction)
    days_ago = (datetime.now() - last).days

    decay = math.exp(-0.693 * days_ago / half_life_days)
    return score * decay

def score_article(conn, article: dict) -> float:
    topics = extract_topics(article["title"], article["summary"])
    if not topics:
        return 0.0
    placeholders = ",".join("?" * len(topics))
    rows = conn.execute(f"""
        SELECT score, interactions, last_interaction 
        FROM topic_scores WHERE topic IN ({placeholders})
    """, topics).fetchall()
    if not rows:
        return 0.0
    
    scores = []
    for score, interactions, last_interaction in rows:
        d = decayed_score(score, last_interaction)

        # boost topics the user has interacted with a lot
        interaction_boost = math.log1p(interactions) * 0.2
        scores.append(d + (interaction_boost if score > 0 else -interaction_boost))
    
    return sum(scores) / len(scores)