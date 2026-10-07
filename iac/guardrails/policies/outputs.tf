output "role_name" {
  description = "Name of the Execution role."
  value       = local.role_name
}

output "trust_policy" {
  description = "Trust policy of the Execution role, as JSON."
  value       = jsonencode(local.trust_policy)
}

output "boundary" {
  description = "Name and JSON document of the Permission boundary."
  value       = { name = "${var.name_prefix}-boundary", json = jsonencode(local.documents[local.boundary_arn]) }
}

output "guardrail" {
  description = "Name and JSON document of the Guardrail policy."
  value       = { name = "${var.name_prefix}-guardrail", json = jsonencode(local.documents[local.guardrail_arn]) }
}

output "permissions" {
  description = "Name and JSON document of the Execution role's own permissions."
  value       = { name = "${var.name_prefix}-execution", json = jsonencode(local.documents[local.permission_arn]) }
}

output "payment_lockout" {
  description = "The payment-method lockout service control policy, as JSON."
  value       = jsonencode(local.payment_lockout)
}

output "manifest" {
  description = "Every role and policy in one object, for the policy checks in iac/policy_checks."
  value = {
    execution_role = local.role_arn
    roles = {
      (local.role_arn) = {
        trust_policy         = local.trust_policy
        permissions_boundary = local.boundary_arn
        policies             = [local.guardrail_arn, local.permission_arn]
      }
    }
    policies                 = local.documents
    service_control_policies = { "deny-payment-method-changes" = local.payment_lockout }
  }
}
