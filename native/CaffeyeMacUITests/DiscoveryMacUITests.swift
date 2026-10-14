import XCTest

/// Real macOS interaction contracts. Synthetic venues keep ranking and filter outcomes deterministic.
final class DiscoveryMacUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }

    @MainActor func testNativeListArrowNavigationAndMenuReset() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing", "--ui-edge-cases-testing"]
        app.launch()
        XCTAssertTrue(app.buttons["reset"].firstMatch.waitForExistence(timeout: 20))
        desktopWindow(app)
        widen(app.windows.firstMatch, in: app)
        let unknown = row("qa-unknown", in: app)
        XCTAssertTrue(unknown.waitForExistence(timeout: 5))
        unknown.click()
        wait(app.staticTexts["detail-name"], label: "QA Unknown Cafe")
        app.typeKey(XCUIKeyboardKey.downArrow.rawValue, modifierFlags: [])
        wait(app.staticTexts["detail-name"], label: "QA Linked Cafe")
        app.typeKey(XCUIKeyboardKey.upArrow.rawValue, modifierFlags: [])
        wait(app.staticTexts["detail-name"], label: "QA Unknown Cafe")
        app.menuBars.menuBarItems["View"].click()
        let reset = app.menuItems["Reset discovery"]
        XCTAssertTrue(reset.waitForExistence(timeout: 5))
        reset.click()
        gone(app.staticTexts["detail-name"])
        wait(app.staticTexts["results-count"], label: "2 spots")
        XCTAssertTrue(unknown.isHittable)
    }

    @MainActor private func launch(bundled: Bool = false, edgeCases: Bool = false) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"] + (bundled ? ["--bundled-venues-testing"] : []) + (edgeCases ? ["--ui-edge-cases-testing"] : [])
        app.launch()
        XCTAssertTrue(app.buttons["reset"].firstMatch.waitForExistence(timeout: 20))
        XCTAssertTrue(app.staticTexts["results-count"].waitForExistence(timeout: 10))
        return app
    }

    @MainActor private func desktopWindow(_ app: XCUIApplication) {
        app.menuBars.menuBarItems["View"].click()
        let exitFullScreen = app.menuItems["Exit Full Screen"]
        if exitFullScreen.exists && exitFullScreen.isEnabled { exitFullScreen.click() }
        else { app.typeKey(XCUIKeyboardKey.escape.rawValue, modifierFlags: []) }
        app.menuBars.menuBarItems["Window"].click()
        let tile = app.menuItems["Full Screen Tile"]
        if tile.exists {
            tile.hover()
            let desktop = app.menuItems["Move Window to Desktop"]
            if desktop.exists && desktop.isEnabled { desktop.click() }
            else { app.typeKey(XCUIKeyboardKey.escape.rawValue, modifierFlags: []) }
        } else {
            app.typeKey(XCUIKeyboardKey.escape.rawValue, modifierFlags: [])
        }
    }

    @MainActor private func widen(_ window: XCUIElement, in app: XCUIApplication) {
        app.menuBars.menuBarItems["Window"].click()
        let fill = app.menuItems["Fill"]
        XCTAssertTrue(fill.exists && fill.isEnabled)
        fill.click()
        waitForWindowWidth(window, wide: true)
    }

    @MainActor private func narrow(_ window: XCUIElement, in app: XCUIApplication) {
        app.menuBars.menuBarItems["Window"].click()
        let resize = app.menuItems["Move & Resize"]
        XCTAssertTrue(resize.exists)
        resize.hover()
        let left = app.menuItems["Left"].firstMatch
        XCTAssertTrue(left.waitForExistence(timeout: 5), app.debugDescription)
        left.click()
        waitForWindowWidth(window, wide: false)
    }

    @MainActor private func waitForWindowWidth(_ window: XCUIElement, wide: Bool) {
        let resized = NSPredicate { element, _ in
            guard let window = element as? XCUIElement else { return false }
            return wide ? window.frame.width >= 760 : window.frame.width < 760
        }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: resized, object: window)], timeout: 10), .completed,
                       "Wait for native window resize; width=\(window.frame.width), wide=\(wide)")
    }

    @MainActor private func wait(_ element: XCUIElement, label: String, file: StaticString = #filePath, line: UInt = #line) {
        let matches = NSPredicate(format: "exists == true AND label == %@", label)
        let result = XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: matches, object: element)], timeout: 10)
        XCTAssertEqual(result, .completed, "Expected \(label); observed \(element.exists ? element.label : "missing")", file: file, line: line)
    }

    @MainActor private func gone(_ element: XCUIElement, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: element)], timeout: 10), .completed, file: file, line: line)
    }

    @MainActor private func search(_ text: String, in app: XCUIApplication) {
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 5))
        search.click()
        search.typeKey("a", modifierFlags: .command)
        search.typeText(text)
    }

    @MainActor private func row(_ id: String, in app: XCUIApplication) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: "venue-\(id)").firstMatch
    }

    @MainActor private func externalAction(_ label: String, in detail: XCUIElement) -> XCUIElement {
        // SwiftUI Link exposes a link or button depending on the macOS SDK.
        detail.descendants(matching: .any).matching(NSPredicate(
            format: "label == %@ AND (elementType == %d OR elementType == %d)",
            label, XCUIElement.ElementType.link.rawValue, XCUIElement.ElementType.button.rawValue)).firstMatch
    }

    @MainActor private func filter(_ id: String, menu: String, in app: XCUIApplication) {
        app.descendants(matching: .any).matching(identifier: menu).firstMatch.click()
        let item = app.descendants(matching: .any).matching(identifier: id).firstMatch
        XCTAssertTrue(item.waitForExistence(timeout: 5), "Missing menu item \(id)")
        item.click()
    }

    @MainActor func testKeyboardSearchSelectionBackAndReset() {
        let app = launch()
        wait(app.staticTexts["results-count"], label: "21 spots")
        search("Demo Coffee 1", in: app)
        let coffee = row("demo-00", in: app)
        XCTAssertTrue(coffee.waitForExistence(timeout: 5))
        coffee.click()
        wait(app.staticTexts["detail-name"], label: "Demo Coffee 1")
        app.typeKey("[", modifierFlags: .command)
        gone(app.staticTexts["detail-name"])
        XCTAssertTrue(coffee.isHittable)
        app.typeKey("r", modifierFlags: [.command, .shift])
        wait(app.staticTexts["results-count"], label: "21 spots")
        XCTAssertEqual(app.searchFields.firstMatch.value as? String, "")
    }

    @MainActor func testEscapeAndBackButtonDismissDetailsWithoutLosingSearch() {
        let app = launch()
        search("Demo Tea/Boba 4", in: app)
        let tea = row("demo-03", in: app)
        XCTAssertTrue(tea.waitForExistence(timeout: 5))
        tea.click()
        wait(app.staticTexts["detail-name"], label: "Demo Tea/Boba 4")
        app.typeKey(XCUIKeyboardKey.escape.rawValue, modifierFlags: [])
        gone(app.staticTexts["detail-name"])
        XCTAssertEqual(app.searchFields.firstMatch.value as? String, "Demo Tea/Boba 4")
        tea.click()
        XCTAssertTrue(app.buttons["back-to-list"].firstMatch.waitForExistence(timeout: 5))
        app.buttons["back-to-list"].firstMatch.click()
        gone(app.staticTexts["detail-name"])
        XCTAssertTrue(tea.isHittable)
    }

    @MainActor func testEveryCategoryAndMultipleCategoryUnion() {
        let app = launch()
        let cases = [("Coffee", 3), ("Roasters", 3), ("Bakery+Cafe", 3), ("Tea/Boba", 4), ("Dessert Cafe", 4), ("Specialty", 4)]
        for (category, count) in cases {
            filter("category-\(category)", menu: "type-filter", in: app)
            wait(app.staticTexts["results-count"], label: "\(count) spots")
            filter("category-\(category)", menu: "type-filter", in: app)
            wait(app.staticTexts["results-count"], label: "21 spots")
        }
        filter("category-Coffee", menu: "type-filter", in: app)
        filter("category-Tea/Boba", menu: "type-filter", in: app)
        wait(app.staticTexts["results-count"], label: "7 spots")
        app.buttons["reset"].firstMatch.click()
        wait(app.staticTexts["results-count"], label: "21 spots")
    }

    @MainActor func testEveryFeatureAndCombinedCategoryIntersection() {
        let app = launch()
        for (feature, count) in [("work", 5), ("meeting", 3), ("late", 7), ("midnight", 3)] {
            filter("feature-\(feature)", menu: "feature-filter", in: app)
            wait(app.staticTexts["results-count"], label: "\(count) spots")
            app.buttons["reset"].firstMatch.click()
            wait(app.staticTexts["results-count"], label: "21 spots")
        }
        filter("category-Coffee", menu: "type-filter", in: app)
        filter("feature-midnight", menu: "feature-filter", in: app)
        wait(app.staticTexts["results-count"], label: "3 spots")
        search("Tea/Boba", in: app)
        XCTAssertTrue(app.staticTexts["No shops in this view"].waitForExistence(timeout: 5))
        app.typeKey("r", modifierFlags: [.command, .shift])
        wait(app.staticTexts["results-count"], label: "21 spots")
    }

    @MainActor func testFranchiseFilterHidesSelectedFranchiseAndRecovers() {
        let app = launch()
        let toggle = app.checkBoxes["include-franchises"]
        XCTAssertTrue(toggle.waitForExistence(timeout: 5))
        search("Demo Coffee 7", in: app)
        XCTAssertTrue(app.staticTexts["No shops in this view"].waitForExistence(timeout: 5))
        toggle.click()
        let franchise = row("demo-06", in: app)
        XCTAssertTrue(franchise.waitForExistence(timeout: 5))
        franchise.click()
        wait(app.staticTexts["detail-name"], label: "Demo Coffee 7")
        XCTAssertTrue(app.staticTexts["Franchise"].exists)
        toggle.click()
        gone(app.staticTexts["detail-name"])
        XCTAssertTrue(app.staticTexts["No shops in this view"].waitForExistence(timeout: 5))
        app.buttons["reset"].firstMatch.click()
        wait(app.staticTexts["results-count"], label: "21 spots")
    }

    @MainActor func testEmptySearchResetThenDetailHasUsefulInformation() {
        let app = launch()
        search("no-such-venue", in: app)
        wait(app.staticTexts["results-count"], label: "0 spots")
        XCTAssertTrue(app.staticTexts["No shops in this view"].exists)
        app.buttons["reset"].firstMatch.click()
        search("Demo Coffee 1", in: app)
        let coffee = row("demo-00", in: app)
        XCTAssertTrue(coffee.waitForExistence(timeout: 5))
        coffee.click()
        wait(app.staticTexts["detail-name"], label: "Demo Coffee 1")
        XCTAssertTrue(app.staticTexts["◆ 4.3 weighted score"].exists)
        XCTAssertTrue(app.staticTexts["Known for"].exists)
        XCTAssertTrue(app.staticTexts["Location & hours"].exists)
        XCTAssertTrue(app.staticTexts["Demo: 8am–10pm"].exists)
        app.buttons["back-to-list"].firstMatch.click()
        XCTAssertTrue(coffee.isHittable)
    }

    @MainActor func testClusterCloseAndMemberSelection() {
        let app = launch()
        let cluster = app.descendants(matching: .any).matching(identifier: "cluster-pins").firstMatch
        XCTAssertTrue(cluster.waitForExistence(timeout: 15))
        cluster.click()
        XCTAssertTrue(app.staticTexts["Venues in selected cluster"].waitForExistence(timeout: 5))
        let close = app.buttons["close-cluster"]
        XCTAssertTrue(close.waitForExistence(timeout: 5))
        for _ in 0..<3 where !close.isHittable { app.scrollViews.firstMatch.scroll(byDeltaX: 0, deltaY: -500) }
        XCTAssertTrue(close.isHittable)
        close.click()
        gone(app.staticTexts["Venues in selected cluster"])
        cluster.click()
        XCTAssertTrue(app.staticTexts["Venues in selected cluster"].waitForExistence(timeout: 5))
        let member = row("demo-00", in: app)
        XCTAssertTrue(member.waitForExistence(timeout: 5))
        member.click()
        wait(app.staticTexts["detail-name"], label: "Demo Coffee 1")
        gone(app.staticTexts["Venues in selected cluster"])
        app.buttons["back-to-list"].firstMatch.click()
        gone(app.staticTexts["detail-name"])
        XCTAssertTrue(member.waitForExistence(timeout: 5))
    }

    @MainActor func testMapPinOpensSameVenueDetailAsList() {
        let app = launch()
        search("Demo Bakery & Cafe 3", in: app)
        wait(app.staticTexts["results-count"], label: "1 spot")
        let pin = app.descendants(matching: .any).matching(identifier: "pin-demo-02").firstMatch
        XCTAssertTrue(pin.waitForExistence(timeout: 15))
        pin.click()
        wait(app.staticTexts["detail-name"], label: "Demo Bakery & Cafe 3")
        app.buttons["back-to-list"].firstMatch.click()
        gone(app.staticTexts["detail-name"])
        let bakery = row("demo-02", in: app)
        XCTAssertTrue(bakery.isHittable)
        bakery.click()
        wait(app.staticTexts["detail-name"], label: "Demo Bakery & Cafe 3")
    }

    @MainActor func testUnknownVenueFieldsAndValidExternalActions() {
        let app = launch(edgeCases: true)
        search("QA Unknown Cafe", in: app)
        let unknown = row("qa-unknown", in: app)
        XCTAssertTrue(unknown.waitForExistence(timeout: 5))
        unknown.click()
        wait(app.staticTexts["detail-name"], label: "QA Unknown Cafe")
        XCTAssertTrue(app.staticTexts["No public rating yet"].exists)
        XCTAssertTrue(app.staticTexts["Hours not verified"].exists)
        XCTAssertTrue(app.staticTexts["Unknown · amenities not yet verified for this venue."].exists)
        XCTAssertFalse(app.staticTexts["Known for"].exists)
        XCTAssertFalse(app.staticTexts["Coworking"].exists)
        XCTAssertFalse(app.links["Website"].exists)
        app.buttons["back-to-list"].firstMatch.click()
        search("QA Linked Cafe", in: app)
        let linked = row("qa-linked", in: app)
        XCTAssertTrue(linked.waitForExistence(timeout: 5))
        linked.click()
        wait(app.staticTexts["detail-name"], label: "QA Linked Cafe")
        let detail = app.scrollViews["detail-scroll"]
        XCTAssertTrue(detail.waitForExistence(timeout: 5))
        let website = externalAction("Website", in: detail)
        XCTAssertTrue(website.waitForExistence(timeout: 5))
        for _ in 0..<6 where !website.isHittable { detail.scroll(byDeltaX: 0, deltaY: -300) }
        XCTAssertTrue(website.isHittable)
        XCTAssertTrue(externalAction("Google Maps", in: detail).isHittable)
        XCTAssertTrue(externalAction("Yelp", in: detail).isHittable)
        XCTAssertTrue(app.buttons["Apple Maps"].isHittable)
        detail.scroll(byDeltaX: 0, deltaY: 2000)
        XCTAssertTrue(app.buttons["back-to-list"].firstMatch.isHittable)
        app.buttons["back-to-list"].firstMatch.click()
        gone(app.staticTexts["detail-name"])
        XCTAssertTrue(linked.isHittable)
    }

    @MainActor func testNewWindowKeepsDiscoveryAndCommandsIndependent() {
        let app = launch()
        search("Demo Coffee 1", in: app)
        let coffee = row("demo-00", in: app)
        XCTAssertTrue(coffee.waitForExistence(timeout: 5))
        coffee.click()
        wait(app.staticTexts["detail-name"], label: "Demo Coffee 1")
        app.typeKey("n", modifierFlags: .command)
        // macOS may create a window or a tab according to the user's preference.
        // Verify the active discovery scene rather than count auxiliary OS windows.
        let fresh = app.windows.firstMatch
        wait(fresh.staticTexts["results-count"], label: "21 spots")
        XCTAssertFalse(fresh.staticTexts["detail-name"].exists)
        let freshSearch = fresh.searchFields.firstMatch
        freshSearch.click()
        freshSearch.typeText("no-such-venue")
        XCTAssertTrue(fresh.staticTexts["No shops in this view"].waitForExistence(timeout: 5))
        app.typeKey("r", modifierFlags: [.command, .shift])
        wait(fresh.staticTexts["results-count"], label: "21 spots")
        // The covered window can be absent from the live accessibility snapshot.
        // Bring it back to the foreground before asserting its retained selection.
        app.typeKey("w", modifierFlags: .command)
        wait(app.staticTexts["detail-name"], label: "Demo Coffee 1")
        app.buttons["back-to-list"].firstMatch.click()
        gone(app.staticTexts["detail-name"])
        XCTAssertEqual(app.searchFields.firstMatch.value as? String, "Demo Coffee 1")
    }

    @MainActor func testBundledRatingOmissionAndNoDataManagementControls() {
        let app = launch(bundled: true)
        XCTAssertTrue(app.staticTexts["Alphabetical · ratings omitted"].waitForExistence(timeout: 15))
        search("Cloud Tea", in: app)
        let venue = app.descendants(matching: .any).matching(NSPredicate(format: "identifier BEGINSWITH 'venue-' AND identifier != 'venue-map'")).firstMatch
        XCTAssertTrue(venue.waitForExistence(timeout: 10))
        venue.click()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Ratings omitted"].exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'weighted score'")).firstMatch.exists)
        XCTAssertFalse(app.buttons["Import snapshot"].exists)
        XCTAssertFalse(app.buttons["Update venues"].exists)
        XCTAssertFalse(app.buttons["Data settings"].exists)
    }

    @MainActor func testMapPanFiltersSelectedSidebarAndRestoresBrowsingContext() {
        let app = launch()
        let map = app.descendants(matching: .any).matching(identifier: "venue-map").firstMatch
        XCTAssertTrue(map.waitForExistence(timeout: 10))
        search("Demo Tea/Boba 4", in: app)
        let coffee = row("demo-03", in: app)
        XCTAssertTrue(coffee.waitForExistence(timeout: 5))
        coffee.click()
        wait(app.staticTexts["detail-name"], label: "Demo Tea/Boba 4")
        let start = map.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.8))
        start.click(forDuration: 0.1, thenDragTo: map.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.1)))
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = "Selected map after pan"; screenshot.lifetime = .keepAlways; add(screenshot)
        let tree = XCTAttachment(string: app.debugDescription)
        tree.name = "Selected map after pan tree"; tree.lifetime = .keepAlways; add(tree)
        wait(app.staticTexts["results-count"], label: "0 in view")
        XCTAssertTrue(app.buttons["show-all"].isHittable)
        wait(app.staticTexts["detail-name"], label: "Demo Tea/Boba 4")
        app.buttons["back-to-list"].firstMatch.click()
        gone(app.staticTexts["detail-name"])
        wait(app.staticTexts["results-count"], label: "1 spot")
        XCTAssertTrue(coffee.isHittable)
    }

    @MainActor func testNarrowWindowKeepsSelectedDetailAndBackUsable() {
        let app = launch()
        desktopWindow(app)
        let window = app.windows.firstMatch
        widen(window, in: app)
        search("Demo Coffee 1", in: app)
        let coffee = row("demo-00", in: app)
        XCTAssertTrue(coffee.waitForExistence(timeout: 5))
        coffee.click()
        wait(app.staticTexts["detail-name"], label: "Demo Coffee 1")
        narrow(window, in: app)
        XCTAssertTrue(app.buttons["back-to-list"].firstMatch.isHittable)
        XCTAssertTrue(coffee.isHittable, "The native Mac sidebar remains usable in a narrow window")
        wait(app.staticTexts["detail-name"], label: "Demo Coffee 1")
        app.buttons["back-to-list"].firstMatch.click()
        gone(app.staticTexts["detail-name"])
        XCTAssertTrue(coffee.waitForExistence(timeout: 5))
        XCTAssertTrue(coffee.isHittable)
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = "macOS compact discovery"; attachment.lifetime = .keepAlways; add(attachment)
        widen(window, in: app)
        XCTAssertTrue(coffee.isHittable)
        search("no-such-venue", in: app)
        narrow(window, in: app)
        XCTAssertTrue(app.staticTexts["No shops in this view"].exists)
        widen(window, in: app)
        app.buttons["reset"].firstMatch.click()
        wait(app.staticTexts["results-count"], label: "21 spots")
        let cluster = app.descendants(matching: .any).matching(identifier: "cluster-pins").firstMatch
        XCTAssertTrue(cluster.waitForExistence(timeout: 15))
        cluster.click()
        XCTAssertTrue(app.buttons["close-cluster"].waitForExistence(timeout: 5))
        narrow(window, in: app)
        let closeCluster = app.buttons["close-cluster"].firstMatch
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: NSPredicate(format: "isHittable == true"), object: closeCluster)], timeout: 5), .completed,
                       "Cluster close must remain reachable after resizing: \(app.debugDescription)")
        closeCluster.click()
        gone(app.staticTexts["Venues in selected cluster"])
        widen(window, in: app)
        wait(app.staticTexts["results-count"], label: "21 spots")
    }
}
