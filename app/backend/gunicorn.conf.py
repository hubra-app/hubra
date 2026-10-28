"""gunicorn settings read from the working directory (/app in the image).

Command-line flags still win.  This file only adds the plugin reload hook:
when a platform manager installs, updates or removes a plugin, the
arbiter replaces its workers so they load the new set of plugins.
"""


def when_ready(server):
    from hubra.core.plugins.reload import watch_gunicorn

    watch_gunicorn(server)
