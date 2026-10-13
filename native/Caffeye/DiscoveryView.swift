import SwiftUI
import CaffeyeCore

struct DiscoveryView: View {
    @Bindable var model: AppModel
    @State private var state = DiscoveryState()
    @FocusState private var searchFocused: Bool
    @AccessibilityFocusState private var accessibleVenue: String?
    @AccessibilityFocusState private var resultsFocused: Bool
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                coverage
                GeometryReader { geometry in
                    if geometry.size.width >= 760 {
                        #if os(macOS)
                        HSplitView {
                            results(state.rows).frame(minWidth: 280, idealWidth: 330, maxWidth: 430)
                            workspace.frame(minWidth: 350)
                        }
                        #else
                        HStack(spacing: 0) {
                            results(state.rows).frame(width: min(360, geometry.size.width * 0.36))
                            Divider()
                            workspace
                        }
                        #endif
                    } else {
                        VStack(spacing: 0) {
                            VenueMap(state: state)
                                .frame(height: max(typeSize.isAccessibilitySize ? 60 : 100, min(typeSize.isAccessibilitySize ? 100 : 230, geometry.size.height * (typeSize.isAccessibilitySize ? 0.18 : 0.32))))
                            Divider()
                            ZStack {
                                results(state.browsingRows, followsSelection: false)
                                    .opacity(state.selected == nil ? 1 : 0)
                                    .allowsHitTesting(state.selected == nil)
                                    .accessibilityHidden(state.selected != nil)
                                if let venue = state.selected {
                                    VenueDetail(venue: venue, priors: state.current?.priors, back: state.back)
                                        .background(.background)
                                }
                            }
                        }
                    }
                }
            }
            .navigationTitle(state.current?.region ?? "Metro Atlanta")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .searchable(text: $state.filters.search, prompt: "Search by name, drink, or area")
            .searchFocused($searchFocused)
            .toolbar { toolbar }
            .onChange(of: state.selection) { old, selected in
                if selected != nil { searchFocused = false }
                if selected == nil, let old {
                    Task { @MainActor in
                        await Task.yield()
                        if state.selection == nil {
                            if state.browsingRows.contains(where: { $0.id == old }) { accessibleVenue = old }
                            else { resultsFocused = true }
                        }
                    }
                }
            }
            .onChange(of: state.deselectionNotice) {
                AccessibilityNotification.Announcement(state.deselectionMessage).post()
            }
            .onChange(of: model.generation, initial: true) {
                if let snapshot = model.snapshot { state.accept(snapshot) }
            }
            .alert("Venues unavailable", isPresented: Binding(get: { model.failure != nil }, set: { if !$0 { model.failure = nil } })) {
                Button("OK") { model.failure = nil }
            } message: { Text(model.failure ?? "") }
            #if os(macOS)
            .onExitCommand { state.back() }
            .focusedSceneValue(\.discoveryCommands, DiscoveryCommandActions(
                reset: state.reset, back: state.back,
                canGoBack: state.selection != nil))
            #endif
        }
    }

    @ViewBuilder private var coverage: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                if model.busy { ProgressView().controlSize(.small).accessibilityLabel("Loading venues") }
                Text(typeSize.isAccessibilitySize && !model.busy && state.current != nil
                     ? (state.current?.isDemo == true ? "Fictional demo" : "Venues")
                     : (state.current?.isDemo == true ? "Demo data · fictional venues and ratings" : model.status))
                    .font(.caption).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityLabel(state.current?.isDemo == true ? "Demo data · fictional venues and ratings" : model.status)
                Spacer()
            }
            Toggle(isOn: $state.filters.includeFranchises) {
                Text("Include franchise stores").fixedSize(horizontal: false, vertical: true)
            }.font(.subheadline)
                .accessibilityIdentifier("include-franchises")
            if state.mapImageryUnavailable {
                Text("Map imagery unavailable")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if state.pending != nil {
                HStack {
                    Text("Updated venues available").font(.caption)
                    Button("Update list") { state.applyPending() }.font(.caption)
                }
            }
            if !state.filters.categories.isEmpty || !state.filters.features.isEmpty {
                Text((state.filters.categories.sorted { $0.rawValue < $1.rawValue }.map { "\($0.glyph) \($0.label)" }
                      + state.filters.features.sorted { $0.rawValue < $1.rawValue }.map { "\($0.glyph) \($0.label)" }).joined(separator: " · "))
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal).padding(.vertical, 8)
    }

    private var workspace: some View {
        VStack(spacing: 0) {
            VenueMap(state: state)
            if let venue = state.selected {
                Divider()
                VenueDetail(venue: venue, priors: state.current?.priors, back: state.back)
                    .frame(maxHeight: 360)
            }
        }
    }

    private func results(_ rows: [Venue], followsSelection: Bool = true) -> some View {
        VStack(spacing: 0) {
            resultHeader(rows.count).padding()
            if rows.count < state.matches.count {
                Button("Show all \(state.matches.count) matches") { state.showAll() }
                    .padding(.bottom, 8)
            }
            ScrollViewReader { proxy in
                List(selection: Binding<String?>(get: { state.selection }, set: { id in
                    if let id, let venue = state.current?.venues.first(where: { $0.id == id }) {
                        state.select(venue)
                    }
                })) {
                    if !state.clusterMembers.isEmpty {
                        Section("Venues in selected cluster") {
                            ForEach(state.clusterVenues) { venue in row(venue) }
                            Button("Close cluster") { state.clusterMembers = [] }
                        }
                    }
                    Section {
                        ForEach(rows) { venue in row(venue).id(venue.id) }
                    }
                    if rows.isEmpty {
                        ContentUnavailableView("No shops in this view", systemImage: "magnifyingglass", description: Text("Try zooming out, clearing filters, or changing search."))
                    }
                }
                .listStyle(.plain)
                .simultaneousGesture(DragGesture().onChanged { _ in state.reading = true })
                .onAppear {
                    if let id = state.scrollID { proxy.scrollTo(id, anchor: .center) }
                }
                .onChange(of: state.scrollID) {
                    if followsSelection, let id = state.scrollID { proxy.scrollTo(id, anchor: .center) }
                }
                .onChange(of: rows.map(\.id)) { scrollToSelection(proxy, rows: rows, followsSelection: followsSelection) }

            }
        }
    }
    @ViewBuilder private func resultHeader(_ count: Int) -> some View {
        let label = "\(count) \(count < state.matches.count ? "in view" : "spots")"
        let legend = state.listSnapshot?.priors == nil ? "Alphabetical · ratings omitted" : "◆ = weighted score"
        if typeSize.isAccessibilitySize {
            VStack(alignment: .leading, spacing: 6) {
                Text(label).font(.headline).accessibilityIdentifier("results-count").accessibilityAddTraits(.isHeader).accessibilityFocused($resultsFocused)
                Text(legend).font(.caption).foregroundStyle(.secondary)
            }.frame(maxWidth: .infinity, alignment: .leading)
        } else {
            HStack {
                Text(label).font(.headline).accessibilityIdentifier("results-count").accessibilityAddTraits(.isHeader).accessibilityFocused($resultsFocused)
                Spacer()
                Text(legend).font(.caption).foregroundStyle(.secondary)
            }
        }
    }
    private func scrollToSelection(_ proxy: ScrollViewProxy, rows: [Venue], followsSelection: Bool) {
        if followsSelection, let id = state.selection, rows.contains(where: { $0.id == id }) {
            proxy.scrollTo(id, anchor: .center)
        }
    }
    private func row(_ venue: Venue) -> some View {
        Group {
            #if os(macOS)
            VenueRow(venue: venue, priors: state.listSnapshot?.priors)
                .frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
                .accessibilityElement(children: .ignore)
            #else
            Button { state.select(venue) } label: {
                VenueRow(venue: venue, priors: state.listSnapshot?.priors)
                    .frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
            }.buttonStyle(.plain)
            #endif
        }
        .tag(venue.id)
        .accessibilityIdentifier("venue-\(venue.id)")
        .accessibilityFocused($accessibleVenue, equals: venue.id)
        .accessibilityHint("Opens venue details and focuses the map")
        .accessibilityLabel("\(venue.name), \(venue.category.label), \(state.listSnapshot?.priors == nil ? "ratings omitted" : venue.rating == nil ? "no public rating" : "weighted score " + String(format: "%.1f", state.listSnapshot?.priors?.score(venue) ?? 0)), \(venue.area)")
    }

    @ToolbarContentBuilder private var toolbar: some ToolbarContent {
        ToolbarItemGroup {
            Menu("☕ Type") {
                Button("All (\(state.inScope.count))") { state.filters.categories = [] }
                ForEach(CaffeyeCore.Category.allCases) { category in
                    Toggle("\(category.glyph) \(category.label) (\(state.categoryCounts[category, default: 0]))", isOn: categoryBinding(category))
                }
            }.accessibilityLabel("Type").accessibilityIdentifier("type-filter")
            Menu("💻 Useful for") {
                ForEach(Feature.allCases) { feature in
                    Toggle("\(feature.glyph) \(feature.label) (\(state.featureCounts[feature, default: 0]))", isOn: featureBinding(feature))
                }
            }.accessibilityLabel("Useful for").accessibilityIdentifier("feature-filter")
            Button("Reset", systemImage: "arrow.counterclockwise") { state.reset() }
                .accessibilityIdentifier("reset")
                #if os(iOS)
                .keyboardShortcut("r", modifiers: [.command, .shift])
                #endif
        }
    }
    private func categoryBinding(_ category: CaffeyeCore.Category) -> Binding<Bool> {
        Binding(get: { state.filters.categories.contains(category) }, set: {
            if $0 { state.filters.categories.insert(category) } else { state.filters.categories.remove(category) }
        })
    }
    private func featureBinding(_ feature: Feature) -> Binding<Bool> {
        Binding(get: { state.filters.features.contains(feature) }, set: {
            if $0 { state.filters.features.insert(feature) } else { state.filters.features.remove(feature) }
        })
    }
}

struct VenueRow: View {
    let venue: Venue
    let priors: RatingPriors?
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Text(venue.category.glyph).font(.title3)
            VStack(alignment: .leading, spacing: 4) {
                Text(venue.name).font(.headline)
                HStack {
                    Text(venue.category.label)
                    if let priors {
                        Text(venue.rating == nil ? "No rating" : "◆ \(String(format: "%.1f", priors.score(venue)))")
                    }
                }.font(.subheadline).foregroundStyle(.secondary)
                Text(venue.area).font(.caption).foregroundStyle(.secondary)
                let tags = Feature.allCases.filter { $0.matches(venue) }.prefix(3).map(\.label)
                if !tags.isEmpty { Text(tags.joined(separator: " · ")).font(.caption) }
            }
            Spacer(minLength: 0)
        }.padding(.vertical, 4)
    }
}
