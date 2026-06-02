"""
steps/step1_auth.py
Port of step1-auth-checker.js + the extension's login-handling logic.

The extension checked for #wpadminbar on the current tab.
We: navigate to the login URL, fill credentials, submit, then verify
#wpadminbar appears on any admin page. Credentials are passed in at run-time.
"""

import logging
from playwright.async_api import Page

log = logging.getLogger("Boostly-API-Support-Engineer.step1")


async def check_auth(page: Page, site_url: str, login_url_path: str, username: str, password: str) -> dict:
    """
    Navigate to the homepage and check for #wpadminbar.
    If not logged in, go to login_url_path and log in with supplied credentials.
    Returns step result dict.
    """
    results = []

    # First — check if already logged in via homepage
    log.info(f"Step 1: checking WP auth on {site_url}/")
    try:
        await page.goto(f"{site_url}/", wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        results.append({"title": "WP Auth", "detail": f"Homepage load failed: {e}", "status": "fail"})
        return {"logged_in": False, "results": results}

    admin_bar = await page.query_selector("#wpadminbar")
    if admin_bar:
        results.append({
            "title": "WP Admin Login",
            "detail": "WordPress admin bar detected — user is logged in ✓",
            "status": "pass",
        })
        return {"logged_in": True, "results": results}

    # Not logged in — attempt login
    login_url = f"{site_url}{login_url_path}"
    log.info(f"Step 1: not logged in, attempting login at {login_url}")
    results.append({
        "title": "WP Admin Login",
        "detail": f"Admin bar not found — attempting login at {login_url}",
        "status": "warn",
    })

    try:
        await page.goto(login_url, wait_until="domcontentloaded", timeout=20000)

        # Fill in standard WP login form fields
        await page.fill("input[name='log'], input[name='username'], #user_login", username)
        await page.fill("input[name='pwd'], input[name='password'], #user_pass", password)
        await page.click("input[type='submit'], button[type='submit'], #wp-submit")
        await page.wait_for_load_state("domcontentloaded", timeout=20000)

        # Verify login by checking for admin bar or /wp-admin/ in URL
        current_url = page.url
        admin_bar = await page.query_selector("#wpadminbar")
        logged_in = bool(admin_bar) or "/wp-admin/" in current_url

        if logged_in:
            results.append({
                "title": "WP Login",
                "detail": f"Login successful ✓ — now at {current_url}",
                "status": "pass",
            })
        else:
            results.append({
                "title": "WP Login",
                "detail": f"Login may have failed — no admin bar at {current_url}",
                "status": "fail",
            })

        return {"logged_in": logged_in, "results": results}

    except Exception as e:
        results.append({"title": "WP Login", "detail": f"Login attempt failed: {e}", "status": "fail"})
        return {"logged_in": False, "results": results}


async def check_admin_session(page: Page, site_url: str, login_url_path: str, username: str, password: str) -> bool:
    """
    Used before any wp-admin navigation. Checks the current page — if we've been
    redirected away from wp-admin, re-logs in. Returns True if session is valid.
    Mirrors openAdminTab() + waitForReLogin() from background.js.
    """
    current_url = page.url
    if "/wp-admin/" in current_url:
        return True

    log.warning("Step: WP session appears expired, re-authenticating...")
    result = await check_auth(page, site_url, login_url_path, username, password)
    return result.get("logged_in", False)
