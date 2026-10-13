import Foundation
import Testing
import CaffeyeCore
@testable import Caffeye

@MainActor @Suite("Offline app recovery")
struct AppModelTests {
    @Test("A corrupt saved snapshot falls back to the bundled dataset and can be replaced")
    func corruptCacheRecovery() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let file = root.appendingPathComponent("cache.json")
        try Data("corrupt".utf8).write(to: file)
        let model = AppModel(store: SnapshotStore(file: file))
        await model.load()
        #expect(model.snapshot?.venues.count == 1705)
        #expect(model.failure == nil)
        #expect(model.status == "Venues · ratings omitted")
        let imported = root.appendingPathComponent("import.json")
        let replacement = Snapshot(revision: "replacement", venues: [Venue(id: "test", name: "Test", coordinate: .init(latitude: 33.96, longitude: -84.14), provenance: .init(source: "Test"))])
        try JSONEncoder().encode(replacement).write(to: imported)
        await model.importSnapshot(imported)
        #expect(model.snapshot == replacement)
        #expect(try await SnapshotStore(file: file).load() == replacement)
    }
    @Test("Rejected imports preserve the visible snapshot and clear busy state")
    func rejectedImport() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let model = AppModel(store: SnapshotStore(file: root.appendingPathComponent("cache.json")))
        await model.load()
        let before = try #require(model.snapshot)
        let invalid = root.appendingPathComponent("invalid.json")
        try Data("{}".utf8).write(to: invalid)
        await model.importSnapshot(invalid)
        #expect(model.snapshot == before)
        #expect(model.failure != nil)
        #expect(!model.busy)
    }
}
