# The guardrail policy documents, written as plain data with no provider.
#
# Keeping them provider-free means `iac/policy_checks/render-policies.sh` can
# render them with a credential-free `terraform plan`, and the pytest checks
# read exactly the JSON that the guardrails root would attach.

locals {
  iam_arn = "arn:aws:iam::${var.account_id}"

  role_name      = "${var.name_prefix}-execution"
  role_arn       = "${local.iam_arn}:role/${local.role_name}"
  boundary_arn   = "${local.iam_arn}:policy/${var.name_prefix}-boundary"
  guardrail_arn  = "${local.iam_arn}:policy/${var.name_prefix}-guardrail"
  permission_arn = "${local.iam_arn}:policy/${var.name_prefix}-execution"

  # Roles the Execution role creates for workloads live under this path, and
  # it may only create them with the Permission boundary attached.
  workload_roles = "${local.iam_arn}:role/workload/*"

  # Everything that would let a role change its own permissions.
  role_edit_actions = [
    "iam:AttachRolePolicy",
    "iam:DeleteRole",
    "iam:DeleteRolePermissionsBoundary",
    "iam:DeleteRolePolicy",
    "iam:DetachRolePolicy",
    "iam:PutRolePermissionsBoundary",
    "iam:PutRolePolicy",
    "iam:TagRole",
    "iam:UntagRole",
    "iam:UpdateAssumeRolePolicy",
    "iam:UpdateRole",
    "iam:UpdateRoleDescription",
  ]

  # Everything that would let a role rewrite a managed policy.
  policy_edit_actions = [
    "iam:CreatePolicyVersion",
    "iam:DeletePolicy",
    "iam:DeletePolicyVersion",
    "iam:SetDefaultPolicyVersion",
    "iam:TagPolicy",
    "iam:UntagPolicy",
  ]

  # The Guardrail policy: explicit denies that win over any allow. It is
  # attached to the Execution role and repeated inside the Permission
  # boundary, so removing the attachment would not lift it.
  guardrail_statements = [
    {
      Sid      = "DenyEditingTheExecutionRole"
      Effect   = "Deny"
      Action   = local.role_edit_actions
      Resource = [local.role_arn]
    },
    {
      Sid      = "DenyEditingTheGuardrails"
      Effect   = "Deny"
      Action   = local.policy_edit_actions
      Resource = [local.boundary_arn, local.guardrail_arn, local.permission_arn]
    },
    {
      Sid      = "DenyRemovingBoundariesFromWorkloadRoles"
      Effect   = "Deny"
      Action   = ["iam:DeleteRolePermissionsBoundary"]
      Resource = [local.workload_roles]
    },
  ]

  # IAM writes the Execution role needs to create workload roles, each named
  # explicitly and only allowed when the new role carries the boundary.
  workload_role_statements = [
    {
      Sid    = "ManageWorkloadRolesWithTheBoundary"
      Effect = "Allow"
      Action = [
        "iam:AttachRolePolicy",
        "iam:CreateRole",
        "iam:DeleteRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePermissionsBoundary",
        "iam:PutRolePolicy",
      ]
      Resource  = [local.workload_roles]
      Condition = { StringEquals = { "iam:PermissionsBoundary" = local.boundary_arn } }
    },
    {
      Sid    = "TidyWorkloadRoles"
      Effect = "Allow"
      Action = [
        "iam:DeleteRole",
        "iam:TagRole",
        "iam:UntagRole",
        "iam:UpdateAssumeRolePolicy",
      ]
      Resource = [local.workload_roles]
    },
    {
      Sid       = "PassWorkloadRolesToEksAndEc2"
      Effect    = "Allow"
      Action    = ["iam:PassRole"]
      Resource  = [local.workload_roles]
      Condition = { StringEquals = { "iam:PassedToService" = ["eks.amazonaws.com", "ec2.amazonaws.com"] } }
    },
  ]

  # The services an infrastructure apply touches, kept to one region.
  service_statement = {
    Sid       = "BuildInfrastructureInOneRegion"
    Effect    = "Allow"
    Action    = ["ec2:*", "eks:*", "kms:*", "logs:*"]
    Resource  = ["*"]
    Condition = { StringEquals = { "aws:RequestedRegion" = var.region } }
  }

  read_iam_statement = {
    Sid      = "ReadIam"
    Effect   = "Allow"
    Action   = ["iam:Get*", "iam:List*"]
    Resource = ["*"]
  }

  documents = {
    # The Permission boundary caps the Execution role: whatever its own
    # policies grant, it can never do more than this.
    (local.boundary_arn) = {
      Version   = "2012-10-17"
      Statement = concat([local.service_statement, local.read_iam_statement], local.workload_role_statements, local.guardrail_statements)
    }
    (local.guardrail_arn) = {
      Version   = "2012-10-17"
      Statement = local.guardrail_statements
    }
    (local.permission_arn) = {
      Version   = "2012-10-17"
      Statement = concat([local.service_statement, local.read_iam_statement], local.workload_role_statements)
    }
  }

  # Only the main branch of one repository can assume the role, through
  # GitHub's OIDC provider. No access keys exist for it.
  trust_policy = {
    Version = "2012-10-17"
    Statement = [{
      Sid       = "GitHubActionsOnMain"
      Effect    = "Allow"
      Principal = { Federated = "${local.iam_arn}:oidc-provider/token.actions.githubusercontent.com" }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:ref:refs/heads/main"
        }
      }
    }]
  }

  # A service control policy for the organization: no principal in a member
  # account can change how the bill is paid. SCPs never apply to the
  # management account, which keeps that power.
  payment_lockout = {
    Version = "2012-10-17"
    Statement = [{
      Sid    = "DenyPaymentMethodChanges"
      Effect = "Deny"
      Action = [
        "aws-portal:ModifyPaymentMethods",
        "payments:CreatePaymentInstrument",
        "payments:DeletePaymentInstrument",
        "payments:MakePayment",
        "payments:UpdatePaymentPreferences",
      ]
      Resource = ["*"]
    }]
  }
}
