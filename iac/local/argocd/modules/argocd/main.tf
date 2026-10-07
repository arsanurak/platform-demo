# Argo CD on one cluster, plus a root app that syncs gitops/bootstrap/<cluster>.
# That folder holds the ApplicationSet which creates every other Application,
# so after this apply Argo CD does the rest from git.

locals {
  charts = jsondecode(file("${path.module}/../../charts.json"))
  values = "${path.module}/../../values"
}

resource "helm_release" "argocd" {
  name             = "argocd"
  namespace        = "argocd"
  create_namespace = true
  repository       = local.charts.repository
  chart            = "argo-cd"
  version          = local.charts["argo-cd"]
  values           = [file("${local.values}/argo-cd.yaml")]
  wait             = true
  timeout          = 600
}

resource "helm_release" "root_app" {
  name       = "root-app"
  namespace  = "argocd"
  repository = local.charts.repository
  chart      = "argocd-apps"
  version    = local.charts["argocd-apps"]
  values     = [file("${local.values}/argocd-apps.yaml")]

  # Only what differs per cluster or per checkout is set here; the rest is in
  # values/argocd-apps.yaml, which CI renders with `helm template`.
  set = [
    {
      name  = "applications.root.source.repoURL"
      value = var.repo_url
    },
    {
      name  = "applications.root.source.targetRevision"
      value = var.git_revision
    },
    {
      name  = "applications.root.source.path"
      value = "gitops/bootstrap/${var.cluster}"
    },
  ]

  # The Application CRD ships with the argo-cd chart.
  depends_on = [helm_release.argocd]
}
