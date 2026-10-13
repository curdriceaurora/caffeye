import SwiftUI
import MapKit
import os
import CaffeyeCore

@MainActor @Observable
final class DiscoveryState {
    static var regionalRect: MKMapRect {
        let a = MKMapPoint(CLLocationCoordinate2D(latitude: 34.75, longitude: -85.05))
        let b = MKMapPoint(CLLocationCoordinate2D(latitude: 33.15, longitude: -83.30))
        return MKMapRect(x: a.x, y: a.y, width: b.x - a.x, height: b.y - a.y)
    }
    var filters = Filters() {
        didSet { if filters != oldValue { filtersChanged() } }
    }
    private(set) var current: Snapshot?
    private(set) var listSnapshot: Snapshot?
    private(set) var pending: Snapshot?
    var selection: String?
    private(set) var visibleRect = regionalRect
    var cameraRect = regionalRect
    var cameraCommand = 0
    private var currentRanked: [Venue] = []
    private var listRanked: [Venue] = []
    var reading = false
    var mapImageryUnavailable = false
    var clusterMembers: [String] = []
    var scrollID: String?
    private var browsingRect: MKMapRect?

    private var currentSearch: [String: String] = [:]
    private var listSearch: [String: String] = [:]
    private var listMatches: [Venue] = []
    private var countsIncludeFranchises = false
    private(set) var matches: [Venue] = []
    private(set) var rows: [Venue] = []
    private(set) var browsingRows: [Venue] = []
    private(set) var inScope: [Venue] = []
    private(set) var categoryCounts: [CaffeyeCore.Category: Int] = [:]
    private(set) var featureCounts: [Feature: Int] = [:]
    var selected: Venue? { current?.venues.first { $0.id == selection } }

    private static let performance = OSLog(subsystem: "com.caffeye.native", category: .pointsOfInterest)
    private func rebuildFilters() {
        os_signpost(.begin, log: Self.performance, name: "Filter venues")
        defer { os_signpost(.end, log: Self.performance, name: "Filter venues") }
        matches = filters.matching(currentRanked, searchIndex: currentSearch)
        listMatches = filters.matching(listRanked, searchIndex: listSearch)
        rebuildRows()
    }
    private func rebuildRows() {
        rows = listMatches.filter { visibleRect.contains(MKMapPoint($0.coordinate.location)) }
        if let browsingRect {
            browsingRows = listMatches.filter { browsingRect.contains(MKMapPoint($0.coordinate.location)) }
        } else { browsingRows = rows }
    }
    private func rebuildCounts() {
        countsIncludeFranchises = filters.includeFranchises
        inScope = currentRanked.filter { countsIncludeFranchises || $0.model == .independent }
        categoryCounts = [:]; featureCounts = [:]
        for venue in inScope {
            categoryCounts[venue.category, default: 0] += 1
            for feature in Feature.allCases where feature.matches(venue) {
                featureCounts[feature, default: 0] += 1
            }
        }
    }
    var clusterVenues: [Venue] {
        matches.filter { clusterMembers.contains($0.id) }
    }
    func accept(_ snapshot: Snapshot) {
        current = snapshot
        currentRanked = snapshot.ranked
        currentSearch = Dictionary(uniqueKeysWithValues: snapshot.venues.map { ($0.id, $0.searchText) })
        if reading || selection != nil {
            pending = snapshot
        } else {
            listSnapshot = snapshot; listRanked = currentRanked; listSearch = currentSearch
        }
        rebuildCounts(); rebuildFilters()
        if let selection, !matches.contains(where: { $0.id == selection }) { back() }
    }
    func applyPending() {
        guard let pending else { return }
        listSnapshot = pending; listRanked = currentRanked; listSearch = currentSearch
        self.pending = nil
        listMatches = filters.matching(listRanked, searchIndex: listSearch)
        rebuildRows()
    }
    func filtersChanged() {
        applyPending(); clusterMembers = []
        if countsIncludeFranchises != filters.includeFranchises { rebuildCounts() }
        rebuildFilters()
        if let selection, !matches.contains(where: { $0.id == selection }) { back() }
    }
    func select(_ venue: Venue) {
        guard selection != venue.id else { return }
        if selection == nil { browsingRect = visibleRect }
        selection = venue.id; scrollID = venue.id; clusterMembers = []; reading = true
        rebuildRows()
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
        rebuildRows()
    }
    func back() {
        selection = nil
        if let browsingRect { visibleRect = browsingRect; move(to: browsingRect) }
        browsingRect = nil
        rebuildRows()
    }
    func reset() {
        filters = Filters(); selection = nil; clusterMembers = []
        browsingRect = nil; reading = false; scrollID = nil; applyPending()
        move(to: Self.regionalRect)
        visibleRect = Self.regionalRect
        rebuildRows()
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
        rebuildRows()
    }
    func move(to rect: MKMapRect) { cameraRect = rect; cameraCommand += 1 }
}

extension Coordinate {
    var location: CLLocationCoordinate2D { .init(latitude: latitude, longitude: longitude) }
}
