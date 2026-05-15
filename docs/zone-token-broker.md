# Zone AuthService Token Helper

`zone-token` is a small notebook helper for calling the platform AuthService delegated token endpoint. It replaces user-written `curl` commands and avoids device-code authentication.

## CLI

```bash
zone-token get --scope https://storage.azure.com/.default
```

The command prints only the access token to stdout. Errors are written to stderr.

Default endpoint:

```text
http://authservice.kubeflow.svc.cluster.local:8080/authservice/getToken
```

Override values when needed:

```bash
export ZONE_TOKEN_BROKER_URL=https://broker.example/authservice
export ZONE_TOKEN_BROKER_TOKEN_PATH=/getToken
```

## Python

```python
import zonetokenbroker

token = zonetokenbroker.get_access_token("https://storage.azure.com/.default")
```

For Azure SDK clients, use `zonetokenbroker.BrokerCredential`.

## R

```r
library(zonetokenbroker)

token <- zone_get_token("https://storage.azure.com/.default")
```

## Notes

- The helper does not persist tokens.
- The `scope` argument is required.
- OneLake DFS access uses `https://storage.azure.com/.default`.
- Fabric REST API calls use Fabric scopes such as `https://api.fabric.microsoft.com/.default`.
- If AuthService returns `AADSTS65001` or `consent_required`, the code path is wired but the app registration still needs consent for that downstream resource.
