# EKS writes control-plane logs to a log group with a fixed name. Creating it
# here first means it is encrypted and has a retention period; otherwise EKS
# creates it unencrypted and keeps logs forever.

resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.this.arn
}

resource "aws_cloudwatch_log_group" "flow_logs" {
  name              = "/aws/vpc/${var.cluster_name}/flow-logs"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.this.arn
}
