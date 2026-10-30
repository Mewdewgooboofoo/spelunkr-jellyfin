import json
import math
import os
import tempfile
import urllib.request
from pathlib import Path

DATA_DIR = Path("/data")
LINEUP_PATH = DATA_DIR / "spelunkr-lineup.json"

UPSTREAMS = [
    "https://jbuopkuluyfjwgsrigry.supabase.co/storage/v1/object/public/broadcast/",
    "https://data.spelunkr.tv/",
]

TIMEOUT = 30


def download(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Spelunkr-Jellyfin-Updater/1.0"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def fetch_upstream(path):
    errors = []

    for base in UPSTREAMS:
        try:
            return download(base + path)
        except Exception as error:
            errors.append(f"{base}: {error}")

    raise RuntimeError(
        f"Could not download {path}: " + "; ".join(errors)
    )


def validate_json(content, description):
    try:
        return json.loads(content)
    except Exception as error:
        raise ValueError(f"Invalid JSON in {description}: {error}")


def require_string(value, description):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{description} must be a non-empty string")


def require_number(value, description):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{description} must be a positive finite number")


def validate_lineup(lineup):
    if not isinstance(lineup, dict):
        raise ValueError("Lineup must be a JSON object")

    channels = lineup.get("channels")

    if not isinstance(channels, list) or not channels:
        raise ValueError("Lineup contains no channels")

    channel_ids = set()
    manifest_paths = set()

    for channel_index, channel in enumerate(channels):
        label = f"Channel {channel_index + 1}"

        if not isinstance(channel, dict):
            raise ValueError(f"{label} must be an object")

        require_string(channel.get("id"), f"{label} ID")
        require_string(channel.get("name"), f"{label} name")

        if channel["id"] in channel_ids:
            raise ValueError(f"Duplicate channel ID: {channel['id']}")

        channel_ids.add(channel["id"])

        versions = channel.get("versions")

        if not isinstance(versions, list) or not versions:
            raise ValueError(f"{label} has no valid versions list")

        for version_index, version in enumerate(versions):
            version_label = (
                f"{label} version {version_index + 1}"
            )

            if not isinstance(version, dict):
                raise ValueError(f"{version_label} must be an object")

            version_number = version.get("v")

            if (
                isinstance(version_number, bool)
                or not isinstance(version_number, int)
                or version_number <= 0
            ):
                raise ValueError(
                    f"{version_label} has an invalid version number"
                )

            require_number(
                version.get("effectiveAtMs"),
                f"{version_label} effectiveAtMs",
            )

            start_index = version.get("startIndex")

            if (
                isinstance(start_index, bool)
                or not isinstance(start_index, int)
                or start_index < 0
            ):
                raise ValueError(
                    f"{version_label} has an invalid startIndex"
                )

            manifest_path = version.get("manifest")
            require_string(manifest_path, f"{version_label} manifest")

            path = Path(manifest_path)

            if (
                not manifest_path.startswith("manifests/")
                or path.is_absolute()
                or "\\" in manifest_path
                or ".." in path.parts
                or "." in path.parts
                or "" in path.parts
            ):
                raise ValueError(
                    f"Unsafe manifest path: {manifest_path}"
                )

            manifest_paths.add(manifest_path)

    return channels, manifest_paths


def validate_manifest(manifest, manifest_path):
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path} must contain a JSON object")

    items = manifest.get("items")

    if not isinstance(items, list) or not items:
        raise ValueError(
            f"{manifest_path} has no valid items list"
        )

    for item_index, item in enumerate(items):
        label = f"{manifest_path}, item {item_index + 1}"

        if not isinstance(item, dict):
            raise ValueError(f"{label} must be an object")

        item_id = item.get("id")
        require_string(item_id, f"{label} ID")

        filename = item.get("mp4") or item.get("file")
        require_string(filename, f"{label} media filename")

        duration_ms = item.get("durationMs")

        if duration_ms is not None:
            require_number(duration_ms, f"{label} durationMs")
        else:
            require_number(item.get("duration"), f"{label} duration")

    return items


def atomic_write(destination, content):
    destination.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary_path = tempfile.mkstemp(
        dir=destination.parent,
        prefix=".spelunkr-",
    )

    try:
        with os.fdopen(fd, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary_path, destination)

    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


def main():
    print("Checking Spelunkr upstream lineup...", flush=True)

    lineup_content = fetch_upstream("lineup.json")
    lineup = validate_json(lineup_content, "lineup.json")

    channels, manifest_paths = validate_lineup(lineup)

    print(
        f"Found {len(channels)} channels and "
        f"{len(manifest_paths)} manifests.",
        flush=True,
    )

    manifests = {}

    for index, manifest_path in enumerate(
        sorted(manifest_paths), start=1
    ):
        content = fetch_upstream(manifest_path)
        manifest = validate_json(content, manifest_path)
        items = validate_manifest(manifest, manifest_path)

        manifests[manifest_path] = (content, len(items))

        print(
            f"[{index}/{len(manifest_paths)}] "
            f"Validated {manifest_path}: {len(items)} items",
            flush=True,
        )

    for channel in channels:
        for version in channel["versions"]:
            manifest_path = version["manifest"]
            item_count = manifests[manifest_path][1]

            if version["startIndex"] >= item_count:
                raise ValueError(
                    f"Channel {channel['id']} version {version['v']} "
                    f"has startIndex {version['startIndex']}, "
                    f"but its manifest only has {item_count} items"
                )

    print("All validation checks passed. Installing data...", flush=True)

    for manifest_path, (content, _) in manifests.items():
        atomic_write(DATA_DIR / manifest_path, content)

    atomic_write(LINEUP_PATH, lineup_content)

    print(
        f"Update complete. Installed {len(manifests)} manifests "
        f"for {len(channels)} channels.",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Update failed: {error}", flush=True)
        raise
