import SwiftUI
import CaffeyeCore
import os

@MainActor @Observable
final class AppModel {
    var snapshot: Snapshot?
    var status = "Loading venues…"
    var failure: String?
    var busy = false
    var loaded = false
    var generation = 0
    private let store: SnapshotStore
    private var updateTask: Task<Snapshot, Error>?
    var canCancelUpdate: Bool { updateTask != nil }
    private static let performance = OSLog(subsystem: "com.caffeye.native", category: .pointsOfInterest)
    init(store: SnapshotStore? = nil) {
        let root = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let file = ProcessInfo.processInfo.arguments.contains("--ui-testing")
            ? FileManager.default.temporaryDirectory.appendingPathComponent("caffeye-ui-" + UUID().uuidString + ".json")
            : root.appendingPathComponent("Caffeye/snapshot.json")
        self.store = store ?? SnapshotStore(file: file)
    }
    func load() async {
        guard !loaded else { return }
        loaded = true
        os_signpost(.begin, log: Self.performance, name: "Load snapshot")
        defer { os_signpost(.end, log: Self.performance, name: "Load snapshot") }
        do {
            snapshot = try await store.load()
            status = "Venues loaded"
        } catch {
            do {
                let arguments = ProcessInfo.processInfo.arguments
                let testing = arguments.contains("--ui-testing") && !arguments.contains("--bundled-venues-testing")
                let resource = testing ? (arguments.contains("--ui-edge-cases-testing") ? "ui-edge-cases" : "demo") : "venues"
                guard let url = Bundle.main.url(forResource: resource, withExtension: "json") else {
                    throw CocoaError(.fileNoSuchFile)
                }
                snapshot = try SnapshotStore.decode(SnapshotStore.readFile(url))
                status = snapshot?.isDemo == true ? "Demo data · fictional venues and ratings" : "Venues · ratings omitted"
            } catch { failure = error.localizedDescription; status = "Venues unavailable" }
        }
        generation += 1
        // Developer profiling waits for venue data, not for network-dependent basemap tiles.
        if ProcessInfo.processInfo.arguments.contains("--ui-testing"), let snapshot,
           ProcessInfo.processInfo.environment["CAFFEYE_PROFILE_READY"] == "1",
           let data = try? JSONSerialization.data(withJSONObject: ["phase": "offlineSnapshotLoaded", "venues": snapshot.venues.count]) {
            FileHandle.standardOutput.write(Data("CAFFEYE_SNAPSHOT_READY ".utf8) + data + Data("\n".utf8))
        }
    }
    func importSnapshot(_ url: URL) async {
        guard !busy else { return }
        busy = true; defer { busy = false }
        let access = url.startAccessingSecurityScopedResource()
        defer { if access { url.stopAccessingSecurityScopedResource() } }
        do {
            snapshot = try await store.importFile(url)
            status = "Venues loaded"
            failure = nil; generation += 1
        } catch { failure = error.localizedDescription }
    }
    func cancelUpdate() { updateTask?.cancel() }
    func refresh(_ endpoint: String) async {
        guard !busy else { return }
        guard let url = URL(string: endpoint), SnapshotStore.isSecureEndpoint(url) else {
            failure = SnapshotError.insecureEndpoint.localizedDescription; return
        }
        busy = true
        let task = Task { try await store.refresh(from: url) }
        updateTask = task
        defer { busy = false; updateTask = nil }
        do {
            snapshot = try await task.value
            status = "Venues updated"
            failure = nil; generation += 1
        } catch where task.isCancelled {
            status = "Update cancelled · current venues retained"
            failure = nil
        } catch {
            failure = "Update failed: \(error.localizedDescription) Your current venues are still available."
        }
    }
}
