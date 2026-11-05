# hubra-cli

`hubra_gh.py` is one command for the hubra-app GitHub repos and the running
Hubra: status of every repo, pull requests, merges, plugin releases, signing
approvals, and Hubra's health, alerts, errors and jobs. `hubra_gh.py tui`
shows all of it on one full-screen view.

Needs Python 3.9+ and the [gh CLI](https://cli.github.com) logged in as an
owner of hubra-app. The TUI also needs Textual (`pip install -r
requirements.txt`); everything else uses only the standard library.

```sh
python hubra_gh.py status                  # every repo in one table (one GraphQL query)
python hubra_gh.py prs                     # every open PR with checks, review, link
python hubra_gh.py pr budgets#12 --diff    # one PR in depth
python hubra_gh.py merge budgets#12        # auto-merge one PR (--now, --ready)
python hubra_gh.py ship                    # merge ready plugin PRs, then release
python hubra_gh.py approve                 # approve signing runs waiting for you
python hubra_gh.py runs --failed           # recent failed Actions runs
python hubra_gh.py login                   # save a Hubra API token
python hubra_gh.py hubra health            # also: alerts, errors, jobs, whoami, get PATH
python hubra_gh.py tui                     # everything on one screen
```

`python hubra_gh.py --help` explains every command. `--dry-run` shows what
would change without changing anything.

## Hubra API

`hubra …` and the TUI's Hubra tab read the running Hubra with an API token
(manage › API-Tokens; a read-only platform token with `platform.diagnostics`
is enough). `login` keeps it in `~/.config/hubra/token`, readable only by you;
`HUBRA_TOKEN` overrides it. `HUBRA_API_URL` (default `https://api.hubra.club`)
and `HUBRA_MANAGE_URL` point at another install.

## TUI keys

`r` refresh · `o` open in browser · `m` auto-merge · `M` merge now · `y` mark
ready · `d` diff · `R` release · `a` approve signing · `q` quit. Every change
asks first.

## Testing without GitHub

`tests/fake_gh` stands in for gh with a made-up org, and `tests/fake_hubra.py`
for the Hubra API:

```sh
mkdir -p /tmp/fakebin && ln -sf "$PWD/tests/fake_gh" /tmp/fakebin/gh
python tests/fake_hubra.py 8765 &
export PATH=/tmp/fakebin:$PATH HUBRA_API_URL=http://127.0.0.1:8765 \
       HUBRA_TOKEN=hbr_plat_AAAAAAAAAAAA_BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB
python hubra_gh.py status && python hubra_gh.py ship --dry-run
```
