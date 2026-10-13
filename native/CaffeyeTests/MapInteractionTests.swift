import Testing
import MapKit
import CaffeyeCore
@testable import Caffeye

@MainActor @Suite("Deferred map interactions")
struct MapInteractionTests {
    @Test("The latest queued pin selection wins during rapid interaction")
    func latestSelectionWins() async throws {
        let source = Provenance(source: "Test")
        let first = Venue(id: "first", name: "First", coordinate: .init(latitude: 33.96, longitude: -84.14), provenance: source)
        let second = Venue(id: "second", name: "Second", coordinate: .init(latitude: 33.98, longitude: -84.14), provenance: source)
        let state = DiscoveryState(); state.accept(Snapshot(revision: "test", venues: [first, second]))
        let map = MKMapView(); let coordinator = VenueMap.Coordinator(state)
        coordinator.configure(map); coordinator.update(map, state: state)
        for name in ["First", "Second"] {
            let annotation = try #require(map.annotations.first { $0.title == name })
            let view = try #require(coordinator.mapView(map, viewFor: annotation))
            coordinator.mapView(map, didSelect: view)
        }
        await withCheckedContinuation { continuation in
            DispatchQueue.main.async { continuation.resume() }
        }
        #expect(state.selection == "second")
    }

    @Test("Reset wins over a queued pin or cluster selection", arguments: [false, true])
    func resetCancelsSelection(_ cluster: Bool) async throws {
        let venue = Venue(id: "one", name: "Cafe", coordinate: .init(latitude: 33.96, longitude: -84.14), provenance: .init(source: "Test"))
        let state = DiscoveryState()
        state.accept(Snapshot(revision: "test", venues: [venue]))
        let map = MKMapView()
        let coordinator = VenueMap.Coordinator(state)
        coordinator.configure(map)
        coordinator.update(map, state: state)
        let annotation = try #require(map.annotations.first { $0.title == "Cafe" })
        let selected: any MKAnnotation = cluster ? MKClusterAnnotation(memberAnnotations: [annotation]) : annotation
        let view = try #require(coordinator.mapView(map, viewFor: selected))
        coordinator.mapView(map, didSelect: view)
        state.reset()
        // Drain the actual main-queue callbacks rather than assume Task.yield ordering.
        await withCheckedContinuation { continuation in
            DispatchQueue.main.async { continuation.resume() }
        }
        #expect(state.selection == nil)
        #expect(state.clusterMembers.isEmpty)
        #expect(MKMapRectEqualToRect(state.cameraRect, DiscoveryState.regionalRect))
    }
}
