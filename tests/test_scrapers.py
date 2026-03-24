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


# ── Lobste.rs JSON scraper ──────────────────────────────────────────────────


class TestLobstersScraper:
    @pytest.mark.asyncio
    @respx.mock
    async def test_extract_articles(self) -> None:
        stories = [
            {
                "title": "Rust in Production",
                "url": "http://example.com/rust",
                "score": 42,
                "description": "A great article about Rust.",
                "tags": ["rust", "programming"],
                "comments_url": "https://lobste.rs/s/abc123",
            },
            {
                "title": "Go Generics Deep Dive",
                "url": "http://example.com/go",
                "score": 30,
                "description": "",
                "tags": ["go"],
                "comments_url": "https://lobste.rs/s/def456",
            },
        ]

        respx.get("https://lobste.rs/hottest.json").mock(
            return_value=httpx.Response(200, json=stories)
        )

        source = SourceConfig(
            name="Lobsters", scraper="lobsters_feed",
            max_articles=5, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        assert len(articles) == 2
        assert articles[0].title == "Rust in Production"
        assert articles[0].url == "http://example.com/rust"
        assert articles[0].source_name == "Lobsters"
        assert articles[0].score == 42
        assert articles[0].snippet == "A great article about Rust."

    @pytest.mark.asyncio
    @respx.mock
    async def test_fallback_to_comments_url(self) -> None:
        """Stories without an external URL should use comments_url."""
        stories = [
            {
                "title": "Ask Lobsters: Best editor?",
                "url": "",
                "score": 10,
                "description": "",
                "comments_url": "https://lobste.rs/s/xyz789",
            },
        ]
        respx.get("https://lobste.rs/hottest.json").mock(
            return_value=httpx.Response(200, json=stories)
        )

        source = SourceConfig(
            name="Lobsters", scraper="lobsters_feed",
            max_articles=5, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        assert len(articles) == 1
        assert articles[0].url == "https://lobste.rs/s/xyz789"


# ── GitHub Trending scraper ─────────────────────────────────────────────────


_GITHUB_TRENDING_HTML = """\
<html>
<body>
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/openai/tiktoken" data-view-component="true">
      openai / tiktoken
    </a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">Fast BPE tokeniser for use with OpenAI models</p>
  <span class="d-inline-block float-sm-right">12 stars today</span>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/astral-sh/uv" data-view-component="true">
      astral-sh / uv
    </a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">An extremely fast Python package manager</p>
  <span class="d-inline-block float-sm-right">1,234 stars today</span>
</article>
</body>
</html>
"""


class TestGitHubTrendingScraper:
    @pytest.mark.asyncio
    @respx.mock
    async def test_extract_articles(self) -> None:
        respx.get("https://github.com/trending").mock(
            return_value=httpx.Response(200, text=_GITHUB_TRENDING_HTML)
        )

        source = SourceConfig(
            name="GH Trending", scraper="github_trending",
            max_articles=10, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        assert len(articles) == 2
        assert articles[0].title == "openai/tiktoken"
        assert articles[0].url == "https://github.com/openai/tiktoken"
        assert articles[0].source_name == "GH Trending"
        assert articles[0].score == 12
        assert articles[0].snippet == "Fast BPE tokeniser for use with OpenAI models"

        assert articles[1].title == "astral-sh/uv"
        assert articles[1].score == 1234

    @pytest.mark.asyncio
    @respx.mock
    async def test_language_filter(self) -> None:
        respx.get("https://github.com/trending").mock(
            return_value=httpx.Response(200, text=_GITHUB_TRENDING_HTML)
        )

        source = SourceConfig(
            name="GH Trending", scraper="github_trending",
            query="python", max_articles=10, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        # Just verify it still works with the query param
        assert len(articles) == 2


# ── Substack RSS scraper ────────────────────────────────────────────────────


_SUBSTACK_RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Substack</title>
    <item>
      <title>Understanding Transformers</title>
      <link>https://example.substack.com/p/understanding-transformers</link>
      <description>A deep dive into the transformer architecture.</description>
    </item>
    <item>
      <title>The State of AI in 2025</title>
      <link>https://example.substack.com/p/state-of-ai</link>
      <description>An overview of recent AI developments.</description>
    </item>
  </channel>
</rss>
"""


class TestSubstackScraper:
    @pytest.mark.asyncio
    @respx.mock
    async def test_extract_articles(self) -> None:
        respx.get("https://example.substack.com/feed").mock(
            return_value=httpx.Response(200, text=_SUBSTACK_RSS)
        )

        source = SourceConfig(
            name="Example Blog", scraper="substack_feed",
            url="https://example.substack.com",
            max_articles=10, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        assert len(articles) == 2
        assert articles[0].title == "Understanding Transformers"
        assert articles[0].url == "https://example.substack.com/p/understanding-transformers"
        assert articles[0].source_name == "Example Blog"
        assert articles[0].snippet == "A deep dive into the transformer architecture."

    @pytest.mark.asyncio
    @respx.mock
    async def test_auto_appends_feed(self) -> None:
        """URL without /feed should have it auto-appended."""
        respx.get("https://example.substack.com/feed").mock(
            return_value=httpx.Response(200, text=_SUBSTACK_RSS)
        )

        source = SourceConfig(
            name="Test", scraper="substack_feed",
            url="https://example.substack.com/",
            max_articles=10, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        assert len(articles) == 2


# ── Podcast RSS scraper ─────────────────────────────────────────────────────


_PODCAST_RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Tech Podcast</title>
    <item>
      <title>Episode 42: The Future of AI</title>
      <link>https://techpodcast.com/ep42</link>
      <description>&lt;p&gt;In this episode we discuss the &lt;b&gt;future&lt;/b&gt; of AI.&lt;/p&gt;</description>
      <enclosure url="https://techpodcast.com/ep42.mp3" type="audio/mpeg" />
    </item>
    <item>
      <title>Episode 41: Rust vs Go</title>
      <link></link>
      <description>Comparing Rust and Go for systems programming.</description>
      <enclosure url="https://techpodcast.com/ep41.mp3" type="audio/mpeg" />
    </item>
  </channel>
</rss>
"""


class TestPodcastRssScraper:
    @pytest.mark.asyncio
    @respx.mock
    async def test_extract_articles(self) -> None:
        respx.get("https://techpodcast.com/feed").mock(
            return_value=httpx.Response(200, text=_PODCAST_RSS)
        )

        source = SourceConfig(
            name="Tech Pod", scraper="podcast_rss",
            url="https://techpodcast.com/feed",
            max_articles=10, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        assert len(articles) == 2
        assert articles[0].title == "Episode 42: The Future of AI"
        assert articles[0].url == "https://techpodcast.com/ep42"
        assert articles[0].source_name == "Tech Pod"
        # HTML should be stripped from snippet
        assert "<p>" not in (articles[0].snippet or "")
        assert "future" in (articles[0].snippet or "").lower()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fallback_to_enclosure_url(self) -> None:
        """Episodes without <link> should fall back to enclosure URL."""
        respx.get("https://techpodcast.com/feed").mock(
            return_value=httpx.Response(200, text=_PODCAST_RSS)
        )

        source = SourceConfig(
            name="Tech Pod", scraper="podcast_rss",
            url="https://techpodcast.com/feed",
            max_articles=10, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        # Episode 41 has empty <link>, should fall back to enclosure
        assert articles[1].url == "https://techpodcast.com/ep41.mp3"


# ── Bluesky scraper ────────────────────────────────────────────────────────


class TestBlueskyFeedScraper:
    @pytest.mark.asyncio
    @respx.mock
    async def test_public_search(self) -> None:
        search_response = {
            "posts": [
                {
                    "record": {
                        "text": "Check out this great article about AI agents https://example.com/ai-agents",
                        "facets": [],
                    },
                    "embed": {},
                },
                {
                    "record": {
                        "text": "No links in this post, just thoughts on AI",
                        "facets": [],
                    },
                    "embed": {},
                },
                {
                    "record": {
                        "text": "Another link: https://example.com/ml-research for ML fans",
                        "facets": [],
                    },
                    "embed": {},
                },
            ]
        }

        respx.get("https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts").mock(
            return_value=httpx.Response(200, json=search_response)
        )

        source = SourceConfig(
            name="Bluesky AI", scraper="bluesky_feed",
            query="AI agents", max_articles=10, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        # Should get 2 articles (the 2 posts with URLs), skipping the text-only post
        assert len(articles) == 2
        assert articles[0].url == "https://example.com/ai-agents"
        assert articles[0].source_name == "Bluesky AI"
        assert articles[1].url == "https://example.com/ml-research"

    @pytest.mark.asyncio
    @respx.mock
    async def test_skips_bsky_internal_urls(self) -> None:
        search_response = {
            "posts": [
                {
                    "record": {
                        "text": "Check https://bsky.app/profile/someone for more",
                        "facets": [],
                    },
                    "embed": {},
                },
            ]
        }

        respx.get("https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts").mock(
            return_value=httpx.Response(200, json=search_response)
        )

        source = SourceConfig(
            name="Bluesky", scraper="bluesky_feed",
            query="test", max_articles=10, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        assert len(articles) == 0  # bsky.app links are filtered out


# ── Mastodon scraper ────────────────────────────────────────────────────────


class TestMastodonFeedScraper:
    @pytest.mark.asyncio
    @respx.mock
    async def test_hashtag_timeline(self) -> None:
        toots = [
            {
                "content": '<p>Great article on ML: <a href="https://example.com/ml">link</a></p>',
                "card": {
                    "url": "https://example.com/ml",
                    "title": "Machine Learning Explained",
                    "description": "A comprehensive guide to ML.",
                },
            },
            {
                "content": "<p>Just my thoughts, no links here.</p>",
                "card": None,
            },
            {
                "content": '<p>Check out <a href="https://example.com/rust">this Rust article</a></p>',
                "card": None,
            },
        ]

        respx.get("https://mastodon.social/api/v1/timelines/tag/machinelearning").mock(
            return_value=httpx.Response(200, json=toots)
        )

        source = SourceConfig(
            name="Mastodon ML", scraper="mastodon_feed",
            url="https://mastodon.social", query="machinelearning",
            max_articles=10, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        # Toot 1 has card, toot 2 has no links, toot 3 has extracted URL
        assert len(articles) == 2
        assert articles[0].url == "https://example.com/ml"
        assert articles[0].title == "Machine Learning Explained"
        assert articles[0].source_name == "Mastodon ML"

    @pytest.mark.asyncio
    @respx.mock
    async def test_public_timeline_fallback(self) -> None:
        """No query and no api_key should use public timeline."""
        respx.get("https://mastodon.social/api/v1/timelines/public").mock(
            return_value=httpx.Response(200, json=[])
        )

        source = SourceConfig(
            name="Mastodon", scraper="mastodon_feed",
            url="https://mastodon.social",
            max_articles=10, request_delay_seconds=0,
        )
        scraper = get_scraper(source)
        articles = await scraper.extract_articles()

        assert len(articles) == 0
