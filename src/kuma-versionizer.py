#!/usr/bin/env python3
"""
Sync Uptime Kuma monitor tags with versions fetched from HTTP endpoints.

Features:
  - Polls each configured service endpoint for its reported version
  - Ensures the matching `<tagPrefix>-<version>` tag exists in Uptime Kuma
  - Removes stale version tags from the monitor so only the latest remains
  - Designed to run as a stateless CronJob (see the bundled Helm chart)
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from uptime_kuma_api import UptimeKumaApi
from urllib3.util.retry import Retry

DEFAULT_UPTIME_KUMA_URL = 'http://uptime-kuma.uptime-kuma.svc.cluster.local:3001'


@dataclass(frozen=True)
class ServiceConfig:
    """Single service definition provided via SERVICES_CONFIG."""

    monitor_name: str
    version_endpoint: str
    tag_prefix: str = 'Version'

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> 'ServiceConfig':
        monitor_name = str(payload.get('monitorName', '')).strip()
        version_endpoint = str(payload.get('versionEndpoint', '')).strip()
        tag_prefix = str(payload.get('tagPrefix', 'Version')).strip() or 'Version'

        if not monitor_name or not version_endpoint:
            raise ValueError('monitorName and versionEndpoint are required')

        return cls(monitor_name=monitor_name, version_endpoint=version_endpoint, tag_prefix=tag_prefix)


@dataclass(frozen=True)
class Settings:
    """Application runtime settings derived from the environment."""

    uptime_kuma_url: str
    uptime_kuma_username: str
    uptime_kuma_password: str
    verify_ssl: bool
    request_timeout: float
    request_retries: int
    services: List[ServiceConfig]


def _read_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() == 'true'


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        return float(raw)
    except ValueError:
        print(f"⚠ Warning: {name} must be a number. Falling back to {default}.", file=sys.stderr)
        return default


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        return int(raw)
    except ValueError:
        print(f"⚠ Warning: {name} must be an integer. Falling back to {default}.", file=sys.stderr)
        return default


def load_raw_services_config() -> str:
    """Return the raw JSON payload, optionally from a file."""
    config_file = os.getenv('SERVICES_CONFIG_FILE')
    if config_file:
        try:
            with open(config_file, 'r', encoding='utf-8') as handle:
                data = handle.read()
                if data.strip():
                    return data
                print(f"✗ Error: SERVICES_CONFIG_FILE '{config_file}' is empty", file=sys.stderr)
        except OSError as exc:
            print(f"✗ Error reading SERVICES_CONFIG_FILE '{config_file}': {exc}", file=sys.stderr)
        # Fall back to SERVICES_CONFIG if reading from file failed

    return os.getenv('SERVICES_CONFIG', '').strip()


def parse_services_config(raw_config: str) -> List[ServiceConfig]:
    """Parse raw JSON into validated ServiceConfig instances."""
    if not raw_config:
        print("✗ Error: SERVICES_CONFIG (or SERVICES_CONFIG_FILE) is required", file=sys.stderr)
        return []

    try:
        payload = json.loads(raw_config)
    except json.JSONDecodeError as exc:
        print(f"✗ Error parsing SERVICES_CONFIG: {exc}", file=sys.stderr)
        return []

    if not isinstance(payload, list) or not payload:
        print("✗ Error: SERVICES_CONFIG must be a non-empty JSON array", file=sys.stderr)
        return []

    services: List[ServiceConfig] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            print(f"⚠ Warning: Skipping service #{index} because it is not an object", file=sys.stderr)
            continue

        try:
            services.append(ServiceConfig.from_dict(item))
        except ValueError as exc:
            print(f"⚠ Warning: Skipping service #{index}: {exc}", file=sys.stderr)

    if services:
        print(f"✓ Loaded {len(services)} service(s) from configuration")
    else:
        print("✗ Error: no valid services found in configuration", file=sys.stderr)

    return services


def load_settings() -> Settings:
    """Build immutable settings from environment variables."""
    url = os.getenv('UPTIME_KUMA_URL', DEFAULT_UPTIME_KUMA_URL).strip()
    username = os.getenv('UPTIME_KUMA_USERNAME', '').strip()
    password = os.getenv('UPTIME_KUMA_PASSWORD', '').strip()
    verify_ssl = _read_bool('VERIFY_SSL', False)
    request_timeout = _read_float('REQUEST_TIMEOUT', 10.0)
    request_retries = _read_int('REQUEST_RETRIES', 3)
    services = parse_services_config(load_raw_services_config())

    if not username:
        print("✗ Error: UPTIME_KUMA_USERNAME must be set", file=sys.stderr)
        sys.exit(1)

    if not password:
        print("✗ Error: UPTIME_KUMA_PASSWORD must be set", file=sys.stderr)
        sys.exit(1)

    if not services:
        sys.exit(1)

    return Settings(
        uptime_kuma_url=url,
        uptime_kuma_username=username,
        uptime_kuma_password=password,
        verify_ssl=verify_ssl,
        request_timeout=request_timeout,
        request_retries=request_retries,
        services=services,
    )


def build_session(settings: Settings) -> requests.Session:
    """Create a shared HTTP session with retry/backoff settings."""
    session = requests.Session()
    retry = Retry(
        total=max(settings.request_retries, 0),
        connect=max(settings.request_retries, 0),
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({'GET'}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.verify = settings.verify_ssl
    return session


def get_version(version_endpoint: str, session: requests.Session, timeout: float) -> Optional[str]:
    """Fetch the version string from the configured endpoint."""
    try:
        response = session.get(version_endpoint, timeout=timeout)
        response.raise_for_status()
        version = response.text.strip()

        if not version:
            print(f"✗ Error: Version endpoint {version_endpoint} returned an empty body", file=sys.stderr)
            return None

        return version
    except requests.exceptions.RequestException as exc:
        print(f"✗ Error fetching version from {version_endpoint}: {exc}", file=sys.stderr)
        return None


def connect_to_uptime_kuma(url: str, username: str, password: str) -> Optional[UptimeKumaApi]:
    """Connect and authenticate with Uptime Kuma."""
    try:
        print(f"Connecting to Uptime Kuma at {url}...")
        api = UptimeKumaApi(url)
        api.login(username, password)
        print("✓ Connected and authenticated successfully")
        return api
    except Exception as exc:  # pragma: no cover - uptime_kuma_api raises generic exceptions
        print(f"✗ Error connecting: {exc}", file=sys.stderr)
        traceback.print_exc()
        return None


class TagCache:
    """Cache tag lookups to avoid repeated API calls."""

    def __init__(self, api: UptimeKumaApi):
        self.api = api
        tags = api.get_tags()
        self._tags_by_name: Dict[str, Dict[str, Any]] = {tag['name']: tag for tag in tags}
        self._tag_names_by_id: Dict[int, str] = {tag['id']: tag['name'] for tag in tags}

    def get_or_create(self, tag_name: str, tag_color: str = '#3b82f6') -> Optional[Dict[str, Any]]:
        if tag_name in self._tags_by_name:
            tag = self._tags_by_name[tag_name]
            print(f"✓ Found existing tag '{tag_name}' (ID: {tag['id']})")
            return tag

        try:
            print(f"Creating new tag '{tag_name}'...")
            new_tag = self.api.add_tag(name=tag_name, color=tag_color)
            print(f"✓ Created tag '{tag_name}' (ID: {new_tag['id']})")
            self._tags_by_name[tag_name] = new_tag
            self._tag_names_by_id[new_tag['id']] = tag_name
            return new_tag
        except Exception as exc:
            print(f"✗ Error managing tags: {exc}", file=sys.stderr)
            traceback.print_exc()
            return None

    def get_name(self, tag_id: Optional[int]) -> str:
        if tag_id is None:
            return ''
        return self._tag_names_by_id.get(tag_id, '')


def _extract_tag_id(tag: Any) -> Optional[int]:
    """Extract tag ID from various tag formats returned by the API."""
    if isinstance(tag, dict):
        return tag.get('tag_id') or tag.get('id')
    return tag


def update_monitor_tags(
    api: UptimeKumaApi,
    monitor: Dict[str, Any],
    monitor_name: str,
    version: str,
    tag_cache: TagCache,
    tag_prefix: str = 'Version',
) -> bool:
    """Update monitor with version tag."""
    try:
        version_tag_name = tag_prefix or 'Version'
        version_tag = tag_cache.get_or_create(version_tag_name)

        if not version_tag:
            return False

        version_tag_id = version_tag['id']
        print(f"   Using tag ID: {version_tag_id}")

        current_tags = monitor.get('tags', [])
        updated_tags = []
        tag_already_exists = False

        for tag in current_tags:
            tag_id = _extract_tag_id(tag)
            tag_name = tag.get('name') if isinstance(tag, dict) else tag_cache.get_name(tag_id)
            tag_value = tag.get('value', '') if isinstance(tag, dict) else ''
            is_version_tag = (tag_id == version_tag_id) or (tag_name == version_tag_name)

            if is_version_tag:
                if tag_value == version:
                    print(f"   ✓ Tag '{version_tag_name}' already has value '{version}'")
                    tag_already_exists = True
                    updated_tags.append(tag)
                else:
                    print(f"   Removing outdated '{version_tag_name}' tag (value: '{tag_value}')...")
                    if tag_id is not None:
                        try:
                            api.delete_monitor_tag(tag_id=tag_id, monitor_id=monitor['id'])
                        except Exception as exc:
                            print(f"   ⚠ Warning: Could not remove old tag: {exc}")
                continue

            updated_tags.append(tag)

        if not tag_already_exists:
            print(f"   Adding tag '{version_tag_name}' with value '{version}'...")
            api.add_monitor_tag(tag_id=version_tag_id, monitor_id=monitor['id'], value=version)
            updated_tags.append({'id': version_tag_id, 'name': version_tag_name, 'value': version})

        monitor['tags'] = updated_tags

        print(
            f"✓ Successfully updated monitor '{monitor_name}' with tag '{version_tag_name}' "
            f"set to '{version}'"
        )
        return True

    except Exception as exc:
        print(f"✗ Error updating monitor '{monitor_name}': {exc}", file=sys.stderr)
        traceback.print_exc()
        return False


def process_service(
    api: UptimeKumaApi,
    session: requests.Session,
    monitor_map: Dict[str, Dict[str, Any]],
    tag_cache: TagCache,
    service: ServiceConfig,
    request_timeout: float,
) -> bool:
    """Process a single service configuration."""
    print(f"\n📦 Processing service: {service.monitor_name}")

    version = get_version(service.version_endpoint, session, request_timeout)
    if not version:
        return False
    print(f"   ✓ Fetched version: {version}")

    monitor = monitor_map.get(service.monitor_name)
    if not monitor:
        print(f"   ✗ Monitor '{service.monitor_name}' not found", file=sys.stderr)
        return False

    return update_monitor_tags(api, monitor, service.monitor_name, version, tag_cache, service.tag_prefix)


def build_monitor_map(api: UptimeKumaApi) -> Dict[str, Dict[str, Any]]:
    """Return a dictionary of monitors keyed by name."""
    monitors = api.get_monitors()
    print(f"✓ Loaded {len(monitors)} monitor(s) from Uptime Kuma")
    return {monitor['name']: monitor for monitor in monitors}


class VersionSyncer:
    """High-level orchestration for syncing tags."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def run(self) -> bool:
        print(f"\n🚀 Starting version sync for {len(self.settings.services)} service(s)")
        print(f"   Uptime Kuma URL: {self.settings.uptime_kuma_url}\n")

        api = connect_to_uptime_kuma(
            self.settings.uptime_kuma_url,
            self.settings.uptime_kuma_username,
            self.settings.uptime_kuma_password,
        )
        if not api:
            return False

        session = build_session(self.settings)
        try:
            monitor_map = build_monitor_map(api)
            tag_cache = TagCache(api)

            results = [
                process_service(api, session, monitor_map, tag_cache, service, self.settings.request_timeout)
                for service in self.settings.services
            ]

            successful = sum(bool(result) for result in results)
            failed = len(results) - successful

            print(f"\n📊 Summary:")
            print(f"   ✓ Successful: {successful}")
            if failed:
                print(f"   ✗ Failed: {failed}")
                return False

            print("\n✓ All version tags updated successfully")
            return True
        finally:
            session.close()
            try:
                api.disconnect()
                print("Disconnected from Uptime Kuma")
            except Exception:
                pass


def main():
    settings = load_settings()
    syncer = VersionSyncer(settings)
    success = syncer.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
