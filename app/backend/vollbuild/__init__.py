"""vollbuild: Hubra backend.

The application factory lives in :mod:`vollbuild.core.app`; it is exported
here so ``from vollbuild import create_app`` and ``wsgi:app`` keep working.
"""

from vollbuild.core.app import create_app

__all__ = ["create_app"]
