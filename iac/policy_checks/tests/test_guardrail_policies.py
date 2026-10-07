"""Guardrail properties, asserted on the policy JSON that Terraform renders.

Each property has two tests: the rendered guardrails pass it, and a copy that is
deliberately loosened fails it. The second test is what proves the check works.
"""

PASSED = 0
FAILED = 1


def test_the_rendered_guardrails_pass_every_check(rendered, check):
    code, output = check(rendered)
    assert code == PASSED, output


def test_a_role_without_a_permission_boundary_fails(manifest, check):
    role = manifest["roles"][manifest["execution_role"]]
    del role["permissions_boundary"]

    code, output = check(manifest)

    assert code == FAILED
    assert "[role-has-boundary]" in output


def remove_from_every_deny(manifest, action):
    """Loosen the guardrails: drop one action from every deny statement."""
    for document in manifest["policies"].values():
        for statement in document["Statement"]:
            if statement["Effect"] == "Deny":
                statement["Action"] = [a for a in statement["Action"] if a != action]


def test_a_role_that_can_attach_policies_to_itself_fails(manifest, check):
    remove_from_every_deny(manifest, "iam:AttachRolePolicy")

    code, output = check(manifest)

    assert code == FAILED
    assert "[role-cannot-edit-itself]" in output
    assert "iam:AttachRolePolicy" in output


def test_a_role_that_can_rewrite_its_boundary_fails(manifest, check):
    remove_from_every_deny(manifest, "iam:CreatePolicyVersion")

    code, output = check(manifest)

    assert code == FAILED
    assert "[role-cannot-edit-itself]" in output
    assert "platform-demo-boundary" in output


def add_to_permissions(manifest, statement):
    """Loosen the guardrails: grant one more statement to the Execution role."""
    role = manifest["roles"][manifest["execution_role"]]
    permissions = next(p for p in role["policies"] if p.endswith("-execution"))
    manifest["policies"][permissions]["Statement"].append(statement)


def test_a_wildcard_iam_action_fails(manifest, check):
    add_to_permissions(manifest, {"Effect": "Allow", "Action": "iam:*", "Resource": "*"})

    code, output = check(manifest)

    assert code == FAILED
    assert "[no-wildcard-iam-writes]" in output
    assert "iam:*" in output


def test_an_iam_write_on_every_resource_fails(manifest, check):
    add_to_permissions(manifest, {"Effect": "Allow", "Action": ["iam:PassRole"], "Resource": ["*"]})

    code, output = check(manifest)

    assert code == FAILED
    assert "[no-wildcard-iam-writes]" in output
    assert "iam:PassRole" in output


def test_reading_iam_with_a_wildcard_passes(manifest, check):
    add_to_permissions(manifest, {"Effect": "Allow", "Action": "iam:List*", "Resource": "*"})

    code, output = check(manifest)

    assert code == PASSED, output


def test_an_scp_that_lets_payment_methods_change_fails(manifest, check):
    for scp in manifest["service_control_policies"].values():
        for statement in scp["Statement"]:
            statement["Condition"] = {"StringNotEquals": {"aws:PrincipalAccount": "000000000000"}}

    code, output = check(manifest)

    assert code == FAILED
    assert "[payment-methods-locked]" in output
