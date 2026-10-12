import SwiftUI
import CaffeyeCore

@MainActor @Observable
final class AppModel {
    var snapshot: Snapshot?
    var status = "Loading offline venues…"
    var failure: String?
    var busy = false
    var loaded = false
    var generation = 0
    private let store: SnapshotStore
    init() {
        let root = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let file = ProcessInfo.processInfo.arguments.contains("--ui-testing")
            ? FileManager.default.temporaryDirectory.appendingPathComponent("caffeye-ui-" + UUID().uuidString + ".json")
            : root.appendingPathComponent("Caffeye/snapshot.json")
        store = SnapshotStore(file: file)
    }
    func load() async {
        guard !loaded else { return }
        loaded = true
        do {
            snapshot = try await store.load()
            status = "Offline snapshot loaded"
        } catch {
            do {
                guard let url = Bundle.main.url(forResource: ProcessInfo.processInfo.arguments.contains("--ui-testing")
                    && !ProcessInfo.processInfo.arguments.contains("--bundled-venues-testing") ? "demo" : "venues", withExtension: "json") else {
                    throw CocoaError(.fileNoSuchFile)
                }
                snapshot = try SnapshotStore.decode(Data(contentsOf: url))
                status = snapshot?.isDemo == true ? "Demo data · fictional venues and ratings" : "Bundled venues · ratings omitted"
            } catch { failure = error.localizedDescription; status = "No offline snapshot available" }
        }
        generation += 1
    }
    func importSnapshot(_ url: URL) async {
        guard !busy else { return }
        busy = true; defer { busy = false }
        let access = url.startAccessingSecurityScopedResource()
        defer { if access { url.stopAccessingSecurityScopedResource() } }
        do {
            let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
            guard size <= SnapshotStore.maximumBytes else { throw SnapshotError.tooLarge }
            let data = try Data(contentsOf: url)
            snapshot = try await store.save(data)
            status = "Imported snapshot · available offline"
            failure = nil; generation += 1
        } catch { failure = error.localizedDescription }
    }
    func refresh(_ endpoint: String) async {
        guard !busy else { return }
        guard let url = URL(string: endpoint), url.scheme == "https" else {
            failure = SnapshotError.insecureEndpoint.localizedDescription; return
        }
        busy = true; defer { busy = false }
        do {
            snapshot = try await store.refresh(from: url)
            status = "Snapshot updated · available offline"
            failure = nil; generation += 1
        } catch {
            failure = "Update failed: \(error.localizedDescription) Your offline snapshot is still available."
        }
    }
}
