
import json

import os

import tempfile

import time

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

            content = download(base + path)

            return content

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



    channels = lineup.get("channels")

    if not isinstance(channels, list) or not channels:

        raise ValueError("Lineup contains no channels")



    manifests = {}



    for channel in channels:

        for version in channel.get("versions", []):

            manifest_path = version.get("manifest")



            if not manifest_path:

                continue



            if not manifest_path.startswith("manifests/"):

                raise ValueError(

                    f"Unexpected manifest path: {manifest_path}"

                )



            if ".." in Path(manifest_path).parts:

                raise ValueError(

                    f"Unsafe manifest path: {manifest_path}"

                )



            manifests[manifest_path] = None



    print(

        f"Found {len(channels)} channels and "

        f"{len(manifests)} manifests.",

        flush=True,

    )



    for index, manifest_path in enumerate(manifests, start=1):

        content = fetch_upstream(manifest_path)

        manifest = validate_json(content, manifest_path)



        if not isinstance(manifest.get("items"), list):

            raise ValueError(

                f"{manifest_path} has no valid items list"

            )



        manifests[manifest_path] = content



        print(

            f"[{index}/{len(manifests)}] Validated {manifest_path}",

            flush=True,

        )



    for manifest_path, content in manifests.items():

        destination = DATA_DIR / manifest_path

        atomic_write(destination, content)



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

