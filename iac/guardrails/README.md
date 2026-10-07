# Guardrails root (tested, never applied)

The identity CI would use to apply this repo's infrastructure, and the policies that stop it loosening itself. Like `eks/`, it is checked on every pull request and **never applied**: the provider only accepts the placeholder account `000000000000`.

| File | What it holds |
| --- | --- |
| `policies/` | Every policy document as plain data, in a module with no provider |
| `main.tf` | The GitHub OIDC provider, the **Execution role**, its **Permission boundary**, the **Guardrail policy** and the payment-method lockout SCP |
| `tests/guardrails.tftest.hcl` | `terraform test` against a mocked AWS provider |

## How it fits together

- **No stored keys.** Only the `main` branch of one repository can assume the **Execution role**, through GitHub's OIDC issuer. The trust pins both the audience and the exact `repo:<owner>/<name>:ref:refs/heads/main` subject.
- **A cap it can't lift.** The **Permission boundary** limits the role to EC2, EKS, KMS and CloudWatch Logs in one region, plus creating workload roles under `role/workload/` that carry the same boundary.
- **Denies that win.** The **Guardrail policy** denies the role editing itself, its boundary or its own policies. The same denies sit inside the boundary, so detaching the policy would not lift them.
- **Beyond IAM.** An organization service control policy denies payment-method changes in every member account. SCPs never bind the management account, which keeps that power.

## How to read the tests

Three layers, all run by `make test-iac` with no credentials:

1. `tests/guardrails.tftest.hcl` checks the wiring in a mocked plan: the role carries the boundary, the guardrail is attached, the trust is pinned, the SCP is attached, and a wildcard repository is rejected.
2. `../policy_checks/check_policies.py` checks the policy JSON that `policies/` renders. Each property has an id: `role-has-boundary`, `role-cannot-edit-itself`, `no-wildcard-iam-writes` and `payment-methods-locked`.
3. `../policy_checks/tests/` runs that checker on the rendered JSON, then on copies loosened on purpose (a boundary removed, a deny dropped, `iam:*` granted). Each loosened copy must fail, which proves the check can catch the regression.

`make simulate-policies` goes one step further and asks the IAM policy simulator what it would decide for a matrix of calls. It needs AWS credentials, so CI runs it only when the repository sets `POLICY_SIMULATOR_ROLE_ARN`; otherwise it skips.
