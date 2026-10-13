import SwiftUI
import MapKit
import CaffeyeCore

struct VenueDetail: View {
    let venue: Venue
    let priors: RatingPriors?
    var back: () -> Void
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Button("Back to list", systemImage: "chevron.left", action: back)
                    .accessibilityIdentifier("back-to-list")
                VStack(alignment: .leading, spacing: 8) {
                    Text("\(venue.category.glyph) \(venue.category.label) · \(venue.area)").foregroundStyle(.secondary)
                    Text(venue.name).font(.title2.bold()).accessibilityIdentifier("detail-name")
                    Text(venue.model == .franchise ? "Franchise" : "Independent spot").font(.caption)
                    if venue.curated == true { Label("Curated", systemImage: "checkmark.seal").font(.caption) }
                    if let rating = venue.rating, let priors {
                        Text("◆ \(String(format: "%.1f", priors.score(venue))) weighted score").font(.headline)
                        Text("\(rating.provenance.source) · ★ \(String(format: "%.1f", rating.average)) · \(rating.count.formatted()) reviews")
                            .font(.subheadline).foregroundStyle(.secondary)
                        provenance(rating.provenance)
                    } else { Text(priors == nil ? "Ratings omitted from this snapshot" : "No public rating yet").foregroundStyle(.secondary) }
                }
                if let summary = venue.summary, !summary.isEmpty { Text(summary) }
                let features = Feature.allCases.filter { $0.matches(venue) }.map(\.label)
                if !features.isEmpty { section("Best for") { Text(features.joined(separator: " · ")) } }
                if !(venue.loved ?? []).isEmpty || venue.signature != nil {
                    section("Known for") {
                        if let loved = venue.loved { Text(loved.joined(separator: " · ")) }
                        if let signature = venue.signature { Text("Try the \(signature).") }
                    }
                }
                section("Location & hours") {
                    Text(venue.address)
                    Text(venue.hours ?? "Hours not verified")
                }
                if let work = venue.work {
                    section("Coworking") {
                        Text(work.label).bold()
                        Text(work.note)
                        if work.hasMeetingRoom {
                            Text("Meeting room").font(.headline)
                            Text(work.meetingRoomNote ?? "Contact the venue for meeting room availability.")
                        }
                        if let source = work.provenance { provenance(source) }
                    }
                } else {
                    section("Work suitability") { Text("Unknown · amenities not yet verified for this venue.") }
                }
                if let late = venue.late {
                    section(late.tier == .midnight ? "Open until midnight" : "Open till 10pm+") { Text(late.when) }
                }
                section("Open in") {
                    Button("Apple Maps", systemImage: "map") {
                        let item = mapItem()
                        item.name = venue.name
                        item.openInMaps()
                    }
                    if let url = Venue.actionURL(venue.googleURL) { Link("Google Maps", destination: url) }
                    if let url = Venue.actionURL(venue.yelpURL) { Link("Yelp", destination: url) }
                    if let url = Venue.actionURL(venue.website) { Link("Website", destination: url) }
                }
                provenance(venue.provenance)
                Text("Ratings, hours, and addresses change. Verify before visiting.")
                    .font(.caption).foregroundStyle(.secondary)
            }.frame(maxWidth: .infinity, alignment: .leading).padding()
        }
        .id(venue.id)
    }
    private func mapItem() -> MKMapItem {
        // Xcode 16 CI has the older SDK; newer SDKs provide this initializer.
        #if compiler(>=6.2)
        if #available(iOS 26, macOS 26, *) {
            let location = CLLocation(latitude: venue.coordinate.latitude, longitude: venue.coordinate.longitude)
            return MKMapItem(location: location, address: nil)
        }
        #endif
        return MKMapItem(placemark: MKPlacemark(coordinate: venue.coordinate.location))
    }
    private func section<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.headline)
            content()
        }
    }
    private func provenance(_ source: Provenance) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text("Source: \(source.source)")
            if let verified = source.verified { Text("Verified \(verified)") }
            if let attribution = source.attribution { Text(attribution) }
        }.font(.caption).foregroundStyle(.secondary)
    }
}
