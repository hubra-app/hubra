"""Moved to :mod:`hubra.core.notifications.services`.

The old name stays for plugins built against older Hubra versions: it is
the same module object, so imports and patches of it still work. Hubra's own
code imports the new name (tests/test_import_boundaries.py).
"""

import sys

from hubra.core.notifications import services as _moved

sys.modules[__name__] = _moved
