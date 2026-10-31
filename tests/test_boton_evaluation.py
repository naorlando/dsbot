"""Offline replay invariants are not claims about live model behavior or quality."""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, patch

from scripts import eval_boton


class BotonEvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_pipeline_replays(self):
        results = await eval_boton.evaluate()
        self.assertEqual(len(results), len(eval_boton.CHECKS))
        self.assertGreaterEqual(len(results), 10)
        self.assertEqual(len({result.name for result in results}), len(results))
        for result in results:
            with self.subTest(check=result.name):
                self.assertTrue(result.passed, result.detail)

    async def test_failures_are_counted_and_later_checks_still_run(self):
        bad = AsyncMock(side_effect=AssertionError("synthetic regression"))
        good = AsyncMock()
        results = await eval_boton.evaluate((("bad", bad), ("good", good)))
        self.assertEqual([result.passed for result in results], [False, True])
        self.assertIn("synthetic regression", results[0].detail)
        good.assert_awaited_once()

    async def test_replay_refuses_unexpected_provider_io(self):
        with eval_boton.Replay() as replay:
            with self.assertRaisesRegex(AssertionError, "Unexpected provider"):
                await replay.post(None, "https://unexpected.invalid", "synthetic", {})
            with self.assertRaisesRegex(AssertionError, "Network access"):
                replay.agent.session.post("https://unexpected.invalid")


class EvaluationCliTests(unittest.TestCase):
    # main owns asyncio.run; these MUST NOT be IsolatedAsyncioTestCase methods.
    def test_cli_success_prints_count_and_honest_scope(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = eval_boton.main()
        self.assertEqual(code, 0, output.getvalue())
        self.assertIn(f"{len(eval_boton.CHECKS)} checks:", output.getvalue())
        self.assertIn("0 failed", output.getvalue())
        self.assertIn("NOT real model conduct", output.getvalue())
        self.assertIn("zero API cost", output.getvalue())

    def test_cli_failure_is_nonzero_and_counts_failed_checks(self):
        results = [eval_boton.CheckResult("bad", False, "synthetic regression"),
                   eval_boton.CheckResult("good", True)]
        output = io.StringIO()
        with patch.object(eval_boton, "evaluate", new=AsyncMock(return_value=results)), redirect_stdout(output):
            code = eval_boton.main()
        self.assertNotEqual(code, 0)
        self.assertIn("FAIL bad: synthetic regression", output.getvalue())
        self.assertIn("2 checks: 1 passed, 1 failed", output.getvalue())
