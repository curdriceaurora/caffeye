import SwiftUI
import MapKit
import CaffeyeCore

struct VenueDetail: View {
    let venue: Venue
    let priors: RatingPriors?
    var back: () -> Void
    @AccessibilityFocusState private var headingFocused: Bool
    var body: some View {
        let detail = VenueDetailPresentation(venue: venue, priors: priors)
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Button(action: back) {
                    Label("Back to list", systemImage: "chevron.left").frame(minHeight: 44)
                }
                    .accessibilityIdentifier("back-to-list")
                VStack(alignment: .leading, spacing: 8) {
                    Text("\(venue.category.glyph) \(venue.category.label) · \(venue.area)").foregroundStyle(.secondary)
                    Text(venue.name).font(.title2.bold()).accessibilityIdentifier("detail-name")
                        .accessibilityAddTraits(.isHeader).accessibilityFocused($headingFocused)
                    Text(venue.model == .franchise ? "Franchise" : "Independent spot").font(.caption)
                    if venue.curated == true { Label("Curated", systemImage: "checkmark.seal").font(.caption) }
                    if let rating = detail.rating {
                        Text("◆ \(String(format: "%.1f", rating.score)) weighted score").font(.headline)
                        Text("\(rating.provenance.source) · ★ \(String(format: "%.1f", rating.average)) · \(rating.count.formatted()) reviews")
                            .font(.subheadline).foregroundStyle(.secondary)
                        provenance(rating.provenance)
                    } else { Text(detail.ratingMessage).foregroundStyle(.secondary) }
                }
                if let summary = detail.summary { Text(summary) }
                let features = Feature.allCases.filter { $0.matches(venue) }.map(\.label)
                if !features.isEmpty { section("Best for") { Text(features.joined(separator: " · ")) } }
                if !detail.loved.isEmpty || detail.signature != nil {
                    section("Known for") {
                        if !detail.loved.isEmpty { Text(detail.loved.joined(separator: " · ")) }
                        if let signature = detail.signature { Text("Try the \(signature).") }
                    }
                }
                section("Location & hours") {
                    Text(venue.address)
                    Text(detail.hours)
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
                    ForEach(detail.links) { link in Link(link.title, destination: link.url) }
                }
                provenance(venue.provenance)
                Text("Ratings, hours, and addresses change. Verify before visiting.")
                    .font(.caption).foregroundStyle(.secondary)
            }.frame(maxWidth: .infinity, alignment: .leading).padding()
        }
        .id(venue.id)
        .task(id: venue.id) { headingFocused = true }
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
            Text(title).font(.headline).accessibilityAddTraits(.isHeader)
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

/// Testable presentation decisions; rendering and spoken accessibility still need UI/device QA.
struct VenueDetailPresentation {
    let venue: Venue
    let priors: RatingPriors?
    struct ExternalLink: Identifiable {
        let title: String
        let url: URL
        var id: String { title }
    }
    private func nonBlank(_ value: String?) -> String? {
        guard let value, !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return nil }
        return value
    }
    var summary: String? { nonBlank(venue.summary) }
    var signature: String? { nonBlank(venue.signature) }
    var loved: [String] { (venue.loved ?? []).compactMap(nonBlank) }
    var hours: String { nonBlank(venue.hours) ?? "Hours not verified" }
    var ratingMessage: String { priors == nil ? "Ratings omitted" : "No public rating yet" }
    var rating: (average: Double, count: Int, provenance: Provenance, score: Double)? {
        guard let rating = venue.rating, let priors else { return nil }
        return (rating.average, rating.count, rating.provenance, priors.score(venue))
    }
    var links: [ExternalLink] {
        [("Google Maps", venue.googleURL), ("Yelp", venue.yelpURL), ("Website", venue.website)].compactMap { title, value in
            Venue.actionURL(value).map { ExternalLink(title: title, url: $0) }
        }
    }
}
