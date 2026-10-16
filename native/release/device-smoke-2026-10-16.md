# Physical-device discovery findings — 2026-10-16

## Environment and original result

SRA-Phone: iPhone 14 Pro, iOS 27.2 (24B5099f), Xcode 27.2 (27B5028f).
Development-signed Debug app built from `cc2cb6f`, with local Xcode signing/scheme changes. Seven selected device UI tests produced five passes and two failures.

Passed: franchise counts/filtering, rotation and Back, empty search/Reset, listing selection/Back, and Show all while detail is open.

Failures:

- `testBundledVenuesWithoutRatings`: exceeded its 120-second allowance during accessibility snapshots. A five-second XCTest stackshot shows Caffeye's main thread spending nearly all sampled time in accessibility snapshot handling and `MKMapViewAccessibility.accessibilityElements` enumeration. This is evidence for the accessibility bottleneck; it is not an allocation/leak diagnosis or proof of a general touch-UI hang.
- `testStreetZoomShowsIndividualPinsAndRegionalZoomRestoresClusters`: failed to open detail before reaching map assertions. The row occupied y=447–564 while the active search controls occupied y=473–511, overlapping its center tap. The original run provides no hardware evidence for individual-pin or cluster restoration behavior.

## Corrections

- iOS uses an `MKMapView` subclass whose accessibility container returns rendered, visible annotation views directly, ordered by screen position. It retains MapKit's native non-marker accessibility elements, including its virtual Legal link, and caches those elements until map size changes. This avoids repeated deep enumeration of MapKit's internal hierarchy. Pins and clusters remain accessible and use their existing labels/delegates; distant annotations remain in the map's data model.
- An initial visible-view implementation omitted the virtual Legal link. A newly added attribution assertion failed on both device and iPad, catching that regression. The native-element cache correction now passes that assertion on both the phone and iPad simulator; the failed intermediate attempts are not passing evidence.
- iOS search explicitly uses the native navigation-bar drawer. The street-pin regression now also asserts that active search does not cover the target row's center before tapping it. It still requires real rendered individual pins before manual zoom and regional cluster selection after Back.
- UI-test launches disable UIKit animations. The first accessibility prototype showed snapshots around 50–120 ms in observed entries, then XCTest logged a 60-second animation-completion wait during search. These are observations from that prototype, not a general latency guarantee for the final container. That attempt was interrupted after the 120-second test allowance was exceeded; it is not counted as passing. Normal app launches keep animations enabled.

## Validation of corrections

- Final-source iPad Pro 13-inch (M5), iOS 27.0 simulator: all three selected UI tests passed (`testBundledVenuesWithoutRatings`, `testAccessibleDiscoveryAndLargeTextDetail`, `testStreetZoomShowsIndividualPinsAndRegionalZoomRestoresClusters`), including the native Legal-link assertion. This checks both the native search placement and rendered accessible pins/clusters, plus the large-text label audit.
- macOS: all 32 app-hosted Swift tests passed.
- Intermediate physical-device rerun: all nine selected journeys passed in 131.8 seconds after unlock, before the additional attribution assertion was introduced. This includes all seven original journeys plus large-text accessibility labels and cluster-member selection. It is a historical checkpoint, not the final-source validation.
- Final-source physical-device run: **all four affected tests passed**, zero failures: real bundled data with accessible native Legal link (28.572 seconds), large-text accessibility, cluster-member selection, and street pins. The street-pin test reached and passed the individual-pin assertions before manual zoom, closest zoom, and regional cluster selection after Back. The original full-data test exceeded 120 seconds; the final one completed in 28.572 seconds. This is a test-duration comparison, not a general app performance budget.
- The ordinary full-data app was relaunched on SRA-Phone without UI-test arguments after testing. Normal UIKit animations remain enabled.

## Local evidence

Ignored artifacts (not uploaded or committed):

- `native/build/sra-phone-smoke-20261016.xcresult`: original 5-pass/2-failure device run.
- `native/build/sra-phone-fixes-first.xcresult`: intermediate attempt, interrupted after animation-wait timeout.
- `native/build/device-fix-ipad.xcresult`: three passing iPad tests.
- `native/build/sra-phone-fixes-verified.xcresult`: nine passing intermediate physical-device tests.
- `native/build/sra-phone-final.xcresult`: four passing final-source physical-device tests.
- `native/build/device-fix-ipad-final.xcresult`: three passing final-source iPad UI tests.
- `native/build/sra-phone-attribution-verified.xcresult` and `native/build/device-fix-attribution-ipad.xcresult`: failed intermediate attribution assertions, preserved as failure evidence.
- `native/build/sra-phone-fix-search.trace`: completed 10-second physical-device Time Profiler capture during the animation wait. It contains one CPU time-profile sample and does not establish a CPU hotspot or memory diagnosis.
- An earlier by-name trace stopped after 1.19 seconds when the app exited during timeout cleanup; a PID-based attempt failed. Neither is counted as a completed diagnosis.

Physical spoken VoiceOver/rotor navigation, sustained Allocations/Leaks/GPU/thermal work, degraded basemap networking, and production distribution signing remain open. Simulator checks and observed snapshot timings do not close those gates.

## Physical iPad follow-up

Tested runtime source `dcbff78` on a physical iPad (A16), iPadOS 27.0 (24A437), using the existing local development signing configuration. **All 10 selected UI tests passed**, zero failures, in 156.3 seconds. No runtime source or test changes were needed for this pass.

| Journey | Duration |
| --- | ---: |
| `testAccessibleDiscoveryAndLargeTextDetail` | 12.209s |
| `testBundledVenuesWithoutRatings` | 21.027s |
| `testClusterShowsSelectableMembers` | 8.697s |
| `testFranchiseToggleUpdatesResultsAndCategoryCounts` | 22.327s |
| `testMapViewportFilteringAndShowAllRecoverMatches` | 16.210s |
| `testRotationPreservesSelectionAndBackNavigation` | 12.851s |
| `testSearchEmptyStateAndReset` | 9.630s |
| `testSelectionAndBack` | 8.928s |
| `testShowAllRemainsReachableWhileVenueDetailIsOpen` | 13.082s |
| `testStreetZoomShowsIndividualPinsAndRegionalZoomRestoresClusters` | 31.335s |

The real-data flow includes the accessible native Legal-link assertion. The street-pin flow verifies that active search does not cover the row's center, then verifies individual colocated pins before manual zoom, closest zoom, and regional cluster selection after Back. Fictional fixtures supply deterministic assertions for the other flows; this does not claim exhaustive venue-by-venue testing.

Discovery and venue-detail screenshots from this physical iPad were visually inspected: search is above the results, the wide sidebar/map/detail layout is present, Show all and Back are visible, and the selected venue displays an individual pin. The normal app was relaunched without test arguments afterward, restoring normal animations and the real bundled dataset.

Local evidence remains ignored and is not uploaded:

- `native/build/physical-ipad-smoke-20261016.xcresult`
- `native/build/physical-ipad-smoke-summary.json`
- `native/build/physical-ipad-screenshots/`

This pass covers rotation and automated large-text/label checks. It does not establish manual spoken VoiceOver/rotor coverage, narrow Split View/Stage Manager behavior, network degradation behavior, or sustained Instruments memory/GPU/thermal acceptance.
