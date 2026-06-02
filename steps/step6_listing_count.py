"""
steps/step6_listing_count.py
Port of step6-listing-counter.js
"""

import re
import logging
from playwright.async_api import Page

log = logging.getLogger("Boostly-API-Support-Engineer.step6")


async def count_published_listings(page: Page) -> dict:
    """Read published listing count from /wp-admin/edit.php?post_type=listing"""
    current_url = page.url

    # Session check
    if "/wp-admin/" not in current_url:
        return {
            "published_count": None,
            "results": [{
                "title": "Published Listing Count",
                "detail": f"WP session expired — redirected away from wp-admin (path: {current_url})",
                "status": "fail",
            }],
        }

    published_count = None

    # Primary: .subsubsub .publish .count
    publish_li = await page.query_selector(".subsubsub .publish")
    if publish_li:
        count_el = await publish_li.query_selector(".count")
        if count_el:
            text = await count_el.inner_text()
            m = re.search(r"\d+", text)
            if m:
                published_count = int(m.group())
        if published_count is None:
            text = await publish_li.inner_text()
            m = re.search(r"Published[^(]*\((\d+)\)", text, re.IGNORECASE)
            if m:
                published_count = int(m.group(1))

    # Fallback: any subsubsub link with "Published" text
    if published_count is None:
        links = await page.query_selector_all(".subsubsub a")
        for a in links:
            text = await a.inner_text()
            if re.search(r"published", text, re.IGNORECASE):
                m = re.search(r"\((\d+)\)", text)
                if m:
                    published_count = int(m.group(1))
                    break

    # Fallback: count visible post rows
    if published_count is None:
        rows = await page.query_selector_all('#the-list tr[id^="post-"]')
        if rows:
            published_count = len(rows)

    return {
        "published_count": published_count,
        "results": [{
            "title": "Published Listing Count",
            "detail": f"{published_count} published listings ✓" if published_count is not None
                      else "Could not read published count from subsubsub — check WP admin page structure",
            "status": "pass" if published_count is not None else "warn",
        }],
    }
