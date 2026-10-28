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

from tests.conftest import *  # noqa: E402,F403
