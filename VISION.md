# Coffee in Duluth — Vision

A one-page, single-tap map of every coffee shop, bakery, and tea house in Duluth, GA — built so a local can decide where to go in under thirty seconds.

## The user we're designing for

Someone in or near Duluth with a few minutes on their phone, looking for a third place. They know the city loosely, not exhaustively. They want to compare options visually, not scroll a thousand reviews. They may want a quick coffee, a study spot, a late-night dessert run, or a meeting room — and they don't want to install an app.

## Principles

Every product decision in this project traces back to one of seven principles. The principles are the "why" behind the requirements.

### 1. One tap to the answer

A map app's job is to get the user from "I want coffee" to "this is the place" with as few steps as possible. We don't make people open popups, then click through to details, then click again for hours.

→ Removed the preview popup that intervened between pin and detail card. Clicking a pin selects the shop and opens the full card in one motion.

### 2. The right default beats the right options

Sorting controls force the user to decide what they want before they know what's available. A good ranking is *implicit*. We chose IMDB's Bayesian weighted rating because it merges score with sample size — a 4.9 with 14 reviews shouldn't beat a 4.6 with 1,680.

→ Removed the sort dropdown entirely. The list opens in the best-overall order. Anyone who wants to slice the data can use the category and feature chips.

### 3. Show what the user can see

If the map is zoomed into Pleasant Hill, the right-side list should not still be showing every shop in Duluth. The view *is* a filter — using it to filter the list keeps the two panels coherent.

→ The list shows only shops whose pins are inside the current viewport. As you pan and zoom, the list narrows or expands.

### 4. Density matters on phones

Mobile users want to see as many options as the map allows. Every pixel of chrome competes with a list row. Cap the map, compress the chips, trim the padding, hide the disclaimer footer — give the list real estate.

→ Map fixed at 220px on mobile; chips compressed to 11.5px font with tight padding; footer hidden < 820px. About 5 cards visible on an iPhone 14 Pro instead of 2.

### 5. Playfulness is information

A colored emoji tile costs almost nothing visually but communicates a category at a glance. ☕ for coffee, 🥐 for a bakery, 🧋 for boba — a user scanning the list reads category before they read the name.

→ Category-colored circular emoji tiles on every list item; same emoji on each map pin with a category-colored background.

### 6. Labels must never lie

If two shop names overlap on the map, the map is lying about which name belongs to which pin. Worse, if a label drifts over a cluster bubble or another pin, it suggests a shop is at the wrong place.

→ Pin labels position themselves at one of 16 angles around their pin. Collision detection runs against every other label, every visible pin, and every cluster bubble. Higher-rated shops claim space first.

### 7. Geocode with the authoritative source

A pin in a residential subdivision when the shop is actually in a strip mall undermines the whole map. We don't approximate coordinates — we geocode every address against the source that maps the country, then verify the house number matches.

→ All 42 unique buildings geocoded via macOS CLGeocoder (Apple Maps data); a result is only accepted when its `subThoroughfare` matches the expected house number.

## What this is not

- **Not a booking app.** Each card links out to Google Maps, Yelp, and the shop's own site. We don't try to own the next click.
- **Not a review aggregator.** We show the star rating and review count as inputs to our ranking, not as the destination. Users who want reviews follow the Yelp/Google links.
- **Not a generic POI app.** Scope is intentionally narrow: coffee, tea, bakeries, and dessert cafés in one suburb. Narrow scope is what makes the curation valuable.

## Operating constraints

- **Static, single HTML file.** No build step. No backend. Deploys via Cloudflare Workers static assets in one `wrangler deploy`. Anyone can grok the whole codebase in a sitting.
- **CDN-loaded libraries only.** Leaflet, MarkerCluster, Inter, Fraunces. No npm install needed to edit.
- **Manual curation.** The shop list is a hand-curated JS array. Adding a shop is a code edit, deliberately — because the value is in the curation, not the count.

## How we know it's working

A first-time visitor on a phone should:

1. See the whole spread of shops on first paint, with category-colored pins.
2. Read at least four shop names without scrolling.
3. Tap one pin and land directly on a detail card with hours, signature drinks, and a Google Maps link.
4. Use the "Work-friendly" chip to filter to the 19 shops with desks they can actually work at.
5. Trust that the pin is on the right block.

The day a Duluth resident texts the link to a friend without explaining what it is, we won.
