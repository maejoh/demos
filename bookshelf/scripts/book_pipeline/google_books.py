import re
import time

import requests

from .utils import sanitize_title

GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
GOOGLE_FIELDS = "items(volumeInfo(title,authors,publishedDate,description,industryIdentifiers))"


def _author_looks_mangled(author: str) -> bool:
    """Return True if Google Books returned an ALL-CAPS or otherwise garbled author string."""
    alpha_words = [re.sub(r'[^A-Za-z]', '', w) for w in author.split()]
    alpha_words = [w for w in alpha_words if w]
    return len(alpha_words) > 0 and sum(1 for w in alpha_words if w.isupper()) > len(alpha_words) / 2


def _title_looks_mangled(title: str) -> bool:
    """Return True if the title is entirely uppercase."""
    alpha = [c for c in title if c.isalpha()]
    return len(alpha) > 0 and all(c.isupper() for c in alpha)


def _google_request(params: dict) -> dict | None:
    """Make a Google Books API request with retry on 429."""
    for attempt in range(3):
        try:
            response = requests.get(GOOGLE_BOOKS_URL, params=params, timeout=10)
            if response.status_code == 429:
                wait = 2 ** attempt
                if attempt == 0:
                    print(f"  [429] rate limited, retrying...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  [warn] request failed: {e}")
            return None
    return None


def _parse_volume(volume_info: dict, epub_year: int | None = None) -> dict:
    """Extract normalized fields from a Google Books volumeInfo dict."""
    identifiers = volume_info.get("industryIdentifiers", [])
    isbn = next(
        (i["identifier"] for i in identifiers if i.get("type") == "ISBN_13"),
        next((i["identifier"] for i in identifiers if i.get("type") == "ISBN_10"), None),
    )

    authors = volume_info.get("authors", [])
    author = " & ".join(authors) if authors else None

    date_str = volume_info.get("publishedDate", "")
    year_match = re.search(r'\d{4}', date_str)
    year = int(year_match.group()) if year_match else epub_year

    return {
        "isbn": isbn,
        "title": volume_info.get("title"),
        "author": author,
        "year": year,
        "description": volume_info.get("description", ""),
    }


def fetch_google_book(
    isbn: str | None,
    title: str,
    author: str,
    epub_year: int | None,
    api_key: str | None,
) -> dict | None:
    """
    Fetch book metadata from Google Books API.
    Queries by ISBN first if available, then falls through title/author variants.
    Returns a normalized dict or None if nothing found.
    """
    base: dict = {"fields": GOOGLE_FIELDS, "maxResults": 1}
    if api_key:
        base["key"] = api_key

    queries: list[str] = []
    if isbn:
        queries.append(f"isbn:{isbn}")

    first_author = author.split(",")[0].strip()
    clean_title = sanitize_title(title)
    queries.append(f'intitle:"{title}" inauthor:"{author}"')
    if first_author != author:
        queries.append(f'intitle:"{title}" inauthor:"{first_author}"')
    queries.append(f'intitle:"{title}"')
    if clean_title != title:
        queries.append(f'intitle:"{clean_title}"')

    for q in queries:
        data = _google_request({**base, "q": q})
        if data:
            items = data.get("items", [])
            if items:
                return _parse_volume(items[0].get("volumeInfo", {}), epub_year)

    return None
