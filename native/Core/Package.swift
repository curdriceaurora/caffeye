// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "CaffeyeCore",
    platforms: [.iOS(.v18), .macOS(.v15)],
    products: [
        .library(name: "CaffeyeCore", targets: ["CaffeyeCore"]),
        .executable(name: "CaffeyeTools", targets: ["CaffeyeTools"])
    ],
    targets: [
        .target(name: "CaffeyeCore"),
        .executableTarget(name: "CaffeyeTools", dependencies: ["CaffeyeCore"]),
        .testTarget(name: "CaffeyeCoreTests", dependencies: ["CaffeyeCore"])
    ]
)
