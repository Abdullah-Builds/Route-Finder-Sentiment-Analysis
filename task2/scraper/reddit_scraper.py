import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote


def fetch_reddit_posts(topic: str, limit: int = 100) -> list[dict]:
    """
    Fetch Reddit posts for a given topic via RSS feed using requests.

    Args:
        topic: Search query string.
        limit: Maximum number of posts to return.

    Returns:
        List of dicts with keys: title, summary, link.
    """
    encoded_topic = quote(topic)
    url = f"https://www.reddit.com/r/all/search.rss?q={encoded_topic}&sort=new&limit={limit}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch Reddit RSS: {e}")
        return []

    posts = []
    try:
        root = ET.fromstring(response.content)
        # Atom namespace used by Reddit RSS
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)

        for entry in entries[:limit]:
            title_el   = entry.find("atom:title", ns)
            content_el = entry.find("atom:content", ns)
            link_el    = entry.find("atom:link", ns)

            title   = title_el.text   if title_el   is not None else ""
            summary = content_el.text if content_el is not None else ""
            link    = link_el.attrib.get("href", "") if link_el is not None else ""

            posts.append({
                "title":   title,
                "summary": summary,
                "link":    link,
            })

    except ET.ParseError as e:
        print(f"[ERROR] Failed to parse RSS XML: {e}")

    return posts