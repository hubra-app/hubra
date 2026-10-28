# Official plugin key

Plugins signed with a key in this folder count as **official**, and the
repository in `index.url` is added to every Hubra as the official
Marketplace (once; a manager who removes it keeps it removed). The file
name is the signer's name shown to managers.

- `Hubra.pub`: the project's key, id `b84edc01a8b17490` (added 2026-10-28).
  Its private key is kept outside the repository; it is the GitHub Actions
  secret `HUBRA_SIGNING_KEY` of hubra-app/hubra-plugins and the
  hubra-plugin-* repositories (an organisation secret).
- `index.url`: the official marketplace, <https://plugins.hubra.club/index.json>.
  hubra-app/hubra-plugins builds it from the releases of the hubra-plugin-*
  repositories and publishes it with GitHub Pages.

To replace or add a key: `flask plugins keygen <name>.pem`, keep the `.pem`
secret, and commit `<name>.pem.pub` here as `<name>.pub`.

`HUBRA_OFFICIAL_INDEX` overrides `index.url` at runtime.
