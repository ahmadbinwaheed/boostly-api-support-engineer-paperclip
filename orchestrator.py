"""
orchestrator.py
---------------
Direct port of background.js startQA() and all sub-flows.
Every step, every tab open/close, every delay mirrors the extension exactly.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import WP_ADMIN, TIMEOUTS, SKIP_PATTERN
from utils.helpers import random_delay, generate_test_date_sets
from utils.report import build_html_report, build_json_report

from steps.step1_auth             import check_auth, check_admin_session
from steps.step3_plugins          import check_plugins
from steps.step4_5_links_images   import collect_links, check_links, validate_images_on_page, check_subpage_images
from steps.step6_listing_count    import count_published_listings
from steps.step7_search           import check_search_form, collect_search_results
from steps.step8_listing_validator import validate_listing
from steps.step9_pms_sync         import detect_active_pms, run_pms_sync

log = logging.getLogger("Boostly-API-Support-Engineer.orchestrator")


# ── State (mirrors `qa` object in background.js) ──────────────────────────────

class QAState:
    def __init__(self, site_url: str):
        parsed = urlparse(site_url)
        self.running          = True
        self.base_url         = site_url
        self.domain           = parsed.netloc
        self.start_time       = time.time()
        self.site_info: dict  = {
            "url":    site_url,
            "domain": parsed.netloc,
            "start_time": datetime.now(timezone.utc).isoformat(),
        }
        self.step_results: list[dict]  = []
        self.api_responses: list[dict] = []
        self.published_count: int | None = None

    def record(self, step_id: str, step_name: str, details: list[dict], raw: dict = None):
        passed = sum(1 for d in details if d.get("status") == "pass")
        failed = sum(1 for d in details if d.get("status") == "fail")
        warned = sum(1 for d in details if d.get("status") == "warn")
        ts = datetime.now().strftime("%H:%M:%S")
        timestamped = [{**d, "timestamp": ts} for d in details]
        self.step_results.append({
            "step_id": step_id,
            "name":    step_name,
            "passed":  passed,
            "failed":  failed,
            "warned":  warned,
            "details": timestamped,
            "raw":     raw or {},
        })
        for d in timestamped:
            log.info(f"[{d.get('status','?').upper()}] {d.get('title','')} — {d.get('detail','')}")

    def finish(self):
        duration = int(time.time() - self.start_time)
        self.site_info["duration"] = f"{duration}s"
        self.running = False


# ── Main entry point ───────────────────────────────────────────────────────────

async def run_full_qa(
    site_url: str,
    login_url: str,
    wp_username: str,
    wp_password: str,
) -> dict:
    """
    Full QA run. Mirrors startQA() in background.js exactly — same step order,
    same early-exit conditions, same human-like delays between tab openings.
    """
    qa = QAState(site_url)
    login_url_path = login_url if login_url.startswith("/") else f"/{login_url}"

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        # Single persistent context — shares cookies across all pages (mirrors the
        # extension running in one browser profile with one WP session cookie).
        context: BrowserContext = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        context.set_default_timeout(TIMEOUTS["tab_load"] * 1000)

        try:
            # ── Step 1: WP Login ─────────────────────────────────────────────
            log.info("=== Step 1: WP Auth ===")
            page = await context.new_page()
            step1 = await check_auth(page, site_url, login_url_path, wp_username, wp_password)
            qa.record("step1", "WP Login Check", step1["results"], step1)

            if not step1.get("logged_in"):
                log.error("Step 1 failed — aborting run")
                qa.finish()
                return _build_report(qa)

            # ── Step 3: Plugin detection ─────────────────────────────────────
            log.info("=== Step 3: Plugin Detection ===")
            await random_delay()
            await _safe_goto(page, f"{site_url}{WP_ADMIN['plugins']}")
            if await _session_ok(page, context, site_url, login_url_path, wp_username, wp_password):
                step3 = await check_plugins(page)
                qa.record("step3", "Plugin Detection", step3["results"], step3)
                qa.site_info["site_version"]            = step3.get("site_version")
                qa.site_info["boostly_connect_version"] = step3.get("boostly_connect_version")

            # ── Step 4: Link collection ──────────────────────────────────────
            log.info("=== Step 4: Link Collection ===")
            await random_delay()
            await _safe_goto(page, f"{site_url}/")
            step4 = await collect_links(page, site_url)
            qa.record("step4", "Link Collection", step4["results"], step4)
            links_to_check = step4.get("links", [])

            # ── Step 5a: Image validation on homepage ───────────────────────
            log.info("=== Step 5a: Image Validation (Homepage) ===")
            step5_home = await validate_images_on_page(page)
            qa.record("step5_home", "Image Validation (Homepage)", step5_home["results"])

            # ── Step 4b: Link 404 check (throttled, background) ─────────────
            log.info(f"=== Step 4b: Link 404 Check ({len(links_to_check)} links) ===")
            link_results = await check_links(links_to_check)
            qa.record("step4_link_check", "Link 404 Check", link_results)

            # ── Step 5b: Sub-page image check ────────────────────────────────
            internal_pages = [
                l for l in links_to_check
                if not SKIP_PATTERN.search(l)
            ][:15]
            log.info(f"=== Step 5b: Sub-page Image Check ({len(internal_pages)} pages) ===")
            subpage_issues = await check_subpage_images(internal_pages, site_url)
            qa.record("step5_subpages", "Image Validation (Sub-pages)", subpage_issues)

            # ── Step 6: Published listing count ──────────────────────────────
            log.info("=== Step 6: Published Listing Count ===")
            await random_delay()
            await _safe_goto(page, f"{site_url}{WP_ADMIN['published_listings']}")
            if await _session_ok(page, context, site_url, login_url_path, wp_username, wp_password):
                step6 = await count_published_listings(page)
                qa.record("step6", "Published Listing Count", step6["results"], step6)
                qa.published_count = step6.get("published_count")

            # ── Step 7: Search (3 iterations) ────────────────────────────────
            date_sets = generate_test_date_sets()
            for i, dates in enumerate(date_sets, start=1):
                if not qa.running:
                    break
                await _run_search_iteration(qa, context, page, site_url, dates, i,
                                            login_url_path, wp_username, wp_password)

            # ── Step 9: PMS settings + sync ───────────────────────────────────
            log.info("=== Step 9: PMS Settings ===")
            await random_delay()
            await _safe_goto(page, f"{site_url}{WP_ADMIN['pms_settings']}")
            if await _session_ok(page, context, site_url, login_url_path, wp_username, wp_password):
                step9_detect = await detect_active_pms(page)
                qa.record("step9_pms_list", "Active PMS Detection", step9_detect["results"], step9_detect)
                active_pms = step9_detect.get("active_pms", [])
                qa.site_info["active_pms"] = active_pms

                for pms_name in active_pms:
                    if not qa.running:
                        break
                    await _run_pms_sync(qa, page, site_url, pms_name,
                                        login_url_path, wp_username, wp_password)

        except Exception as e:
            log.error(f"Orchestration error: {e}", exc_info=True)
            qa.record("orchestrator_error", "Orchestration", [{
                "title": "Error", "detail": str(e), "status": "fail"
            }])

        finally:
            await context.close()
            await browser.close()

    qa.finish()
    return _build_report(qa)


# ── Search iteration (mirrors runSearchIteration) ─────────────────────────────

async def _run_search_iteration(
    qa: QAState,
    context: BrowserContext,
    page: Page,
    site_url: str,
    dates: dict,
    iter_num: int,
    login_url_path: str,
    wp_username: str,
    wp_password: str,
):
    label = dates["label"]
    log.info(f"=== Step 7 Iteration {iter_num}: {label} ===")

    # Load homepage and check the search form
    await random_delay()
    await _safe_goto(page, f"{site_url}/")
    step7a = await check_search_form(page)
    qa.record(f"step7_iter{iter_num}_search", f"Search Form (Iter {iter_num}): {label}", step7a["results"], step7a)

    if not step7a.get("search_bar_found"):
        return

    # Navigate directly to search-results with query params
    # (same as the extension — Boostly datepickers can't be set via input.value)
    search_url = (
        f"{site_url}/search-results"
        f"?arrive={dates['arrive']}&depart={dates['depart']}&guest={dates['guests']}"
    )
    log.info(f"  Navigating to: {search_url}")
    await random_delay()
    await _safe_goto(page, search_url, timeout=60)

    # Collect results — 60s timeout because pages load listings async
    step7b = await collect_search_results(page, dates, qa.published_count)
    qa.record(f"step7_iter{iter_num}_results", f"Search Results (Iter {iter_num}): {label}",
              step7b["results"], step7b)

    if step7b.get("count_results"):
        qa.record(f"step7_iter{iter_num}_count", f"Listing Count (Iter {iter_num})",
                  step7b["count_results"])

    # Step 8: Validate first 3 listing pages
    listing_urls = step7b.get("listing_urls", [])
    for j, listing in enumerate(listing_urls[:3]):
        if not qa.running:
            break
        title_short = listing.get("title", f"Listing {j+1}")[:40]
        log.info(f"  Step 8 Listing {j+1}: {listing['url']}")
        await random_delay()
        await _safe_goto(page, listing["url"])
        step8 = await validate_listing(page)
        qa.record(
            f"step8_iter{iter_num}_listing{j+1}",
            f"Listing {j+1} (Iter {iter_num}): {title_short}",
            step8["results"],
            step8,
        )


# ── PMS sync run (mirrors runPmsSync) ─────────────────────────────────────────

async def _run_pms_sync(
    qa: QAState,
    page: Page,
    site_url: str,
    pms_name: str,
    login_url_path: str,
    wp_username: str,
    wp_password: str,
):
    log.info(f"=== Step 9 PMS Sync: {pms_name} ===")
    tab_url = f"{site_url}{WP_ADMIN['pms_settings_tab']}{pms_name}"
    await random_delay()
    await _safe_goto(page, tab_url)

    if not await _session_ok(page, context=None, site_url=site_url,
                              login_url_path=login_url_path,
                              username=login_url_path, password="",
                              page_ref=page):
        return

    step_results, api_responses = await run_pms_sync(page, pms_name)
    qa.record(f"step9_sync_{pms_name}", f"PMS Sync: {pms_name}", step_results)
    qa.api_responses.extend(api_responses)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _safe_goto(page: Page, url: str, timeout: int = None):
    t = (timeout or TIMEOUTS["tab_load"]) * 1000
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=t)
    except Exception as e:
        log.warning(f"goto {url} failed: {e}")


async def _session_ok(
    page: Page,
    context: BrowserContext | None,
    site_url: str,
    login_url_path: str,
    username: str,
    password: str,
    page_ref: Page = None,
) -> bool:
    """
    Check if we're still in wp-admin. If not, re-authenticate.
    Mirrors openAdminTab() + waitForReLogin() from background.js.
    """
    current_url = (page_ref or page).url
    if "/wp-admin/" in current_url:
        return True

    log.warning("WP session appears expired — re-authenticating...")
    result = await check_auth(page_ref or page, site_url, login_url_path, username, password)
    return result.get("logged_in", False)


def _build_report(qa: QAState) -> dict:
    html = build_html_report(qa.site_info, qa.step_results, qa.api_responses)
    json_report = build_json_report(qa.site_info, qa.step_results, qa.api_responses)
    return {
        **json_report,
        "html_report": html,
    }
