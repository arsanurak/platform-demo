# One helm provider per cluster. Both read the kubeconfig stage 1 wrote, so
# this stage never needs the clusters' credentials in its own state.

provider "helm" {
  alias = "old"

  kubernetes = {
    config_path    = var.kubeconfig_path
    config_context = "kind-old"
  }
}

provider "helm" {
  alias = "new"

  kubernetes = {
    config_path    = var.kubeconfig_path
    config_context = "kind-new"
  }
}
