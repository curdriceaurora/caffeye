# Native UI flow QA matrix

Prepared 2026-10-13 from the currently reachable SwiftUI UI and test sources. This document combines a flow inventory with the validation checkpoint below. Inventory-time gaps are retained to distinguish the original coverage from later additions. Test names below initially identify tests present at inventory time; the integrating QA run must record new mappings and actual outcomes before claiming a flow passed.

## Scope and test contracts

Target iPhone compact portrait/landscape, iPad regular width and narrow Split View, and macOS wide/narrow windows. Width 760 points changes from a list beside the map/detail workspace to a map above a list replaced by detail. macOS uses native List selection; iOS uses row buttons. Both paths must be exercised.

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
| M07 | Select row; pan while detail open; choose another venue (wide); Back | Wide sidebar tracks viewport; compact browsing list restored; Back restores first browsing camera | State `selectedViewport`, `cameraRestoration`; UI gap |
| M08 | Rapidly select pin/row/cluster and Reset repeatedly | Final UI matches last intended action; no duplicate detail, stale cluster or crash from queued map callbacks | State `mapCallbackLifetime`; interaction stress gap |
| M09 | Fail basemap loading; continue search/filter/select; allow recovery | “Map imagery unavailable” appears then clears; venue list/detail remain usable | Delegate source only; controlled callback/state gap; real network manual |
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
| W02 | Resize across 760-point boundary repeatedly; iPad narrow Split View and macOS narrow/wide | Same selected venue, search/filter state and usable navigation; no duplicate row/detail | Gap; physical iPad Stage Manager manual |
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
| macOS UI | `testNarrowWindowKeepsSelectedDetailAndBackUsable` | W02 wide→compact with selected detail, D01 |
| App-hosted Swift Testing | `finiteFilterCombinations` | F01–F05: all 2,048 category/feature/franchise configurations against fixed demo ID classifications; `matches`, `rows`, and `browsingRows` retain snapshot rank order |
| App-hosted Swift Testing | `composedFiltersSearchAndViewport` | S02, S03, F04, F05, F08, M01: mixed-case multiword/whitespace query, editorial query, zero result, camera-local subset, scope counts and Reset; both franchise states |

Remaining uncovered UI assertions include controlled startup failure, foreground resume, direct individual-pin activation, rapid callback/Reset ordering, rendered missing-metadata fixtures, complete bottom-of-detail traversal/external handoff, full spoken VoiceOver/rotor/focus, dark/contrast appearance, all layout-transition states, native arrow-key navigation, menu-click commands and multiple-window command targeting. Treat these as explicit follow-up work or manual boundaries, not implicitly passed flows.

## Sequence coverage and evidence recording

Prioritize these composed journeys in addition to isolated controls:

1. Fresh launch → franchise on → two types → useful-for intersection → multiword search → detail → Back → clear search → Reset.
2. Narrow viewport → empty local list → Show all → pin → Back → cluster → Close cluster → filter → Reset.
3. Open detail → retaining filter → excluding filter → recovered list → another detail → Reset.
4. Selected detail → rotate/resize across layout boundary → scroll bottom → Back → search again.
5. Real bundle → named search → ratings-omitted detail → Back → franchise scope → Reset.

For each actual run record platform/destination, source revision/dirty state, named test functions, result bundle/log, pass/fail and any fix/re-run. Screenshots should show discovery, active filter summary, empty state, detail top/bottom, and largest text. A test blocked by MapKit readiness or native menu querying is a recorded gap until repaired; do not silently replace interaction assertions with state-only tests.

## Source-audit risks and boundaries

* **Queued map transitions:** delegate callbacks publish on the next main-loop turn. A select/cluster callback queued before Reset could execute afterward. Lifetime tests establish released coordinators are not retained; they do not establish last-action ordering. Exercise rapid pin/cluster/Reset transitions and add a deterministic ordering regression if reproduced.
* **Layout transition:** compact results use stable `browsingRows`; wide results follow the selected camera. Verify selection survives layout changes and Back restores correct browsing context, rather than merely checking that some row exists.
* **External actions:** URL validation checks link eligibility, not correct live destinations or successful Maps/browser handoff. Automated tests can assert controls and invocation inputs; actual external apps and network results remain separate manual checks.
* **Map geometry:** Show all uses padded bounds and map camera limits. State geometry tests do not prove MapKit has settled to those bounds on every window/device size. UI tests must wait for observable row/result changes instead of fixed sleeps.
* **Announcement/focus:** an incremented notice or accessibility description audit does not prove VoiceOver speech, rotor order or focus restoration. Keep this boundary explicit.
* **Failure injection:** startup unavailable/pending-snapshot banners cannot be reached through ordinary hidden import/update controls in this build. Test injection can cover defensive UI without presenting removed storage capabilities to users.
* **Crash confidence:** successful bounded tests establish those journeys only. They do not justify “crash-free,” all-sequence coverage, physical-device performance or release compliance. Physical hardware, basemap network failures, distribution signing and dataset permissions remain open release work.

## Validation checkpoint — 2026-10-13

Three QA subagents inventoried flows and implemented tests. The current source contains 22 iPhone/iPad UI tests, 13 macOS UI tests, 24 hosted Swift tests, and the unchanged 23 shared Swift tests. Ten Python tests and export freshness passed. The state suite covers all 2,048 finite filter combinations against independently classified synthetic venue IDs.

All 22 simulator flows passed across the main 20-test runs and targeted reruns after harness fixes, on iPhone 17 Pro and iPad Pro 11-inch (M5). This is combined evidence, not a single clean 22-test run. Safari address and return-state checks and Apple Maps foreground/return-state checks passed; live Maps destination and remote webpage content are not established. Eleven Mac UI tests, new-scene isolation and all 24 hosted tests passed in earlier bounded runs. Final desktop resize/arrow navigation checks remain open: a later rerun reported a startup SIGTRAP in SwiftUI ViewListTree/OutlineListCoordinator during list teardown. This checkpoint is not a crash-free or release-ready claim.

Implemented app fixes keep the filter toolbar visible while searching, put Close cluster in the section header, use singular result text, reject stale queued pin/cluster selections after Reset, and retain the latest rapid queued pin selection. Test harness fixes target the native switch thumb, preserve the query before pin selection, use Show All for offscreen search matches, scope detail assertions away from the list legend, and handle Safari's collapsed/editable address controls. Native tiling and saved window size require explicit setup for desktop layout tests.

The native CI workflow now runs the real Mac UI target and independent iPhone/iPad UI jobs and retains result bundles. These new jobs have not yet been verified remotely at this checkpoint. Full spoken VoiceOver/rotor, physical iPad Split View/Stage Manager, controlled unavailable startup, real basemap expiry/failure and sustained rapid interaction remain explicit QA boundaries.
