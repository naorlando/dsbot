import unittest
from unittest.mock import patch

from scripts.deploy.configure_assistant import configure


class ConfigureTests(unittest.TestCase):
    def test_only_fixed_flag_without_deployment(self):
        with patch("scripts.deploy.configure_assistant.graphql", return_value={"variableUpsert": True}) as call:
            configure("true")
        payload = call.call_args.args[1]["input"]
        self.assertEqual(payload["name"], "AI_SHARE_METRICS")
        self.assertEqual(payload["value"], "true")
        self.assertTrue(payload["skipDeploys"])
        self.assertEqual(payload["serviceId"], "90c60cd3-9b09-48c4-81b0-bd5fb5297033")

    def test_invalid_value_no_mutation(self):
        with patch("scripts.deploy.configure_assistant.graphql") as call:
            with self.assertRaises(ValueError):
                configure("arbitrary")
        call.assert_not_called()

    def test_unconfirmed_write_fails(self):
        with patch("scripts.deploy.configure_assistant.graphql", return_value={"variableUpsert": False}):
            with self.assertRaises(RuntimeError):
                configure("false")
