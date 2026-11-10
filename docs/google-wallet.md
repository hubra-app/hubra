# Member badge in Google Wallet

Members can save their member badge (sso › My account › Profile) as a pass in
Google Wallet. Hubra is the one issuer for every club: one issuer account,
one generic pass class, and one pass per person.

The pass shows the person's name, the badge number as text and QR code, and
the names of their clubs. Code: `app/backend/hubra/core/services/google_wallet.py`.

Google charges nothing for the Wallet API. The only limit is 20 calls per
second ([FAQ](https://developers.google.com/wallet/generic/resources/faq)).

## Setup

1. **Issuer account.** In the [Google Pay & Wallet Console](https://pay.google.com/business/console)
   fill in the business profile and note the **issuer id** (a long number).
2. **Generic class.** Google Wallet API › Create a generic class. Class id
   e.g. `hubra`, "Multiple devices and holders" = one user, all devices.
   Leave the modules empty (a link module "Mein Konto" to
   `https://<sso>/account/profil` is fine). Logo, colour and texts are set
   per pass by Hubra.
3. **Service account.** In a Google Cloud project, enable the
   [Google Wallet API](https://console.cloud.google.com/apis/library/walletobjects.googleapis.com),
   create a service account (no roles) and a **JSON key** for it.
4. **Give it access.** Wallet Console › Users: invite the service account's
   e-mail with the **Developer** role.
5. **Hubra.** manage › Services › Google Wallet: issuer id, class id, and
   paste the whole JSON key (stored encrypted). Optional: a logo URL (square
   PNG, 660 px recommended; default is the sign-in site's `icon-512.png`).

With all three set, My Account shows **Add to Google Wallet** under the
badge.

## Demo mode and going live

A new issuer account is in demo mode: only the console's admins, developers
and **test accounts** (Wallet Console › Test accounts) can save the pass, and
it says "[TEST ONLY]". When it works, click **Request publishing access** in
the console; Google reviews the business profile
([docs](https://developers.google.com/wallet/generic/test-and-go-live/request-publishing-access)).

## Keeping passes current

A Wallet pass can't be deleted, only changed. Hubra keeps the pass's id and a
hash of what it shows on the account (`users.google_wallet_object`,
`users.google_wallet_hash`) and patches the pass when it changes:

- after a member joins or leaves a club, and after a name or language change
  on My Account (a worker job right after the change);
- nightly at 03:50 UTC (`google-wallet-passes-nightly`) for everything else,
  e.g. a club renamed. Unchanged passes cost no call.

A disabled or deleted account's pass is set to `INACTIVE`, without name and
clubs; it moves to the expired passes on the phone.

## Button

The button is Google's own artwork (black, not to be restyled), in
`app/sso-frontend/public/google-wallet/add-{de,en}.svg`. It follows the
[brand guidelines](https://developers.google.com/wallet/generic/resources/brand-guidelines):
48 px high where it fits, scaled as a whole, 8 px clear space. To refresh
it, take the SVGs from Google's
[button download](https://developers.google.com/static/wallet/download-assets/add-to-wallet-svg.zip).

## Self-hosted installs

Each install needs its own issuer account and key; passes signed by one
issuer can't be issued from another. Without the settings the button is
hidden and nothing talks to Google.
