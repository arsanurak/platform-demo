# The policy documents live in ./policies, a module with no provider, so the
# pytest checks in iac/policy_checks read the same JSON this root attaches.

module "policies" {
  source = "./policies"

  account_id        = "000000000000"
  region            = var.region
  github_repository = var.github_repository
}

# GitHub's OIDC issuer. CI exchanges a short-lived GitHub token for role
# credentials, so no access key for the Execution role ever exists.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

# The Permission boundary: the most the Execution role can ever do.
# trivy flags any iam:PassRole (AWS-0342). EKS needs it to hand the cluster and
# node roles to the service; it is limited to role/workload/* and to the EKS
# and EC2 services by condition, and the pytest checks forbid it on "*".
#trivy:ignore:AWS-0342
resource "aws_iam_policy" "boundary" {
  name        = module.policies.boundary.name
  description = "Caps the Execution role, whatever its own policies grant."
  policy      = module.policies.boundary.json
}

# Denies that stop the Execution role from loosening itself.
resource "aws_iam_policy" "guardrail" {
  name        = module.policies.guardrail.name
  description = "Denies the Execution role editing itself, its boundary or these policies."
  policy      = module.policies.guardrail.json
}

# PassRole: see the note on the boundary above.
#trivy:ignore:AWS-0342
resource "aws_iam_policy" "permissions" {
  name        = module.policies.permissions.name
  description = "What the Execution role needs to apply this repo's infrastructure."
  policy      = module.policies.permissions.json
}

resource "aws_iam_role" "execution" {
  name                 = module.policies.role_name
  description          = "Assumed by CI through GitHub OIDC to apply infrastructure."
  assume_role_policy   = module.policies.trust_policy
  permissions_boundary = aws_iam_policy.boundary.arn
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "execution" {
  for_each = {
    guardrail   = aws_iam_policy.guardrail.arn
    permissions = aws_iam_policy.permissions.arn
  }

  role       = aws_iam_role.execution.name
  policy_arn = each.value
}

# Account-level protection beyond IAM: an organization SCP that stops every
# principal in the target accounts changing payment methods.
resource "aws_organizations_policy" "payment_lockout" {
  name        = "deny-payment-method-changes"
  description = "No principal in a member account can change how the bill is paid."
  type        = "SERVICE_CONTROL_POLICY"
  content     = module.policies.payment_lockout
}

resource "aws_organizations_policy_attachment" "payment_lockout" {
  policy_id = aws_organizations_policy.payment_lockout.id
  target_id = var.scp_target_id
}
