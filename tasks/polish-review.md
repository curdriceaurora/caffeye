# Website polish review — September 2026 expansion

Reviewed locally at 1280×800, 375×750, and 320×568, including light and dark themes. Dataset checks use the browser's accepted records after deduplication, not the sum of JSON array lengths.

## Addressed in this update

- Neutral “Caffeye” and “Loading spots…” first paint replaces the Duluth/59 shell.
- Loaded region and total drive page/social metadata; header counts continue to follow franchise inclusion. Static metadata and the manifest use count-free Metro Atlanta copy for clients that do not execute JavaScript.
- Freshness identifies the source when only one of the two datasets has a known verification month. Regional retry updates the label and metadata.
- Search has an explicit accessible name.
- Repository overview, product/design scope, data editing instructions, and manual test baselines now describe the real regional dataset and seed fallback. TESTS.md includes a reusable console summary for subsequent crawls.

## Follow-up fixes

- Repaired 11 malformed dark-theme CSS rules, including model badges, feature pills, the franchise switch, and map controls. Explicit and system dark modes now apply the same styles; explicit light mode overrides a dark system preference. Curated labels use a lighter green in dark mode, and the checked switch thumb contrasts against its gold track.
- At widths ≤ 380 px, the visible heading shows the loaded region without “Coffee in”. The page title and accessible home-button label retain the full name. The 320 px header fits on one line without overflow.
- Added `python3 scripts/curate_places.py --research-queue`: a read-only top-ten list of independent venues missing coworking data, ordered by the site's global Bayesian score, with location identifiers and website/map links. The current queue begins with Black Coffee Atlanta, Lumier’s Chimney Cake, and Douceur De France in Roswell. Re-running it updates priorities after a crawl. Actual amenity verification remains editorial work; unknowns are not converted into false “no meeting room” claims.

## Validation

- 97 Python unit tests passed, including research-queue ranking, deduplication, and empty-data cases.
- Browser coverage includes slow first paint, data-derived metadata and feature counts, meeting-room filtering, regional fallback/retry, compact mobile headings, and rendered text contrast of at least 4.5:1 for dark badges and feature pills. The final full suite passed 75 checks with 4 viewport-specific skips using the configured Node static server.
- Mobile-density checks passed: at least five fully visible cards at 375×750 and three at 320×568.
- The research queue’s top ten IDs were checked against the loaded browser ranking. Inline JavaScript syntax and `git diff --check` passed.
- Local basemap tiles displayed “API key required” because localhost does not supply the allowed referrer. The user confirmed that the deployed website renders correctly with its authorized referrer; this is a local preview limitation, not an open website defect.
