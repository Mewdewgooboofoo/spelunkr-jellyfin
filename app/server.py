
import json

import os

import time

import subprocess
import threading

from datetime import datetime, timezone

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from urllib.parse import quote

from xml.sax.saxutils import escape



DATA = "/data"

PORT = 8787

BASE_URL = os.environ.get("BASE_URL", "http://192.168.1.141:8787")



LINEUP_PATH = os.path.join(DATA, "spelunkr-lineup.json")



CHANNELS = {}

lineup = {}

reload_lock = threading.Lock()

last_lineup_mtime = 0





def load_channels():

    with open(LINEUP_PATH) as f:

        new_lineup = json.load(f)



    now_ms = int(time.time() * 1000)

    new_channels = {}



    for channel in new_lineup["channels"]:

        versions = channel["versions"]

        eligible = [v for v in versions if v["effectiveAtMs"] <= now_ms]

        version = max(

            eligible or versions,

            key=lambda v: v["effectiveAtMs"]

        )



        manifest_path = os.path.join(DATA, version["manifest"])



        with open(manifest_path) as f:

            manifest = json.load(f)



        new_channels[channel["id"]] = {

            "id": channel["id"],

            "name": channel["name"],

            "version": version["v"],

            "effectiveAtMs": version["effectiveAtMs"],

            "startIndex": version["startIndex"],

            "items": manifest["items"],

        }



    return new_lineup, new_channels





def maybe_reload_channels():

    global lineup, CHANNELS, last_lineup_mtime



    try:

        current_mtime = os.stat(LINEUP_PATH).st_mtime_ns

    except OSError as error:

        print(f"Could not check lineup file: {error}", flush=True)

        return



    if current_mtime == last_lineup_mtime:

        return



    with reload_lock:

        try:

            current_mtime = os.stat(LINEUP_PATH).st_mtime_ns



            if current_mtime == last_lineup_mtime:

                return



            new_lineup, new_channels = load_channels()



            lineup = new_lineup

            CHANNELS = new_channels

            last_lineup_mtime = current_mtime



            print(

                f"Reloaded lineup: {len(CHANNELS)} channels",

                flush=True

            )



        except Exception as error:

            print(f"Lineup reload failed; keeping current data: {error}", flush=True)





def item_duration(item):
    duration_ms = item.get("durationMs")
    if duration_ms is not None:
        return float(duration_ms) / 1000
    return float(item["duration"])



def cycle_items(channel, cycle):

    items = channel["items"]

    return items[channel["startIndex"]:] if cycle == 0 else items



def cycle_duration(channel, cycle):

    return sum(item_duration(x) for x in cycle_items(channel, cycle))



def locate(channel, timestamp):

    elapsed = max(0, timestamp - channel["effectiveAtMs"] / 1000)



    first_length = cycle_duration(channel, 0)



    if elapsed < first_length:

        cycle = 0

        position = elapsed

    else:

        elapsed -= first_length

        full_length = cycle_duration(channel, 1)

        cycle = 1 + int(elapsed // full_length)

        position = elapsed % full_length



    sequence = cycle_items(channel, cycle)

    cursor = 0



    for index, item in enumerate(sequence):

        duration = item_duration(item)



        if position < cursor + duration:

            return {

                "item": item,

                "offset": position - cursor,

                "remaining": cursor + duration - position,

                "start": timestamp - (position - cursor),

            }



        cursor += duration



    raise RuntimeError("Could not locate programme")



def archive_url(item):

    filename = item.get("mp4") or item.get("file")



    return (

        "https://archive.org/download/"

        + quote(item["id"], safe="")

        + "/"

        + quote(filename, safe="")

    )



def programme_schedule(channel, hours=48):

    now = time.time()

    end = now + hours * 3600

    current = locate(channel, now)

    cursor = current["start"]

    result = []



    while cursor < end:

        item = current["item"]

        duration = item_duration(item)



        result.append((cursor, cursor + duration, item))

        cursor += duration



        if cursor < end:

            current = locate(channel, cursor + 0.01)



    return result



def xmltv_time(timestamp):

    return datetime.fromtimestamp(

        timestamp, timezone.utc

    ).strftime("%Y%m%d%H%M%S +0000")



class Handler(BaseHTTPRequestHandler):



    def log_message(self, fmt, *args):

        print("%s - %s" % (self.address_string(), fmt % args), flush=True)



    def send_text(self, content, content_type):

        data = content.encode()

        self.send_response(200)

        self.send_header("Content-Type", content_type)

        self.send_header("Content-Length", str(len(data)))

        self.send_header("Access-Control-Allow-Origin", "*")

        self.end_headers()

        self.wfile.write(data)



    def do_HEAD(self):

        maybe_reload_channels()
        path = self.path.split("?")[0]



        if path in ("/", "/playlist.m3u", "/guide.xml"):

            content_type = {

                "/": "text/plain",

                "/playlist.m3u": "audio/x-mpegurl",

                "/guide.xml": "application/xml",

            }[path]

        elif path.startswith("/stream/") and path[8:] in CHANNELS:

            content_type = "video/mp2t"

        else:

            return self.send_error(404)



        self.send_response(200)

        self.send_header("Content-Type", content_type)

        self.send_header("Access-Control-Allow-Origin", "*")

        self.end_headers()



    def do_GET(self):

        maybe_reload_channels()
        path = self.path.split("?")[0]



        if path == "/":

            return self.send_text(

                f"Spelunkr Jellyfin service running. Channels: {len(CHANNELS)}\n"

                "Playlist: /playlist.m3u\n"

                "Guide: /guide.xml\n",

                "text/plain"

            )



        if path == "/playlist.m3u":

            output = ["#EXTM3U"]



            for channel in CHANNELS.values():

                output.append(

                    f'#EXTINF:-1 tvg-id="{channel["id"]}" '

                    f'tvg-name="{channel["name"]}" '

                    f'group-title="Spelunkr",{channel["name"]}'

                )

                output.append(

                    f'{BASE_URL}/stream/{channel["id"]}'

                )



            return self.send_text("\n".join(output) + "\n", "audio/x-mpegurl")



        if path == "/guide.xml":

            output = [

                '<?xml version="1.0" encoding="UTF-8"?>',

                '<tv generator-info-name="Spelunkr Jellyfin">'

            ]



            for channel in CHANNELS.values():

                output.append(

                    f'<channel id="{escape(channel["id"])}">'

                    f'<display-name>{escape(channel["name"])}</display-name>'

                    f'</channel>'

                )



            for channel in CHANNELS.values():

                for start, stop, item in programme_schedule(channel):

                    title = escape(item.get("title", item.get("id", "Unknown")))

                    output.append(

                        f'<programme start="{xmltv_time(start)}" '

                        f'stop="{xmltv_time(stop)}" '

                        f'channel="{escape(channel["id"])}">'

                        f'<title>{title}</title>'

                        f'<category>Television</category>'

                        f'</programme>'

                    )



            output.append("</tv>")

            return self.send_text("\n".join(output), "application/xml")



        if path.startswith("/stream/"):

            channel_id = path[len("/stream/"):]



            if channel_id not in CHANNELS:

                return self.send_error(404)



            return self.stream_channel(CHANNELS[channel_id])



        self.send_error(404)



    def stream_channel(self, channel):

        self.send_response(200)

        self.send_header("Content-Type", "video/mp2t")

        self.send_header("Cache-Control", "no-cache")

        self.send_header("Access-Control-Allow-Origin", "*")

        self.end_headers()



        timestamp = time.time()

        process = None



        try:

            while True:

                slot = locate(channel, timestamp)

                item = slot["item"]

                remaining = slot["remaining"]

                offset = slot["offset"]



                print(

                    f'{channel["name"]}: '

                    f'{item.get("title", item["id"])} at {offset:.1f}s',

                    flush=True

                )



                command = [

                    "ffmpeg", "-hide_banner", "-loglevel", "error",

                    "-ss", str(offset),

                    "-re", "-i", archive_url(item),

                    "-t", str(remaining),

                    "-map", "0:v:0?",

                    "-map", "0:a:0?",

                    "-c:v", "libx264",

                    "-preset", "veryfast",

                    "-crf", "23",

                    "-c:a", "aac",

                    "-b:a", "128k",

                    "-f", "mpegts",

                    "-mpegts_flags", "+resend_headers",

                    "pipe:1"

                ]



                process = subprocess.Popen(

                    command,

                    stdout=subprocess.PIPE,

                    stderr=subprocess.DEVNULL,

                    bufsize=0

                )



                while True:

                    chunk = process.stdout.read(65536)



                    if not chunk:

                        break



                    self.wfile.write(chunk)

                    self.wfile.flush()



                process.wait()

                process = None

                timestamp = max(timestamp + remaining, time.time())



        except (BrokenPipeError, ConnectionResetError):

            print(f'{channel["name"]}: client disconnected', flush=True)



        except Exception as error:

            print(f'{channel["name"]}: stream error: {error}', flush=True)



        finally:

            if process and process.poll() is None:

                process.terminate()

                process.wait()



lineup, CHANNELS = load_channels()
last_lineup_mtime = os.stat(LINEUP_PATH).st_mtime_ns



if __name__ == "__main__":

    print(f"Starting Spelunkr service on port {PORT}", flush=True)

    print(f"Loaded {len(CHANNELS)} channels:", flush=True)



    for channel in CHANNELS.values():

        print(

            f'  {channel["name"]} (v{channel["version"]})',

            flush=True

        )



    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

