"""Stealth-aware article fetching with multi-tier fallback.

Fetch chain: Playwright+stealth -> httpx (realistic headers) -> trafilatura.fetch_url
"""

from __future__ import annotations

import asyncio
import logging
import random
import re

import httpx
from playwright.async_api import Browser, BrowserContext
from playwright_stealth import Stealth

log = logging.getLogger(__name__)

_stealth = Stealth()

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1680, "height": 1050},
]

_CONTENT_SELECTORS = ["article", "main", "[role='main']", ".post-content", ".article-body", "#content"]

_BOT_CHALLENGE_RE = re.compile(
    r"verify.{0,20}(human|not a robot|you are a)"
    r"|captcha"
    r"|challenge-platform"
    r"|cf-browser-verification"
    r"|checking.{0,20}browser"
    r"|bot.{0,15}(check|detection|protect)"
    r"|security.{0,15}check"
    r"|access.{0,15}denied"
    r"|please.{0,20}(enable|allow).{0,20}(javascript|cookies)"
    r"|unusual.{0,15}traffic"
    r"|automated.{0,15}access"
    r"|rate.{0,10}limit",
    re.IGNORECASE,
)


def random_user_agent() -> str:
    """Return a random realistic browser User-Agent string."""
    return random.choice(_USER_AGENTS)


def is_bot_challenge(html: str) -> bool:
    """Detect whether the HTML is a bot-challenge/CAPTCHA page rather than real content."""
    if len(html) > 100_000:
        return False

    sample = html[:15_000]
    if _BOT_CHALLENGE_RE.search(sample):
        tag_count = sample.count("<p") + sample.count("<article") + sample.count("<section")
        if tag_count < 5:
            return True
    return False


async def create_stealth_context(browser: Browser) -> BrowserContext:
    """Create a Playwright BrowserContext with stealth patches and realistic fingerprint."""
    viewport = random.choice(_VIEWPORTS)
    ua = random_user_agent()

    context = await browser.new_context(
        user_agent=ua,
        viewport=viewport,
        locale="en-US",
        timezone_id="America/New_York",
        color_scheme="light",
    )

    await _stealth.apply_stealth_async(context)
    return context


async def _fetch_playwright(
    url: str,
    context: BrowserContext,
    timeout_ms: int,
) -> str | None:
    """Fetch HTML using a stealth Playwright context."""
    page = await context.new_page()
    try:
        await asyncio.sleep(random.uniform(0.5, 2.0))

        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        for selector in _CONTENT_SELECTORS:
            try:
                await page.wait_for_selector(selector, timeout=3000)
                break
            except Exception:
                continue

        return await page.content()
    except Exception:
        log.debug("Playwright stealth failed for %s", url, exc_info=True)
        return None
    finally:
        await page.close()


async def _fetch_httpx(url: str) -> str | None:
    """Fetch HTML with httpx using realistic browser headers."""
    ua = random_user_agent()
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            http2=True,
        ) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text
    except Exception:
        log.debug("httpx fetch failed for %s", url, exc_info=True)
        return None


def _fetch_trafilatura(url: str) -> str | None:
    """Fetch HTML using trafilatura's built-in downloader (sync, run in thread)."""
    try:
        import trafilatura
        return trafilatura.fetch_url(url)
    except Exception:
        log.debug("trafilatura fetch failed for %s", url, exc_info=True)
        return None


async def fetch_article_html(
    url: str,
    *,
    context: BrowserContext | None = None,
    timeout_ms: int = 30_000,
) -> str | None:
    """Three-tier fetch: Playwright+stealth -> httpx -> trafilatura.fetch_url.

    Returns the raw HTML string, or None if all methods fail.
    Each tier checks for bot-challenge pages and falls through if detected.
    """
    if context is not None:
        html = await _fetch_playwright(url, context, timeout_ms)
        if html and len(html) > 500:
            if is_bot_challenge(html):
                log.info("Bot challenge detected via Playwright for %s, trying fallbacks", url)
            else:
                log.debug("Fetched %s via Playwright (%d chars)", url, len(html))
                return html

    html = await _fetch_httpx(url)
    if html and len(html) > 500:
        if is_bot_challenge(html):
            log.info("Bot challenge detected via httpx for %s, trying trafilatura", url)
        else:
            log.debug("Fetched %s via httpx (%d chars)", url, len(html))
            return html

    html = await asyncio.to_thread(_fetch_trafilatura, url)
    if html and len(html) > 500:
        if is_bot_challenge(html):
            log.warning("Bot challenge detected via trafilatura for %s, all tiers failed", url)
            return None
        log.debug("Fetched %s via trafilatura (%d chars)", url, len(html))
        return html

    log.warning("All fetch methods failed for %s", url)
    return None
