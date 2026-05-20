# Product — caffeye

## Purpose

A curated, opinionated map of every café, bakery, and tea house in the Duluth, GA area. Ranked by Bayesian-weighted rating so the best answer is always on top. Exists because generic platforms make you work too hard to find a genuinely good local spot. Success looks like: user opens it, sees the answer in under 10 seconds, puts the phone away and goes.

## Users

Duluth, GA locals and regulars who already know the coffee scene. Primary job: quick lookup on a specific need ("open late tonight?", "good wifi for a call?", "which boba spot is actually worth it?"). Session length is 30 seconds to 2 minutes. They trust the data because they've been here before and it was right.

They know the city loosely, not exhaustively. They want to compare options visually, not scroll a thousand reviews. They don't want to install an app.

## Brand

**Personality:** Playful, opinionated, local. Feels like a friend who has been to every spot and has a take on all of them. Confident about its rankings. Warm but not precious. Has character without being loud.

**Anti-references:**
- Generic Yelp/Google Maps: corporate, flat, every city looks the same
- Startup SaaS dashboard: dark mode, metric cards, gradient text, hero numbers
- Foodie Instagram aesthetic: latte art photos, serif-on-beige, oversaturated warmth
- Tourist trap / chamber of commerce: promotional tone, "Visit Duluth!" energy, clip art vibes

## Principles

Every product decision traces back to one of these principles. The `→` line records the concrete decision made.

### §1. One tap to the answer

A map app's job is to get the user from "I want coffee" to "this is the place" with as few steps as possible. We don't make people open popups, then click through to details, then click again for hours. Navigation should never require leaving the viewport — the detail card comes to the user.

→ Removed the preview popup that intervened between pin and detail card. Clicking a pin selects the shop and opens the full card in one motion.

### §2. The right default beats the right options

Sorting controls force the user to decide what they want before they know what's available. A good ranking is *implicit*. We chose IMDB's Bayesian weighted rating because it merges score with sample size — a 4.9 with 14 reviews shouldn't beat a 4.6 with 1,680. Rankings are opinionated. Never add controls that let users second-guess the default order.

→ Removed the sort dropdown entirely. The list opens in the best-overall order. Anyone who wants to slice the data can use the category and feature chips.

### §3. Show what the user can see

If the map is zoomed into Pleasant Hill, the right-side list should not still be showing every shop in Duluth. The view *is* a filter — using it to filter the list keeps the two panels coherent. But a list that silently changes count without explanation breaks that coherence — the user sees the number drop and doesn't know why.

→ The list shows only shops whose pins are inside the current viewport. When the viewport is the active constraint, the header reads **"X in view"** instead of **"X spots"**. List items stagger in on each refresh (28 ms per row, capped at 140 ms) so the update reads as a deliberate response to the map. The count pops to accent color when it changes.

### §4. Local first, not tourist-first

The user already knows Duluth exists. Don't explain it to them. No hero banners, no taglines, no introductory copy. The core session is 30 seconds — every layer of UI is a tax on that.

→ No onboarding, no splash, no "Welcome to caffeye" copy. The page opens directly to the map with all shops visible.

### §5. Density matters on phones

Mobile users want to see as many options as the map allows. Every pixel of chrome competes with a list row. Cap the map, compress the chips, trim the padding, hide the disclaimer footer — give the list real estate.

→ Map fixed at 220 px on mobile; chips compressed to 11.5 px font with tight padding; footer hidden below 820 px. About 5 cards visible on an iPhone 14 Pro instead of 2.

### §6. Playfulness is information

A colored emoji tile costs almost nothing visually but communicates a category at a glance. ☕ for coffee, 🥐 for a bakery, 🧋 for boba — a user scanning the list reads category before they read the name. Emoji, color, and typographic personality are evidence that a human curated this, not an algorithm. Lean into them as trust signals.

→ Category-colored circular emoji tiles on every list item; same emoji on each map pin with a category-colored background.

### §7. Labels must never lie

If two shop names overlap on the map, the map is lying about which name belongs to which pin. Worse, if a label drifts over a cluster bubble or another pin, it suggests a shop is at the wrong place.

→ Pin labels position themselves at one of 16 angles around their pin. Collision detection runs against every other label, every visible pin, and every cluster bubble. Higher-rated shops claim space first.

### §8. Geocode with the authoritative source

A pin in a residential subdivision when the shop is actually in a strip mall undermines the whole map. We don't approximate coordinates — we geocode every address against the source that maps the country, then verify the house number matches.

→ All unique buildings geocoded via macOS `CLGeocoder` (Apple Maps data); a result is only accepted when its `subThoroughfare` matches the expected house number.

### §9. Motion communicates cause

When the UI changes in response to user action, the animation should make the cause legible — not just decorate. List items cascading in after a pan tells the user "the map drove this"; a crossfade between list and detail tells them "you went somewhere". Animations that don't carry meaning shouldn't exist. All transitions use compositor-only properties (opacity, transform) targeting 60 fps.

→ List↔detail is a compositor crossfade (no layout/paint). Viewport-triggered list refreshes pulse the results bar and stagger items in. Count pops on change.

## Operating constraints

- **Static, single HTML file.** No build step. No backend. Deploys via Cloudflare Workers static assets. Anyone can grok the whole codebase in a sitting.
- **CDN-loaded libraries only.** Leaflet, MarkerCluster, Inter, Fraunces. No npm install needed to edit.
- **Manual curation.** The shop list is hand-curated. Adding a shop is a code edit, deliberately — because the value is in the curation, not the count.

## What this is not

- **Not a booking app.** Each card links out to Google Maps, Yelp, and the shop's own site. We don't try to own the next click.
- **Not a review aggregator.** We show the star rating and review count as inputs to our ranking, not as the destination.
- **Not a generic POI app.** Scope is intentionally narrow: coffee, tea, bakeries, and dessert cafés in one suburb. Narrow scope is what makes the curation valuable.

## Accessibility & Inclusion

WCAG AA minimum. Color is never the sole signal (categories use icon + color). `prefers-reduced-motion` collapses all animation durations to near-zero. Keyboard navigation for chip filters and shop list items.

## How we know it's working

A first-time visitor on a phone should:

1. See the whole spread of shops on first paint, with category-colored pins.
2. Read at least four shop names without scrolling.
3. Tap one pin and land directly on a detail card with hours, signature drinks, and a Google Maps link.
4. Use the "Work-friendly" chip to filter to the shops with desks they can actually work at.
5. Trust that the pin is on the right block.

The day a Duluth resident texts the link to a friend without explaining what it is, we won.
