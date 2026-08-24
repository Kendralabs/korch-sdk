# Korchestrator SDK — Documentation Site Deployment

Short reference for the publicly hosted documentation site: where it lives, how it is
deployed, and how to install the SDK itself.

## Live link

**https://koe.kendralabs.com/docs/** — Korchestrator SDK documentation (installation,
quickstart, tutorials, API reference, architecture, versioning, releases, FAQ,
troubleshooting).

The documentation is served as a sub-path of the [KOE ecosystem
site](https://koe.kendralabs.com), the Kendra Labs developer entry point, which links here as
the SDK's documentation. The two are deployed independently — nginx answers `/docs/` from a
static directory on disk and never proxies it to the KOE application, and the KOE application
deliberately defines no `/docs` route — so either can be redeployed without touching the
other.

> **Migration status: live.** Public ingress is done. `koe-proxy` (nginx) listens on
> `0.0.0.0:8080`; Cloudflare terminates TLS for `koe.kendralabs.com` and connects back to
> this port via an Origin Rule (8080 is one of Cloudflare's supported origin ports — 5888,
> the old port, is not, which is why that link stopped working). `ufw` admits only
> Cloudflare's published IP ranges to 8080, so the origin cannot be reached directly by IP to
> bypass the edge. Re-verified 2026-08-24 from outside the VPS, over the real internet:
> `https://koe.kendralabs.com/docs/`, `/installation/`, `/quickstart/`, `/reference/`,
> `/tutorials/` all return `200` with valid Cloudflare-issued TLS.
>
> The content currently live predates a same-day round of documentation fixes (stale
> release-status claims, a new Contributing/Feedback page) — redeploy with the command below
> to publish them. Steps 5–7 in [Cutting over](#cutting-over-from-port-5888) (decommissioning
> the old `:5888` container) are still outstanding.

## Why it moved

The documentation was originally published from its own container at
`http://koe.kendralabs.com:5888`. That worked, but had three problems worth fixing before a
public beta:

- **No TLS.** Every link shared with a user was plain HTTP.
- **A port number in the URL.** `koe.kendralabs.com:5888` is not a URL anyone wants in a
  README, and some corporate networks block non-standard ports outright.
- **Disconnected from the ecosystem.** Nothing linked the docs to the rest of Kendra Labs, or
  the rest of Kendra Labs to the docs.

Serving the same static build at `https://koe.kendralabs.com/docs/` fixes all three at once:
one origin for the site and its documentation, one certificate covering both, no new DNS
record, and the same shape Kendra Nexus already uses for its own documentation at
`nexus.kendralabs.com/docs`. (That certificate does not exist yet — issuing it is part of
the public-ingress step below.)

## How it is built and deployed

1. **Build.** `mkdocs build --strict` produces a static `site/` directory (~4.2 MB).
2. **Transfer.** The build is copied to the VPS at `/opt/korch-sdk-docs/site/`.
3. **Serve.** The `koe-proxy` container mounts that directory read-only and serves it at
   `/docs/`, with long-lived caching on the hashed assets and revalidation on the HTML.
   The configuration is `deploy/nginx.conf` in the KOE repository.

Nothing in the KOE deployment has to change when the documentation is rebuilt: the proxy
reads the directory directly, so a new build is live as soon as it is copied.

### Redeploying an updated build

From the repository root:

```bash
mkdocs build --strict
scp -r site/* vps:/opt/korch-sdk-docs/site/
```

No container restart is needed — nginx serves the directory directly. (`vps` is an SSH config
alias; substitute the real host/user/key if running from elsewhere.)

The SDK's own GitHub Pages workflow (`.github/workflows/docs.yml`) continues to publish the
same content on every push to `main`, unaffected by any of this. `site_url` in `mkdocs.yml`
points at `koe.kendralabs.com/docs/` because that is the address the ecosystem advertises.

### Cutting over from port 5888

Steps 1–4 are done:

1. ~~The KOE stack is deployed at `/opt/koe`~~ — done.
2. ~~Serves this documentation at `/docs/` internally~~ — done.
3. ~~Give `koe.kendralabs.com` public ingress~~ — done via a Cloudflare Origin Rule to
   `koe-proxy`'s `0.0.0.0:8080` (not the `127.0.0.1:5100` originally planned — `5100` is the
   `koe` Next.js app's own internal port, which `koe-proxy` fronts; `8080` is the port
   Cloudflare's Origin Rule actually targets, chosen because it's one of Cloudflare's
   supported origin ports). `ufw` restricts `8080` to Cloudflare's published ranges only.
4. ~~Confirm `https://koe.kendralabs.com/docs/` serves the site~~ — re-verified 2026-08-24
   from outside the VPS: `/`, `/installation/`, `/quickstart/`, `/reference/`, `/tutorials/`
   all return `200` over valid HTTPS.

Steps 5–7 are also done, as of 2026-08-24:

5. ~~Stop and remove the old Compose project~~ — done (`docker compose down` at
   `/opt/korch-sdk-docs`; the `site/` directory was left in place, since `koe-proxy` reads it
   directly).
6. ~~Close port `5888` in `ufw`~~ — done (both the IPv4 and IPv6 rules, which were already
   labeled "retire after koe ingress," removed). Confirmed `http://koe.kendralabs.com:5888/`
   no longer connects. **Hostinger panel firewall** (hPanel, separate from `ufw`) was not
   checked from this session — verify there directly if it also has a rule for 5888.
7. ~~Update any link still pointing at `:5888`~~ — repo-wide grep found no live links, only
   historical mentions explaining why the port stopped working (this file, the engineering
   log, `PROJECT_STATE.md`).

### Known limitations

- **Manual redeploy.** No CI/CD automates the build-and-copy step above; it is a manual
  command run after documentation changes.
- **Single instance, no monitoring.** One VPS, no uptime checks beyond nginx itself.

## Repository

**https://github.com/Kendralabs/korch-sdk** (private) — branches `dev` (integration) →
`staging` (release candidate) → `main` (released, default branch; tags cut from here only).

## Package / release

Not published to PyPI — the repository is private and stays that way for now ([ADR
0020](docs/adr/0020-private-distribution-defers-pypi-publishing.md)). Releases are published
as **GitHub Releases** on the repository instead, built and verified automatically on every
version tag (`.github/workflows/release.yml`).

**Latest release:** [`v0.1.0`](https://github.com/Kendralabs/korch-sdk/releases/tag/v0.1.0) —
assets: `korchestrator-0.1.0-py3-none-any.whl`, `korchestrator-0.1.0.tar.gz`, `SHA256SUMS`.

### Installing it

Requires a GitHub credential (SSH key or PAT) with read access to this private repository.

**From the tagged release** (no local clone needed):

```bash
pip install "korchestrator[dspy] @ git+https://github.com/Kendralabs/korch-sdk.git@v0.1.0"
# or, every optional extra:
pip install "korchestrator[all] @ git+https://github.com/Kendralabs/korch-sdk.git@v0.1.0"
```

**From a local clone** (editable install, e.g. for development):

```bash
git clone git@github.com:Kendralabs/korch-sdk.git && cd korch-sdk
pip install -e '.[dspy]'      # cognitive layer (agents, compiled signatures) — most users need this
pip install -e '.[all]'       # everything
```

**Verify:**

```bash
python -c "import korchestrator; print(korchestrator.__version__)"   # 0.1.0
```

Full install/extras reference: [docs/installation.md](docs/installation.md) (also on the live
documentation site above).
