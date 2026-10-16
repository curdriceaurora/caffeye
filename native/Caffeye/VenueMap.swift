import SwiftUI
import MapKit
import os
import CaffeyeCore

private final class VenueAnnotation: NSObject, MKAnnotation {
    let venue: Venue
    var coordinate: CLLocationCoordinate2D { venue.coordinate.location }
    var title: String? { venue.name }
    init(_ venue: Venue) { self.venue = venue }
}

#if os(macOS)
/// The monitor observes input without replacing MapKit's native gestures.
private final class MapInputMonitor {
    let token: Any
    init(_ token: Any) { self.token = token }
    deinit { NSEvent.removeMonitor(token) }
}
#endif

@MainActor struct VenueMap {
    var state: DiscoveryState
    func makeCoordinator() -> Coordinator { Coordinator(state) }

    @MainActor final class Coordinator: NSObject, MKMapViewDelegate {
        static let individualPinDistance: CLLocationDistance = 1_500
        static func usesIndividualPins(at distance: CLLocationDistance) -> Bool {
            distance.isFinite && distance > 0 && distance <= individualPinDistance
        }
        var state: DiscoveryState
        private var annotations: [String: VenueAnnotation] = [:]
        var lastCommand = -1
        var programmatic = false
        private var selectionEvent = 0
        private(set) var clustersEnabled = true
        private var staleClusteringIDs: Set<String> = []
        private var clusteringGeneration = 0
        private var pendingClustering: (enabled: Bool, command: Int)?
        #if os(macOS)
        private var userRegionChange = false
        private var inputMonitor: MapInputMonitor?
        private var lastRegionSize: CGSize?
        #endif
        init(_ state: DiscoveryState) { self.state = state }

        func configure(_ map: MKMapView) {
            #if os(iOS)
            map.accessibilityIdentifier = "venue-map"
            #else
            map.setAccessibilityIdentifier("venue-map")
            #endif
            programmatic = true
            map.delegate = self
            #if os(macOS)
            if let token = NSEvent.addLocalMonitorForEvents(matching: [.leftMouseDown, .leftMouseDragged, .scrollWheel, .magnify], handler: { [weak self, weak map] event in
                guard let self, let map else { return event }
                // A pin click is selection, not camera input. Only a drag, zoom,
                // or double-click arms viewport filtering for region callbacks.
                if event.type == .leftMouseDown { self.userRegionChange = false }
                if !self.programmatic, !map.inLiveResize, let window = map.window,
                   event.window === window,
                   (event.type != .leftMouseDown || event.clickCount > 1),
                   map.bounds.contains(map.convert(event.locationInWindow, from: nil)) {
                    self.userRegionChange = true
                }
                return event
            }) { inputMonitor = MapInputMonitor(token) }
            #endif
            map.register(MKMarkerAnnotationView.self, forAnnotationViewWithReuseIdentifier: "venue")
            map.register(MKMarkerAnnotationView.self, forAnnotationViewWithReuseIdentifier: "cluster")
            map.pointOfInterestFilter = .excludingAll
            map.showsCompass = true
            map.isRotateEnabled = false
            map.isPitchEnabled = false
            map.cameraBoundary = MKMapView.CameraBoundary(mapRect: DiscoveryState.regionalRect)
            map.cameraZoomRange = MKMapView.CameraZoomRange(minCenterCoordinateDistance: 300, maxCenterCoordinateDistance: 300_000)
            map.setVisibleMapRect(DiscoveryState.regionalRect, animated: false)
        }
        private static let performance = OSLog(subsystem: "com.caffeye.native", category: .pointsOfInterest)
        func update(_ map: MKMapView, state: DiscoveryState) {
            os_signpost(.begin, log: Self.performance, name: "Map annotations")
            defer { os_signpost(.end, log: Self.performance, name: "Map annotations") }
            self.state = state
            let venues = state.matches
            let ids = Set(venues.map(\.id))
            let removed = annotations.keys.filter { !ids.contains($0) }
            for id in removed {
                staleClusteringIDs.remove(id)
                if let annotation = annotations.removeValue(forKey: id) { map.removeAnnotation(annotation) }
            }
            for venue in venues where annotations[venue.id]?.venue != venue {
                if let old = annotations[venue.id] { map.removeAnnotation(old) }
                let annotation = VenueAnnotation(venue)
                annotations[venue.id] = annotation
                map.addAnnotation(annotation)
            }
            if lastCommand != state.cameraCommand {
                lastCommand = state.cameraCommand
                programmatic = true
                #if os(macOS)
                userRegionChange = false
                #endif
                if let focus = state.cameraFocus {
                    // A fitted rectangle changes effective zoom with map aspect ratio.
                    // Venue selection always enters the individual-pin street scale.
                    let camera = MKMapCamera(lookingAtCenter: focus.location,
                                             fromDistance: 1_000, pitch: 0, heading: 0)
                    map.setCamera(camera, animated: false)
                } else {
                    map.setVisibleMapRect(state.cameraRect, animated: false)
                }
                // Delegate callbacks may be synchronous; publish geometry on the next run loop.
                DispatchQueue.main.async { [weak self, weak map] in
                    guard let self, let map else { return }
                    self.state.cameraChanged(map.visibleMapRect, userInitiated: false)
                    self.programmatic = false
                }
            }
            updateClustering(map)
            synchronizeSelection(map)
        }
        private func synchronizeSelection(_ map: MKMapView) {
            for annotation in map.selectedAnnotations {
                if let venue = annotation as? VenueAnnotation, venue.venue.id != state.selection {
                    map.deselectAnnotation(annotation, animated: false)
                }
            }
            if let id = state.selection, let annotation = annotations[id],
               !map.selectedAnnotations.contains(where: { ($0 as? VenueAnnotation)?.venue.id == id }) {
                map.selectAnnotation(annotation, animated: false)
            }
        }
        private func updateClustering(_ map: MKMapView) {
            let distance = map.camera.centerCoordinateDistance
            let enabled = !Self.usesIndividualPins(at: distance)
            if enabled != clustersEnabled {
                clustersEnabled = enabled
                selectionEvent += 1
                staleClusteringIDs = Set(annotations.keys)
            }
            let nearby = Self.clusteringRefreshRect(map.visibleMapRect)
            let needsRefresh = annotations.values.contains {
                staleClusteringIDs.contains($0.venue.id) && nearby.contains(MKMapPoint($0.coordinate))
            }
            guard needsRefresh || (!enabled && !state.clusterMembers.isEmpty) else {
                if pendingClustering != nil {
                    clusteringGeneration += 1
                    pendingClustering = nil
                }
                return
            }
            let command = state.cameraCommand
            if let pendingClustering, pendingClustering.enabled == enabled, pendingClustering.command == command { return }
            clusteringGeneration += 1
            let generation = clusteringGeneration
            pendingClustering = (enabled, command)
            // MapKit may call regionDidChange synchronously inside setCamera while
            // its annotation manager is still updating. Rebuilding there is unsafe.
            DispatchQueue.main.async { [weak self, weak map] in
                guard let self, let map, self.clusteringGeneration == generation else { return }
                self.pendingClustering = nil
                guard self.state.cameraCommand == command, self.clustersEnabled == enabled,
                      !Self.usesIndividualPins(at: map.camera.centerCoordinateDistance) == enabled else { return }
                // Only nearby stale annotations need re-registration. Keep distant
                // IDs pending: a later pan refreshes them, or viewFor configures a
                // freshly dequeued view with the current mode.
                let nearby = Self.clusteringRefreshRect(map.visibleMapRect)
                let existing = self.annotations.values.filter {
                    self.staleClusteringIDs.contains($0.venue.id) && nearby.contains(MKMapPoint($0.coordinate))
                }
                self.staleClusteringIDs.subtract(existing.map { $0.venue.id })
                // Remove views with their old clustering identifiers intact. The
                // delegate configures the new mode when MapKit dequeues them again.
                map.removeAnnotations(existing)
                map.addAnnotations(existing)
                self.synchronizeSelection(map)
                if !enabled { self.state.clusterMembers = [] }
            }
        }
        private static func clusteringRefreshRect(_ rect: MKMapRect) -> MKMapRect {
            rect.insetBy(dx: -rect.size.width, dy: -rect.size.height)
        }
        private func configureMarkerClustering(_ view: MKMarkerAnnotationView) {
            view.clusteringIdentifier = clustersEnabled ? "venues" : nil
            view.displayPriority = clustersEnabled ? .defaultHigh : .required
        }
        func mapView(_ mapView: MKMapView, viewFor annotation: any MKAnnotation) -> MKAnnotationView? {
            if let annotation = annotation as? VenueAnnotation {
                guard let view = mapView.dequeueReusableAnnotationView(withIdentifier: "venue", for: annotation) as? MKMarkerAnnotationView else { return nil }
                view.canShowCallout = false
                configureMarkerClustering(view)
                staleClusteringIDs.remove(annotation.venue.id)
                view.glyphText = annotation.venue.category.glyph
                view.markerTintColor = annotation.venue.category.platformColor
                view.titleVisibility = .adaptive
                #if os(iOS)
                view.isAccessibilityElement = true
                view.accessibilityTraits = .button
                view.accessibilityLabel = annotation.venue.name
                view.accessibilityIdentifier = "pin-\(annotation.venue.id)"
                #else
                view.setAccessibilityIdentifier("pin-\(annotation.venue.id)")
                #endif
                return view
            }
            if let annotation = annotation as? MKClusterAnnotation {
                guard let view = mapView.dequeueReusableAnnotationView(withIdentifier: "cluster", for: annotation) as? MKMarkerAnnotationView else { return nil }
                view.canShowCallout = false
                view.glyphText = "\(annotation.memberAnnotations.count)"
                view.titleVisibility = .hidden
                #if os(iOS)
                view.isAccessibilityElement = true
                view.accessibilityTraits = .button
                view.accessibilityIdentifier = "cluster-pins"
                view.accessibilityLabel = "\(annotation.memberAnnotations.count) venues. Show members."
                #else
                view.setAccessibilityIdentifier("cluster-pins")
                #endif
                return view
            }
            return nil
        }
        func mapView(_ mapView: MKMapView, didSelect view: MKAnnotationView) {
            if view.annotation is MKClusterAnnotation, !clustersEnabled {
                if let annotation = view.annotation { mapView.deselectAnnotation(annotation, animated: false) }
                return
            }
            selectionEvent += 1
            let event = selectionEvent
            let command = state.cameraCommand
            let filters = state.filters
            if let annotation = view.annotation as? VenueAnnotation {
                if state.selection != annotation.venue.id {
                    let id = annotation.venue.id
                    DispatchQueue.main.async { [weak self] in
                        guard let self, self.selectionEvent == event, self.state.cameraCommand == command, self.state.filters == filters,
                              let venue = self.state.matches.first(where: { $0.id == id }) else { return }
                        self.state.select(venue)
                    }
                }
            } else if let cluster = view.annotation as? MKClusterAnnotation {
                let ids = cluster.memberAnnotations.compactMap { ($0 as? VenueAnnotation)?.venue.id }
                DispatchQueue.main.async { [weak self, weak mapView] in
                    guard let self, let mapView, self.clustersEnabled, self.selectionEvent == event, self.state.cameraCommand == command,
                          self.state.filters == filters else { return }
                    let currentIDs = ids.filter { id in self.state.matches.contains { $0.id == id } }
                    guard !currentIDs.isEmpty else { return }
                    self.state.showCluster(currentIDs)
                    mapView.deselectAnnotation(cluster, animated: false)
                }
            }
        }
        #if os(macOS)
        func mapView(_ mapView: MKMapView, regionWillChangeAnimated animated: Bool) {
            // Native window resizing can emit several region callbacks at one size.
            // Suppress them until actual input in this map starts a new gesture.
            if programmatic || lastRegionSize != mapView.bounds.size { userRegionChange = false }
        }
        #endif
        func mapView(_ mapView: MKMapView, regionDidChangeAnimated animated: Bool) {
            updateClustering(mapView)
            #if os(macOS)
            let userInitiated = !programmatic && userRegionChange
            lastRegionSize = mapView.bounds.size
            #else
            let userInitiated = !programmatic
            #endif
            let rect = mapView.visibleMapRect
            DispatchQueue.main.async { [weak self] in
                self?.state.cameraChanged(rect, userInitiated: userInitiated)
            }
        }
        func mapViewDidFailLoadingMap(_ mapView: MKMapView, withError error: any Error) {
            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                if !self.state.mapImageryUnavailable { self.state.mapImageryUnavailable = true }
            }
        }
        func mapViewDidFinishLoadingMap(_ mapView: MKMapView) {
            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                if self.state.mapImageryUnavailable { self.state.mapImageryUnavailable = false }
            }
        }
    }
}

#if os(iOS)
extension VenueMap: UIViewRepresentable {
    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView(); context.coordinator.configure(map); return map
    }
    func updateUIView(_ map: MKMapView, context: Context) { context.coordinator.update(map, state: state) }
}
#else
extension VenueMap: NSViewRepresentable {
    func makeNSView(context: Context) -> MKMapView {
        let map = MKMapView(); context.coordinator.configure(map); return map
    }
    func updateNSView(_ map: MKMapView, context: Context) { context.coordinator.update(map, state: state) }
}
#endif

extension CaffeyeCore.Category {
    var color: Color {
        switch self {
        case .coffee: .brown
        case .roasters: .orange
        case .bakery: .yellow
        case .tea: .green
        case .dessert: .pink
        case .specialty: .purple
        }
    }
    #if os(iOS)
    var platformColor: UIColor { UIColor(color) }
    #else
    var platformColor: NSColor { NSColor(color) }
    #endif
}
