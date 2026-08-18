# Korchestrator SDK — Documentation Site Deployment

Short reference for the live, publicly hosted documentation site: what it is, how it got there, and how to install the SDK itself.

## Live link

**https://koe.kendralabs.com:5888** — Korchestrator SDK docs (installation, quickstart, tutorials, API reference, architecture, versioning, releases, FAQ, troubleshooting)

> Plain HTTP over a non-standard port, not HTTPS — see [Known limitations](#known-limitations) below.

## What was done

The SDK's existing MkDocs documentation source (`docs/`, built via `mkdocs.yml`) was built into a static site and deployed to a VPS as its own, independent, containerized web app — separate from the SDK's own GitHub Pages deploy (`.github/workflows/docs.yml`, which continues to publish the same content to GitHub Pages on every push to `main`, unaffected by any of this).

## How it was done

1. **Build.** `mkdocs build --strict` locally, producing a static `site/` directory (~4.2 MB).
2. **Transfer.** Site copied to the VPS at `/opt/korch-sdk-docs/site/` over SSH/`scp`.
3. **Serve.** A `docker-compose.yml` at `/opt/korch-sdk-docs/` runs one service — `nginx:1.27-alpine`, bind-mounting `./site` read-only, `restart: unless-stopped`. It's a fully standalone Compose project: own container, own network, no dependency on or interference with anything else on the box.
4. **Expose.** The container publishes host port `5888`, opened as an `Accept / TCP / 5888 / Any` rule in the VPS provider's (Hostinger) panel-level network firewall — a separate layer from the server's own `ufw`, which was also opened for this port.
5. **DNS.** `koe.kendralabs.com` → the VPS's IP, an `A` record (**DNS only** / not proxied through Cloudflare — the port-forwarding needed here isn't compatible with Cloudflare's default proxy).

### Redeploying an updated build

From the repo root, after `mkdocs build --strict`:

```bash
scp -r site/* vps:/opt/korch-sdk-docs/site/
ssh vps 'cd /opt/korch-sdk-docs && docker compose restart'
```

(`vps` is an SSH config alias; substitute the real host/user/key if running from elsewhere.)

### Known limitations

- **No TLS.** The site is served over plain HTTP; the URL includes `:5888` rather than a clean HTTPS origin. A follow-up (e.g. a Cloudflare Tunnel, giving `https://koe.kendralabs.com` with no port and free TLS) would remove both limitations at once but has not been done.
- **Single instance, no monitoring/alerting.** One container, one VPS, no uptime checks configured beyond Docker's own `restart: unless-stopped`.
- **Manual redeploy.** No CI/CD automates the build-and-push step above; it's a manual command run after doc changes.

## Repository

**https://github.com/Kendralabs/korch-sdk** (private) — branches `dev` (integration) → `staging` (release candidate) → `main` (released, default branch; tags cut from here only).

## Package / release

Not published to PyPI — the repository is private and stays that way ([ADR 0020](docs/adr/0020-private-distribution-defers-pypi-publishing.md)). Releases are published as **GitHub Releases** on the repo instead, built and verified automatically on every version tag (`.github/workflows/release.yml`).

**Latest release:** [`v0.1.0`](https://github.com/Kendralabs/korch-sdk/releases/tag/v0.1.0) — assets: `korchestrator-0.1.0-py3-none-any.whl`, `korchestrator-0.1.0.tar.gz`, `SHA256SUMS`.

### Installing it

Requires a GitHub credential (SSH key or PAT) with read access to this private repo.

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

Full install/extras reference: [docs/installation.md](docs/installation.md) (also on the live docs site above).
