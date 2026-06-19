# briefd

A fast, customizable terminal news reader with personalized relevance scoring.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![Platform](https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20mac-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- Pulls from any RSS feed you configure
- Like/dislike articles to train your personal relevance score
- Scores decay over time so your feed stays fresh
- Caches articles locally
- Read/unread tracking
- Full article content fetched on demand
- Runs on anything with Python 3.11+

## Installation

```bash
git clone https://github.com/nicorajala/briefd
cd briefd
python setup.py
```

Restart your terminal, then just run:

```bash
briefd
```

On Windows, config and data are stored in `%APPDATA%\briefd\`.
On Linux/Mac, in `~/.briefd/`.

## Configuration

Edit your config file to add sources and set your interests:

**Windows:** `%APPDATA%\briefd\config.toml`
**Linux/Mac:** `~/.briefd/config.toml`

### Example Config:
```toml
[user]
name = "Bob"
interests = ["programming", "linux", "music"]

[[sources]]
name = "Hacker News"
url = "https://news.ycombinator.com/rss"
category = "tech"
enabled = true

[[sources]]
name = "BBC News"
url = "https://feeds.bbci.co.uk/news/rss.xml"
category = "world"
enabled = true

[[sources]]
name = "Some Blog"
url = "https://someblog.com/feed.xml"
category = "tech"
enabled = false   # disabled but saved for later
```

Any site with an RSS feed works. Most major news sites and blogs have one.

## Controls

| Key | Action |
|-----|--------|
| `↑` `↓` | Navigate articles |
| `Enter` | Open article |
| `^r` | Refresh feeds |
| `^q` | Quit |
| `Esc` | Back to feed |

You can like or dislike an article within the article view. You can either use a mouse to click or navigate the buttons with tab and shift + tab.

## How relevance scoring works

briefd tracks which topics you engage with. Like an article about Rust and
you'll see more Rust. Dislike everything about football and it sinks to the
bottom. Scores decay exponentially over time so old preferences don't haunt
you forever.

Nothing leaves your machine. All scoring data lives in a local SQLite database.

## Finding RSS feeds

Most sites have RSS even if they don't advertise it. Try:
- `https://site.com/rss`
- `https://site.com/feed`
- `https://site.com/rss.xml`

Or just Google `"site name" RSS feed`.

## License

MIT License - see more in the file.
Copyright (C) 2026 Nico Rajala. All rights reserved.
