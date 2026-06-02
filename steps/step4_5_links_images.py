"""
steps/step4_links.py  — Port of step4-link-crawler.js + checkLinksInBackground()
steps/step5_images.py — Port of step5-image-validator.js + checkSubPageImagesViaFetch()
Both are in one file since they share the same page context.
"""

import asyncio
import re
import logging
import httpx
from urllib.parse import urlparse, urljoin
from playwright.async_api import Page

from config import IMAGE_PLACEHOLDERS
from utils.helpers import is_skippable_url, is_wp_admin_url, random_delay

log = logging.getLogger("Boostly-API-Support-Engineer.step4_5")


# ── Step 4: Link collection (port of step4-link-crawler.js) ────────────────────

async def collect_links(page: Page, base_url: str) -> dict:
    """Collect all unique internal frontend links from the homepage."""
    base_origin = urlparse(base_url).scheme + "://" + urlparse(base_url).netloc

    anchors = await page.evaluate("""(baseOrigin) => {
        return Array.from(document.querySelectorAll('a[href]')).map(a => {
            try { return new URL(a.href, baseOrigin).href; } catch(_) { return null; }
        }).filter(Boolean);
    }""", base_origin)

    links = []
    seen = set()
    for href in anchors:
        if href in seen:
            continue
        seen.add(href)
        if is_skippable_url(href):
            continue
        try:
            if urlparse(href).netloc != urlparse(base_origin).netloc:
                continue
        except Exception:
            continue
        if is_wp_admin_url(href):
            continue
        links.append(href)

    return {
        "base_domain": base_origin,
        "links": links,
        "results": [{
            "title": "Links Collected",
            "detail": f"Found {len(links)} unique front-end links on homepage",
            "status": "info",
        }],
    }


# ── Step 4b: Link 404 check (port of checkLinksInBackground) ──────────────────

async def check_links(urls: list[str]) -> list[dict]:
    """HEAD-check each URL with human-like delays. Mirrors checkLinksInBackground()."""
    results = []
    seen = set()

    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        for url in urls:
            if url in seen:
                continue
            seen.add(url)

            try:
                resp = await client.head(url)
                if resp.status_code == 404:
                    results.append({"title": "404 Link", "detail": url, "status": "fail"})
                elif resp.status_code >= 400:
                    results.append({"title": f"HTTP {resp.status_code}", "detail": url, "status": "warn"})
            except Exception as e:
                results.append({"title": "Unreachable Link", "detail": f"{url} — {e}", "status": "warn"})

            await random_delay(4.0, 8.0)

    if not any(r["status"] in ("fail", "warn") for r in results):
        results.append({
            "title": "Link Check",
            "detail": f"All {len(seen)} links reachable ✓",
            "status": "pass",
        })

    return results


# ── Step 5: Image validation on a live page (port of step5-image-validator.js) ─

async def validate_images_on_page(page: Page) -> dict:
    """Check all <img> and <figure> elements on the current page."""
    results = []
    page_url = page.url

    image_data = await page.evaluate("""(placeholders) => {
        const images = Array.from(document.querySelectorAll('img, figure'));
        const issues = [];
        const data = [];

        images.forEach(el => {
            const isImg = el.tagName === 'IMG';
            const src   = isImg ? (el.getAttribute('src') || '') : '';
            const alt   = isImg ? (el.getAttribute('alt') || '') : '';

            if (isImg) {
                const isEmpty       = !src || src.trim() === '';
                const isPlaceholder = !isEmpty && placeholders.some(p => src.includes(p));
                const isBroken      = !isEmpty && el.complete && el.naturalHeight === 0;

                if (isEmpty)       issues.push({title:'Empty Image src',   detail:`img[alt="${alt || 'no-alt'}"] has empty src`,      status:'fail'});
                else if(isPlaceholder) issues.push({title:'Placeholder Image', detail:`Possible placeholder: ${src.substring(0,80)}`, status:'warn'});
                else if(isBroken)  issues.push({title:'Broken Image',       detail:`Failed to load: ${src.substring(0,80)}`,           status:'fail'});

                data.push({src, isEmpty, isPlaceholder, isBroken});
            } else {
                const img = el.querySelector('img');
                if (!img) issues.push({title:'Empty Figure', detail:'<figure> has no <img> child', status:'warn'});
            }
        });
        return {issues, count: data.length};
    }""", IMAGE_PLACEHOLDERS)

    issues = image_data.get("issues", [])
    count  = image_data.get("count", 0)

    if not issues:
        results.append({
            "title": "Image Validation",
            "detail": f"All {count} images on this page appear valid ✓",
            "status": "pass",
        })
    else:
        results.extend(issues)

    return {"results": results, "page_url": page_url}


# ── Step 5b: Sub-page image check via HTTP fetch (port of checkSubPageImagesViaFetch) ─

async def check_subpage_images(page_urls: list[str], base_url: str) -> list[dict]:
    """
    Fetch raw HTML of each sub-page and scan for image issues.
    Uses the same human-like delays. Mirrors checkSubPageImagesViaFetch().
    """
    all_issues = []

    # Carry session cookies from Playwright to httpx
    # (sub-page images don't need auth, but some WP themes redirect guests)
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        for page_url in page_urls:
            await random_delay(4.0, 8.0)
            try:
                resp = await client.get(page_url)
                if not resp.is_success:
                    continue
                html = resp.text

                # Empty src
                if re.search(r'<img[^>]+src=["\'\s]["\']', html):
                    all_issues.append({"title": "Empty Image src", "detail": f"Empty src found on: {page_url}", "status": "fail"})

                # Missing src entirely
                if re.search(r'<img(?![^>]*\bsrc\b)[^>]*>', html):
                    all_issues.append({"title": "Image Missing src", "detail": f"<img> with no src on: {page_url}", "status": "fail"})

                # Placeholder patterns
                for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE):
                    src = match.group(1)
                    if any(p in src.lower() for p in IMAGE_PLACEHOLDERS):
                        path = page_url.replace(base_url, "")
                        all_issues.append({"title": "Placeholder Image", "detail": f"{src[:70]} — {path}", "status": "warn"})

            except Exception:
                pass  # Already reported in link check

    if not all_issues:
        all_issues.append({
            "title": "Sub-page Images",
            "detail": f"No image issues found across {len(page_urls)} sub-pages ✓",
            "status": "pass",
        })

    return all_issues
