import time
from loguru import logger
from duckduckgo_search import DDGS
from src import config

def get_search_query(sport: str) -> str:
    """Generates an optimized search query based on the selected sport to fetch current news."""
    return f"latest {sport} tournament championship winners match results news 2025 2026"

def search_live_news(sport: str, max_results: int = 5) -> list[dict]:
    """
    Queries DuckDuckGo search for live news snippets of the selected sport.
    Returns a list of dicts: [{'title': ..., 'link': ..., 'snippet': ...}].
    """
    query = get_search_query(sport)
    logger.info(f"Querying DuckDuckGo for live news: '{query}'")
    
    results = []
    
    # We attempt to connect with retries
    retries = 2
    for attempt in range(1, retries + 1):
        try:
            with DDGS() as ddgs:
                ddg_results = list(ddgs.text(query, max_results=max_results))
                
                for r in ddg_results:
                    results.append({
                        "title": r.get("title", "No Title"),
                        "link": r.get("href", ""),
                        "snippet": r.get("body", "")
                    })
                    
            if results:
                logger.info(f"Successfully retrieved {len(results)} search results.")
                return results
                
        except Exception as e:
            logger.warning(f"DuckDuckGo search attempt {attempt} failed: {e}")
            if attempt < retries:
                time.sleep(1) # wait before retry
            else:
                logger.error(f"All DuckDuckGo search attempts failed.")
                
    # Fallback response when internet is offline or DDG blocks search
    logger.warning("Returning empty list for live search due to error or unavailability.")
    return []
