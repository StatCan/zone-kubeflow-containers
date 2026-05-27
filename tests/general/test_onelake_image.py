import os

import pytest


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("IMAGE_NAME"), reason="requires a built notebook image")
def test_onelake_helpers_are_installed_in_image(container):
    image_name = container.image_name.lower()
    if "/base:" in image_name or image_name.endswith("/base") or "base:" in image_name.split("/")[-1]:
        pytest.skip("Base image does not include the OneLake utility layer")

    running_container = container.run(
        tty=True,
        command=["start.sh", "bash", "-c", "sleep infinity"],
    )

    checks = [
        "command -v onelake && onelake --help >/tmp/onelake-help",
        "python -c \"import onelake, zone_token_broker; print(onelake.status()['endpoint'])\"",
        "Rscript -e \"library(onelake); stopifnot(exists('ol_ls')); cat('ok')\"",
    ]
    for command in checks:
        result = running_container.exec_run(["bash", "-lc", command])
        output = result.output.decode("utf-8", errors="replace")
        assert result.exit_code == 0, f"Command failed: {command}\n{output}"
