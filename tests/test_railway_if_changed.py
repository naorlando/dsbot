import unittest
from datetime import datetime

from scripts.deploy.railway_if_changed import decision, off_peak


def deployment(status, commit="abc"):
    return {"status": status, "meta": {"commitHash": commit}}


class DeploymentDecisionTests(unittest.TestCase):
    def test_same_success_or_sleeping_skips(self):
        for status in ("SUCCESS", "SLEEPING"):
            self.assertEqual(decision({"latestDeployment": deployment(status)}, "abc")[0], "skip")

    def test_new_commit_deploys(self):
        self.assertEqual(decision({"latestDeployment": deployment("SUCCESS")}, "new")[0], "deploy")

    def test_failed_or_crashed_same_commit_retries(self):
        for status in ("FAILED", "CRASHED", "REMOVED", "SKIPPED"):
            self.assertEqual(decision({"latestDeployment": deployment(status)}, "abc")[0], "deploy")

    def test_autodeploy_in_progress_skips_even_different_sha(self):
        self.assertEqual(decision({"latestDeployment": deployment("BUILDING")}, "new")[0], "skip")

    def test_healthy_active_version_skips_after_failed_attempt(self):
        instance = {"latestDeployment": deployment("FAILED"),
                    "activeDeployments": [deployment("SUCCESS")]}
        self.assertEqual(decision(instance, "abc")[0], "skip")

    def test_missing_sha_fails_closed(self):
        with self.assertRaises(RuntimeError):
            decision({"latestDeployment": deployment("SUCCESS", None)}, "abc")

    def test_empty_service_deploys(self):
        self.assertEqual(decision({}, "abc")[0], "deploy")

    def test_peak_boundary(self):
        for hour, expected in ((7, True), (8, False), (19, False), (20, True)):
            self.assertEqual(off_peak(datetime(2026, 10, 1, hour)), expected)


if __name__ == "__main__":
    unittest.main()
