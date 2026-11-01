# Official keys

Every key has one purpose.

- `*.pub` in this folder are **plugin keys**: plugins signed with one count
  as **official**. The file name is the signer's name shown to managers.
- `index/*.pub` are **index keys**: they sign the official Marketplace's
  `index.json` and nothing else. While `index/` holds no key, the plugin
  key signs the index too (the old format).
- `index.url`: the official marketplace, <https://plugins.hubra.club/index.json>.
  hubra-app/hubra-plugins builds it from the releases of the hubra-plugin-*
  repositories and publishes it with GitHub Pages. It is added to every
  Hubra as the official Marketplace (once; a manager who removes it keeps
  it removed), with the index key and plugin keys from this folder.

Keys:

- `Hubra.pub`: the project's plugin key, id `b84edc01a8b17490` (added
  2026-10-28). Its private key is the `HUBRA_SIGNING_KEY` secret of the
  "plugin-signing" environment in each hubra-plugin-* repository.
- `index/`: the index key. Its private key is the `HUBRA_INDEX_KEY` secret of
  the "plugin-signing" environment in hubra-app/hubra-plugins, which then
  holds no plugin key.

To add a key: `flask plugins keygen <name>.pem`, keep the `.pem` secret, and
commit `<name>.pem.pub` here (plugin key) or in `index/` (index key) as
`<name>.pub`. Never use one key for both.

`HUBRA_OFFICIAL_INDEX` overrides `index.url` at runtime.
