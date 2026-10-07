# Stage 2: Argo CD and its root app on each kind cluster from stage 1
# (../clusters). Run it as a separate apply, after stage 1.

module "old" {
  source = "./modules/argocd"

  providers = {
    helm = helm.old
  }

  cluster      = "old"
  repo_url     = var.repo_url
  git_revision = var.git_revision
}

module "new" {
  source = "./modules/argocd"

  providers = {
    helm = helm.new
  }

  cluster      = "new"
  repo_url     = var.repo_url
  git_revision = var.git_revision
}
