# Standalone SwiftUI implementation plan

Date: 2026-09-25. Branch: `agent/standalone-swiftui`.
Scope confirmed: iPhone, iPad, and native macOS. Planning only; no application implementation yet.

## Recommendation

Build a shared Swift domain layer and SwiftUI interface, using Apple's standard typography, colors, controls, navigation, and MapKit rendering. Use a small platform adapter around `MKMapView` for native annotation clustering. This is a native app with SwiftUI screens; it is not exclusively SwiftUI framework code. No WebView or JavaScript runtime.

Preserve Caffeye's decision-making behavior: opinionated ranking, independent venues by default, useful filters, map-relative results, one-action venue details, and accurate editorial information. Accept that the native version will have different density, navigation, map labels, and visual identity.

Proposed deployment floor: iOS/iPadOS 18 and macOS 15, pending device-support requirements. Build with the installed Xcode 27.0, but do not make newer OS design treatments a requirement or emulate them on older systems. Use the appearance supplied by the running OS.

## Evidence and first dependency

Reviewed `PRODUCT.md`, `REQUIREMENTS.md`, `DESIGN.md`, `CLAUDE.md`, current `public/index.html`, dataset ingestion, ranking, filtering, detail rendering, and hydration logic. Where documents disagree, current implementation takes precedence: for example, some design examples still show raw stars in rows and removed location chips.

The documented snapshot is 1,705 accepted venues, including 970 independents, from 61 seed and 1,688 regional input records. These are fixture expectations to verify during implementation, not hardcoded UI counts. Planning did not execute the browser suite. The branch starts from local main, which was one commit behind origin/main when created; inspect that upstream change before implementing.

**Data portability must be resolved before shipping the MapKit version.** Regional coordinates and operational data, plus ranking inputs, come from Google Places. Google's published Places API policy says results shown on a map must be on a Google Map and restricts storage beyond permitted exceptions. Existing JSON files are not evidence of permission to redistribute the content in an Apple Maps app. Review the applicable account terms and provenance before choosing a shipping dataset. This also affects bundled/offline snapshots and derived ranking inputs.

Preferred native-default path: independently sourced or appropriately licensed venue data and ranking inputs. If that cannot preserve the current inputs, explicitly redesign ranking and coverage; Apple Maps is not a drop-in source for Google's rating/review counts or Caffeye's editorial fields. A Google Maps implementation would be a separate provider decision outside this platform-default plan. Use synthetic fixtures to develop the native shell while resolving this dependency.

Source: [Google Places API policies](https://developers.google.com/maps/documentation/places/web-service/policies).

## What changes with platform defaults

| Web behavior | Native decision | Consequence |
|---|---|---|
| Inter/Fraunces, cream/forest/gold surfaces, bespoke borders and shadows | System fonts, semantic colors, standard control styles; retain app icon and optional category tint | The distinctive web styling will not translate exactly. No bundled UI fonts or CSS-token recreation. |
| Tiny filter chips and five visible phone cards | Standard target sizes, Dynamic Type, native list rows | Cannot promise five visible rows, especially with large text or keyboard visible. |
| All categories and utility chips always visible | Type and Useful for menus containing independent toggles; visible active-filter summary and Reset | More taps to change filters; accept this explicit departure from the web's no-hidden-filters preference. A segmented picker would incorrectly make categories mutually exclusive. |
| Always-visible map plus list/detail | Phone stacked map + list/detail; regular-width split layout | Layout composition is still app code. A default `NavigationSplitView` collapses on compact screens and does not guarantee both surfaces remain visible. |
| CARTO tiles and optional MapLibre renderer | Apple basemap | Different labels, roads, POIs, colors, attribution, and loading behavior. Remove renderer switch/fallback. |
| Dark count bubbles and custom emoji discs/halos | Standard MapKit marker and cluster views with category glyph/tint where legible | Exact cluster geometry, late-night glow, and selection halo go away. Keep late-night information in accessible rows/details. |
| Sixteen-angle labels prioritized by rating | MapKit collision handling and title visibility | No guarantee every pin has a label, labels favor the highest score, or placement matches the web. Native decluttering is not our ranking algorithm. |
| Roughly 20 m radial displacement of colocated shops | Keep true coordinates; cluster and expose cluster members | No artificial pin offsets. Zoom alone cannot separate identical coordinates; a member list is required. Individual pins still open detail directly. |
| Leaflet zoom 7–19, label threshold 13, strict tile bounds | Native camera boundary/distance constraints, regional reset | Zoom numbers do not map directly. Cannot enforce or promise Apple's tile-request boundary. |
| Panning updates in-view list; offscreen matches retained | Preserve in domain state using visible map rectangle | Native API provides geometry; app must still implement filtering and avoid camera/selection feedback loops. |
| List/detail crossfade, staggered rows, flashing counts | Native navigation and modest system animation | Exact choreography and compositor/LCP guarantees do not carry over; honor Reduce Motion. |
| Load 200 more | Lazy native `List` with all matching IDs | Remove manual pagination, preserve scroll identity; measure map annotation cost separately. |
| Header theme button saved in localStorage | Follow system appearance initially | Per-app appearance override is omitted from v1; a later preference can use native Settings. |
| Click brand to reset | Explicit Reset toolbar command | Reset clears search/categories/features, restores indie-only and regional camera. |
| Links open a new browser tab | `Link`/`openURL` to Google Maps, Yelp, venue site | OS decides browser versus installed app; no guaranteed new tab. Validate allowed URL schemes. Optional Apple Maps directions use true coordinates. |
| Browser DOM/ARIA, focus and Escape | Native accessibility, focus, keyboard commands | Tests and focus restoration must be rewritten; preserve spoken score meaning and actionable empty/error states. |
| Cache API, fetch races, CDN bootstrap | URLSession, validated disk snapshot, local launch data if permitted | Preserve freshness and stable reading, not the browser's exact 1.8/2.5-second races. |
| Single HTML, Cloudflare deployment, URL sharing/PWA | Xcode app targets, signing and app distribution | Install required; no automatic parity with web link sharing, SEO, or zero-build deployment. Universal links are separate scope. |

Standard controls do not require replacing every category emoji with an SF Symbol. Keep existing category vocabulary and emoji where they fit in native labels; do not invent misleading symbols for boba/roasters. Category text must remain available without color.

## Platform layout

**iPhone and compact iPad windows:** One `NavigationStack` owns a discovery screen. Keep the map above a native list, with adaptive height rather than the web's pixel clamp. Use `.searchable` and toolbar filter menus. Selection replaces the lower results content with scrollable detail and a Back action while keeping the map mounted. This small amount of custom composition preserves the product's central interaction. At accessibility text sizes or constrained landscape height, prioritize readable content and allow the map to contract; simultaneous visibility is best effort, not a fixed density contract. Avoid a persistent map sheet in v1 because it introduces map occlusion and gesture complexity.

**iPad regular width:** Native resizable split layout, results sidebar and map/detail workspace. Detail appears beside or below the map according to available width. Selection must not replace the whole map column. Handle resizing and compact transitions without losing selection or search.

**macOS:** Native SwiftUI app, not Catalyst. Results sidebar, map workspace, and detail inspector when width permits. Native toolbar search, menus, keyboard list navigation, Back/Escape, and Reset command. Window-scoped selection/camera/filter state; shared read-only dataset service. A second window must not move the first window's map.

Do not add accounts, favorites, location permission prompts, live opening-status computation, bookings, or navigation routing in v1. “Open late” remains a recorded amenity, not “open now.” The app starts at Metro Atlanta without requiring user location.

## Shared implementation

Proposed tree under `native/`:

```text
native/Caffeye.xcodeproj
native/Caffeye/App/                 app entry, platform scenes, commands
native/Caffeye/Core/                Codable DTOs, venue model, merge, ranking, filters
native/Caffeye/Data/                repository, URLSession, snapshot validation/cache
native/Caffeye/Discovery/           window state, results, filters, search
native/Caffeye/Details/             venue sections and external actions
native/Caffeye/Map/                 shared adapter contract + iOS/macOS wrappers
native/Caffeye/Resources/           asset catalog and permitted data fixtures
native/CaffeyeTests/                domain and repository tests
native/CaffeyeUITests/              native interaction tests
```

Keep the static web app and discovery scripts as independent deliverables. Do not duplicate hand-maintained data: after provenance is resolved, use a deterministic resource-copy/export step from the approved source. No API secrets or paid discovery calls in the client. No database framework is needed for this read-only dataset initially.

Use value models and pure domain functions, an actor-isolated repository, and main-actor observable per-window discovery state. Separate DTO decoding from normalized venue models; preserve source provenance and unknown optional fields.

The map adapter receives matching venues, selection, and camera commands; emits user camera changes, selection, and cluster membership. Wrap `MKMapView` with `UIViewRepresentable` on iPhone/iPad and `NSViewRepresentable` on macOS. Reconcile annotations by stable ID instead of removing and reinserting everything on every update. Disable intermediary callouts for individual venue selection.

Apple documents clustering through `MKAnnotationView.clusteringIdentifier` and `MKClusterAnnotation`. Inspection of the installed macOS SwiftUI Map interface did not expose an equivalent clustering control. Validate both target SDKs in the first spike; do not assume pure SwiftUI `Map` supplies equivalent clustering at this dataset size.

Sources: [MapKit clustering](https://developer.apple.com/documentation/mapkit/decluttering-a-map-with-mapkit-annotation-clustering), [clusteringIdentifier](https://developer.apple.com/documentation/mapkit/mkannotationview/clusteringidentifier), [NavigationSplitView](https://developer.apple.com/documentation/swiftui/navigationsplitview).

## Behavior to preserve explicitly

- Seed wins duplicate place IDs. Port the current relisted-duplicate heuristic faithfully first; document its approximate coordinate/name-token behavior rather than calling it a precise distance check. Repeated loads must be idempotent. Stable IDs must survive refreshes.
- Ranking uses supplied regional `C` and `m` priors, with the current fallback algorithm if absent. Sort on unrounded score, preserving input order for ties. Filtering must not recompute priors. Display one decimal, distinguish ◆ weighted score from Google's raw ★ provenance, and label unrated venues accurately. Production parity depends on permitted ranking inputs.
- Categories combine with OR; selected utility features combine with AND. Work-friendly means `cw.tier == excellent`, not `good`. Search lowercases and trims, then requires every whitespace-delimited word to occur somewhere in the same indexed fields as the web. Do not replace this with Apple POI search.
- Category and utility counts use the franchise-filtered dataset, independently of the current search, viewport, and other filter choices. Results count uses all active constraints. Show in-view versus global match counts and a Show all matches camera action.
- All global matches remain map candidates; only list membership depends on viewport. Use true coordinates in the native version and document small boundary differences caused by removing the web's pin displacement.
- Save browsing camera before the first selection. Switching venue selections must not overwrite it. Back restores camera and list scroll position. Programmatic camera changes must not be mistaken for user browsing.
- A filter/search change that excludes the selected venue closes detail and communicates the change accessibly. Missing editorial data stays unknown, never inferred. Preserve source dates and verification notes.
- Load the latest valid permitted snapshot immediately, refresh asynchronously, show stale/partial status with retry, and retain last-good data on failure. Atomically validate and replace snapshots. Reject malformed schemas/coordinates and untrusted action URL schemes.
- Refresh the map promptly, but do not reorder a list being read or move an actively used camera. Stage changes behind Update list; preserve selected identity and scroll. Keep per-source freshness distinct from download time. Handle seed-only, regional-only, both-failed, cancellation, and repeated refresh states.
- Offline venue access is conditional on permitted local data; Apple basemap availability offline is not guaranteed.

## Delivery sequence and acceptance gates

1. **Resolve dataset portability and capture baseline.** Inspect upstream delta; record expected IDs, deduplication results, ranking and filter outputs from the current app for permitted fixtures. Decide which data can ship, refresh, and remain offline. Exit: explicit source/field decisions and any ranking changes documented.
2. **Map and adaptive-layout spike.** Create the three-platform project using synthetic data at roughly 1,700 venues. Prove clustering, colocated-member selection, direct pin detail, viewport callbacks, camera restore, and compact/regular layouts. Exit: working prototype on iPhone/iPad simulators and native Mac, with the map visible during ordinary detail browsing. This is the largest technical uncertainty and should precede UI polish.
3. **Domain and repository.** Implement decoding, stable identity, merge, ranking, filters/search, count semantics, source metadata, and refresh state machine. Exit: deterministic fixtures verify parity, missing values, duplicates, tie order, cancellation and failed refresh without data loss.
4. **Complete discovery and detail.** Connect native lists, toolbar controls, counts, empty states, unknown amenities, provenance, links, Reset and Back. Exit: a venue can be found by search/filter/map and opened in one action on all platforms; reading state survives detail and refresh.
5. **Native usability and performance.** Verify Dynamic Type, VoiceOver, contrast, Reduce Motion, hardware keyboard, iPad window resizing, Mac multiwindow, and keyboard-visible phone layouts. Profile launch-to-interactive-results, pan/zoom hitches, memory and annotation reconciliation with Instruments. Exit: no unbounded annotation churn or repeated full list rebuilds; record measured device baselines instead of claiming web FPS/LCP parity.
6. **Distribution readiness.** Configure identifiers, signing, app icons, macOS sandbox/network access, privacy/support links and native CI build/test jobs. Validate distribution using an appropriate release toolchain and the chosen channel. Exit: buildable iOS/iPadOS and macOS artifacts, documented release procedure, and a feature-parity/change checklist. Actual upload/release is separate from this planning task.

## Verification scope

Use domain tests for observable behavior: ingestion/deduplication, priors, ranking ties, unrated records, OR/AND filtering, all-word search, counts, and refresh stability. Use native UI tests for pin/list selection, Back camera restoration, reset, filter-induced deselection, offscreen matches, colocated clusters, and interrupted loads. Existing Playwright tests serve as behavioral references; they cannot validate native views.

Manual matrix: small iPhone plus large Dynamic Type; iPad portrait/landscape and narrow windows; macOS narrow/wide and two windows; light/dark, VoiceOver, keyboard-only, offline and slow/failing refresh. Check that attribution stays visible and that the usable map rectangle matches the area used for list filtering.

No application tests ran for this plan. Research verified current code paths, installed Xcode version/MapKit interface, and the cited vendor documentation. The next concrete deliverable is the map/layout spike after the dataset decision; implementation has not begun.
