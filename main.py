from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import requests
import socket
from urllib.parse import urlparse
import time
import asyncio
from typing import List, Dict
import concurrent.futures

requests.packages.urllib3.disable_warnings()

app = FastAPI(title="URL Checker")

# Mount static jika diperlukan
# app.mount("/static", StaticFiles(directory="static"), name="static")

def check_single_url(url: str) -> Dict:
    url = url.strip()
    if not url:
        return None
    
    result = {
        "url": url,
        "status": "❌ Error",
        "provider": "Unknown",
        "tier": "",
        "latency": "-",
        "country": "-"
    }

    try:
        if not url.startswith("http"):
            url = "http://" + url
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if url.startswith("https") else 80)

        # Latency (TCP connect)
        start = time.time()
        sock = socket.create_connection((host, port), timeout=7)
        sock.close()
        result["latency"] = f"{round((time.time() - start)*1000, 1)} ms"

        # IP Info
        ip = socket.gethostbyname(host)
        r = requests.get(f"http://ip-api.com/json/{ip}?fields=status,country,isp,org,as,hosting", timeout=8)
        data = r.json()

        if data.get('status') == 'success':
            text = f"{data.get('isp','')} {data.get('org','')} {data.get('as','')}".lower()
            result["country"] = data.get('country', '-')

            providers = {
                "Cloudflare": ("Cloudflare", "🏆 Enterprise"),
                "Amazon AWS": ("Amazon AWS", "🏆 Enterprise"),
                "Google Cloud": ("Google Cloud", "🏆 Enterprise"),
                "Microsoft Azure": ("Microsoft Azure", "🏆 Enterprise"),
                "Hetzner": ("Hetzner", "⭐ Premium"),
                "OVH": ("OVH", "⭐ Premium"),
                "Contabo": ("Contabo", "⭐ Premium"),
                "DigitalOcean": ("DigitalOcean", "⭐ Premium"),
                "Vultr": ("Vultr", "⭐ Premium"),
            }

            for name, (prov, tier) in providers.items():
                if name.lower() in text:
                    result["provider"] = prov
                    result["tier"] = tier
                    break
            else:
                result["provider"] = data.get('isp', 'Unknown')

        # HTTP Status
        r2 = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
        result["status"] = "✅ Online" if r2.status_code in (200, 403, 429) else f"⚠️ {r2.status_code}"

    except Exception as e:
        result["status"] = f"❌ {str(e)[:30]}"

    return result


@app.get("/", response_class=HTMLResponse)
async def home():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>URL Checker</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f8f9fa; }
            textarea { width: 100%; height: 200px; font-family: monospace; }
            button { padding: 12px 24px; font-size: 16px; background: #0070f3; color: white; border: none; border-radius: 6px; cursor: pointer; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; background: white; }
            th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
            th { background: #f1f1f1; }
            .online { color: green; }
            .error { color: red; }
        </style>
    </head>
    <body>
        <h1>🌐 URL Checker</h1>
        <p>Paste semua URL (satu per baris)</p>
        <textarea id="urls" placeholder="contoh.com&#10;https://google.com&#10;github.com"></textarea><br><br>
        <button onclick="checkUrls()">🔍 Check Semua URL</button>
        
        <div id="result"></div>

        <script>
        async function checkUrls() {
            const text = document.getElementById('urls').value.trim();
            if (!text) return alert('Masukkan URL!');
            
            const urls = text.split('\\n').filter(u => u.trim());
            
            const res = await fetch('/api/check', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({urls: urls})
            });
            
            const data = await res.json();
            let html = `<h2>Hasil (${data.length} URL)</h2>`;
            html += `<table><tr>
                <th>No</th><th>URL</th><th>Status</th><th>Provider</th>
                <th>Tier</th><th>Latency</th><th>Country</th>
            </tr>`;
            
            data.forEach((item, i) => {
                html += `<tr>
                    <td>${i+1}</td>
                    <td>${item.url}</td>
                    <td class="${item.status.includes('✅') ? 'online' : 'error'}">${item.status}</td>
                    <td>${item.provider}</td>
                    <td>${item.tier}</td>
                    <td>${item.latency}</td>
                    <td>${item.country}</td>
                </tr>`;
            });
            html += '</table>';
            document.getElementById('result').innerHTML = html;
        }
        </script>
    </body>
    </html>
    """
    return html


@app.post("/api/check")
async def check_urls(request: Request):
    data = await request.json()
    urls = data.get("urls", [])
    
    # Jalankan paralel (mirip ThreadPoolExecutor)
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(check_single_url, urls))
    
    return [r for r in results if r]


# Jalankan dengan: uvicorn main:app --reload (local testing)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
