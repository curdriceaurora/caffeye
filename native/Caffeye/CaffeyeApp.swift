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
        .windowResizability(.contentMinSize)
        .commands { DiscoveryCommands() }
        #endif
    }
}

#if os(macOS)
struct DiscoveryCommandActions {
    var reset: @MainActor () -> Void
    var back: @MainActor () -> Void
    var canGoBack: Bool
}

private struct DiscoveryCommandsKey: FocusedValueKey {
    typealias Value = DiscoveryCommandActions
}

extension FocusedValues {
    var discoveryCommands: DiscoveryCommandActions? {
        get { self[DiscoveryCommandsKey.self] }
        set { self[DiscoveryCommandsKey.self] = newValue }
    }
}

@MainActor struct DiscoveryCommands: Commands {
    @FocusedValue(\.discoveryCommands) private var actions
    var body: some Commands {
        CommandGroup(after: .toolbar) {
            Button("Back to list") { actions?.back() }
                .keyboardShortcut("[", modifiers: .command)
                .disabled(actions?.canGoBack != true)
            Button("Reset discovery") { actions?.reset() }
                .keyboardShortcut("r", modifiers: [.command, .shift])
                .disabled(actions == nil)
        }
    }
}
#endif
