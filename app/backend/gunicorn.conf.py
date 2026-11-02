"""gunicorn settings read from the working directory (/app in the image).

Command-line flags still win.  This file only adds two hooks: the plugin
reload hook (when a platform manager installs, updates or removes a plugin,
the arbiter replaces its workers so they load the new set of plugins) and the
build heartbeat, so manage sees which commit the API runs.
"""


def when_ready(server):
    from hubra.core.plugins.reload import watch_gunicorn

    watch_gunicorn(server)


def post_worker_init(worker):
    from hubra.core.build_info import start_heartbeat

    start_heartbeat("api", worker.wsgi)
