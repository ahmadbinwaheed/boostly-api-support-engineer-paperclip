"""
utils/helpers.py — Port of utils/dates.js + utils/dom.js
"""

import asyncio
import random
from datetime import date, timedelta
from urllib.parse import urlparse, parse_qs

from config import QUERY_PARAMS, SKIP_PATTERN


# ── Date generation (exact port of generateTestDateSets) ───────────────────────

def fmt_date(d: date) -> str:
    """Format as MM-DD-YYYY — same format Boostly search URLs expect."""
    return d.strftime("%m-%d-%Y")


def generate_test_date_sets() -> list[dict]:
    today = date.today()

    # Iteration 1: tomorrow → +2 nights
    arrive1 = today + timedelta(days=1)
    depart1 = arrive1 + timedelta(days=2)

    # Iteration 2: 8th of next month → +4 nights
    month2 = today.month + 1
    year2  = today.year + (1 if month2 > 12 else 0)
    month2 = month2 if month2 <= 12 else month2 - 12
    arrive2 = date(year2, month2, 8)
    depart2 = arrive2 + timedelta(days=4)

    # Iteration 3: 10th of 3 months from now → +3 nights
    month3 = today.month + 3
    year3  = today.year + (1 if month3 > 12 else 0)
    month3 = month3 if month3 <= 12 else month3 - 12
    arrive3 = date(year3, month3, 10)
    depart3 = arrive3 + timedelta(days=3)

    return [
        {"arrive": fmt_date(arrive1), "depart": fmt_date(depart1), "guests": "2", "label": "Near-term (2 nights)"},
        {"arrive": fmt_date(arrive2), "depart": fmt_date(depart2), "guests": "2", "label": "Next month (4 nights)"},
        {"arrive": fmt_date(arrive3), "depart": fmt_date(depart3), "guests": "2", "label": "3 months out (3 nights)"},
    ]


# ── Human-like delay (port of randomDelay) ─────────────────────────────────────

async def random_delay(min_s: float = 4.0, max_s: float = 8.0):
    """Mirrors the extension's randomDelay(4000, 8000) — bots have perfectly
    regular timing, humans don't."""
    await asyncio.sleep(random.uniform(min_s, max_s))


# ── URL helpers (port of dom.js) ───────────────────────────────────────────────

def is_skippable_url(url: str) -> bool:
    return bool(SKIP_PATTERN.search(url))


def is_wp_admin_url(url: str) -> bool:
    return "/wp-admin/" in url or "/wp-login.php" in url


def has_required_query_params(url: str) -> dict:
    try:
        params = parse_qs(urlparse(url).query)
        has_arrive = any(k in params for k in QUERY_PARAMS["arrive"])
        has_depart = any(k in params for k in QUERY_PARAMS["depart"])
        has_guests = any(k in params for k in QUERY_PARAMS["guests"])
        return {
            "has_arrive": has_arrive,
            "has_depart": has_depart,
            "has_guests": has_guests,
            "all": has_arrive and has_depart and has_guests,
        }
    except Exception:
        return {"has_arrive": False, "has_depart": False, "has_guests": False, "all": False}


def get_url_param(url: str, keys: list[str]) -> str | None:
    try:
        params = parse_qs(urlparse(url).query)
        for k in keys:
            if k in params:
                return params[k][0]
    except Exception:
        pass
    return None
