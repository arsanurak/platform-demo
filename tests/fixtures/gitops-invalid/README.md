Manifests that are wrong on purpose. `make check-gitops` expects kubeconform to
reject every file here, which proves the CRD schemas are really applied and an
unknown kind is never silently skipped.
