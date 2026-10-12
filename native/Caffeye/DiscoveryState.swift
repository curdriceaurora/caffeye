import SwiftUI
import MapKit
import CaffeyeCore

@MainActor @Observable
final class DiscoveryState {
    static var regionalRect: MKMapRect {
        let a = MKMapPoint(CLLocationCoordinate2D(latitude: 34.75, longitude: -85.05))
        let b = MKMapPoint(CLLocationCoordinate2D(latitude: 33.15, longitude: -83.30))
        return MKMapRect(x: a.x, y: a.y, width: b.x - a.x, height: b.y - a.y)
    }
    var filters = Filters()
    var current: Snapshot?
    var listSnapshot: Snapshot?
    var pending: Snapshot?
    var selection: String?
    var visibleRect = regionalRect
    var cameraRect = regionalRect
    var cameraCommand = 0
    private var currentRanked: [Venue] = []
    private var listRanked: [Venue] = []
    var reading = false
    var clusterMembers: [String] = []
    var scrollID: String?
    private var browsingRect: MKMapRect?

    var matches: [Venue] { currentRanked.filter(filters.matches) }
    var rows: [Venue] { rows(in: visibleRect) }
    var browsingRows: [Venue] { rows(in: browsingRect ?? visibleRect) }
    private func rows(in rect: MKMapRect) -> [Venue] {
        listRanked.filter { filters.matches($0) && rect.contains(MKMapPoint($0.coordinate.location)) }
    }
    var selected: Venue? { current?.venues.first { $0.id == selection } }
    var inScope: [Venue] {
        current?.venues.filter { filters.includeFranchises || $0.model == .independent } ?? []
    }
    var clusterVenues: [Venue] {
        matches.filter { clusterMembers.contains($0.id) }
    }
    func accept(_ snapshot: Snapshot) {
        current = snapshot
        currentRanked = snapshot.ranked
        if reading || selection != nil {
            pending = snapshot
        } else { listSnapshot = snapshot; listRanked = currentRanked }
        if let selection, !matches.contains(where: { $0.id == selection }) { back() }
    }
    func applyPending() {
        if let pending { listSnapshot = pending; listRanked = pending.ranked }
        pending = nil
    }
    func filtersChanged() {
        applyPending(); clusterMembers = []
        if let selection, !matches.contains(where: { $0.id == selection }) { back() }
    }
    func select(_ venue: Venue) {
        guard selection != venue.id else { return }
        if selection == nil { browsingRect = visibleRect }
        selection = venue.id; clusterMembers = []; reading = true
        let point = MKMapPoint(venue.coordinate.location)
        let side = 1300 / MKMetersPerMapPointAtLatitude(venue.coordinate.latitude)
        move(to: MKMapRect(x: point.x - side / 2, y: point.y - side / 2, width: side, height: side))
    }
    func showCluster(_ ids: [String]) {
        selection = nil
        browsingRect = nil
        applyPending()
        clusterMembers = ids
        reading = true
    }
    func back() {
        selection = nil
        if let browsingRect { visibleRect = browsingRect; move(to: browsingRect) }
        browsingRect = nil
    }
    func reset() {
        filters = Filters(); selection = nil; clusterMembers = []
        browsingRect = nil; reading = false; scrollID = nil; applyPending()
        move(to: Self.regionalRect)
    }
    func showAll() {
        guard !matches.isEmpty else { return }
        let rect = matches.reduce(MKMapRect.null) {
            let p = MKMapPoint($1.coordinate.location)
            return $0.union(MKMapRect(x: p.x, y: p.y, width: 1, height: 1))
        }
        let minimum = 2000 / MKMetersPerMapPointAtLatitude(33.9)
        move(to: rect.insetBy(dx: -max(rect.width * 0.12, minimum), dy: -max(rect.height * 0.12, minimum)))
    }
    func cameraChanged(_ rect: MKMapRect, userInitiated: Bool) {
        visibleRect = rect
        if userInitiated { cameraRect = rect; reading = true; applyPending(); clusterMembers = [] }
    }
    func move(to rect: MKMapRect) { cameraRect = rect; cameraCommand += 1 }
}

extension Coordinate {
    var location: CLLocationCoordinate2D { .init(latitude: latitude, longitude: longitude) }
}
