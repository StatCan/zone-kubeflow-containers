# Zone managed-identity login (zone-msi-shim)

*Engineering and security notes for browserless Azure sign-in in Zone
notebook pods. User-facing doc: [`images/mid/azure-sign-in.md`](../images/mid/azure-sign-in.md).
Broker client code: [`images/mid/zone-token-broker/`](../images/mid/zone-token-broker/).*

## Summary

Zone notebook pods obtain **user-delegated** Azure access tokens with no
browser and no device code. The user's real Entra sign-in already happened
in their desktop browser when they logged into zone.statcan.ca (Kubeflow
AuthService / OIDC). StatCan's AuthService fork exposes
`getPassthroughToken?scope=X` in-cluster, which performs an Entra
**on-behalf-of (OBO)** exchange and returns a delegated access token for the
pod's user — this is the existing `zone-token-broker` package.

New in this change: a localhost shim (**zone-msi-shim**, `127.0.0.1:8901`)
speaks the Azure App Service managed-identity protocol and translates
managed-identity token requests (`resource=X`) into broker calls
(`scope=X/.default`). The result:

- `az login --identity` just works.
- Python `DefaultAzureCredential` / `ManagedIdentityCredential` just work.
- R keeps using the native broker client (`zonetokenbroker::zone_get_token`)
  because R AzureAuth's managed-identity path pins the IMDS IP
  (`169.254.169.254`) and ignores `IDENTITY_ENDPOINT` (see below).

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

The pod never contacts `login.microsoftonline.com`, GC SSO, or any
Microsoft CDN. The only Entra traffic is server-side, from AuthService,
which already has that connectivity for the OIDC login flow.

## Protocol details

The shim implements the App Service managed-identity protocol
(api-version `2019-08-01`), which `az`, `azure-identity`, and other MSAL
based SDKs automatically prefer when both environment variables are set:

```
IDENTITY_ENDPOINT=http://127.0.0.1:8901/msi/token
IDENTITY_HEADER=<per-pod random secret>
```

Request (what the SDKs send):

```
GET /msi/token?api-version=2019-08-01&resource=https://storage.azure.com
X-IDENTITY-HEADER: <value of $IDENTITY_HEADER>
```

Response (App Service shape; `expires_on` is epoch seconds, as a string,
matching the 2019-08-01 contract):

```json
{
  "access_token": "eyJ...",
  "expires_on": "1767200000",
  "resource": "https://storage.azure.com",
  "token_type": "Bearer"
}
```

Behavior:

- **resource → scope mapping.** The managed-identity protocol is
  resource-based (Entra v1 style); the broker is scope-based (v2). The shim
  maps `resource=X` to `scope=X/.default`, normalizing any trailing slash
  on the resource first.
- **Backing call.** Each request becomes a broker call to
  `http://authservice.kubeflow.svc.cluster.local:8080/authservice/getPassthroughToken?scope=X/.default`
  (same endpoint and env overrides — `AUTHSERVICE_BROKER_URL`,
  `AUTHSERVICE_BROKER_TOKEN_PATH` — as the existing Python/R clients).
  The broker's JSON (`access_token`, `expires_on` epoch seconds) maps
  directly onto the MSI response.
- **Requests without the correct `X-IDENTITY-HEADER` are rejected**,
  matching App Service semantics.
- **Single identity.** Real MSI endpoints accept `client_id`/`object_id`/
  `mi_res_id` to select among user-assigned identities. There is exactly
  one identity here — the signed-in Zone user — so these selectors are
  accepted and ignored.
- **Errors** are returned in the MSI error shape so SDK retry/failure
  behavior is sensible; broker error detail (e.g. AADSTS codes from a
  failed OBO) is passed through for diagnosability.

### Why R is different

R `AzureAuth`'s managed-identity code path hardcodes the IMDS address
(`169.254.169.254`) rather than honoring `IDENTITY_ENDPOINT`, so it cannot
reach a loopback shim. R users therefore call the native broker client
directly — `zonetokenbroker::zone_get_token(scope)` — which mirrors the
Python module (same endpoint, env overrides, 30 s timeout, and per-scope
in-memory caching with a 5-minute expiry buffer).

## Trust boundaries and threat notes

- **Loopback only.** The shim binds `127.0.0.1`; it is not reachable from
  other pods, and there is no new Service, port, ingress, or NetworkPolicy.
  `IDENTITY_HEADER` is a per-pod random secret, so even a same-node
  process outside the pod's network namespace cannot forge requests.
- **No credentials in the shim.** The shim is a pure protocol translator.
  It holds no client secret, no refresh token, nothing to exfiltrate. All
  credential material stays server-side in AuthService.
- **Broker trust model unchanged.** AuthService identifies the caller by
  source pod IP, maps it to the owning namespace, and uses that user's
  stored OIDC session for the OBO exchange. The shim adds no new principal
  and no new path to anyone else's tokens. As with the broker today, **any
  process running in the user's pod (or namespace) can obtain that user's
  delegated tokens** — the pod is inside the user's trust boundary.
- **Token audience limits.** Every token is audience-bound to the single
  requested resource and carries only that resource's delegated
  permissions; the shim cannot mint anything the broker could not already
  mint.
- **ARM consent widens scope — flag for Cybersecurity.** Consenting the
  Azure Service Management permission (below) extends delegated access
  from data-plane services (Storage, Cognitive Services — already proven)
  to the **control plane**: an ARM token lets a pod process enumerate and
  manage whatever Azure resources the *user's own RBAC roles* allow. The
  blast radius stays bounded by the user's RBAC, but it is a real widening
  and should be assessed as such.
- **No new egress.** Unlike browser-based flows, nothing in the pod
  connects to Microsoft sign-in infrastructure.

## Tenant prerequisite (platform team)

Before `az login --identity` can work, the **Zone AuthService app
registration** needs the delegated permission
**Azure Service Management → `user_impersonation`** added and
**admin-consented** in the tenant. Without it, the OBO exchange for an ARM
audience fails with a consent-required error (AADSTS65001) and `az login`
cannot obtain its ARM token. Storage and Cognitive Services scopes are
already consented and proven end-to-end; ARM is the only net-new consent
this feature requires. The same process applies to any future scope users
request: one-time delegated consent on the AuthService app registration.

## Limits

- **User-delegated only.** No app-only tokens, no service principals — a
  token is always minted *as the signed-in user* with that user's
  permissions.
- **Bounded by the Zone session (~24 h).** When the AuthService session
  expires, token requests fail until the user signs in to zone.statcan.ca
  again in their desktop browser. No re-login inside the pod is possible
  or needed.
- **Single tenant.** Only the StatCan tenant; no guest/multi-tenant use.
- **No Conditional Access step-up.** If a resource requires an
  authentication step-up (e.g. a fresh-MFA claims challenge) beyond what
  the original zone.statcan.ca sign-in satisfied, the OBO exchange cannot
  provide it.
- **Pod-level trust.** Any process in the user's pod/namespace can obtain
  the user's tokens — identical to the existing broker trust model.

## History and rationale

Device-code authentication is being retired because the grant is phishable
(an attacker-initiated flow can be completed by a victim entering a code in
their own trusted browser). An in-pod browser was prototyped as the
replacement (PR #281): a headless Chromium in the pod runs the standard
interactive authorization-code flow, streamed into a JupyterLab tab. It
worked end-to-end in the test harness, but the sign-in pages depend on
egress to GC SSO (`sso1.gcsso.gc.ca`) and Microsoft's sign-in CDNs, which
pod egress does not reliably allow. The managed-identity shim needs **no
new egress at all**, because the token exchange happens server-side in
AuthService — the pod only ever talks to loopback and to the in-cluster
AuthService endpoint the broker already used.
