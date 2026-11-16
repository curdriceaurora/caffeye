import Foundation
import Darwin
import CaffeyeCore

func milliseconds(_ duration: Duration) -> Double {
    let value = duration.components
    return Double(value.seconds) * 1_000 + Double(value.attoseconds) / 1_000_000_000_000_000
}
func sample(_ count: Int = 30, _ operation: () throws -> Int) rethrows -> [String: Double] {
    var samples: [Double] = []
    var checksum = 0
    for _ in 0..<count {
        let duration = try ContinuousClock().measure { checksum += try operation() }
        samples.append(milliseconds(duration))
    }
    samples.sort()
    return ["median_ms": samples[count / 2], "p95_ms": samples[Int(Double(count - 1) * 0.95)],
            "iterations": Double(count), "checksum": Double(checksum)]
}

do {
    let args = Array(CommandLine.arguments.dropFirst())
    guard args.count == 2, ["validate", "benchmark"].contains(args[0]) else {
        throw NSError(domain: "CaffeyeTools", code: 1, userInfo: [NSLocalizedDescriptionKey: "Usage: CaffeyeTools validate|benchmark snapshot.json"])
    }
    let data = try SnapshotStore.readFile(URL(fileURLWithPath: args[1]))
    let snapshot = try SnapshotStore.decode(data)
    var report: [String: Any] = ["schemaVersion": 1, "revision": snapshot.revision,
                              "venues": snapshot.venues.count, "isDemo": snapshot.isDemo,
                              "ratings": snapshot.venues.filter { $0.rating != nil }.count]
    if args[0] == "benchmark" {
        let index = Dictionary(uniqueKeysWithValues: snapshot.venues.map { ($0.id, $0.searchText) })
        var filters = Filters(); filters.includeFranchises = true; filters.search = "coffee atlanta"
        report["decode_validate"] = try sample { try SnapshotStore.decode(data).venues.count }
        report["ranking"] = sample { snapshot.ranked.count }
        report["build_search_index"] = sample {
            let built = Dictionary(uniqueKeysWithValues: snapshot.venues.map { ($0.id, $0.searchText) })
            return built.values.reduce(0) { $0 + $1.utf8.count }
        }
        report["indexed_search"] = sample(100) { filters.matching(snapshot.venues, searchIndex: index).count }
        var usage = rusage()
        getrusage(RUSAGE_SELF, &usage)
        report["peak_process_rss_bytes"] = usage.ru_maxrss
        report["os"] = ProcessInfo.processInfo.operatingSystemVersionString
        report["logical_processors"] = ProcessInfo.processInfo.processorCount
        report["scope"] = "Release command-line domain harness on this Mac; excludes SwiftUI, MapKit rendering, app launch and GPU performance."
    }
    let output = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
    print(String(decoding: output, as: UTF8.self))
} catch {
    FileHandle.standardError.write(Data((error.localizedDescription + "\n").utf8))
    exit(1)
}
