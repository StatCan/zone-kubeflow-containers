import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_r_wrapper_invokes_zone_token_cli(tmp_path):
    if os.name == "nt" or shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available for the R wrapper smoke test")

    mock = tmp_path / "zone-token"
    mock.write_text("#!/usr/bin/env sh\nprintf 'r-token\\n'\n", encoding="utf-8")
    mock.chmod(0o755)
    wrapper = ROOT / "images" / "zone_token" / "zonetokenbroker-r" / "R" / "zonetokenbroker.R"

    command = (
        f"Sys.setenv(ZONE_TOKEN_COMMAND='{mock.as_posix()}'); "
        f"source('{wrapper.as_posix()}'); "
        "cat(zone_get_token('scope-a'))"
    )
    result = subprocess.run(["Rscript", "-e", command], capture_output=True, text=True, check=True)

    assert result.stdout == "r-token"
