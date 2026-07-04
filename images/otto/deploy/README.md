# otto platform stubs

Everything the platform team applies to move otto from pilot to
production — fill in the `CHANGE-ME`s and go. The full runbook, including
the flagged assumptions to validate, is
[`docs/otto-prod.md`](../../../docs/otto-prod.md).

| File | What it is |
|---|---|
| `config-platform.toml.example` | The model catalogue (`/etc/otto/config.toml`): profiles for Azure OpenAI, AI Foundry, Foundry catalogue models, broker or api-key auth |
| `configmap-otto.yaml.example` | The catalogue wrapped as a ConfigMap per user namespace |
| `poddefault-otto.yaml.example` | Opt-in PodDefault mounting the catalogue (and optionally the key Secret) into notebook pods |
| `secret-api-key.yaml.example` | Key delivery for `auth = "api-key"` profiles (broker profiles need no secret at all) |

Users then run `otto --list-models`, pick with `--model`, and debug
with `otto --doctor`.
