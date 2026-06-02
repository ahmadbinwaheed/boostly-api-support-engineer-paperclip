"""
config.py — Python port of config.js
All selectors, patterns, and constants are kept identical to the extension.
"""

import re

# ── Site detection ──────────────────────────────────────────────────────────────
DETECTION = {
    "footer_text": "Website made by Boostly",
    "wp_admin_bar": "#wpadminbar",
}

# ── URL patterns ────────────────────────────────────────────────────────────────
URL_PATTERNS = {
    "homepage":      re.compile(r"^https?://[^/]+/?(\\?.*)?$"),
    "search_results": re.compile(r"/search-results", re.IGNORECASE),
    "single_listing": re.compile(
        r"/(properties|listing|listings|stays|cabins|rentals|units|accommodation)/",
        re.IGNORECASE,
    ),
}

# ── WP Admin paths ──────────────────────────────────────────────────────────────
WP_ADMIN = {
    "plugins":            "/wp-admin/plugins.php",
    "published_listings": "/wp-admin/edit.php?post_type=listing",
    "pms_settings":       "/wp-admin/admin.php?page=boostly-pms-settings",
    "pms_settings_tab":   "/wp-admin/admin.php?post_type=listing&page=boostly-pms-settings&tab=",
}

# ── Plugin name patterns ────────────────────────────────────────────────────────
PLUGINS = {
    "boostly_connect": re.compile(r"boostly\s*connect", re.IGNORECASE),
    "boostly_pms":     re.compile(r"^boostly\s*pms$", re.IGNORECASE),
    "author_text":     "By Boostly",
}

# ── Search form selectors ───────────────────────────────────────────────────────
SEARCH_FORM = {
    "bar":           ".search-banner, .search-wrap, .hori-daily-search-wrap, [class*='search-wrap'], [class*='search-banner']",
    "arrive_input":  "input[name='arrive']",
    "depart_input":  "input[name='depart']",
    "guests_input":  "input[name='guest'], input[name='guests'], select[name='guest'], select[name='guests']",
    "submit_button": "button[type='submit'].search-button, .search-button, .hori-search-btn, button[class*='search'], form[action*='search-results'] button[type='submit']",
    "form_tag":      "form[action*='search-results']",
}

# ── Search results selectors ────────────────────────────────────────────────────
SEARCH_RESULTS = {
    "listing_cards": ".listing-item, .item-listing, article[class*='listing'], .property-item, [class*='listing-card']",
    "listing_title": ".item-title a, h2 a, .listing-title a, .property-title a, h3 a",
    "listing_image": ".listing-media img, .item-media img, .property-image img, [class*='listing'] img",
    "listing_price": ".item-price, .price-area, .listing-price, .nightly-price, [class*='price']",
    "listing_link":  "a[href*='/properties/'], a[href*='/listing/'], a[href*='/listings/'], a[href*='/stays/'], a[href*='/cabins/'], a[href*='/rentals/']",
    "map_listing_link": ".map-popup a, .marker-popup a, .map-listing a, [class*='map'] a[href*='properties']",
}

# ── WP Admin selectors ──────────────────────────────────────────────────────────
WP_ADMIN_SELECTORS = {
    "plugin_rows":        "#the-list tr",
    "plugin_name":        ".plugin-title strong",
    "plugin_author_link": ".plugin-meta a",
    "plugin_version":     ".plugin-version-author-uri",
    "published_count":    ".subsubsub .publish .count",
    "active_pms_items":   "#select2-boostly_active_pms-container .select2-selection__choice",
}

# ── Query param aliases ─────────────────────────────────────────────────────────
QUERY_PARAMS = {
    "arrive": ["arrive", "checkin", "check_in", "arrival"],
    "depart": ["depart", "checkout", "check_out", "departure"],
    "guests": ["guest", "guests", "adults", "adult_guests"],
}

# ── PMS widget selectors ────────────────────────────────────────────────────────
PMS = {
    "homey": {
        "name":               "Homey (Onsite)",
        "is_iframe":          False,
        "widget_selectors":   [".sidebar-booking-module", ".block-body-sidebar", "#homey-booking-form"],
        "checkin_selectors":  ["input[name='arrive']", ".arrival-date input", "#arrive"],
        "checkout_selectors": ["input[name='depart']", ".departure-date input", "#depart"],
        "guests_selectors":   ["input[name='guest']", "input[name='guests']", "select[name='guests']", "select[name='guest']"],
        "price_selectors":    [".total-price", ".price-total", ".booking-total", "[class*='total-price']"],
        "view_details_selectors": [".view-details", "a[class*='view-details']", "button[class*='view-details']"],
        "book_now_selectors": [".book-now", "a.book-now", "button.book-now", "a[class*='book-now']", "button[class*='book']"],
    },
    "ownerrez": {
        "name":               "OwnerRez",
        "is_iframe":          True,
        "iframe_origin":      "app.ownerrez.com",
        "widget_selectors":   ["div.ownerrez-widget", "[data-widgetid]"],
        "iframe_selectors":   ["iframe.ownerrez-widget-iframe", "iframe[src*='ownerrez']", "iframe[src*='ownerreservations']"],
        "checkin_selectors":  ["#ArrivalDate"],
        "checkout_selectors": ["#DepartureDate"],
        "guests_selectors":   ["#Adults"],
        "book_now_selectors": ["button[name='actionType'][value='Book']", "button[value='Book']"],
        "price_selectors":    [".quote-total", ".total-price"],
    },
    "lodgify": {
        "name":               "Lodgify",
        "is_iframe":          False,
        "widget_selectors":   ["#lodgify-book-now-box", ".ldg-bnb", "[id*='lodgify']"],
        "checkin_selectors":  ["[data-lodgify*='checkin']", "input[name*='checkin']"],
        "checkout_selectors": ["[data-lodgify*='checkout']", "input[name*='checkout']"],
        "guests_selectors":   ["select[name*='guest']", "[data-lodgify*='guest']"],
        "book_now_selectors": [".ldg-bnb button[type='submit']", "button[class*='lodgify']"],
        "price_selectors":    [".ldg-bnb [class*='price']", "[class*='lodgify-price']"],
    },
}

# ── Image placeholder patterns ──────────────────────────────────────────────────
IMAGE_PLACEHOLDERS = [
    "placeholder",
    "no-image",
    "default-thumbnail",
    "blank.gif",
    "placeholder.png",
    "data:image/gif;base64,R0lGODlh",
]

# ── Timeouts (ms → seconds) ─────────────────────────────────────────────────────
TIMEOUTS = {
    "tab_load":    20,
    "step_result": 30,
    "ajax_wait":   15,
    "search_results": 60,
    "pms_sync":    480,
    "relogin":     300,
}

# ── Skip patterns (static assets, mail links, etc.) ────────────────────────────
SKIP_PATTERN = re.compile(
    r"\.(jpg|jpeg|png|gif|svg|webp|pdf|zip|mp4|mp3|css|js)(\?.*)?$"
    r"|^(javascript:|mailto:|tel:|#)",
    re.IGNORECASE,
)

# ── Boostly sync action patterns ────────────────────────────────────────────────
SYNC_ACTION_PATTERNS = [
    re.compile(r"^boostly_.+_sync_(listings?|ical)$", re.IGNORECASE),
    re.compile(r"boostly.*sync", re.IGNORECASE),
]
