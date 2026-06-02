"""
steps/step9_pms_sync.py
Port of step9-pms-tester.js + step9-sync-tester.js + the XHR/fetch interception logic.
Playwright's route/response interception replaces the monkey-patching approach.
"""

import asyncio
import re
import json
import logging
from datetime import datetime
from playwright.async_api import Page, Response

from config import TIMEOUTS

log = logging.getLogger("Boostly-API-Support-Engineer.step9")

# Patterns from background.js _isBoostlySyncRelated()
_SYNC_PATTERNS = [
    re.compile(r"^boostly_.+_sync_(listings?|ical)$", re.IGNORECASE),
    re.compile(r"boostly.*sync", re.IGNORECASE),
]


def _is_boostly_sync(action: str, url: str) -> bool:
    for p in _SYNC_PATTERNS:
        if action and p.search(action):
            return True
    if url and "/wp-json/" in url.lower() and "boostly" in url.lower():
        return True
    return False


def _extract_action(body: str | None, url: str) -> str | None:
    if body:
        m = re.search(r"(?:^|[?&])action=([^&]+)", body)
        if m:
            return m.group(1)
        try:
            j = json.loads(body)
            if isinstance(j, dict) and "action" in j:
                return j["action"]
        except Exception:
            pass
    if url:
        m = re.search(r"[?&]action=([^&]+)", url)
        if m:
            return m.group(1)
    return None


# ── Step 9a: Detect active PMS (port of step9-pms-tester.js) ──────────────────

async def detect_active_pms(page: Page) -> dict:
    """Read active PMS list from the Boostly Connect settings page via Select2."""
    current_url = page.url
    if "/wp-admin/" not in current_url:
        return {
            "active_pms": [],
            "results": [{
                "title": "PMS Settings",
                "detail": f"WP session expired — redirected away from wp-admin (path: {current_url})",
                "status": "fail",
            }],
        }

    # Wait up to 6s for Select2 container (async render) — mirrors waitForSelect2()
    try:
        await page.wait_for_selector(
            "#select2-boostly_active_pms-container",
            timeout=6000,
            state="attached",
        )
    except Exception:
        return {
            "active_pms": [],
            "results": [{
                "title": "Active PMS",
                "detail": "select2-boostly_active_pms-container not found after 6s — check if Boostly Connect settings page loaded correctly",
                "status": "fail",
            }],
        }

    items = await page.query_selector_all(
        "#select2-boostly_active_pms-container .select2-selection__choice"
    )

    active_pms = []
    for li in items:
        display = await li.query_selector("[class*='choice__display']")
        if display:
            title = (await display.inner_text()).strip()
        else:
            title = await li.get_attribute("title") or ""
        if title:
            active_pms.append(title.lower().replace(" ", "-"))

    return {
        "active_pms": active_pms,
        "results": [{
            "title": "Active PMS List",
            "detail": f"Found: {', '.join(active_pms)} ✓" if active_pms else "No active PMS configured in Boostly Connect",
            "status": "pass" if active_pms else "warn",
        }],
    }


# ── Step 9b: PMS sync tester (port of step9-sync-tester.js + runPmsSync) ───────

async def run_pms_sync(page: Page, pms_name: str) -> tuple[list[dict], list[dict]]:
    """
    Navigate to the PMS sync tab, detect sync buttons, intercept AJAX responses,
    click sync buttons and wait for responses. Returns (step_results, api_responses).
    """
    results = []
    api_responses = []

    if "/wp-admin/" not in page.url:
        return [{"title": "PMS Sync", "detail": "Redirected to login", "status": "fail"}], []

    # ── Button detection (port of step9-sync-tester.js) ──────────────────────
    has_sync_button = await page.evaluate("""(pmsName) => {
        const btn = document.getElementById(`${pmsName}_listings_sync`)
            || Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"]'))
                .find(el => /listings?\\s*sync/i.test(el.textContent || el.value || ''));
        return !!btn;
    }""", pms_name)

    has_ical_button = await page.evaluate("""(pmsName) => {
        const btn = document.getElementById(`${pmsName}_ical_sync`)
            || Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"]'))
                .find(el => /ical\\s*sync/i.test(el.textContent || el.value || ''));
        return !!btn;
    }""", pms_name)

    results.append({
        "title": f"{pms_name} Listings Sync",
        "detail": "Listings Sync button found — click will be triggered" if has_sync_button else "Listings Sync button not found",
        "status": "info" if has_sync_button else "fail",
    })
    results.append({
        "title": f"{pms_name} iCal Sync",
        "detail": "iCal Sync button found ✓" if has_ical_button else "iCal Sync button not found",
        "status": "info" if has_ical_button else "fail",
    })

    # Auto-sync cron status
    for sync_type, input_name in [("Listing", f"boostly_{pms_name}_listing_auto_sync_enable"),
                                   ("iCal",    f"boostly_{pms_name}_ical_auto_sync_enable")]:
        cron = await page.evaluate("""(name) => {
            const el = document.querySelector(`input[name="${name}"]`);
            if (!el) return null;
            const row = el.closest('tr');
            const cells = row ? Array.from(row.querySelectorAll('td')) : [];
            return {
                enabled:   el.checked,
                last_sync: cells[3] ? cells[3].textContent.trim() : 'unknown',
                status:    cells[4] ? cells[4].textContent.trim() : 'unknown',
            };
        }""".replace("${name}", input_name), input_name)

        if cron:
            results.append({
                "title": f"{pms_name} {sync_type} Auto-Sync",
                "detail": f"Enabled: {'Yes' if cron['enabled'] else 'No'} | Last run: {cron['last_sync']} | Status: {cron['status']}",
                "status": "pass" if cron["enabled"] else "warn",
            })
        else:
            results.append({
                "title": f"{pms_name} {sync_type} Auto-Sync",
                "detail": f"{sync_type} auto-sync checkbox not found",
                "status": "warn",
            })

    # ── Network interception — replaces XHR/fetch monkey-patching ────────────
    captured: list[dict] = []

    async def _on_response(response: Response):
        url = response.url
        try:
            action = _extract_action(None, url)
            if _is_boostly_sync(action or "", url):
                try:
                    body = await response.text()
                except Exception:
                    body = ""
                try:
                    parsed = json.loads(body)
                except Exception:
                    parsed = body
                captured.append({
                    "pms_name":  pms_name,
                    "action":    action or url,
                    "response":  parsed,
                    "status":    response.status,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
        except Exception:
            pass

    page.on("response", _on_response)

    # ── Click Listings Sync button ────────────────────────────────────────────
    if has_sync_button:
        before = len(captured)
        await page.evaluate("""(pmsName) => {
            const btn = document.getElementById(`${pmsName}_listings_sync`)
                || Array.from(document.querySelectorAll('button, input[type="submit"]'))
                    .find(el => /listings?\\s*sync/i.test(el.textContent || el.value || ''));
            if (btn) btn.click();
        }""", pms_name)
        await _wait_for_capture(captured, before, timeout_s=TIMEOUTS["pms_sync"])

    # ── Click iCal Sync button ────────────────────────────────────────────────
    if has_ical_button:
        before = len(captured)
        await page.evaluate("""(pmsName) => {
            const btn = document.getElementById(`${pmsName}_ical_sync`)
                || Array.from(document.querySelectorAll('button, input[type="submit"]'))
                    .find(el => /ical\\s*sync/i.test(el.textContent || el.value || ''));
            if (btn) btn.click();
        }""", pms_name)
        await _wait_for_capture(captured, before, timeout_s=TIMEOUTS["pms_sync"])

    page.remove_listener("response", _on_response)
    api_responses.extend(captured)

    results.append({
        "title": "Sync API Capture",
        "detail": f"{len(captured)} response(s) captured: {', '.join(r['action'] for r in captured)} ✓"
                  if captured
                  else "No XHR/fetch intercepted — sync button may use a different request mechanism",
        "status": "pass" if captured else "warn",
    })

    return results, api_responses


async def _wait_for_capture(captured: list, count_before: int, timeout_s: int = 480):
    """Poll until a new entry appears in captured, or timeout. Mirrors waitForAjaxResponse()."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        if len(captured) > count_before:
            return True
        await asyncio.sleep(1)
    return False
