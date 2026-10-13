# Caffeye native

Standalone SwiftUI app for iPhone, iPad, and native macOS. Requires iOS/iPadOS 18 or macOS 15. Uses system appearance and MapKit, without a WebView, account, or location permission.

Open `Caffeye.xcodeproj` in Xcode. Choose **Caffeye-iOS** for iPhone/iPad or **Caffeye-macOS** for Mac. For a physical device, select your own development team in Signing & Capabilities. The project is checked in; XcodeGen is needed only after editing `project.yml`:

```sh
xcodegen generate --spec native/project.yml
swift test --package-path native/Core
xcodebuild -project native/Caffeye.xcodeproj -scheme Caffeye-macOS \
  -destination 'platform=macOS,arch=arm64' CODE_SIGN_IDENTITY=- test
xcodebuild -project native/Caffeye.xcodeproj -scheme Caffeye-iOS \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' CODE_SIGNING_ALLOWED=NO test
```

Simulator names vary by installed runtime. Use `xcrun simctl list devices available` to choose a destination. Build artifacts go under `native/build/` when using `-derivedDataPath native/build/...`.

## Data and offline use

First launch loads **1,705 existing venues**, including **970 independents**, from the bundled `venues.json`. Names, addresses, true coordinates, categories, cities/counties, neighborhoods, hours, editorial recommendations, coworking/meeting-room notes, late-night information, source verification dates, provider IDs/types, and available external links are preserved. Ratings, review counts, weighted scores, and rating-derived priors are excluded. The list is alphabetical and explicitly says ratings were omitted.

Regenerate the export after a source dataset change:

```sh
python3 native/scripts/export_venues.py
python3 native/scripts/export_venues.py --check
python3 -m unittest discover -s native/scripts -p 'test_*.py'
```

The exporter follows the webapp's curated-first place-ID and relisted-venue deduplication, resolves seed coordinates through `shops.json.addr`, and generates stable app IDs. Export bytes and revision are independent of all rating inputs. It makes no API calls and does not claim the original sources were independently reverified. Google Places provenance remains attached to discovered operational data; excluding ratings does not change the provenance of the other fields. The rated fictional `demo.json` is retained as an explicit UI-testing fixture.

Use **Data → Import offline snapshot…** to import a provider-neutral JSON file. A complete example is `Caffeye/Resources/demo.json`. Its exact data contract is defined by the public `Codable` models in `Core/Sources/CaffeyeCore/Venue.swift` and the accompanying `snapshot.schema.json`.

A snapshot has:

- `schemaVersion: 1`, nonempty `revision` and `region`, explicit `isDemo`.
- Optional `priors` with `mean`, positive `weight`, and source provenance. Priors are required whenever any venue has a rating; the bundled venue-only snapshot omits them.
- A nonempty `venues` array with unique app-owned IDs, category, true coordinates, address, city, business model, and provenance.
- Optional ratings containing `average` (0–5), nonnegative `count`, and separate provenance; optional editorial, work, late-night, website and action fields.

Dates belong to each source record as `provenance.verified`. Do not substitute a download timestamp. `providerIDs` are matching metadata; IDs used by the UI belong to Caffeye and must remain stable across revisions. Export adapters must normalize and resolve provider/curated duplicates before producing a snapshot. The importer rejects duplicate app IDs rather than guessing which record should win.

Imports are validated before an atomic file replacement under the app's Application Support directory. Invalid updates leave the previous file intact. On subsequent launches the snapshot loads locally, with no network request. Data is shared by windows; filters, selection and map camera are window-specific. While someone reads, a refresh stages list changes behind **Update list**, while the map receives the new dataset. Switching filters or moving the map applies pending list data.

**Data settings** optionally saves an HTTPS snapshot URL. **Update snapshot** fetches a full replacement on demand, with a 20-second request timeout and a 20 MB streaming limit. There is no background polling or paid API call. Imports use the same 20 MB limit. Exporters must supply content permitted for local storage and Apple Maps display. A provider-neutral schema does not confer new rights on source data.

Venue data, search, editorial details, and ranking work offline; Apple map imagery is not bundled and may need internet access. Browser links and opening Apple Maps depend on the OS and network.

## Ranking and interaction

The Bayesian formula remains `(v × R + m × C) / (v + m)`. When rating inputs are supplied, snapshot priors `C` and `m` are independent of filters and viewport. Without priors or ratings, the app orders venues alphabetically and displays no scores. Sort uses full precision and stable input order for ties; display uses one decimal. An unrated venue uses the population mean internally but displays “No rating.” Raw rating/review counts and their source appear only in detail.

**Include franchise stores** is a visible header toggle, off by default. Categories combine with OR; utilities combine with AND. Work-friendly requires the `excellent` tier. Every search word must match somewhere in name/category/address/area/editorial/work/late fields. Normalized search text is indexed once per accepted snapshot; current map matches, staged list matches, and viewport rows are cached separately. Filter counts are computed in one pass when the snapshot or franchise scope changes, independently of search and viewport. The list follows the visible map rectangle, while the map retains all global matches. There is no sort dropdown or load-more pagination.

Individual pins and list rows open detail directly. On regular-width layouts, map selection scrolls the sidebar to the selected row; compact browsing keeps its saved list position. Native clusters expose their ranked members so shops sharing true coordinates remain selectable. Back restores the camera saved before the first selection; switching venues keeps that original camera. Reset clears search and filters, restores indie-only scope and the Metro Atlanta frame. Standard system fonts, native list controls and menu toggles replace web styling and compressed chip rows. On macOS, File provides Import and Update, the app menu provides Data settings, and View provides Back and Reset. Commands target the active window; Reset (⌘⇧R), Import (⌘⇧O), Back (⌘[), and Data settings (⌘,) work independently of toolbar focus. Apple Maps actions use the location initializer on iOS/macOS 26 and newer, retaining the placemark fallback for older systems and SDKs.

## Validation and remaining release work

Domain/storage and discovery-state tests cover Bayesian ordering, unrated values, stable ties, AND/OR filters, search, URL handling, persisted reload, rejected updates, viewport behavior, camera restore, pending updates, and Reset. iOS UI tests cover selection/Back and empty search/Reset; they can also run on an iPad destination.

Before distribution: resolve source redistribution requirements, select signing identities and identifiers, configure support/privacy links and release metadata, and profile representative physical devices. Full VoiceOver navigation, large accessibility text, keyboard-only Mac use, narrow iPad multitasking, and Apple basemap offline failures still require manual release QA. Builds and functional tests do not establish FPS, memory, or launch-time guarantees.

### Checks run on 2026-10-12

Using Xcode 27.2 and the installed iOS 27 simulator runtime:

- Swift package: 10 domain/storage tests passed (plus four parameterized URL cases).
- Native macOS: build and seven discovery-state tests passed, including a 1,705-venue fixture.
- iPhone 17 Pro: all three UI tests passed on the final implementation.
- iPad Pro 11-inch (M5): all three UI tests passed on the final implementation.
- XCTest screenshots checked for compact discovery/detail and tablet discovery layout.
- Git whitespace check passed. Native CI configuration was added but has not run remotely.

The simulator emitted SDK/runtime diagnostics; they are not app performance measurements. Physical-device profiling and the manual release checks above remain outstanding.

### Venue-only bundle update — 2026-10-12

The bundle now loads existing venue data by default. Two exporter tests verify accepted counts, deduplication, editorial/coordinate preservation, deterministic IDs/revision, and exclusion of every rating input. Three additional Swift tests cover alphabetical snapshots, required priors for future rated imports, and decoding all 1,705 bundled venues. Existing Bayesian tests remain in place. The original fictional-data screenshots and validation above describe the earlier implementation.

Validation for this update: two exporter tests and 13 Swift domain/storage tests passed; all seven macOS state tests passed; iOS and macOS builds succeeded. The targeted iPhone UI test verified real venue search/detail, the alphabetical label, and absence of scores and per-row rating placeholders. The final regenerated bundle also passed the three dedicated unrated-snapshot tests.

### Local test builds

Release builds are available locally under `native/build/test-release/`: `Caffeye.app`, `Caffeye-macOS.zip`, and `Caffeye-iOS-Simulator.zip`. These generated artifacts are ignored by Git. The macOS app uses ad-hoc signing for local testing; the simulator archive cannot be installed on a physical iPhone/iPad. Physical devices require a development team, and external distribution requires signing and release setup.

### Review verification — 2026-10-12

On the final source, the export freshness check and two Python tests passed; all 13 shared Swift tests and seven macOS state tests passed; all four UI tests passed on both iPhone 17 Pro and iPad Pro 11-inch (M5). The macOS and generic iOS simulator Release builds also passed. The visible macOS franchise toggle was manually checked in both directions (970 ↔ 1,705 full-region results). Compact discovery/detail screenshots were inspected. XcodeGen regeneration produced no project changes, and Git whitespace checks passed. Remote CI results belong to the pull request; these are local checks.

### Review follow-ups — 2026-10-12

Merged the latest `origin/main`. Added snapshot search indexes, cached filtered/viewport results, counts refreshed per dataset/franchise scope, active-window macOS menu commands, sidebar scrolling after map selection, and a compatible modern Apple Maps action. Three new state regressions cover edited search metadata with staged lists, scope counts, and pin scroll targets.

Validation: export freshness and both Python tests passed; all 13 shared Swift tests and 10 macOS state tests passed; all four UI tests passed on both iPhone and iPad. Debug and Release builds passed for macOS and the iOS simulator. Manually verified macOS File import, View Reset, Reset with search focused, and an initially offscreen venue's sidebar selection after clicking its map pin. Updated local release artifacts are under `native/build/review-followups/`, including `Caffeye.app` and platform ZIPs. These checks establish behavior, not device performance measurements.

## Resilience, accessibility, and release preparation

Updates use an ephemeral HTTPS session, refuse credential-bearing URLs and insecure redirects, enforce request/resource timeouts and the 20 MB stream limit, and support cancellation from the discovery header. Saved/imported files use bounded reads; normalization also stays within the reload limit. Corrupt caches fall back to the bundled data, and failed imports/updates retain the current snapshot. MapKit loading failures show that map imagery is unavailable while venue data remains usable.

Detail selection dismisses the search keyboard without clearing the query. Detail and section titles are accessibility headings; Back requests focus on the originating row, or the results heading when filtering removes it. Accessibility-sized text wraps the franchise label, uses a shorter status label with the full spoken description, stacks count/order labels, and reduces the compact map height. XCTest checks descriptions and large-text navigation; full device VoiceOver/rotor and hit-target/contrast QA remain release work.

Field source overrides now distinguish curated coordinate sourcing and work-note sourcing; omitted overrides inherit record provenance. Verification dates are never fabricated. The same provider-neutral schema still accepts snapshots without these optional fields.

See [`release/README.md`](release/README.md) for snapshot source inventory, exact-hash release prerequisites, the known UserDefaults privacy declaration, reproducible test packaging with alternative snapshots, measured Release domain benchmarks, and Instruments signposts. The default venue data has no new redistribution approval. These tools prepare evidence and local builds; they do not authorize distribution.

Validation for this hardening update: five Python tests, 20 shared Swift tests in four suites, and 12 macOS tests in two suites passed. All five UI tests passed on both iPhone and iPad; after the final text-layout refinement, the large accessibility text test passed again on each platform and the iPhone screenshot was inspected. Release packaging passed for macOS and the simulator, including an alternate fictional snapshot on macOS. The default package passed dataset-hash and privacy-manifest checks; release preflight correctly remained blocked on human reviews, metadata, and production signing. The domain benchmark and a verified macOS Time Profiler capture are documented separately with their measurement limits. Current local test artifacts are under `native/build/hardening-release/`.
