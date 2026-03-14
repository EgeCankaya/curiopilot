"""Scraper tests with mocked HTTP responses."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from curiopilot.config import SourceConfig
from curiopilot.scrapers import get_scraper


# ── Registry tests ───────────────────────────────────────────────────────────


class TestScraperRegistry:
    def test_get_hackernews_scraper(self) -> None:
        source = SourceConfig(name="HN", scraper="hackernews_api")
        scraper = get_scraper(source)
        assert scraper.__class__.__name__ == "HackerNewsApiScraper"

    def test_get_reddit_scraper(self) -> None:
        source = SourceConfig(name="Reddit", scraper="reddit_json", url="r/test")
        scraper = get_scraper(source)
        assert scraper.__class__.__name__ == "RedditJsonScraper"

    def test_get_arxiv_scraper(self) -> None:
        source = SourceConfig(name="ArXiv", scraper="arxiv_feed")
        scraper = get_scraper(source)
        assert scraper.__class__.__name__ == "ArxivFeedScraper"

    def test_unknown_scraper_raises(self) -> None:
        source = SourceConfig.model_construct(name="Bad", scraper="nonexistent")
        with pytest.raises(ValueError, match="No scraper registered"):
            get_scraper(source)


# ── HackerNews API scraper ───────────────────────────────────────────────────


class TestHackerNewsScraper:
    @pytest.mark.asyncio
    @respx.mock
    async def test_extract_articles(self) -> None:
        respx.get("https://hacker-news.firebaseio.com/v0/topstories.json").mock(
            return_value=httpx.Response(200, json=[1001, 1002])
        )
        respx.get("https://hacker-news.firebaseio.com/v0/item/1001.json").mock(
            return_value=httpx.Response(200, json={
                "type": "story",
                "title": "Test Story 1",
                "url": "http://example.com/1",
                "score": 100,
            })
        )
        respx.get("https://hacker-news.firebaseio.com/v0/item/1002.json").mock(
            return_value=httpx.Response(200, json={
                "type": "story",
                "title": "Test Story 2",
                "url": "http://example.com/2",
                "score": 50,
            })
        )

        source = SourceConfig(
            name="HN", scraper="hackernews_api",
            max_articles=2, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        assert len(articles) == 2
        assert articles[0].title == "Test Story 1"
        assert articles[0].url == "http://example.com/1"
        assert articles[0].source_name == "HN"
        assert articles[0].score == 100


# ── Reddit JSON scraper ──────────────────────────────────────────────────────


class TestRedditScraper:
    @pytest.mark.asyncio
    @respx.mock
    async def test_extract_articles(self) -> None:
        listing = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Reddit Post 1",
                            "url": "http://example.com/reddit/1",
                            "score": 200,
                            "stickied": False,
                            "is_self": False,
                            "selftext": "",
                            "permalink": "/r/test/comments/abc/",
                        }
                    },
                    {
                        "data": {
                            "title": "Stickied Post",
                            "url": "http://example.com/reddit/2",
                            "stickied": True,
                            "is_self": False,
                            "selftext": "",
                        }
                    },
                ],
                "after": None,
            }
        }

        respx.get("https://www.reddit.com/r/test/hot.json").mock(
            return_value=httpx.Response(200, json=listing)
        )

        source = SourceConfig(
            name="r/test", scraper="reddit_json", url="r/test",
            max_articles=10, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        assert len(articles) == 1  # stickied post filtered out
        assert articles[0].title == "Reddit Post 1"


# ── ArXiv feed scraper ───────────────────────────────────────────────────────


_ARXIV_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Attention Is All You Need</title>
    <id>https://arxiv.org/abs/1706.03762</id>
    <summary>We propose a new network architecture, the Transformer.</summary>
  </entry>
  <entry>
    <title>BERT: Pre-training of Deep Bidirectional Transformers</title>
    <id>https://arxiv.org/abs/1810.04805</id>
    <summary>We introduce BERT.</summary>
  </entry>
</feed>
"""


class TestArxivScraper:
    @pytest.mark.asyncio
    @respx.mock
    async def test_extract_articles(self) -> None:
        respx.get("http://export.arxiv.org/api/query").mock(
            return_value=httpx.Response(200, text=_ARXIV_XML)
        )

        source = SourceConfig(
            name="ArXiv AI", scraper="arxiv_feed",
            max_articles=5, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        assert len(articles) == 2
        assert articles[0].title == "Attention Is All You Need"
        assert "arxiv.org" in articles[0].url
        assert articles[0].source_name == "ArXiv AI"
