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

> **Migration status.** The `/docs` arrangement is defined in the KOE repository at
> `deploy/nginx.conf`. Until it is applied on the VPS, the documentation remains reachable at
> its previous address, `http://koe.kendralabs.com:5888` — plain HTTP on a non-standard port.
> See [Cutting over](#cutting-over-from-port-5888) below.

## Why it moved

The documentation was originally published from its own container at
`http://koe.kendralabs.com:5888`. That worked, but had three problems worth fixing before a
public beta:

- **No TLS.** Every link shared with a user was plain HTTP.
- **A port number in the URL.** `koe.kendralabs.com:5888` is not a URL anyone wants in a
  README, and some corporate networks block non-standard ports outright.
- **Disconnected from the ecosystem.** Nothing linked the docs to the rest of Kendra Labs, or
  the rest of Kendra Labs to the docs.

Serving the same static build at `https://koe.kendralabs.com/docs/` fixes all three at once,
reuses the certificate the ecosystem site already has, needs no new DNS record, and matches
how Kendra Nexus already serves its own documentation at `nexus.kendralabs.com/docs`.

## How it is built and deployed

1. **Build.** `mkdocs build --strict` produces a static `site/` directory (~4.2 MB).
2. **Transfer.** The build is copied to the VPS at `/opt/korch-sdk-docs/site/`.
3. **Serve.** nginx serves that directory at `/docs/` on the `koe.kendralabs.com` server
   block, with long-lived caching on hashed assets and revalidation on the HTML.

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

The steps to retire the standalone container, in order:

1. Apply `deploy/nginx.conf` from the KOE repository on the VPS and reload nginx.
2. Confirm `https://koe.kendralabs.com/docs/` serves the site, and that in-page navigation,
   search, and static assets all resolve.
3. Stop and remove the old Compose project at `/opt/korch-sdk-docs/docker-compose.yml`. The
   `site/` directory stays — nginx now reads it directly.
4. Close port `5888` in both the Hostinger panel firewall and the server's `ufw`.
5. Update any link still pointing at `:5888`.

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
