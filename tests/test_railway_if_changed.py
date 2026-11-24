import unittest
import os
from unittest.mock import patch
from datetime import datetime

from scripts.deploy.railway_if_changed import (decision, describe, forced, graphql, graphql_detail,
                                              off_peak, service_instance, successful_ci, main)


def deployment(status, commit="abc"):
    return {"status": status, "meta": {"commitHash": commit}}


class DeploymentDecisionTests(unittest.TestCase):
    def test_ci_requires_latest_success_for_exact_main_push(self):
        good = {'head_sha': 'abc', 'head_branch': 'main', 'event': 'push',
                'status': 'completed', 'conclusion': 'success'}
        self.assertTrue(successful_ci({'workflow_runs': [good]}, 'abc'))
        for change in ({'head_sha': 'old'}, {'head_branch': 'fork'}, {'event': 'pull_request'},
                       {'status': 'in_progress'}, {'conclusion': 'failure'}, {'conclusion': 'cancelled'}):
            self.assertFalse(successful_ci({'workflow_runs': [{**good, **change}, good]}, 'abc'))
        for data in ({}, None, {'workflow_runs': []}, {'workflow_runs': [None]}):
            self.assertFalse(successful_ci(data, 'abc'))

    def test_reconciliation_never_mutates_railway_when_ci_is_not_successful(self):
        env = {'RAILWAY_TOKEN': 'synthetic', 'RAILWAY_SERVICE_ID': 'service',
               'RAILWAY_ENVIRONMENT_ID': 'env', 'GITHUB_REPOSITORY': 'example/repo',
               'GH_TOKEN': 'synthetic', 'CHECK_ONLY': 'false'}
        with patch.dict(os.environ, env, clear=True), \
             patch('scripts.deploy.railway_if_changed.off_peak', return_value=True), \
             patch('scripts.deploy.railway_if_changed.report'), \
             patch('scripts.deploy.railway_if_changed.request_json', side_effect=[{'sha': 'abc'},
                   {'workflow_runs': []}]), \
             patch('scripts.deploy.railway_if_changed.graphql', return_value={'serviceInstance': {}}) as graphql:
            main()
        self.assertEqual(graphql.call_count, 2)
        self.assertTrue(all('mutation' not in call.args[0] for call in graphql.call_args_list))

    def test_successful_exact_sha_ci_allows_existing_off_peak_deploy_path(self):
        env = {'RAILWAY_TOKEN': 'synthetic', 'RAILWAY_SERVICE_ID': 'service',
               'RAILWAY_ENVIRONMENT_ID': 'env', 'GITHUB_REPOSITORY': 'example/repo',
               'GH_TOKEN': 'synthetic', 'CHECK_ONLY': 'false'}
        run = {'head_sha': 'abc', 'head_branch': 'main', 'event': 'push',
               'status': 'completed', 'conclusion': 'success'}
        with patch.dict(os.environ, env, clear=True), \
             patch('scripts.deploy.railway_if_changed.off_peak', return_value=True), \
             patch('scripts.deploy.railway_if_changed.report'), \
             patch('scripts.deploy.railway_if_changed.request_json', side_effect=[{'sha': 'abc'},
                   {'workflow_runs': [run]}]), \
             patch('scripts.deploy.railway_if_changed.graphql', side_effect=[{'serviceInstance': {}},
                   {'serviceInstance': {}}, {'serviceInstanceDeployV2': 'synthetic-deployment'},
                   {'deployment': deployment('SUCCESS')}]) as graphql:
            main()
        mutations = [call for call in graphql.call_args_list if 'mutation' in call.args[0]]
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0].args[1]['commitSha'], 'abc')

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

    def test_force_deploy_parsing(self):
        for value, expected in (("true", True), ("TRUE", True), ("1", True), ("yes", True),
                                ("false", False), ("", False), ("nope", False)):
            with patch.dict(os.environ, {"FORCE_DEPLOY": value}, clear=True):
                self.assertEqual(forced(), expected)
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(forced())

    def test_missing_service_instance_is_a_clear_failure_not_an_attribute_error(self):
        for data in ({}, {"serviceInstance": None}, {"serviceInstance": "nope"}):
            with self.assertRaises(RuntimeError) as caught:
                service_instance(data)
            self.assertIn("no service instance", str(caught.exception))

    def test_graphql_detail_is_one_safe_line(self):
        self.assertEqual(graphql_detail({"errors": [{"message": "  Not\n Authorized "}]}),
                         "Not Authorized")
        self.assertEqual(graphql_detail({"errors": [{"message": "x" * 500}]}), "x" * 200)
        for data in ({}, None, {"errors": []}, {"errors": [None]}, {"errors": [{"message": 5}]}):
            self.assertEqual(graphql_detail(data), "")

    def test_expired_token_names_the_real_problem(self):
        with patch.dict(os.environ, {"RAILWAY_TOKEN": "synthetic"}, clear=True), \
             patch('scripts.deploy.railway_if_changed.request_json',
                   return_value={"errors": [{"message": "Not Authorized"}], "data": None}):
            with self.assertRaises(RuntimeError) as caught:
                graphql("query { me { id } }", {})
        self.assertIn("generate a new project token", str(caught.exception))
        self.assertNotIn("synthetic", str(caught.exception))

    def test_other_graphql_errors_keep_their_detail(self):
        with patch.dict(os.environ, {"RAILWAY_TOKEN": "synthetic"}, clear=True), \
             patch('scripts.deploy.railway_if_changed.request_json',
                   return_value={"errors": [{"message": "Field 'x' does not exist"}], "data": None}):
            with self.assertRaises(RuntimeError) as caught:
                graphql("query { x }", {})
        self.assertIn("Field 'x' does not exist", str(caught.exception))

    def test_describe_reports_status_and_short_commit(self):
        self.assertEqual(describe(deployment("SUCCESS", "abcdef1234567")), "SUCCESS @ abcdef1")
        self.assertEqual(describe(deployment("FAILED", None)), "FAILED")
        self.assertEqual(describe(None), "none")
        self.assertEqual(describe({}), "none")

    def test_main_survives_a_null_instance_without_mutating(self):
        env = {'RAILWAY_TOKEN': 'synthetic', 'RAILWAY_SERVICE_ID': 'service',
               'RAILWAY_ENVIRONMENT_ID': 'env', 'GITHUB_REPOSITORY': 'example/repo',
               'GH_TOKEN': 'synthetic', 'CHECK_ONLY': 'false'}
        with patch.dict(os.environ, env, clear=True), \
             patch('scripts.deploy.railway_if_changed.off_peak', return_value=True), \
             patch('scripts.deploy.railway_if_changed.report'), \
             patch('scripts.deploy.railway_if_changed.request_json', return_value={'sha': 'abc'}), \
             patch('scripts.deploy.railway_if_changed.graphql',
                   return_value={'serviceInstance': None}) as graphql:
            with self.assertRaises(RuntimeError) as caught:
                main()
        self.assertIn("no service instance", str(caught.exception))
        self.assertTrue(all('mutation' not in call.args[0] for call in graphql.call_args_list))

    def test_force_bypasses_the_peak_window(self):
        env = {'RAILWAY_TOKEN': 'synthetic', 'RAILWAY_SERVICE_ID': 'service',
               'RAILWAY_ENVIRONMENT_ID': 'env', 'GITHUB_REPOSITORY': 'example/repo',
               'GH_TOKEN': 'synthetic', 'CHECK_ONLY': 'false', 'FORCE_DEPLOY': 'true'}
        run = {'head_sha': 'abc', 'head_branch': 'main', 'event': 'push',
               'status': 'completed', 'conclusion': 'success'}
        with patch.dict(os.environ, env, clear=True), \
             patch('scripts.deploy.railway_if_changed.off_peak', return_value=False), \
             patch('scripts.deploy.railway_if_changed.report'), \
             patch('scripts.deploy.railway_if_changed.request_json', side_effect=[{'sha': 'abc'},
                   {'workflow_runs': [run]}]), \
             patch('scripts.deploy.railway_if_changed.graphql', side_effect=[{'serviceInstance': {}},
                   {'serviceInstance': {}}, {'serviceInstanceDeployV2': 'synthetic-deployment'},
                   {'deployment': deployment('SUCCESS')}]) as graphql:
            main()
        mutations = [call for call in graphql.call_args_list if 'mutation' in call.args[0]]
        self.assertEqual(len(mutations), 1)


if __name__ == "__main__":
    unittest.main()
