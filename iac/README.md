# IaC area

Terraform roots and modules. See `docs/adr/0001-one-repo-for-iac-and-gitops.md` for why this lives next to `gitops/`.

- `eks/`: an EKS cluster root that is validated and tested but never applied. See `eks/README.md`.
- `guardrails/`: the **Execution role** CI assumes through GitHub OIDC, its **Permission boundary** and the **Guardrail policies**. Tested, never applied. See `guardrails/README.md`.
- `policy_checks/`: pytest checks and the opt-in IAM policy simulator, run on the guardrail policy JSON.

`make test-iac` runs every check here with no cloud credentials: fmt, validate, `terraform test`, tflint, trivy, checkov and the policy checks. `make iac-tools` installs the pinned tools into `.tools/` first.
