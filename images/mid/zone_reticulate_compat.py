"""Activate /opt/reticulate-compat when this Conda Python runs under R.

R processes (terminal R/Rscript, the Jupyter IR kernel, RStudio's rsession)
export R_HOME. When reticulate embeds this interpreter in such a process,
Ubuntu OpenSSL is already resident and Conda's OpenSSL-linked extension
modules cannot load next to it, so the audited system-OpenSSL rebuilds and
version-pinned wheels must come first on sys.path.

Imported through zone-reticulate-compat.pth at `site` time, before any
affected module can load. Because the hook lives inside this interpreter's
site-packages, the cp314-specific overlay can never attach to a different
interpreter, regardless of how reticulate was pointed at one. No-op outside
R processes, when the audited overlay is absent, or when
ZONE_RETICULATE_COMPAT=0.
"""

import os
import sys

_OVERLAY = (
    "/opt/reticulate-compat/lib/python3.14/lib-dynload",
    "/opt/reticulate-compat/lib/python3.14/site-packages",
)


def _activate():
    if not os.environ.get("R_HOME"):
        return
    if os.environ.get("ZONE_RETICULATE_COMPAT", "1") == "0":
        return
    if not os.path.exists("/opt/reticulate-compat/.audit-passed"):
        return
    for path in reversed(_OVERLAY):
        if path not in sys.path:
            sys.path.insert(0, path)


_activate()
del _activate
