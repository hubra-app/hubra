"""Run the plugins' tests with Hubra's test fixtures.

From app/backend: ``pytest`` runs Hubra's tests and these (``testpaths``),
or ``pytest ../../plugins/keys`` one plugin.  The bundled plugins are all
loaded in tests (``PLUGINS_AUTOINSTALL = "all"`` in TestingConfig).
"""

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "app" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Test modules import plugin packages at collection time, before an app
# (and so the plugin loader) exists.
for _plugin in sorted(Path(__file__).resolve().parent.iterdir()):
    if (_plugin / "plugin.yaml").is_file() and str(_plugin) not in sys.path:
        sys.path.insert(0, str(_plugin))

import tests.conftest as _core  # noqa: E402

# Every fixture, also the autouse ones whose names start with "_" (such as
# the one that clears cached keys between tests), which "import *" skips.
globals().update({k: v for k, v in vars(_core).items() if not k.startswith("__")})
