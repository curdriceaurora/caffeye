import SwiftUI

@main
struct CaffeyeApp: App {
    @State private var model = AppModel()
    var body: some Scene {
        WindowGroup {
            DiscoveryView(model: model)
                .task { await model.load() }
        }
        #if os(macOS)
        .defaultSize(width: 1180, height: 780)
        #endif
    }
}
