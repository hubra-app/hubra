"""
vollbuild — application factory re-export.

The actual implementation lives in vollbuild.core.app.
This module exists for backwards compatibility so that
``from vollbuild import create_app`` keeps working.
"""

from vollbuild.core.app import create_app  # noqa: F401
from vollbuild.core.app import _last_seen_cache  # noqa: F401

__all__ = ["create_app"]
