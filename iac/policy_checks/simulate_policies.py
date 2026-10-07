#!/usr/bin/env python3
"""Run the guardrails through the IAM policy simulator: simulate_policies.py MANIFEST.json

Opt-in and read-only. It runs only when AWS credentials are in the environment
(CI exports them through OIDC when the repo configures a simulator role) and
otherwise prints that it skipped and exits 0. `simulate-custom-policy` only
evaluates the JSON it is given: it reads and changes nothing in the account.

Each case states the decision IAM must reach for one call made by the
Execution role, with its boundary and policies applied. SCPs can't be
simulated this way; the payment lockout is covered by check_policies.py.
"""

import json
import os
import subprocess
import sys

ROLE = "arn:aws:iam::000000000000:role/platform-demo-execution"
BOUNDARY = "arn:aws:iam::000000000000:policy/platform-demo-boundary"
GUARDRAIL = "arn:aws:iam::000000000000:policy/platform-demo-guardrail"
WORKLOAD_ROLE = "arn:aws:iam::000000000000:role/workload/app01"
WITH_BOUNDARY = {"iam:PermissionsBoundary": BOUNDARY}
IN_REGION = {"aws:RequestedRegion": "eu-west-1"}

# (action, resource, context, expected decision)
CASES = [
    ("iam:PutRolePolicy", ROLE, {}, "explicitDeny"),
    ("iam:AttachRolePolicy", ROLE, {}, "explicitDeny"),
    ("iam:DeleteRolePermissionsBoundary", ROLE, {}, "explicitDeny"),
    ("iam:PutRolePermissionsBoundary", ROLE, {}, "explicitDeny"),
    ("iam:UpdateAssumeRolePolicy", ROLE, {}, "explicitDeny"),
    ("iam:CreatePolicyVersion", BOUNDARY, {}, "explicitDeny"),
    ("iam:SetDefaultPolicyVersion", BOUNDARY, {}, "explicitDeny"),
    ("iam:CreatePolicyVersion", GUARDRAIL, {}, "explicitDeny"),
    ("iam:CreateRole", WORKLOAD_ROLE, WITH_BOUNDARY, "allowed"),
    ("iam:CreateRole", WORKLOAD_ROLE, {}, "implicitDeny"),
    ("iam:CreateRole", "arn:aws:iam::000000000000:role/admin", WITH_BOUNDARY, "implicitDeny"),
    ("iam:DeleteRolePermissionsBoundary", WORKLOAD_ROLE, {}, "explicitDeny"),
    ("eks:CreateCluster", "*", IN_REGION, "allowed"),
    ("eks:CreateCluster", "*", {"aws:RequestedRegion": "us-east-1"}, "implicitDeny"),
]


def simulate(manifest, action, resource, context):
    role = manifest["roles"][manifest["execution_role"]]
    command = [
        "aws", "iam", "simulate-custom-policy", "--output", "json",
        "--action-names", action,
        "--resource-arns", resource,
        "--permissions-boundary-policy-input-list",
        json.dumps(manifest["policies"][role["permissions_boundary"]]),
        "--policy-input-list",
        *[json.dumps(manifest["policies"][p]) for p in role["policies"]],
    ]
    if context:
        command += ["--context-entries"] + [
            f"ContextKeyName={key},ContextKeyValues={value},ContextKeyType=string"
            for key, value in context.items()
        ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)["EvaluationResults"][0]["EvalDecision"]


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        print("Policy simulator skipped: no AWS credentials in the environment.")
        return 0
    with open(argv[1]) as f:
        manifest = json.load(f)

    failed = 0
    for action, resource, context, expected in CASES:
        decision = simulate(manifest, action, resource, context)
        ok = decision == expected
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {action} on {resource}: got {decision}, expected {expected}")
    print(f"{len(CASES) - failed} of {len(CASES)} simulated calls matched.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
