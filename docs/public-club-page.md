# Public club page and events widget

A club can show a public page on the join portal, for people who aren't
members yet. It is **off by default**.

## Turning it on

Settings › Membership › **Public club page** (`public_page` in the club
settings). The page then lives at `https://<join portal>/clubs/<slug>` and
shows, without signing in:

- the club's name, logo, description (Settings › Club) and website;
- upcoming events marked **Public event**, with a calendar to subscribe to;
- the club's groups, only when **List groups publicly** is on, and never
  private groups (name, meeting times, description; no members);
- a link to book a trial training when an upcoming event takes trials;
- **Become a member**: sign in or create an account, then the usual join
  request (or "invitation only" when the club takes no requests).

Signed-in visitors see the same information below the join form.

API: `GET /api/v1/global/clubs/<slug>/public` (no sign-in; 404 while the page
is off).

## Events on the club's own website

Events › **Subscribe to calendar** shows a one-line snippet:

```html
<script src="https://api.example/api/v1/app/events/public/<slug>/widget.js" async></script>
```

Put it where the list should appear. It shows the next public events (no
member data), in the page's language (German or English), and a link to
subscribe to the calendar. Options on the script tag: `data-max="10"`
(1–20, default 5) and `data-lang="en"`. It draws into a shadow root, so the
website's styles don't change it, and it only sets text, so event texts
can't add markup to the website. The JSON behind it is
`/api/v1/app/events/public/<slug>`.
