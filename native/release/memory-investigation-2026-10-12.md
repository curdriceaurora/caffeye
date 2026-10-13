# macOS discovery memory investigation

Profiled the ad-hoc Release app from `47bc6ec`, with the bundled 1,705 venues and isolated storage, on macOS 27.2 / Xcode 27.2. Executable and dataset hashes are in the accompanying JSON. These are short developer measurements, not production memory budgets or device results.

## Findings

| Checkpoint | VM physical footprint | Live heap bytes | Reported leaks |
| --- | --- | --- | --- |
| Stack-logged interaction run | 519.7 MiB in memory graph (520.7 MiB in nearby VM snapshot) | 219,866,384 | 174 / 11,136 bytes |
| Separate settled zero-result run | 286.1 MiB | 138,990,505 | 74 / 3,552 bytes |

The first run exercised three franchise/zoom/reset cycles and an attempted pan. Its graph overlapped Reset, so it cannot establish zero-result retention. The second exercised one franchise/zoom/reset cycle, then left an unmatched search at zero results before capture. Its RSS samples ranged from about 307 to 414 MiB. RSS and physical footprint are different metrics; neither should be compared directly with live allocated heap bytes. The first run requested malloc stack logging; instrumentation, accessibility inspection, tile caching, and different interaction histories make these runs unsuitable as a before/after optimization comparison.

The stack-logged graph identifies large VectorKit allocations for layer data and geometry, plus map rendering zones and CoreAutoLayout allocations. The separate graph contains one `AppModel`, one `DiscoveryState`, and one map coordinator, with three venue-array storage allocations totaling about 2.3 MiB. These counts do not demonstrate an accumulating set of app models or snapshots.

At zero results, the second graph still contains 2,079 `MKMarkerAnnotationView` objects (3,193,344 directly allocated bytes) and 865 `VenueAnnotation` objects (442,880 directly allocated bytes). A sampled annotation has references through a marker view's `_annotation`, MapKit's annotation manager, and cluster annotations. The graph also reports coordinator dictionary paths; conservative pointer scanning and allocation timing mean these paths alone cannot establish occupied dictionary entries or a retain cycle. Direct object sizes exclude their referenced object graphs.

The first leak scan reports AppKit `NSAccessibilityCustomAction` objects and blocks, with allocation stacks through AppKit accessibility action enumeration. The second reports 74 blocks. Those few KiB do not explain the observed hundreds of MiB. This is not proof that the app or frameworks are leak-free.

**Assessment:** evidence supports substantial map rendering/view retention and allocator overhead. It does not establish that all growth is tile caching, that it is bounded over prolonged use, or that app heap retention is absent. No runtime optimization was made from this incomplete diagnosis.

## Instruments limitation

Attached Allocations+Leaks and a separate Allocations attempt failed to finalize within bounded waits. A launch-based attempt resolved another installed Debug copy and reported `_lockKPerf: could not lock kperf`. A uniquely named/re-signed local copy resolved the correct executable but stalled during recorder startup with a stopped child process. These incomplete recordings are excluded from performance evidence. Only processes created for these attempts were terminated; earlier user app instances were left alone.

Usable evidence comes from `vmmap`, `leaks` memory graphs, `heap` type inventories and reference tracing. It is **not a completed Instruments Allocations/Leaks analysis**. Raw graphs and logs remain local under `native/build/memory-investigation/` and `native/build/memory-retry/`; their contents can include environment/process details and should be reviewed before sharing.

## Repeatable capture and remaining diagnosis

```sh
python3 native/scripts/profile_memory.py \
  --app native/build/hardening-release/macos/Caffeye.app \
  --output native/build/memory-session-new --duration 90 --stack-logging
```

The script verifies the directly launched executable, takes initial/final heap and VM snapshots, samples RSS during the interaction interval, records tool exit codes, and terminates its own app. It does not automate UI interactions or run Instruments. Output must be a new directory. A separate 10-second idle run validated this capture path; it is a tooling smoke check, not another interactive experiment.

For the next diagnosis, obtain a successful Instruments session, mark allocation generations across identical pan/zoom/filter cycles, then settle and close the test window. Compare live annotation/view counts and retained allocation stacks after each generation and window teardown. Use an otherwise identical map-disabled control to isolate SwiftUI/list/storage from MapKit. Repeat on physical iPhone/iPad before setting budgets. The recording failure and retained-view behavior remain open investigations.
