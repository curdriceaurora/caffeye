import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from profile_memory import executable_path, summarize, wait_for_snapshot


class ProfileMemoryTests(unittest.TestCase):
    def test_proc_path_success_and_failure_are_distinct(self):
        def path(pid, buffer, count):
            buffer.value = b"/test/Caffeye"
            return len(buffer.value)
        self.assertEqual(executable_path(123, SimpleNamespace(proc_pidpath=path)), "/test/Caffeye")
        with self.assertRaisesRegex(RuntimeError, "proc_pidpath failed"):
            executable_path(123, SimpleNamespace(proc_pidpath=lambda *args: 0))

    def test_readiness_waits_for_valid_marker_and_rejects_early_exit_and_timeout(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "ready.json"
            live = SimpleNamespace(poll=lambda: None)
            ready = {"phase": "offlineSnapshotLoaded", "venues": 1705}
            self.assertEqual(wait_for_snapshot(live, marker, clock=lambda: 0,
                pause=lambda _: marker.write_text("CAFFEYE_SNAPSHOT_READY " + json.dumps(ready))), ready)
            with self.assertRaisesRegex(RuntimeError, "app exited"):
                wait_for_snapshot(SimpleNamespace(poll=lambda: 1), marker)
            marker.write_text('CAFFEYE_SNAPSHOT_READY {"phase":"other","venues":1705}')
            with self.assertRaisesRegex(RuntimeError, "invalid snapshot readiness"):
                wait_for_snapshot(live, marker)
            marker.unlink()
            ticks = iter([0, 1])
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                wait_for_snapshot(live, marker, timeout=1, clock=lambda: next(ticks))

    def test_summary_distinguishes_missing_leak_data_from_zero_leaks(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); heap = base / "heap"; leaks = base / "leaks"; vm = base / "vm"
            heap.write_text("  2079 3193344 1536.0 MKMarkerAnnotationView ObjC MapKit\n  1 224 224.0 AppModel Swift Caffeye\n")
            leaks.write_text("Process 123: 0 leaks for 0 total leaked bytes.\n")
            vm.write_text("Physical footprint: 286.1M\n")
            result = summarize(heap, leaks, vm)
            self.assertEqual(result["leaks"], {"count": 0, "bytes": 0})
            self.assertEqual(result["physicalFootprint"], "286.1M")
            self.assertEqual(result["appObjects"][0]["count"], 2079)
            leaks.write_text("Permission denied")
            self.assertIsNone(summarize(heap, leaks, vm)["leaks"])

    def test_readiness_survives_split_json_and_unrelated_partial_utf8(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "app.log"
            marker.write_text('CAFFEYE_SNAPSHOT_READY {"phase":')
            def finish_line(_):
                with marker.open("ab") as output:
                    output.write(b'"offlineSnapshotLoaded","venues":1705}\n' + b'\xc3')
            result = wait_for_snapshot(SimpleNamespace(poll=lambda: None), marker,
                                       clock=lambda: 0, pause=finish_line)
            self.assertEqual(result["venues"], 1705)

    def test_malformed_json_is_bounded_by_the_readiness_deadline(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "app.log"
            marker.write_text('CAFFEYE_SNAPSHOT_READY {"phase":')
            ticks = iter([0, 1])
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                wait_for_snapshot(SimpleNamespace(poll=lambda: None), marker,
                                  timeout=1, clock=lambda: next(ticks))


if __name__ == "__main__":
    unittest.main()
