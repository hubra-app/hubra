"""Events: club events, registrations and attendance."""

from hubra.core.modules import Blueprint, Module, NavItem, Schedule, SettingField

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
            "/api/v1/app/events",
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
        SettingField(
            "reminder_hours",
            "int",
            default=24,
            label="Reminder before an event (hours)",
            description="Members who signed up get a reminder this long before the start, in the app and by mail. 0: no reminders",
        ),
        SettingField(
            "event_types",
            "str",
            default="",
            label="Event types",
            description=(
                "The types to pick from, separated by commas (for example "
                "Training, Match, Versammlung). Empty: Workshop, Social, "
                "Certification and Meeting."
            ),
        ),
    ),
    nav=(
        NavItem(
            "/app/operations/events",
            "shell.nav.events",
            "calendar",
            section="activities",
            order=30,
        ),
    ),
    # The calendar feed authenticates with its own signed token.
    public_endpoints=(
        "events_bp.calendar_feed",
        "events_bp.public_calendar",
        "events_bp.public_events",
        # The trial page: people who aren't members book a trial training.
        "events_bp.public_trials",
        "events_bp.public_trial_signup",
        "events_bp.public_trial_confirm",
        "events_bp.public_trial_cancel",
    ),
    tables=(
        "event_series",
        "club_events",
        "event_attendees",
        "event_registrations",
        "event_attendance",
        "trial_signups",
    ),
    tasks=("hubra.core.tasks.reminder_tasks",),
    schedule=(
        Schedule(
            "event-reminders",
            "hubra.core.tasks.reminder_tasks.send_event_reminders_task",
            900,
        ),
        # Trial bookings are personal data: gone half a year after the training.
        Schedule(
            "trial-signups-purge",
            "hubra.core.tasks.reminder_tasks.purge_trial_signups_task",
            86400,
        ),
    ),
)
