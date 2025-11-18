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

### Automated via GitHub Actions (Recommended)
The repository includes a GitHub Actions workflow that automatically builds and pushes the Docker image to GitHub Container Registry (GHCR) when you:
- Push to the `main` branch (creates `latest` tag)
- Create a version tag (e.g., `v1.0.0`)

**Setup:**
1. Enable GitHub Actions in your repository
2. Ensure GitHub Packages are enabled
3. Push to `main` or create a tag: `git tag v1.0.0 && git push --tags`
4. The image will be available at `ghcr.io/<your-username>/kuma-versionizer:latest`

Update `chart/values.yaml` with your GitHub username:
```yaml
image:
  repository: ghcr.io/<your-username>/kuma-versionizer
  tag: latest
```

### Manual build (Alternative)
```bash
# From the repo root
IMAGE=ghcr.io/<org>/kuma-versionizer:latest

docker build -t "$IMAGE" -f Dockerfile .
docker push "$IMAGE"
```

## Helm quick start

### 1. Create the Uptime Kuma credentials secret
```bash
kubectl create secret generic uptime-kuma-credentials \
  --from-literal=username=<your-username> \
  --from-literal=password=<your-password> \
  --namespace version-sync
```

### 2. Install the Helm chart
```bash
helm upgrade --install kuma-versionizer ./chart \
  --namespace version-sync --create-namespace \
  --set image.repository=ghcr.io/<your-username>/kuma-versionizer \
  --set image.tag=latest \
  --set uptimeKuma.url=http://uptime-kuma.uptime-kuma.svc.cluster.local:3001
```

Or create a `values-override.yaml`:
```yaml
image:
  repository: ghcr.io/<your-username>/kuma-versionizer
  tag: latest

uptimeKuma:
  url: "http://uptime-kuma.uptime-kuma.svc.cluster.local:3001"

services:
  - monitorName: "My Service"
    versionEndpoint: "http://myservice.namespace.svc.cluster.local/version.txt"
    tagPrefix: "version"
```

Then install:
```bash
helm upgrade --install kuma-versionizer ./chart \
  --namespace version-sync --create-namespace \
  -f values-override.yaml
```

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
- Optional ConfigMap support for service definitions that exceed env-var limits
- Support for token-based Uptime Kuma auth
- Multi-architecture support (amd64, arm64)

Contributions and feedback are welcome!

