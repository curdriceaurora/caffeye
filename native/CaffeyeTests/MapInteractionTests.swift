import Testing
import MapKit
import CaffeyeCore
@testable import Caffeye

@MainActor @Suite("Deferred map interactions")
struct MapInteractionTests {
    private func streetFixture(size: CGSize = CGSize(width: 800, height: 600)) throws -> (DiscoveryState, MKMapView, VenueMap.Coordinator, [any MKAnnotation]) {
        let source = Provenance(source: "Test")
        let venues = [
            Venue(id: "first", name: "First", coordinate: .init(latitude: 33.96, longitude: -84.14), provenance: source),
            Venue(id: "second", name: "Second", coordinate: .init(latitude: 33.96, longitude: -84.14), provenance: source)
        ]
        let state = DiscoveryState(); state.accept(Snapshot(revision: "original", venues: venues))
        let map = MKMapView(frame: CGRect(origin: .zero, size: size))
        let coordinator = VenueMap.Coordinator(state)
        coordinator.configure(map); coordinator.update(map, state: state)
        let annotations = try ["First", "Second"].map { name in
            try #require(map.annotations.first { !($0 is MKClusterAnnotation) && $0.title == name })
        }
        return (state, map, coordinator, annotations)
    }
    private func setDistance(_ distance: CLLocationDistance, on map: MKMapView,
                             coordinator: VenueMap.Coordinator) {
        let camera = MKMapCamera(lookingAtCenter: CLLocationCoordinate2D(latitude: 33.96, longitude: -84.14),
                                 fromDistance: distance, pitch: 0, heading: 0)
        map.setCamera(camera, animated: false)
        coordinator.mapView(map, regionDidChangeAnimated: false)
    }
    private func drainCallbacks() async {
        await withCheckedContinuation { continuation in
            DispatchQueue.main.async { continuation.resume() }
        }
    }

    @Test("The 1,500m street boundary is inclusive and invalid camera distances retain regional clustering")
    func streetClusteringBoundary() {
        #expect(VenueMap.Coordinator.usesIndividualPins(at: 300))
        #expect(VenueMap.Coordinator.usesIndividualPins(at: 1_500))
        #expect(!VenueMap.Coordinator.usesIndividualPins(at: 1_501))
        #expect(!VenueMap.Coordinator.usesIndividualPins(at: 0))
        #expect(!VenueMap.Coordinator.usesIndividualPins(at: .nan))
        #expect(!VenueMap.Coordinator.usesIndividualPins(at: .infinity))
    }

    @Test("Selecting a venue enters individual-pin street scale independently of map aspect ratio",
          arguments: [CGSize(width: 1_500, height: 350), CGSize(width: 350, height: 700)])
    func selectionUsesStreetCamera(_ size: CGSize) async throws {
        let (state, map, coordinator, annotations) = try streetFixture(size: size)
        await drainCallbacks()
        let browsingRect = state.visibleRect
        let venue = try #require(state.current?.venues.first)
        state.select(venue)
        coordinator.update(map, state: state)
        await drainCallbacks()
        #expect(map.camera.centerCoordinateDistance > 0)
        #expect(map.camera.centerCoordinateDistance <= 1_500)
        #expect(abs(map.camera.centerCoordinate.latitude - venue.coordinate.latitude) < 0.00001)
        #expect(abs(map.camera.centerCoordinate.longitude - venue.coordinate.longitude) < 0.00001)
        #expect(!coordinator.clustersEnabled)
        #expect(state.selection == "first")
        for annotation in annotations {
            let view = try #require(coordinator.mapView(map, viewFor: annotation) as? MKMarkerAnnotationView)
            #expect(view.clusteringIdentifier == nil)
            #expect(view.displayPriority == .required)
        }

        state.showAll()
        coordinator.update(map, state: state)
        await drainCallbacks()
        #expect(state.cameraFocus == nil)
        #expect(map.camera.centerCoordinateDistance > 1_500)
        #expect(coordinator.clustersEnabled)
        #expect(state.selection == "first")
        #expect(map.annotations.contains { $0 === annotations[0] })

        state.back()
        coordinator.update(map, state: state)
        await drainCallbacks()
        #expect(state.selection == nil)
        #expect(state.cameraFocus == nil)
        #expect(MKMapRectEqualToRect(state.cameraRect, browsingRect))
        #expect(map.camera.centerCoordinateDistance > 1_500)
        #expect(coordinator.clustersEnabled)
    }

    @Test("Street zoom shows individual required pins and restores clustering on zoom out without replacing venue identity")
    func streetZoomPreservesSelectionAndPendingSnapshot() async throws {
        let (state, map, coordinator, annotations) = try streetFixture()
        let first = try #require(state.current?.venues.first)
        state.select(first)
        coordinator.update(map, state: state)
        var replacement = try #require(state.current); replacement.revision = "pending"
        state.accept(replacement)
        setDistance(5_000, on: map, coordinator: coordinator)
        await drainCallbacks()
        #expect(coordinator.clustersEnabled)
        let regional = try #require(coordinator.mapView(map, viewFor: annotations[0]) as? MKMarkerAnnotationView)
        #expect(regional.clusteringIdentifier == "venues")
        #expect(regional.displayPriority == .defaultHigh)

        setDistance(500, on: map, coordinator: coordinator)
        await drainCallbacks()
        #expect(map.camera.centerCoordinateDistance <= VenueMap.Coordinator.individualPinDistance)
        #expect(!coordinator.clustersEnabled)
        for annotation in annotations {
            #expect(map.annotations.contains { $0 === annotation })
            let marker = try #require(coordinator.mapView(map, viewFor: annotation) as? MKMarkerAnnotationView)
            #expect(marker.clusteringIdentifier == nil)
            #expect(marker.displayPriority == .required)
        }
        #expect(map.selectedAnnotations.contains { $0 === annotations[0] })
        await drainCallbacks()
        #expect(state.selection == "first")
        #expect(state.pending?.revision == "pending")
        #expect(state.listSnapshot?.revision == "original")

        setDistance(5_000, on: map, coordinator: coordinator)
        await drainCallbacks()
        #expect(coordinator.clustersEnabled)
        for annotation in annotations {
            #expect(map.annotations.contains { $0 === annotation })
            let marker = try #require(coordinator.mapView(map, viewFor: annotation) as? MKMarkerAnnotationView)
            #expect(marker.clusteringIdentifier == "venues")
            #expect(marker.displayPriority == .defaultHigh)
        }
        #expect(map.selectedAnnotations.contains { $0 === annotations[0] })
        await drainCallbacks()
        #expect(state.selection == "first")
        #expect(state.pending?.revision == "pending")
    }

    @Test("Street zoom cancels queued cluster callbacks and closes the old member list")
    func streetZoomInvalidatesClusterSelection() async throws {
        let (state, map, coordinator, annotations) = try streetFixture()
        setDistance(5_000, on: map, coordinator: coordinator)
        let cluster = MKClusterAnnotation(memberAnnotations: annotations)
        let view = try #require(coordinator.mapView(map, viewFor: cluster))
        state.showCluster(["first", "second"])
        coordinator.mapView(map, didSelect: view)
        setDistance(500, on: map, coordinator: coordinator)
        await drainCallbacks()
        #expect(state.clusterMembers.isEmpty)
        #expect(state.selection == nil)

        // A late callback for an obsolete cluster must not cancel a valid close pin.
        let pin = try #require(coordinator.mapView(map, viewFor: annotations[1]))
        coordinator.mapView(map, didSelect: pin)
        coordinator.mapView(map, didSelect: view)
        setDistance(600, on: map, coordinator: coordinator)
        await drainCallbacks()
        #expect(state.selection == "second")
        #expect(state.clusterMembers.isEmpty)
    }

    @Test("Deferred clustering uses the latest zoom, filtered annotations and camera command")
    func deferredStreetRefreshUsesCurrentState() async throws {
        let (state, map, coordinator, annotations) = try streetFixture()
        setDistance(500, on: map, coordinator: coordinator)
        setDistance(5_000, on: map, coordinator: coordinator)
        await drainCallbacks()
        #expect(coordinator.clustersEnabled)
        let regional = try #require(coordinator.mapView(map, viewFor: annotations[0]) as? MKMarkerAnnotationView)
        #expect(regional.clusteringIdentifier == "venues")

        setDistance(500, on: map, coordinator: coordinator)
        state.filters.search = "First"
        coordinator.update(map, state: state)
        await drainCallbacks()
        #expect(!coordinator.clustersEnabled)
        #expect(map.annotations.contains { $0 === annotations[0] })
        #expect(!map.annotations.contains { $0 === annotations[1] })
        let close = try #require(coordinator.mapView(map, viewFor: annotations[0]) as? MKMarkerAnnotationView)
        #expect(close.clusteringIdentifier == nil)

        // A camera command superseding the queued opposite-mode refresh must win.
        setDistance(5_000, on: map, coordinator: coordinator)
        state.reset()
        coordinator.update(map, state: state)
        await drainCallbacks()
        #expect(coordinator.clustersEnabled)
        #expect(state.matches.count == 2)
        #expect(state.selection == nil)
        #expect(state.clusterMembers.isEmpty)
        #expect(map.annotations.contains { $0.title == "Second" })
    }

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
