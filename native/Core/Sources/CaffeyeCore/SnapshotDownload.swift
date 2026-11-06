import Foundation

/// URLSession delivers Data chunks rather than one AsyncBytes element per byte.
/// All mutable state is protected by lock; callbacks and cancellation may run concurrently.
final class SnapshotDownload: NSObject, URLSessionDataDelegate, @unchecked Sendable {
    private let lock = NSLock()
    private weak var task: URLSessionDataTask?
    private var continuation: CheckedContinuation<Data, any Error>?
    private var outcome: Result<Data, any Error>?
    private var buffer = Data()
    private var acceptedResponse = false

    func data(for request: URLRequest, session: URLSession) async throws -> Data {
        try Task.checkCancellation()
        guard session.configuration.identifier == nil else {
            throw URLError(.unsupportedURL, userInfo: [NSLocalizedDescriptionKey: "Snapshot updates require a foreground URL session."])
        }
        return try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { continuation in
                start(request, session: session, continuation: continuation)
            }
        } onCancel: {
            self.finish(.failure(CancellationError()), cancelTransport: true)
        }
    }

    private func start(_ request: URLRequest, session: URLSession,
                       continuation: CheckedContinuation<Data, any Error>) {
        lock.lock()
        if let outcome {
            lock.unlock()
            continuation.resume(with: outcome)
            return
        }
        self.continuation = continuation
        let transport = session.dataTask(with: request)
        transport.delegate = self
        task = transport
        lock.unlock()
        transport.resume()
    }

    private func finish(_ result: Result<Data, any Error>, cancelTransport: Bool = false) {
        lock.lock()
        finishLocked(result, cancelTransport: cancelTransport)
    }

    /// Resolves once and unlocks before resuming callers or invoking URLSession.
    private func finishLocked(_ result: Result<Data, any Error>, cancelTransport: Bool = false) {
        guard outcome == nil else { lock.unlock(); return }
        outcome = result
        let continuation = continuation
        self.continuation = nil
        let transport = task
        task = nil
        buffer = Data()
        lock.unlock()
        if cancelTransport { transport?.cancel() }
        continuation?.resume(with: result)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask,
                    didReceive response: URLResponse,
                    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        guard let response = response as? HTTPURLResponse, (200...299).contains(response.statusCode),
              let url = response.url, SnapshotStore.isSecureEndpoint(url) else {
            finish(.failure(URLError(.badServerResponse)), cancelTransport: true)
            completionHandler(.cancel)
            return
        }
        guard response.expectedContentLength <= SnapshotStore.maximumBytes else {
            finish(.failure(SnapshotError.tooLarge), cancelTransport: true)
            completionHandler(.cancel)
            return
        }
        lock.lock()
        let active = outcome == nil
        acceptedResponse = active
        lock.unlock()
        completionHandler(active ? .allow : .cancel)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        lock.lock()
        guard outcome == nil else { lock.unlock(); return }
        guard data.count <= SnapshotStore.maximumBytes - buffer.count else {
            finishLocked(.failure(SnapshotError.tooLarge), cancelTransport: true)
            return
        }
        buffer.append(data)
        lock.unlock()
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: (any Error)?) {
        lock.lock()
        let result: Result<Data, any Error>
        if let error { result = .failure(error) }
        else if !acceptedResponse { result = .failure(URLError(.badServerResponse)) }
        else { result = .success(buffer) }
        finishLocked(result)
    }

    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(request.url.map(SnapshotStore.isSecureEndpoint) == true ? request : nil)
    }
}
