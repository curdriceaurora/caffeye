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
        return URLSession(configuration: configuration, delegate: HTTPSRedirects(), delegateQueue: nil)
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
        let data = try handle.read(upToCount: maximumBytes + 1) ?? Data()
        guard data.count <= maximumBytes else { throw SnapshotError.tooLarge }
        return data
    }
    public func load() throws -> Snapshot { try Self.decode(Self.readFile(file)) }
    @discardableResult
    public func importFile(_ url: URL) throws -> Snapshot { try save(Self.readFile(url)) }
    @discardableResult
    public func save(_ data: Data) throws -> Snapshot {
        let snapshot = try Self.decode(data)
        let normalized = try JSONEncoder().encode(snapshot)
        guard normalized.count <= Self.maximumBytes else { throw SnapshotError.tooLarge }
        try Task.checkCancellation()
        try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try normalized.write(to: file, options: .atomic)
        return snapshot
    }
    @discardableResult
    public func refresh(from url: URL) async throws -> Snapshot {
        try Task.checkCancellation()
        guard Self.isSecureEndpoint(url) else { throw SnapshotError.insecureEndpoint }
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (bytes, response) = try await session.bytes(for: request)
        guard let response = response as? HTTPURLResponse, (200...299).contains(response.statusCode),
              let finalURL = response.url, Self.isSecureEndpoint(finalURL) else { throw URLError(.badServerResponse) }
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

private final class HTTPSRedirects: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(request.url.map(SnapshotStore.isSecureEndpoint) == true ? request : nil)
    }
}
