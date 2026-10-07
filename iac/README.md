# IaC area

Terraform roots and modules. See `docs/adr/0001-one-repo-for-iac-and-gitops.md` for why this lives next to `gitops/`.

- `eks/`: an EKS cluster root that is validated and tested but never applied. See `eks/README.md`.
