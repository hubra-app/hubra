"""apps package — v2 namespace blueprints for global, manager, and tenant planes."""

from __future__ import annotations

import importlib
import logging

from flask import Flask

_log = logging.getLogger(__name__)


def _register_v2_blueprints(app: Flask, specs: list[tuple[str, str, str, str]]) -> None:
    """Register existing blueprints under v2 prefixes with unique names.

    Each spec is (module_path, blueprint_attr, url_prefix, v2_blueprint_name).
    The v2 name avoids Flask's duplicate-blueprint-registration error.
    """
    for module_path, bp_name, prefix, v2_name in specs:
        try:
            module = importlib.import_module(module_path)
            blueprint = getattr(module, bp_name)
            app.register_blueprint(blueprint, url_prefix=prefix, name=v2_name)
            app.logger.debug("Registered v2 blueprint %s → %s", v2_name, prefix)
        except ModuleNotFoundError as exc:
            top_level = module_path.split(".")[0]
            if exc.name and not exc.name.startswith(top_level):
                raise
            app.logger.debug("v2 blueprint %s not yet available, skipping", module_path)
        except AttributeError:
            app.logger.warning(
                "Module '%s' does not expose '%s' — skipping v2 registration.",
                module_path,
                bp_name,
            )
        except Exception as exc:
            _log.warning("Failed to register v2 blueprint %s: %s", v2_name, exc)
