# Triage labels

| Label             | Meaning                                    |
| ----------------- | ------------------------------------------ |
| `needs-triage`    | The maintainer still needs to evaluate it  |
| `needs-info`      | Waiting on the reporter for more detail    |
| `ready-for-agent` | Fully specified, ready for an agent to do  |
| `ready-for-human` | Needs a human to do it                     |
| `wontfix`         | Will not be actioned                       |

`scripts/create-labels.sh` creates or updates these labels with `gh label create --force`. It is safe to run more than once.
