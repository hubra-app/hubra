# Contracts: how modules and plugins use each other

A plugin never imports another plugin, reads its tables or calls its REST
routes from the backend. Instead each module offers **contracts** by name
and version, and others use them through core:

| Kind | What it is | How others use it | Reply |
| --- | --- | --- | --- |
| event | a fact (`booking.confirmed`) | subscribe with `Module.events` | none; zero or more listeners |
| action | a command with one owner (`keys.key.hand_out`) | `call()` now, or `send()` after the commit | the action's result |
| query | a read (`inventory.items.get`) | `query()` | the result; writes are rolled back |
| widget | a dashboard widget (`inventory.lent`) | members add it to dashboards | what it shows, read as the viewer |

Core finds who offers a contract, checks that its module is on for the club,
checks the acting member's right, checks the input and the result against
the contract's schema, and keeps a failing handler's work away from the
caller's. The code is in `app/backend/hubra/core/contracts/`.

## Offering

```python
# hubra_inventory/__init__.py
from hubra.core.contracts import event_contract, query_contract
from hubra.core.modules import Module

module = Module(
    code="inventory",
    name="Inventory",
    provides=(
        query_contract(
            "inventory.items.get",
            "hubra_inventory.contracts:get_items",
            input="hubra_inventory.contracts:ItemsIn",
            output="hubra_inventory.contracts:Item",
            perm="inventory.items.read",
        ),
        event_contract("inventory.item.deleted", "hubra_inventory.contracts:ItemRef"),
    ),
)
```

```python
# hubra_inventory/contracts.py
from pydantic import BaseModel


class ItemsIn(BaseModel):
    ids: list[int]


class Item(BaseModel):
    id: int
    name: str


class ItemRef(BaseModel):
    item_id: int


def get_items(ctx, data: ItemsIn) -> list[Item]:
    rows = InventoryItem.query.filter(InventoryItem.id.in_(data.ids)).all()
    return [Item(id=r.id, name=r.name) for r in rows]
```

Rules (checked when the plugin loads, `core/plugins/limits.py`):

- Names start with the module code: `inventory.items.get`.
- Handlers and schemas are the plugin's own code. Schemas are pydantic
  models, named by dotted path so the manifest loads without them.
- No two modules offer the same name; Hubra's own events are taken.
- `plugin.yaml` lists `contracts` under `uses:`.

A handler gets a `CallContext` (`tenant_id`, `actor`, `system`, `caller`,
`message_id`) and the checked input. It returns a model, a list of models
or plain values. To say no for a reason the caller can show, raise
`Refused("This key is already handed out", code="KEY_TAKEN")`. A handler
must not commit: core does, so its work rolls back alone when it fails.

## Using

```python
# hubra_booking/__init__.py
module = Module(
    code="booking",
    ...,
    consumes={"inventory.items.get": ">=1,<2", "keys.key.hand_out": ">=1,<2"},
    events={"inventory.item.deleted": "hubra_booking.hooks:on_item_deleted"},
)
```

```python
from hubra.core.contracts import (
    SYSTEM, ActionUnavailable, Refused, available, call, query, send,
)

if available("inventory.items.get"):
    items = query("inventory.items.get", ids=[3, 7])  # as the signed-in member

try:
    call("keys.key.hand_out", key_id=12, member_id=5, actor=SYSTEM)
except ActionUnavailable:
    ...  # Keys isn't installed, didn't load, or is off for this club
except Refused as exc:
    ...  # show exc to the person

send("keys.key.hand_out", key_id=12, member_id=5, actor=SYSTEM)  # after the commit, retried
```

- A plugin may only use contracts it lists under `consumes` (and its own);
  anything else raises `ContractError`. The range is checked against the
  offer's version on every use.
- `consumes` doesn't make the other plugin required. To require it, also
  list it under `depends:` in `plugin.yaml`.
- `actor` defaults to the member of the current request. `actor=SYSTEM`
  skips the permission check: use it in jobs, or when the plugin acts on its
  own behalf (a booking hands out a key the member couldn't hand out).
- Errors: `ActionUnavailable`, `ActionForbidden`, `Refused` (with `code`),
  `ActionFailed` (the handler broke; its work was rolled back, yours wasn't)
  and `ContractError` (a bug: bad input, undeclared use).
- A plugin's own events need a contract too: `emit()` refuses a name no
  module lists under `provides` when a plugin sends it.

## Widgets

`widget_contract(name, handler, label=…, size=…, view=…, fields=…, perm=…)`
offers a dashboard widget. Core lists it only to members who may see it
(module on, `perm` held), runs its handler as the viewing member like a
query, and checks the result against its view (`stat`, `list`, or the
contract's `output` for `custom`). See [dashboards.md](dashboards.md).

## Versions

`version` is the contract's major version, a whole number. Adding an
optional field keeps it. Removing or renaming a field, or changing what it
means, raises it, and consumers name the versions they accept
(`">=1,<2"`). A consumer whose range isn't met gets `ActionUnavailable`;
an event subscriber whose range isn't met isn't called (logged).

## Delivery: the outbox

A plugin's event handlers and every `send()` go through the
`contract_outbox` table (public schema, one row per delivery):

1. The row is written in the caller's transaction. Rolled back, it's gone.
2. After the commit the transport hands it to the worker
   (`hubra.core.tasks.contract_tasks.deliver`).
3. The worker claims the row for 5 minutes, runs the handler in the club
   and marks it `done`. A failure is retried after 30 s, 2 min, 10 min,
   1 h and 6 h, then the row is `dead`. `Refused`, `ActionForbidden`,
   `ActionUnavailable` and `ContractError` are not retried.
4. Every minute the sweep (`contract_tasks.sweep`) sends what is due again:
   retries, rows whose worker died, rows the transport lost because Redis
   was down at the commit. A new row is left to its own delivery for
   2 minutes first, so a busy queue doesn't get a second copy of every row.
   Done rows are kept 7 days, dead ones 30.
5. A delivery is stopped after 4 minutes (inside the 5 minute claim), so a
   row is never run by two workers at once. Keep handlers short; queue
   longer work as a job of your own.
6. A row that gives up after every retry, or fails with `ContractError`,
   raises a system alert (once an hour per contract and module).

Delivery is at least once. A handler that only writes to the database gets
it once in effect. One that talks to an outside service should accept an
`event_id` argument (events) or read `ctx.message_id` (actions): both stay
the same on every retry. An event whose own data has an `event_id` (the club
events `event.*`: the id of the event) passes that one instead.

```
flask contracts list [--json]   # every contract, with JSON schemas
flask contracts outbox [--dead] # rows per status, or the dead ones
flask contracts retry <uid>     # another round for a dead row
```

## Jobs queued after the commit

`delay_after_commit(task, ...)` (`hubra/core/tasks/after_commit.py`) uses the
same table: just before the commit each held task becomes a row of kind
`job`, and delivering it queues the real Celery task. A mail, push or Discord
message for a committed change therefore reaches the queue even when Redis
was down at the commit. Arguments that aren't plain JSON go straight to the
broker after the commit, as before; in tests (eager Celery) nothing changes.

## Ready for a message broker

Nothing here assumes Celery:

- Each row stores an envelope shaped like a
  [CloudEvents 1.0](https://cloudevents.io) event: `specversion`, `id`,
  `source`, `type`, `time`, `data`, plus `tenantid`, `dataversion` and
  `hubrakind`. Brokers carry it unchanged.
- Payloads are plain JSON values, checked when stored.
- The transport is one class (`contracts/transport.py`, `Transport`) with
  one method, `publish(uid, tenant_id)`. A NATS, Kafka or RabbitMQ transport
  implements it and is set at start-up (`set_transport`); the outbox and
  sweep stay, so nothing is lost while the broker is down.
- `flask contracts list --json` prints every contract's JSON schema, for a
  schema registry or the plugin index.

Moving to a broker means: write the transport, run a consumer that calls
`outbox.deliver(uid)` (or reads the envelope straight from the message),
and switch it on. Emitters and handlers don't change.

## What Hubra's own modules offer

| Contract | Kind | What it does |
| --- | --- | --- |
| `finance.billing_period` | query | `{on}` → `{start, end}`, the club's billing year around that day |
| `finance.invoice.set_status` | action | `{invoice_id, status: Paid\|Open, actor_id?}`, with the mails and `invoice.updated`; needs `finance.invoices.update` |

A plugin that adds a source to the fee basis (Finanzen › Beitragsgrundlage)
offers a query named `<module>.fee_basis.<source>`: input `{on}`, output
`{lines: [{category_id, name, color, amount, items}], period}` (shapes in
`hubra/api/finance/contracts.py`). The Finances plugin offers
`finance.books.fee_basis.recurring` and `.last_year` this way.

## Not covered yet

- Club webhooks keep their own delivery and retries (`webhooks.md`).
- Hubra's own modules still call each other directly; they offer
  contracts as features move into plugins (below).
- Frontend slots are declared in core (`SlotProps`); a plugin can't yet
  declare a slot of its own for others to fill.
