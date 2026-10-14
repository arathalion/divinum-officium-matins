#!/usr/bin/env python3
"""Render podcast episodes of the daily readings and keep them in R2.

  python3 matins/podcast/render.py --models DIR [--calendar 1954] [--lang en]
      [--voice bm_lewis] [--back 2] [--ahead 1] [--keep-days 30]

For each date from --back days ago to --ahead days ahead (UTC) that has no
episode yet, reads the day's published readings, renders them with Kokoro,
and uploads podcast/<calendar>/<lang>/<date>.mp3 with its duration and title
as object metadata (the Worker builds the feed from these). Episodes older
than --keep-days are deleted.

R2 credentials come from the environment: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
R2_SECRET_ACCESS_KEY, R2_BUCKET.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

import boto3
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import script as S  # noqa: E402
from voice import Voice  # noqa: E402

DATA_URL = "https://raw.githubusercontent.com/arathalion/divinum-officium-matins/daily-data"


def fetch_day(calendar, lang, date):
    try:
        with urllib.request.urlopen(f"{DATA_URL}/{calendar}/{lang}/{date}.json", timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--calendar", default="1954")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--voice", default="bm_lewis")
    ap.add_argument("--speed", type=float, default=0.95)
    ap.add_argument("--back", type=int, default=2)
    ap.add_argument("--ahead", type=int, default=1)
    ap.add_argument("--keep-days", type=int, default=30)
    args = ap.parse_args()

    bucket = os.environ.get("R2_BUCKET", "matutinum")
    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    prefix = f"podcast/{args.calendar}/{args.lang}/"
    existing = set()
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        existing.update(o["Key"][len(prefix):-4] for o in page.get("Contents", []))

    today = datetime.datetime.now(datetime.timezone.utc).date()
    wanted = [(today + datetime.timedelta(days=d)).isoformat() for d in range(-args.back, args.ahead + 1)]
    todo = [d for d in wanted if d not in existing]
    print(f"{len(existing)} episodes stored; to render: {', '.join(todo) or 'none'}")

    voice = Voice(args.models, args.voice) if todo else None
    tmp = tempfile.mkdtemp()
    for date in todo:
        doc = fetch_day(args.calendar, args.lang, date)
        if not doc:
            print(f"{date}: no readings published, skipped")
            continue
        start = time.time()
        wave, rate = voice.read(S.script(doc), speed=args.speed)
        wav, mp3 = os.path.join(tmp, f"{date}.wav"), os.path.join(tmp, f"{date}.mp3")
        sf.write(wav, wave, rate)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav,
                        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ac", "1", "-ar", "24000",
                        "-codec:a", "libmp3lame", "-b:a", "64k",
                        "-metadata", f"title=Matins, {date}: {doc['title']['local']}", mp3], check=True)
        seconds = round(len(wave) / rate)
        s3.upload_file(mp3, bucket, f"{prefix}{date}.mp3", ExtraArgs={
            "ContentType": "audio/mpeg",
            "CacheControl": "public, max-age=86400",
            # Object metadata must be ASCII, so the titles are URL-encoded.
            "Metadata": {
                "duration": str(seconds),
                "title": urllib.parse.quote(doc["title"]["local"]),
                "latin": urllib.parse.quote(doc["title"]["latin"]),
            },
        })
        os.remove(wav)
        print(f"{date}: {seconds / 60:.1f} min, {os.path.getsize(mp3) / 1e6:.1f} MB, "
              f"rendered in {time.time() - start:.0f}s: {doc['title']['local']}")

    cutoff = (today - datetime.timedelta(days=args.keep_days)).isoformat()
    old = sorted(d for d in existing if d < cutoff)
    for date in old:
        s3.delete_object(Bucket=bucket, Key=f"{prefix}{date}.mp3")
    if old:
        print(f"deleted {len(old)} episodes older than {cutoff}")


if __name__ == "__main__":
    main()
