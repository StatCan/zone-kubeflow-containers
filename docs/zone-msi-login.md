# Azure sign-in: technical reference (zone-msi-shim)

<!-- prettier-ignore -->
!!! info
    This page covers the architecture, protocol and security model. For the
    non-technical guide, see the user-facing doc: [`images/mid/azure-sign-in.md`](../images/mid/azure-sign-in.md).
Broker client code: [`images/mid/zone-token-broker/`](../images/mid/zone-token-broker/).*

## Summary

Zone notebook pods obtain **user-delegated** Azure access tokens with no
browser and no device code. The user's real Entra ID sign-in (credentials,
MFA, GC SSO) already happened in their desktop browser when they logged in to
zone.statcan.ca via Kubeflow AuthService (OIDC). StatCan's AuthService fork
exposes an in-cluster endpoint, `getPassthroughToken?scope=X`, which performs
an Entra **on-behalf-of (OBO)** exchange against that stored session and
returns a delegated access token minted _as the pod's user_. This endpoint - along with the Zone Token Broker provided on notebook images - was already in production for Storage workflows (`zone-dvc`) through the `zone-token-broker` Python and R client packages.

The new piece is a loopback shim, **zone-msi-shim** (`127.0.0.1:8901`), that
speaks the **Azure App Service managed-identity protocol** and translates
managed-identity token requests (`resource=X`) into broker calls
(`scope=X/.default`). Because MSAL and `azure-identity` auto-detect a
managed-identity endpoint through the `IDENTITY_ENDPOINT` / `IDENTITY_HEADER`
environment variables, the result requires **zero client configuration**:

- `az login --identity` works — no browser, no device code, no new egress.
- Python `DefaultAzureCredential()` / `ManagedIdentityCredential()` work out
  of the box.
- R keeps using the native broker client
  (`zonetokenbroker::zone_get_token`), because R `AzureAuth`'s
  managed-identity path pins the IMDS IP and ignores `IDENTITY_ENDPOINT`
  (details below).

Per-user isolation holds by construction: caller pod IP → owning namespace →
that user's AuthService session → OBO token. Concurrent users are isolated by
namespace — the same trust model as the existing broker.

## Background: why this design

**Device-code retirement.** Device-code authentication is being retired by
Cybersecurity because the grant is phishable: an attacker-initiated flow can
be completed by a victim who types the code into their own trusted browser,
approving the attacker's session.

**Why not an in-pod browser.** An in-pod browser was prototyped as the
replacement (headless Chromium running the standard interactive
authorization-code flow, streamed into a JupyterLab tab). It worked
end-to-end in the test harness, but the Entra sign-in pages depend on egress
to GC SSO (`sso1.gcsso.gc.ca`) and Microsoft sign-in CDNs that notebook-pod
egress does not reliably allow — navigations died before commit.

**The shim needs no new egress to external services.** The token exchange happens
server-side in AuthService, which already has Entra connectivity for the OIDC
login flow. The pod only ever talks to loopback and to the in-cluster
AuthService endpoint the broker already used.

## Architecture

```
Desktop                          Zone cluster                          Entra ID
───────                          ────────────                         ─────────
User's browser ──── OIDC ──► zone.statcan.ca ingress
  (real Entra sign-in,             │
   MFA, GC SSO)                    ▼
                          AuthService (StatCan fork)
                            │  holds user's OIDC session
                            │
   User's notebook pod      │
  ┌────────────────────────┐│
  │ az / azure-identity /  ││
  │ any MSI-aware SDK      ││
  │      │ MSI protocol    ││
  │      │ (App Service,   ││
  │      │  2019-08-01)    ││
  │      ▼                 ││
  │ zone-msi-shim          ││
  │ (127.0.0.1:8901) ──────┼┼──► getPassthroughToken?scope=X
  │                        ││    (caller pod IP → namespace →
  │ R: zonetokenbroker ────┼┘     namespace owner's session)
  └────────────────────────┘            │
                                        │ on-behalf-of exchange
                                        ▼
                              Entra token endpoint ──► delegated access
                                                       token, minted as
                                                       the user
```

The notebook pod never contacts `login.microsoftonline.com`, GC SSO, or any Microsoft
CDN. The only Entra traffic is server-side, from AuthService.

### Components

| Component                    | Where                              | Role                                                                                                                        |
| ---------------------------- | ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| AuthService (StatCan fork)   | zone authservice image                         | Holds the user's OIDC session; performs the OBO exchange; exposes `getPassthroughToken`                                      |
| `zone-token-broker` (Python) | notebook image                     | Broker client: per-scope in-memory caching (5-min expiry buffer), sync + async `TokenCredential` implementations             |
| `zonetokenbroker` (R)        | notebook image                     | Mirror of the Python client (same endpoint, env overrides, 30 s timeout, caching)                                            |
| `zone-msi-shim`              | notebook image, s6 service `zone-msi` | Stdlib-only loopback HTTP server translating the MSI protocol to broker calls; started at pod boot                        |

## Protocol details

The shim implements the App Service managed-identity protocol (api-version
`2019-08-01`), which `az`, `azure-identity`, and other MSAL-based SDKs
automatically prefer when both environment variables are set (they are set in
the notebook image):

```
IDENTITY_ENDPOINT=http://127.0.0.1:8901/msi/token
IDENTITY_HEADER=<per-pod random secret>
```

Request (what the SDKs send):

```
GET /msi/token?api-version=2019-08-01&resource=https://storage.azure.com
X-IDENTITY-HEADER: <value of $IDENTITY_HEADER>
```

Response (App Service shape; `expires_on` is epoch seconds **as a string**,
matching the 2019-08-01 contract — both MSAL and azure-identity call `int()`
on it):

```json
{
  "access_token": "eyJ...",
  "expires_on": "1767200000",
  "resource": "https://storage.azure.com",
  "token_type": "Bearer"
}
```

Behavior:

- **Resource → scope mapping.** The managed-identity protocol is
  resource-based (Entra v1 style); the broker is scope-based (v2). The shim
  maps `resource=X` to `scope=X/.default`, normalizing any trailing slash on
  the resource first.
- **Backing call.** Each request becomes a broker call to
  `http://authservice.kubeflow.svc.cluster.local:8080/authservice/getPassthroughToken?scope=X/.default`
  — the same endpoint and environment overrides (`AUTHSERVICE_BROKER_URL`,
  `AUTHSERVICE_BROKER_TOKEN_PATH`) as the existing Python/R clients. The
  broker's JSON (`access_token`, `expires_on` epoch seconds) maps directly
  onto the MSI response. Broker-side caching means repeated SDK calls for the
  same scope are served from memory.
- **Header check.** Requests without the correct `X-IDENTITY-HEADER` are
  rejected with 401, matching App Service semantics. A missing `resource`
  parameter returns 400.
- **Single identity.** Real MSI endpoints accept `client_id` / `object_id` /
  `mi_res_id` to select among user-assigned identities. There is exactly one
  identity here — the signed-in Zone user — so these selectors are accepted
  and ignored.
- **Errors** are returned in the MSI error shape (`error`,
  `error_description`) so SDK retry/fall-through behavior stays sensible; a
  broker failure returns `broker_error` with redacted detail (e.g. AADSTS
  codes from a failed OBO) passed through for diagnosability. Token-shaped
  strings are redacted from all error text and logs; the shim never logs query
  strings verbatim.

### Why R is different

R `AzureAuth`'s managed-identity code path hardcodes the IMDS address
(`169.254.169.254`) rather than honoring `IDENTITY_ENDPOINT`, so it cannot
reach a loopback shim. R users therefore call the native broker client
directly — `zonetokenbroker::zone_get_token(scope)` — which mirrors the Python
module.

## Trust boundaries and threat notes

- **Loopback only.** The shim binds `127.0.0.1`; it is not reachable from
  other pods, and there is no new Service, port, ingress, or NetworkPolicy.
  `IDENTITY_HEADER` is a per-pod random secret, so even a same-node process
  outside the pod's network namespace cannot forge requests.
- **No credentials in the shim.** The shim is a pure protocol translator. It
  holds no client secret, no refresh token — nothing to exfiltrate. All
  credential material stays server-side in AuthService.
- **Broker trust model unchanged.** AuthService identifies the caller by
  source pod IP, maps it to the owning namespace, and uses that user's stored
  OIDC session for the OBO exchange. The shim adds no new principal and no new
  path to anyone else's tokens. As with the broker today, **any process
  running in the user's pod (or namespace) can obtain that user's delegated
  tokens** — the pod is inside the user's trust boundary.
- **Token audience limits.** Every token is audience-bound to the single
  requested resource and carries only that resource's delegated permissions;
  the shim cannot mint anything the broker could not already mint.
- **Azure Resource Management(ARM) consent widens scope.** Consenting the Azure Service Management
  permission (below) extends delegated access from data-plane services
  (Storage, Cognitive Services — already consented and proven) to the
  **control plane**: an ARM token lets a pod process enumerate and manage
  whatever Azure resources the _user's own RBAC roles_ allow. The blast radius
  stays bounded by the user's RBAC, but it is a real widening and is assessed
  as such with Cybersecurity.
- **No new egress.** Unlike browser-based flows, nothing in the pod connects
  to Microsoft sign-in infrastructure.
- **Phishing surface removed.** The retired device-code grant was phishable;
  the interactive flows are gone from the pod entirely. The only interactive
  sign-in is the standard zone.statcan.ca OIDC login in the user's own desktop
  browser.

## Tenant prerequisite (platform team)

Before `az login --identity` can work, the **Zone AuthService app
registration** needs the delegated permission **Azure Service Management →
`user_impersonation`** added and **admin-consented** in the tenant. Without
it, the OBO exchange for an ARM audience fails with AADSTS65001 (consent
required) and `az login` cannot obtain its ARM token. Storage and Cognitive
Services scopes are already consented and proven end-to-end; ARM is the only
net-new consent this feature requires. The same process applies to any future
scope users request: a one-time delegated consent on the AuthService app
registration.

## Limits

- **User-delegated only.** No app-only tokens, no service principals — a token
  is always minted _as the signed-in user_, with that user's permissions.
- **Bounded by the Zone session (~24 h).** When the AuthService session
  expires, token requests fail until the user signs in to zone.statcan.ca
  again in their desktop browser. No re-login inside the pod is possible or
  needed.
- **Single tenant.** Only the StatCan tenant; no guest/multi-tenant use.
- **No Conditional Access step-up.** If a resource requires an authentication
  step-up (e.g. a fresh-MFA claims challenge) beyond what the original
  zone.statcan.ca sign-in satisfied, the OBO exchange cannot provide it.
- **Pod-level trust.** Any process in the user's pod/namespace can obtain the
  user's tokens — identical to the existing broker trust model.

## Source layout (zone-kubeflow-containers)

| Path                                                | Contents                                                        |
| --------------------------------------------------- | --------------------------------------------------------------- |
| `images/mid/zone-token-broker/zone_msi_shim.py`     | Stdlib-only loopback MSI server                                 |
| `images/mid/zone-token-broker/zone_token_broker.py` | Broker client (sync/async credentials, caching, redaction)      |
| `images/mid/zone-token-broker/zone-token-broker-r/` | R client package                                                |
| `images/mid/s6/services.d/zone-msi/run`             | s6 service starting the shim at pod boot                        |
| `images/mid/azure-sign-in.md`                       | User guide seeded to `$HOME`                                    |
| `docs/zone-msi-login.md`                            | In-repo engineering/security notes                              |
| `tests/mid/test_zone_msi.py`                        | In-image protocol test against a mock broker                    |

## Validation

Container harness: protocol responses verified (200 token shape / 401 on
header mismatch / 400 on missing resource); a real `az login --identity`
auto-detected the shim, fetched and parsed the brokered token, and proceeded
to ARM. The final leg (a genuine OBO token) requires the in-cluster
AuthService plus the ARM consent above — that is the cluster acceptance test.