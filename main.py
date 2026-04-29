from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import json

app = FastAPI()

# Configure static files for HTML/CSS/JS
app.mount("/static", StaticFiles(directory="static"), name="static")

# FastAPI Route for Instagram scraping
@app.get("/instagram/{username}")
def scrape_instagram(username: str):
    try:
        url = f'https://www.instagram.com/{username}/'
        response = requests.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Instagram user not found.")

        soup = BeautifulSoup(response.text, 'html.parser')
        user_data = json.loads(soup.find('script', type='application/ld+json').string)
        return user_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# FastAPI Route for TikTok scraping
@app.get("/tiktok/{username}")
def scrape_tiktok(username: str):
    try:
        url = f'https://www.tiktok.com/@{username}'
        response = requests.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="TikTok user not found.")

        soup = BeautifulSoup(response.text, 'html.parser')
        user_data = soup.find('script', type='application/json').string
        return json.loads(user_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# HTML/CSS for frontend
html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Social Info Scraper</title>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <h1>Social Info Scraper</h1>
    <div class="container">
        <h2>Instagram Info</h2>
        <input type="text" id="instagram-username" placeholder="Enter Instagram username">
        <button onclick="fetchInstagramInfo()">Fetch Instagram Info</button>
        <div id="instagram-result"></div>

        <h2>TikTok Info</h2>
        <input type="text" id="tiktok-username" placeholder="Enter TikTok username">
        <button onclick="fetchTikTokInfo()">Fetch TikTok Info</button>
        <div id="tiktok-result"></div>
    </div>
    <script src="/static/scripts.js"></script>
</body>
</html>'''

# Save HTML response
@app.get("/")
def get_home():
    return HTMLResponse(content=html_content)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)