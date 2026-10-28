"""hubra: Hubra backend.

The application factory lives in :mod:`hubra.core.app`; it is exported
here so ``from hubra import create_app`` and ``wsgi:app`` keep working.
"""

from hubra.core.app import create_app

__all__ = ["create_app"]
