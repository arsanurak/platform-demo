# Plan-level tests. The AWS provider is mocked, so these run with no
# credentials and never reach a real account. The pytest checks in
# iac/policy_checks cover what is inside the policy documents; these cover
# how this root wires them together.

mock_provider "aws" {
  override_during = plan
}

override_resource {
  override_during = plan
  target          = aws_iam_policy.boundary
  values          = { arn = "arn:aws:iam::000000000000:policy/platform-demo-boundary" }
}

override_resource {
  override_during = plan
  target          = aws_iam_policy.guardrail
  values          = { arn = "arn:aws:iam::000000000000:policy/platform-demo-guardrail" }
}

override_resource {
  override_during = plan
  target          = aws_iam_policy.permissions
  values          = { arn = "arn:aws:iam::000000000000:policy/platform-demo-execution" }
}

run "execution_role_is_capped_by_the_boundary" {
  command = plan

  assert {
    condition     = aws_iam_role.execution.permissions_boundary == "arn:aws:iam::000000000000:policy/platform-demo-boundary"
    error_message = "The Execution role must carry the Permission boundary."
  }
}

run "guardrail_is_attached_to_the_execution_role" {
  command = plan

  assert {
    condition     = aws_iam_role_policy_attachment.execution["guardrail"].policy_arn == "arn:aws:iam::000000000000:policy/platform-demo-guardrail"
    error_message = "The Guardrail policy must be attached to the Execution role."
  }

  assert {
    condition     = toset(keys(aws_iam_role_policy_attachment.execution)) == toset(["guardrail", "permissions"])
    error_message = "The Execution role must get exactly its own permissions and the Guardrail policy."
  }
}

run "only_main_of_one_repository_can_assume_the_role" {
  command = plan

  assert {
    condition     = jsondecode(aws_iam_role.execution.assume_role_policy).Statement[0].Action == "sts:AssumeRoleWithWebIdentity"
    error_message = "The role must only be assumable through web identity (OIDC)."
  }

  assert {
    condition = jsondecode(aws_iam_role.execution.assume_role_policy).Statement[0].Condition.StringEquals == {
      "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
      "token.actions.githubusercontent.com:sub" = "repo:example-org/platform-demo:ref:refs/heads/main"
    }
    error_message = "The trust must pin the audience and the exact repository and branch, with no wildcard."
  }
}

run "github_is_the_only_oidc_issuer" {
  command = plan

  assert {
    condition     = aws_iam_openid_connect_provider.github.url == "https://token.actions.githubusercontent.com"
    error_message = "The OIDC provider must be GitHub Actions' token issuer."
  }

  assert {
    condition     = toset(aws_iam_openid_connect_provider.github.client_id_list) == toset(["sts.amazonaws.com"])
    error_message = "Tokens must be issued for STS only."
  }
}

run "payment_lockout_is_an_attached_scp" {
  command = plan

  assert {
    condition     = aws_organizations_policy.payment_lockout.type == "SERVICE_CONTROL_POLICY"
    error_message = "The payment lockout must be a service control policy, so it binds whole accounts."
  }

  assert {
    condition     = jsondecode(aws_organizations_policy.payment_lockout.content).Statement[0].Effect == "Deny"
    error_message = "The payment lockout must deny."
  }

  assert {
    condition     = aws_organizations_policy_attachment.payment_lockout.target_id == var.scp_target_id
    error_message = "The payment lockout must be attached to its target."
  }
}

run "a_wildcard_repository_is_rejected" {
  command = plan

  variables {
    github_repository = "example-org/*"
  }

  expect_failures = [var.github_repository]
}
