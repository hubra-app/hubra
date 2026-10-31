"""A connected-app provider for tests: records what core asked of it."""

from hubra.core.apps import AppError, ConnectionDraft

calls: list[tuple] = []


class Handler:
    fail_complete = False
    fail_revoke = False

    def unavailable(self):
        return None

    def authorize_url(self, state, redirect_uri, scopes):
        calls.append(("authorize_url", state, redirect_uri, tuple(scopes)))
        return f"https://fake.example/authorize?state={state}"

    def complete(self, args, redirect_uri):
        calls.append(("complete", args.get("guild_id")))
        if self.fail_complete:
            raise AppError("nope")
        return ConnectionDraft(
            external_id=args.get("guild_id", "g1"),
            label="Fake server",
            config={"channel": None},
            secret="s3cret",
        )

    def confirmed(self, conn):
        calls.append(("confirmed", conn.id))

    def options(self, conn):
        return {"channels": [{"id": "c42", "name": "general"}]}

    def update_config(self, conn, config):
        if config.get("channel") == "bad":
            raise AppError("No such channel")
        return {"channel": config.get("channel")}

    def test(self, conn):
        return "hello"

    def revoke(self, conn):
        calls.append(("revoke", conn.id))
        if self.fail_revoke:
            raise RuntimeError("service down")


handler = Handler()
