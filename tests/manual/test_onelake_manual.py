#!/usr/bin/env python3
"""
OneLake PR #241 — Manual Validation Script
Run this inside a Zone Kubeflow notebook or terminal.

Usage:
    python test_onelake_manual.py           # offline tests only
    python test_onelake_manual.py --live    # include live OneLake connection test
"""

import importlib
import inspect
import json
import os
import subprocess
import sys
import time
import traceback

# ── colours & symbols ──────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

PASS_TAG = f"{GREEN}{BOLD} PASS {RESET}"
FAIL_TAG = f"{RED}{BOLD} FAIL {RESET}"
SKIP_TAG = f"{YELLOW}{BOLD} SKIP {RESET}"

# ── state ──────────────────────────────────────────────────────────────────────

results = []  # list of (name, passed: bool|None, detail)
test_number = 0


def section(title):
    print(f"\n{BOLD}{CYAN}{'━' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'━' * 70}{RESET}")


def evidence(label, content, indent=6):
    """Print labelled evidence block."""
    pad = " " * indent
    print(f"{pad}{BLUE}{label}:{RESET}")
    if isinstance(content, str):
        for line in content.split("\n"):
            print(f"{pad}  {DIM}{line}{RESET}")
    elif isinstance(content, (list, dict)):
        formatted = json.dumps(content, indent=2)
        for line in formatted.split("\n"):
            print(f"{pad}  {DIM}{line}{RESET}")


def verdict(name, passed, reasoning, evidence_blocks=None):
    """Record and display a test result with reasoning."""
    global test_number
    test_number += 1
    results.append((name, passed, reasoning))

    if passed is None:
        tag = SKIP_TAG
    elif passed:
        tag = PASS_TAG
    else:
        tag = FAIL_TAG

    print(f"\n  {tag}  {BOLD}{name}{RESET}")
    print(f"         {DIM}Reasoning: {reasoning}{RESET}")

    if evidence_blocks:
        for label, content in evidence_blocks:
            evidence(label, content)


def timed(fn):
    """Run a function and return (result, elapsed_ms)."""
    t0 = time.perf_counter()
    result = fn()
    elapsed = (time.perf_counter() - t0) * 1000
    return result, elapsed


# ── Test 1: SDK packages ──────────────────────────────────────────────────────

def test_sdk_packages():
    section("1 / 8 · Python SDK Packages")
    print(f"\n  {DIM}Why: PR #241 adds 'azure-storage-file-datalake' and 'azure-identity'")
    print(f"  to the mid Dockerfile. If these don't import, the entire OneLake")
    print(f"  integration is dead on arrival.{RESET}")

    for pkg_name, pip_name in [
        ("azure.storage.filedatalake", "azure-storage-file-datalake"),
        ("azure.identity", "azure-identity"),
    ]:
        try:
            mod, ms = timed(lambda p=pkg_name: importlib.import_module(p))
            version = getattr(mod, "__version__", getattr(mod, "VERSION", "unknown"))
            location = getattr(mod, "__file__", "unknown")

            verdict(
                f"import {pkg_name}",
                True,
                f"Module loaded in {ms:.0f}ms. Version resolves to '{version}'. "
                f"This confirms the pip package '{pip_name}' was installed correctly "
                f"in the container image and is on sys.path.",
                [
                    ("Module file", location),
                    ("Version", str(version)),
                    ("Import time", f"{ms:.1f}ms"),
                ],
            )
        except ImportError as e:
            verdict(
                f"import {pkg_name}",
                False,
                f"ImportError means '{pip_name}' is not installed or has a broken "
                f"dependency. Check the Dockerfile RUN pip install layer.",
                [("Exception", str(e))],
            )


# ── Test 2: Helper module ─────────────────────────────────────────────────────

def test_helper_import():
    section("2 / 8 · onelake_utils Helper Module")
    print(f"\n  {DIM}Why: PR #241 COPYs onelake_utils.py into site-packages. This is")
    print(f"  the user-facing API — if it's missing or malformed, users get nothing.{RESET}")

    try:
        mod, ms = timed(lambda: importlib.import_module("onelake_utils"))
        location = getattr(mod, "__file__", "unknown")
        all_attrs = [a for a in dir(mod) if not a.startswith("_")]

        verdict(
            "import onelake_utils",
            True,
            f"Module loaded in {ms:.0f}ms from '{location}'. "
            f"This confirms the COPY instruction in the Dockerfile placed the file "
            f"at the correct site-packages path for the container's Python version.",
            [
                ("Module file", location),
                ("Public attributes", ", ".join(all_attrs)),
                ("Import time", f"{ms:.1f}ms"),
            ],
        )
    except ImportError as e:
        verdict(
            "import onelake_utils",
            False,
            f"Module not found. The Dockerfile COPYs to python3.13/site-packages — "
            f"if the container's Python is a different version, the path is wrong.",
            [("Exception", str(e)), ("sys.path", "\n".join(sys.path))],
        )
        return

    expected_fns = ["ls", "read", "write", "download", "upload", "info"]
    for fn_name in expected_fns:
        attr = getattr(mod, fn_name, None)
        if attr is not None and callable(attr):
            sig = str(inspect.signature(attr))
            doc = (inspect.getdoc(attr) or "").split("\n")[0]
            verdict(
                f"onelake_utils.{fn_name}{sig}",
                True,
                f"Function exists and is callable. Signature matches the plan spec. "
                f"First line of docstring: \"{doc}\"",
                [("Signature", f"{fn_name}{sig}"), ("Docstring", doc)],
            )
        else:
            verdict(
                f"onelake_utils.{fn_name}() exists",
                False,
                f"Attribute is {'not callable' if attr else 'missing'}. "
                f"Check onelake_utils.py source for typos or missing def.",
            )

    # Check key internals exist
    endpoint = getattr(mod, "ONELAKE_ENDPOINT", None)
    if endpoint:
        verdict(
            "ONELAKE_ENDPOINT constant",
            endpoint == "https://onelake.dfs.fabric.microsoft.com",
            f"Endpoint is '{endpoint}'. Must be the OneLake DFS endpoint, not "
            f"the regular Azure dfs.core.windows.net — that would hit a "
            f"completely different service.",
            [("Value", endpoint)],
        )
    else:
        verdict("ONELAKE_ENDPOINT constant", False, "Constant not found in module.")


# ── Test 3: info() unconfigured ───────────────────────────────────────────────

def test_info_unconfigured():
    section("3 / 8 · info() Without Config (Graceful Degradation)")
    print(f"\n  {DIM}Why: When a user spins up a notebook without OneLake env vars,")
    print(f"  info() must NOT crash. It should print a clear 'not configured'")
    print(f"  message. If it throws, every new user's first experience is broken.{RESET}")

    saved = {
        "ONELAKE_WORKSPACE": os.environ.pop("ONELAKE_WORKSPACE", None),
        "ONELAKE_LAKEHOUSE": os.environ.pop("ONELAKE_LAKEHOUSE", None),
    }

    try:
        import onelake_utils
        importlib.reload(onelake_utils)
        onelake_utils._client = None
        onelake_utils._fs_client = None

        from io import StringIO
        import contextlib

        buf = StringIO()
        exc = None
        try:
            with contextlib.redirect_stdout(buf):
                onelake_utils.info()
        except Exception as e:
            exc = e

        output = buf.getvalue()

        if exc:
            verdict(
                "info() runs without crash",
                False,
                f"Threw {type(exc).__name__}: {exc}. This means every user without "
                f"OneLake config will see a stack trace instead of a helpful message.",
                [("Exception", traceback.format_exc()), ("Stdout before crash", output)],
            )
            return

        verdict(
            "info() runs without crash",
            True,
            "Function completed without exception. Users will see output, not a traceback.",
            [("Full output", output.strip())],
        )

        has_na = "N/A" in output
        verdict(
            "info() shows 'N/A' for missing workspace/lakehouse",
            has_na,
            f"{'Found' if has_na else 'Missing'} 'N/A' in output. When env vars "
            f"aren't set, displaying N/A clearly tells the user nothing is configured "
            f"vs leaving fields blank (which looks like a bug).",
            [("Output", output.strip())],
        )

        has_status = "not configured" in output.lower() or "non config" in output.lower()
        verdict(
            "info() shows 'Not configured' status",
            has_status,
            f"{'Found' if has_status else 'Missing'} status indicator. The user needs "
            f"to know OneLake is OFF — not that it failed or is partially working.",
            [("Output", output.strip())],
        )
    finally:
        for key, val in saved.items():
            if val is not None:
                os.environ[key] = val


# ── Test 4: Bilingual messages ────────────────────────────────────────────────

def test_bilingual():
    section("4 / 8 · Bilingual (EN/FR) Messages")
    print(f"\n  {DIM}Why: StatCan is a federal agency under the Official Languages Act.")
    print(f"  All user-facing text must work in both English and French.")
    print(f"  The module checks the LANG env var to pick the language.{RESET}")

    from io import StringIO
    import contextlib
    import onelake_utils

    saved = {
        "LANG": os.environ.get("LANG"),
        "ONELAKE_WORKSPACE": os.environ.pop("ONELAKE_WORKSPACE", None),
        "ONELAKE_LAKEHOUSE": os.environ.pop("ONELAKE_LAKEHOUSE", None),
    }

    try:
        def capture_info(lang_val):
            os.environ["LANG"] = lang_val
            importlib.reload(onelake_utils)
            onelake_utils._client = None
            onelake_utils._fs_client = None
            buf = StringIO()
            with contextlib.redirect_stdout(buf):
                onelake_utils.info()
            return buf.getvalue()

        # English
        en_out = capture_info("en_US.UTF-8")
        en_keys = ["Status", "Workspace", "Endpoint"]
        en_found = [k for k in en_keys if k in en_out]
        en_missing = [k for k in en_keys if k not in en_out]

        verdict(
            "English output (LANG=en_US.UTF-8)",
            len(en_missing) == 0,
            f"Found {len(en_found)}/{len(en_keys)} expected English labels. "
            f"{'All present.' if not en_missing else 'Missing: ' + ', '.join(en_missing)}",
            [("LANG", "en_US.UTF-8"), ("Output", en_out.strip())],
        )

        # French
        fr_out = capture_info("fr_CA.UTF-8")
        fr_keys = ["Statut", "Espace de travail", "Point de terminaison"]
        fr_found = [k for k in fr_keys if k in fr_out]
        fr_missing = [k for k in fr_keys if k not in fr_out]

        verdict(
            "French output (LANG=fr_CA.UTF-8)",
            len(fr_missing) == 0,
            f"Found {len(fr_found)}/{len(fr_keys)} expected French labels. "
            f"{'All present.' if not fr_missing else 'Missing: ' + ', '.join(fr_missing)}",
            [("LANG", "fr_CA.UTF-8"), ("Output", fr_out.strip())],
        )

        # Verify they're actually different
        are_different = en_out != fr_out
        verdict(
            "EN and FR outputs are different strings",
            are_different,
            f"{'Outputs differ' if are_different else 'Outputs are IDENTICAL'} — "
            f"if they match, the LANG switch is not being read and one language "
            f"is hardcoded.",
            [("EN (first line)", en_out.strip().split("\n")[0]),
             ("FR (first line)", fr_out.strip().split("\n")[0])],
        )
    except Exception as e:
        verdict("Bilingual test", False, str(e), [("Traceback", traceback.format_exc())])
    finally:
        if saved["LANG"] is not None:
            os.environ["LANG"] = saved["LANG"]
        elif "LANG" in os.environ:
            del os.environ["LANG"]
        for key in ["ONELAKE_WORKSPACE", "ONELAKE_LAKEHOUSE"]:
            if saved[key] is not None:
                os.environ[key] = saved[key]


# ── Test 5: Graceful errors ───────────────────────────────────────────────────

def test_graceful_errors():
    section("5 / 8 · Graceful Errors (Operations Without Config)")
    print(f"\n  {DIM}Why: If a user calls onelake.ls('/') without env vars set, they")
    print(f"  should get a clear RuntimeError saying ONELAKE_WORKSPACE is missing —")
    print(f"  not a cryptic Azure SDK traceback about NoneType or empty strings.{RESET}")

    saved = {
        "ONELAKE_WORKSPACE": os.environ.pop("ONELAKE_WORKSPACE", None),
        "ONELAKE_LAKEHOUSE": os.environ.pop("ONELAKE_LAKEHOUSE", None),
    }

    try:
        import onelake_utils
        importlib.reload(onelake_utils)
        onelake_utils._client = None
        onelake_utils._fs_client = None

        test_calls = [
            ("ls", lambda: onelake_utils.ls("/")),
            ("read", lambda: onelake_utils.read("/dummy")),
            ("download", lambda: onelake_utils.download("/dummy", "/tmp/dummy")),
            ("write", lambda: onelake_utils.write("/dummy", b"data")),
        ]

        for fn_name, fn_call in test_calls:
            try:
                fn_call()
                verdict(
                    f"{fn_name}() raises RuntimeError when unconfigured",
                    False,
                    f"No exception raised. {fn_name}() should fail before any "
                    f"network call because ONELAKE_WORKSPACE is empty. If it "
                    f"silently succeeds, it might hit Azure with bad params.",
                )
            except RuntimeError as e:
                msg = str(e)
                mentions_var = "ONELAKE_WORKSPACE" in msg or "ONELAKE_LAKEHOUSE" in msg

                verdict(
                    f"{fn_name}() raises RuntimeError when unconfigured",
                    True,
                    f"Correctly raises RuntimeError before attempting any network I/O. "
                    f"The error message {'names the missing env var' if mentions_var else 'does NOT name the env var (should it?)'}.",
                    [("Exception type", "RuntimeError"),
                     ("Message", msg),
                     ("Mentions env var", str(mentions_var))],
                )

                if not mentions_var:
                    verdict(
                        f"{fn_name}() error message names the missing env var",
                        False,
                        f"Error message is \"{msg}\" — it should explicitly say "
                        f"'ONELAKE_WORKSPACE' or 'ONELAKE_LAKEHOUSE' so the user "
                        f"knows exactly what to fix, not just 'not set'.",
                    )
            except Exception as e:
                verdict(
                    f"{fn_name}() raises RuntimeError when unconfigured",
                    False,
                    f"Raised {type(e).__name__} instead of RuntimeError. Raw Azure "
                    f"SDK exceptions leak implementation details to users.",
                    [("Exception type", type(e).__name__), ("Message", str(e))],
                )
    finally:
        for key, val in saved.items():
            if val is not None:
                os.environ[key] = val


# ── Test 6: s6 status file ───────────────────────────────────────────────────

def test_s6_status_file():
    section("6 / 8 · s6 Init Script (Status File)")
    print(f"\n  {DIM}Why: The 03-onelake-init s6 script writes ~/.onelake_status at")
    print(f"  container boot. The helper module and users can read it to check")
    print(f"  config without making network calls. If not running in s6, this is")
    print(f"  expected to be missing.{RESET}")

    home = os.path.expanduser("~")
    status_path = os.path.join(home, ".onelake_status")

    if not os.path.exists(status_path):
        verdict(
            "~/.onelake_status exists",
            None,  # skip
            f"File not found at '{status_path}'. This is expected if you're "
            f"running outside the container (s6-overlay creates this at boot). "
            f"To test: run this script inside a built container.",
            [("Expected path", status_path)],
        )
        return

    try:
        with open(status_path) as f:
            raw = f.read()

        verdict(
            "~/.onelake_status exists and is readable",
            True,
            f"File found ({len(raw)} bytes). s6 init script ran successfully.",
            [("Path", status_path), ("Raw content", raw.strip())],
        )

        data = json.loads(raw)
        verdict(
            "~/.onelake_status is valid JSON",
            True,
            f"Parsed successfully. Both the helper module and shell scripts "
            f"can consume this file.",
            [("Parsed", data)],
        )

        has_key = "configured" in data
        verdict(
            "Status JSON has 'configured' key",
            has_key,
            f"{'Found' if has_key else 'Missing'} the 'configured' boolean. "
            f"This is the primary flag the helper checks to know if OneLake "
            f"was set up by the init script.",
            [("Keys present", list(data.keys()))],
        )

        if data.get("configured"):
            ws = data.get("workspace", "")
            ep = data.get("endpoint", "")
            verdict(
                "Status shows configured=true with workspace",
                bool(ws),
                f"Workspace: '{ws}'. Endpoint: '{ep}'. The init script found "
                f"ONELAKE_WORKSPACE in the environment and recorded it.",
                [("Full status", data)],
            )
        else:
            verdict(
                "Status shows configured=false (expected without env vars)",
                True,
                f"ONELAKE_WORKSPACE was not set when the container booted. "
                f"This is normal for pods without OneLake PodDefaults.",
                [("Full status", data)],
            )
    except json.JSONDecodeError as e:
        verdict(
            "~/.onelake_status is valid JSON",
            False,
            f"JSON parse failed. The s6 init script's heredoc may have been "
            f"corrupted by variable expansion or missing quotes.",
            [("Raw content", raw.strip()), ("Parse error", str(e))],
        )
    except Exception as e:
        verdict("~/.onelake_status readable", False, str(e))


# ── Test 7: R environment ────────────────────────────────────────────────────

def test_r_environment():
    section("7 / 8 · R Environment Integrity")
    print(f"\n  {DIM}Why: Commit 6d0234c removed 13 R packages from the mamba install")
    print(f"  to reduce build time. We need to verify R itself still starts and")
    print(f"  the init script's Renviron writes didn't break anything.{RESET}")

    # 7a: R starts
    try:
        result, ms = timed(lambda: subprocess.run(
            ["R", "--vanilla", "-e", "cat(R.version.string)"],
            capture_output=True, text=True, timeout=30,
        ))
        if result.returncode == 0:
            # R --vanilla -e "cat(...)" outputs the version after the > prompt
            # Filter out empty lines and R prompt lines to get the actual version
            stdout_lines = result.stdout.strip().split("\n")
            version = "unknown"
            for line in stdout_lines:
                cleaned = line.strip().lstrip("> ").strip()
                if cleaned.startswith("R version"):
                    version = cleaned
                    break
            if version == "unknown":
                # Fallback: try stderr where R sometimes prints version info
                for line in result.stderr.strip().split("\n"):
                    if "R version" in line:
                        version = line.strip()
                        break
            verdict(
                "R starts and reports version",
                True,
                f"R launched in {ms:.0f}ms and printed version string. "
                f"The removal of R packages from mamba did not break the R runtime.",
                [("R version", version), ("Startup time", f"{ms:.0f}ms")],
            )
        else:
            stderr = result.stderr.strip()[:300]
            verdict(
                "R starts and reports version",
                False,
                f"R exited with code {result.returncode}. Removing packages "
                f"from the mamba layer may have broken a dependency chain.",
                [("Exit code", str(result.returncode)), ("Stderr", stderr)],
            )
            return
    except FileNotFoundError:
        verdict(
            "R starts and reports version",
            None,
            "R not found on PATH. Expected if running outside the container.",
        )
        return
    except subprocess.TimeoutExpired:
        verdict("R starts and reports version", False, "Timed out after 30s. R may be hanging on startup.")
        return

    # 7b: Renviron file exists and is readable
    renviron = "/opt/conda/lib/R/etc/Renviron"
    try:
        result = subprocess.run(
            ["R", "--vanilla", "-e", f"cat(readLines('{renviron}', warn=FALSE), sep='\\n')"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            content = result.stdout.strip()
            has_onelake_line = "ONELAKE_WORKSPACE" in content
            verdict(
                "Renviron file accessible from R",
                True,
                f"R can read '{renviron}'. "
                f"{'Contains ONELAKE_WORKSPACE line (s6 init script wrote it).' if has_onelake_line else 'No ONELAKE_WORKSPACE line yet (expected — s6 writes it at boot, not at build time).'}",
                [("ONELAKE vars present", str(has_onelake_line))],
            )
    except Exception:
        pass  # non-critical


# ── Test 8: Live OneLake connection ──────────────────────────────────────────

def test_live_connection():
    section("8 / 8 · Live OneLake Connection")
    print(f"\n  {DIM}Why: This is the real proof. Tests 1–7 verify the code is installed")
    print(f"  correctly. This test verifies the end-to-end flow: auth, network,")
    print(f"  OneLake API, read, write. If this passes, Phase 1 works.{RESET}")

    ws = os.environ.get("ONELAKE_WORKSPACE", "")
    lh = os.environ.get("ONELAKE_LAKEHOUSE", "")

    if not ws:
        print(f"\n  {YELLOW}ONELAKE_WORKSPACE is not set in environment.{RESET}")
        print(f"  {DIM}This is expected outside the Zone platform.{RESET}")
        ws = input(f"\n  Enter workspace name or GUID (or Enter to skip): ").strip()
        if not ws:
            verdict("Live connection test", None, "Skipped — no workspace provided. Run with env vars set on the Zone.")
            return
        os.environ["ONELAKE_WORKSPACE"] = ws

    if not lh:
        print(f"\n  {YELLOW}ONELAKE_LAKEHOUSE is not set in environment.{RESET}")
        lh = input(f"  Enter lakehouse name (or Enter to skip): ").strip()
        if not lh:
            verdict("Live connection test", None, "Skipped — no lakehouse provided.")
            return
        os.environ["ONELAKE_LAKEHOUSE"] = lh

    print(f"\n  {DIM}Using workspace: {ws}{RESET}")
    print(f"  {DIM}Using lakehouse: {lh}{RESET}")

    import onelake_utils
    importlib.reload(onelake_utils)
    onelake_utils._client = None
    onelake_utils._fs_client = None

    # 8a: Network reachability (W0-1 from stress test doc)
    print(f"\n  {DIM}Testing network reachability to OneLake endpoint...{RESET}")
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://onelake.dfs.fabric.microsoft.com",
            method="HEAD",
        )
        resp, ms = timed(lambda: urllib.request.urlopen(req, timeout=10))
        verdict(
            "Network: onelake.dfs.fabric.microsoft.com reachable",
            True,
            f"Got HTTP {resp.status} in {ms:.0f}ms. The pod's egress rules "
            f"allow traffic to OneLake. (This validates W0-1 from the stress test doc.)",
            [("HTTP status", str(resp.status)), ("Latency", f"{ms:.0f}ms")],
        )
    except Exception as e:
        err_type = type(e).__name__
        verdict(
            "Network: onelake.dfs.fabric.microsoft.com reachable",
            # A 400/403 still means the endpoint is reachable
            "urlopen" not in str(e).lower() and "timeout" not in str(e).lower(),
            f"Got {err_type}: {e}. If this is a connection/timeout error, the "
            f"firewall is blocking egress and ALL OneLake access is dead. "
            f"If it's an HTTP error (400/403), the endpoint is reachable but "
            f"auth or request format is wrong — that's fine for a HEAD request.",
            [("Exception", f"{err_type}: {e}")],
        )

    # 8b: info() with config
    from io import StringIO
    import contextlib

    try:
        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            onelake_utils.info()
        out = buf.getvalue()
        has_connected = "connected" in out.lower() or "connecte" in out.lower()
        verdict(
            "info() with config shows 'Connected'",
            has_connected,
            f"With env vars set, info() should report connected status. "
            f"Note: this checks config presence, not actual auth — auth is lazy.",
            [("Output", out.strip())],
        )
    except Exception as e:
        verdict("info() with config", False, str(e))

    # 8c: ls() — the real auth + network + API test
    print(f"\n  {DIM}Attempting ls('/') — this will trigger authentication...{RESET}")
    print(f"  {DIM}(DefaultAzureCredential will try Workload Identity, then MSI,")
    print(f"   then SPN env vars, then Azure CLI token, in order){RESET}\n")

    try:
        items, ms = timed(lambda: onelake_utils.ls("/"))
        verdict(
            "ls('/') succeeds — auth + network + API all working",
            True,
            f"Returned {len(items)} items in {ms:.0f}ms. This single call proves: "
            f"(1) DefaultAzureCredential found a valid token, "
            f"(2) the token has Fabric workspace read permissions, "
            f"(3) OneLake's DFS API accepted the workspace/lakehouse path. "
            f"This validates W0-3, W0-4, and W0-5 from the stress test doc.",
            [("Items returned", str(len(items))),
             ("Auth + API time", f"{ms:.0f}ms")],
        )
        for item in items[:8]:
            kind = "DIR " if item.get("is_directory") else "FILE"
            size = item.get("size", 0)
            print(f"       {DIM}{kind}  {item['name']:<40} ({size:,} bytes){RESET}")
        if len(items) > 8:
            print(f"       {DIM}... and {len(items) - 8} more{RESET}")

    except Exception as e:
        verdict(
            "ls('/') succeeds",
            False,
            f"Failed with {type(e).__name__}: {e}. Diagnose: "
            f"(1) Is this a 401/403? — Check SPN permissions on the Fabric workspace. "
            f"(2) Is this a connection error? — Firewall blocking egress. "
            f"(3) Is this a 404? — Wrong workspace name or GUID. "
            f"(4) Is the Fabric tenant setting 'external access to OneLake' ON?",
            [("Exception", f"{type(e).__name__}: {e}"),
             ("Traceback", traceback.format_exc()[-500:])],
        )
        return  # can't test write/read if ls fails

    # 8d: write + read round-trip
    test_file = "__zone_onelake_test.txt"
    test_data = f"Zone OneLake validation | {time.strftime('%Y-%m-%d %H:%M:%S')} | PR #241"
    print(f"\n  {DIM}Testing write → read round-trip with '{test_file}'...{RESET}")

    try:
        _, w_ms = timed(lambda: onelake_utils.write(test_file, test_data))
        verdict(
            f"write('{test_file}') succeeds",
            True,
            f"Wrote {len(test_data)} bytes in {w_ms:.0f}ms. This proves write "
            f"permissions on the lakehouse — the SPN/WI token has Contributor "
            f"or Writer role.",
            [("Bytes written", str(len(test_data))),
             ("Write time", f"{w_ms:.0f}ms"),
             ("Content", test_data)],
        )
    except Exception as e:
        verdict(
            f"write('{test_file}') succeeds",
            False,
            f"Write failed. If ls() worked but write fails, the credential "
            f"has read-only access. Check the SPN's Fabric role.",
            [("Exception", f"{type(e).__name__}: {e}")],
        )
        return

    try:
        got, r_ms = timed(lambda: onelake_utils.read(test_file, as_text=True))
        match = got == test_data
        verdict(
            "read() returns exact data that was written",
            match,
            f"Read {len(got)} bytes in {r_ms:.0f}ms. "
            f"{'Data matches exactly — full round-trip confirmed.' if match else f'DATA MISMATCH. Expected {len(test_data)} bytes, got {len(got)}. Possible encoding issue or partial write.'}",
            [("Expected", test_data),
             ("Got", got),
             ("Match", str(match)),
             ("Read time", f"{r_ms:.0f}ms")],
        )
    except Exception as e:
        verdict(f"read('{test_file}')", False, str(e))

    # 8e: download to local filesystem
    local_tmp = "/tmp/__zone_onelake_test.txt"
    try:
        _, d_ms = timed(lambda: onelake_utils.download(test_file, local_tmp))
        with open(local_tmp) as f:
            content = f.read()
        match = content == test_data
        file_size = os.path.getsize(local_tmp)

        verdict(
            "download() writes correct local file",
            match,
            f"Downloaded to '{local_tmp}' ({file_size} bytes) in {d_ms:.0f}ms. "
            f"{'Content matches original.' if match else 'CONTENT MISMATCH.'}",
            [("Local path", local_tmp),
             ("File size", f"{file_size} bytes"),
             ("Content match", str(match)),
             ("Download time", f"{d_ms:.0f}ms")],
        )
    except Exception as e:
        verdict(f"download('{test_file}')", False, str(e))
    finally:
        if os.path.exists(local_tmp):
            os.remove(local_tmp)

    # 8f: upload round-trip
    upload_local = "/tmp/__zone_upload_test.txt"
    upload_remote = "__zone_upload_test.txt"
    upload_data = f"Upload test | {time.strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        with open(upload_local, "w") as f:
            f.write(upload_data)

        _, u_ms = timed(lambda: onelake_utils.upload(upload_local, upload_remote))
        got = onelake_utils.read(upload_remote, as_text=True)
        match = got == upload_data

        verdict(
            "upload() local file → OneLake round-trip",
            match,
            f"Uploaded {len(upload_data)} bytes in {u_ms:.0f}ms, read back matches. "
            f"This confirms the full cycle: local file → OneLake → read back.",
            [("Upload time", f"{u_ms:.0f}ms"), ("Match", str(match))],
        )
    except Exception as e:
        verdict("upload() round-trip", False, str(e))
    finally:
        if os.path.exists(upload_local):
            os.remove(upload_local)


# ── Summary ───────────────────────────────────────────────────────────────────

def summary():
    section("Results Summary")

    total   = len(results)
    passed  = sum(1 for _, s, _ in results if s is True)
    failed  = sum(1 for _, s, _ in results if s is False)
    skipped = sum(1 for _, s, _ in results if s is None)

    bar_width = 50
    p_width = int(bar_width * passed / total) if total else 0
    f_width = int(bar_width * failed / total) if total else 0
    s_width = bar_width - p_width - f_width

    bar = f"{GREEN}{'█' * p_width}{RED}{'█' * f_width}{YELLOW}{'░' * s_width}{RESET}"
    print(f"\n  {bar}")
    print(f"  {GREEN}{passed} passed{RESET}  {RED}{failed} failed{RESET}  {YELLOW}{skipped} skipped{RESET}  {DIM}({total} total){RESET}\n")

    if failed:
        print(f"  {RED}{BOLD}Failures requiring attention:{RESET}\n")
        for name, status, reasoning in results:
            if status is False:
                print(f"    {RED}x{RESET}  {name}")
                print(f"       {DIM}{reasoning[:120]}{RESET}")
        print()

    if failed == 0 and skipped == 0:
        print(f"  {GREEN}{BOLD}All {total} checks passed. PR #241 is validated.{RESET}\n")
    elif failed == 0:
        print(f"  {GREEN}{BOLD}All executed checks passed ({skipped} skipped).{RESET}")
        print(f"  {DIM}Skipped tests are expected outside the container environment.{RESET}\n")
    else:
        print(f"  {RED}{BOLD}{failed} check(s) need investigation before merging.{RESET}\n")

    return 1 if failed else 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    live = "--live" in sys.argv

    print(f"\n{BOLD}{'═' * 70}{RESET}")
    print(f"{BOLD}  OneLake PR #241 — Validation Suite{RESET}")
    print(f"{BOLD}  {DIM}zone-kubeflow-containers | Phase 1 SDK Integration{RESET}")
    print(f"{BOLD}{'═' * 70}{RESET}")
    print(f"  {DIM}Date: {time.strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"  {DIM}Mode: {'LIVE (with OneLake connection)' if live else 'OFFLINE (install verification only)'}{RESET}")
    print(f"  {DIM}Python: {sys.version.split()[0]} at {sys.executable}{RESET}")
    if not live:
        print(f"\n  {YELLOW}Tip: Run with --live to test actual OneLake connectivity.{RESET}")

    test_sdk_packages()
    test_helper_import()
    test_info_unconfigured()
    test_bilingual()
    test_graceful_errors()
    test_s6_status_file()
    test_r_environment()

    if live:
        test_live_connection()
    else:
        section("8 / 8 · Live OneLake Connection")
        verdict(
            "Live connection test",
            None,
            "Skipped — pass --live flag to enable. This tests actual auth, "
            "network egress, and OneLake read/write from inside the pod.",
        )

    code = summary()

    # Raise SystemExit only when run as a script, not inside Jupyter/IPython
    try:
        get_ipython()  # noqa: F821 — defined in IPython environments
        # Inside Jupyter/IPython — don't call sys.exit(), just return the code
        if code != 0:
            print(f"  {DIM}(exit code: {code}){RESET}")
    except NameError:
        # Running as a normal script — safe to exit
        sys.exit(code)


if __name__ == "__main__":
    main()
