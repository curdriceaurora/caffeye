import Foundation

public enum Category: String, Codable, CaseIterable, Sendable, Identifiable {
    case coffee = "Coffee", roasters = "Roasters", bakery = "Bakery+Cafe"
    case tea = "Tea/Boba", dessert = "Dessert Cafe", specialty = "Specialty"
    public var id: String { rawValue }
    public var label: String { rawValue.replacingOccurrences(of: "+", with: " & ") }
    public var glyph: String {
        switch self {
        case .coffee: "☕"
        case .roasters: "🫘"
        case .bakery: "🥐"
        case .tea: "🧋"
        case .dessert: "🍰"
        case .specialty: "✦"
        }
    }
}

public enum Feature: String, CaseIterable, Sendable, Identifiable {
    case work, meeting, late, midnight
    public var id: String { rawValue }
    public var label: String {
        switch self {
        case .work: "Work-friendly"
        case .meeting: "Meeting room"
        case .late: "Open late"
        case .midnight: "Until midnight"
        }
    }
    public func matches(_ venue: Venue) -> Bool {
        switch self {
        case .work: venue.work?.tier == .excellent
        case .meeting: venue.work?.hasMeetingRoom == true
        case .late: venue.late != nil
        case .midnight: venue.late?.tier == .midnight
        }
    }
}

public struct Coordinate: Codable, Hashable, Sendable {
    public var latitude: Double
    public var longitude: Double
    public init(latitude: Double, longitude: Double) {
        self.latitude = latitude; self.longitude = longitude
    }
    public var isValid: Bool {
        latitude.isFinite && longitude.isFinite && (-90...90).contains(latitude)
            && (-180...180).contains(longitude) && !(latitude == 0 && longitude == 0)
    }
}

public struct Provenance: Codable, Hashable, Sendable {
    public var source: String
    public var verified: String?
    public var attribution: String?
    public init(source: String, verified: String? = nil, attribution: String? = nil) {
        self.source = source; self.verified = verified; self.attribution = attribution
    }
}

public struct Rating: Codable, Hashable, Sendable {
    public var average: Double
    public var count: Int
    public var provenance: Provenance
    public init(average: Double, count: Int, provenance: Provenance) {
        self.average = average; self.count = count; self.provenance = provenance
    }
}

public struct WorkInfo: Codable, Hashable, Sendable {
    public enum Tier: String, Codable, Sendable { case excellent, good, limited }
    public var tier: Tier
    public var note: String
    public var hasMeetingRoom: Bool
    public var meetingRoomNote: String?
    public var provenance: Provenance?
    public var label: String {
        switch tier { case .excellent: "Coworking-ready"; case .good: "Workable"; case .limited: "Quick-grab" }
    }
}

public struct LateInfo: Codable, Hashable, Sendable {
    public enum Tier: String, Codable, Sendable { case late = "10pm+", midnight }
    public var tier: Tier
    public var when: String
}

public struct Venue: Codable, Hashable, Identifiable, Sendable {
    public enum BusinessModel: String, Codable, Sendable { case independent, franchise }
    public var id: String
    public var name: String
    public var category: Category
    public var coordinate: Coordinate
    public var address: String
    public var city: String
    public var county: String?
    public var neighborhood: String?
    public var model: BusinessModel
    public var provenance: Provenance
    public var providerIDs: [String: String]?
    public var types: [String]?
    public var rating: Rating?
    public var hours: String?
    public var summary: String?
    public var loved: [String]?
    public var signature: String?
    public var work: WorkInfo?
    public var late: LateInfo?
    public var website: String?
    public var googleURL: String?
    public var yelpURL: String?
    public var curated: Bool?

    public init(id: String, name: String, category: Category = .coffee,
                coordinate: Coordinate, address: String = "", city: String = "",
                model: BusinessModel = .independent, provenance: Provenance,
                rating: Rating? = nil) {
        self.id = id; self.name = name; self.category = category; self.coordinate = coordinate
        self.address = address; self.city = city; self.model = model
        self.provenance = provenance; self.rating = rating
    }
    public var area: String { neighborhood ?? (city.isEmpty ? "Area not listed" : city) }
    public var searchText: String {
        var parts: [String] = [name, category.rawValue, address, city, county ?? "", area]
        parts.append(contentsOf: [summary ?? "", signature ?? ""])
        parts.append(contentsOf: [work?.tier.rawValue ?? "", work?.note ?? ""])
        parts.append(contentsOf: [late?.tier.rawValue ?? "", late?.when ?? ""])
        if let loved { parts.append(contentsOf: loved) }
        return parts.joined(separator: " ").lowercased()
    }
    public static func actionURL(_ value: String?) -> URL? {
        guard let value, let url = URL(string: value),
              ["https", "http"].contains(url.scheme?.lowercased() ?? ""),
              let host = url.host, !host.isEmpty, url.user == nil, url.password == nil else { return nil }
        return url
    }
}

public struct RatingPriors: Codable, Hashable, Sendable {
    public var mean: Double
    public var weight: Double
    public var provenance: Provenance
    public init(mean: Double, weight: Double, provenance: Provenance) {
        self.mean = mean; self.weight = weight; self.provenance = provenance
    }
    public func score(_ venue: Venue) -> Double {
        let count = Double(venue.rating?.count ?? 0)
        let average = venue.rating?.average ?? mean
        let total = count + weight
        return (count / total) * average + (weight / total) * mean
    }
}

public struct Snapshot: Codable, Equatable, Sendable {
    public var schemaVersion: Int
    public var revision: String
    public var region: String
    public var isDemo: Bool
    public var priors: RatingPriors?
    public var venues: [Venue]
    public init(revision: String, region: String = "Metro Atlanta", isDemo: Bool = false,
                priors: RatingPriors? = nil, venues: [Venue]) {
        schemaVersion = 1; self.revision = revision; self.region = region
        self.isDemo = isDemo; self.priors = priors; self.venues = venues
    }
    public func validated() throws -> Snapshot {
        guard schemaVersion == 1 else { throw SnapshotError.unsupportedVersion }
        guard !revision.isEmpty, !region.isEmpty, !venues.isEmpty else { throw SnapshotError.invalidMetadata }
        if let priors {
            guard priors.mean.isFinite, (0...5).contains(priors.mean),
                  priors.weight.isFinite, priors.weight > 0,
                  !priors.provenance.source.isEmpty else { throw SnapshotError.invalidMetadata }
        } else if venues.contains(where: { $0.rating != nil }) {
            throw SnapshotError.invalidMetadata
        }
        var ids = Set<String>()
        for venue in venues {
            guard !venue.id.isEmpty, !venue.name.isEmpty, venue.coordinate.isValid,
                  !venue.provenance.source.isEmpty, ids.insert(venue.id).inserted else {
                throw SnapshotError.invalidVenue(venue.id)
            }
            if let rating = venue.rating {
                guard rating.average.isFinite, (0...5).contains(rating.average), rating.count >= 0,
                      !rating.provenance.source.isEmpty else { throw SnapshotError.invalidVenue(venue.id) }
            }
        }
        return self
    }
    public var ranked: [Venue] {
        venues.enumerated().sorted {
            if let priors {
                let a = priors.score($0.element), b = priors.score($1.element)
                return a == b ? $0.offset < $1.offset : a > b
            }
            let order = $0.element.name.localizedStandardCompare($1.element.name)
            return order == .orderedSame ? $0.offset < $1.offset : order == .orderedAscending
        }.map(\.element)
    }
}

public enum SnapshotError: LocalizedError {
    case unsupportedVersion, invalidMetadata, invalidVenue(String), tooLarge, insecureEndpoint
    public var errorDescription: String? {
        switch self {
        case .unsupportedVersion: "This snapshot format is not supported."
        case .invalidMetadata: "The snapshot has invalid metadata or ranking priors."
        case .invalidVenue(let id): "Invalid or duplicate venue: \(id)."
        case .tooLarge: "The snapshot exceeds the 20 MB limit."
        case .insecureEndpoint: "Use an HTTPS URL for snapshot updates."
        }
    }
}

public struct Filters: Equatable, Sendable {
    public var categories: Set<Category> = []
    public var features: Set<Feature> = []
    public var includeFranchises = false
    public var search = ""
    public init() {}
    public func matches(_ venue: Venue) -> Bool {
        matches(venue, words: searchWords, indexedText: nil)
    }
    /// Normalize the query once per pass; snapshot owners can reuse their search index.
    public func matching(_ venues: [Venue], searchIndex: [String: String]) -> [Venue] {
        let words = searchWords
        return venues.filter { matches($0, words: words, indexedText: searchIndex[$0.id]) }
    }
    private var searchWords: [Substring] {
        search.lowercased().split(whereSeparator: { $0.isWhitespace })
    }
    private func matches(_ venue: Venue, words: [Substring], indexedText: String?) -> Bool {
        guard includeFranchises || venue.model == .independent,
              categories.isEmpty || categories.contains(venue.category),
              features.allSatisfy({ $0.matches(venue) }) else { return false }
        guard !words.isEmpty else { return true }
        let text = indexedText ?? venue.searchText
        return words.allSatisfy { text.contains($0) }
    }
}
