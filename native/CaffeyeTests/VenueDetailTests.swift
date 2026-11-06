import Testing
import CaffeyeCore
@testable import Caffeye

@MainActor @Suite("Detail presentation")
struct VenueDetailTests {
    private func venue() -> Venue {
        Venue(id: "test", name: "Test cafe", coordinate: .init(latitude: 33.96, longitude: -84.14), provenance: .init(source: "Fixture"))
    }
    @Test("Missing and blank hours stay unknown", arguments: [nil, "", " \n", "Daily 9–5"] as [String?])
    func hours(_ value: String?) {
        var venue = venue(); venue.hours = value
        let detail = VenueDetailPresentation(venue: venue, priors: nil)
        #expect(detail.hours == (value == "Daily 9–5" ? "Daily 9–5" : "Hours not verified"))
    }
    @Test("Empty editorial fields do not create empty known-for content")
    func missingEditorial() {
        var venue = venue(); venue.summary = " \n"; venue.signature = ""; venue.loved = ["", " ", "Espresso"]
        let detail = VenueDetailPresentation(venue: venue, priors: nil)
        #expect(detail.summary == nil)
        #expect(detail.signature == nil)
        #expect(detail.loved == ["Espresso"])
    }
    @Test("Omitted and unrated details never infer a public score")
    func ratingStates() throws {
        var venue = venue()
        let priors = RatingPriors(mean: 4.2, weight: 10, provenance: .init(source: "Fixture"))
        let omitted = VenueDetailPresentation(venue: venue, priors: nil)
        #expect(omitted.rating == nil)
        #expect(omitted.ratingMessage == "Ratings omitted")
        let unrated = VenueDetailPresentation(venue: venue, priors: priors)
        #expect(unrated.rating == nil)
        #expect(unrated.ratingMessage == "No public rating yet")
        venue.rating = Rating(average: 4.6, count: 10, provenance: .init(source: "Permitted fixture"))
        let scored = try #require(VenueDetailPresentation(venue: venue, priors: priors).rating)
        #expect(abs(scored.score - 4.4) < 0.0001)
        #expect(scored.average == 4.6)
        #expect(scored.count == 10)
        #expect(scored.provenance.source == "Permitted fixture")
        #expect(VenueDetailPresentation(venue: venue, priors: nil).rating == nil)
    }
    @Test("Only usable external links appear and retain platform order")
    func links() {
        var venue = venue()
        #expect(VenueDetailPresentation(venue: venue, priors: nil).links.isEmpty)
        venue.googleURL = "https://maps.google.com/example"
        venue.yelpURL = "javascript:alert(1)"
        venue.website = "https://user:password@example.com/"
        #expect(VenueDetailPresentation(venue: venue, priors: nil).links.map(\.title) == ["Google Maps"])
        venue.yelpURL = "https://yelp.com/example"; venue.website = "https://example.com/"
        let links = VenueDetailPresentation(venue: venue, priors: nil).links
        #expect(links.map(\.title) == ["Google Maps", "Yelp", "Website"])
        #expect(links.last?.url.host == "example.com")
    }
}
