# 📱 Social Media Lookup API

A fast REST API to fetch **public profile details** from **TikTok, Instagram, Facebook, and YouTube** — with a built-in **rotating proxy system** and smart **auto port detection** for both local and cloud deployments.

---

## ✨ Features

- 🔍 Fetch followers, following, likes, bio, verified status & more
- 🔒 Detects **private accounts** automatically
- 🔄 **Rotating proxy system** with health tracking & auto-retry
- 🌐 Works on **Termux**, **Render**, **Railway**, **Fly.io**, **Heroku**
- ⚡ Smart **auto port detection** — no config needed for cloud platforms
- 📖 Auto-generated **Swagger UI docs** at `/docs`

---

## 🚀 Supported Platforms

| Platform  | Endpoint              | Data Fetched                                      |
|-----------|-----------------------|---------------------------------------------------|
| TikTok    | `/tiktok?username=`   | followers, following, likes, videos, bio, verified |
| Instagram | `/instagram?username=`| followers, following, posts, bio, verified         |
| Facebook  | `/facebook?username=` | followers, likes, bio, verified                   |
| YouTube   | `/youtube?username=`  | subscribers, videos, bio, verified                |

---

## 📦 Installation

### Requirements
- Python 3.10+

### Install dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ Running the API

### Locally (PC / Termux)
```bash
python main.py
```
> Runs on **port 8000** by default.

### Custom port
```bash
PORT=9090 python main.py
```

### Cloud (Render / Railway / Fly.io / Heroku)
Just deploy — the platform sets `$PORT` automatically and the code handles it.

**Render start command:**
```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## 📡 API Endpoints

### Social Media

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tiktok?username=<username>` | TikTok profile info |
| GET | `/instagram?username=<username>` | Instagram profile info |
| GET | `/facebook?username=<username>` | Facebook profile info |
| GET | `/youtube?username=<username>` | YouTube channel info |

### Proxy Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxies` | List all proxies + health status |
| POST | `/proxies/add` | Add a new proxy |
| DELETE | `/proxies/remove` | Remove a proxy |
| GET | `/proxies/test` | Test all proxies live |

---

## 🔁 Example Requests

### TikTok
```
GET http://localhost:8000/tiktok?username=charlidamelio
```

### Instagram
```
GET http://localhost:8000/instagram?username=cristiano
```

### YouTube
```
GET http://localhost:8000/youtube?username=MrBeast
```

---

## 📬 Example Response (Public Account)

```json
{
  "platform": "TikTok",
  "username": "charlidamelio",
  "display_name": "charli d'amelio",
  "bio": "...",
  "verified": true,
  "private": false,
  "followers": "151.2M",
  "following": "1.2K",
  "likes": "11.1B",
  "videos": "2.1K",
  "profile_url": "https://www.tiktok.com/@charlidamelio"
}
```

## 🔒 Private Account Response

```json
{
  "platform": "TikTok",
  "username": "someuser",
  "verified": false,
  "private": true,
  "message": "This account is private"
}
```

---

## 🔄 Proxy System

This API includes a **smart rotating proxy manager** with:

- ✅ Score-based proxy selection (best proxy picked first)
- 🔁 Auto-retry with a different proxy on failure
- ⏱️ Cooldown banning (2 min on failure, 10 min after 5+ failures)
- 📊 Per-proxy success/failure tracking

### Add Proxies

**Option 1 — Edit `main.py` directly:**
```python
PROXY_LIST: list[str] = [
    "http://user:password@host:port",
    "http://host:port",
    "socks5://user:password@host:port",
]
```

**Option 2 — Environment variable:**
```bash
PROXIES="http://u:p@host1:3128,http://u:p@host2:3128" python main.py
```

**Option 3 — Runtime API:**
```bash
curl -X POST http://localhost:8000/proxies/add \
  -H "Content-Type: application/json" \
  -d '{"proxy": "http://user:pass@host:port"}'
```

### Test Your Proxies
```
GET http://localhost:8000/proxies/test
```

Response:
```json
{
  "working": 2,
  "total": 3,
  "results": [
    { "proxy": "http://...", "working": true, "latency_ms": 312, "ip_seen": "12.34.56.78" },
    { "proxy": "http://...", "working": true, "latency_ms": 890, "ip_seen": "98.76.54.32" },
    { "proxy": "http://...", "working": false, "latency_ms": null, "ip_seen": "Connection refused" }
  ]
}
```

---

## 🗂️ Project Structure

```
├── main.py            # Main API — all logic here
├── requirements.txt   # Python dependencies
└── README.md          # You are here
```

---

## ⚠️ Notes

- **Instagram** is most restricted — may need a session cookie for consistent results
- **Facebook** shows limited data without login
- All platforms use **web scraping** — add proxies for production use
- This API works with **public profiles only**

---

## 📄 License

MIT — free to use, modify, and deploy.
