"""Choose and publish MP3 files without confusing same-title recordings."""

import os
import re
import shutil
from pathlib import Path


class OutputCollisionError(RuntimeError):
    """An existing file cannot be proven to be the requested recording."""


def clean_part(value):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(value or ""))
    return " ".join(cleaned.strip().rstrip(".").split())


def base_stem(row):
    artist = clean_part(row["artist_name"])
    title = clean_part(row["track_name"])
    if not artist or not title:
        raise OutputCollisionError("Artist or title becomes empty after filename cleaning.")
    return f"{artist} - {title}"


def read_recording_id(path):
    """Return the MusicBrainz recording ID saved in an existing MP3, if any."""
    try:
        from mutagen.id3 import ID3
        tags = ID3(path)
        frames = tags.getall("TXXX:MUSICBRAINZ_RECORDING_ID")
        if frames and frames[0].text:
            return str(frames[0].text[0])
    except Exception:
        pass
    return None


def existing_name(folder, name):
    wanted = name.casefold()
    for path in folder.iterdir():
        if path.is_file() and path.name.casefold() == wanted:
            return path
    return None


def choose_output_path(row, recording_id, folder, skip_existing):
    """Return (path, skip) without relying on a filename as identity."""
    stem = base_stem(row)
    base = existing_name(folder, stem + ".mp3")
    if base is None:
        return folder / (stem + ".mp3"), False
    if read_recording_id(base) == recording_id:
        return base, bool(skip_existing)

    # A legacy file with no identity is not safe to skip or overwrite.
    suffix = recording_id[:8]
    alternate_name = f"{stem} [{suffix}].mp3"
    alternate = existing_name(folder, alternate_name)
    if alternate is None:
        return folder / alternate_name, False
    if read_recording_id(alternate) == recording_id:
        return alternate, bool(skip_existing)
    raise OutputCollisionError(
        f"{alternate_name} already exists but is not verified as this recording."
    )


def publish_mp3(staged_path, destination, recording_id):
    """Exclusively create a new file, or replace only a verified same recording."""
    existing = existing_name(destination.parent, destination.name)
    if existing is not None:
        if existing != destination or read_recording_id(existing) != recording_id:
            raise OutputCollisionError(
                f"{destination.name} appeared or changed during download; no file was overwritten."
            )
        os.replace(staged_path, destination)
        return

    created = False
    try:
        with staged_path.open("rb") as source:
            with destination.open("xb") as output:
                created = True
                shutil.copyfileobj(source, output)
    except Exception:
        if created:
            destination.unlink()
        raise
