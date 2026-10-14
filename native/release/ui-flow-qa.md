# Native UI flow QA matrix

Prepared 2026-10-14 from the currently reachable SwiftUI UI and test sources. This document combines a flow inventory with the validation checkpoint below. Inventory-time gaps are retained to distinguish the original coverage from later additions. Test names below initially identify tests present at inventory time; the integrating QA run must record new mappings and actual outcomes before claiming a flow passed.

## Scope and test contracts

Target iPhone compact portrait/landscape, iPad regular width and narrow Split View, and macOS wide/narrow windows. On iOS, width 760 points changes from a list beside the map/detail workspace to a map above a list replaced by detail. macOS keeps a native split view and List selection at every supported width; iOS uses row buttons. Both paths must be exercised.

The reachable UI has search, Type and Useful for menus, Include franchise stores, Reset, map pan/zoom/pins/clusters, result rows, Show all matches, detail/Back, detail external actions, and macOS active-window commands. Import, download/update controls, data settings and offline capability messaging are intentionally hidden. No current-location button or location-permission flow exists: location filtering means the **visible map region**, not GPS distance. Do not invent QA steps for removed controls.

Categories combine with OR; useful-for features combine with AND; search requires every case-insensitive whitespace-separated word. Franchise inclusion gates all results. Menu counts describe the complete dataset within franchise scope, not the current search, viewport or other facets. A selected venue can remain selected outside the panned viewport, but filters excluding it must dismiss detail. Back restores the original browsing region, even after switching venues.

Use `--ui-testing` for isolated fictional demo data and `--ui-testing --bundled-venues-testing` for the real, unrated bundle. Assert named venue IDs and expected rows wherever possible; merely asserting that some row exists can miss incorrect filtering. Keep real-bundle assertions independent of frequently changing real business hours or links. The demo includes all six categories, franchise entries, colocated venues, work/meeting/late/midnight attributes and fictional scores. Missing metadata, absent ratings with priors, unsafe links and failure paths require dedicated fixture/state tests; they cannot be established from the happy-path demo alone.

There are 64 category subsets × 16 feature subsets × 2 franchise states = **2,048 finite filter combinations** (empty category set means all). These are suitable for exhaustive deterministic domain/state assertions against an independent expected predicate. UI automation should exercise every control and representative intersections, rather than repeat thousands of menu taps. Search text, camera positions, window sizes and action sequences are unbounded; cover equivalence classes and transition boundaries rather than claim every possible sequence was run.

## Flow matrix

“Gap” below means no matching end-to-end UI assertion was present at inventory time. State/presentation tests are supporting evidence, not a replacement for the rendered interaction.

| ID | Concrete steps | Required outcome | Initial automation / gap |
| --- | --- | --- | --- |
| L01 | Launch demo with a fresh isolated store; wait for rows | Fictional-data notice, regional map, indie defaults, meaningful result count and enabled controls; no crash | Existing tests launch demo, but lack full default-state assertions |
| L02 | Launch real bundled venues | Ratings-omitted alphabetical legend; no synthetic score; indie defaults | `testBundledVenuesWithoutRatings` partially covers |
| L03 | Launch with malformed saved data | Bundled fallback remains usable and no unrecoverable blank screen | `AppModelTests.corruptCacheRecovery`; rendered startup gap |
| L04 | Make bundle/load unavailable via controlled fixture; dismiss alert | Venues-unavailable alert is dismissible; controls remain safe with no snapshot | Gap; requires injection, not deleting installed resources |
| L05 | Background/foreground and relaunch after filtering/selecting | Resume does not crash or duplicate UI; fresh launch defaults are explicit (filter persistence is not implemented) | Gap |
| S01 | Search a venue name; select result; Back | Correct detail identity; keyboard dismisses on selection; query retained; browsing rows restored | Existing real-bundle test checks keyboard; demo Back test checks a row |
| S02 | Search area, editorial drink, uppercase and multiple words with repeated whitespace | Same matching semantics as documented; every word required | `CoreTests.search`, `DiscoveryStateTests.indexedUpdates`; UI gap |
| S03 | Search nonexistent text | Empty-state explanation appears; no stale rows/pins/detail | `testSearchEmptyStateAndReset` checks empty state |
| S04 | Clear text using native search clear control | Results repopulate; no unnecessary reset of other filters | Gap |
| S05 | Cancel compact search or dismiss keyboard, then use Reset | Toolbar becomes usable; Reset clears query, filters and selection | Existing empty-search Reset test partially covers |
| S06 | Change search while a detail is selected, with retaining and excluding queries | Retaining query keeps detail; excluding query returns to usable list; no stale selected pin | State `excludedSelectionAnnouncement`; UI gap |
| F01 | Open Type; toggle each of six categories on and off | Correct glyph/name/count and selected check state; rows belong to chosen category; all-off restores all categories | `CoreTests.filters`; UI gap |
| F02 | Select two categories, then Type → All | Union of categories, then categories cleared; feature/search/franchise settings retained | UI gap |
| F03 | Toggle each of four Useful for features | Correct emoji/name/count; matching rows meet actual attribute; toggle-off restores prior set | `CoreTests.filters`; UI gap |
| F04 | Combine Work-friendly + Meeting room; Open late + Until midnight; incompatible category + feature | Features intersect; redundant late/midnight intersection works; zero results remain recoverable | Domain partial; UI gap |
| F05 | Toggle Include franchise stores on/off | Franchises appear/disappear; independent rows remain; scope menu counts change; active category/features persist | `scopeCounts`; UI gap |
| F06 | Select franchise detail; turn franchise inclusion off | Detail dismisses; list remains usable; no dangling selected annotation | State general exclusion coverage; UI gap |
| F07 | Change Type/Useful for while detail or cluster open | Filtered-out detail dismissed; cluster members cleared; summary matches toggles | State general coverage; UI gap |
| F08 | Combine search + category + feature + franchise; Reset twice | First Reset restores indie defaults, empty query, no summary/selection/cluster, regional map; second Reset is harmless | State `reset`; UI partial |
| F09 | Inspect filter menu and active summary after selecting each filter | Emojis preserved, names legible, native selected state, count contract consistent | UI gap; visual review required |
| M01 | Pan/zoom map to include only part of the matches | List and “in view” count follow camera; offscreen map candidates retained; no crash on repeated gestures | State `viewport`; UI gap |
| M02 | Pan to region with no rows while global matches exist; tap Show all matches | Recovery button visible; camera fits global matching set; rows return | State `showAllMatches`; UI gap |
| M03 | Search globally nonexistent result | No misleading Show all 0 action; empty-state recovery instructions | State `showAllEmpty`; UI gap |
| M04 | Tap a distinct individual pin | Matching detail identity, selected row/scroll target and camera focus | State `pinScrollTarget`; direct pin UI gap |
| M05 | Tap cluster; inspect/select a named member | Member section appears with correct members; choosing member opens that venue | `testClusterShowsSelectableMembers` only checks any row |
| M06 | Tap cluster; Close cluster; reopen; change filters; Reset | Close removes member section without moving map; filters/Reset clear it; repeated use safe | UI gap |
| M07 | Select row; pan while detail open; choose another venue (wide); Back | Mac sidebar preserves context during camera focus, follows deliberate map gestures; Back restores first browsing camera | State `selectedViewport`, `cameraRestoration`; UI gap |
| M08 | Rapidly select pin/row/cluster and Reset repeatedly | Final UI matches last intended action; no duplicate detail, stale cluster or crash from queued map callbacks | State `mapCallbackLifetime`; interaction stress gap |
| M09 | Fail basemap loading; continue search/filter/select; allow recovery | “Map imagery unavailable” appears then clears; venue list/detail remain usable | Delegate source only; controlled callback/state gap; real network manual |
| M10 | Zoom from regional overview to the closest street view, then zoom out/Back | Individual venue pins replace clusters at street level, including colocated venues; regional clustering returns and selection remains coherent | Hosted, iPhone/iPad street-zoom, and Mac listing-map regressions |
| D01 | Open row, inspect top, Back; repeat another venue | Name/category/area/model correct; Back hittable; result identity/scroll context restored | `testSelectionAndBack` partial |
| D02 | Open rated fictional detail and scroll fully | Bayesian score/provenance, summary, known-for, hours, work/meeting/late sections and bottom actions readable | `VenueDetailTests.ratingStates`; rendered-scroll gap |
| D03 | Open real unrated detail | Ratings omitted; no weighted score, review count or misleading “No rating” | `testBundledVenuesWithoutRatings` |
| D04 | Open fixture with missing/blank hours, editorial, work and links; unrated venue with priors | Unknown-hours/work copy; no empty editorial sections, inferred public score or absent links | `VenueDetailTests.hours`, `missingEditorial`, `ratingStates`, `links`; rendered fixture gap |
| D05 | Scroll bottom; activate Apple Maps; return | Destination/name handed to Maps; app safely resumes with selection intact | UI action existence gap; actual external app handoff manual |
| D06 | Activate each valid Google Maps/Yelp/Website link; return; inspect absent/unsafe link fixture | Correct destination; absent/unsafe links omitted; no crash | Presenter `links`; external app/real URL manual |
| A01 | Largest supported accessibility text: discover, filter, select, scroll bottom and Back | Controls readable/hittable; no truncation blocking action; detail complete | `testAccessibleDiscoveryAndLargeTextDetail` checks description/top/Back only |
| A02 | VoiceOver traverse toolbar, rows, pins, cluster, detail headings; Back; exclude selected venue | Single meaningful row label, focus moves/restores appropriately, exclusion announcement actually spoken | Accessibility label audit/state request tests only; spoken delivery and rotor manual |
| A03 | Dark/light appearance and increased contrast on compact/wide layouts | Selected states, text and map labels discernible; no color-only critical distinction | Gap / visual QA |
| W01 | Rotate iPhone/iPad while browsing, searching, cluster open and detail open | Correct layout; active state retained; no inaccessible Back/Reset or crash | Gap |
| W02 | Resize iPad across 760-point boundary; resize macOS native split view narrow/wide | Same selected venue, search/filter state and usable navigation; no duplicate row/detail | Gap; physical iPad Stage Manager manual |
| W03 | On macOS click row; use arrow keys; Escape and Command-[ | Native selection updates detail; Back restores list; disabled Back when no selection | Prior manual reports exist; automated macOS UI gap |
| W04 | On macOS use View → Reset discovery / Shift-Command-R with search focused | Reset affects active window and clears search/filters/selection without crashing | State `reset`; macOS UI gap |
| W05 | macOS create second window; operate commands with alternating active windows | Command targets active discovery state; shared model does not cause duplicate loads or cross-window filters | Source contract; UI gap |
| H01 | Inspect toolbar, menus, detail and macOS commands | No import/download/data-settings controls or advertised offline capabilities | UI gap |

## Expanded automation mapping

The following named tests are written for this QA change. Their presence is not a pass result; use the integrating run's result bundles for execution status. The initial matrix above preserves the before-change gaps to explain the additional coverage. Several tests partially cover an ID; for example a description audit does not complete A02, and a single rotation does not complete all W01 states.

| Suite | Exact test name | Flow IDs addressed |
| --- | --- | --- |
| iOS UI | `testSelectionAndBack` | L01, D01 |
| iOS UI | `testSearchEmptyStateAndReset` | S03, S05 |
| iOS UI | `testClusterShowsSelectableMembers` | M05 |
| iOS UI | `testBundledVenuesWithoutRatings` | L02, S01, D03 |
| iOS UI | `testAccessibleDiscoveryAndLargeTextDetail` | A01; A02 description audit only |
| iOS UI | `testEveryCategoryCanBeSelectedAndAllRestoresResults` | F01, F02, F09 |
| iOS UI | `testCategoryUnionAndFeatureIntersection` | F02, F04, F08 |
| iOS UI | `testEveryFeatureAndCombinedLateNightFilters` | F03, F04, F08, F09 |
| iOS UI | `testFranchiseToggleUpdatesResultsAndCategoryCounts` | F05, F08 |
| iOS UI | `testSearchIgnoresCaseAndWhitespaceAndCanBeCleared` | S02, S03, S04 via text replacement, S05 |
| iOS UI | `testSearchCombinesWithCategoryAndResetClearsAllChoices` | S01, F05, F08 |
| iOS UI | `testChangingFiltersDismissesExcludedDetail` | F07, S03, F08 |
| iOS UI | `testClusterCanCloseAndReopenBeforeSelecting` | M05, M06, D01 |
| iOS UI | `testMapViewportFilteringAndShowAllRecoverMatches` | M01, M02 |
| iOS UI | `testStreetZoomShowsIndividualPinsAndRegionalZoomRestoresClusters` | M10: actual pinch, both known colocated pins, no actionable visible cluster, Back and real cluster selection |
| iOS UI | `testRotationPreservesSelectionAndBackNavigation` | W01 selected-detail rotation, D01 |
| iOS UI | `testDiscoveryHasNoOfflineControlsAndRelaunchStartsClean` | L05 fresh relaunch, H01 |
| macOS UI | `testKeyboardSearchSelectionBackAndReset` | S01, W03 keyboard Back, W04 shortcut |
| macOS UI | `testEscapeAndBackButtonDismissDetailsWithoutLosingSearch` | S01, D01, W03 Escape |
| macOS UI | `testEveryCategoryAndMultipleCategoryUnion` | F01, F02 |
| macOS UI | `testEveryFeatureAndCombinedCategoryIntersection` | F03, F04, S03, W04 shortcut |
| macOS UI | `testFranchiseFilterHidesSelectedFranchiseAndRecovers` | F05, F06, F08 |
| macOS UI | `testEmptySearchResetThenDetailHasUsefulInformation` | S03, D01, D02 top/content existence |
| macOS UI | `testClusterCloseAndMemberSelection` | M05 named member, M06 |
| macOS UI | `testBundledRatingOmissionAndNoDataManagementControls` | L02, D03, H01 |
| macOS UI | `testNarrowWindowKeepsSelectedDetailAndBackUsable` | W02 wide→narrow native sidebar with selected detail, D01 |
| iOS UI | `testIndividualMapPinOpensExactVenueAndReturnsToResults` | M04 direct pin identity |
| iOS UI | `testMissingVenueDataUsesHonestDetailFallbacks` | D04 missing metadata |
| iOS UI | `testWebsiteHandoffAndReturnPreservesDetailAndSearch` | D06 Safari URL/return state |
| iOS UI | `testAppleMapsHandoffAndReturnPreservesDetailAndSearch` | D05 foreground/return state only |
| iOS UI | `testDetailScrollToActionsAndBackRemainsReachable` | D02 bottom traversal, D01 Back |
| iOS UI | `testVerifiedExternalLinksAreReachableInDetail` | D06 action availability |
| macOS UI | `testMapPinOpensSameVenueDetailAsList` | M04 |
| macOS UI | `testMapPanFiltersSelectedSidebarAndRestoresBrowsingContext` | M01, M07 actual mouse drag while detail is selected; Back restores browsing rows |
| macOS UI | `testUnknownVenueFieldsAndValidExternalActions` | D04 missing metadata; D06 action availability |
| macOS UI | `testNativeListArrowNavigationAndMenuReset` | W03 arrows, W04 menu |
| macOS UI | `testNewWindowKeepsDiscoveryAndCommandsIndependent` | W05 active-scene command isolation |
| App-hosted Swift Testing | `streetClusteringBoundary`, `selectionUsesStreetCamera`, `streetZoomPreservesSelectionAndPendingSnapshot`, `streetZoomInvalidatesClusterSelection`, `deferredStreetRefreshUsesCurrentState` | M10 boundary, wide/narrow selected camera, identities/selection/staged data, rapid zoom/filter/Reset, obsolete-cluster callbacks; M08 callback ordering |
| macOS UI | `testListingSelectionShowsIndividualPinsAndBackRestoresClusters` | M10: select listing, verify both colocated pins and no visible cluster before manual zoom; Back and real regional cluster selection; window/map screenshot attachments |
| App-hosted Swift Testing | `showAllFromSelectedViewport` | M02, M07: Show all expands the selected sidebar; Back restores the original restricted region |
| App-hosted Swift Testing | `resetCancelsSelection`, `latestSelectionWins` | M08 deterministic delegate ordering; gesture stress remains manual |
| App-hosted Swift Testing | `finiteFilterCombinations` | F01–F05: all 2,048 category/feature/franchise configurations against fixed demo ID classifications; `matches`, `rows`, and `browsingRows` retain snapshot rank order |
| App-hosted Swift Testing | `composedFiltersSearchAndViewport` | S02, S03, F04, F05, F08, M01: mixed-case multiword/whitespace query, editorial query, zero result, camera-local subset, scope counts and Reset; both franchise states |

Additional tests below cover individual pins, missing metadata, bottom actions, external handoff, queued callback ordering, native arrows/menu Reset and independent scenes. Remaining boundaries include controlled startup failure, ordinary foreground resume beyond handoff, sustained rapid interaction, spoken VoiceOver/rotor/focus, dark/contrast appearance and every layout-transition state. Treat these as explicit follow-up work or manual boundaries, not implicitly passed flows.

## Sequence coverage and evidence recording

Prioritize these composed journeys in addition to isolated controls:

1. Fresh launch → franchise on → two types → useful-for intersection → multiword search → detail → Back → clear search → Reset.
2. Narrow viewport → empty local list → Show all → pin → Back → cluster → Close cluster → filter → Reset.
3. Open detail → retaining filter → excluding filter → recovered list → another detail → Reset.
4. Selected detail → rotate/resize across layout boundary → scroll bottom → Back → search again.
5. Real bundle → named search → ratings-omitted detail → Back → franchise scope → Reset.

For each actual run record platform/destination, source revision/dirty state, named test functions, result bundle/log, pass/fail and any fix/re-run. Screenshots should show discovery, active filter summary, empty state, detail top/bottom, and largest text. A test blocked by MapKit readiness or native menu querying is a recorded gap until repaired; do not silently replace interaction assertions with state-only tests.

## Source-audit risks and boundaries

* **Queued map transitions:** delegate callbacks publish on the next main-loop turn. Guarded callbacks and `MapInteractionTests.resetCancelsSelection`/`latestSelectionWins` now cover Reset ordering and latest queued pin selection; lifetime coverage separately checks released coordinators. Sustained real gesture stress remains a manual boundary.
* **Layout transition:** compact iOS results use stable `browsingRows` during selection; Mac preserves browsing rows for programmatic focus and follows the viewport after deliberate map input; regular iPad results follow the selected camera. Mac keeps the same native split view/List across widths to avoid tearing down the outline during live resize. Verify selection survives layout changes and Back restores correct browsing context, rather than merely checking that some row exists.
* **External actions:** URL validation checks link eligibility, not correct live destinations or successful Maps/browser handoff. Automated tests can assert controls and invocation inputs; actual external apps and network results remain separate manual checks.
* **Map geometry:** Show all uses padded bounds and map camera limits. State geometry tests do not prove MapKit has settled to those bounds on every window/device size. UI tests must wait for observable row/result changes instead of fixed sleeps.
* **Announcement/focus:** an incremented notice or accessibility description audit does not prove VoiceOver speech, rotor order or focus restoration. Keep this boundary explicit.
* **Failure injection:** startup unavailable/pending-snapshot banners cannot be reached through ordinary hidden import/update controls in this build. Test injection can cover defensive UI without presenting removed storage capabilities to users.
* **Crash confidence:** successful bounded tests establish those journeys only. They do not justify “crash-free,” all-sequence coverage, physical-device performance or release compliance. Physical hardware, basemap network failures, distribution signing and dataset permissions remain open release work.

## Validation checkpoint — 2026-10-13

Three QA subagents inventoried flows and implemented tests. At that checkpoint the source contained 22 iPhone/iPad UI tests, 13 macOS UI tests, 24 hosted Swift tests, and the unchanged 23 shared Swift tests. Ten Python tests and export freshness passed. The state suite covers all 2,048 finite filter combinations against independently classified synthetic venue IDs.

All 22 simulator flows passed across the main 20-test runs and targeted reruns after harness fixes, on iPhone 17 Pro and iPad Pro 11-inch (M5). This is combined evidence, not a single clean 22-test run. Safari address and return-state checks and Apple Maps foreground/return-state checks passed; live Maps destination and remote webpage content are not established. Eleven Mac UI tests, new-scene isolation and all 24 hosted tests passed in earlier bounded runs. Final desktop resize/arrow navigation checks remain open. XCTest reported a critical-process crash, but the available SIGTRAP report in SwiftUI ViewListTree/OutlineListCoordinator belongs to an older background app process, not either test target PID. It does not establish a crash in this QA build. This checkpoint is not a crash-free or release-ready claim.

Implemented app fixes keep the filter toolbar visible while searching, keep Close cluster above the scrolling list, use singular result text, reject stale queued pin/cluster selections after Reset, and retain the latest rapid queued pin selection. Test harness fixes target the native switch thumb, preserve the query before pin selection, use Show All for offscreen search matches, scope detail assertions away from the list legend, and handle Safari's collapsed/editable address controls. Mac keeps a native split view/List at every width and preserves browsing rows while the selection focuses the map, allowing arrow-key navigation. Deliberate map gestures still filter sidebar rows by the visible region, covered by `selectedViewport`. Desktop tests exit saved full-screen/tile state, use native Window menu resizing, and wait for actual width changes. The narrow test exercises selected detail, empty search and a cluster. The half-screen check requires a test display whose half-width is below 760 points; physical layouts on larger displays remain manual.

The native CI workflow now runs the real Mac UI target and independent iPhone/iPad UI jobs and retains result bundles. Its first remote run exposed duplicate macOS toolbar buttons, cluster/action accessibility differences, and iOS 26.2 menu wrappers and Safari address roles. Follow-up fixes are undergoing local and remote verification; these first runs are not green. Full spoken VoiceOver/rotor, physical iPad Split View/Stage Manager, controlled unavailable startup, real basemap expiry/failure and sustained rapid interaction remain explicit QA boundaries.


## Follow-up validation — 2026-10-14

At this checkpoint the source contained 14 Mac UI tests. The targeted Mac pan and narrow-window journeys both passed together (`macos-mouse-drag-1014.log`, 2 tests, zero failures). The earlier pan failure used XCTest's touch-event `press` API; the mouse-event `click(forDuration:thenDragTo:)` now drives an actual MapKit pan. Recorded geometry from the failed run kept the selected venue exactly centered, so that failure did not establish an event-monitor bypass. The earlier resize tree omitted the entire cluster section; generic accessibility container “Disabled” labels did not prove a global WindowServer disablement. Single pin/cluster clicks no longer arm camera movement, preserving the member section during subsequent resizing. No test-only gesture bridge was added.

All 14 Mac UI tests passed in one clean full run (`macos-full-1014.log`); that run also passed the prior 24 hosted tests. The subsequent Show all correction passed all 25 hosted tests (`macos-hosted-1014.log`), including its new restricted-region/selection/Show all/Back regression. The 23 shared Swift tests, export freshness and ten Python tests passed again. The targeted category-union/feature-intersection and Website handoff/return journeys passed on iPhone 17 Pro and iPad Pro 11-inch (M5) across targeted reruns (`iphone-targeted-1014.log`, `iphone-safari-1014.log`, `ipad-targeted-1014.log`, `ipad-safari-1014.log`); these are not single clean two-test runs because the first Safari assertions failed before the observed address roles were repaired. The final 25-test hosted rerun also configures the map before testing coordinator release, covering the new input-monitor ownership path. Remote CI on this follow-up remains to be checked. Safari checks read known address controls, normalize invisible formatting marks and compare the parsed host exactly; webpage text cannot satisfy the destination assertion. These checks do not establish successful remote page loading.


### SDK compatibility follow-up

CI on `9ccecf4` passed 25 hosted and 23 shared Swift tests, 11 of 14 Mac UI tests, and 14 of 22 UI tests on each simulator. The failures remain recorded in run `38619845726`. Mac recordings show enabled, visible MapKit annotation wrappers with finite bounds but no XCTest hit point, plus a recycled/offscreen duplicate of the named cluster row. The follow-up clicks observed marker centers inside the map/window, then requires the exact expected detail or member section. Member selection scrolls the native list and resolves a rendered row. Cluster members now appear once; remaining rows are labeled “Other venues in this view,” with a uniqueness regression assertion.

The seven simulator menu failures originate in toolbar accessibility wrappers whose hittability query fails or whose nested button has an infinite frame. The follow-up taps the identified wrapper's measured rectangle only after validating it against the navigation bar and app window, then requires the requested menu option and existing result/count assertions. Safari waits for the known address UI before comparing the exact host; foreground process state alone is not address readiness.

Mac QA explicitly activates the launched app and waits for its window, using AppKit's isolated-launch arguments rather than saved restoration state. Feature-branch PRs run the native workflow once; pushes to main retain post-merge verification. The Mac job has a 30-minute timeout. Follow-up targeted local runs and CI must be recorded before calling this source green.


### Street-level clustering requirement

The closest street view now uses individual venue pins. At camera distance at or below 1,500 metres, markers have no clustering identifier and use required display priority; farther views retain MapKit clustering. Selecting a listing explicitly sets a 1,000-metre camera distance: fitting a rectangle alone did not guarantee street scale across map aspect ratios. Only crossing the boundary refreshes annotations, preserving venue identities and selection. The refresh is deferred outside MapKit camera callbacks, removes views with their old identifiers intact and uses current filtered annotations; hosted testing caught an unsafe synchronous teardown before this correction. Obsolete cluster selections cannot reopen the member list after entering street view.

The current suite contains 23 simulator UI tests, 15 Mac UI tests and 30 hosted tests. The new UI journeys assert the rendered map immediately after opening a listing, before any manual zoom: both known colocated pins must be within the map, with no visible cluster. The simulator journey then pinches closer; both platforms use Back and reopen a real regional cluster. Hosted tests also cover wide/narrow aspect ratios, rapid zoom reversal, filters changing before a queued refresh and Reset superseding it.

All 30 hosted tests passed (`macos-deferred-cluster-hosted-1014.log`). Five targeted Mac UI tests passed together (`macos-rendered-street-1014.log`): listing-to-map, pin-to-detail, cluster member selection, selected-map panning and narrow-window navigation. The listing-map test passed again with window and map screenshot attachments (`macos-listing-screenshot-1014.log`); the exported window image was visually inspected and shows the individual coffee marker with no numeric cluster badge. The latest simulator test build passed. The five-flow simulator runs passed category/feature intersections, cluster close/reopen, late-night combinations and Safari return on both devices, but initially failed before the map assertion because caret-relative deletion produced `Demo1`. The helper now uses the native Clear text button, refocuses the field and asserts the exact replacement query. The listing/street-map regression passed on both iPhone and iPad after that correction (`iphone-street-refocus-1014.log`, `ipad-street-refocus-1014.log`). The case/whitespace/empty-query journey also passed on both devices (`iphone-search-empty-1014.log`, `ipad-search-empty-1014.log`), including UIKit's placeholder accessibility value for an empty field. Subsequent committed-source CI results remain to be recorded. Earlier failed attempts, including restored-window/focus issues and the repaired unsafe annotation teardown, are excluded from passing evidence.


### Committed-source CI checkpoint

On `2bacbcc`, run `38627806944` passed all 15 Mac UI, 30 hosted, 23 shared Swift and ten Python tests, export freshness/inventory checks and the generic simulator build. Web CI also passed. The full iPhone UI job reached the workflow's 20-minute limit, cancelling the test step; its incomplete result bundle is not a passing result. Simulator jobs now receive the same bounded 30-minute limit as the Mac job, allowing the expanded journeys to complete. Final simulator outcomes remain to be checked.


### iPad completion and follow-up

Run `38630951339` on `6120544` passed the full Mac job (15 UI, 30 hosted, 23 shared Swift and ten Python tests), web CI and all 23 iPhone UI tests. The iPad job completed all 23 tests: 20 passed, including the listing/street-map regression; three failed. This is not a green iPad suite.

The large-text recording shows the first row remained in a 360-point sidebar at the largest accessibility size and no detail opened after the tap. The revised iOS layout uses its existing full-width list/detail presentation for accessibility text on wide iPads too. The strengthened journey checks row width, a named venue and reachable Back; it passed on a local iPhone and 13-inch iPad. This fixes the demonstrated readability defect without claiming the narrow layout alone proves why the earlier tap was lost.

The Maps return failure coincided with its delayed system location prompt; the next test's default interruption handler denied it. The handoff journey now waits for that exact Maps prompt, chooses only “Don’t Allow” if present, verifies dismissal and then requires the same selected venue/search/Back state. It does not grant location access or accept terms. Safari's final failure hierarchy already contained the correct `example.com` address; enumeration retried stale static-text indices while Safari changed to a native field. The check now reads known native address fields first, avoids enumerating changing title children, retains exact parsed-host comparison and allows a bounded 20-second readiness wait. Full follow-up results remain to be recorded in the PR.
