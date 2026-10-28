"""Events: club events, registrations and attendance."""

from hubra.core.modules import Blueprint, Module, NavItem, SettingField

module = Module(
    code="events",
    name="Events",
    description="Events, workshops and gatherings with registration",
    default_enabled=True,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "hubra.api.events.routes",
            "events_bp",
            "/api/v1/events",
        ),
    ),
    settings=(
        SettingField(
            "notify_members",
            "bool",
            default=True,
            label="Notify members about new events",
            description="An in-app notification for every member when an event is published",
        ),
    ),
    nav=(
        NavItem(
            "/app/operations/events",
            "shell.nav.management",
            "layout-list",
            order=40,
            group="management",
        ),
    ),
    # The calendar feed authenticates with its own signed token.
    public_endpoints=("events_bp.calendar_feed",),
    tables=("club_events", "event_attendees", "event_registrations"),
)
