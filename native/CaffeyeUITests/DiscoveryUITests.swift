import XCTest

final class DiscoveryUITests: XCTestCase {
    override func setUp() {
        super.setUp()
        continueAfterFailure = false
    }

    @MainActor private func launch(_ arguments: [String] = []) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"] + arguments
        app.launch()
        XCTAssertTrue(app.buttons["reset"].waitForExistence(timeout: 15))
        return app
    }

    @MainActor func testSelectionAndBack() {
        let app = launch()
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'venue-demo-'")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        let discovery = XCTAttachment(screenshot: app.screenshot())
        discovery.name = "Discovery"; discovery.lifetime = .keepAlways
        add(discovery)
        row.tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        let detail = XCTAttachment(screenshot: app.screenshot())
        detail.name = "Venue detail"; detail.lifetime = .keepAlways
        add(detail)
        app.buttons["back-to-list"].tap()
        XCTAssertTrue(row.waitForExistence(timeout: 5))
    }

    @MainActor func testSearchEmptyStateAndReset() {
        let app = launch()
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 5))
        search.tap()
        search.typeText("no-such-venue")
        XCTAssertTrue(app.staticTexts["No shops in this view"].waitForExistence(timeout: 5))
        // Compact search hides the toolbar; regular-width search keeps Reset visible.
        if !app.buttons["reset"].exists {
            let close = app.buttons.matching(NSPredicate(format: "label == 'close' OR label == 'Cancel'")).firstMatch
            XCTAssertTrue(close.waitForExistence(timeout: 5))
            close.tap()
        }
        app.buttons["reset"].tap()
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'venue-demo-'")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 5))
    }
    @MainActor func testClusterShowsSelectableMembers() throws {
        let app = launch()
        try tapVisibleMapButton(app, identifier: "cluster-pins")
        XCTAssertTrue(app.staticTexts["Venues in selected cluster"].waitForExistence(timeout: 5))
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'venue-demo-'")).firstMatch
        row.tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
    }

    @MainActor func testBundledVenuesWithoutRatings() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing", "--bundled-venues-testing"]
        app.launch()
        XCTAssertTrue(app.staticTexts["Alphabetical · ratings omitted"].waitForExistence(timeout: 20))
        let search = app.searchFields.firstMatch
        search.tap(); search.typeText("Cloud Tea")
        let rowID = "venue-73ee11fc-192f-5906-ac37-f4077a808d69"
        let results = app.buttons.matching(NSPredicate(format: "identifier IN %@", [rowID, "show-all"])).firstMatch
        XCTAssertTrue(results.waitForExistence(timeout: 10))
        let showAll = app.buttons["show-all"]
        if showAll.exists {
            XCTAssertTrue(showAll.isHittable, "A match outside the viewport must be reachable through Show All")
            showAll.tap()
        }
        let row = app.buttons[rowID]
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["detail-name"].label, "Cloud Tea")
        XCTAssertFalse(app.keyboards.firstMatch.exists, "Opening detail should dismiss the search keyboard")
        XCTAssertTrue(app.staticTexts["Ratings omitted"].exists)
        XCTAssertFalse(app.staticTexts["No rating"].exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'weighted score'")).firstMatch.exists)
        let detail = XCTAttachment(screenshot: app.screenshot())
        detail.name = "Real venue without ratings"; detail.lifetime = .keepAlways
        add(detail)
    }

    @MainActor func testAccessibleDiscoveryAndLargeTextDetail() throws {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing", "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
        app.launch()
        XCTAssertTrue(app.switches["include-franchises"].waitForExistence(timeout: 15))
        try app.performAccessibilityAudit(for: [.sufficientElementDescription])
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'venue-demo-'")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["back-to-list"].isHittable)
        try app.performAccessibilityAudit(for: [.sufficientElementDescription])
        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = "Large text detail"; shot.lifetime = .keepAlways; add(shot)
        app.buttons["back-to-list"].tap()
        XCTAssertTrue(row.waitForExistence(timeout: 5))
    }

    // The synthetic snapshot supplies every category and feature, three franchises,
    // and colocated markers. These assertions exercise visible behavior, not the model.
    @MainActor private func expectCount(_ app: XCUIApplication, _ count: Int,
                                       file: StaticString = #filePath, line: UInt = #line) {
        let header = app.staticTexts["results-count"]
        let expectation = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "exists == true AND label == %@", "\(count) \(count == 1 ? "spot" : "spots")"), object: header)
        XCTAssertEqual(XCTWaiter.wait(for: [expectation], timeout: 10), .completed,
                       "Expected \(count) \(count == 1 ? "spot" : "spots"); observed \(header.exists ? header.label : "missing results header")",
                       file: file, line: line)
    }

    @MainActor private func choose(_ app: XCUIApplication, menu: String, option: String,
                                  file: StaticString = #filePath, line: UInt = #line) {
        let control = app.buttons[menu]
        XCTAssertTrue(control.waitForExistence(timeout: 5), file: file, line: line)
        // SwiftUI's toolbar proxy can throw from isHittable or report an infinite
        // child frame on some SDKs. Its identified wrapper has the actual button
        // rectangle. Use that measured rectangle, bounded by the navigation bar
        // and app window, then require the requested menu item to appear.
        let frame = control.frame
        let window = app.frame
        let bar = app.navigationBars.firstMatch.frame
        guard frame.origin.x.isFinite, frame.origin.y.isFinite,
              frame.width.isFinite, frame.height.isFinite,
              frame.width > 0, frame.height > 0,
              window.contains(frame), bar.contains(frame) else {
            XCTFail("Filter menu must have a finite visible navigation-bar frame: \(frame)", file: file, line: line)
            return
        }
        app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(
            dx: frame.midX - window.minX, dy: frame.midY - window.minY)).tap()
        let item = app.descendants(matching: .any).matching(identifier: option).firstMatch
        XCTAssertTrue(item.waitForExistence(timeout: 5), file: file, line: line)
        item.tap()
    }

    @MainActor private func toggleFranchises(_ app: XCUIApplication,
                                           file: StaticString = #filePath, line: UInt = #line) {
        let control = app.switches["include-franchises"]
        XCTAssertTrue(control.waitForExistence(timeout: 5), file: file, line: line)
        let expected = control.value as? String == "1" ? "0" : "1"
        // SwiftUI exposes the full labeled row and a nested native UISwitch.
        // A percentage of the row width misses the thumb on wide iPad layouts.
        let nativeSwitch = control.switches.firstMatch
        let reachable = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            nativeSwitch.exists ? nativeSwitch.isHittable : control.isHittable
        }, object: control)
        XCTAssertEqual(XCTWaiter.wait(for: [reachable], timeout: 5), .completed,
                       "Franchise switch should be reachable: \(control.debugDescription)", file: file, line: line)
        if nativeSwitch.exists {
            XCTAssertTrue(nativeSwitch.isHittable, file: file, line: line)
            nativeSwitch.tap()
        } else {
            // Older SDKs can expose only the labeled wrapper. Its trailing thumb
            // remains the observed target; verify the state change below.
            control.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.5)).tap()
        }
        let changed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "value == %@", expected), object: control)
        XCTAssertEqual(XCTWaiter.wait(for: [changed], timeout: 5), .completed,
                       "Franchise switch should change to \(expected); observed \(String(describing: control.value))",
                       file: file, line: line)
    }

    @MainActor private func finishSearch(_ app: XCUIApplication) {
        // iPhone search enters a navigation search session; iPad may retain the toolbar.
        let cancel = app.buttons.matching(NSPredicate(format: "label == 'close' OR label == 'Cancel'")).firstMatch
        if cancel.exists && cancel.isHittable { cancel.tap() }
    }

    @MainActor private func replaceSearch(_ app: XCUIApplication, with text: String) {
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 5))
        search.tap()
        if let current = search.value as? String, !current.isEmpty, current != search.placeholderValue {
            // Tapping can put the caret in the middle of the existing query.
            // The native clear control replaces the whole query regardless of caret.
            let clear = search.buttons.matching(NSPredicate(format: "label == 'Clear text' OR label == 'Clear'")).firstMatch
            XCTAssertTrue(clear.waitForExistence(timeout: 5))
            clear.tap()
            search.tap()
        }
        if !text.isEmpty { app.typeText(text) }
        let entered = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            guard let value = search.value as? String else { return false }
            return value == text || (text.isEmpty && value == search.placeholderValue)
        }, object: search)
        XCTAssertEqual(XCTWaiter.wait(for: [entered], timeout: 5), .completed,
                       "The search field must contain the requested replacement query")
    }

    @MainActor func testEveryCategoryCanBeSelectedAndAllRestoresResults() {
        let app = launch()
        expectCount(app, 21)
        for (category, glyph, count) in [("Coffee", "☕", 3), ("Roasters", "🫘", 3),
                                        ("Bakery+Cafe", "🥐", 3), ("Tea/Boba", "🧋", 4),
                                        ("Dessert Cafe", "🍰", 4), ("Specialty", "✦", 4)] {
            choose(app, menu: "type-filter", option: "category-\(category)")
            expectCount(app, count)
            XCTAssertTrue(app.staticTexts["active-filters"].label.contains(glyph))
            choose(app, menu: "type-filter", option: "category-all")
            expectCount(app, 21)
            XCTAssertFalse(app.staticTexts["active-filters"].exists)
        }
    }

    @MainActor func testCategoryUnionAndFeatureIntersection() {
        let app = launch()
        choose(app, menu: "type-filter", option: "category-Coffee")
        choose(app, menu: "type-filter", option: "category-Tea/Boba")
        expectCount(app, 7) // Categories are OR: three coffee shops plus four tea shops.
        choose(app, menu: "feature-filter", option: "feature-work")
        expectCount(app, 5)
        choose(app, menu: "feature-filter", option: "feature-meeting")
        expectCount(app, 3) // Feature selections are AND: tea has no meeting rooms.
        choose(app, menu: "feature-filter", option: "feature-meeting")
        expectCount(app, 5)
        choose(app, menu: "feature-filter", option: "feature-work")
        expectCount(app, 7)
        app.buttons["reset"].tap()
        expectCount(app, 21)
        XCTAssertFalse(app.staticTexts["active-filters"].exists)
    }

    @MainActor func testEveryFeatureAndCombinedLateNightFilters() {
        let app = launch()
        for (feature, glyph, count) in [("work", "💻", 5), ("meeting", "🤝", 3),
                                       ("late", "🌙", 7), ("midnight", "🦉", 3)] {
            choose(app, menu: "feature-filter", option: "feature-\(feature)")
            expectCount(app, count)
            XCTAssertTrue(app.staticTexts["active-filters"].label.contains(glyph))
            choose(app, menu: "feature-filter", option: "feature-\(feature)")
            expectCount(app, 21)
        }
        choose(app, menu: "feature-filter", option: "feature-late")
        choose(app, menu: "feature-filter", option: "feature-midnight")
        expectCount(app, 3)
        choose(app, menu: "type-filter", option: "category-Roasters")
        XCTAssertTrue(app.staticTexts["No shops in this view"].waitForExistence(timeout: 5))
        app.buttons["reset"].tap()
        expectCount(app, 21)
    }

    @MainActor func testFranchiseToggleUpdatesResultsAndCategoryCounts() {
        let app = launch()
        expectCount(app, 21)
        toggleFranchises(app)
        expectCount(app, 24)
        choose(app, menu: "type-filter", option: "category-Coffee")
        expectCount(app, 4)
        toggleFranchises(app)
        expectCount(app, 3)
        app.buttons["reset"].tap()
        expectCount(app, 21)
        XCTAssertEqual(app.switches["include-franchises"].value as? String, "0")
    }

    @MainActor func testSearchIgnoresCaseAndWhitespaceAndCanBeCleared() {
        let app = launch()
        replaceSearch(app, with: "  DEMO   COFFEE  ")
        expectCount(app, 3)
        replaceSearch(app, with: "  ")
        expectCount(app, 21)
        replaceSearch(app, with: "no-such-venue")
        XCTAssertTrue(app.staticTexts["No shops in this view"].waitForExistence(timeout: 5))
        replaceSearch(app, with: "")
        expectCount(app, 21)
        finishSearch(app)
        XCTAssertTrue(app.buttons["reset"].isHittable)
    }

    @MainActor func testSearchCombinesWithCategoryAndResetClearsAllChoices() {
        let app = launch()
        choose(app, menu: "type-filter", option: "category-Coffee")
        toggleFranchises(app)
        replaceSearch(app, with: "Demo Coffee 7")
        expectCount(app, 1)
        let row = app.buttons["venue-demo-06"]
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        row.tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["detail-name"].label, "Demo Coffee 7")
        XCTAssertFalse(app.keyboards.firstMatch.exists)
        app.buttons["back-to-list"].tap()
        finishSearch(app)
        app.buttons["reset"].tap()
        expectCount(app, 21)
        XCTAssertFalse(app.staticTexts["active-filters"].exists)
        XCTAssertEqual(app.switches["include-franchises"].value as? String, "0")
    }

    @MainActor func testChangingFiltersDismissesExcludedDetail() {
        let app = launch()
        replaceSearch(app, with: "Demo Coffee 1")
        let row = app.buttons["venue-demo-00"]
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        row.tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        choose(app, menu: "type-filter", option: "category-Tea/Boba")
        let dismissed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"),
                                                  object: app.staticTexts["detail-name"])
        XCTAssertEqual(XCTWaiter.wait(for: [dismissed], timeout: 5), .completed)
        XCTAssertTrue(app.staticTexts["No shops in this view"].waitForExistence(timeout: 5))
        finishSearch(app)
        app.buttons["reset"].tap()
        expectCount(app, 21)
    }

    @MainActor func testClusterCanCloseAndReopenBeforeSelecting() throws {
        let app = launch()
        try tapVisibleMapButton(app, identifier: "cluster-pins")
        let close = app.buttons["close-cluster"]
        XCTAssertTrue(close.waitForExistence(timeout: 5))
        close.tap()
        XCTAssertFalse(close.exists)
        try tapVisibleMapButton(app, identifier: "cluster-pins")
        XCTAssertTrue(close.waitForExistence(timeout: 5))
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'venue-demo-'")).firstMatch
        row.tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        app.buttons["back-to-list"].tap()
        XCTAssertTrue(app.staticTexts["results-count"].waitForExistence(timeout: 5))
        app.buttons["reset"].tap()
        expectCount(app, 21)
    }

    @MainActor func testMapViewportFilteringAndShowAllRecoverMatches() {
        let app = launch()
        expectCount(app, 21)
        let map = app.descendants(matching: .any).matching(identifier: "venue-map").firstMatch
        XCTAssertTrue(map.waitForExistence(timeout: 10))
        map.pinch(withScale: 10, velocity: 2)
        map.swipeLeft()
        let showAll = app.buttons["show-all"]
        XCTAssertTrue(showAll.waitForExistence(timeout: 10), "Zoom/pan should limit the visible result set")
        XCTAssertEqual(showAll.label, "Show all 21 matches")
        showAll.tap()
        expectCount(app, 21)
        XCTAssertFalse(showAll.exists)
    }

    @MainActor func testRotationPreservesSelectionAndBackNavigation() {
        let app = launch()
        defer { XCUIDevice.shared.orientation = .portrait }
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'venue-demo-'")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        let name = app.staticTexts["detail-name"]
        XCTAssertTrue(name.waitForExistence(timeout: 5))
        let selectedName = name.label
        XCUIDevice.shared.orientation = .landscapeLeft
        XCTAssertTrue(name.waitForExistence(timeout: 5))
        XCTAssertEqual(name.label, selectedName)
        XCTAssertTrue(app.buttons["back-to-list"].isHittable)
        XCUIDevice.shared.orientation = .portrait
        XCTAssertTrue(app.buttons["back-to-list"].waitForExistence(timeout: 5))
        app.buttons["back-to-list"].tap()
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        app.buttons["reset"].tap()
        expectCount(app, 21)
    }

    @MainActor func testDiscoveryHasNoOfflineControlsAndRelaunchStartsClean() {
        let app = launch()
        for title in ["Data", "Import data", "Import offline snapshot…", "Update snapshot", "Data settings…"] {
            XCTAssertFalse(app.buttons[title].exists)
        }
        expectCount(app, 21)
        toggleFranchises(app)
        expectCount(app, 24)
        choose(app, menu: "feature-filter", option: "feature-midnight")
        expectCount(app, 4)
        app.terminate()
        app.launch()
        XCTAssertTrue(app.buttons["reset"].waitForExistence(timeout: 15))
        expectCount(app, 21)
        XCTAssertFalse(app.staticTexts["active-filters"].exists)
        XCTAssertEqual(app.switches["include-franchises"].value as? String, "0")
    }


    @MainActor func testStreetZoomShowsIndividualPinsAndRegionalZoomRestoresClusters() throws {
        let app = launch()
        replaceSearch(app, with: "Demo Coffee 1")
        expectCount(app, 3)
        app.buttons["venue-demo-00"].tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["detail-name"].label, "Demo Coffee 1")
        // Keep the selected camera focus while restoring the colocated Roasters
        // venue and the rest of the demo snapshot through the actual search UI.
        replaceSearch(app, with: "Demo")
        XCTAssertEqual(app.searchFields.firstMatch.value as? String, "Demo")
        let map = app.descendants(matching: .any).matching(identifier: "venue-map").firstMatch
        XCTAssertTrue(map.waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["detail-name"].label, "Demo Coffee 1")

        func isInsideMap(_ frame: CGRect) -> Bool {
            frame.origin.x.isFinite && frame.origin.y.isFinite && frame.width.isFinite && frame.height.isFinite
                && frame.width > 0 && frame.height > 0 && map.frame.contains(frame)
        }
        func visibleIndividual(_ identifier: String, name: String) -> Bool {
            app.buttons.matching(identifier: identifier).allElementsBoundByIndex.contains {
                $0.label == name && isInsideMap($0.frame)
            }
        }
        func expectIndividualPins(_ message: String, line: UInt = #line) {
            let street = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
                guard visibleIndividual("pin-demo-00", name: "Demo Coffee 1"),
                      visibleIndividual("pin-demo-01", name: "Demo Roasters 2") else { return false }
                // MapKit can retain hidden reused annotation nodes; only a finite,
                // on-map, actionable cluster would contradict the selected map UI.
                return !app.buttons.matching(identifier: "cluster-pins").allElementsBoundByIndex.contains {
                    isInsideMap($0.frame) && $0.isHittable
                }
            }, object: app)
            XCTAssertEqual(XCTWaiter.wait(for: [street], timeout: 10), .completed, message, line: line)
        }
        expectIndividualPins("Opening a listing must expose both colocated individual pins without requiring a zoom gesture")
        map.pinch(withScale: 10, velocity: 2)
        expectIndividualPins("Closest street zoom must retain the individual pins without an actionable cluster")
        XCTAssertTrue(app.buttons["back-to-list"].isHittable)
        app.buttons["back-to-list"].tap()
        expectCount(app, 21)
        try tapVisibleMapButton(app, identifier: "cluster-pins")
        XCTAssertTrue(app.staticTexts["Venues in selected cluster"].waitForExistence(timeout: 5))
    }

    @MainActor private func tapVisibleMapButton(_ app: XCUIApplication, identifier: String,
                                              file: StaticString = #filePath, line: UInt = #line) throws {
        let markers = app.buttons.matching(identifier: identifier)
        // MapKit can expose reused/covered annotation views alongside the visible
        // marker. Existence of the first AX node is not evidence it can be tapped.
        let reachable = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            markers.allElementsBoundByIndex.contains { $0.isHittable }
        }, object: app)
        XCTAssertEqual(XCTWaiter.wait(for: [reachable], timeout: 15), .completed,
                       "Expected a reachable map marker: \(identifier)", file: file, line: line)
        let marker = try XCTUnwrap(markers.allElementsBoundByIndex.first { $0.isHittable },
                                   "Map marker should remain reachable", file: file, line: line)
        marker.tap()
    }

    @MainActor private func reveal(_ element: XCUIElement, in container: XCUIElement,
                                  file: StaticString = #filePath, line: UInt = #line) {
        for _ in 0..<10 {
            if element.exists && element.isHittable { return }
            container.swipeUp()
        }
        XCTAssertTrue(element.exists && element.isHittable, "Expected reachable content after scrolling", file: file, line: line)
    }

    @MainActor func testIndividualMapPinOpensExactVenueAndReturnsToResults() {
        let app = launch()
        replaceSearch(app, with: "Demo Tea/Boba 4")
        expectCount(app, 1)
        XCTAssertEqual(app.searchFields.firstMatch.value as? String, "Demo Tea/Boba 4")
        let pin = app.buttons["pin-demo-03"]
        XCTAssertTrue(pin.waitForExistence(timeout: 10))
        XCTAssertTrue(pin.isHittable)
        let pinFrame = pin.frame
        pin.tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5),
                      "Expected pin selection to open details; marker frame was \(pinFrame)")
        XCTAssertEqual(app.staticTexts["detail-name"].label, "Demo Tea/Boba 4")
        app.buttons["back-to-list"].tap()
        XCTAssertTrue(app.buttons["venue-demo-03"].waitForExistence(timeout: 5))
        app.buttons["reset"].tap()
        expectCount(app, 21)
    }

    @MainActor func testDetailScrollToActionsAndBackRemainsReachable() {
        let app = launch()
        replaceSearch(app, with: "Demo Coffee 1")
        let row = app.buttons["venue-demo-00"]
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        row.tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        let scroll = app.scrollViews["detail-scroll"]
        XCTAssertTrue(scroll.waitForExistence(timeout: 5))
        reveal(app.staticTexts["Meeting room"], in: scroll)
        XCTAssertTrue(app.staticTexts["Demo meeting room information."].exists)
        reveal(app.buttons["Apple Maps"], in: scroll)
        XCTAssertTrue(app.buttons["Apple Maps"].isHittable)
        XCTAssertTrue(app.staticTexts.matching(identifier: "Source: Synthetic demo").firstMatch.exists)
        // Reverse scrolling must leave the original navigation available.
        for _ in 0..<10 {
            if app.buttons["back-to-list"].isHittable { break }
            scroll.swipeDown()
        }
        XCTAssertTrue(app.buttons["back-to-list"].isHittable)
        app.buttons["back-to-list"].tap()
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        finishSearch(app)
        app.buttons["reset"].tap()
        expectCount(app, 21)
    }


    @MainActor func testMissingVenueDataUsesHonestDetailFallbacks() {
        let app = launch(["--ui-edge-cases-testing"])
        expectCount(app, 2)
        let row = app.buttons["venue-qa-unknown"]
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        row.tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["detail-name"].label, "QA Unknown Cafe")
        let scroll = app.scrollViews["detail-scroll"]
        XCTAssertTrue(scroll.staticTexts["No public rating yet"].exists)
        XCTAssertFalse(scroll.staticTexts.matching(NSPredicate(format: "label CONTAINS 'weighted score'")).firstMatch.exists)
        reveal(app.staticTexts["Hours not verified"], in: scroll)
        reveal(app.staticTexts["Unknown · amenities not yet verified for this venue."], in: scroll)
        XCTAssertFalse(app.staticTexts["Known for"].exists)
        XCTAssertFalse(app.staticTexts["Coworking"].exists)
        XCTAssertFalse(app.staticTexts["Open until midnight"].exists)
        XCTAssertFalse(app.staticTexts["Open till 10pm+"].exists)
        reveal(app.buttons["Apple Maps"], in: scroll)
        for title in ["Google Maps", "Yelp", "Website"] {
            XCTAssertFalse(app.buttons[title].exists)
            XCTAssertFalse(app.links[title].exists)
        }
        for _ in 0..<10 {
            if app.buttons["back-to-list"].isHittable { break }
            scroll.swipeDown()
        }
        XCTAssertTrue(app.buttons["back-to-list"].isHittable)
        app.buttons["back-to-list"].tap()
        expectCount(app, 2)
    }

    @MainActor func testVerifiedExternalLinksAreReachableInDetail() {
        let app = launch(["--ui-edge-cases-testing"])
        expectCount(app, 2)
        app.buttons["venue-qa-linked"].tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["detail-name"].label, "QA Linked Cafe")
        let scroll = app.scrollViews["detail-scroll"]
        XCTAssertTrue(scroll.staticTexts.matching(NSPredicate(format: "label CONTAINS 'weighted score'")).firstMatch.exists)
        // Link's accessibility role differs across SwiftUI SDK versions.
        let controls = ["Google Maps", "Yelp", "Website"].map {
            app.buttons[$0].exists ? app.buttons[$0] : app.links[$0]
        }
        reveal(controls[2], in: scroll)
        var priorY = -CGFloat.infinity
        for control in controls {
            XCTAssertTrue(control.isHittable)
            XCTAssertGreaterThan(control.frame.minY, priorY)
            priorY = control.frame.minY
        }
        XCTAssertFalse(app.staticTexts["Meeting room"].exists)
        for _ in 0..<10 {
            if app.buttons["back-to-list"].isHittable { break }
            scroll.swipeDown()
        }
        XCTAssertTrue(app.buttons["back-to-list"].isHittable)
        app.buttons["back-to-list"].tap()
        expectCount(app, 2)
    }


    @MainActor private func linkedDetailForHandoff() -> XCUIApplication {
        let app = launch(["--ui-edge-cases-testing"])
        expectCount(app, 2)
        replaceSearch(app, with: "QA Linked Cafe")
        expectCount(app, 1)
        app.buttons["venue-qa-linked"].tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["detail-name"].label, "QA Linked Cafe")
        return app
    }

    @MainActor private func returnFromExternalApp(_ app: XCUIApplication) {
        app.activate()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["detail-name"].label, "QA Linked Cafe")
        XCTAssertEqual(app.searchFields.firstMatch.value as? String, "QA Linked Cafe")
        let scroll = app.scrollViews["detail-scroll"]
        for _ in 0..<10 {
            if app.buttons["back-to-list"].isHittable { break }
            scroll.swipeDown()
        }
        XCTAssertTrue(app.buttons["back-to-list"].isHittable)
        app.buttons["back-to-list"].tap()
        expectCount(app, 1)
        XCTAssertTrue(app.buttons["venue-qa-linked"].exists)
    }

    @MainActor private func safariAddressContainers(_ safari: XCUIApplication) -> XCUIElementQuery {
        safari.descendants(matching: .any).matching(NSPredicate(
            format: "identifier IN %@ OR identifier BEGINSWITH 'SearchFieldItemView?'",
            ["TabBarItemTitle", "TabBarItemTitleContainer"]))
    }

    @MainActor private func safariAddress(_ safari: XCUIApplication, identifies host: String) -> Bool {
        func identifiesHost(_ element: XCUIElement) -> Bool {
            // Safari inserts directional display marks around domains. Compare the
            // parsed host rather than requiring those invisible formatting marks.
            let texts = [element.value as? String, element.label].compactMap { $0 }
            return texts.contains { text in
                let address = String(String.UnicodeScalarView(text.unicodeScalars.filter {
                    $0.properties.generalCategory != .format
                })).trimmingCharacters(in: .whitespacesAndNewlines)
                let url = address.contains("://") ? address : "https://" + address
                return URLComponents(string: url)?.host?.lowercased() == host.lowercased()
            }
        }
        // Only observed browser address containers participate; webpage labels
        // cannot satisfy this assertion. Use one query to avoid serial full-tree
        // snapshots while Safari is still creating its accessibility hierarchy.
        for item in safariAddressContainers(safari).allElementsBoundByIndex {
            if identifiesHost(item) || item.staticTexts.allElementsBoundByIndex.contains(where: identifiesHost) { return true }
        }
        return false
    }

    @MainActor func testWebsiteHandoffAndReturnPreservesDetailAndSearch() {
        let app = linkedDetailForHandoff()
        let website = app.buttons["Website"].exists ? app.buttons["Website"] : app.links["Website"]
        reveal(website, in: app.scrollViews["detail-scroll"])
        website.tap()
        let safari = XCUIApplication(bundleIdentifier: "com.apple.mobilesafari")
        XCTAssertTrue(safari.wait(for: .runningForeground, timeout: 10), "Website should open the simulator's Safari browser")
        // Foreground process state precedes Safari's address UI on a fresh launch.
        XCTAssertTrue(safariAddressContainers(safari).firstMatch.waitForExistence(timeout: 10),
                      "Safari should expose its address control after launch")
        let destination = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            self.safariAddress(safari, identifies: "example.com")
        }, object: safari)
        XCTAssertEqual(XCTWaiter.wait(for: [destination], timeout: 5), .completed,
                       "Safari's address should identify the fixture website: \(safari.debugDescription)")
        // This checks the handoff URL, not network availability or external webpage content.
        returnFromExternalApp(app)
    }

    @MainActor func testAppleMapsHandoffAndReturnPreservesDetailAndSearch() {
        let app = linkedDetailForHandoff()
        let mapsButton = app.buttons["Apple Maps"]
        reveal(mapsButton, in: app.scrollViews["detail-scroll"])
        mapsButton.tap()
        let maps = XCUIApplication(bundleIdentifier: "com.apple.Maps")
        XCTAssertTrue(maps.wait(for: .runningForeground, timeout: 10), "Apple Maps action should launch Maps")
        // Never accept external onboarding, permissions, or terms. Foreground launch
        // verifies the handoff; real destination presentation is separate platform QA.
        returnFromExternalApp(app)
    }

}
