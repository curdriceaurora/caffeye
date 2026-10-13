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

@MainActor struct VenueMap {
    var state: DiscoveryState
    func makeCoordinator() -> Coordinator { Coordinator(state) }

    @MainActor final class Coordinator: NSObject, MKMapViewDelegate {
        var state: DiscoveryState
        private var annotations: [String: VenueAnnotation] = [:]
        var lastCommand = -1
        var programmatic = false
        init(_ state: DiscoveryState) { self.state = state }

        func configure(_ map: MKMapView) {
            programmatic = true
            map.delegate = self
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
                map.setVisibleMapRect(state.cameraRect, animated: false)
                // Delegate callbacks may be synchronous; publish geometry on the next run loop.
                DispatchQueue.main.async { [weak self, weak map] in
                    guard let self, let map else { return }
                    self.state.cameraChanged(map.visibleMapRect, userInitiated: false)
                    self.programmatic = false
                }
            }
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
        func mapView(_ mapView: MKMapView, viewFor annotation: any MKAnnotation) -> MKAnnotationView? {
            if let annotation = annotation as? VenueAnnotation {
                let view = mapView.dequeueReusableAnnotationView(withIdentifier: "venue", for: annotation) as! MKMarkerAnnotationView
                view.canShowCallout = false
                view.clusteringIdentifier = "venues"
                view.glyphText = annotation.venue.category.glyph
                view.markerTintColor = annotation.venue.category.platformColor
                view.titleVisibility = .adaptive
                view.displayPriority = .defaultHigh
                #if os(iOS)
                view.isAccessibilityElement = true
                view.accessibilityTraits = .button
                view.accessibilityLabel = annotation.venue.name
                view.accessibilityIdentifier = "pin-\(annotation.venue.id)"
                #endif
                return view
            }
            if let annotation = annotation as? MKClusterAnnotation {
                let view = mapView.dequeueReusableAnnotationView(withIdentifier: "cluster", for: annotation) as! MKMarkerAnnotationView
                view.canShowCallout = false
                view.glyphText = "\(annotation.memberAnnotations.count)"
                view.titleVisibility = .hidden
                #if os(iOS)
                view.isAccessibilityElement = true
                view.accessibilityTraits = .button
                view.accessibilityIdentifier = "cluster-pins"
                view.accessibilityLabel = "\(annotation.memberAnnotations.count) venues. Show members."
                #endif
                return view
            }
            return nil
        }
        func mapView(_ mapView: MKMapView, didSelect view: MKAnnotationView) {
            if let annotation = view.annotation as? VenueAnnotation {
                if state.selection != annotation.venue.id {
                    DispatchQueue.main.async { [weak self] in self?.state.select(annotation.venue) }
                }
            } else if let cluster = view.annotation as? MKClusterAnnotation {
                let ids = cluster.memberAnnotations.compactMap { ($0 as? VenueAnnotation)?.venue.id }
                DispatchQueue.main.async { [weak self, weak mapView] in
                    guard let self, let mapView else { return }
                    self.state.showCluster(ids)
                    mapView.deselectAnnotation(cluster, animated: false)
                }
            }
        }
        func mapView(_ mapView: MKMapView, regionDidChangeAnimated animated: Bool) {
            let userInitiated = !programmatic
            let rect = mapView.visibleMapRect
            DispatchQueue.main.async { [weak self] in self?.state.cameraChanged(rect, userInitiated: userInitiated) }
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
