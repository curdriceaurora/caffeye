import Foundation
import Testing
@testable import CaffeyeCore

private final class Responses: @unchecked Sendable {
    let lock = NSLock()
    private var handlers: [URL: @Sendable (SnapshotProtocol) -> Void] = [:]
    func set(_ url: URL, _ handler: @escaping @Sendable (SnapshotProtocol) -> Void) {
        lock.lock(); defer { lock.unlock() }; handlers[url] = handler
    }
    func handler(_ url: URL) -> (@Sendable (SnapshotProtocol) -> Void)? {
        lock.lock(); defer { lock.unlock() }; return handlers[url]
    }
    func remove(_ url: URL) { lock.lock(); defer { lock.unlock() }; handlers[url] = nil }
}

private final class SnapshotProtocol: URLProtocol, @unchecked Sendable {
    static let responses = Responses()
    override class func canInit(with request: URLRequest) -> Bool { request.url?.host == "snapshot.test" }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        guard let url = request.url, let handler = Self.responses.handler(url) else {
            client?.urlProtocol(self, didFailWithError: URLError(.resourceUnavailable)); return
        }
        handler(self)
    }
    override func stopLoading() {}
    func respond(_ data: Data, status: Int = 200, length: Int? = nil, finish: Bool = true) {
        let headers = length.map { ["Content-Length": String($0)] }
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: headers)!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        if finish { client?.urlProtocolDidFinishLoading(self) }
    }
}

@Suite("Failed updates retain offline data", .timeLimit(.minutes(1)))
struct RefreshTests {
    private func good(_ revision: String = "old") -> Snapshot {
        Snapshot(revision: revision, venues: [Venue(id: "one", name: "Cafe", coordinate: .init(latitude: 33.96, longitude: -84.14), provenance: .init(source: "Test"))])
    }
    private func session() -> URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [SnapshotProtocol.self]
        return URLSession(configuration: config)
    }
    @Test("Timeout, interrupted transfer, bad status, and malformed JSON keep the saved snapshot",
           arguments: ["timeout", "interrupted", "status", "invalid", "declared-size"])
    func failures(_ scenario: String) async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let url = URL(string: "https://snapshot.test/" + UUID().uuidString)!
        defer { SnapshotProtocol.responses.remove(url) }
        SnapshotProtocol.responses.set(url) { stub in
            #expect(stub.request.timeoutInterval == 20)
            #expect(stub.request.value(forHTTPHeaderField: "Accept") == "application/json")
            switch scenario {
            case "timeout": stub.client?.urlProtocol(stub, didFailWithError: URLError(.timedOut))
            case "interrupted":
                stub.respond(Data("{\"schemaVersion\":".utf8), finish: false)
                stub.client?.urlProtocol(stub, didFailWithError: URLError(.networkConnectionLost))
            case "status": stub.respond(Data(), status: 503)
            case "declared-size": stub.respond(Data(), length: SnapshotStore.maximumBytes + 1)
            default: stub.respond(Data("not JSON".utf8))
            }
        }
        let connection = session(); defer { connection.invalidateAndCancel() }
        let store = SnapshotStore(file: root.appendingPathComponent("snapshot.json"), session: connection)
        try await store.save(JSONEncoder().encode(good()))
        await #expect(throws: (any Error).self) { try await store.refresh(from: url) }
        #expect(try await store.load() == good())
        #expect(try await SnapshotStore(file: root.appendingPathComponent("snapshot.json")).load() == good())
    }
    @Test("Cancel during a partial response leaves the old snapshot usable")
    func cancellation() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let url = URL(string: "https://snapshot.test/" + UUID().uuidString)!
        defer { SnapshotProtocol.responses.remove(url) }
        let started = AsyncStream<Void> { continuation in
            SnapshotProtocol.responses.set(url) { stub in
                stub.respond(Data("{\"schemaVersion\":".utf8), finish: false)
                continuation.yield(); continuation.finish()
            }
        }
        let connection = session(); defer { connection.invalidateAndCancel() }
        let store = SnapshotStore(file: root.appendingPathComponent("snapshot.json"), session: connection)
        try await store.save(JSONEncoder().encode(good()))
        let original = try SnapshotStore.readFile(root.appendingPathComponent("snapshot.json"))
        let task = Task { try await store.refresh(from: url) }
        var iterator = started.makeAsyncIterator()
        _ = await iterator.next()
        task.cancel()
        await #expect(throws: (any Error).self) { try await task.value }
        #expect(try await store.load() == good())
        #expect(try SnapshotStore.readFile(root.appendingPathComponent("snapshot.json")) == original)
    }
    @Test("Unknown-length streams exceeding the limit cannot overwrite the cache")
    func streamedLimit() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let url = URL(string: "https://snapshot.test/" + UUID().uuidString)!
        defer { SnapshotProtocol.responses.remove(url) }
        SnapshotProtocol.responses.set(url) { $0.respond(Data(repeating: 32, count: SnapshotStore.maximumBytes + 1)) }
        let connection = session(); defer { connection.invalidateAndCancel() }
        let store = SnapshotStore(file: root.appendingPathComponent("snapshot.json"), session: connection)
        try await store.save(JSONEncoder().encode(good()))
        await #expect(throws: SnapshotError.tooLarge) { try await store.refresh(from: url) }
        #expect(try await store.load() == good())
    }
    @Test("Successful replacement is available after reopening the store")
    func success() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let url = URL(string: "https://snapshot.test/" + UUID().uuidString)!
        defer { SnapshotProtocol.responses.remove(url) }
        let data = try JSONEncoder().encode(good("new"))
        SnapshotProtocol.responses.set(url) { $0.respond(data) }
        let connection = session(); defer { connection.invalidateAndCancel() }
        let store = SnapshotStore(file: root.appendingPathComponent("snapshot.json"), session: connection)
        try await store.save(JSONEncoder().encode(good()))
        #expect(try await store.refresh(from: url).revision == "new")
        #expect(try await SnapshotStore(file: root.appendingPathComponent("snapshot.json")).load().revision == "new")
    }
    @Test("Corrupt and oversized local files fail bounded reads and imports preserve good data")
    func localFiles() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let file = root.appendingPathComponent("snapshot.json")
        try Data("broken".utf8).write(to: file)
        await #expect(throws: (any Error).self) { try await SnapshotStore(file: file).load() }
        let store = SnapshotStore(file: file)
        try await store.save(JSONEncoder().encode(good()))
        let huge = root.appendingPathComponent("huge.json")
        try Data().write(to: huge)
        let handle = try FileHandle(forWritingTo: huge)
        try handle.truncate(atOffset: UInt64(SnapshotStore.maximumBytes + 1)); try handle.close()
        #expect(throws: SnapshotError.tooLarge) { try SnapshotStore.readFile(huge) }
        await #expect(throws: SnapshotError.tooLarge) { try await store.importFile(huge) }
        #expect(try await store.load() == good())
    }
    @Test("Validated payloads retain future optional fields and original bytes after reopening")
    func futureFields() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let file = root.appendingPathComponent("snapshot.json")
        var object = try #require(JSONSerialization.jsonObject(with: JSONEncoder().encode(good())) as? [String: Any])
        object["futureSnapshot"] = ["arbitrary": [true, false]]
        var venues = try #require(object["venues"] as? [[String: Any]])
        venues[0]["futureVenue"] = ["nested": ["value": "retained"]]
        var coordinate = try #require(venues[0]["coordinate"] as? [String: Any])
        coordinate["futureCoordinate"] = 123
        venues[0]["coordinate"] = coordinate
        object["venues"] = venues
        let original = try JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys])
        let store = SnapshotStore(file: file)
        #expect(try await store.save(original) == good())
        #expect(try SnapshotStore.readFile(file) == original)
        #expect(try await SnapshotStore(file: file).load() == good())
    }
    @Test("Bounded reads accumulate short chunks, accept an exact limit, and reject the next byte")
    func shortReads() throws {
        var chunks = [Data([1]), Data([2, 3]), Data([4]), Data()]
        #expect(try SnapshotStore.readBounded(limit: 4) { _ in chunks.removeFirst() } == Data([1, 2, 3, 4]))
        var oversized = [Data([1, 2]), Data([3, 4]), Data([5])]
        #expect(throws: SnapshotError.tooLarge) {
            try SnapshotStore.readBounded(limit: 4) { _ in oversized.removeFirst() }
        }
        #expect(try SnapshotStore.readBounded(limit: 4) { _ in nil }.isEmpty)
    }
    @Test("Reject insecure and credential-bearing update endpoints", arguments: [
        "http://snapshot.test/", "https://user:pass@snapshot.test/", "file:///tmp/data.json"
    ])
    func endpoints(_ value: String) async {
        let store = SnapshotStore(file: FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString))
        await #expect(throws: SnapshotError.insecureEndpoint) { try await store.refresh(from: URL(string: value)!) }
    }
}
