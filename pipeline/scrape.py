"""Step 1 - scrape a company website for raw signal.

`fetch(domain, page)` returns visible text for one logical page. Each logical page
maps to a few common URL paths; the first that responds with real content wins.
The qualifier agent (step 3) uses the same function as its tool.
"""
import requests
from bs4 import BeautifulSoup

from . import config

# Logical page -> candidate paths. These are also the tool options shown to the agent.
PAGES = {
    "home": [""],
    "about": ["about", "about-us", "company"],
    "security": ["security", "trust", "trust-center", "compliance"],
    "customers": ["customers", "case-studies", "enterprise"],
    "pricing": ["pricing", "plans"],
    "careers": ["careers", "jobs"],
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; outreach-research-bot/1.0)"}
MAX_CHARS = 6000


def clean(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "form"]):
        tag.decompose()
    parts = []
    if soup.title and soup.title.string:
        parts.append(soup.title.string.strip())
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        parts.append(meta["content"].strip())
    seen = set()
    for line in soup.get_text("\n").splitlines():
        line = " ".join(line.split())
        if len(line.split()) >= 4 and line not in seen:
            seen.add(line)
            parts.append(line)
    return "\n".join(parts)[:MAX_CHARS]


def fetch(domain, page="home"):
    """Return (text, url) for a logical page, or ("", None) if nothing usable."""
    if config.OFFLINE:
        f = config.PAGES_DIR / f"{domain}_{page}.txt"
        return (f.read_text(), f"fixture://{f.name}") if f.exists() else ("", None)

    for path in PAGES.get(page, [page]):
        url = f"https://{domain}/{path}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        except requests.RequestException:
            continue
        if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
            text = clean(r.text)
            if len(text) > 200:
                return text, r.url
    return "", None
