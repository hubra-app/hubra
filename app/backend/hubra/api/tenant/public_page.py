"""A club's public page: what anyone may see without signing in.

Off until the club turns it on (Settings › Club › "Public club page",
``public_page``). Then ``GET /global/clubs/<slug>/public`` gives the join
portal (join.hubra.club/clubs/<slug>) the club's name, logo, description
and website, its upcoming public events, its groups when the club lists
them publicly (``public_group_listing``, private groups never), whether it
takes join requests and whether it offers trial trainings.

``GET /app/events/public/<slug>/widget.js`` is a script a club puts on its
own website to show the public events there (docs/public-club-page.md).
"""

from __future__ import annotations

from datetime import date

from flask import Response, current_app, jsonify, request
from sqlalchemy import func, select

from hubra.api.events.routes import _public_events, events_bp, public_event
from hubra.api.tenant.routes import _active_club, club_access_bp
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.tenant.club_settings import (
    accepts_join_requests,
    club_logo_version,
    club_setting,
)

MAX_EVENTS = 20
MAX_GROUPS = 50


def public_page_on(tenant) -> bool:
    return club_setting(tenant, "public_page", False) is True


def _groups() -> list[dict]:
    from hubra.core.models.group import Group

    rows = db.session.scalars(
        select(Group)
        .where(Group.visibility != "private")
        .where(Group.deleted_at.is_(None))
        .where(Group.archived_at.is_(None))
        .order_by(Group.name)
        .limit(MAX_GROUPS)
    ).all()
    return [
        {
            "name": g.name,
            "description": g.description,
            "sessions": g.sessions,
            "color": g.color,
        }
        for g in rows
    ]


def _trials_open(today: date) -> bool:
    from hubra.core.models.event import ClubEvent

    count = db.session.scalar(
        select(func.count(ClubEvent.id))
        .where(ClubEvent.trial_spots.isnot(None))
        .where(ClubEvent.trial_spots > 0)
        .where(ClubEvent.date >= today)
    )
    return bool(count)


def _public_calendar_url(slug: str) -> str:
    """The club's public .ics feed (events_bp.public_calendar).

    Built by hand: this page is served by the global backend, which does
    not register the club routes, so url_for raised BuildError there and
    the whole page answered 500. The feed itself is a club (app) route on
    the same API host.
    """
    from urllib.parse import quote

    return f"{request.url_root.rstrip('/')}/api/v1/app/events/public/{quote(slug)}.ics"


def _public_url(value) -> str | None:
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        return value[:500]
    return None


@club_access_bp.route("/clubs/<slug>/public", methods=["GET"])
def club_public_page(slug: str):
    """The club's public page, or 404 when the club hasn't turned it on."""
    from hubra.core.modules import is_enabled
    from hubra.core.tenant.context import reset_search_path, set_search_path

    tenant = _active_club(slug)
    if not public_page_on(tenant):
        raise_error(404, "NOT_FOUND", "This club has no public page")
    today = date.today()
    try:
        set_search_path(tenant.id)
        events_on = is_enabled("events", tenant.id)
        events = _public_events(today)[:MAX_EVENTS] if events_on else []
        sso = (current_app.config.get("SSO_BASE_URL") or "").rstrip("/")
        body = {
            "slug": tenant.slug,
            "name": tenant.name,
            "description": club_setting(tenant, "club_description"),
            "website": _public_url(club_setting(tenant, "website")),
            "logoVersion": club_logo_version(tenant),
            "acceptsRequests": accepts_join_requests(tenant),
            "trials": events_on and _trials_open(today),
            # Public events link to this page, not to the members' app.
            "events": [
                {**public_event(e, None), "url": None} for e in events
            ],
            "calendar": (
                _public_calendar_url(tenant.slug)
                if events_on
                else None
            ),
            "groups": (
                _groups()
                if club_setting(tenant, "public_group_listing", False) is True
                else []
            ),
            "pageUrl": f"{sso}/clubs/{tenant.slug}" if sso else None,
        }
    finally:
        reset_search_path()
    resp = jsonify(body)
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


# The embeddable events list. Plain JS, no dependencies; it draws into a
# shadow root so the club's own styles and ours don't mix, and only ever
# sets textContent, so event texts can't inject markup.
_WIDGET = r"""(function () {
  var me = document.currentScript;
  if (!me) return;
  var api = new URL(me.src).origin + new URL(me.src).pathname.replace(/\/widget\.js$/, '');
  var lang = (me.getAttribute('data-lang') || document.documentElement.lang || navigator.language || 'de').slice(0, 2);
  var max = Math.max(1, Math.min(20, parseInt(me.getAttribute('data-max') || '5', 10) || 5));
  var de = lang === 'de';
  var host = document.createElement('div');
  host.className = 'hubra-events';
  me.parentNode.insertBefore(host, me.nextSibling);
  var root = host.attachShadow ? host.attachShadow({ mode: 'open' }) : host;
  var style = document.createElement('style');
  style.textContent = ':host{all:initial;display:block;font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;color:inherit}' +
    'ul{list-style:none;margin:0;padding:0}li{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid rgba(127,127,127,.25)}' +
    '.d{min-width:52px;text-align:center;border-radius:8px;background:rgba(116,65,224,.12);color:#5b2fc2;padding:4px 0;font-weight:700;line-height:1.15}' +
    '.d small{display:block;font-weight:600;font-size:11px;text-transform:uppercase}.t{font-weight:600}.m{opacity:.75;font-size:13px}' +
    '.f{margin-top:8px;font-size:13px}.f a{color:#5b2fc2}';
  root.appendChild(style);
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text) e.textContent = text; return e; }
  fetch(api).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (data) {
    var list = el('ul');
    var events = (data.events || []).slice(0, max);
    if (!events.length) root.appendChild(el('p', 'm', de ? 'Zurzeit keine öffentlichen Anlässe.' : 'No public events at the moment.'));
    events.forEach(function (ev) {
      var day = new Date(ev.date + 'T12:00:00');
      var li = el('li');
      var d = el('div', 'd', String(day.getDate()));
      d.appendChild(el('small', '', day.toLocaleDateString(de ? 'de-CH' : 'en-GB', { month: 'short' })));
      var body = el('div');
      body.appendChild(el('div', 't', ev.title));
      var meta = [ev.time, ev.location].filter(Boolean).join(' · ');
      if (meta) body.appendChild(el('div', 'm', meta));
      li.appendChild(d); li.appendChild(body); list.appendChild(li);
    });
    root.appendChild(list);
    var foot = el('div', 'f');
    if (data.calendar) {
      var a = el('a', '', de ? 'Kalender abonnieren' : 'Subscribe to the calendar');
      a.href = data.calendar.replace(/^https?:/, 'webcal:'); foot.appendChild(a);
    }
    root.appendChild(foot);
  }).catch(function () { host.remove(); });
})();
"""


@events_bp.get("/public/<string:slug>/widget.js")
def public_events_widget(slug: str):
    """A script that shows the club's public events on another website."""
    resp = Response(_WIDGET, mimetype="application/javascript")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp
