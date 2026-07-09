from __future__ import annotations

from nyx.domains.investing.news import news_url, parse_news_rss

_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Google News</title>
  <item>
    <title>Coca-Cola (KO) Looks Undervalued on Cash Flow - Example</title>
    <link>https://example.com/1</link>
    <pubDate>Mon, 06 Jul 2026 12:00:00 GMT</pubDate>
  </item>
  <item>
    <title><![CDATA[JNJ beats on earnings & raises outlook]]></title>
    <pubDate>Tue, 07 Jul 2026 09:30:00 GMT</pubDate>
  </item>
  <item>
    <link>https://example.com/3</link>
  </item>
</channel></rss>"""


def test_parse_news_rss_extracts_titles_and_unescapes():
    items = parse_news_rss(_RSS)
    assert len(items) == 2                                   # item with no title is skipped
    assert items[0].title == "Coca-Cola (KO) Looks Undervalued on Cash Flow - Example"
    assert items[0].published == "Mon, 06 Jul 2026 12:00:00 GMT"
    assert items[1].title == "JNJ beats on earnings & raises outlook"   # CDATA + &amp; decoded


def test_parse_news_rss_is_resilient_and_bounded():
    assert parse_news_rss("not xml at all") == []
    assert parse_news_rss("") == []
    assert len(parse_news_rss(_RSS, limit=1)) == 1


def test_news_url_encodes_query():
    url = news_url("BRK-B stock & value")
    assert url.startswith("https://news.google.com/rss/search?q=")
    assert " " not in url and "%26" in url          # space + '&' percent-encoded
