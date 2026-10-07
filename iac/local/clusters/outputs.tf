output "kube_contexts" {
  description = "Kubeconfig context of each cluster, keyed by cluster name. Stage 2 uses these."
  value       = { for name, cluster in kind_cluster.this : name => "kind-${cluster.name}" }
}

output "kubeconfig_path" {
  description = "Kubeconfig file holding both contexts."
  value       = var.kubeconfig_path
}
