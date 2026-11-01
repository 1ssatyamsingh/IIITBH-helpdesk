from typing import Any

from ddgs import DDGS


class WebSearchError(RuntimeError):
    pass


class DDGSWebSearch:
    """Live metasearch adapter; returns compact, untrusted web evidence."""

    def __init__(self, max_results: int = 6) -> None:
        self.max_results = max(1, min(max_results, 8))

    def search(self, query: str) -> list[dict[str, Any]]:
        clean_query = " ".join(query.split())[:400]
        if not clean_query:
            return []
        collected: dict[str, dict[str, Any]] = {}
        try:
            with DDGS(timeout=12) as client:
                searches = [
                    f"site:iiitbh.ac.in {clean_query}",
                    clean_query,
                ]
                for search_query in searches:
                    try:
                        results = client.text(
                            search_query,
                            region="in-en",
                            safesearch="moderate",
                            max_results=self.max_results,
                            backend="auto",
                        )
                    except Exception:
                        # Some providers return no matches for site-restricted queries;
                        # continue with the general query rather than aborting the search.
                        continue
                    for item in results or []:
                        url = str(item.get("href") or item.get("url") or "").strip()
                        title = str(item.get("title") or "").strip()
                        snippet = str(item.get("body") or item.get("snippet") or "").strip()
                        if not url.startswith(("https://", "http://")) or not title or not snippet:
                            continue
                        if url not in collected:
                            collected[url] = {
                                "title": title[:240],
                                "url": url[:1500],
                                "snippet": snippet[:1800],
                            }
                        if len(collected) >= self.max_results:
                            break
                    if len(collected) >= self.max_results:
                        break
        except Exception as exc:
            raise WebSearchError("Live web search failed: " + type(exc).__name__) from exc
        results = list(collected.values())
        # Stable sort boosts official institute domains without disturbing search relevance.
        results.sort(key=lambda item: 0 if "iiitbh.ac.in" in item["url"].lower() else 1)
        return results[: self.max_results]
