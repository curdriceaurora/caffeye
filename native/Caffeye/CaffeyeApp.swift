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
        .commands { DiscoveryCommands() }
        #endif
    }
}

#if os(macOS)
struct DiscoveryCommandActions {
    var reset: @MainActor () -> Void
    var back: @MainActor () -> Void
    var importSnapshot: @MainActor () -> Void
    var updateSnapshot: @MainActor () -> Void
    var settings: @MainActor () -> Void
    var canUpdate: Bool
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
        CommandGroup(after: .newItem) {
            Button("Import offline snapshot…") { actions?.importSnapshot() }
                .keyboardShortcut("o", modifiers: [.command, .shift])
                .disabled(actions == nil)
            Button("Update snapshot") { actions?.updateSnapshot() }
                .disabled(actions?.canUpdate != true)
        }
        CommandGroup(replacing: .appSettings) {
            Button("Data settings…") { actions?.settings() }
                .keyboardShortcut(",", modifiers: .command)
                .disabled(actions == nil)
        }
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
