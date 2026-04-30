"""
Social Media Profile Lookup API  —  with Rotating Proxy System
===============================================================
Endpoints:
  GET /tiktok?username=<username>
  GET /instagram?username=<username>
  GET /facebook?username=<username>
  GET /youtube?username=<username>

  GET /proxies            → list all proxies + their status
  POST /proxies/add       → add a new proxy  { "proxy": "http://user:pass@host:port" }
  DELETE /proxies/remove  → remove a proxy   { "proxy": "http://..." }
  GET /proxies/test       → test all proxies right now

Install:
  pip install fastapi uvicorn httpx beautifulsoup4

════════════════════════════════════════════
PORT SYSTEM  (automatic — kuch karne ki zaroorat nahi)
════════════════════════════════════════════
  Termux / Local  →  PORT env variable nahi mila toh port 8000 use hoga
  Render / Railway / Fly.io / Heroku  →  PORT env variable automatically
                                         platform set karta hai, wo use hoga

  Custom port chahiye?
    PORT=9090 python main.py

════════════════════════════════════════════
HOW TO ADD YOUR PROXIES
════════════════════════════════════════════
Option 1 — Edit PROXY_LIST below (recommended for static proxies)
Option 2 — Runtime via POST /proxies/add
Option 3 — Set env var:  PROXIES="http://u:p@h1:p1,http://u:p@h2:p2"

Proxy formats supported:
  http://host:port
  http://user:password@host:port
  socks5://user:password@host:port
────────────────────────────────────────────
"""

from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
import httpx
from bs4 import BeautifulSoup
import json
import re
import random
import asyncio
import time
import os
from typing import Optional
from dataclasses import dataclass

# ============================================================
# STAR  ADD YOUR PROXIES HERE  STAR
# ============================================================
PROXY_LIST: list[str] = [
    # "http://user:password@host:port",
    # "http://host:port",
    # "socks5://user:password@host:port",
]

# Also reads from environment variable
_env_proxies = os.environ.get("PROXIES", "")
if _env_proxies:
    PROXY_LIST += [p.strip() for p in _env_proxies.split(",") if p.strip()]


# ============================================================
# Proxy Manager
# ============================================================

@dataclass
class ProxyEntry:
    url: str
    failures: int = 0
    successes: int = 0
    last_used: float = 0.0
    last_failure: float = 0.0
    banned_until: float = 0.0

    @property
    def is_available(self) -> bool:
        return time.time() > self.banned_until

    @property
    def score(self) -> float:
        """Higher score = better proxy to pick next."""
        if not self.is_available:
            return -1.0
        total = self.successes + self.failures
        success_rate = self.successes / total if total else 0.5
        freshness_penalty = 1 / (1 + time.time() - self.last_used)
        return success_rate - freshness_penalty * 0.1


class ProxyManager:
    """
    Rotating proxy pool with:
    - Automatic failure tracking & cooldown banning
    - Score-based selection (best proxy first)
    - Runtime add/remove
    - Health test endpoint
    """

    COOLDOWN_SECONDS = 120   # ban proxy for 2 min after a failure
    MAX_FAILURES     = 5     # consecutive failures before long ban
    LONG_BAN_SECONDS = 600   # 10-min ban for persistently bad proxies

    def __init__(self, proxies: list[str]):
        self._lock = asyncio.Lock()
        self._pool: list[ProxyEntry] = [ProxyEntry(url=p) for p in proxies]

    # ─── Public API ──────────────────────────────────────────

    async def add(self, proxy_url: str):
        async with self._lock:
            existing = {p.url for p in self._pool}
            if proxy_url not in existing:
                self._pool.append(ProxyEntry(url=proxy_url))

    async def remove(self, proxy_url: str):
        async with self._lock:
            self._pool = [p for p in self._pool if p.url != proxy_url]

    async def pick(self) -> Optional[str]:
        """Return best available proxy URL, or None to go direct."""
        async with self._lock:
            available = [p for p in self._pool if p.is_available]
            if not available:
                return None
            best = max(available, key=lambda p: p.score)
            best.last_used = time.time()
            return best.url

    async def report_success(self, proxy_url: Optional[str]):
        if not proxy_url:
            return
        async with self._lock:
            entry = self._find(proxy_url)
            if entry:
                entry.successes += 1
                entry.failures = 0   # reset consecutive count

    async def report_failure(self, proxy_url: Optional[str]):
        if not proxy_url:
            return
        async with self._lock:
            entry = self._find(proxy_url)
            if entry:
                entry.failures += 1
                entry.last_failure = time.time()
                ban_time = (
                    self.LONG_BAN_SECONDS
                    if entry.failures >= self.MAX_FAILURES
                    else self.COOLDOWN_SECONDS
                )
                entry.banned_until = time.time() + ban_time

    async def status(self) -> list[dict]:
        async with self._lock:
            now = time.time()
            return [
                {
                    "proxy": p.url,
                    "available": p.is_available,
                    "successes": p.successes,
                    "failures": p.failures,
                    "banned_for_seconds": max(0, round(p.banned_until - now)),
                    "score": round(p.score, 3),
                }
                for p in self._pool
            ]

    async def test_all(self) -> list[dict]:
        """Verify each proxy against httpbin.org/ip."""
        async with self._lock:
            pool_copy = list(self._pool)

        results = []
        for entry in pool_copy:
            ok = False
            latency_ms = None
            detected_ip = None
            try:
                t0 = time.time()
                async with httpx.AsyncClient(proxy=entry.url, timeout=10) as client:
                    r = await client.get("https://httpbin.org/ip")
                    ok = r.status_code == 200
                    if ok:
                        detected_ip = r.json().get("origin")
                latency_ms = round((time.time() - t0) * 1000)
            except Exception as exc:
                latency_ms = None
                detected_ip = str(exc)

            if ok:
                await self.report_success(entry.url)
            else:
                await self.report_failure(entry.url)

            results.append({
                "proxy": entry.url,
                "working": ok,
                "latency_ms": latency_ms,
                "ip_seen": detected_ip,
            })
        return results

    def _find(self, url: str) -> Optional[ProxyEntry]:
        for p in self._pool:
            if p.url == url:
                return p
        return None


# Global singleton
proxy_manager = ProxyManager(PROXY_LIST)


# ============================================================
# HTTP helper: fetch with rotating proxy + auto-retry
# ============================================================

HEADERS_POOL = [
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        ),
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
]


def get_headers(extra: dict = None) -> dict:
    h = random.choice(HEADERS_POOL).copy()
    if extra:
        h.update(extra)
    return h


async def fetch_with_proxy(
    url: str,
    headers: dict = None,
    max_retries: int = 3,
    timeout: int = 15,
) -> httpx.Response:
    """
    Fetch a URL using the rotating proxy pool.

    Flow per attempt:
      1. Pick best available proxy (or None = direct)
      2. Make request
      3a. Success (2xx/3xx/404) → report success, return response
      3b. Bot-block (403/429/503) → report failure, wait, retry with next proxy
      3c. Network error → report failure, wait, retry
    Raises HTTPException(503) if all retries fail.
    """
    if headers is None:
        headers = get_headers()

    last_error = "Unknown error"
    tried_proxies: set[str] = set()

    for attempt in range(max_retries):
        proxy_url = await proxy_manager.pick()

        # Don't retry with the same bad proxy
        if proxy_url in tried_proxies:
            proxy_url = None
        if proxy_url:
            tried_proxies.add(proxy_url)

        proxy_label = proxy_url or "direct (no proxy)"

        try:
            client_kwargs: dict = {
                "follow_redirects": True,
                "timeout": timeout,
                "headers": headers,
            }
            if proxy_url:
                client_kwargs["proxy"] = proxy_url

            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.get(url)

            # Treat bot-detection codes as soft failures (retry)
            if resp.status_code in (403, 429, 503) and attempt < max_retries - 1:
                await proxy_manager.report_failure(proxy_url)
                last_error = f"HTTP {resp.status_code} via [{proxy_label}]"
                await asyncio.sleep(1.5 * (attempt + 1))
                continue

            await proxy_manager.report_success(proxy_url)
            return resp

        except (httpx.ProxyError, httpx.ConnectError, httpx.TimeoutException) as exc:
            await proxy_manager.report_failure(proxy_url)
            last_error = f"{type(exc).__name__} via [{proxy_label}]: {exc}"
            await asyncio.sleep(1.0 * (attempt + 1))

        except Exception as exc:
            last_error = f"Unexpected error: {exc}"
            break

    raise HTTPException(
        status_code=503,
        detail=f"Request failed after {max_retries} attempts. Last error: {last_error}",
    )


# ============================================================
# Utility
# ============================================================

def fmt_num(n) -> str:
    try:
        n = int(str(n).replace(",", ""))
        if n >= 1_000_000_000:
            return f"{n / 1_000_000_000:.1f}B"
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)
    except Exception:
        return str(n)


# ============================================================
# FastAPI app
# ============================================================

app = FastAPI(
    title="Social Media Lookup API",
    description=(
        "Fetch public profile details from TikTok, Instagram, Facebook, YouTube. "
        "Includes rotating proxy support with health tracking."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Proxy Management Endpoints
# ─────────────────────────────────────────────────────────────

@app.get("/proxies", tags=["Proxy Management"])
async def list_proxies():
    """List all proxies and their current health/status."""
    pool = await proxy_manager.status()
    return {
        "total": len(pool),
        "available": sum(1 for p in pool if p["available"]),
        "proxies": pool,
        "tip": (
            "No proxies? Add them via POST /proxies/add or edit PROXY_LIST in main.py. "
            "Without proxies, all requests go direct."
        ),
    }


@app.post("/proxies/add", tags=["Proxy Management"])
async def add_proxy(proxy: str = Body(..., embed=True)):
    """
    Add a proxy at runtime.
    Body JSON: { "proxy": "http://user:pass@host:port" }
    """
    if not proxy.startswith(("http://", "https://", "socks5://")):
        raise HTTPException(
            status_code=400,
            detail="Proxy must start with http://, https://, or socks5://",
        )
    await proxy_manager.add(proxy)
    return {"message": "Proxy added", "proxy": proxy}


@app.delete("/proxies/remove", tags=["Proxy Management"])
async def remove_proxy(proxy: str = Body(..., embed=True)):
    """
    Remove a proxy from the pool.
    Body JSON: { "proxy": "http://..." }
    """
    await proxy_manager.remove(proxy)
    return {"message": "Proxy removed", "proxy": proxy}


@app.get("/proxies/test", tags=["Proxy Management"])
async def test_proxies():
    """
    Test every proxy against httpbin.org/ip.
    Shows working status, latency, and the IP the proxy exposes.
    """
    pool = await proxy_manager.status()
    if not pool:
        return {
            "message": "No proxies configured — add some via POST /proxies/add",
            "results": [],
        }
    results = await proxy_manager.test_all()
    working = sum(1 for r in results if r["working"])
    return {
        "working": working,
        "total": len(results),
        "results": results,
    }


# ─────────────────────────────────────────────────────────────
# TikTok
# ─────────────────────────────────────────────────────────────

@app.get("/tiktok", tags=["Social Media"])
async def tiktok_profile(
    username: str = Query(..., description="TikTok username without @")
):
    """Fetch TikTok public profile — followers, following, likes, bio, verified."""
    url = f"https://www.tiktok.com/@{username}"

    resp = await fetch_with_proxy(
        url,
        headers=get_headers({"Referer": "https://www.tiktok.com/"}),
    )

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="TikTok user not found")

    html = resp.text

    match = re.search(
        r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
        html, re.DOTALL,
    )
    if not match:
        match = re.search(
            r'<script id="SIGI_STATE"[^>]*>(.*?)</script>', html, re.DOTALL
        )
    if not match:
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not parse TikTok response. "
                "TikTok may be blocking — add more proxies at POST /proxies/add"
            ),
        )

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Invalid JSON received from TikTok")

    try:
        user_detail = (
            data
            .get("__DEFAULT_SCOPE__", {})
            .get("webapp.user-detail", {})
            .get("userInfo", {})
        )
        if not user_detail:
            user_detail = data.get("UserPage", {}).get("uniqueId", {})
        user  = user_detail.get("user",  {})
        stats = user_detail.get("stats", {})
    except Exception:
        raise HTTPException(status_code=502, detail="Unexpected TikTok data structure")

    if not user:
        raise HTTPException(status_code=404, detail="TikTok user data not found")

    private = user.get("privateAccount", False)

    result = {
        "platform":     "TikTok",
        "username":     user.get("uniqueId", username),
        "display_name": user.get("nickname"),
        "bio":          user.get("signature"),
        "avatar":       user.get("avatarLarger"),
        "verified":     user.get("verified", False),
        "private":      private,
        "profile_url":  url,
    }

    if private:
        result["message"] = "This account is private"
    else:
        result.update({
            "followers": fmt_num(stats.get("followerCount", 0)),
            "following": fmt_num(stats.get("followingCount", 0)),
            "likes":     fmt_num(stats.get("heartCount",    0)),
            "videos":    fmt_num(stats.get("videoCount",    0)),
        })

    return result


# ─────────────────────────────────────────────────────────────
# Instagram
# ─────────────────────────────────────────────────────────────

@app.get("/instagram", tags=["Social Media"])
async def instagram_profile(
    username: str = Query(..., description="Instagram username")
):
    """Fetch Instagram public profile — followers, following, posts, bio, verified."""
    url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"

    resp = await fetch_with_proxy(
        url,
        headers=get_headers({
            "Referer": "https://www.instagram.com/",
            "X-IG-App-ID": "936619743392459",
        }),
    )

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Instagram user not found")

    try:
        data = resp.json()
        user = data["graphql"]["user"]
    except Exception:
        return await _instagram_html_fallback(username)

    private = user.get("is_private", False)

    result = {
        "platform":     "Instagram",
        "username":     user.get("username", username),
        "display_name": user.get("full_name"),
        "bio":          user.get("biography"),
        "avatar":       user.get("profile_pic_url_hd") or user.get("profile_pic_url"),
        "verified":     user.get("is_verified", False),
        "private":      private,
        "profile_url":  f"https://www.instagram.com/{username}/",
        "external_url": user.get("external_url"),
    }

    if private:
        result["message"] = "This account is private"
    else:
        result.update({
            "followers": fmt_num(user["edge_followed_by"]["count"]),
            "following": fmt_num(user["edge_follow"]["count"]),
            "posts":     fmt_num(user["edge_owner_to_timeline_media"]["count"]),
        })

    return result


async def _instagram_html_fallback(username: str) -> dict:
    url  = f"https://www.instagram.com/{username}/"
    resp = await fetch_with_proxy(url, headers=get_headers())
    soup = BeautifulSoup(resp.text, "html.parser")

    desc_tag = soup.find("meta", attrs={"name": "description"})
    desc = desc_tag["content"] if desc_tag else ""

    followers = following = posts = None
    m = re.search(r"([\d,]+)\s+Followers", desc)
    if m: followers = m.group(1).replace(",", "")
    m = re.search(r"([\d,]+)\s+Following", desc)
    if m: following = m.group(1).replace(",", "")
    m = re.search(r"([\d,]+)\s+Posts", desc)
    if m: posts = m.group(1).replace(",", "")

    title = soup.find("title")
    display_name = title.text.split("•")[0].strip() if title else username
    private = followers is None

    result = {
        "platform":     "Instagram",
        "username":     username,
        "display_name": display_name,
        "profile_url":  url,
        "private":      private,
        "verified":     False,
        "note":         "Limited data — Instagram restricts scraping",
    }
    if private:
        result["message"] = "This account is private or data could not be retrieved"
    else:
        result.update({
            "followers": fmt_num(followers),
            "following": fmt_num(following),
            "posts":     fmt_num(posts),
        })
    return result


# ─────────────────────────────────────────────────────────────
# Facebook
# ─────────────────────────────────────────────────────────────

@app.get("/facebook", tags=["Social Media"])
async def facebook_profile(
    username: str = Query(..., description="Facebook username or page name")
):
    """Fetch Facebook public page/profile info."""
    url = f"https://www.facebook.com/{username}"

    resp = await fetch_with_proxy(
        url,
        headers=get_headers({"Referer": "https://www.facebook.com/"}),
    )

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Facebook profile not found")

    if "login" in str(resp.url) or "checkpoint" in str(resp.url):
        return {
            "platform":   "Facebook",
            "username":   username,
            "profile_url": url,
            "private":    True,
            "message":    "This account is private or requires login to view",
        }

    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag    = soup.find("title")
    display_name = title_tag.text.replace(" | Facebook", "").strip() if title_tag else username

    desc_tag = soup.find("meta", attrs={"name": "description"})
    desc = desc_tag["content"] if desc_tag else ""

    followers = likes = None
    m = re.search(r"([\d,\.]+[KMB]?)\s*(people\s+)?follow", desc, re.I)
    if m: followers = m.group(1)
    m = re.search(r"([\d,\.]+[KMB]?)\s*(people\s+)?like", desc, re.I)
    if m: likes = m.group(1)

    verified = False
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(script.string or "")
            if isinstance(ld, dict) and (ld.get("isVerified") or "VerifiedAccount" in str(ld)):
                verified = True
        except Exception:
            pass

    og_img = soup.find("meta", property="og:image")
    avatar = og_img["content"] if og_img else None

    result = {
        "platform":     "Facebook",
        "username":     username,
        "display_name": display_name,
        "bio":          desc[:300] if desc else None,
        "avatar":       avatar,
        "verified":     verified,
        "private":      False,
        "profile_url":  url,
    }
    if followers: result["followers"] = followers
    if likes:     result["likes"]     = likes

    if not followers and not likes:
        result["private"] = True
        result["message"] = "Profile is private or data is behind login wall"

    return result


# ─────────────────────────────────────────────────────────────
# YouTube
# ─────────────────────────────────────────────────────────────

@app.get("/youtube", tags=["Social Media"])
async def youtube_profile(
    username: str = Query(..., description="YouTube handle (without @) or channel name")
):
    """Fetch YouTube channel — subscribers, videos, bio, verified."""
    urls_to_try = [
        f"https://www.youtube.com/@{username}",
        f"https://www.youtube.com/c/{username}",
        f"https://www.youtube.com/user/{username}",
    ]

    html = final_url = None
    for url in urls_to_try:
        try:
            resp = await fetch_with_proxy(
                url,
                headers=get_headers({"Referer": "https://www.youtube.com/"}),
                max_retries=2,
            )
            if resp.status_code == 200 and "ytInitialData" in resp.text:
                html      = resp.text
                final_url = str(resp.url)
                break
        except Exception:
            continue

    if not html:
        raise HTTPException(status_code=404, detail="YouTube channel not found")

    match = re.search(r"var ytInitialData\s*=\s*(\{.*?\});</script>", html, re.DOTALL)
    if not match:
        raise HTTPException(status_code=502, detail="Could not parse YouTube page data")

    try:
        yt_data = json.loads(match.group(1))
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Invalid JSON from YouTube")

    try:
        header = (
            yt_data.get("header", {}).get("pageHeaderRenderer", {})
            or yt_data.get("header", {}).get("c4TabbedHeaderRenderer", {})
        )
        channel_meta = yt_data.get("metadata", {}).get("channelMetadataRenderer", {})
    except Exception:
        header = {}
        channel_meta = {}

    display_name = (
        channel_meta.get("title")
        or (header.get("pageTitle") if isinstance(header.get("pageTitle"), str) else None)
        or username
    )
    bio = channel_meta.get("description", "")

    avatar_url = None
    try:
        thumbs = channel_meta.get("avatar", {}).get("thumbnails", [])
        if thumbs:
            avatar_url = thumbs[-1].get("url")
    except Exception:
        pass

    verified = False
    try:
        for badge in header.get("badges", []):
            if "VERIFIED" in str(badge).upper():
                verified = True
                break
    except Exception:
        pass

    subscribers = None
    try:
        sub_text = header.get("subscriberCountText", {}).get("simpleText", "")
        if not sub_text:
            sub_text = (
                header
                .get("content", {})
                .get("pageHeaderViewModel", {})
                .get("metadata", {})
                .get("contentMetadataViewModel", {})
                .get("metadataRows", [{}])[0]
                .get("metadataParts", [{}])[0]
                .get("text", {})
                .get("content", "")
            )
        if sub_text:
            m = re.search(r"([\d,\.]+[KMB]?)", sub_text, re.I)
            if m:
                subscribers = m.group(1)
    except Exception:
        pass

    video_count = None
    try:
        tabs = (
            yt_data
            .get("contents", {})
            .get("twoColumnBrowseResultsRenderer", {})
            .get("tabs", [])
        )
        for tab in tabs:
            tab_r = tab.get("tabRenderer", {})
            if "Videos" in tab_r.get("title", ""):
                mv = re.search(
                    r'"videoCountText".*?"([\d,]+)\s*videos?"', str(tab_r), re.I
                )
                if mv:
                    video_count = mv.group(1).replace(",", "")
    except Exception:
        pass

    result = {
        "platform":     "YouTube",
        "username":     username,
        "display_name": display_name,
        "bio":          bio[:400] if bio else None,
        "avatar":       avatar_url,
        "verified":     verified,
        "private":      False,
        "profile_url":  final_url or urls_to_try[0],
        "subscribers":  subscribers or "N/A",
    }
    if video_count:
        result["videos"] = fmt_num(video_count)

    return result


# ─────────────────────────────────────────────────────────────
# Root / Info
# ─────────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
async def root():
    pool      = await proxy_manager.status()
    available = sum(1 for p in pool if p["available"])
    return {
        "name":    "Social Media Lookup API",
        "version": "2.0.0",
        "endpoints": {
            "TikTok":    "/tiktok?username=<username>",
            "Instagram": "/instagram?username=<username>",
            "Facebook":  "/facebook?username=<username>",
            "YouTube":   "/youtube?username=<username>",
        },
        "proxy_management": {
            "list":   "GET    /proxies",
            "add":    "POST   /proxies/add    { proxy: 'http://...' }",
            "remove": "DELETE /proxies/remove { proxy: 'http://...' }",
            "test":   "GET    /proxies/test",
        },
        "proxy_pool": {
            "total":     len(pool),
            "available": available,
        },
    }


# ─────────────────────────────────────────────────────────────
# Smart Port System
# ─────────────────────────────────────────────────────────────
# Priority:
#   1. PORT env variable  →  set by Render / Railway / Fly / Heroku automatically
#   2. DEFAULT_PORT below →  used when running locally (Termux, PC, etc.)
#
# Change default local port here if 8000 is taken:
DEFAULT_PORT = 8000

def get_port() -> int:
    """Read PORT from environment (cloud platforms), else use DEFAULT_PORT."""
    raw = os.environ.get("PORT", "").strip()
    if raw.isdigit():
        return int(raw)
    return DEFAULT_PORT

def is_cloud() -> bool:
    """Detect if running on a cloud platform."""
    cloud_hints = ["PORT", "RENDER", "RAILWAY_ENVIRONMENT",
                   "FLY_APP_NAME", "HEROKU_APP_NAME", "VERCEL"]
    return any(os.environ.get(h) for h in cloud_hints)


if __name__ == "__main__":
    import uvicorn

    port   = get_port()
    cloud  = is_cloud()

    # Cloud platforms handle restarts — disable reload there
    reload = not cloud

    print("=" * 52)
    print("  Social Media Lookup API  v2.0")
    print("=" * 52)
    print(f"  Environment : {'Cloud (auto-detected)' if cloud else 'Local (Termux / PC)'}")
    print(f"  Port        : {port}  {'(from $PORT env)' if cloud else '(default — set PORT= to change)'}")
    print(f"  Hot-reload  : {'OFF (cloud mode)' if not reload else 'ON'}")
    print(f"  Proxy pool  : {len(PROXY_LIST)} proxies configured")
    print("=" * 52)
    print(f"  Docs  →  http://localhost:{port}/docs")
    print(f"  API   →  http://localhost:{port}/")
    print("=" * 52)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",   # 0.0.0.0 = accessible from outside (required for cloud)
        port=port,
        reload=reload,
    )
