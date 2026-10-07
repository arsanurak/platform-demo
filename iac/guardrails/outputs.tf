output "execution_role_arn" {
  description = "ARN CI would pass to aws-actions/configure-aws-credentials."
  value       = aws_iam_role.execution.arn
}
