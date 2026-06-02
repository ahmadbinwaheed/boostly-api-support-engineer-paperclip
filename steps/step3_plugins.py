"""
steps/step3_plugins.py
Port of step3-plugin-checker.js
"""

import re
import logging
from playwright.async_api import Page

log = logging.getLogger("Boostly-API-Support-Engineer.step3")


async def check_plugins(page: Page) -> dict:
    """Reads /wp-admin/plugins.php and detects Boostly plugins + site version."""
    results = []
    boostly_plugins = []
    site_version = "Light"
    boostly_connect_version = None

    # Check for login redirect (session expired)
    current_url = page.url
    if "/wp-admin/" not in current_url:
        return {
            "site_version": "Unknown",
            "boostly_connect_version": None,
            "boostly_plugins": [],
            "results": [{
                "title": "Plugin Check",
                "detail": f"WP session expired — redirected away from wp-admin (current: {current_url})",
                "status": "fail",
            }],
        }

    # Primary: detect by data-slug (most reliable)
    bc_row = await page.query_selector('tr[data-slug="boostly-connect"]')
    pms_row = await page.query_selector('tr[data-slug="boostly-pms"]')

    if bc_row:
        is_active = "active" in (await bc_row.get_attribute("class") or "")
        if is_active:
            version_div = await bc_row.query_selector(".plugin-version-author-uri")
            version_text = await version_div.inner_text() if version_div else ""
            m = re.search(r"Version\s+([\d.]+)", version_text, re.IGNORECASE)
            boostly_connect_version = m.group(1) if m else None
            site_version = "3.5"
            boostly_plugins.append({"name": "Boostly Connect", "version": boostly_connect_version, "active": True})
            results.append({
                "title": "Boostly Connect",
                "detail": f"Active{' — v' + boostly_connect_version if boostly_connect_version else ''} ✓",
                "status": "pass",
            })
        else:
            results.append({
                "title": "Boostly Connect",
                "detail": "Found but NOT active — may need activation",
                "status": "warn",
            })

    if pms_row:
        is_active = "active" in (await pms_row.get_attribute("class") or "")
        if is_active:
            version_div = await pms_row.query_selector(".plugin-version-author-uri")
            version_text = await version_div.inner_text() if version_div else ""
            m = re.search(r"Version\s+([\d.]+)", version_text, re.IGNORECASE)
            ver = m.group(1) if m else None
            if site_version != "3.5":
                site_version = "3.0"
            boostly_plugins.append({"name": "Boostly PMS", "version": ver, "active": True})
            results.append({
                "title": "Boostly PMS",
                "detail": f"Active{' — v' + ver if ver else ''} ✓",
                "status": "pass",
            })

    # Fallback: scan all active rows for "By Boostly" author link
    if not boostly_plugins:
        active_rows = await page.query_selector_all("#the-list tr.active")
        for row in active_rows:
            name_el = await row.query_selector(".plugin-title strong")
            author_link = await row.query_selector(".plugin-version-author-uri a[href*='boostly']")
            if not name_el or not author_link:
                continue
            name = (await name_el.inner_text()).strip()
            version_div = await row.query_selector(".plugin-version-author-uri")
            version_text = await version_div.inner_text() if version_div else ""
            m = re.search(r"Version\s+([\d.]+)", version_text, re.IGNORECASE)
            ver = m.group(1) if m else None
            boostly_plugins.append({"name": name, "version": ver, "active": True})
            if site_version == "Light":
                site_version = "2.0"
            results.append({
                "title": name,
                "detail": f"Active (By Boostly){' — v' + ver if ver else ''} ✓",
                "status": "pass",
            })

    if not boostly_plugins:
        results.append({
            "title": "Plugin Check",
            "detail": "No active Boostly plugins found — classified as Boostly Light site",
            "status": "warn",
        })

    results.append({
        "title": "Site Version",
        "detail": f"Classified as Boostly v{site_version} site",
        "status": "info",
    })

    return {
        "site_version":             site_version,
        "boostly_connect_version":  boostly_connect_version,
        "boostly_plugins":          boostly_plugins,
        "results":                  results,
    }
