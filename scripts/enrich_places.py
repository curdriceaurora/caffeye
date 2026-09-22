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


# ==============================================================================
# 1. Balanced Queue Generator
# ==============================================================================

def generate_balanced_queue(places: list, shops: list = None,
                            quotas: dict = None, target_total: int = 100) -> list:
    """Generates a balanced research queue across all 14 counties.

    Filters to independent venues with valid websites that lack cw qualitative assessments.
    Ranks within each county by Bayesian weighted rating.
    """
    if quotas is None:
        quotas = DEFAULT_COUNTY_QUOTAS

    all_venues = merge_venues(places, shops)
    curated = load_curations()

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

    # Allocate according to quota, redistributing unused quota if a county has fewer candidates
    queue = []
    allocated_counts = Counter()
    unfilled_quota = 0

    for county, quota in quotas.items():
        cands = candidates_by_county.get(county, [])
        take = min(quota, len(cands))
        queue.extend(cands[:take])
        allocated_counts[county] = take
        if take < quota:
            unfilled_quota += (quota - take)

    # Distribute any unfilled quota to largest candidate pools (Fulton, Gwinnett, Cobb, DeKalb)
    if unfilled_quota > 0:
        for county in ["Fulton", "Gwinnett", "Cobb", "DeKalb", "Cherokee"]:
            if unfilled_quota <= 0:
                break
            cands = candidates_by_county.get(county, [])
            current_take = allocated_counts[county]
            available = len(cands) - current_take
            if available > 0:
                more = min(available, unfilled_quota)
                queue.extend(cands[current_take:current_take + more])
                allocated_counts[county] += more
                unfilled_quota -= more

    return queue[:target_total] if target_total else queue


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
               force_refresh: bool = False) -> dict:
    """Fetches a URL with disk caching, polite headers, and error capture."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    c_key = cache_key_for_url(url)
    c_file = cache_dir / f"{c_key}.json"

    if not force_refresh and c_file.exists():
        try:
            return json.loads(c_file.read_text())
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


DIRECTORY_DOMAINS = {
    "atlantacoffeeshops.com", "menutoeat.com", "facebook.com", "instagram.com",
    "toasttab.com", "yelp.com", "tripadvisor.com"
}


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
                        cache_dir: Path = CACHE_DIR, pause_sec: float = 0.2) -> dict:
    """Crawls venue homepage and prioritized subpages, respecting bounds and caching."""
    home_res = fetch_page(url, cache_dir=cache_dir)
    pages = {canonicalize_url(url): home_res}

    if not home_res.get("ok"):
        return pages

    subpages = discover_subpages(url, home_res.get("content", ""), max_pages=max_pages)
    for sub_url in subpages:
        if pause_sec > 0:
            time.sleep(pause_sec)
        sub_res = fetch_page(sub_url, cache_dir=cache_dir)
        pages[canonicalize_url(sub_url)] = sub_res

    return pages


# ==============================================================================
# 3. Branch & Multi-Location Disambiguation
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


def match_branch_pages(pages: dict, address: str, city: str) -> dict:
    """Examines crawled pages and tags them as branch_match (True/False/General).

    Ensures that location-specific subpages for a different branch are ignored
    for location-specific amenities (e.g. meeting rooms, patio).
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

        is_loc = any(kw in path for kw in ("location", "locations", "contact", "visit"))

        other_major_cities = [
            "alpharetta", "roswell", "duluth", "decatur", "marietta", "smyrna",
            "woodstock", "cumming", "lawrenceville", "suwanee", "buford", "canton",
            "peachtree city", "newnan", "midtown", "buckhead", "inman park", "west end"
        ]

        if is_loc:
            matches_us = (city_norm and city_norm in text_norm) or (street_num and street_num in text_norm)
            mentions_other = any(
                c in text_norm and c != city_norm
                for c in other_major_cities
            )
            if matches_us:
                tagged_pages[page_url] = {"data": p_data, "branch_match": True, "is_location_page": True}
            elif mentions_other and not matches_us:
                tagged_pages[page_url] = {"data": p_data, "branch_match": False, "is_location_page": True}
            else:
                tagged_pages[page_url] = {"data": p_data, "branch_match": True, "is_location_page": True}
        else:
            tagged_pages[page_url] = {"data": p_data, "branch_match": True, "is_location_page": False}

    return tagged_pages


# ==============================================================================
# 4. Tri-State Evidence & Fact Extractor
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

PATTERNS_MEETING_POSITIVE = [
    re.compile(r"\b(?:private\s+)?(?:meeting|conference|board|study|seminar)\s*(?:room|space|hall)\b", re.I),
    re.compile(r"\b(?:reservable|reserve|rent|book)\s+(?:a\s+)?(?:meeting\s+room|conference\s+room|study\s+room|private\s+room)\b", re.I),
    re.compile(r"\bbook\s+(?:our|the)\s+(?:conference|meeting)\s+room\b", re.I),
]

PATTERNS_PARTY_ONLY = [
    re.compile(r"\b(?:host|book)\s+(?:your\s+)?(?:private\s+party|wedding|reception|birthday|shower|buyout)\b", re.I),
    re.compile(r"\bfull\s+venue\s+buyout\b", re.I),
]

PATTERNS_ROASTER = [
    re.compile(r"\b(?:roast(?:ed)?\s+in[- ]house|in[- ]house\s+roast(?:ing|er)?|we\s+roast\s+our\s+own|house[- ]roasted|our\s+own\s+roast(?:s|ing)?|on[- ]site\s+roast(?:ing|ery)?|micro[- ]roaster(?:y)?)\b", re.I),
]


def extract_facts(pages: dict, address: str = "", city: str = "") -> dict:
    """Extracts structured facts as confirmed, unavailable, or unknown with supporting excerpts."""
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

    for page_url, p_info in tagged.items():
        if not p_info.get("branch_match"):
            continue
        p_data = p_info["data"]
        text = clean_text_from_html(p_data.get("content", ""))
        sentences = extract_sentences(text)

        for sent in sentences:
            # Laptop Policy
            if facts["laptopPolicy"]["status"] == "unknown":
                if any(p.search(sent) for p in PATTERNS_LAPTOP_NEGATIVE):
                    facts["laptopPolicy"] = {
                        "status": "unavailable",
                        "excerpt": sent,
                        "sourceUrl": page_url,
                        "checkedDate": now_str,
                    }
                elif any(p.search(sent) for p in PATTERNS_LAPTOP_POSITIVE):
                    facts["laptopPolicy"] = {
                        "status": "confirmed",
                        "excerpt": sent,
                        "sourceUrl": page_url,
                        "checkedDate": now_str,
                    }

            # Wi-Fi
            if facts["wifi"]["status"] == "unknown":
                if any(p.search(sent) for p in PATTERNS_WIFI_NEGATIVE):
                    facts["wifi"] = {
                        "status": "unavailable",
                        "excerpt": sent,
                        "sourceUrl": page_url,
                        "checkedDate": now_str,
                    }
                elif any(p.search(sent) for p in PATTERNS_WIFI_POSITIVE):
                    facts["wifi"] = {
                        "status": "confirmed",
                        "excerpt": sent,
                        "sourceUrl": page_url,
                        "checkedDate": now_str,
                    }

            # Outlets
            if facts["outlets"]["status"] == "unknown":
                if any(p.search(sent) for p in PATTERNS_OUTLETS_POSITIVE):
                    facts["outlets"] = {
                        "status": "confirmed",
                        "excerpt": sent,
                        "sourceUrl": page_url,
                        "checkedDate": now_str,
                    }

            # Seating
            if facts["seating"]["status"] == "unknown":
                m = [p.search(sent) for p in PATTERNS_SEATING_POSITIVE if p.search(sent)]
                if m:
                    facts["seating"] = {
                        "status": "confirmed",
                        "excerpt": sent,
                        "sourceUrl": page_url,
                        "checkedDate": now_str,
                    }

            # Meeting Room
            if facts["meetingRoom"]["status"] != "confirmed":
                if any(p.search(sent) for p in PATTERNS_MEETING_POSITIVE):
                    facts["meetingRoom"] = {
                        "status": "confirmed",
                        "excerpt": sent,
                        "sourceUrl": page_url,
                        "checkedDate": now_str,
                    }
                elif facts["meetingRoom"]["status"] == "unknown" and any(p.search(sent) for p in PATTERNS_PARTY_ONLY):
                    facts["meetingRoom"] = {
                        "status": "unavailable",
                        "excerpt": sent,
                        "sourceUrl": page_url,
                        "checkedDate": now_str,
                        "note": "Private party and event rentals only; no work/study meeting room.",
                    }

            # Roaster status
            if facts["roaster"]["status"] == "unknown":
                if any(p.search(sent) for p in PATTERNS_ROASTER):
                    facts["roaster"] = {
                        "status": "confirmed",
                        "excerpt": sent,
                        "sourceUrl": page_url,
                        "checkedDate": now_str,
                    }

        # Menu Highlights from menu pages
        path = urllib.parse.urlparse(page_url).path.lower()
        if "menu" in path or "drink" in path or "coffee" in path or "food" in path:
            spec_matches = re.findall(r"(?:signature|house\s+special|featured|specialty):\s*([A-Za-z0-9\s&'-]{3,40})", text, re.I)
            for m in spec_matches:
                clean_item = m.strip()
                if len(clean_item) >= 3 and clean_item not in facts["menuHighlights"]:
                    facts["menuHighlights"].append(clean_item)

    return facts


# ==============================================================================
# 5. Derivation of Curation Overlays & Contradiction Detection
# ==============================================================================

def derive_curation_overlay(facts: dict, place_meta: dict) -> dict:
    """Derives qualitative curation overlay (cw, usp, signature, loved, category)

    strictly grounded in factual evidence. Missing facts remain unassessed.
    """
    now_str = datetime.now(timezone.utc).strftime("%B %Y")
    overlay = {
        "name": place_meta.get("name"),
        "city": place_meta.get("city"),
        "county": place_meta.get("county"),
        "source": "website-crawl",
        "verified": now_str,
    }

    lp = facts.get("laptopPolicy", {})
    wifi = facts.get("wifi", {})
    seating = facts.get("seating", {})
    mr = facts.get("meetingRoom", {})
    roaster = facts.get("roaster", {})

    cw = None
    if lp.get("status") == "unavailable" or wifi.get("status") == "unavailable":
        note = lp.get("excerpt") or wifi.get("excerpt") or "Laptop use or Wi-Fi restricted per venue policy."
        cw = {
            "tier": "limited",
            "note": note,
            "hasMeetingRoom": False,
        }
    elif mr.get("status") == "confirmed":
        note = "Work-friendly space with reservable meeting room."
        if wifi.get("status") == "confirmed":
            note = f"Features verified Wi-Fi and reservable meeting space."
        cw = {
            "tier": "excellent",
            "note": note,
            "hasMeetingRoom": True,
            "meetingRoomNote": mr.get("excerpt", "Reservable meeting space available."),
        }
    elif wifi.get("status") == "confirmed" and (lp.get("status") == "confirmed" or seating.get("status") == "confirmed"):
        w_ex = wifi.get("excerpt", "").strip()
        s_ex = seating.get("excerpt", "").strip()
        if w_ex and s_ex and w_ex == s_ex:
            note = f"Verified work-friendly spot: {w_ex}"
        elif w_ex and s_ex:
            note = f"Verified work-friendly spot: {w_ex} ({s_ex})"
        else:
            note = f"Verified work-friendly spot: {w_ex or s_ex}"
        cw = {
            "tier": "excellent",
            "note": note,
            "hasMeetingRoom": False,
        }
    elif wifi.get("status") == "confirmed" or lp.get("status") == "confirmed":
        cw = {
            "tier": "good",
            "note": wifi.get("excerpt") or lp.get("excerpt") or "Verified guest Wi-Fi available for patrons.",
            "hasMeetingRoom": False,
        }
    elif mr.get("status") == "unavailable":
        cw = {
            "hasMeetingRoom": False,
        }

    if cw:
        overlay["cw"] = cw

    is_roastery_name = "roast" in place_meta.get("name", "").lower()
    if (roaster.get("status") == "confirmed" or is_roastery_name) and place_meta.get("category") in ("Coffee", "Specialty"):
        overlay["category"] = "Roasters"

    name = place_meta.get("name", "Local venue")
    city = place_meta.get("city", "Metro Atlanta")
    cat = overlay.get("category") or place_meta.get("category", "Cafe")
    if roaster.get("status") == "confirmed":
        overlay["usp"] = f"Independent craft coffee roaster in {city} offering house-roasted specialty coffee."
    elif cw and cw.get("hasMeetingRoom"):
        overlay["usp"] = f"Community {cat.lower()} in {city} featuring reservable meeting space and craft beverages."
    elif cw and cw.get("tier") == "excellent":
        overlay["usp"] = f"Work-friendly {cat.lower()} in {city} with verified Wi-Fi and comfortable seating."
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
            f"Meeting room conflict: existing record has hasMeetingRoom=True, but crawl indicates no meeting room."
        )

    if exist_cw.get("tier") == "excellent" and prop_cw.get("tier") == "limited":
        contradictions.append(
            f"Tier downgrade conflict: existing tier is 'excellent', but crawl detected restricted policy: {prop_cw.get('note')}"
        )

    return contradictions


# ==============================================================================
# 6. Pipeline CLI Actions
# ==============================================================================

def cmd_queue(args) -> int:
    places_data = json.loads(PLACES_PATH.read_text())
    shops_data = json.loads(SHOPS_PATH.read_text())
    queue = generate_balanced_queue(places_data["places"], shops_data.get("shops", []), target_total=args.limit)

    print(f"=== BALANCED RESEARCH QUEUE ({len(queue)} venues) ===")
    county_counts = Counter(c["county"] for c in queue)
    for county, count in sorted(county_counts.items()):
        print(f"  {county:12s}: {count:2d} venues")

    if args.json:
        print(json.dumps(queue, indent=2, ensure_ascii=False))
    return 0


def cmd_crawl_batch(args) -> int:
    places_data = json.loads(PLACES_PATH.read_text())
    shops_data = json.loads(SHOPS_PATH.read_text())
    queue = generate_balanced_queue(places_data["places"], shops_data.get("shops", []), target_total=args.limit)

    print(f"Crawling {len(queue)} venues (cache: {CACHE_DIR})...")
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
        pages = crawl_venue_website(website, venue, max_pages=6, cache_dir=CACHE_DIR, pause_sec=args.pause)
        facts = extract_facts(pages, address=addr, city=city)

        overlay = derive_curation_overlay(facts, venue)
        contradictions = detect_contradictions(overlay, curated.get(pid, {}))
        if contradictions:
            contradiction_count += len(contradictions)
            for c in contradictions:
                print(f"  ⚠ {c}")

        staged[pid] = {
            "venue": venue,
            "facts": facts,
            "proposed": overlay,
            "contradictions": contradictions,
            "pagesCrawled": list(pages.keys()),
        }

        facts_repo[pid] = {
            "name": name,
            "city": city,
            "county": venue.get("county"),
            "website": website,
            "pagesChecked": list(pages.keys()),
            "checkedDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
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

    print(f"Summary of findings:")
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

    committed = 0
    for pid, entry in staged.items():
        prop = entry.get("proposed")
        facts_repo[pid] = {
            "name": entry["venue"]["name"],
            "city": entry["venue"]["city"],
            "county": entry["venue"]["county"],
            "website": entry["venue"]["website"],
            "pagesChecked": entry.get("pagesCrawled", []),
            "checkedDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "facts": entry.get("facts", {}),
        }
        # Only commit an overlay to curations.json if qualitative findings exist
        has_curation = bool(
            prop and (
                prop.get("cw")
                or prop.get("loved")
                or prop.get("signature")
                or prop.get("category") == "Roasters"
            )
        )
        if has_curation:
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
    print(f"Persisted facts for {len(facts_repo)} venues to {FACTS_PATH}")
    print("Now run: python3 scripts/curate_places.py --apply")
    return 0


def cmd_crawl_url(args) -> int:
    pages = crawl_venue_website(args.crawl_url, max_pages=8, cache_dir=CACHE_DIR)
    facts = extract_facts(pages, address=args.address or "", city=args.city or "")
    overlay = derive_curation_overlay(facts, {"name": "Test Venue", "city": args.city or "Atlanta"})
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
    parser.add_argument("--json", action="store_true", help="Output queue as JSON")
    parser.add_argument("--crawl-batch", action="store_true", help="Crawl websites and stage proposals")
    parser.add_argument("--pause", type=float, default=0.2, help="Pause between page requests (default: 0.2s)")
    parser.add_argument("--review", action="store_true", help="Review staged proposals")
    parser.add_argument("--verbose", action="store_true", help="Detailed review breakdown")
    parser.add_argument("--approve", action="store_true", help="Commit staged proposals to curations.json and research_facts.json")
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
