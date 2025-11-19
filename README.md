# kuma-versionizer

Automatically fetches each service’s reported version, turns it into a tag, and keeps the matching [Uptime Kuma](https://github.com/louislam/uptime-kuma) monitor updated—so your dashboard always shows the live version without manual tweaks.

## Features
- Poll configurable endpoints (e.g. `/static/version.txt`) for any number of services
- Create or reuse `tagPrefix-<version>` tags in Uptime Kuma and remove stale ones
- Ship as a tiny Kubernetes CronJob

## Repository layout
```
.
├── Dockerfile
├── src/
│   └── kuma-versionizer.py
└── chart/
    ├── Chart.yaml
    ├── values.yaml
    └── templates/
```

## Container image

### GitHub Actions (recommended)
A workflow in `.github/workflows` builds and pushes to GHCR whenever you:
- push to `main` → publishes `:latest`
- push a git tag (e.g. `v1.0.0`) → publishes the matching tag

Setup is just enabling Actions + GitHub Packages, then pushing as usual. Images land at `ghcr.io/<user-or-org>/kuma-versionizer`.

### Manual build
```bash
IMAGE=ghcr.io/<org>/kuma-versionizer:latest
docker build -t "$IMAGE" -f Dockerfile .
docker push "$IMAGE"
```

Point the Helm chart (or any deployment) at your repo/tag by updating `image.repository` and `image.tag`.

## Helm quick start

1. Create the credentials secret:
   ```bash
   kubectl create secret generic uptime-kuma-credentials \
     --from-literal=username=<your-username> \
     --from-literal=password=<your-password> \
     --namespace kuma-versionizer
   ```

Each `monitorName` must match an existing monitor in Uptime Kuma.


## Develop locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # or requests + uptime-kuma-api

export UPTIME_KUMA_URL=http://localhost:3001
export UPTIME_KUMA_USERNAME=<user>
export UPTIME_KUMA_PASSWORD=<pass>
export SERVICES_CONFIG='[{"monitorName":"example","versionEndpoint":"http://example/version.txt"}]'
# or point to a file:
# export SERVICES_CONFIG_FILE=./services.json

python src/kuma-versionizer.py
```

## Configuration reference
- `UPTIME_KUMA_URL` (default: `http://uptime-kuma.uptime-kuma.svc.cluster.local:3001`)
- `UPTIME_KUMA_USERNAME` (required)
- `UPTIME_KUMA_PASSWORD` (required)
- `VERIFY_SSL` (`true`/`false`, controls TLS verification for version endpoints)
- `SERVICES_CONFIG` JSON array describing services
- `SERVICES_CONFIG_FILE` path to a JSON file containing the same payload (takes precedence over `SERVICES_CONFIG`)
- `REQUEST_TIMEOUT` seconds to wait for each version endpoint (default: `10`)
- `REQUEST_RETRIES` retry attempts for transient HTTP failures (default: `3`)

## Roadmap
- Optional ConfigMap support for service definitions that exceed env-var limits
- Support for token-based Uptime Kuma auth
- Multi-architecture support (amd64, arm64)

Contributions and feedback are welcome!

