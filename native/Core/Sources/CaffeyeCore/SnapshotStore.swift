import Foundation

/// Provider adapters export this schema; source permissions remain an upstream decision.
public actor SnapshotStore {
    public static let maximumBytes = 20 * 1024 * 1024
    private let file: URL
    private let session: URLSession

    public init(file: URL, session: URLSession? = nil) {
        self.file = file
        self.session = session ?? Self.updateSession()
    }
    private static func updateSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 20
        configuration.timeoutIntervalForResource = 30
        return URLSession(configuration: configuration)
    }
    public static func isSecureEndpoint(_ url: URL) -> Bool {
        url.scheme?.lowercased() == "https" && !(url.host ?? "").isEmpty
            && url.user == nil && url.password == nil
    }
    public static func decode(_ data: Data) throws -> Snapshot {
        guard data.count <= maximumBytes else { throw SnapshotError.tooLarge }
        return try JSONDecoder().decode(Snapshot.self, from: data).validated()
    }
    /// Bound reads before decoding, including corrupt caches and files replaced during import.
    public static func readFile(_ url: URL) throws -> Data {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        return try readBounded { try handle.read(upToCount: $0) }
    }
    /// Short reads are not EOF. Keep one extra byte available to detect oversized input.
    static func readBounded(limit: Int = maximumBytes, _ readChunk: (Int) throws -> Data?) throws -> Data {
        var data = Data()
        while let chunk = try readChunk(min(64 * 1024, limit + 1 - data.count)), !chunk.isEmpty {
            data.append(chunk)
            guard data.count <= limit else { throw SnapshotError.tooLarge }
        }
        return data
    }
    public func load() throws -> Snapshot { try Self.decode(Self.readFile(file)) }
    @discardableResult
    public func importFile(_ url: URL) throws -> Snapshot { try save(Self.readFile(url)) }
    @discardableResult
    public func save(_ data: Data) throws -> Snapshot {
        let snapshot = try Self.decode(data)
        try Task.checkCancellation()
        try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        // Persist the validated input, preserving unknown optional fields at every nesting level.
        try data.write(to: file, options: .atomic)
        return snapshot
    }
    @discardableResult
    public func refresh(from url: URL) async throws -> Snapshot {
        try Task.checkCancellation()
        guard Self.isSecureEndpoint(url) else { throw SnapshotError.insecureEndpoint }
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let data = try await SnapshotDownload().data(for: request, session: session)
        try Task.checkCancellation()
        return try save(data)
    }
}
