output "cluster_name" {
  description = "Name of the EKS cluster."
  value       = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  description = "Private endpoint of the Kubernetes API."
  value       = aws_eks_cluster.this.endpoint
}

output "vpc_id" {
  description = "ID of the cluster VPC."
  value       = aws_vpc.this.id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets the nodes run in."
  value       = aws_subnet.private[*].id
}
