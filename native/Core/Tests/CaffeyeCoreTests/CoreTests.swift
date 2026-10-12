import Foundation
import Testing
@testable import CaffeyeCore

private let source = Provenance(source: "Test fixture")
private let priors = RatingPriors(mean: 4.32, weight: 238, provenance: source)
private func venue(_ id: String, rating: Double? = 4.6, count: Int = 1680) -> Venue {
    Venue(id: id, name: "Cafe \(id)", coordinate: .init(latitude: 33.96, longitude: -84.14),
          city: "Duluth", provenance: source,
          rating: rating.map { Rating(average: $0, count: count, provenance: source) })
}

@Suite("Bayesian discovery")
struct DiscoveryTests {
    @Test("A well-established venue outranks a tiny high-rating sample")
    func ranking() {
        let small = venue("small", rating: 4.9, count: 14)
        let established = venue("established")
        let snapshot = Snapshot(revision: "test", priors: priors, venues: [small, established])
        #expect(snapshot.ranked.map(\.id) == ["established", "small"])
        #expect(abs(priors.score(established) - 4.565255474452555) < 0.00001)
    }
    @Test("Sort retains precision when displayed scores round to the same value")
    func unroundedOrder() {
        let lower = venue("lower", rating: 4.59, count: 1000)
        let higher = venue("higher", rating: 4.60, count: 1000)
        let snapshot = Snapshot(revision: "precision", priors: priors, venues: [lower, higher])
        #expect(String(format: "%.1f", priors.score(lower)) == String(format: "%.1f", priors.score(higher)))
        #expect(snapshot.ranked.map(\.id) == ["higher", "lower"])
    }
    @Test("Large finite priors do not overflow a weighted score")
    func largePrior() {
        let large = RatingPriors(mean: 4.32, weight: Double.greatestFiniteMagnitude, provenance: source)
        #expect(large.score(venue("one")).isFinite)
        #expect(large.score(venue("one")) == large.mean)
    }
    @Test("Unrated venues use the population mean; ties retain input order")
    func unratedAndTies() {
        let snapshot = Snapshot(revision: "test", priors: priors,
                                venues: [venue("z", rating: nil), venue("a", rating: nil)])
        #expect(priors.score(snapshot.venues[0]) == priors.mean)
        #expect(snapshot.ranked.map(\.id) == ["z", "a"])
    }
    @Test("Category filters OR together, feature filters AND together")
    func filters() throws {
        let data = Data(#"{"tier":"excellent","note":"Wi-Fi","hasMeetingRoom":true}"#.utf8)
        var a = venue("one"); a.work = try JSONDecoder().decode(WorkInfo.self, from: data)
        var b = venue("two"); b.category = .tea
        var filters = Filters()
        filters.categories = [.coffee, .tea]
        #expect(filters.matches(a)); #expect(filters.matches(b))
        filters.features = [.work, .meeting]
        #expect(filters.matches(a)); #expect(!filters.matches(b))
    }
    @Test("Search requires all words and uses editorial and area fields")
    func search() {
        var a = venue("one"); a.signature = "Honey espresso"
        var filters = Filters(); filters.search = "  DULUTH honey "
        #expect(filters.matches(a))
        filters.search = "Duluth matcha"; #expect(!filters.matches(a))
        a.model = .franchise; filters.search = ""
        #expect(!filters.matches(a))
        filters.includeFranchises = true; #expect(filters.matches(a))
    }
    @Test("Action links reject script, file and credential URLs", arguments: [
        "javascript:alert(1)", "file:///tmp/test", "https://user:password@example.com", "https:///"
    ])
    func links(value: String) { #expect(Venue.actionURL(value) == nil) }
}

@Suite("Offline snapshots")
struct StoreTests {
    @Test("Invalid update leaves the last good snapshot on disk")
    func atomicReplacement() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = SnapshotStore(file: root.appendingPathComponent("snapshot.json"))
        let good = Snapshot(revision: "good", priors: priors, venues: [venue("one")])
        try await store.save(JSONEncoder().encode(good))
        var bad = good; bad.venues[0].coordinate.latitude = 100
        await #expect(throws: (any Error).self) { try await store.save(JSONEncoder().encode(bad)) }
        #expect(try await store.load() == good)
        // Reopening uses the persisted file without a network request.
        let reopened = SnapshotStore(file: root.appendingPathComponent("snapshot.json"))
        #expect(try await reopened.load() == good)
    }
    @Test("Reject duplicate IDs and invalid priors")
    func validation() {
        let a = venue("one")
        #expect(throws: (any Error).self) { try Snapshot(revision: "test", priors: priors, venues: [a, a]).validated() }
        let bad = RatingPriors(mean: 4.3, weight: 0, provenance: source)
        #expect(throws: (any Error).self) { try Snapshot(revision: "test", priors: bad, venues: [a]).validated() }
    }
    @Test("Unsupported schema and malformed input never replace data")
    func decoding() throws {
        var snapshot = Snapshot(revision: "test", priors: priors, venues: [venue("one")])
        snapshot.schemaVersion = 99
        let data = try JSONEncoder().encode(snapshot)
        #expect(throws: (any Error).self) { try SnapshotStore.decode(data) }
        #expect(throws: (any Error).self) { try SnapshotStore.decode(Data("{}".utf8)) }
    }
}

@Suite("Snapshots with ratings omitted")
struct UnratedSnapshotTests {
    @Test("Snapshots without priors load alphabetically and never infer a score")
    func alphabetical() throws {
        let snapshot = Snapshot(revision: "unrated", venues: [venue("z", rating: nil), venue("a", rating: nil)])
        let decoded = try SnapshotStore.decode(JSONEncoder().encode(snapshot))
        #expect(decoded.priors == nil)
        #expect(decoded.ranked.map(\.id) == ["a", "z"])
    }
    @Test("Rated snapshots still require Bayesian priors")
    func missingPriors() {
        #expect(throws: (any Error).self) {
            try Snapshot(revision: "invalid", venues: [venue("rated")]).validated()
        }
    }
    @Test("The bundled real dataset decodes with no rating inputs")
    func bundledSnapshot() throws {
        let native = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let data = try Data(contentsOf: native.appendingPathComponent("Caffeye/Resources/venues.json"))
        let snapshot = try SnapshotStore.decode(data)
        #expect(snapshot.venues.count == 1705)
        #expect(snapshot.venues.filter { $0.model == .independent }.count == 970)
        #expect(!snapshot.isDemo)
        #expect(snapshot.priors == nil)
        #expect(snapshot.venues.allSatisfy { $0.rating == nil })
    }
}
