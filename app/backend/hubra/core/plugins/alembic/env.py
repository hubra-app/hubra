"""Alembic environment for one plugin's migrations.

Run through ``hubra.core.plugins.migrate``, never by ``flask db``: each
plugin has its own version table (``alembic_version_<id>``) so its
revisions are independent of Hubra's own chain and of other plugins.
The caller passes the connection (search_path already set to the club's
schema, or public) in ``config.attributes``.
"""

from alembic import context

from hubra.core.extensions import db

config = context.config
connection = config.attributes["connection"]
tables = set(config.attributes.get("tables") or ())


def include_object(obj, name, type_, reflected, compare_to):
    # Autogenerate only looks at this plugin's own tables.
    if type_ == "table":
        return name in tables
    table = getattr(obj, "table", None)
    if table is not None:
        return table.name in tables
    return True


context.configure(
    connection=connection,
    target_metadata=db.metadata,
    version_table=config.attributes["version_table"],
    version_table_schema=config.attributes.get("schema"),
    include_object=include_object,
    render_as_batch=connection.dialect.name == "sqlite",
)

with context.begin_transaction():
    context.run_migrations()
