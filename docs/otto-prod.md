# otto — production runbook

*How to take the agent from the pilot (one demo Azure OpenAI deployment,
env vars set by hand) to production on the Zone. Code:
[`images/otto/`](../images/otto/); platform stubs:
[`images/otto/deploy/`](../images/otto/deploy/).*

Where this document cannot see StatCan internals it says **ASSUMPTION** —
each one is a checkbox for the platform team, not a hidden dependency.

## The shape of production

```
notebook pod (otto image)
  otto CLI
    │  reads /etc/otto/config.toml   ← ConfigMap via PodDefault (platform catalogue)
    │  reads ~/.otto/config.toml     ← user overrides (home PV)
    │  reads env                           ← Secret via PodDefault (api-key teams only)
    ├─ auth = broker ──► AuthService (in-cluster) ──► delegated per-user Entra token
    └─ HTTPS ──► Azure OpenAI / AI Foundry endpoint
                 (*.openai.azure.com / *.services.ai.azure.com)
```

Configuration is layered (platform file → user file → env → flags), so the
platform team owns the model catalogue centrally while users keep full
local override for experiments. Nothing about the pilot's env-var flow
breaks: `AZURE_OPENAI_ENDPOINT` + `OTTO_DEPLOYMENT` still work with
no files present.

## What the platform team provisions

1. **The Azure resource** — either a classic Azure OpenAI resource or an
   Azure AI Foundry project/AI Services resource, in a StatCan-controlled
   subscription. **ASSUMPTION:** cloud resources go through the standard
   SSC/cloud-brokering intake; nothing here requires a new pattern —
   Fabric/OneLake access already established the Zone→Azure path.
2. **Model deployments** on that resource (`gpt-5-mini` etc. — for
   Foundry catalogue models, deployments must support tool calling).
3. **Access, choose per resource:**
   - *Broker (preferred):* grant the "Cognitive Services OpenAI User" role
     to a user **group** on the resource. Calls run as the individual user
     via AuthService delegated tokens — per-user attribution in Azure
     logs, no secrets anywhere, nothing to rotate.
     **ASSUMPTION:** AuthService can mint delegated tokens for the
     `https://cognitiveservices.azure.com/.default` scope (it already does
     so for storage). Validate with `otto --doctor` from an
     in-cluster notebook; if the scope needs enabling, it is an
     AuthService/Entra app-registration change, not an image change.
   - *API key (fallback):* store the resource key in the enterprise secret
     store, deliver it as a Secret (`deploy/secret-api-key.yaml.example`).
     One identity per team, rotate on schedule.
4. **Distribution** — apply `deploy/configmap-otto.yaml.example`
   (the catalogue) and `deploy/poddefault-otto.yaml.example` (mounts
   it at `/etc/otto`) to user namespaces, via the same mechanism
   that distributes filer PodDefaults today.
5. **Networking** — pods must reach the resource endpoint on 443.
   **ASSUMPTION:** either the endpoint has a private endpoint reachable
   from the cluster VNet, or inspected egress allows
   `*.openai.azure.com` / `*.services.ai.azure.com`. TLS inspection is
   fine: otto wires the image's `REQUESTS_CA_BUNDLE` (which carries
   the StatCan CAs) into its HTTP client.

## Day-2 operations

- **`otto --doctor`** is the support tool: it prints the resolved
  profile (model, provider, endpoint, deployment, auth source, which
  config layer supplied it), acquires a token or checks the key env var,
  and makes one real model call. Exit code 0 = a user's pod can use the
  model. Ask for its output in every support ticket.
- **`otto --list-models`** shows the catalogue a pod actually
  received — the fastest way to spot a namespace missing the PodDefault.
- **Changing models** = editing the ConfigMap. No image rebuild, no user
  action; new sessions pick it up immediately.
- **Cost/quota:** with broker auth every request carries the user's
  identity, so Azure OpenAI usage logs attribute spend per user. Set
  deployment-level rate limits (TPM) in Azure as the backstop.

## Security posture (summary for review)

- No secrets in images, git, or home directories. Broker mode has no
  secrets at all; key mode holds the key only in a namespaced Secret.
- Requests are user-attributable (delegated tokens), satisfying the same
  auditability stance as the broker's storage flows.
- The agent's mutating tools (write/edit/bash) require interactive [y/N]
  approval unless the user passes `-y`; model access adds no new
  privilege — it can only do what the user's identity can already do.
- Opt-in rollout: the agent ships in its own notebook image
  (`otto`), so only users who select that flavour get the CLI, and
  the pilot can be scoped to named namespaces via the PodDefault.

## Rollout checklist

- [ ] Resource + deployments provisioned (SSC intake)
- [ ] RBAC group granted (broker) and/or key in secret store (api-key)
- [ ] AuthService issues cognitiveservices-scope tokens (validate with
      `--doctor` in-cluster)
- [ ] Egress/private endpoint confirmed from a notebook pod
- [ ] ConfigMap + PodDefault applied to pilot namespaces
- [ ] `otto --doctor` clean from a pilot user's notebook
- [ ] Pilot feedback → widen namespaces → fold image into default catalogue
