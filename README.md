# Boostly API Support Engineer — Python Agent

Python/Playwright port of the Chrome extension, deployable as a Paperclip agent.

---

## Architecture

```
Paperclip ticket → POST /run → orchestrator.py → Playwright (headless Chromium)
                                     │
                         ┌───────────┼───────────────────┐
                     step1_auth  step3_plugins    step4_5_links_images
                     step6_listing_count  step7_search
                     step8_listing_validator  step9_pms_sync
                                     │
                              Claude API (only for final diagnosis)
                                     │
                              POST reply to Teamwork ticket
```

**Token economy:** All QA checks are deterministic Python — zero AI tokens. Claude is only called at the end to interpret the structured results and write a human-readable diagnosis.

---

## Step mapping (Chrome extension → Python agent)

| Extension file | Python file | What it does |
|---|---|---|
| `background.js` `startQA()` | `orchestrator.py` | Full orchestration flow |
| `step1-auth-checker.js` | `steps/step1_auth.py` | WP login check + credential login |
| `step3-plugin-checker.js` | `steps/step3_plugins.py` | Boostly plugin detection + site version |
| `step4-link-crawler.js` | `steps/step4_5_links_images.py` | Homepage link collection |
| `checkLinksInBackground()` | `steps/step4_5_links_images.py` | 404 link check |
| `step5-image-validator.js` | `steps/step4_5_links_images.py` | Homepage image validation |
| `checkSubPageImagesViaFetch()` | `steps/step4_5_links_images.py` | Sub-page image check |
| `step6-listing-counter.js` | `steps/step6_listing_count.py` | Published listing count |
| `step7-search-tester.js` | `steps/step7_search.py` | Search form presence check |
| `step7-results-collector.js` | `steps/step7_search.py` | Search results validation |
| `step8-listing-validator.js` | `steps/step8_listing_validator.py` | Listing page widget check |
| `step9-pms-tester.js` | `steps/step9_pms_sync.py` | Active PMS detection |
| `step9-sync-tester.js` | `steps/step9_pms_sync.py` | Sync button + XHR interception |
| `widgets/homey.js` | `steps/step8_listing_validator.py` | Homey widget checks |
| `widgets/ownerrez.js` | `steps/step8_listing_validator.py` | OwnerRez detection |
| `widgets/index.js` | `steps/step8_listing_validator.py` | Widget type router |

---

## Setup (local)

```bash
pip install -r requirements.txt
playwright install chromium --with-deps
python agent.py
```

Agent starts on `http://localhost:8000`.

---

## API

### Heartbeat (Paperclip requires this)
```
GET /heartbeat
→ {"status": "ok", "agent": "Boostly API Support Engineer", "running": false}
```

### Start a QA run
```
POST /run
Content-Type: application/json

{
  "site_url":    "https://blackhillsbungalows.com",
  "login_url":   "/boostly",       ← or "/wp-admin" for default WP login
  "wp_username": "admin",
  "wp_password": "your-password"
}

→ {"status": "started", "site": "https://blackhillsbungalows.com"}
```

### Poll for result
```
GET /report
→ {"status": "running"}              ← while running
→ {full JSON report + html_report}   ← when done
```

---

## Deploy on Paperclip

1. Build the Docker image:
   ```bash
   docker build -t boostly-api-support-engineer .
   ```

2. Push to your registry, then in Paperclip:
   - **Agent type:** HTTP
   - **Heartbeat URL:** `http://<your-host>:8000/heartbeat`
   - **Run URL:** `http://<your-host>:8000/run`

3. Paperclip will POST a support ticket payload to `/run`. Map ticket fields to:
   - `site_url` ← site URL from ticket
   - `login_url` ← `/boostly` (default for all Boostly sites)
   - `wp_username` / `wp_password` ← store as Paperclip secrets

---

## Login URL per site

| Site | Login URL |
|---|---|
| Most Boostly sites | `/boostly` |
| A few older sites | `/wp-admin` |

Pass the correct `login_url` in the run payload. The agent handles the rest.

---

## Key differences from the Chrome extension

| Extension | Python agent |
|---|---|
| Opens real Chrome tabs | Headless Playwright (same engine) |
| `chrome.tabs.create()` delays | `random_delay(4s–8s)` — identical timing |
| XHR/fetch monkey-patching | `page.on('response')` — cleaner, more reliable |
| Manual login re-prompt to user | Credential-based re-login automatically |
| Downloads HTML report | Returns HTML + JSON in API response |

All selector logic, URL patterns, step order, and timing are preserved exactly.
