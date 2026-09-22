#!/usr/bin/env python3
"""Enrichment Pipeline for Caffeye: Multi-page crawler and qualitative fact extractor
for Metro Atlanta coffee shops, bakeries, and tea houses.

Extracts decision-making facts (laptop policy, Wi-Fi, seating, meeting rooms,
menu highlights, roaster status) with supporting verbatim excerpts, source subpage URLs,
and checked dates. Separates confirmed, unavailable, and unknown facts.
Disambiguates multi-branch websites by physical address/city.

Usage:
    python3 scripts/enrich_places.py --queue
        Generates and prints the balanced 100-venue research queue across 14 counties.
    python3 scripts/enrich_places.py --crawl-batch [--limit N]
        Crawls websites for the queue, caches pages, extracts facts, and stages proposals.
    python3 scripts/enrich_places.py --review
        Reviews staged proposals, checks evidence excerpts, and flags contradictions.
    python3 scripts/enrich_places.py --approve
        Commits verified overlays to scripts/curations.json and facts to scripts/research_facts.json.
    python3 scripts/enrich_places.py --crawl-url <url> [--address <addr>] [--city <city>]
        Inspects a single venue website and prints extracted facts.
"""

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES_PATH = ROOT / "public" / "places.json"
SHOPS_PATH = ROOT / "public" / "shops.json"
CURATIONS_PATH = ROOT / "scripts" / "curations.json"
FACTS_PATH = ROOT / "scripts" / "research_facts.json"
STAGING_PATH = ROOT / "scratch" / "enrichment_staging.json"
CACHE_DIR = ROOT / "scratch" / "crawl_cache"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from refresh_ratings import norm  # noqa: E402
from curate_places import merge_venues, load_curations  # noqa: E402

# County quotas targeting a balanced ~100 venue batch across Metro Atlanta's 14 counties
DEFAULT_COUNTY_QUOTAS = {
    "Fulton": 20,
    "Gwinnett": 15,
    "Cobb": 15,
    "DeKalb": 14,
    "Cherokee": 8,
    "Forsyth": 6,
    "Henry": 5,
    "Hall": 5,
    "Fayette": 3,
    "Coweta": 3,
    "Douglas": 3,
    "Clayton": 3,
    "Dawson": 1,
    "Rockdale": 1,
}

# Major cities/districts in Metro Atlanta for branch isolation
OTHER_MAJOR_CITIES = [
    "alpharetta", "roswell", "duluth", "decatur", "marietta", "smyrna",
    "woodstock", "cumming", "lawrenceville", "suwanee", "buford", "canton",
    "peachtree city", "newnan", "midtown", "buckhead", "inman park", "west end",
    "johns creek", "sandy springs", "dunwoody", "kennesaw", "norcross", "snellville"
]

# Subpage URL keywords of high research value
RELEVANT_PATH_KEYWORDS = [
    "location", "locations", "hours", "visit", "contact", "find-us",
    "menu", "drinks", "coffee", "food", "bakery", "order",
    "about", "story", "faq", "frequently-asked", "policy", "policies", "rules",
    "work", "workspace", "cowork", "study", "remote", "laptop", "wifi", "amenities",
    "meeting", "meetings", "conference", "room", "rent", "rental", "space", "events", "private-events", "booking",
]

# Patterns to skip when discovering internal links
SKIP_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
    ".zip", ".tar", ".gz", ".mp4", ".mp3", ".css", ".js",
}
SKIP_PATH_PATTERNS = [
    re.compile(r"/wp-content/|/cdn-cgi/|/cart|/checkout|/login|/account|/feed|/tag/|/category/|/author/", re.I),
]

DIRECTORY_DOMAINS = {
    "atlantacoffeeshops.com", "menutoeat.com", "facebook.com", "instagram.com",
    "toasttab.com", "yelp.com", "tripadvisor.com"
}

EVENT_PAGE_PATTERNS = [
    re.compile(r"/location-events\b", re.I),
    re.compile(r"/location-scouts\b", re.I),
    re.compile(r"/private-events\b", re.I),
    re.compile(r"/private-dining\b", re.I),
    re.compile(r"/event-rentals?\b", re.I),
    re.compile(r"/venue-rentals?\b", re.I),
    re.compile(r"/private-event-hire\b", re.I),
    re.compile(r"/space-rental\b", re.I),
    re.compile(r"/party-rentals?\b", re.I),
    re.compile(r"/host-your-event\b", re.I),
    re.compile(r"/weddings?\b", re.I),
]

ERROR_CACHE_TTL_SEC = 3600  # 1 hour retry for failed fetches
MAX_CACHE_AGE_DAYS = 14     # 14 days freshness for cached content


# ==============================================================================
# 1. Balanced Queue Generator with Proportional Allocation
# ==============================================================================

def compute_scaled_quotas(base_quotas: dict, target_total: int, available_by_county: dict = None) -> dict:
    """Proportionally scales county quotas so they sum exactly to target_total,
    distributing across diverse counties without tail truncation and capped by candidate availability."""
    if target_total <= 0:
        return {c: 0 for c in base_quotas}

    if available_by_county is None:
        available_by_county = {c: 999999 for c in base_quotas}

    active_counties = [c for c in base_quotas if available_by_county.get(c, 0) > 0]
    if not active_counties:
        return {}

    total_base_weight = sum(base_quotas[c] for c in active_counties)
    if total_base_weight == 0:
        return {}

    alloc = {c: 0 for c in active_counties}
    exact_shares = {
        c: (base_quotas[c] / total_base_weight) * target_total
        for c in active_counties
    }

    rem = target_total
    # When target_total >= number of active counties, give 1 to each active county
    if target_total >= len(active_counties):
        for c in active_counties:
            take = min(1, available_by_county.get(c, 0))
            alloc[c] = take
            rem -= take
    else:
        # For small limits (< len(active_counties)), distribute across distinct counties (at most 1 per county)
        # to maximize geographical diversity across Metro Atlanta
        sorted_counties = sorted(
            active_counties,
            key=lambda c: (exact_shares[c], base_quotas[c]),
            reverse=True
        )
        for c in sorted_counties[:target_total]:
            take = min(1, available_by_county.get(c, 0))
            alloc[c] = take
            rem -= take

    # Distribute remaining quota by highest residual share (exact_shares[c] - alloc[c])
    while rem > 0:
        candidates_to_add = [
            c for c in active_counties
            if alloc[c] < available_by_county.get(c, 0)
        ]
        if not candidates_to_add:
            break
        best_c = max(candidates_to_add, key=lambda c: (exact_shares[c] - alloc[c], base_quotas[c]))
        alloc[best_c] += 1
        rem -= 1

    return alloc


def generate_balanced_queue(places: list, shops: list = None,
                            quotas: dict = None, target_total: int = 100,
                            recheck: bool = False,
                            facts_path: Path = FACTS_PATH,
                            researched_facts: dict = None) -> list:
    """Generates a balanced research queue across all 14 counties.

    Filters to independent venues with valid websites that lack cw qualitative assessments.
    Skips venues already recorded in research_facts.json unless recheck=True.
    Ranks within each county by Bayesian weighted rating.
    """
    if quotas is None:
        quotas = DEFAULT_COUNTY_QUOTAS

    all_venues = merge_venues(places, shops)
    curated = load_curations()

    # Load research ledger to avoid repeating completed research
    researched_pids = set()
    if researched_facts is not None:
        researched_pids = set(researched_facts.keys())
    elif facts_path and Path(facts_path).exists():
        try:
            facts_data = json.loads(Path(facts_path).read_text())
            researched_pids = set(facts_data.get("places", {}).keys())
        except Exception:
            pass

    # Precompute Bayesian rating over the whole population
    rated = [v["rating"] for v in all_venues if isinstance(v.get("rating"), (int, float))]
    mean_rating = sum(rated) / len(rated) if rated else 0.0
    counts = sorted(v.get("ratingNum") or 0 for v in all_venues)
    median_reviews = counts[len(counts) // 2] if counts else 0

    # Group eligible candidates by county
    candidates_by_county = {}
    for v in all_venues:
        pid = v.get("placeId")
        if not pid:
            continue
        # Exclude franchises
        if v.get("model") == "franchise":
            continue
        # Must have a website
        website = (v.get("website") or "").strip()
        if not website or not (website.startswith("http://") or website.startswith("https://")):
            continue
        # Skip if already curated with a tier
        existing_cw = v.get("cw")
        if existing_cw and isinstance(existing_cw, dict) and existing_cw.get("tier"):
            continue
        if pid in curated and (curated[pid].get("cw") or {}).get("tier"):
            continue
        # Deduplicate against research facts ledger unless recheck is requested
        if not recheck and pid in researched_pids:
            continue
        if recheck and pid not in researched_pids:
            continue

        county = v.get("county") or "Unknown"
        votes = v.get("ratingNum") or 0
        r = v.get("rating")
        if not isinstance(r, (int, float)):
            r = mean_rating
        score = (votes * r + median_reviews * mean_rating) / (votes + median_reviews) if (votes + median_reviews) else mean_rating

        cand = {
            "placeId": pid,
            "name": v.get("name"),
            "city": v.get("city"),
            "county": county,
            "address": v.get("address"),
            "website": website,
            "category": v.get("category"),
            "rating": v.get("rating"),
            "ratingNum": v.get("ratingNum", 0),
            "weightedRating": round(score, 4),
        }
        candidates_by_county.setdefault(county, []).append(cand)

    # Sort each county by weightedRating descending
    for county in candidates_by_county:
        candidates_by_county[county].sort(key=lambda c: (c["weightedRating"], c["ratingNum"]), reverse=True)

    available_by_county = {c: len(candidates_by_county.get(c, [])) for c in quotas}
    scaled_quotas = compute_scaled_quotas(quotas, target_total, available_by_county)

    queue = []
    for county, q in scaled_quotas.items():
        if q > 0:
            cands = candidates_by_county.get(county, [])
            queue.extend(cands[:q])

    return queue


# ==============================================================================
# 2. Page Caching & Polite Multi-Page Crawler
# ==============================================================================

def canonicalize_url(url: str) -> str:
    """Strip tracking fragments and query params that don't affect page content."""
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    q_pairs = urllib.parse.parse_qsl(parsed.query)
    clean_q = [
        (k, v) for k, v in q_pairs
        if not k.startswith("utm_") and k not in ("fbclid", "gclid", "ref", "source")
    ]
    query = urllib.parse.urlencode(clean_q)
    return urllib.parse.urlunparse((scheme, netloc, path, "", query, ""))


def cache_key_for_url(url: str) -> str:
    return hashlib.sha256(canonicalize_url(url).encode("utf-8")).hexdigest()


def fetch_page(url: str, timeout: float = 6.0, cache_dir: Path = CACHE_DIR,
               force_refresh: bool = False,
               error_ttl_sec: float = ERROR_CACHE_TTL_SEC,
               max_age_days: float = MAX_CACHE_AGE_DAYS) -> dict:
    """Fetches a URL with disk caching, polite headers, and error retry rules."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    c_key = cache_key_for_url(url)
    c_file = cache_dir / f"{c_key}.json"

    if not force_refresh and c_file.exists():
        try:
            cached = json.loads(c_file.read_text())
            fetched_at_str = cached.get("fetchedAt")
            is_valid = True
            if fetched_at_str:
                try:
                    fetched_dt = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00"))
                    age_sec = (datetime.now(timezone.utc) - fetched_dt).total_seconds()
                    if not cached.get("ok") and age_sec > error_ttl_sec:
                        is_valid = False  # Expire error cache
                    elif cached.get("ok") and age_sec > max_age_days * 86400:
                        is_valid = False  # Expire old content
                except Exception:
                    pass
            if is_valid:
                return cached
        except Exception:
            pass

    if not url.startswith("http"):
        url = "https://" + url

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Caffeye/1.0 ResearchBot"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
    )

    result = {
        "url": url,
        "ok": False,
        "status": 0,
        "content": "",
        "error": None,
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
    }

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result["status"] = resp.status
            content_type = resp.headers.get("Content-Type", "").lower()
            if content_type and "text" not in content_type and "html" not in content_type:
                result["error"] = f"non-html content-type: {content_type}"
                c_file.write_text(json.dumps(result))
                return result
            raw = resp.read(1_500_000)
            result["content"] = raw.decode("utf-8", errors="ignore")
            result["ok"] = True
    except urllib.error.HTTPError as e:
        result["status"] = e.code
        result["error"] = f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        result["error"] = str(e)

    try:
        c_file.write_text(json.dumps(result))
    except Exception:
        pass

    return result


def discover_subpages(homepage_url: str, html: str, max_pages: int = 8) -> list:
    """Parses internal links from HTML and selects high-value subpages."""
    if not html:
        return []

    parsed_home = urllib.parse.urlparse(homepage_url)
    home_domain = parsed_home.netloc.lower().replace("www.", "")

    # Directory/aggregator sites should not have sibling venue pages crawled
    if home_domain in DIRECTORY_DOMAINS:
        return []

    raw_hrefs = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\']', html, re.I)

    scored_urls = {}
    for href in raw_hrefs:
        href = href.strip()
        if not href or href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:"):
            continue

        full_url = urllib.parse.urljoin(homepage_url, href)
        parsed = urllib.parse.urlparse(full_url)
        domain = parsed.netloc.lower().replace("www.", "")

        if domain != home_domain and not domain.endswith("." + home_domain):
            continue

        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
            continue
        if any(p.search(path) for p in SKIP_PATH_PATTERNS):
            continue

        canon = canonicalize_url(full_url)
        if canon == canonicalize_url(homepage_url):
            continue

        score = 0
        for kw in RELEVANT_PATH_KEYWORDS:
            if kw in path:
                if kw in ("meeting", "meetings", "conference", "room", "workspace", "cowork", "laptop", "wifi"):
                    score += 5
                elif kw in ("location", "locations", "hours", "contact"):
                    score += 4
                elif kw in ("menu", "drinks", "coffee", "food"):
                    score += 3
                else:
                    score += 2

        if score > 0:
            scored_urls[canon] = max(scored_urls.get(canon, 0), score)

    sorted_subpages = sorted(scored_urls.items(), key=lambda x: x[1], reverse=True)
    return [url for url, _ in sorted_subpages[:max_pages]]


def crawl_venue_website(url: str, place_meta: dict = None, max_pages: int = 8,
                        cache_dir: Path = CACHE_DIR, pause_sec: float = 0.2,
                        force_refresh: bool = False) -> dict:
    """Crawls venue homepage and prioritized subpages, respecting bounds, caching, and force_refresh."""
    home_res = fetch_page(url, cache_dir=cache_dir, force_refresh=force_refresh)
    pages = {canonicalize_url(url): home_res}

    if not home_res.get("ok"):
        return pages

    subpages = discover_subpages(url, home_res.get("content", ""), max_pages=max_pages)
    for sub_url in subpages:
        if pause_sec > 0:
            time.sleep(pause_sec)
        sub_res = fetch_page(sub_url, cache_dir=cache_dir, force_refresh=force_refresh)
        pages[canonicalize_url(sub_url)] = sub_res

    return pages


# ==============================================================================
# 3. Branch Disambiguation, Section & Table Preservation
# ==============================================================================

def clean_text_from_html(html: str) -> str:
    """Converts HTML into clean plain text with structural whitespace preserved."""
    if not html:
        return ""
    text = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<(p|div|br|li|h[1-6]|tr)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&amp;", "&").replace("&nbsp;", " ").replace("&#39;", "'").replace("&quot;", '"')
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(l for l in lines if l)


def extract_sentences(text: str) -> list:
    """Splits cleaned text into distinct sentence-level candidate excerpts."""
    raw_chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    sentences = []
    for c in raw_chunks:
        clean = c.strip()
        if len(clean) >= 5 and len(clean) <= 300:
            sentences.append(clean)
    return sentences


def extract_table_facts(html: str, target_city: str = "", address: str = "") -> list:
    """Extracts text from HTML tables, matching columns to the target venue location."""
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.I | re.S)
    results = []
    target_city_norm = norm(target_city or "")
    street_num = ""
    num_match = re.search(r"^\d+", address or "")
    if num_match:
        street_num = num_match.group(0)

    for table_html in tables:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.I | re.S)
        if not rows:
            continue
        parsed_rows = []
        for r in rows:
            cells = re.findall(r"<(?:td|th)[^>]*>(.*?)</(?:td|th)>", r, re.I | re.S)
            cleaned_cells = [
                re.sub(r"<[^>]+>", " ", c).replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'").strip()
                for c in cells
            ]
            if any(cleaned_cells):
                parsed_rows.append(cleaned_cells)
        if len(parsed_rows) < 2:
            continue

        target_col_idx = None
        for r_idx, r in enumerate(parsed_rows[:3]):
            for c_idx, cell in enumerate(r):
                cell_norm = norm(cell)
                if target_city_norm and target_city_norm in cell_norm:
                    target_col_idx = c_idx
                    break
                if street_num and street_num in cell_norm:
                    target_col_idx = c_idx
                    break
            if target_col_idx is not None:
                break

        if target_col_idx is not None:
            for r in parsed_rows[r_idx + 1:]:
                if len(r) > target_col_idx:
                    label = r[0] if len(r) > 1 and target_col_idx > 0 else ""
                    val = r[target_col_idx]
                    if val and val.lower() not in ("yes", "no"):
                        results.append(f"{label}: {val}" if label else val)
                    elif val:
                        results.append(f"{label}: {val}")
    return results


def extract_location_scoped_sentences(html: str, target_city: str, address: str = "") -> list:
    """Extracts candidate sentences from HTML while isolating sections/tables
    that belong to different branches."""
    target_city_norm = norm(target_city or "")
    street_num = ""
    num_match = re.search(r"^\d+", address or "")
    if num_match:
        street_num = num_match.group(0)

    # 1. Extract table facts matching this location
    table_lines = extract_table_facts(html, target_city)

    # 2. Remove <table>...</table> to avoid flattening cross-column text
    clean_html = re.sub(r"<table[^>]*>.*?</table>", " ", html, flags=re.I | re.S)

    # 3. Split HTML by structural sections (headings, section, article)
    section_chunks = re.split(r"(<h[1-6][^>]*>|<section[^>]*>|<article[^>]*>)", clean_html, flags=re.I)

    current_section_ok = True
    all_sentences = []

    for l in table_lines:
        for sent in extract_sentences(l):
            all_sentences.append(sent)

    for chunk in section_chunks:
        chunk_text = clean_text_from_html(chunk)
        if not chunk_text:
            continue
        chunk_norm = norm(chunk_text)

        mentions_target = (target_city_norm and target_city_norm in chunk_norm) or (street_num and street_num in chunk_norm)
        mentions_other = any(
            re.search(r"\b" + re.escape(oc) + r"\b", chunk_norm)
            for oc in OTHER_MAJOR_CITIES if oc != target_city_norm
        )

        if mentions_other and not mentions_target and len(chunk_text) < 150:
            current_section_ok = False
            continue
        elif mentions_target and len(chunk_text) < 150:
            current_section_ok = True

        if not current_section_ok and mentions_other and not mentions_target:
            continue

        for sent in extract_sentences(chunk_text):
            s_norm = norm(sent)
            # Skip sentences that explicitly name another branch without mentioning our city
            if target_city_norm and target_city_norm not in s_norm:
                if any(re.search(r"\b" + re.escape(oc) + r"\b", s_norm) for oc in OTHER_MAJOR_CITIES if oc != target_city_norm):
                    continue
            all_sentences.append(sent)

    return all_sentences


def match_branch_pages(pages: dict, address: str, city: str) -> dict:
    """Examines crawled pages and tags them as branch_match (True/False).

    Filters out subpages dedicated to other branches based on URL path and content.
    """
    addr_norm = norm(address or "")
    city_norm = norm(city or "")
    street_num = ""
    num_match = re.search(r"^\d+", address or "")
    if num_match:
        street_num = num_match.group(0)

    tagged_pages = {}
    for page_url, p_data in pages.items():
        if not p_data.get("ok"):
            tagged_pages[page_url] = {"data": p_data, "branch_match": False, "is_location_page": False}
            continue

        text = clean_text_from_html(p_data.get("content", ""))
        text_norm = norm(text)
        path = urllib.parse.urlparse(page_url).path.lower()

        # Check if URL explicitly points to another city/locality
        url_mentions_other = any(
            re.search(r"\b" + re.escape(oc) + r"\b", path)
            for oc in OTHER_MAJOR_CITIES if oc != city_norm
        )
        url_mentions_target = city_norm and (city_norm in path)

        if url_mentions_other and not url_mentions_target:
            tagged_pages[page_url] = {"data": p_data, "branch_match": False, "is_location_page": True}
            continue

        is_loc = any(kw in path for kw in ("location", "locations", "contact", "visit", "stores", "about"))
        mentions_other_in_text = any(
            re.search(r"\b" + re.escape(oc) + r"\b", text_norm)
            for oc in OTHER_MAJOR_CITIES if oc != city_norm
        )
        matches_us = (city_norm and city_norm in text_norm) or (street_num and street_num in text_norm)

        if is_loc and mentions_other_in_text and not matches_us:
            tagged_pages[page_url] = {"data": p_data, "branch_match": False, "is_location_page": True}
        else:
            tagged_pages[page_url] = {"data": p_data, "branch_match": True, "is_location_page": is_loc}

    return tagged_pages


def is_event_rental_page(url: str, html: str = "") -> bool:
    """Detects pages dedicated to private event venue / banquet / party rentals."""
    path = urllib.parse.urlparse(url).path.lower()
    if any(p.search(path) for p in EVENT_PAGE_PATTERNS):
        return True
    if html:
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        if title_match:
            title = title_match.group(1).lower()
            if any(w in title for w in ("host your event", "private event venue", "wedding venue", "venue rental", "party buyout")):
                return True
    return False


# ==============================================================================
# 4. Tri-State Evidence & Fact Extractor with Negation Guards
# ==============================================================================

PATTERNS_LAPTOP_NEGATIVE = [
    re.compile(r"\bno\s+(?:laptops?|screens?|computers?)\b", re.I),
    re.compile(r"\blaptops?\s+(?:are\s+)?(?:not\s+allowed|prohibited|forbidden|restricted)\b", re.I),
    re.compile(r"\blaptop[- ]free\b", re.I),
    re.compile(r"\bno\s+screens\s+on\s+weekends\b", re.I),
    re.compile(r"\bno\s+(?:working|studying)\s+on\s+weekends\b", re.I),
    re.compile(r"\b(?:put|turn)\s+away\s+(?:your\s+)?laptops?\b", re.I),
]

PATTERNS_LAPTOP_POSITIVE = [
    re.compile(r"\b(?:laptops?|studying|remote\s+work)\s+(?:are\s+)?(?:welcome|encouraged|allowed|permitted)\b", re.I),
    re.compile(r"\b(?:laptop|work|study)[- ]friendly\b", re.I),
    re.compile(r"\bdesignated\s+laptop\s+(?:tables?|areas?|bar)\b", re.I),
    re.compile(r"\bplenty\s+of\s+space\s+(?:for|to)\s+(?:work|study|laptops)\b", re.I),
    re.compile(r"\bperfect\s+(?:spot|place)\s+(?:for\s+studying|to\s+work)\b", re.I),
    re.compile(r"\bbuilt\s+for\s+coworking\b", re.I),
]

PATTERNS_WIFI_NEGATIVE = [
    re.compile(r"\bno\s+wi[- ]?fi\b", re.I),
    re.compile(r"\bwi[- ]?fi[- ]free\b", re.I),
    re.compile(r"\bwe\s+do\s+not\s+(?:have|offer|provide)\s+wi[- ]?fi\b", re.I),
    re.compile(r"\bunplug\s+(?:and|to)\s+connect\b", re.I),
]

PATTERNS_WIFI_POSITIVE = [
    re.compile(r"\b(?:free|complimentary|guest|high[- ]speed|fast)\s+wi[- ]?fi\b", re.I),
    re.compile(r"\bwi[- ]?fi\s+(?:is\s+)?(?:available|free|complimentary|provided|fast|access)\b", re.I),
    re.compile(r"^\s*free\s+wi[- ]?fi\s*$", re.I),
    re.compile(r"\baccess\s+(?:free\s+)?wi[- ]?fi\b", re.I),
]

PATTERNS_OUTLETS_POSITIVE = [
    re.compile(r"\b(?:power\s+)?outlets?\s+(?:at\s+(?:every|all|most)\s+tables?|available|throughout)\b", re.I),
    re.compile(r"\bcharging\s+stations?\b", re.I),
    re.compile(r"\bplenty\s+of\s+(?:power\s+)?outlets?\b", re.I),
]

PATTERNS_SEATING_POSITIVE = [
    re.compile(r"\b(communal\s+tables?|community\s+tables?|spacious\s+(?:indoor\s+)?seating|outdoor\s+patio|indoor\s+(?:and\s+)?outdoor\s+seating|covered\s+patio|patio\s+seating|enclosed\s+patio|picnic\s+benches|comfortable\s+booths?|bar\s+seating|large\s+tables?|zen\s+garden\s+seating)\b", re.I),
]

PATTERNS_MEETING_NEGATIVE = [
    re.compile(r"\b(?:we\s+)?(?:do\s+not|don['’]t)\s+have\s+(?:a\s+)?(?:meeting|conference|board|study|seminar)\s*(?:room|space|hall)\b", re.I),
    re.compile(r"\bno\s+(?:meeting|conference|board|study|seminar)\s*(?:room|space|hall)s?\b", re.I),
    re.compile(r"\b(?:meeting|conference|board|study|seminar)\s*(?:room|space|hall)s?\s+(?:are\s+)?(?:not\s+available|unavailable|not\s+offered|do\s+not\s+exist)\b", re.I),
    re.compile(r"\bwithout\s+(?:a\s+)?(?:meeting|conference|board|study)\s*(?:room|space)\b", re.I),
]

PATTERNS_MEETING_POSITIVE = [
    re.compile(r"\b(?:private\s+)?(?:meeting|conference|board|study|seminar)\s*(?:room|space|hall)\b", re.I),
    re.compile(r"\b(?:reservable|reserve|rent|book)\s+(?:a\s+)?(?:meeting\s+room|conference\s+room|study\s+room|private\s+room)\b", re.I),
    re.compile(r"\bbook\s+(?:our|the)\s+(?:conference|meeting)\s+room\b", re.I),
]

PATTERNS_ROASTER = [
    re.compile(r"\b(?:roast(?:ed)?\s+in[- ]house|in[- ]house\s+roast(?:ing|er)?|we\s+roast\s+our\s+own|house[- ]roasted|our\s+own\s+roast(?:s|ing)?|on[- ]site\s+roast(?:ing|ery)?|micro[- ]roaster(?:y)?)\b", re.I),
]


def extract_facts(pages: dict, address: str = "", city: str = "") -> dict:
    """Extracts structured facts as confirmed, unavailable, or unknown with supporting excerpts,
    guarded against negation and multi-match policy conflicts."""
    tagged = match_branch_pages(pages, address, city)
    now_str = datetime.now(timezone.utc).strftime("%B %Y")

    facts = {
        "laptopPolicy": {"status": "unknown"},
        "wifi": {"status": "unknown"},
        "outlets": {"status": "unknown"},
        "seating": {"status": "unknown"},
        "meetingRoom": {"status": "unknown"},
        "roaster": {"status": "unknown"},
        "menuHighlights": [],
        "hoursMention": None,
    }

    laptop_candidates = []
    wifi_candidates = []
    outlet_candidates = []
    seating_candidates = []
    meeting_candidates = []
    roaster_candidates = []

    for page_url, p_info in tagged.items():
        if not p_info.get("branch_match"):
            continue
        p_data = p_info["data"]
        raw_content = p_data.get("content", "")
        fetched_at = p_data.get("fetchedAt")
        date_str = now_str
        if fetched_at:
            try:
                date_str = datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).strftime("%B %Y")
            except Exception:
                pass

        is_event_page = is_event_rental_page(page_url, raw_content)
        sentences = extract_location_scoped_sentences(raw_content, city, address)

        for sent in sentences:
            # Laptop Policy (exclude event hall rental pages)
            if not is_event_page:
                if any(p.search(sent) for p in PATTERNS_LAPTOP_NEGATIVE):
                    laptop_candidates.append(("unavailable", sent, page_url, date_str))
                elif any(p.search(sent) for p in PATTERNS_LAPTOP_POSITIVE):
                    laptop_candidates.append(("confirmed", sent, page_url, date_str))

            # Wi-Fi (exclude event hall rental pages)
            if not is_event_page:
                if any(p.search(sent) for p in PATTERNS_WIFI_NEGATIVE):
                    wifi_candidates.append(("unavailable", sent, page_url, date_str))
                elif any(p.search(sent) for p in PATTERNS_WIFI_POSITIVE):
                    wifi_candidates.append(("confirmed", sent, page_url, date_str))

            # Outlets
            if not is_event_page:
                if any(p.search(sent) for p in PATTERNS_OUTLETS_POSITIVE):
                    outlet_candidates.append(("confirmed", sent, page_url, date_str))

            # Seating
            if not is_event_page:
                if any(p.search(sent) for p in PATTERNS_SEATING_POSITIVE):
                    seating_candidates.append(("confirmed", sent, page_url, date_str))

            # Meeting Room: check negation first, then positive.
            # Private party mentions do NOT make meeting room unavailable; absence remains unknown.
            if any(p.search(sent) for p in PATTERNS_MEETING_NEGATIVE):
                meeting_candidates.append(("unavailable", sent, page_url, date_str))
            elif any(p.search(sent) for p in PATTERNS_MEETING_POSITIVE):
                meeting_candidates.append(("confirmed", sent, page_url, date_str))

            # Roaster status
            if any(p.search(sent) for p in PATTERNS_ROASTER):
                roaster_candidates.append(("confirmed", sent, page_url, date_str))

        # Menu Highlights from menu pages
        path = urllib.parse.urlparse(page_url).path.lower()
        if "menu" in path or "drink" in path or "coffee" in path or "food" in path:
            text = clean_text_from_html(raw_content)
            spec_matches = re.findall(r"(?:signature|house\s+special|featured|specialty):\s*([A-Za-z0-9\s&'-]{3,40})", text, re.I)
            for m in spec_matches:
                clean_item = m.strip()
                if len(clean_item) >= 3 and clean_item not in facts["menuHighlights"]:
                    facts["menuHighlights"].append(clean_item)

    # Multi-candidate resolution:
    # 1. Laptop policy: Specific negative restrictions override general positive statements
    unavail_laptop = [c for c in laptop_candidates if c[0] == "unavailable"]
    conf_laptop = [c for c in laptop_candidates if c[0] == "confirmed"]
    if unavail_laptop:
        st, sent, url, dt = unavail_laptop[0]
        facts["laptopPolicy"] = {"status": "unavailable", "excerpt": sent, "sourceUrl": url, "checkedDate": dt}
    elif conf_laptop:
        st, sent, url, dt = conf_laptop[0]
        facts["laptopPolicy"] = {"status": "confirmed", "excerpt": sent, "sourceUrl": url, "checkedDate": dt}

    # 2. Wi-Fi
    unavail_wifi = [c for c in wifi_candidates if c[0] == "unavailable"]
    conf_wifi = [c for c in wifi_candidates if c[0] == "confirmed"]
    if unavail_wifi:
        st, sent, url, dt = unavail_wifi[0]
        facts["wifi"] = {"status": "unavailable", "excerpt": sent, "sourceUrl": url, "checkedDate": dt}
    elif conf_wifi:
        st, sent, url, dt = conf_wifi[0]
        facts["wifi"] = {"status": "confirmed", "excerpt": sent, "sourceUrl": url, "checkedDate": dt}

    # 3. Outlets
    if outlet_candidates:
        st, sent, url, dt = outlet_candidates[0]
        facts["outlets"] = {"status": "confirmed", "excerpt": sent, "sourceUrl": url, "checkedDate": dt}

    # 4. Seating
    if seating_candidates:
        st, sent, url, dt = seating_candidates[0]
        facts["seating"] = {"status": "confirmed", "excerpt": sent, "sourceUrl": url, "checkedDate": dt}

    # 5. Meeting Room: Negation wins; absence stays unknown
    unavail_mr = [c for c in meeting_candidates if c[0] == "unavailable"]
    conf_mr = [c for c in meeting_candidates if c[0] == "confirmed"]
    if unavail_mr:
        st, sent, url, dt = unavail_mr[0]
        facts["meetingRoom"] = {"status": "unavailable", "excerpt": sent, "sourceUrl": url, "checkedDate": dt}
    elif conf_mr:
        st, sent, url, dt = conf_mr[0]
        facts["meetingRoom"] = {"status": "confirmed", "excerpt": sent, "sourceUrl": url, "checkedDate": dt}

    # 6. Roaster
    if roaster_candidates:
        st, sent, url, dt = roaster_candidates[0]
        facts["roaster"] = {"status": "confirmed", "excerpt": sent, "sourceUrl": url, "checkedDate": dt}

    return facts


# ==============================================================================
# 5. Derivation of Curation Overlays & Contradiction Detection
# ==============================================================================

def derive_curation_overlay(facts: dict, place_meta: dict) -> dict:
    """Derives grounded curation overlay (cw, usp, category, menu items).

    Guarantees:
    - Only true coworking or confirmed meeting room receives 'excellent'.
    - Unknown meeting room is preserved as unknown/omitted (never false).
    - No unevidenced 'comfortable seating' claims.
    - Third-party directories receive third-party source attribution.
    """
    website = place_meta.get("website", "")
    domain = urllib.parse.urlparse(website).netloc.lower().replace("www.", "")
    source = "website-crawl"
    if domain in DIRECTORY_DOMAINS:
        source = f"{domain.split('.')[0]}-directory"
        if "atlantacoffeeshops" in domain:
            source = "atlanta-coffee-shops-directory"

    overlay = {
        "name": place_meta.get("name"),
        "city": place_meta.get("city"),
        "county": place_meta.get("county"),
        "source": source,
        "verified": "September 2026",
    }

    lp = facts.get("laptopPolicy", {})
    wifi = facts.get("wifi", {})
    mr = facts.get("meetingRoom", {})
    seating = facts.get("seating", {})
    roaster = facts.get("roaster", {})

    cw = None

    # Case A: Explicit restriction
    if lp.get("status") == "unavailable" or wifi.get("status") == "unavailable":
        note = lp.get("excerpt") or wifi.get("excerpt") or "Laptop use or Wi-Fi restricted per venue policy."
        cw = {
            "tier": "limited",
            "note": note,
            "source": source,
            "verified": lp.get("checkedDate") or wifi.get("checkedDate") or "September 2026",
        }
        if mr.get("status") == "unavailable":
            cw["hasMeetingRoom"] = False
        elif mr.get("status") == "confirmed":
            cw["hasMeetingRoom"] = True
            cw["meetingRoomNote"] = mr.get("excerpt")

    # Case B: Confirmed reservable meeting room -> excellent
    elif mr.get("status") == "confirmed":
        note = "Work-friendly space with reservable meeting room."
        if wifi.get("status") == "confirmed":
            note = "Features verified Wi-Fi and reservable meeting space."
        cw = {
            "tier": "excellent",
            "note": note,
            "hasMeetingRoom": True,
            "meetingRoomNote": mr.get("excerpt", "Reservable meeting space available."),
            "source": source,
            "verified": mr.get("checkedDate") or "September 2026",
        }

    # Case C: Confirmed laptop-friendly AND confirmed Wi-Fi
    elif wifi.get("status") == "confirmed" and lp.get("status") == "confirmed":
        w_ex = wifi.get("excerpt", "").strip()
        l_ex = lp.get("excerpt", "").strip()
        note = f"Verified work-friendly spot: {l_ex}" if l_ex else f"Verified work-friendly spot: {w_ex}"
        is_dedicated_cowork = any(
            re.search(r"\b(built\s+for\s+coworking|coworking\s+space|dedicated\s+(?:work\s+)?desks?)\b", ex, re.I)
            for ex in (w_ex, l_ex)
        )
        tier = "excellent" if is_dedicated_cowork else "good"
        cw = {
            "tier": tier,
            "note": note,
            "source": source,
            "verified": wifi.get("checkedDate") or lp.get("checkedDate") or "September 2026",
        }
        if mr.get("status") == "unavailable":
            cw["hasMeetingRoom"] = False

    # Case D: Confirmed Wi-Fi or confirmed laptop policy (patio, tables, general study)
    elif wifi.get("status") == "confirmed" or lp.get("status") == "confirmed":
        note = wifi.get("excerpt") or lp.get("excerpt") or "Verified guest Wi-Fi available for patrons."
        if seating.get("status") == "confirmed" and wifi.get("status") == "confirmed":
            s_ex = seating.get("excerpt", "").strip()
            w_ex = wifi.get("excerpt", "").strip()
            if s_ex and s_ex != w_ex:
                note = f"{w_ex} ({s_ex})"
        cw = {
            "tier": "good",
            "note": note,
            "source": source,
            "verified": wifi.get("checkedDate") or lp.get("checkedDate") or "September 2026",
        }
        if mr.get("status") == "unavailable":
            cw["hasMeetingRoom"] = False

    # Case E: Only meeting room unavailable is verified
    elif mr.get("status") == "unavailable":
        cw = {
            "hasMeetingRoom": False,
            "source": source,
            "verified": mr.get("checkedDate") or "September 2026",
        }

    if cw:
        overlay["cw"] = cw

    # Roasters
    is_roastery_name = "roast" in place_meta.get("name", "").lower()
    if (roaster.get("status") == "confirmed" or is_roastery_name) and place_meta.get("category") in ("Coffee", "Specialty"):
        overlay["category"] = "Roasters"

    name = place_meta.get("name", "Local venue")
    city = place_meta.get("city", "Metro Atlanta")
    cat = overlay.get("category") or place_meta.get("category", "Cafe")

    # Check if text explicitly evidenced comfortable seating
    has_explicit_comfort = False
    for ex in [seating.get("excerpt", ""), wifi.get("excerpt", ""), lp.get("excerpt", "")]:
        if re.search(r"\bcomfortable\s+seating\b", ex, re.I):
            has_explicit_comfort = True
            break

    if roaster.get("status") == "confirmed":
        overlay["usp"] = f"Independent craft coffee roaster in {city} offering house-roasted specialty coffee."
    elif cw and cw.get("hasMeetingRoom"):
        overlay["usp"] = f"Community {cat.lower()} in {city} featuring reservable meeting space and craft beverages."
    elif cw and cw.get("tier") == "excellent":
        seating_str = "comfortable seating" if has_explicit_comfort else "study-friendly space"
        overlay["usp"] = f"Work-friendly {cat.lower()} in {city} with verified Wi-Fi and {seating_str}."
    elif cw and cw.get("tier") == "good":
        overlay["usp"] = f"Independent {cat.lower()} in {city} with verified guest Wi-Fi and specialty coffee."
    else:
        overlay["usp"] = f"Independent {cat.lower()} in {city} serving specialty coffee and fresh menu offerings."

    highlights = facts.get("menuHighlights", [])
    if highlights:
        overlay["loved"] = highlights[:3]
        if len(highlights) >= 1:
            overlay["signature"] = highlights[0]

    return overlay


def detect_contradictions(proposed: dict, existing: dict) -> list:
    """Flags conflicts between newly crawled findings and existing curated records."""
    contradictions = []
    if not existing:
        return contradictions

    prop_cw = proposed.get("cw") or {}
    exist_cw = existing.get("cw") or {}

    if exist_cw.get("hasMeetingRoom") is True and prop_cw.get("hasMeetingRoom") is False:
        contradictions.append(
            "Meeting room conflict: existing record has hasMeetingRoom=True, but crawl indicates no meeting room."
        )

    if exist_cw.get("tier") == "excellent" and prop_cw.get("tier") == "limited":
        contradictions.append(
            f"Tier downgrade conflict: existing tier is 'excellent', but crawl detected restricted policy: {prop_cw.get('note')}"
        )

    return contradictions


def field_preserving_merge(existing: dict, prop: dict) -> dict:
    """Merges proposed crawl data into an existing curation without clobbering editorial fields."""
    merged = dict(existing)
    if prop.get("category") == "Roasters":
        merged["category"] = "Roasters"
    if prop.get("loved") and not merged.get("loved"):
        merged["loved"] = prop["loved"]
    if prop.get("signature") and not merged.get("signature"):
        merged["signature"] = prop["signature"]
    if prop.get("usp") and not merged.get("usp"):
        merged["usp"] = prop["usp"]

    if prop.get("cw"):
        exist_cw = merged.get("cw") or {}
        merged_cw = dict(exist_cw)
        for k, v in prop["cw"].items():
            # Don't clobber confirmed meeting rooms unless explicitly verified unavailable
            if k == "hasMeetingRoom" and exist_cw.get("hasMeetingRoom") is True and v is not True:
                continue
            merged_cw[k] = v
        merged["cw"] = merged_cw

    if prop.get("source"):
        merged["source"] = prop["source"]
    if prop.get("verified"):
        merged["verified"] = prop["verified"]
    return merged


# ==============================================================================
# 6. Pipeline CLI Actions
# ==============================================================================

def cmd_queue(args) -> int:
    places_data = json.loads(PLACES_PATH.read_text())
    shops_data = json.loads(SHOPS_PATH.read_text())
    recheck = getattr(args, "recheck", False)
    queue = generate_balanced_queue(
        places_data["places"],
        shops_data.get("shops", []),
        target_total=args.limit,
        recheck=recheck
    )

    mode_str = "RECHECK" if recheck else "NEW RESEARCH"
    print(f"=== BALANCED QUEUE ({len(queue)} venues, Mode: {mode_str}) ===")
    county_counts = Counter(c["county"] for c in queue)
    for county, count in sorted(county_counts.items()):
        print(f"  {county:12s}: {count:2d} venues")

    if args.json:
        print(json.dumps(queue, indent=2, ensure_ascii=False))
    return 0


def cmd_crawl_batch(args) -> int:
    places_data = json.loads(PLACES_PATH.read_text())
    shops_data = json.loads(SHOPS_PATH.read_text())
    force_refresh = getattr(args, "force_refresh", False)
    recheck = getattr(args, "recheck", False)

    queue = generate_balanced_queue(
        places_data["places"],
        shops_data.get("shops", []),
        target_total=args.limit,
        recheck=recheck
    )

    print(f"Crawling {len(queue)} venues (cache: {CACHE_DIR}, force_refresh={force_refresh})...")
    staged = {}
    facts_repo = {}
    if FACTS_PATH.exists():
        try:
            facts_repo = json.loads(FACTS_PATH.read_text()).get("places", {})
        except Exception:
            pass

    curated = load_curations()
    contradiction_count = 0

    for i, venue in enumerate(queue, 1):
        pid = venue["placeId"]
        name = venue["name"]
        website = venue["website"]
        addr = venue.get("address", "")
        city = venue.get("city", "")

        print(f"[{i:3d}/{len(queue):3d}] {name} ({city}, {venue.get('county')}) -> {website}")
        pages = crawl_venue_website(
            website, venue, max_pages=6, cache_dir=CACHE_DIR,
            pause_sec=args.pause, force_refresh=force_refresh
        )
        facts = extract_facts(pages, address=addr, city=city)

        overlay = derive_curation_overlay(facts, venue)
        contradictions = detect_contradictions(overlay, curated.get(pid, {}))
        if contradictions:
            contradiction_count += len(contradictions)
            for c in contradictions:
                print(f"  ⚠ {c}")

        page_fetches = [
            {
                "url": p_info.get("url", u),
                "status": p_info.get("status", 0),
                "ok": p_info.get("ok", False),
                "fetchedAt": p_info.get("fetchedAt"),
                "error": p_info.get("error"),
            }
            for u, p_info in pages.items()
        ]

        now_iso = datetime.now(timezone.utc).isoformat()
        earliest_fetch = min((p.get("fetchedAt") for p in pages.values() if p.get("fetchedAt")), default=now_iso)

        staged[pid] = {
            "venue": venue,
            "facts": facts,
            "proposed": overlay,
            "contradictions": contradictions,
            "hasContradictions": bool(contradictions),
            "status": "pending",
            "pagesCrawled": list(pages.keys()),
            "pageFetches": page_fetches,
            "fetchedAt": earliest_fetch,
            "extractedAt": now_iso,
        }

        facts_repo[pid] = {
            "name": name,
            "city": city,
            "county": venue.get("county"),
            "website": website,
            "pagesChecked": list(pages.keys()),
            "pageFetches": page_fetches,
            "checkedDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "fetchedAt": earliest_fetch,
            "extractedAt": now_iso,
            "reviewedAt": None,
            "facts": facts,
        }

    STAGING_PATH.parent.mkdir(parents=True, exist_ok=True)
    STAGING_PATH.write_text(json.dumps(staged, indent=2, ensure_ascii=False) + "\n")
    print(f"\nStaged {len(staged)} proposals to {STAGING_PATH}")
    if contradiction_count > 0:
        print(f"Flagged {contradiction_count} contradictions for review.")
    return 0


def cmd_review(args) -> int:
    if not STAGING_PATH.exists():
        print(f"No staging file found at {STAGING_PATH}. Run --crawl-batch first.")
        return 1

    staged = json.loads(STAGING_PATH.read_text())
    print(f"=== REVIEWING {len(staged)} STAGED PROPOSALS ===")

    cw_tiers = Counter()
    meeting_rooms = 0
    restricted = 0
    contradictions = 0

    for pid, entry in staged.items():
        prop = entry.get("proposed", {})
        cw = prop.get("cw")
        if cw:
            tier = cw.get("tier")
            if tier:
                cw_tiers[tier] += 1
            if cw.get("hasMeetingRoom"):
                meeting_rooms += 1
            if tier == "limited":
                restricted += 1
        if entry.get("contradictions"):
            contradictions += len(entry["contradictions"])

    print("Summary of findings:")
    print(f"  Work-Friendly (excellent/good): {cw_tiers.get('excellent', 0) + cw_tiers.get('good', 0)}")
    print(f"    - Excellent: {cw_tiers.get('excellent', 0)}")
    print(f"    - Good:      {cw_tiers.get('good', 0)}")
    print(f"    - Limited / Restricted: {cw_tiers.get('limited', 0)}")
    print(f"  Verified Meeting Rooms: {meeting_rooms}")
    print(f"  Contradictions flagged: {contradictions}")

    if args.verbose:
        for pid, entry in staged.items():
            venue = entry["venue"]
            prop = entry["proposed"]
            cw = prop.get("cw") or {}
            print(f"\n{venue['name']} ({venue['city']}, {venue['county']})")
            if cw.get("tier"):
                print(f"  Tier: {cw.get('tier')} | Note: {cw.get('note')}")
            if cw.get("hasMeetingRoom"):
                print(f"  Meeting room: {cw.get('meetingRoomNote')}")
            if prop.get("loved"):
                print(f"  Menu: {prop.get('loved')}")
            if entry.get("contradictions"):
                for c in entry["contradictions"]:
                    print(f"  ⚠ {c}")
    return 0


def cmd_approve(args) -> int:
    if not STAGING_PATH.exists():
        print(f"No staging file found at {STAGING_PATH}. Run --crawl-batch first.")
        return 1

    staged = json.loads(STAGING_PATH.read_text())
    curations_data = json.loads(CURATIONS_PATH.read_text())
    places_cur = curations_data.setdefault("places", {})

    facts_repo = {}
    if FACTS_PATH.exists():
        try:
            facts_repo = json.loads(FACTS_PATH.read_text()).get("places", {})
        except Exception:
            pass

    allow_contradictions = getattr(args, "allow_contradictions", False)
    target_pid = getattr(args, "pid", None)

    committed = 0
    skipped_contradictions = 0

    for pid, entry in staged.items():
        if target_pid and pid != target_pid:
            continue

        prop = entry.get("proposed")
        contradictions = entry.get("contradictions", [])
        if contradictions and not allow_contradictions:
            print(f"Skipping {pid} ({entry['venue']['name']}): unresolved contradictions ({len(contradictions)}). Use --allow-contradictions to override.")
            skipped_contradictions += 1
            continue

        # Persist to facts repo with separate reviewedAt timestamp
        facts_entry = facts_repo.setdefault(pid, {})
        facts_entry.update({
            "name": entry["venue"]["name"],
            "city": entry["venue"]["city"],
            "county": entry["venue"]["county"],
            "website": entry["venue"]["website"],
            "pagesChecked": entry.get("pagesCrawled", []),
            "pageFetches": entry.get("pageFetches", []),
            "checkedDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "fetchedAt": entry.get("fetchedAt"),
            "extractedAt": entry.get("extractedAt"),
            "reviewedAt": datetime.now(timezone.utc).isoformat(),
            "facts": entry.get("facts", {}),
        })

        has_curation = bool(
            prop and (
                prop.get("cw")
                or prop.get("loved")
                or prop.get("signature")
                or prop.get("category") == "Roasters"
            )
        )
        if has_curation:
            if pid in places_cur:
                places_cur[pid] = field_preserving_merge(places_cur[pid], prop)
            else:
                places_cur[pid] = prop

            committed += 1

    CURATIONS_PATH.write_text(json.dumps(curations_data, indent=2, ensure_ascii=False) + "\n")
    FACTS_PATH.write_text(json.dumps({
        "version": 1,
        "description": "Evidence-backed research facts extracted from venue websites",
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "places": facts_repo,
    }, indent=2, ensure_ascii=False) + "\n")

    print(f"Committed {committed} overlays to {CURATIONS_PATH}")
    if skipped_contradictions > 0:
        print(f"Skipped {skipped_contradictions} venues due to unresolved contradictions.")
    print(f"Persisted facts for {len(facts_repo)} venues to {FACTS_PATH}")
    print("Now run: python3 scripts/curate_places.py --apply")
    return 0


def cmd_crawl_url(args) -> int:
    force_refresh = getattr(args, "force_refresh", False)
    pages = crawl_venue_website(
        args.crawl_url,
        max_pages=8,
        cache_dir=CACHE_DIR,
        force_refresh=force_refresh
    )
    facts = extract_facts(pages, address=args.address or "", city=args.city or "")
    overlay = derive_curation_overlay(facts, {
        "name": "Test Venue",
        "city": args.city or "Atlanta",
        "website": args.crawl_url,
    })
    print(json.dumps({
        "url": args.crawl_url,
        "pagesCrawled": list(pages.keys()),
        "facts": facts,
        "derivedOverlay": overlay,
    }, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queue", action="store_true", help="Print balanced research queue")
    parser.add_argument("--limit", type=int, default=100, help="Total venues in queue (default: 100)")
    parser.add_argument("--recheck", action="store_true", help="Select venues that already exist in research facts ledger for rechecking")
    parser.add_argument("--json", action="store_true", help="Output queue as JSON")
    parser.add_argument("--crawl-batch", action="store_true", help="Crawl websites and stage proposals")
    parser.add_argument("--pause", type=float, default=0.2, help="Pause between page requests (default: 0.2s)")
    parser.add_argument("--force-refresh", action="store_true", help="Force re-fetching cached pages")
    parser.add_argument("--review", action="store_true", help="Review staged proposals")
    parser.add_argument("--verbose", action="store_true", help="Detailed review breakdown")
    parser.add_argument("--approve", action="store_true", help="Commit staged proposals to curations.json and research_facts.json")
    parser.add_argument("--allow-contradictions", action="store_true", help="Allow committing entries with unresolved contradictions")
    parser.add_argument("--pid", type=str, default=None, help="Target specific placeId for approval")
    parser.add_argument("--crawl-url", type=str, default="", help="Crawl single URL and extract facts")
    parser.add_argument("--address", type=str, default="", help="Address for single URL crawl")
    parser.add_argument("--city", type=str, default="", help="City for single URL crawl")
    args = parser.parse_args()

    if args.queue:
        return cmd_queue(args)
    if args.crawl_batch:
        return cmd_crawl_batch(args)
    if args.review:
        return cmd_review(args)
    if args.approve:
        return cmd_approve(args)
    if args.crawl_url:
        return cmd_crawl_url(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
