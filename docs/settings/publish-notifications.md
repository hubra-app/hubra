# Notify members about new posts, events and polls

**Where:** Settings › Module & Plugins › Posts / Events / Polls ›
Einstellungen.

Each of the `posts`, `events` and `polls` modules has one setting:

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `notify_members` | bool | on | Publishing creates an in-app notification for every active member |

Off: no in-app notification. Everything else stays: the event bus
(`post.published` and so on), so Discord announcements still go out, and
direct notifications such as "you were given a proxy vote" are not affected.

**Code.** `notify_on_publish(module_code, ...)` in
`hubra/api/notifications/services.py` wraps `notify_all_active` and checks
the module setting.

**Not included.** Per-member preferences ("don't tell me about polls") and
email or push for new content. See [ideas.md](ideas.md).

**Tests:** `tests/notifications/test_publish_settings.py`.
