"""app/tasks.py (tidy, run lock) and app/instances.py (reports of several Tuttiphon instances).

No steps are run: TaskRunner._start is replaced in the lock tests."""
from tests.python import env  # noqa: F401  (before app.*)

import json
import os
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock

from app import images, instances, tasks
from app.config import BACKUP_DIR, LOG_DIR
from app.tasks import HISTORY_FILE, TaskRunner

DAY = 86400


class TestTidy(unittest.TestCase):
    def setUp(self):
        env.clear_dir(LOG_DIR)
        env.clear_dir(images.CACHE_DIR)
        HISTORY_FILE.unlink(missing_ok=True)
        self.addCleanup(env.clear_dir, LOG_DIR)
        self.addCleanup(env.clear_dir, images.CACHE_DIR)
        self.addCleanup(HISTORY_FILE.unlink, missing_ok=True)
        self.now = time.time()

    def file(self, path, age_days):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
        t = self.now - age_days * DAY
        os.utime(path, (t, t))
        return path

    def test_removes_old_logs_and_cached_images(self):
        old_log = self.file(LOG_DIR / "2025-01-01_050000_playlists.log", 91)
        old_sub = self.file(LOG_DIR / "alt" / "x.log", 200)
        new_log = self.file(LOG_DIR / "2026-09-01_050000_scan.log", 89)
        old_img = self.file(images.CACHE_DIR / "ab" / "abc.jpg", 61)
        new_img = self.file(images.CACHE_DIR / "cd" / "cde.jpg", 59)
        kept_backup = self.file(BACKUP_DIR / "test-tidy-original.nsp", 400)
        self.addCleanup(kept_backup.unlink, missing_ok=True)
        self.assertEqual(tasks.tidy(self.now), 3)
        for p in (old_log, old_sub, old_img):
            self.assertFalse(p.exists(), p)
        for p in (new_log, new_img, kept_backup):   # backups always stay
            self.assertTrue(p.exists(), p)

    def test_history_is_cut_to_the_last_2000_runs(self):
        HISTORY_FILE.write_text("".join(json.dumps({"n": i}) + "\n" for i in range(2050)))
        tasks.tidy(self.now)
        lines = HISTORY_FILE.read_text().splitlines()
        self.assertEqual(len(lines), 2000)
        self.assertEqual((json.loads(lines[0])["n"], json.loads(lines[-1])["n"]), (50, 2049))
        HISTORY_FILE.write_text("{}\n" * 10)
        tasks.tidy(self.now)
        self.assertEqual(len(HISTORY_FILE.read_text().splitlines()), 10)

    def test_missing_folders_are_fine(self):
        HISTORY_FILE.unlink(missing_ok=True)
        self.assertEqual(tasks.tidy(self.now), 0)


class InstanceTest(unittest.TestCase):
    def setUp(self):
        env.clear_dir(env.SHARED)
        env.reset_caches()
        self.instance_id = instances.INSTANCE_ID
        self.state = dict(instances._state)

        def restore():
            instances.INSTANCE_ID = self.instance_id
            instances._state.clear()
            instances._state.update(self.state, dir=None, at=0.0)
            env.clear_dir(env.SHARED)
        self.addCleanup(restore)

    def other(self, name="docker:nas", running=True, age=0, raw=None, install=None):
        path = env.SHARED / f"instance-{name.replace(':', '_')}.json"
        data = {"id": name, "ts": time.time() - age, "host": name.split(":")[-1], "docker": name.startswith("docker"),
                "running": running, **({"install": install} if install else {})}
        path.write_text(raw if raw is not None else json.dumps(data))
        return path

    def own_file(self):
        return instances._file(instances.INSTANCE_ID)


class TestInstances(InstanceTest):
    def test_shared_dir_from_environment(self):
        self.assertEqual(instances.shared_dir(), env.SHARED)

    @unittest.skipIf(os.geteuid() == 0, "as root every folder is writable")
    def test_shared_dir_falls_back_to_state(self):
        ro = env.ROOT / "nur-lesen"
        ro.mkdir(exist_ok=True)
        os.chmod(ro, 0o555)
        self.addCleanup(os.chmod, ro, 0o755)
        with mock.patch.dict(os.environ, {"TUTTIPHON_SHARED_DIR": str(ro / "x")}):
            instances._state.update(dir=None, at=0.0)
            self.assertEqual(instances.shared_dir(), instances.STATE_DIR)
        instances._state.update(dir=None, at=0.0)

    def test_heartbeat_writes_own_report(self):
        instances.heartbeat(running=True)
        data = json.loads(self.own_file().read_text())
        self.assertEqual((data["id"], data["running"]), (instances.INSTANCE_ID, True))
        self.assertEqual(os.stat(self.own_file()).st_mode & 0o777, 0o666)   # PC and container may write
        instances.heartbeat()   # without an argument the state stays
        self.assertTrue(json.loads(self.own_file().read_text())["running"])
        instances.heartbeat(running=False)
        self.assertFalse(json.loads(self.own_file().read_text())["running"])

    def test_others(self):
        instances.heartbeat(running=True)                          # our own report does not count
        self.other("docker:nas", running=True)
        self.other("pc:laptop", running=False, age=60)
        stale = self.other("pc:alt", running=True, age=instances.FRESH + 10)
        gone = self.other("pc:weg", running=True, age=8 * DAY)
        self.other("pc:kaputt", raw="{nicht json")
        self.other("pc:liste", raw="[1, 2]")
        found = sorted(instances.others(), key=lambda o: o["host"])
        self.assertEqual(found, [{"host": "laptop", "docker": False, "running": False},
                                 {"host": "nas", "docker": True, "running": True}])
        self.assertTrue(stale.exists())     # only too old for "still running"
        self.assertFalse(gone.exists())     # removed after a week

    def test_busy_elsewhere(self):
        self.assertFalse(instances.busy_elsewhere())
        self.other("docker:nas", running=False)
        self.assertFalse(instances.busy_elsewhere())
        self.other("pc:alt", running=True, age=instances.FRESH + 10)
        self.assertFalse(instances.busy_elsewhere())
        self.other("docker:nas", running=True)
        self.assertTrue(instances.busy_elsewhere())
        instances.heartbeat(running=True)   # our own instance is never "elsewhere"
        self.other("docker:nas", running=False)
        self.assertFalse(instances.busy_elsewhere())

    def test_same_installation_under_another_name_is_not_a_second_tuttiphon(self):
        # e.g. the container before an update, when its host name changed from "navitool" to "tuttiphon"
        own = instances.install_id()
        self.assertRegex(own, r"^[0-9a-f]{16}$")
        self.assertEqual(instances.install_id(), own)                      # stays the same
        instances._state["install"] = None
        self.assertEqual(instances.install_id(), own)                      # read back from the data folder
        self.other("docker:navitool", running=True, install=own)
        self.other("pc:laptop", running=False, install="0123456789abcdef")
        self.assertEqual([o["host"] for o in instances.others(foreign_only=True)], ["laptop"])
        self.assertEqual(len(instances.others()), 2)
        self.assertTrue(instances.busy_elsewhere())                        # its run still blocks ours
        instances.heartbeat()
        self.assertEqual(json.loads(self.own_file().read_text())["install"], own)

    def test_command_line_run_has_its_own_report(self):
        instances.heartbeat(running=False)          # the server on the same machine
        server_file = self.own_file()
        instances.use_cli_id()
        self.assertTrue(instances.INSTANCE_ID.endswith(f":run-{os.getpid()}"))
        instances.heartbeat(running=True)
        cli_file = self.own_file()
        self.assertNotEqual(cli_file, server_file)
        self.assertEqual([o["running"] for o in instances.others()], [False])   # sees the server
        instances.heartbeat(running=False)          # run over: report gone, the server's stays
        self.assertFalse(cli_file.exists())
        self.assertTrue(server_file.exists())


LOCKER = """
import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o666)
fcntl.lockf(fd, fcntl.LOCK_EX)
print("gesperrt", flush=True)
sys.stdin.read()
"""


@env.german   # checks the German output of existing installations
class TestTaskRunnerLock(InstanceTest):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(TaskRunner, "_start", autospec=True, return_value={"gestartet": True})
        self.start_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def release_started(self):
        """Release the lock that start() passed to the (replaced) _start."""
        lock = self.start_mock.call_args.args[4]
        lock.release()
        instances.heartbeat(running=False)

    def test_other_instance_running_blocks_start(self):
        self.other("docker:nas", running=True)
        runner = TaskRunner()
        with self.assertRaises(RuntimeError) as ctx:
            runner.start(["playlists", "scan"])
        self.assertIn("andere Tuttiphon-Instanz", str(ctx.exception))
        self.start_mock.assert_not_called()
        self.assertFalse(self.own_file().exists())   # nothing reported as "running"
        self.assertFalse(runner.running())

    def test_idle_or_stale_other_instance_does_not_block(self):
        self.other("docker:nas", running=False)
        self.other("pc:alt", running=True, age=instances.FRESH + 10)
        self.assertEqual(TaskRunner().start(["playlists"]), {"gestartet": True})
        self.assertTrue(json.loads(self.own_file().read_text())["running"])   # reported right away
        self.release_started()

    def test_lock_held_by_another_process_blocks_start(self):
        lock_file = env.SHARED / "task.lock"
        proc = subprocess.Popen([sys.executable, "-c", LOCKER, str(lock_file)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(), "gesperrt")
            with self.assertRaises(RuntimeError):
                TaskRunner().start(["deezer"])
            self.start_mock.assert_not_called()
        finally:
            proc.stdin.close()
            proc.wait(timeout=10)
            proc.stdout.close()
        lock = tasks._InstanceLock()   # other instance done -> lock free
        self.assertTrue(lock.acquire())
        lock.release()

    def test_second_start_in_the_same_process(self):
        stop = threading.Event()
        runner = TaskRunner()
        runner.thread = threading.Thread(target=stop.wait, daemon=True)
        runner.thread.start()
        try:
            with self.assertRaises(RuntimeError) as ctx:
                runner.start(["scan"])
            self.assertIn("läuft bereits", str(ctx.exception))
        finally:
            stop.set()
            runner.thread.join()
        self.start_mock.assert_not_called()

    def test_unknown_or_no_steps(self):
        for steps in (["kaffee"], [], ["scan", "x"]):
            with self.assertRaises(ValueError):
                TaskRunner().start(steps)
        self.start_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
