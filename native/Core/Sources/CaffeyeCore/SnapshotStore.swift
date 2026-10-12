import Foundation

/// Provider adapters export this schema; the app never needs a Places response.
/// Source permission is an upstream responsibility, not inferred from field names.
public actor SnapshotStore {
    public static let maximumBytes = 20 * 1024 * 1024
    private let file: URL
    public init(file: URL) { self.file = file }

    public static func decode(_ data: Data) throws -> Snapshot {
        guard data.count <= maximumBytes else { throw SnapshotError.tooLarge }
        return try JSONDecoder().decode(Snapshot.self, from: data).validated()
    }
    public func load() throws -> Snapshot {
        try Self.decode(Data(contentsOf: file))
    }
    @discardableResult
    public func save(_ data: Data) throws -> Snapshot {
        let snapshot = try Self.decode(data)
        let normalized = try JSONEncoder().encode(snapshot)
        try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try normalized.write(to: file, options: .atomic)
        return snapshot
    }
    @discardableResult
    public func refresh(from url: URL) async throws -> Snapshot {
        guard url.scheme?.lowercased() == "https", url.host != nil else { throw SnapshotError.insecureEndpoint }
        var request = URLRequest(url: url, cachePolicy: .reloadRevalidatingCacheData, timeoutInterval: 20)
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        guard let response = response as? HTTPURLResponse, (200...299).contains(response.statusCode),
              response.url?.scheme == "https" else { throw URLError(.badServerResponse) }
        guard response.expectedContentLength <= Self.maximumBytes else { throw SnapshotError.tooLarge }
        var data = Data()
        for try await byte in bytes {
            guard data.count < Self.maximumBytes else { throw SnapshotError.tooLarge }
            data.append(byte)
        }
        try Task.checkCancellation()
        return try save(data)
    }
}
