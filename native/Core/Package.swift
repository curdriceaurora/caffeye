// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "CaffeyeCore",
    platforms: [.iOS(.v18), .macOS(.v15)],
    products: [.library(name: "CaffeyeCore", targets: ["CaffeyeCore"])],
    targets: [
        .target(name: "CaffeyeCore"),
        .testTarget(name: "CaffeyeCoreTests", dependencies: ["CaffeyeCore"])
    ]
)
