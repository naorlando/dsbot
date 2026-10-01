"""Manual opt-in for summarized metrics. No secrets in output; no deployment."""

import os
import sys

from scripts.deploy.railway_if_changed import graphql


def configure(value):
    if value not in {"true", "false"}:
        raise ValueError("AI_SHARE_METRICS must be true or false")
    result = graphql("mutation($input: VariableUpsertInput!) { variableUpsert(input: $input) }", {
        "input": {
            "projectId": "715d7dc5-22d0-413a-9482-3f9b3a0fe3fb",
            "serviceId": "90c60cd3-9b09-48c4-81b0-bd5fb5297033",
            "environmentId": "f80a184d-71dc-4b3a-9a79-b3760d7e4176",
            "name": "AI_SHARE_METRICS", "value": value, "skipDeploys": True,
        }})
    if result.get("variableUpsert") is not True:
        raise RuntimeError("Railway did not confirm configuration")
    print("AI_SHARE_METRICS=" + value + "; no deployment started")


if __name__ == "__main__":
    try:
        configure(os.environ.get("AI_SHARE_METRICS", ""))
    except (ValueError, RuntimeError, KeyError):
        print("Configuration failed; inspect project token permissions", file=sys.stderr)
        raise SystemExit(1) from None
