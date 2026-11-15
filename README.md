# SiteCrawler: Android bulk scraper / crawler / JSON extractor

```
backend/   FastAPI crawler service (Python)
app/       Expo / React Native Android app (JavaScript)
```

## What it does
- **Browse** any public page in the in-app browser, then **Extract page** (one page → JSON) or **Crawl site**.
- **Crawls the whole site**, not just what you're viewing: follows links breadth-first, and also seeds from `robots.txt` / `sitemap.xml`, so pages not linked from the start page are found.
- Stays on the **same site** (optional subdomains), skips binaries/duplicates/tracking params, honors include/exclude regexes.
- Extracts structured **JSON** per page: title, description, canonical, OpenGraph/Twitter, headings, JSON-LD, tables, links, images, emails, phones, text, plus your own **CSS-selector fields** (`price=.price`, `hero=img.hero@src`).
- Jobs run server-side (keep going if the app closes), with live progress, stop, delete, and **JSON / NDJSON export**.

## Run the backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000        # API docs at /docs
# or: docker build -t sitecrawler . && docker run -p 8000:8000 -v crawl-data:/data sitecrawler
```
Environment variables: `API_KEY` (require `X-API-Key`; **set this if the server is public**), `MAX_PAGES_HARD` (default 2000), `MAX_CONCURRENT_JOBS` (default 3), `DB_PATH`.

## Run the app
```bash
cd app && chmod +x setup.sh && ./setup.sh
cd ../sitecrawler-app && npx expo start      # scan QR with Expo Go
```
In **Settings**, set the server URL (`http://10.0.2.2:8000` on the emulator, your LAN IP on a phone, or your deployed HTTPS URL) and API key.
Build an installable APK with EAS: `npx eas-cli build -p android --profile preview`.

## Safety and limits (built in)
- **SSRF protection:** only public http(s) hosts; loopback, private, link-local and cloud-metadata addresses are refused, re-checked on every redirect hop.
- Respects `robots.txt` by default, identifies itself with a clear User-Agent, throttles per request (`delay_ms`), caps page size and page count.
- **JavaScript pages** are rendered in headless Chromium (Playwright) when `render_js` is `auto` (default, only for pages that look empty) or `always`. Install with `pip install playwright && playwright install chromium` (the Dockerfile already includes it). Without it the crawler falls back to static HTML.
- Not supported by design: logging in / private pages, CAPTCHA solving, and evading bot protection or rate limits. If a site blocks crawlers, use its official API or ask for permission.
- Only crawl sites you're allowed to, and check each site's terms of service.

## API summary
`POST /jobs` · `GET /jobs` · `GET /jobs/{id}` · `GET /jobs/{id}/results?after=&limit=` · `GET /jobs/{id}/pages/{pageId}` · `GET /jobs/{id}/export?format=json|ndjson` · `POST /jobs/{id}/cancel` · `DELETE /jobs/{id}` · `POST /extract`

## Deploy the backend on Render (free tier to start)
1. Render dashboard → **New → Blueprint** → select this repo (it reads `render.yaml`).
2. After the first deploy, copy the generated `API_KEY` from the service's Environment tab.
3. In the app's **Settings**, enter `https://<your-service>.onrender.com` and the API key.

Free-tier caveats: the service sleeps when idle (first request is slow), has 512 MB RAM (headless Chromium may run out of memory; set “JavaScript pages” to `off`/`auto` and keep parallel requests low, or upgrade) and has no disk, so job results disappear on restart. Export your JSON when a crawl finishes.

## Build the APK
GitHub → **Actions → Build Android APK → Run workflow**, then download `sitecrawler-apk` from the run's artifacts. (Workflow is untested; if it fails, `npx eas-cli build -p android --profile preview` is the alternative.)
