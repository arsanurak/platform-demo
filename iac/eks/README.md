# EKS root (validated, never applied)

A small Terraform root that shows how the **New cluster** would look on AWS. It is checked on every pull request and **never applied**: nobody runs `terraform apply` against it and it costs nothing. The provider only accepts the placeholder account `000000000000`, so even a mistaken plan with real credentials stops before it reads or changes anything. The S3 backend is a placeholder too.

It uses plain `aws_*` resources and no community EKS module, so every setting is visible in these files.

| File | What it holds |
| --- | --- |
| `main.tf` | The EKS control plane, with a private-only API endpoint, KMS-encrypted secrets and access through EKS access entries |
| `nodes.tf` | One managed node group in the private subnets, with IMDSv2 only and encrypted disks |
| `network.tf` | VPC, private and public subnets, one NAT gateway, routes, VPC flow logs and a closed default security group |
| `iam.tf` | Roles for the control plane, the nodes and the flow logs |
| `kms.tf`, `logs.tf` | The cluster's KMS key and its encrypted log groups |

## Checks

- `make validate` runs `terraform validate`.
- `make test-tf` runs `tests/eks.tftest.hcl` against a mocked AWS provider: no credentials, no account. Each `run` block checks one security property of the plan.
- `make test-iac` runs all of the above plus tflint (with the AWS ruleset), trivy and checkov. This root passes all three with no skipped checks.

## What it leaves out

Add-ons (CoreDNS, kube-proxy, VPC CNI versions), Pod Identity associations, a NAT gateway per zone and a bastion or VPN to reach the private endpoint. They add length, not insight, to a root that is never applied.
