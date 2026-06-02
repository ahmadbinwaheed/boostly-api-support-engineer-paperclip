"""
steps/step8_listing_validator.py
Port of step8-listing-validator.js + widgets/homey.js + widgets/ownerrez.js + widgets/index.js
"""

import logging
from playwright.async_api import Page
from urllib.parse import urlparse, parse_qs

from config import PMS, QUERY_PARAMS

log = logging.getLogger("Boostly-API-Support-Engineer.step8")


async def validate_listing(page: Page) -> dict:
    """Validate a single listing page — widget detection, auto-fill, price, book-now."""
    results = []
    current_url = page.url

    # URL params
    params = parse_qs(urlparse(current_url).query)
    def get_param(keys):
        for k in keys:
            if k in params:
                return params[k][0]
        return None

    arrive_param = get_param(QUERY_PARAMS["arrive"])
    depart_param = get_param(QUERY_PARAMS["depart"])
    guest_param  = get_param(QUERY_PARAMS["guests"])

    results.append({
        "title": "Listing URL Params",
        "detail": f"arrive={arrive_param}, depart={depart_param}, guests={guest_param}",
        "status": "pass" if all([arrive_param, depart_param, guest_param]) else "warn",
    })

    # Widget detection — mirrors detectBookingWidget()
    widget = await _detect_booking_widget(page)

    results.append({
        "title": "Booking Widget Type",
        "detail": f"{widget['type']} widget detected ✓" if widget["found"] else "No booking widget found on this listing",
        "status": "pass" if widget["found"] else "fail",
    })

    if not widget["found"]:
        return {"widget_type": None, "results": results, "page_url": current_url}

    if widget.get("is_iframe"):
        iframe_src = widget.get("iframe_src", "")
        origin = urlparse(iframe_src).hostname if iframe_src else "unknown origin"
        results.append({
            "title": "Widget Access",
            "detail": f"{widget['type']} widget is iframe-based ({origin}) — auto-fill and price checks require manual verification",
            "status": "warn",
        })
        return {"widget_type": widget["type"], "is_iframe": True, "results": results, "page_url": current_url}

    # Homey inline widget
    if widget["type"] == "homey":
        cfg = PMS["homey"]

        fields = await page.evaluate("""(cfg) => {
            function firstMatch(selectors) {
                for (const sel of selectors) {
                    try { const el = document.querySelector(sel); if (el) return el; } catch(_) {}
                }
                return null;
            }
            const checkin  = firstMatch(cfg.checkin_selectors);
            const checkout = firstMatch(cfg.checkout_selectors);
            const guests   = firstMatch(cfg.guests_selectors);
            const priceEl  = firstMatch(cfg.price_selectors);
            const vdEl     = firstMatch(cfg.view_details_selectors)
                || Array.from(document.querySelectorAll('a,button')).find(el => el.textContent.trim().toLowerCase().includes('view details'));
            const bnEl     = firstMatch(cfg.book_now_selectors)
                || Array.from(document.querySelectorAll('a,button')).find(el => /book\\s*(now)?/i.test(el.textContent.trim()));

            const vdVisible = vdEl ? (() => {
                const s = window.getComputedStyle(vdEl);
                return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
            })() : false;

            return {
                checkin:        checkin  ? checkin.value  : null,
                checkout:       checkout ? checkout.value : null,
                guests:         guests   ? (guests.value || guests.textContent.trim()) : null,
                price:          priceEl  ? priceEl.textContent.trim() : null,
                view_details:   vdVisible,
                book_now_href:  bnEl ? (bnEl.href || null) : null,
                book_now_found: !!bnEl,
            };
        }""", {
            "checkin_selectors":      cfg["checkin_selectors"],
            "checkout_selectors":     cfg["checkout_selectors"],
            "guests_selectors":       cfg["guests_selectors"],
            "price_selectors":        cfg["price_selectors"],
            "view_details_selectors": cfg["view_details_selectors"],
            "book_now_selectors":     cfg["book_now_selectors"],
        })

        if arrive_param:
            results.append({
                "title": "Check-in Auto-fill",
                "detail": f"Value: {fields['checkin']} ✓" if fields["checkin"] else "Check-in field found but empty",
                "status": "pass" if fields["checkin"] else "warn",
            })
        if depart_param:
            results.append({
                "title": "Check-out Auto-fill",
                "detail": f"Value: {fields['checkout']} ✓" if fields["checkout"] else "Check-out field found but empty",
                "status": "pass" if fields["checkout"] else "warn",
            })
        if guest_param:
            results.append({
                "title": "Guests Auto-fill",
                "detail": f"Value: {fields['guests']} ✓" if fields["guests"] else "Guests field found but empty",
                "status": "pass" if fields["guests"] else "warn",
            })

        results.append({
            "title": "Price Display",
            "detail": f"Total price shown: {fields['price']} ✓" if fields["price"] else "No total price visible",
            "status": "pass" if fields["price"] else "warn",
        })
        results.append({
            "title": '"View Details" Button',
            "detail": "View Details is visible ✓" if fields["view_details"] else "View Details not found or hidden",
            "status": "pass" if fields["view_details"] else "warn",
        })

        if fields["book_now_found"]:
            href_str = f" — {fields['book_now_href'][:80]}" if fields["book_now_href"] else ""
            results.append({"title": '"Book Now" Button', "detail": f"Found ✓{href_str}", "status": "pass"})
        else:
            results.append({"title": '"Book Now" Button', "detail": "Book Now button not found", "status": "warn"})

        return {
            "widget_type": "homey",
            "is_iframe":   False,
            "price":       fields["price"],
            "book_now_href": fields["book_now_href"],
            "results":     results,
            "page_url":    current_url,
        }

    return {"widget_type": widget["type"], "results": results, "page_url": current_url}


async def _detect_booking_widget(page: Page) -> dict:
    """Port of detectBookingWidget() + HomeyWidget.detect() + OwnerRezWidget.detect()"""
    return await page.evaluate("""(pms) => {
        function firstMatch(selectors) {
            for (const sel of selectors) {
                try { const el = document.querySelector(sel); if (el) return el; } catch(_) {}
            }
            return null;
        }

        // Homey
        const homeyEl = firstMatch(pms.homey.widget_selectors);
        if (homeyEl) return {type:'homey', found:true, is_iframe:false};

        // OwnerRez
        const orEl = firstMatch(pms.ownerrez.widget_selectors);
        if (orEl) {
            const iframe = firstMatch(pms.ownerrez.iframe_selectors);
            return {type:'ownerrez', found:true, is_iframe:true, iframe_found:!!iframe, iframe_src: iframe ? iframe.src : null};
        }

        // Lodgify
        const ldgEl = firstMatch(pms.lodgify.widget_selectors);
        if (ldgEl) {
            const iframe = ldgEl.querySelector('iframe');
            return {type:'lodgify', found:true, is_iframe:!!iframe, iframe_src: iframe ? iframe.src : null};
        }

        // Generic iframe fallback
        const iframes = Array.from(document.querySelectorAll('#sidebar iframe, .sidebar iframe, [class*="booking"] iframe'));
        if (iframes.length > 0) {
            return {type:'unknown-iframe', found:true, is_iframe:true, iframe_src: iframes[0].src};
        }

        return {type: null, found: false};
    }""", {
        "homey":    {k: v for k, v in PMS["homey"].items() if isinstance(v, list)},
        "ownerrez": {k: v for k, v in PMS["ownerrez"].items() if isinstance(v, list)},
        "lodgify":  {k: v for k, v in PMS["lodgify"].items() if isinstance(v, list)},
    })
