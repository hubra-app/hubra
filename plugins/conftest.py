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
import tests.conftest as _hubra_conftest  # noqa: E402

# ``import *`` leaves out names starting with "_", and some of Hubra's
# autouse fixtures do (e.g. the one that forgets the last test's platform
# key). Take those too, or plugin tests fail depending on their order.
globals().update(
    {
        name: value
        for name, value in vars(_hubra_conftest).items()
        if name.startswith("_") and not name.startswith("__") and callable(value)
    }
)
