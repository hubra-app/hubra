"""Plugins: modules that are installed into Hubra rather than built in.

A plugin is a folder with a ``plugin.yaml`` (see ``spec.py``), signed with
Ed25519 (``trust.py``, the labdex format), distributed through signed
repositories and installed by a platform manager from the Marketplace.
Each club then switches the plugin's modules on in Settings › Modules.

Read ``plugins/README.md`` in the repository for how to write one.
"""

from .loader import current

__all__ = ["current"]
