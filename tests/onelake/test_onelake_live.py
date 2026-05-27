import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "images" / "onelake" / "onelake_cli.py"


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("ONELAKE_LIVE_TEST") != "1", reason="set ONELAKE_LIVE_TEST=1 to run against OneLake"),
]


def _run(args, input_bytes=None):
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'images' / 'onelake'}{os.pathsep}{env.get('PYTHONPATH', '')}"
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        input=input_bytes,
        capture_output=True,
        check=True,
        env=env,
    )


def test_live_cli_token_read_write_roundtrip(tmp_path):
    missing = [name for name in ("ONELAKE_WORKSPACE", "ONELAKE_LAKEHOUSE") if not os.getenv(name)]
    if missing:
        pytest.skip(f"missing live OneLake config: {', '.join(missing)}")

    remote = os.getenv("ONELAKE_LIVE_TEST_PATH", "Files/onelake-smoke.txt")
    uploaded = os.getenv("ONELAKE_LIVE_UPLOAD_PATH", "Files/onelake-smoke-upload.txt")
    payload = b"onelake live smoke\n"

    _run(["status", "--live"])
    _run(["ls", "/"])
    _run(["write", remote], input_bytes=payload)
    assert _run(["cat", remote]).stdout == payload

    local = tmp_path / "download.txt"
    _run(["get", remote, str(local)])
    assert local.read_bytes() == payload

    upload = tmp_path / "upload.txt"
    upload.write_bytes(b"onelake upload smoke\n")
    _run(["put", str(upload), uploaded])
    assert _run(["cat", uploaded]).stdout == b"onelake upload smoke\n"
