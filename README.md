# kuma-versionizer

Automatically fetches each service’s reported version, turns it into a tag, and keeps the matching [Uptime Kuma](https://github.com/louislam/uptime-kuma) monitor updated—so your dashboard always shows the live version without manual tweaks.

## What it does
- Polls configurable version endpoints (e.g. `/static/version.txt`) for every service you care about
- Creates or reuses `tagPrefix-<version>` tags inside Uptime Kuma
- Removes stale version tags from each monitor so only the current release is visible
- Runs as a lightweight CronJob inside Kubernetes

## Repository layout
```
.
├── Dockerfile          # Prebuilt image for the cron job
├── src/
│   └── kuma-versionizer.py
└── chart/
    ├── Chart.yaml
    ├── values.yaml
    └── templates/
```

## Build and publish the container image
```bash
# From the repo root
IMAGE=ghcr.io/<org>/kuma-versionizer:latest

docker build -t "$IMAGE" -f Dockerfile .
docker push "$IMAGE"
```
Update `chart/values.yaml` (or your own override file) with the image reference you just pushed.

## Helm quick start
```bash
helm upgrade --install kuma-versionizer ./chart \
  --namespace version-sync --create-namespace \
  --set image.repository=ghcr.io/<org>/kuma-versionizer \
  --set image.tag=latest
```
You also need an `uptime-kuma-credentials` secret in the same namespace that holds the username/password used by the job.

### Configure services
In `values.yaml`, add entries under `services`:
```yaml
services:
  - monitorName: "webapp-color"
    versionEndpoint: "http://webapp-color.webapp-color.svc.cluster.local/static/version.txt"
    tagPrefix: "version"   # optional; defaults to "version"
```
Each monitor name must match the corresponding name inside Uptime Kuma.

## Developing locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install requests uptime-kuma-api
export SERVICES_CONFIG='[{"monitorName":"example","versionEndpoint":"http://example/version.txt"}]'
python src/kuma-versionizer.py
```
Provide the required `UPTIME_KUMA_*` env vars (see the script header) plus a `SERVICES_CONFIG` JSON payload when running locally.

## Roadmap
- GitHub Actions workflow to lint, build, and publish the image
- Optional ConfigMap support for service definitions that exceed env-var limits
- Support for token-based Uptime Kuma auth

Contributions and feedback are welcome!

