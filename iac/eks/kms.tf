# One customer-managed key for this cluster: it envelope-encrypts Kubernetes
# secrets and encrypts the cluster's CloudWatch log groups.

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  account_arn = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"
}

resource "aws_kms_key" "this" {
  description             = "Encrypts secrets and logs for the ${var.cluster_name} EKS cluster"
  enable_key_rotation     = true
  deletion_window_in_days = 30

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AccountAdministersKeyThroughIam"
        Effect    = "Allow"
        Principal = { AWS = local.account_arn }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "CloudWatchLogsEncryptsClusterLogs"
        Effect    = "Allow"
        Principal = { Service = "logs.${var.region}.amazonaws.com" }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
        ]
        Resource = "*"
        Condition = {
          ArnLike = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:${data.aws_partition.current.partition}:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:*"
          }
        }
      },
    ]
  })
}

resource "aws_kms_alias" "this" {
  name          = "alias/${var.cluster_name}-eks"
  target_key_id = aws_kms_key.this.key_id
}
