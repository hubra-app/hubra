# Public API (pricing and plugins)

Two read-only endpoints for the website (hubra.club) and anyone else. No
sign-in, no cookies, `Access-Control-Allow-Origin: *`, and
`Cache-Control: public, max-age=300`. They keep working in maintenance mode.

Only what a platform admin marked **public** in manage › Einstellungen ›
Tarife & Preise is listed. Hidden or archived plans, non-public plans
(e.g. a "Gesponsert" plan for special deals) and add-ons without a public
list price never show up. A club's own price, discount or sponsor is never
part of this API.

## GET /api/v1/public/pricing

```json
{
  "currency": "CHF",
  "plans": [
    {
      "key": "starter",
      "name_de": "Starter", "name_en": "Starter",
      "description_de": "Für kleine Vereine", "description_en": "For small clubs",
      "price_month_chf": "29.00",
      "price_year_chf": "290.00",
      "features": [{ "de": "Mitglieder, Anlässe, Umfragen", "en": "Members, events, polls" }],
      "modules": [
        {
          "code": "discord", "name_de": "Discord", "name_en": "Discord",
          "plugin": "discord", "price_chf": null, "unit": "flat", "included": true
        },
        {
          "code": "mail", "name_de": "Mail", "name_en": "Mail",
          "plugin": null, "price_chf": "0.20", "unit": "member", "included": false
        }
      ],
      "limits": { "members": 50, "mail_month": 500, "storage_mb": 200 },
      "highlighted": false,
      "sort": 1
    }
  ],
  "addons": [
    {
      "code": "mail",
      "name_de": "Mail", "name_en": "Mail",
      "note_de": "Eigene Vereinsadressen", "note_en": "Own club addresses",
      "plugin": null,
      "price_month_chf": "9.00",
      "price_unit": "flat",
      "included_in": ["starter"]
    }
  ]
}
```

* Prices are strings with two decimals. `null` means "on request"
  (`price_month_chf`) or "no yearly price" (`price_year_chf`).
* A limit of `null` means unlimited.
* Plans come sorted by `sort`; `highlighted` marks the recommended one.
* `addons[].plugin` is the plugin id when the add-on comes from a plugin.
* `plans[].modules` are the modules that come with the plan. `included:
  true` (`price_chf` `null`) means at no extra cost; otherwise `price_chf`
  is what the module costs per month in that plan, per `unit`.
* Every module price has a unit (`unit` on a plan module, `price_unit` on
  an add-on): `flat` (once per club), `member` (each member that is not
  archived) or `license` (each licence the club takes).
* `addons[].included_in` lists the keys of the public plans that include
  the add-on, so the site can say "in Growth included".

## GET /api/v1/public/plugins

The plugins installed on this platform, from the signed marketplace index:

```json
{
  "plugins": [
    {
      "id": "discord", "name": "Discord", "description": "…",
      "version": "2.4.0", "author": "Hubra", "tags": ["chat"],
      "official": true,
      "modules": [
        {
          "code": "discord", "price_month_chf": "5.00", "price_unit": "flat",
          "included_in": ["growth"]
        }
      ]
    }
  ]
}
```

`modules[].price_month_chf` is the public add-on price, or `null`;
`price_unit` is its unit (`null` when the add-on is not public), and
`included_in` the public plans that include the module.
