# Native privacy API inventory

Reviewed app/core source on 2026-10-12. This inventory is a starting point for the shipping app's privacy review; signing, App Store labels, Apple SDK behavior, and distribution requirements still need owner review.

| Runtime use | Purpose and scope | Declaration/evidence |
| --- | --- | --- |
| SwiftUI `@AppStorage("snapshotEndpoint")` | Stores the user's optional update URL in this app's own preferences; no shared group or system preferences are read. | `PrivacyInfo.xcprivacy` declares UserDefaults reason `CA92.1`. |
| `FileHandle` and Foundation file reads/writes | Read bounded bundled/imported/local venue JSON and atomically replace app-owned storage. Security-scoped access covers user-selected imports. | The previous file-size metadata lookup was removed. No app code reads timestamps, available disk space, or file metadata for fingerprinting. Inspect the distribution privacy report for remaining linked APIs. |
| Ephemeral `URLSession` | Explicit user-requested HTTPS snapshot download; bounded size and duration; credentials in URLs and insecure redirects are refused. | No automatic polling, cookie persistence, analytics client, data upload, or embedded API key. Endpoint operators still receive normal network request metadata; review the chosen service. |
| MapKit and Apple Maps actions | Render the region and open a venue at its recorded business coordinates. | No user-location permission or live GPS access. Review Apple's service/SDK disclosures and external-link behavior for the chosen distribution channel. |
| OSLog signposts | Developer timing of snapshot load, filters and annotation reconciliation. | Phase names only; no query text, venue IDs, names or coordinates. With both `--ui-testing` and `CAFFEYE_PROFILE_READY=1`, the developer capture emits a stdout readiness marker containing the loaded venue count; normal app launches do not emit it. |

The manifest declares the known required-reason use. It does not invent App Store privacy labels or assert that all Apple services are data-free. There are no third-party binary SDKs in this project; the local Swift package is reviewed with the app.

Developer-only `CaffeyeTools` uses a monotonic clock and `getrusage` for benchmarks. It is a separate CLI product, not linked into the app. Packaging/audit scripts inspect file metadata on the development machine; they are not shipped in app bundles.

Apple describes `CA92.1` for app-owned UserDefaults access in [NSPrivacyAccessedAPITypeReasons](https://developer.apple.com/documentation/bundleresources/app-privacy-configuration/nsprivacyaccessedapitypes/nsprivacyaccessedapitypereasons). Review the current [required-reason API guidance](https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api) and Xcode archive privacy report before release.
