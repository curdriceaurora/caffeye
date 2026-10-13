import Testing
import MapKit
import CaffeyeCore
@testable import Caffeye

@MainActor @Suite("Discovery state")
struct DiscoveryStateTests {
    private func snapshot(_ revision: String = "first") -> Snapshot {
        let source = Provenance(source: "Test")
        return Snapshot(revision: revision, priors: .init(mean: 4.32, weight: 238, provenance: source), venues: [
            Venue(id: "near", name: "Nearby coffee", coordinate: .init(latitude: 33.96, longitude: -84.14), provenance: source),
            Venue(id: "far", name: "Other coffee", coordinate: .init(latitude: 34.6, longitude: -84.8), provenance: source)
        ])
    }
    @Test("Back restores first browsing camera even after switching venues")
    func cameraRestoration() {
        let state = DiscoveryState(); let data = snapshot(); state.accept(data)
        let browse = state.visibleRect
        state.select(data.venues[0])
        state.cameraChanged(state.cameraRect, userInitiated: false)
        state.select(data.venues[1])
        state.back()
        #expect(MKMapRectEqualToRect(state.cameraRect, browse))
        #expect(state.selection == nil)
    }
    @Test("Viewport filters rows but retains offscreen map candidates")
    func viewport() {
        let state = DiscoveryState(); state.accept(snapshot())
        let point = MKMapPoint(state.current!.venues[0].coordinate.location)
        state.cameraChanged(MKMapRect(x: point.x - 100, y: point.y - 100, width: 200, height: 200), userInitiated: true)
        #expect(state.matches.count == 2)
        #expect(state.rows.map(\.id) == ["near"])
    }
    @Test("Updates stage while reading and filters dismiss excluded details")
    func stableReading() {
        let state = DiscoveryState(); state.accept(snapshot())
        state.reading = true; state.accept(snapshot("new"))
        #expect(state.listSnapshot?.revision == "first")
        #expect(state.pending?.revision == "new")
        state.select(state.current!.venues[0])
        state.filters.search = "Other"; state.filtersChanged()
        #expect(state.selection == nil)
        #expect(state.listSnapshot?.revision == "new")
        #expect(state.pending == nil)
    }
    @Test("Visible sidebar follows the camera while compact browsing rows stay stable")
    func selectedViewport() {
        let state = DiscoveryState(); let data = snapshot(); state.accept(data)
        state.select(data.venues[0])
        state.cameraChanged(state.cameraRect, userInitiated: false)
        #expect(state.rows.map(\.id) == ["near"])
        #expect(state.browsingRows.count == 2)
        state.back()
        #expect(state.rows.count == 2)
    }
    @Test("Selecting a cluster replaces an open detail without moving the map")
    func clusterFromDetail() {
        let state = DiscoveryState(); let data = snapshot(); state.accept(data)
        state.select(data.venues[0])
        let command = state.cameraCommand
        state.showCluster(["near", "far"])
        #expect(state.selection == nil)
        #expect(state.clusterVenues.count == 2)
        #expect(state.cameraCommand == command)
    }
    @Test("Reset restores indie defaults and regional camera")
    func reset() {
        let state = DiscoveryState(); state.accept(snapshot())
        state.filters.includeFranchises = true; state.filters.features = [.work]
        state.filters.search = "coffee"; state.reset()
        #expect(state.filters == Filters())
        #expect(MKMapRectEqualToRect(state.cameraRect, DiscoveryState.regionalRect))
    }
    @Test("Regional-scale data preserves all map candidates and stable ranking")
    func regionalScale() throws {
        var data = snapshot()
        let template = data.venues[0]
        data.venues = (0..<1705).map { index in
            var venue = template
            venue.id = "scale-\(index)"
            venue.coordinate = .init(latitude: 33.5 + Double(index / 50) * 0.025,
                                     longitude: -84.7 + Double(index % 50) * 0.02)
            return venue
        }
        let state = DiscoveryState(); state.accept(try data.validated())
        #expect(state.matches.count == 1705)
        #expect(state.matches.first?.id == "scale-0")
        #expect(state.matches.last?.id == "scale-1704")
    }

    @Test("Search indexes refresh for edited venues while a reading list stays staged")
    func indexedUpdates() {
        let state = DiscoveryState()
        var data = snapshot()
        data.venues[0].loved = ["Honey espresso"]
        state.accept(data)
        state.filters.search = "honey nearby"
        #expect(state.rows.map(\.id) == ["near"])
        state.reading = true
        // Revisions are labels, not cache keys: changed fields must always be indexed.
        data.venues[0].loved = ["Matcha"]
        state.accept(data)
        #expect(state.matches.isEmpty)
        #expect(state.rows.map(\.id) == ["near"])
        state.applyPending()
        #expect(state.rows.isEmpty)
        state.filters.search = "MATCHA nearby"
        #expect(state.rows.map(\.id) == ["near"])
    }

    @Test("Scope counts ignore search and viewport and refresh when franchises change")
    func scopeCounts() throws {
        let state = DiscoveryState()
        var data = snapshot()
        data.venues[1].category = .tea
        data.venues[1].model = .franchise
        data.venues[1].late = try JSONDecoder().decode(LateInfo.self, from: Data(#"{"tier":"midnight","when":"Daily"}"#.utf8))
        state.accept(data)
        #expect(state.inScope.count == 1)
        #expect(state.categoryCounts[.tea, default: 0] == 0)
        state.filters.includeFranchises = true
        state.filters.search = "Nearby"
        let point = MKMapPoint(data.venues[0].coordinate.location)
        state.cameraChanged(MKMapRect(x: point.x - 100, y: point.y - 100, width: 200, height: 200), userInitiated: true)
        #expect(state.rows.map(\.id) == ["near"])
        #expect(state.inScope.count == 2)
        #expect(state.categoryCounts[.tea] == 1)
        #expect(state.featureCounts[.midnight] == 1)
        state.filters.includeFranchises = false
        #expect(state.inScope.count == 1)
        #expect(state.featureCounts[.midnight, default: 0] == 0)
    }

    @Test("Map selection supplies a sidebar scroll target and Reset clears it")
    func pinScrollTarget() {
        let state = DiscoveryState(); let data = snapshot(); state.accept(data)
        state.select(data.venues[1])
        #expect(state.scrollID == "far")
        state.select(data.venues[0])
        #expect(state.scrollID == "near")
        state.reset()
        #expect(state.scrollID == nil)
    }

    @Test("Only involuntary deselection requests an accessibility announcement")
    func excludedSelectionAnnouncement() {
        let state = DiscoveryState(); let data = snapshot(); state.accept(data)
        state.select(data.venues[0])
        state.filters.search = "Nearby"
        #expect(state.deselectionNotice == 0)
        state.filters.search = "no match"
        #expect(state.selection == nil)
        #expect(state.deselectionNotice == 1)
        #expect(state.deselectionMessage == "Venue no longer matches active filters.")
        state.reset(); state.select(data.venues[0]); state.back()
        #expect(state.deselectionNotice == 1)
        state.select(data.venues[0]); state.reset()
        #expect(state.deselectionNotice == 1)
        state.select(data.venues[0])
        var replacement = data; replacement.venues.removeFirst(); state.accept(replacement)
        #expect(state.selection == nil)
        #expect(state.deselectionNotice == 2)
    }

    @Test("Queued map callbacks do not keep a released coordinator alive")
    func mapCallbackLifetime() async {
        let state = DiscoveryState()
        var coordinator: VenueMap.Coordinator? = VenueMap.Coordinator(state)
        weak var released = coordinator
        coordinator?.mapViewDidFailLoadingMap(MKMapView(), withError: URLError(.notConnectedToInternet))
        coordinator = nil
        #expect(released == nil)
        await Task.yield()
        #expect(!state.mapImageryUnavailable)
    }

}
