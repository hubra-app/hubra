"""Notes: a module with nothing in it, for Hubra's plugin tests."""

from hubra.core.modules import Module

module = Module(code="notes", name="Notes", depends_on=("members",))
