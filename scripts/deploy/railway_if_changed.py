"""Off-peak reconciliation against Railway's real deployment state; no local marker."""

import json
import os
import sys
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ENDPOINT = "https://backboard.railway.com/graphql/v2"
HEALTHY = {"SUCCESS", "SLEEPING"}
PENDING = {"INITIALIZING", "QUEUED", "BUILDING", "DEPLOYING", "WAITING", "REMOVING"}


def request_json(url, headers, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = Request(url, data=body, headers={"Content-Type": "application/json", **headers})
    try:
        with urlopen(req, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        # Never print headers, tokens, or untrusted provider response bodies.
        raise RuntimeError(f"API request failed (HTTP {exc.code})") from None
    except URLError:
        raise RuntimeError("API connection failed") from None


def graphql(query, variables):
    result = request_json(ENDPOINT, {"Project-Access-Token": os.environ["RAILWAY_TOKEN"]},
                          {"query": query, "variables": variables})
    if result.get("errors") or not result.get("data"):
        raise RuntimeError("Railway rejected the query; check token scope and API schema")
    return result["data"]


def commit_of(deployment):
    meta = (deployment or {}).get("meta") or {}
    if isinstance(meta, str):
        meta = json.loads(meta)
    return meta.get("commitHash") or meta.get("commitSha")


def decision(instance, target):
    """Fail closed if SHA metadata is missing instead of rebuilding every night."""
    latest = instance.get("latestDeployment")
    if latest and latest["status"] in PENDING:
        return "skip", "There is already a deployment in progress"
    for deployment in [latest, *instance.get("activeDeployments", [])]:
        if deployment and deployment["status"] in HEALTHY:
            commit = commit_of(deployment)
            if not commit:
                raise RuntimeError("Healthy deployment has no Git commit metadata; refusing blind redeploy")
            if commit == target:
                return "skip", "This exact commit is already deployed (including sleeping services)"
    if latest and latest["status"] == "NEEDS_APPROVAL":
        raise RuntimeError("Railway deployment requires approval")
    return "deploy", "The current main commit is not deployed successfully"


def off_peak(now=None):
    now = now or datetime.now(ZoneInfo("America/New_York"))
    return now.hour < 8 or now.hour >= 20


def report(message):
    print(message)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(message + "\n\n")


def main():
    for name in ("RAILWAY_TOKEN", "RAILWAY_SERVICE_ID", "RAILWAY_ENVIRONMENT_ID", "GITHUB_REPOSITORY", "GH_TOKEN"):
        if not os.getenv(name):
            raise RuntimeError(f"Missing required variable: {name}")
    repository = os.environ["GITHUB_REPOSITORY"]
    target = request_json(f"https://api.github.com/repos/{repository}/commits/main",
                          {"Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                           "User-Agent": "dsbot-deployment-check"})["sha"]
    variables = {"serviceId": os.environ["RAILWAY_SERVICE_ID"],
                 "environmentId": os.environ["RAILWAY_ENVIRONMENT_ID"]}
    instance = graphql("""query($serviceId: String!, $environmentId: String!) {
        serviceInstance(serviceId: $serviceId, environmentId: $environmentId) {
            latestDeployment { id status meta }
            activeDeployments { id status meta }
        }
    }""", variables)["serviceInstance"]
    action, reason = decision(instance, target)
    report(f"main: `{target}` — {action}: {reason}")
    if action == "skip":
        return
    if os.getenv("CHECK_ONLY", "false").lower() == "true":
        report("Check only: no deployment created.")
        return
    if not off_peak():
        report("Peak hours in New York: deployment deferred to the next scheduled run.")
        return
    # Recheck just before mutating to avoid racing GitHub autodeploy.
    fresh = graphql("""query($serviceId: String!, $environmentId: String!) {
        serviceInstance(serviceId: $serviceId, environmentId: $environmentId) {
            latestDeployment { id status meta } activeDeployments { id status meta }
        }
    }""", variables)["serviceInstance"]
    if decision(fresh, target)[0] == "skip":
        report("Railway changed while checking; no duplicate deployment created.")
        return
    deployment_id = graphql("""mutation($serviceId: String!, $environmentId: String!, $commitSha: String!) {
        serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId, commitSha: $commitSha)
    }""", {**variables, "commitSha": target})["serviceInstanceDeployV2"]
    report(f"Created deployment `{deployment_id}` for `{target}`.")
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        deployment = graphql("query($id: String!) { deployment(id: $id) { status meta } }",
                             {"id": deployment_id})["deployment"]
        status = deployment["status"]
        if status in HEALTHY:
            if commit_of(deployment) != target:
                raise RuntimeError("Deployment succeeded but its commit does not match the requested version")
            report(f"Railway confirmed `{status}` for the requested version.")
            return
        if status not in PENDING:
            raise RuntimeError(f"Railway deployment ended with status {status}")
        time.sleep(15)
    raise RuntimeError("Railway did not confirm success within 10 minutes; next run will inspect real state")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, KeyError, ValueError) as exc:
        print(f"Deployment check failed: {exc}", file=sys.stderr)
        sys.exit(1)
