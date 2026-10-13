#!/usr/bin/env python3
"""Capture local macOS memory evidence; launches and terminates only its own app."""
import argparse
import ctypes
import datetime
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path


def run_to_file(command, destination, timeout=60):
    with destination.open("w") as output:
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
    return result.returncode


def executable_path(pid, library=None):
    library = library or ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    buffer = ctypes.create_string_buffer(4096)
    if library.proc_pidpath(pid, buffer, len(buffer)) <= 0:
        raise RuntimeError(f"proc_pidpath failed for owned PID {pid}")
    return buffer.value.decode()


def wait_for_snapshot(app, marker, timeout=30, clock=time.monotonic, pause=time.sleep):
    deadline = clock() + timeout
    while True:
        if app.poll() is not None:
            raise RuntimeError("app exited before its offline snapshot loaded")
        if marker.is_file():
            line = next((line for line in marker.read_text().splitlines() if line.startswith("CAFFEYE_SNAPSHOT_READY ")), None)
            readiness = json.loads(line.removeprefix("CAFFEYE_SNAPSHOT_READY ")) if line else None
            if readiness is not None and (readiness.get("phase") != "offlineSnapshotLoaded" or not isinstance(readiness.get("venues"), int) or readiness["venues"] <= 0):
                raise RuntimeError("invalid snapshot readiness marker")
            if readiness is not None:
                return readiness
        if clock() >= deadline:
            raise RuntimeError("timed out waiting for offline snapshot readiness; basemap readiness is not measured")
        pause(0.1)


def summarize(heap_file, leaks_file, vm_file):
    classes = []
    for line in heap_file.read_text().splitlines():
        match = re.match(r"\s*(\d+)\s+(\d+)\s+[\d.]+\s+(.+?)\s+(?:ObjC|Swift|C\+\+|C)\s+(\S+)\s*$", line)
        if match:
            classes.append({"count": int(match[1]), "bytes": int(match[2]), "type": match[3], "binary": match[4]})
    leaks = re.search(r": (\d+) leaks for (\d+) total leaked bytes", leaks_file.read_text())
    footprint = re.search(r"Physical footprint:\s+([^\n]+)", vm_file.read_text())
    return {"physicalFootprint": footprint[1].strip() if footprint else None,
            "leaks": {"count": int(leaks[1]), "bytes": int(leaks[2])} if leaks else None,
            "largestIdentifiedTypes": sorted(classes, key=lambda value: value["bytes"], reverse=True)[:15],
            "appObjects": [value for value in classes if value["type"] in
                           ["AppModel", "DiscoveryState", "VenueMap.Coordinator", "VenueAnnotation", "MKMarkerAnnotationView"]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--duration", type=int, default=60, help="Seconds to exercise discovery between snapshots")
    parser.add_argument("--stack-logging", action="store_true", help="Adds allocation stacks, with substantial memory/timing overhead")
    args = parser.parse_args()
    if not 1 <= args.duration <= 600:
        parser.error("duration must be between 1 and 600 seconds")
    executable = (args.app / "Contents/MacOS/Caffeye").resolve()
    if not executable.is_file():
        parser.error("app must contain Contents/MacOS/Caffeye")
    output = args.output.resolve()
    if output.exists():
        parser.error("output must be a new directory to preserve earlier evidence")
    root = Path(__file__).resolve().parents[2]
    if output.is_relative_to(root / "public"):
        parser.error("raw profiles must remain outside the published public directory")
    output.mkdir(parents=True)
    environment = dict(os.environ)
    marker = output / "app.log"
    environment["CAFFEYE_PROFILE_READY"] = "1"
    if args.stack_logging:
        environment["MallocStackLogging"] = "1"
    else:
        environment.pop("MallocStackLogging", None)
    report = {"executableSHA256": hashlib.sha256(executable.read_bytes()).hexdigest(),
              "capturedAtUTC": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "datasetSHA256": hashlib.sha256((args.app / "Contents/Resources/venues.json").read_bytes()).hexdigest(),
              "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
              "stackLogging": args.stack_logging, "durationSeconds": args.duration,
              "scope": "macOS local discovery; RSS, VM summary and heap/leak snapshots. No Instruments recording, GPU/FPS, physical device, or release-readiness claim.",
              "samples": [], "checkpoints": {}}
    with (output / "app.log").open("w") as log:
        app = subprocess.Popen([str(executable), "--ui-testing", "--bundled-venues-testing"],
                               stdout=log, stderr=log, env=environment)
        try:
            if executable_path(app.pid) != str(executable):
                raise RuntimeError("launched executable did not match requested app")
            report["executableVerified"] = True
            print(f"Verified owned PID {app.pid}; waiting for offline snapshot", flush=True)
            report["snapshotReadiness"] = wait_for_snapshot(app, marker)
            for phase in ["initial", "final"]:
                if phase == "final":
                    print(f"Exercise the launched app for {args.duration} seconds, then leave it settled", flush=True)
                    start = time.monotonic()
                    while time.monotonic() - start < args.duration:
                        if app.poll() is not None:
                            raise RuntimeError("app exited before capture finished")
                        rss = subprocess.check_output(["ps", "-p", str(app.pid), "-o", "rss="], text=True).strip()
                        report["samples"].append({"seconds": round(time.monotonic() - start, 2), "rssBytes": int(rss) * 1024})
                        time.sleep(1)
                graph = output / (phase + ".memgraph")
                vm = output / (phase + "-vmmap.txt")
                leak_file = output / (phase + "-leaks.txt")
                heap_file = output / (phase + "-heap.txt")
                codes = {"vmmap": run_to_file(["vmmap", "-summary", str(app.pid)], vm),
                         "graph": run_to_file(["leaks", "--noContent", "--outputGraph=" + str(graph), str(app.pid)], output / (phase + "-graph.log"))}
                if not graph.is_file():
                    raise RuntimeError("memory graph capture failed; inspect local graph log")
                codes["leaks"] = run_to_file(["leaks", "--list", str(graph)], leak_file)
                codes["heap"] = run_to_file(["heap", "--sortBySize", str(graph)], heap_file)
                report["checkpoints"][phase] = {**summarize(heap_file, leak_file, vm), "toolExitCodes": codes}
                (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        finally:
            app.terminate()
            try:
                app.wait(timeout=5)
            except subprocess.TimeoutExpired:
                app.kill()
                app.wait()
    print(output / "report.json")


if __name__ == "__main__":
    main()
