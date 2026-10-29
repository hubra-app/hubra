"""Badges: a module with nothing in it, for Hubra's plugin tests."""

from hubra.core.modules import Module

module = Module(code="badges", name="Badges", depends_on=("members",))
