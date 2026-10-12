import XCTest

final class DiscoveryUITests: XCTestCase {
    @MainActor private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
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
    @MainActor func testClusterShowsSelectableMembers() {
        let app = launch()
        let cluster = app.descendants(matching: .any).matching(identifier: "cluster-pins").firstMatch
        XCTAssertTrue(cluster.waitForExistence(timeout: 15))
        cluster.tap()
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
        XCTAssertFalse(app.staticTexts["No rating"].exists)
        let search = app.searchFields.firstMatch
        search.tap(); search.typeText("Cloud Tea")
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'venue-'")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        XCTAssertTrue(app.staticTexts["detail-name"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Ratings omitted from this snapshot"].exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'weighted score'")).firstMatch.exists)
        let detail = XCTAttachment(screenshot: app.screenshot())
        detail.name = "Real venue without ratings"; detail.lifetime = .keepAlways
        add(detail)
    }

}
