#!/usr/bin/env python3
"""Check the guardrail properties on a rendered policy manifest.

Usage: check_policies.py MANIFEST.json

The manifest comes from render-policies.sh. Each failed property prints one
line starting with its id, such as `[role-has-boundary]`. Exits 1 if any fail.
"""

import fnmatch
import json
import sys

# Actions that would let a role change its own permissions. Written out here,
# not read from the Terraform, so the checks are an independent spec.
ROLE_EDIT_ACTIONS = [
    "iam:AttachRolePolicy",
    "iam:DeleteRolePermissionsBoundary",
    "iam:DeleteRolePolicy",
    "iam:DetachRolePolicy",
    "iam:PutRolePermissionsBoundary",
    "iam:PutRolePolicy",
    "iam:UpdateAssumeRolePolicy",
]

# Actions that would let a role rewrite a managed policy.
POLICY_EDIT_ACTIONS = [
    "iam:CreatePolicyVersion",
    "iam:DeletePolicyVersion",
    "iam:SetDefaultPolicyVersion",
]

# A sample of IAM writes. Any Allow pattern that matches one of these with a
# wildcard grants IAM writes nobody listed by hand.
IAM_WRITE_SAMPLE = ROLE_EDIT_ACTIONS + POLICY_EDIT_ACTIONS + [
    "iam:CreateAccessKey",
    "iam:CreatePolicy",
    "iam:CreateRole",
    "iam:CreateUser",
    "iam:PassRole",
]

IAM_READ_PREFIXES = ("iam:get", "iam:list", "iam:generate", "iam:simulate")

# Changes to how the bill is paid. The organization's SCPs must deny all of them.
PAYMENT_ACTIONS = [
    "aws-portal:ModifyPaymentMethods",
    "payments:CreatePaymentInstrument",
    "payments:DeletePaymentInstrument",
    "payments:UpdatePaymentPreferences",
]


def as_list(value):
    return value if isinstance(value, list) else [value]


def matches(patterns, value):
    """IAM-style match: `*` and `?` wildcards, case-insensitive."""
    return any(fnmatch.fnmatchcase(value.lower(), p.lower()) for p in as_list(patterns))


def denied(documents, action, resource):
    """True if an unconditional Deny in any of the documents covers the call."""
    return any(
        s["Effect"] == "Deny"
        and "Condition" not in s
        and matches(s.get("Action", []), action)
        and matches(s.get("Resource", []), resource)
        for document in documents
        for s in document["Statement"]
    )


def check_role_has_boundary(manifest):
    for arn, role in manifest["roles"].items():
        boundary = role.get("permissions_boundary")
        if not boundary:
            yield f"{arn} has no permissions boundary"
        elif boundary not in manifest["policies"]:
            yield f"{arn} names boundary {boundary}, which is not a rendered policy"


def check_role_cannot_edit_itself(manifest):
    arn = manifest["execution_role"]
    role = manifest["roles"][arn]
    own_policies = [role.get("permissions_boundary")] + role["policies"]
    documents = [manifest["policies"][p] for p in own_policies if p in manifest["policies"]]

    for action in ROLE_EDIT_ACTIONS:
        if not denied(documents, action, arn):
            yield f"{action} on {arn} is not denied"
    for policy in own_policies:
        for action in POLICY_EDIT_ACTIONS:
            if policy and not denied(documents, action, policy):
                yield f"{action} on {policy} is not denied"


def is_wildcard(text):
    return "*" in text or "?" in text


def check_no_wildcard_iam_writes(manifest):
    for arn, document in manifest["policies"].items():
        for s in document["Statement"]:
            if s["Effect"] != "Allow":
                continue
            if "NotAction" in s:
                yield f"{arn} allows NotAction, which grants every IAM write it does not name"
                continue
            for action in as_list(s["Action"]):
                if is_wildcard(action) and any(matches(action, w) for w in IAM_WRITE_SAMPLE):
                    yield f"{arn} allows {action}, a wildcard that covers IAM writes"
                elif (
                    action.lower().startswith("iam:")
                    and not action.lower().startswith(IAM_READ_PREFIXES)
                    and "*" in as_list(s.get("Resource", []))
                ):
                    yield f"{arn} allows {action} on every resource"


def check_payment_methods_locked(manifest):
    scps = list(manifest.get("service_control_policies", {}).values())
    for action in PAYMENT_ACTIONS:
        if not denied(scps, action, "*"):
            yield f"no service control policy denies {action} unconditionally"


CHECKS = {
    "role-has-boundary": check_role_has_boundary,
    "role-cannot-edit-itself": check_role_cannot_edit_itself,
    "no-wildcard-iam-writes": check_no_wildcard_iam_writes,
    "payment-methods-locked": check_payment_methods_locked,
}


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        manifest = json.load(f)

    failed = False
    for check_id, check in CHECKS.items():
        problems = list(check(manifest))
        for problem in problems:
            print(f"[{check_id}] FAIL: {problem}")
        if not problems:
            print(f"[{check_id}] ok")
        failed = failed or bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
