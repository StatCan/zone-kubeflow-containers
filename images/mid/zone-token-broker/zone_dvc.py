"""Run DVC Azure commands with Zone AuthService delegated credentials."""

import sys

STORAGE_SCOPE = "https://storage.azure.com/.default"
MISSING_DVC_DEPENDENCIES_MESSAGE = (
    "zone-dvc requires DVC Azure dependencies. Install zone-token-broker[zone-dvc] "
    "or use the Zone mid image that includes the zone-dvc extra."
)


def _patch_dvc_azure():
    import dvc_azure
    import zone_token_broker

    prepare_credentials = dvc_azure.AzureFileSystem._prepare_credentials
    if getattr(prepare_credentials, "_zone_token_broker_patched", False):
        return

    def prepare_credentials_with_zone_broker(self, **config):
        login_info = prepare_credentials(self, **config)
        explicit_credentials = (
            "connection_string",
            "account_key",
            "sas_token",
            "tenant_id",
            "client_id",
            "client_secret",
        )
        if login_info.get("credential") is not None and not any(login_info.get(name) for name in explicit_credentials):
            login_info["credential"] = zone_token_broker.async_credential(STORAGE_SCOPE)
        return login_info

    prepare_credentials_with_zone_broker._zone_token_broker_patched = True
    dvc_azure.AzureFileSystem._prepare_credentials = prepare_credentials_with_zone_broker


def main(argv=None):
    try:
        _patch_dvc_azure()
        from dvc.cli import main as dvc_main
    except ModuleNotFoundError as error:
        if error.name in {"dvc", "dvc_azure"}:
            print(MISSING_DVC_DEPENDENCIES_MESSAGE, file=sys.stderr)
            return 2
        raise

    return dvc_main(sys.argv[1:] if argv is None else argv)
