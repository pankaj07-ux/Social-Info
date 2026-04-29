from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import re
import json
import os
import uvicorn

app = FastAPI()

HEADERS = {"User-Agent": "Mozilla/5.0"}

# -------------------------
# 🏠 FRONTEND (UI)
# -------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Social Finder Pro</title>
<script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>

<style>
body {
    font-family: Arial;
    background: #0f172a;
    color: white;
    text-align: center;
    padding-top: 50px;
}

.box {
    background: #111827;
    width: 420px;
    margin: auto;
    padding: 20px;
    border-radius: 15px;
}

input, select, button {
    width: 90%;
    padding: 10px;
    margin: 6px;
    border-radius: 8px;
    border: none;
}

button {
    background: #22c55e;
    font-weight: bold;
    cursor: pointer;
}

.card {
    margin-top: 15px;
    background: #0b1220;
    padding: 15px;
    border-radius: 12px;
}

img {
    width: 90px;
    height: 90px;
    border-radius: 50%;
}

.download {
    background: #3b82f6;
    color: white;
}
</style>
</head>

<body>

<h1>🚀 Social Finder Pro</h1>

<div class="box">

<select id="platform">
<option value="tiktok">TikTok</option>
<option value="instagram">Instagram</option>
</select>

<input id="username" placeholder="Enter username">

<button onclick="search()">Search</button>

<div id="result"></div>

</div>

<script>

async function search(){
    let p = document.getElementById("platform").value;
    let u = document.getElementById("username").value;

    let res = await fetch(`/social/${p}/${u}`);
    let data = await res.json();

    if(!data.data){
        document.getElementById("result").innerHTML = "❌ User not found";
        return;
    }

    let d = data.data;

    document.getElementById("result").innerHTML = `
    <div class="card" id="card">
        <img src="${d.avatar}">
        <h3>@${d.username}</h3>
        <p>${d.bio || ""}</p>
        <p>👥 ${d.followers}</p>
        <p>➡ ${d.following}</p>

        <button class="download" onclick="downloadCard()">⬇ Download Card</button>
    </div>
    `;
}

function downloadCard(){
    html2canvas(document.getElementById("card")).then(canvas => {
        let a = document.createElement("a");
        a.download = "profile.png";
        a.href = canvas.toDataURL();
        a.click();
    });
}

</script>

</body>
</html>
"""

# -------------------------
# 🔵 TIKTOK SCRAPER
# -------------------------
async def get_tiktok(username: str):
    url = f"https://www.tiktok.com/@{username}"

    async with httpx.AsyncClient(headers=HEADERS, timeout=20) as client:
        r = await client.get(url)

    match = re.search(
        r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>',
        r.text
    )

    if not match:
        return None

    try:
        data = json.loads(match.group(1))
        user_info = data["__DEFAULT_SCOPE__"]["webapp.user-detail"]["userInfo"]

        stats = user_info["stats"]
        user = user_info["user"]

        avatar = user.get("avatarLarger") or user.get("avatarMedium")

        return {
            "platform": "tiktok",
            "username": user.get("uniqueId"),
            "bio": user.get("signature"),
            "followers": stats.get("followerCount"),
            "following": stats.get("followingCount"),
            "likes": stats.get("heart"),
            "avatar": avatar
        }
    except:
        return None

# -------------------------
# 🟣 INSTAGRAM
# -------------------------
async def get_instagram(username: str):
    url = f"https://www.instagram.com/{username}/?__a=1"

    async with httpx.AsyncClient(headers=HEADERS, timeout=20) as client:
        r = await client.get(url)

    if r.status_code != 200:
        return None

    try:
        data = r.json()
        user = data["graphql"]["user"]

        return {
            "platform": "instagram",
            "username": username,
            "bio": user.get("biography"),
            "followers": user["edge_followed_by"]["count"],
            "following": user["edge_follow"]["count"],
            "avatar": user.get("profile_pic_url_hd")
        }
    except:
        return None

# -------------------------
# 🌐 API ENDPOINT
# -------------------------
@app.get("/social/{platform}/{username}")
async def social(platform: str, username: str):

    if platform == "tiktok":
        data = await get_tiktok(username)

    elif platform == "instagram":
        data = await get_instagram(username)

    else:
        raise HTTPException(400, "Invalid platform")

    if not data:
        raise HTTPException(404, "User not found")

    return {"status": "success", "data": data}

# -------------------------
# ▶ RUN SERVER
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)