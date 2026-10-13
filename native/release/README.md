# Native release preparation

The branch is an engineering milestone. None of these tools authorizes source redistribution, uploads a build, configures an Apple account, or establishes full release compliance.

## Reproducible local test builds

```sh
python3 native/scripts/build_test.py
# Use your own reviewed snapshot without changing the checked-in development bundle:
python3 native/scripts/build_test.py --snapshot /absolute/path/to/snapshot.json --output native/build/custom-test
```

The script validates the snapshot with the same Swift runtime decoder, builds Release targets, substitutes the selected data in the packaged app, signs the Mac app ad hoc, and creates Mac/simulator ZIPs plus `build-info.json` with toolchain, commit/dirty state, and artifact/dataset SHA-256 hashes. This is a local-testing workflow. Simulator apps cannot be installed on physical devices. Source permission is not inferred from validation or successful builds.

## Dataset review and preflight

```sh
python3 native/scripts/audit_snapshot.py native/Caffeye/Resources/venues.json
python3 native/scripts/release_preflight.py \
  --snapshot native/Caffeye/Resources/venues.json \
  --approval native/release/approval.example.json \
  --app native/build/hardening-release/macos/Caffeye.app
```

The example intentionally has no approvals; the preflight exits 1 and reports failed prerequisites. Copy it into a private review workspace and attach real review evidence before distribution. Evidence paths are relative to the approval file. Approval is tied to the exact dataset bytes; any dataset change requires re-review. Evidence presence cannot establish that a document is legally valid or that a QA report is complete.

The checker verifies evidence presence, HTTPS support/privacy URLs, dataset hashes, the required-reason manifest entry, and a verified production signing authority. It rejects ad-hoc local signing. It is a minimum prerequisite check, not notarization, App Store acceptance, certificate/profile expiration validation, or permission to ship. The checked-in Google-derived bundle has unresolved redistribution requirements.

`dataset-inventory.json` lists record and field sources for the current bundle. Field overrides identify curated Apple geocoding and separately sourced work notes; other fields inherit record provenance. Coordinate-specific verification dates were not recorded and are not fabricated. Imported snapshots may omit field overrides, retaining the record source. No records are declared independently sourced merely because their schema changed or ratings were removed.

## Performance evidence

```sh
python3 native/scripts/benchmark.py --output native/build/benchmark.json
```

`benchmark-2026-10-12.json` records measurements on this Mac using a Release domain harness, with toolchain, source/dataset hashes, iterations, median/p95 times, and process peak RSS. The harness measures decoding/validation, ranking, search-index construction, and one multiword search. It excludes SwiftUI, MapKit rendering, cold app launch, GPU frames and device battery cost. Its peak RSS is the CLI process, not the app's memory footprint. It supplies a reproducible baseline, not a guarantee or an iPhone/iPad result.

`mac-profile-2026-10-12.json` records a separately verified Release macOS executable with the bundled 1,705 venues and isolated storage. A 10-second attached Time Profiler capture succeeded; 15 once-per-second RSS samples reached 462,143,488 bytes (about 441 MiB). This is one short idle discovery run, not an allocation diagnosis or a memory budget. The earliest sample precedes initialization. Investigate retained allocations and repeated map interactions before setting performance targets. Launch-template attempts resolved another installed app copy and were excluded; the accepted capture attached to a PID whose executable path was checked directly. Raw traces stay local.

The follow-up [memory investigation](memory-investigation-2026-10-12.md) records VM/heap/leak evidence, map-view and annotation references, and the unsuccessful Instruments recording attempts. It does not establish a completed allocation diagnosis or a memory fix. `native/scripts/profile_memory.py` provides a bounded, repeatable local heap/VM capture workflow.

For real app profiling, build Release and use Instruments **Time Profiler**, **Allocations**, and **Points of Interest**. Filter signposts by subsystem `com.caffeye.native`: `Load snapshot`, `Filter venues`, and `Map annotations`. Signposts include phase names only, not queries, venue names or coordinates. Record device model, OS, toolchain, dataset hash, cold/warm launch conditions, duration, memory before/after repeated pan/zoom, and representative category/search/franchise operations. Record Instruments traces locally; do not commit them.

## Release QA evidence still required

- Physical iPhone/iPad: cold and warm launch, 1,705 annotations, sustained pan/zoom/clustering, memory and thermal behavior; retain traces and measured conditions.
- VoiceOver: discover filters and counts, select individual/cluster pins, traverse detail headings, activate links, and Back to the originating row. Automated label audits are a subset of this review.
- Accessibility text sizes, portrait/landscape, keyboard-visible discovery, narrow iPad windows/Stage Manager, Mac keyboard-only use and two independent windows.
- Airplane mode after launch and after restart, failed/expired basemap tiles, valid/malformed update endpoints, interrupted updates and cancellation. Venue data must remain available even when map imagery is unavailable.
- Production provisioning/signing, required privacy disclosures and SDK review, support/privacy pages, distribution metadata, and notarization/App Store review appropriate to the chosen channel.

See [privacy-api-inventory.md](privacy-api-inventory.md) for the current API review. Do not mark these gates passed from simulator tests alone.
