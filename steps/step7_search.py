"""
steps/step7_search.py
Port of step7-search-tester.js (pre-nav form check) + step7-results-collector.js
"""

import asyncio
import logging
from urllib.parse import urlparse, parse_qs
from playwright.async_api import Page

from config import SEARCH_FORM, SEARCH_RESULTS, QUERY_PARAMS
from utils.helpers import has_required_query_params

log = logging.getLogger("Boostly-API-Support-Engineer.step7")


# ── Step 7a: Search form presence check (port of step7-search-tester.js) ───────

async def check_search_form(page: Page) -> dict:
    """Check that the homepage search form has all required inputs."""
    results = []
    cfg = SEARCH_FORM

    search_bar = await page.query_selector(cfg["bar"])
    if not search_bar:
        results.append({"title": "Search Bar", "detail": "Search bar not found on homepage", "status": "fail"})
        return {"search_bar_found": False, "results": results}
    results.append({"title": "Search Bar", "detail": "Search bar found on homepage ✓", "status": "pass"})

    arrive_input  = await page.query_selector(cfg["arrive_input"])
    depart_input  = await page.query_selector(cfg["depart_input"])
    guests_input  = await page.query_selector(cfg["guests_input"])
    submit_btn    = await page.query_selector(cfg["submit_button"])

    results.append({
        "title": "Check-in Input",
        "detail": f"Input present ✓" if arrive_input else "arrive input not found",
        "status": "pass" if arrive_input else "fail",
    })
    results.append({
        "title": "Check-out Input",
        "detail": "Input present ✓" if depart_input else "depart input not found",
        "status": "pass" if depart_input else "fail",
    })
    results.append({
        "title": "Guests Input",
        "detail": "Input present ✓" if guests_input else "guests input not found",
        "status": "pass" if guests_input else "warn",
    })
    results.append({
        "title": "Submit Button",
        "detail": "Submit/Search button found ✓" if submit_btn else "Submit button not found",
        "status": "pass" if submit_btn else "fail",
    })

    return {"search_bar_found": True, "results": results}


# ── Step 7b: Search results collector (port of step7-results-collector.js) ─────

NO_RESULTS_SELECTORS = ", ".join([
    ".no-results", ".no-listings", ".no-properties", ".nothing-found",
    "[class*='no-result']", "[class*='no-listing']", "[class*='not-found']",
    ".search-no-results", ".listing-not-found", ".empty-results", ".no-available",
])

NO_RESULTS_PATTERNS = [
    r"no\s+(listings?|properties|results?|units?|cabins?|accommodation|homes?|rentals?|stays?)\s*(found|available|to\s+show|match)",
    r"sorry[^.]{0,60}no\s+(listings?|properties|available)",
    r"unfortunately[^.]{0,60}no\s+(listings?|properties|available)",
    r"couldn.t\s+find\s+any",
    r"0\s+(properties|listings?|results?)\s+(found|available|match)",
]

SEARCH_CONTAINER_SELECTORS = ", ".join([
    ".search-results-wrap", ".search-results", "#search-results",
    ".search-container", "#search-container", ".listing-results",
    ".listings-container", ".search-wrap", ".results-wrap",
    ".properties-wrap", ".units-wrap", ".availability-results",
    "[class*='search-result']", "[class*='listing-result']",
    "[class*='no-listing']", "[class*='availability']",
])


async def collect_search_results(page: Page, dates: dict, published_count: int | None) -> dict:
    """
    Wait for listing cards or a 'no results' indicator, then validate each card.
    Mirrors step7-results-collector.js including the 30s MutationObserver wait.
    """
    results = []
    current_url = page.url
    cfg = SEARCH_RESULTS

    if "/search-results" not in current_url.lower():
        results.append({"title": "Search Results Page", "detail": f"Not on /search-results — URL: {current_url}", "status": "fail"})
        return {"listing_count": 0, "listing_urls": [], "results": results}

    # Verify query params
    params = parse_qs(urlparse(current_url).query)

    def get_param(keys):
        for k in keys:
            if k in params:
                return params[k][0]
        return None

    arrive_val = get_param(QUERY_PARAMS["arrive"])
    depart_val = get_param(QUERY_PARAMS["depart"])
    guests_val = get_param(QUERY_PARAMS["guests"])

    all_params = all([arrive_val, depart_val, guests_val])
    results.append({
        "title": "Search Query Params",
        "detail": f"arrive={arrive_val}, depart={depart_val}, guests={guests_val} ✓" if all_params
                  else f"Missing params in URL",
        "status": "pass" if all_params else "warn",
    })

    # Wait up to 30s for listing cards or no-results node — mirrors waitForCardsOrNoResults
    listing_count, no_results = await _wait_for_cards_or_no_results(page, cfg["listing_cards"], timeout_s=30)

    if no_results and listing_count == 0:
        results.append({"title": "Listing Count", "detail": "No listings available for these dates ✓", "status": "warn"})
        return {"listing_count": 0, "listing_urls": [], "results": results}

    results.append({
        "title": "Listing Count",
        "detail": f"{listing_count} listings returned ✓" if listing_count > 0
                  else "No listing cards found after 30s — dates may have no availability, or selector needs updating",
        "status": "pass" if listing_count > 0 else "warn",
    })

    if listing_count == 0:
        return {"listing_count": 0, "listing_urls": [], "results": results}

    # Validate cards
    card_data = await page.evaluate("""(cfg) => {
        const cards = Array.from(document.querySelectorAll(cfg.listingCards));
        let withImages = 0, withTitles = 0, withPrices = 0, withParams = 0;
        const listingUrls = [];

        function hasParams(url) {
            try {
                const p = new URL(url).searchParams;
                const arrive = ['arrive','checkin','check_in','arrival'].some(k => p.has(k));
                const depart = ['depart','checkout','check_out','departure'].some(k => p.has(k));
                const guests = ['guest','guests','adults','adult_guests'].some(k => p.has(k));
                return arrive && depart && guests;
            } catch(_) { return false; }
        }

        cards.forEach((card, i) => {
            const titleLink = card.querySelector(cfg.listingTitle);
            const img       = card.querySelector(cfg.listingImage);
            const price     = card.querySelector(cfg.listingPrice);
            const link      = card.querySelector(cfg.listingLink) || titleLink;

            if (img && img.src) withImages++;
            if (titleLink) withTitles++;
            if (price) withPrices++;

            if (link && link.href) {
                if (hasParams(link.href)) withParams++;
                if (i < 3) {
                    listingUrls.push({
                        url: link.href,
                        title: titleLink ? titleLink.textContent.trim() : `Listing ${i+1}`,
                        price: price ? price.textContent.trim() : null,
                        has_params: hasParams(link.href),
                    });
                }
            }
        });

        const mapLinks = Array.from(document.querySelectorAll(cfg.mapListingLink));
        const mapWithParams = mapLinks.filter(l => hasParams(l.href)).length;

        return { withImages, withTitles, withPrices, withParams, listingUrls, total: cards.length, mapTotal: mapLinks.length, mapWithParams };
    }""", {
        "listingCards": cfg["listing_cards"],
        "listingTitle": cfg["listing_title"],
        "listingImage": cfg["listing_image"],
        "listingPrice": cfg["listing_price"],
        "listingLink":  cfg["listing_link"],
        "mapListingLink": cfg["map_listing_link"],
    })

    total = card_data["total"]
    results.append({"title": "Listing Images",    "detail": f"{card_data['withImages']}/{total} cards have images",  "status": "pass" if card_data["withImages"] == total else "warn"})
    results.append({"title": "Listing Titles",    "detail": f"{card_data['withTitles']}/{total} cards have titles",  "status": "pass" if card_data["withTitles"] == total else "fail"})
    results.append({"title": "Listing Prices",    "detail": f"{card_data['withPrices']}/{total} cards have prices",  "status": "pass" if card_data["withPrices"] == total else "warn"})
    results.append({"title": "Card Query Params", "detail": f"{card_data['withParams']}/{total} listing links carry arrive/depart/guest params", "status": "pass" if card_data["withParams"] == total else "fail"})

    if card_data["mapTotal"] > 0:
        results.append({"title": "Map Listing Links", "detail": f"{card_data['mapWithParams']}/{card_data['mapTotal']} map links carry query params", "status": "pass" if card_data["mapWithParams"] == card_data["mapTotal"] else "warn"})

    # Compare with published count
    count_results = []
    if published_count is not None and total > 0:
        is_less = total < published_count
        count_results.append({
            "title": "Listings vs Published",
            "detail": f"{total} returned / {published_count} published {'✓ (filtered correctly)' if is_less else '— same as published total (filter may not be working)'}",
            "status": "pass" if is_less else "warn",
        })

    return {
        "listing_count": total,
        "listing_urls":  card_data["listingUrls"],
        "results":       results,
        "count_results": count_results,
    }


async def _wait_for_cards_or_no_results(page: Page, card_selector: str, timeout_s: int = 30) -> tuple[int, bool]:
    """
    Poll for listing cards or a no-results indicator — mirrors waitForCardsOrNoResults().
    Returns (count, no_results_flag).
    """
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        result = await page.evaluate("""(args) => {
            const {cardSel, noResSel, containerSel, patterns} = args;
            const cards = document.querySelectorAll(cardSel);
            if (cards.length > 0) return {count: cards.length, noResults: false};

            if (document.querySelector(noResSel)) return {count: 0, noResults: true};

            const containers = document.querySelectorAll(containerSel);
            if (containers.length > 0) {
                for (const el of containers) {
                    const text = el.textContent;
                    for (const pattern of patterns) {
                        if (new RegExp(pattern, 'i').test(text)) return {count: 0, noResults: true};
                    }
                }
            }
            return {count: 0, noResults: false};
        }""", {
            "cardSel":      card_selector,
            "noResSel":     NO_RESULTS_SELECTORS,
            "containerSel": SEARCH_CONTAINER_SELECTORS,
            "patterns":     NO_RESULTS_PATTERNS,
        })
        if result["count"] > 0 or result["noResults"]:
            return result["count"], result["noResults"]
        await asyncio.sleep(1)
    # Final check
    cards = await page.query_selector_all(card_selector)
    return len(cards), False
