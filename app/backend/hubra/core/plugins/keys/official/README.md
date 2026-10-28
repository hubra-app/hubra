# Official plugin key

Plugins signed with a key in this folder count as **official**, and the
repository in `index.url` is added to every Hubra as the official
Marketplace (once; a manager who removes it keeps it removed).

Neither is set up yet. To set them up:

1. `flask plugins keygen hubra-project.pem` — keep `hubra-project.pem`
   secret (a GitHub Actions secret `HUBRA_SIGNING_KEY` in the marketplace
   repository), and commit `hubra-project.pem.pub` here.
2. Publish the marketplace (see `plugins/README.md`) and write the URL of its
   `index.json` into `index.url`.

`HUBRA_OFFICIAL_INDEX` overrides `index.url` at runtime.
