"""Moved to :mod:`hubra.core.auth.helpers`.

The old name stays for plugins built against older Hubra versions: it is
the same module object, so imports and patches of it still work. Hubra's own
code imports the new name (tests/test_import_boundaries.py).
"""

import sys

from hubra.core.auth import helpers as _moved

sys.modules[__name__] = _moved
