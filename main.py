import csv
import json
import re
import shutil
import sys
import subprocess
import tempfile
from pathlib import Path

from matching import MatchError, choose_youtube_video, identify_recording
from output_files import choose_output_path, publish_mp3

# ============================================================
# CONFIGURATION
# ============================================================

# Destination for the finished MP3 files.
# Examples:
#   r"D:\Music"
#   r"E:\Music"              # SD card
#   r"C:\Users\YourName\Music"
DESTINATION = r"/Users/localadmin/Music/harrys_music"

# Input file.
#
# If this is None, the script searches the same folder for CSV files
# or TXT files that can be validated and converted with confirmation.
#
# Examples:
# INPUT_FILE = "songs.csv"
# INPUT_FILE = "songs.txt"
# INPUT_FILE = None
INPUT_FILE = "songs.csv"

# Download artwork and embed it into the MP3.
EMBED_ARTWORK = True

# Maximum number of search results to examine.
# Usually 5 is plenty.
SEARCH_RESULTS = 5

# Skip a song only when an existing MP3 has the same MusicBrainz recording ID.
SKIP_EXISTING = True

# ============================================================
# END CONFIGURATION
# ============================================================


SCRIPT_FOLDER = Path(__file__).resolve().parent
DESTINATION_PATH = Path(DESTINATION)
ERROR_LOG = SCRIPT_FOLDER / "download_errors.txt"

# Only these export headers have a defined meaning. Other columns are kept
# unchanged in original_fields for later processing.
HEADER_NAMES = {
    "Track name": "track_name",
    "Artist name": "artist_name",
    "Album": "album",
    "Playlist name": "playlist_name",
    "Type": "export_type",
    "ISRC": "isrc",
    "Spotify - id": "spotify_id",
}


# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------

def print_header():
    print()
    print("=" * 65)
    print("                 MUSIC DOWNLOADER")
    print("=" * 65)
    print()


def find_input_file():
    """
    Select a CSV file, or a TXT file to validate and convert to CSV.
    """

    if INPUT_FILE:
        path = SCRIPT_FOLDER / INPUT_FILE

        if not path.is_file():
            raise FileNotFoundError(
                f"Configured input file does not exist:\n{path}"
            )

        if path.name.lower() == ERROR_LOG.name.lower():
            raise ValueError("The download error log is not a song list.")

        return path

    files = sorted(
        (
            path for path in SCRIPT_FOLDER.iterdir()
            if path.is_file()
            and path.suffix.lower() in (".csv", ".txt")
            and path.name.lower() != ERROR_LOG.name.lower()
        ),
        key=lambda path: path.name.lower()
    )

    if not files:
        raise FileNotFoundError(
            "No CSV input file or convertible TXT file was found next to the Python script."
        )

    if len(files) > 1:
        print("Multiple input files were found:")
        for i, file in enumerate(files, 1):
            label = " (validate and convert to CSV)" if file.suffix.lower() == ".txt" else ""
            print(f"  {i}. {file.name}{label}")

        print()
        choice = input("Enter the number of the input file: ").strip()

        try:
            index = int(choice)
        except ValueError:
            raise ValueError("Invalid input file selection.")
        if not 1 <= index <= len(files):
            raise ValueError("Invalid input file selection.")
        return files[index - 1]
    return files[0]


def _read_song_rows(input_file):
    """Validate every CSV record before returning any songs.

    source_line is the physical line where a record ends. For a quoted
    multiline field, this is the last line occupied by that record.
    """
    try:
        with input_file.open("r", encoding="utf-8-sig", newline="") as file:
            header_reader = csv.reader(file, strict=True)
            csv_reader = header_reader
            while True:
                headers = next(header_reader, None)
                if headers is None:
                    raise ValueError("The file is empty or has no header row.")
                if any(value.strip() for value in headers):
                    break
            header_line = header_reader.line_num

            stripped_headers = [header.strip() for header in headers]
            if any(not name for name in stripped_headers):
                raise ValueError(f"Line {header_line}: the CSV contains an empty column header.")
            duplicates = sorted({name for name in stripped_headers
                                 if stripped_headers.count(name) > 1})
            if duplicates:
                raise ValueError(
                    f"Line {header_line}: Duplicate CSV header(s): " + ", ".join(duplicates)
                )
            missing = [name for name in ("Track name", "Artist name")
                       if name not in stripped_headers]
            headerless = False
            if missing and len(headers) == 2 and all(stripped_headers) \
                    and not any(name in HEADER_NAMES for name in stripped_headers):
                print(f"First row may be song data: {headers[0]!r}, {headers[1]!r}")
                answer = input(
                    "Treat it as a song and use Track name,Artist name headers in memory? [y/N]: "
                ).strip().lower()
                headerless = answer in ("y", "yes")
                if headerless:
                    headers = ["Track name", "Artist name"]
                    stripped_headers = headers[:]
                    missing = []

            if missing:
                raise ValueError(
                    f"Line {header_line}: Missing required CSV header(s): " + ", ".join(missing)
                    + ". Expected Track name,Artist name."
                )
            if headerless:
                file.seek(0)
                line_offset = 0
            else:
                line_offset = header_line
            extra_columns = object()
            reader = csv.DictReader(
                file,
                fieldnames=headers,
                restkey=extra_columns,
                strict=True,
            )
            csv_reader = reader
            songs = []
            errors = []
            for row in reader:
                line = line_offset + reader.line_num
                extra = row.get(extra_columns, [])
                values = [row[name] for name in headers] + extra
                if all(value is None or not value.strip() for value in values):
                    continue

                if extra:
                    errors.append(f"Line {line}: too many columns; check quoting or remove extra cells.")
                    continue
                absent = [name for name in headers if row[name] is None]
                if absent:
                    errors.append(f"Line {line}: too few columns; missing {', '.join(absent)}.")
                    continue

                raw_fields = {name: row[name] for name in headers}
                normalized = {
                    HEADER_NAMES[clean_name]: row[raw_name].strip()
                    for raw_name, clean_name in zip(headers, stripped_headers)
                    if clean_name in HEADER_NAMES
                }
                empty = [name for name in ("Track name", "Artist name")
                         if not normalized[HEADER_NAMES[name]]]
                if empty:
                    errors.append(f"Line {line}: empty required field(s): {', '.join(empty)}.")
                    continue

                songs.append({
                    **normalized,
                    "original_fields": raw_fields,
                    "source_line": line,
                })

            if errors:
                raise ValueError("CSV validation failed:\n" + "\n".join(errors))
            if not songs:
                raise ValueError("No songs were found in the input file.")
            return songs
    except UnicodeDecodeError as error:
        raise ValueError(f"Input must be UTF-8 encoded: {input_file.name}") from error
    except csv.Error as error:
        underlying_reader = getattr(csv_reader, "reader", csv_reader)
        line = underlying_reader.line_num
        if isinstance(csv_reader, csv.DictReader):
            line += line_offset
        raise ValueError(
            f"Malformed CSV in {input_file.name} near line {line}: {error}. Check quoting."
        ) from error


def load_songs(input_file):
    """Read and validate a CSV file, preserving all original fields."""
    input_file = Path(input_file)
    if input_file.suffix.lower() != ".csv":
        raise ValueError("Input file must be CSV; TXT files require confirmed conversion.")
    return _read_song_rows(input_file)


def prepare_input_file(input_file):
    """Validate a selected file and safely convert CSV-like TXT on request."""
    input_file = Path(input_file)
    if input_file.suffix.lower() == ".csv":
        return input_file, load_songs(input_file)
    if input_file.suffix.lower() != ".txt" or input_file.name.lower() == ERROR_LOG.name.lower():
        raise ValueError("Choose a CSV file or a CSV-formatted TXT file to convert.")

    print(f"Preview of {input_file.name}:")
    try:
        with input_file.open("r", encoding="utf-8-sig", newline="") as file:
            for row_number, row in enumerate(csv.reader(file, strict=True), 1):
                if row_number > 3:
                    break
                print("  " + ", ".join(repr(value[:80]) for value in row))
    except UnicodeDecodeError as error:
        raise ValueError(f"Input must be UTF-8 encoded: {input_file.name}") from error
    except csv.Error as error:
        raise ValueError(f"Malformed CSV in {input_file.name}: {error}") from error

    songs = _read_song_rows(input_file)
    target = input_file.with_suffix(".csv")
    if target.exists():
        raise FileExistsError(f"Cannot convert: {target.name} already exists. Neither file was changed.")
    answer = input(f"Rename {input_file.name} to {target.name}? [y/N]: ").strip().lower()
    if answer not in ("y", "yes"):
        raise ValueError("TXT-to-CSV conversion cancelled; the file was not changed.")

    # Exclusive creation prevents a file appearing after the check from being overwritten.
    target_created = False
    try:
        with input_file.open("rb") as source:
            with target.open("xb") as destination:
                target_created = True
                shutil.copyfileobj(source, destination)
    except Exception:
        if target_created:
            target.unlink()
        raise
    try:
        input_file.unlink()
    except OSError as error:
        raise OSError(
            f"Created {target.name}, but could not remove {input_file.name}; both files remain."
        ) from error
    print(f"Converted {input_file.name} to {target.name}.")
    return target, songs


# ------------------------------------------------------------
# yt-dlp
# ------------------------------------------------------------

def check_yt_dlp():
    """
    Make sure yt-dlp is installed.
    """

    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError

        print(f"yt-dlp version: {result.stdout.strip()}")

    except Exception:
        print()
        print("ERROR: yt-dlp is not installed.")
        print()
        print("Install it with:")
        print("    python -m pip install -U yt-dlp")
        print()
        sys.exit(1)


def check_ffmpeg():
    """
    Make sure FFmpeg is installed.
    """

    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if result.returncode != 0:
            raise RuntimeError

    except Exception:
        print()
        print("ERROR: FFmpeg was not found.")
        print()
        print(
            "FFmpeg is required because yt-dlp needs it to convert "
            "the downloaded audio to MP3."
        )
        print()
        sys.exit(1)


def search_youtube(song, artist, album=None):
    """
    Search YouTube and return candidates for verification.
    """

    query = f"ytsearch{SEARCH_RESULTS}:{song} {artist} {album or ''}".strip()

    command = [
        sys.executable,
        "-m",
        "yt_dlp",

        "--flat-playlist",

        "--dump-single-json",

        query
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"YouTube search failed:\n{result.stderr.strip()}"
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("Could not read yt-dlp search results.")

    entries = data.get("entries", [])

    if not entries:
        raise RuntimeError("No YouTube results found.")

    return entries


# ------------------------------------------------------------
# Download
# ------------------------------------------------------------

def download_song(url, staging_folder, stem):
    """
    Download into a temporary folder; publishing happens after tagging.
    """

    expected_path = staging_folder / (stem + ".mp3")

    # Temporary filename.
    output_template = str(
        staging_folder / f"{stem}.%(ext)s"
    )

    command = [
        sys.executable,
        "-m",
        "yt_dlp",

        # Best available audio.
        "-f", "bestaudio/best",

        # Convert to MP3.
        "-x",
        "--audio-format", "mp3",

        # High-quality MP3.
        "--audio-quality", "0",

        # Embed basic metadata.
        "--embed-metadata",

        # Keep thumbnail temporarily for embedding.
        "--write-thumbnail",

        # Convert thumbnail to JPEG when possible.
        "--convert-thumbnails", "jpg",

        # Output filename.
        "-o", output_template,

        url
    ]

    if not EMBED_ARTWORK:
        # Remove thumbnail-related options.
        command = [
            x for x in command
            if x not in (
                "--write-thumbnail",
                "--convert-thumbnails"
            )
        ]

    print()
    print("Downloading...")

    result = subprocess.run(command)

    if result.returncode != 0:
        raise RuntimeError("yt-dlp failed to download the song.")

    # yt-dlp should have created the MP3.
    if expected_path.exists():
        return expected_path

    # Look for an MP3 if the exact name wasn't found.
    raise RuntimeError(
        "Download completed, but the resulting MP3 could not be found."
    )


# ------------------------------------------------------------
# Metadata
# ------------------------------------------------------------

def get_metadata(url):
    """
    Get detailed metadata from the YouTube source.
    """

    command = [
        sys.executable,
        "-m",
        "yt_dlp",

        "--dump-single-json",
        "--skip-download",

        url
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("Warning: could not retrieve detailed metadata.")
        return {}

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def safe_metadata_value(metadata, *keys):
    """
    Return the first useful metadata value.
    """

    for key in keys:
        value = metadata.get(key)

        if value is None:
            continue

        if isinstance(value, str) and value.strip():
            return value.strip()

        if isinstance(value, (int, float)):
            return str(value)

    return None


def apply_metadata(mp3_path, requested_title, requested_artist, metadata):
    """
    Apply detailed ID3 metadata using Mutagen.
    """

    try:
        from mutagen.id3 import (
            ID3,
            TIT2,
            TPE1,
            TPE2,
            TALB,
            TRCK,
            TPOS,
            TDRC,
            TSRC,
            TCON,
            TCMP,
            TCOM,
            TLAN,
            COMM,
            TCOP,
            TPUB,
            WOAS,
            TXXX,
            APIC
        )

        from mutagen.mp3 import MP3

    except ImportError:
        raise RuntimeError(
            "Mutagen is not installed.\n"
            "Install it with: python -m pip install mutagen"
        )

    audio = MP3(mp3_path)

    if audio.tags is None:
        audio.add_tags()

    tags = audio.tags

    # --------------------------------------------------------
    # Core information
    # --------------------------------------------------------

    # IMPORTANT:
    # The Track name is ALWAYS exactly what the user put in the
    # input file.
    tags["TIT2"] = TIT2(encoding=3, text=requested_title)

    tags["TPE1"] = TPE1(
        encoding=3,
        text=requested_artist
    )

    # --------------------------------------------------------
    # Album
    # --------------------------------------------------------

    album = safe_metadata_value(
        metadata,
        "album",
        "album_name"
    )

    if album:
        tags["TALB"] = TALB(
            encoding=3,
            text=album
        )

    # --------------------------------------------------------
    # Album artist
    # --------------------------------------------------------

    album_artist = safe_metadata_value(
        metadata,
        "album_artist",
        "artist"
    )

    if album_artist:
        tags["TPE2"] = TPE2(
            encoding=3,
            text=album_artist
        )

    # --------------------------------------------------------
    # Track number
    # --------------------------------------------------------

    track = safe_metadata_value(
        metadata,
        "track_number"
    )

    if track:
        tags["TRCK"] = TRCK(
            encoding=3,
            text=track
        )

    # --------------------------------------------------------
    # Disc number
    # --------------------------------------------------------

    disc = safe_metadata_value(
        metadata,
        "disc_number"
    )

    if disc:
        tags["TPOS"] = TPOS(
            encoding=3,
            text=disc
        )

    # --------------------------------------------------------
    # Release date / year
    # --------------------------------------------------------

    release_date = safe_metadata_value(
        metadata,
        "release_date",
        "upload_date"
    )

    if release_date:
        # YouTube upload dates can be YYYYMMDD.
        if re.fullmatch(r"\d{8}", release_date):
            release_date = (
                f"{release_date[0:4]}-"
                f"{release_date[4:6]}-"
                f"{release_date[6:8]}"
            )

        tags["TDRC"] = TDRC(
            encoding=3,
            text=release_date
        )

    # --------------------------------------------------------
    # Genre
    # --------------------------------------------------------

    genre = safe_metadata_value(
        metadata,
        "genre"
    )

    if genre:
        tags["TCON"] = TCON(
            encoding=3,
            text=genre
        )

    # --------------------------------------------------------
    # Composer
    # --------------------------------------------------------

    composer = safe_metadata_value(
        metadata,
        "composer"
    )

    if composer:
        tags["TCOM"] = TCOM(
            encoding=3,
            text=composer
        )

    # --------------------------------------------------------
    # Language
    # --------------------------------------------------------

    language = safe_metadata_value(
        metadata,
        "language"
    )

    if language:
        tags["TLAN"] = TLAN(
            encoding=3,
            text=language
        )

    # --------------------------------------------------------
    # Copyright
    # --------------------------------------------------------

    copyright_text = safe_metadata_value(
        metadata,
        "copyright"
    )

    if copyright_text:
        tags["TCOP"] = TCOP(
            encoding=3,
            text=copyright_text
        )

    # --------------------------------------------------------
    # Publisher
    # --------------------------------------------------------

    publisher = safe_metadata_value(
        metadata,
        "publisher",
        "label"
    )

    if publisher:
        tags["TPUB"] = TPUB(
            encoding=3,
            text=publisher
        )

    # --------------------------------------------------------
    # Comment
    # --------------------------------------------------------

    description = safe_metadata_value(
        metadata,
        "description"
    )

    if description:
        # Keep comments from becoming enormous.
        description = description[:5000]

        tags["COMM::eng"] = COMM(
            encoding=3,
            lang="eng",
            desc="Description",
            text=description
        )

    # --------------------------------------------------------
    # Source URL
    # --------------------------------------------------------

    webpage_url = safe_metadata_value(
        metadata,
        "webpage_url",
        "original_url"
    )

    if webpage_url:
        tags["WOAS"] = WOAS(
            encoding=3,
            url=webpage_url
        )

    # --------------------------------------------------------
    # Extra metadata
    # --------------------------------------------------------

    uploader = safe_metadata_value(
        metadata,
        "uploader",
        "channel"
    )

    if uploader:
        tags["TXXX:YT_UPLOADER"] = TXXX(
            encoding=3,
            desc="YT_UPLOADER",
            text=uploader
        )

    channel_url = safe_metadata_value(
        metadata,
        "channel_url"
    )

    if channel_url:
        tags["TXXX:YT_CHANNEL_URL"] = TXXX(
            encoding=3,
            desc="YT_CHANNEL_URL",
            text=channel_url
        )

    video_id = safe_metadata_value(
        metadata,
        "id"
    )

    if video_id:
        tags["TXXX:YT_VIDEO_ID"] = TXXX(
            encoding=3,
            desc="YT_VIDEO_ID",
            text=video_id
        )

    duration = safe_metadata_value(
        metadata,
        "duration"
    )

    if duration:
        tags["TXXX:DURATION"] = TXXX(
            encoding=3,
            desc="DURATION",
            text=duration
        )

    isrc = safe_metadata_value(metadata, "isrc")
    if isrc:
        tags["TSRC"] = TSRC(encoding=3, text=isrc)

    recording_id = safe_metadata_value(metadata, "musicbrainz_recording_id")
    if recording_id:
        tags["TXXX:MUSICBRAINZ_RECORDING_ID"] = TXXX(
            encoding=3, desc="MUSICBRAINZ_RECORDING_ID", text=recording_id
        )

    release_id = safe_metadata_value(metadata, "musicbrainz_release_id")
    if release_id:
        tags["TXXX:MUSICBRAINZ_RELEASE_ID"] = TXXX(
            encoding=3, desc="MUSICBRAINZ_RELEASE_ID", text=release_id
        )

    # Save metadata.
    audio.save()

    return audio


def tag_metadata(row, target, video):
    """CSV fields override verified release fields, then YouTube fields."""
    result = dict(video)
    release = target.get("release")
    if release:
        if release.get("title"):
            result["album"] = release["title"]
        if release.get("date"):
            result["release_date"] = release["date"]
        result["musicbrainz_release_id"] = release.get("id")
    if row.get("album"):
        result["album"] = row["album"]
    result["album_artist"] = target["artist"]
    result["musicbrainz_recording_id"] = target["id"]
    if target.get("isrc"):
        result["isrc"] = target["isrc"]
    return result


# ------------------------------------------------------------
# Artwork
# ------------------------------------------------------------

def find_thumbnail(stem, folder):
    """
    Find a thumbnail temporarily downloaded by yt-dlp.
    """

    possible_extensions = [
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    ]

    for extension in possible_extensions:

        path = folder / (stem + extension)

        if path.exists():
            return path

    return None


def embed_artwork(mp3_path, artwork_path):
    """
    Embed album artwork into the MP3.
    """

    if not artwork_path or not artwork_path.exists():
        return

    try:
        from mutagen.id3 import ID3, APIC

        tags = ID3(mp3_path)

        with open(artwork_path, "rb") as image_file:
            image_data = image_file.read()

        extension = artwork_path.suffix.lower()

        if extension in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        elif extension == ".png":
            mime = "image/png"
        else:
            mime = "image/jpeg"

        # Remove existing attached pictures.
        tags.delall("APIC")

        tags.add(
            APIC(
                encoding=3,
                mime=mime,
                type=3,  # Front cover
                desc="Cover",
                data=image_data
            )
        )

        tags.save(mp3_path)

        print("Artwork embedded.")

    except Exception as error:
        print(f"Warning: could not embed artwork: {error}")


# ------------------------------------------------------------
# Main processing
# ------------------------------------------------------------

def process_song(song_number, total_songs, row):
    """
    Process one song.
    """

    print()
    print("=" * 65)
    print(f"SONG {song_number} / {total_songs}")
    print("=" * 65)
    song = row["track_name"]
    artist = row["artist_name"]
    print(f"Track name : {song}")
    print(f"Artist: {artist}")
    print()

    print("Identifying recording with MusicBrainz...")
    target = identify_recording(row)
    print(f"Recording: {target['title']} - {target['artist']} ({target['id']})")

    print("Searching YouTube candidates...")
    entries = search_youtube(song, artist, row.get("album"))
    score, url, video, reasons = choose_youtube_video(row, target, entries, get_metadata)
    print(f"Selected: {url}")
    print(f"Confidence: {score}/100; {', '.join(reasons)}")

    destination, skip = choose_output_path(row, target["id"], DESTINATION_PATH, SKIP_EXISTING)
    if skip:
        print(f"Already downloaded recording: {destination.name}")
        return "skipped"

    with tempfile.TemporaryDirectory(prefix=".musicdownloader-", dir=DESTINATION_PATH) as folder:
        staging_folder = Path(folder)
        mp3_path = download_song(url, staging_folder, destination.stem)
        print("Writing metadata...")
        apply_metadata(
            mp3_path,
            requested_title=song,
            requested_artist=artist,
            metadata=tag_metadata(row, target, video),
        )
        if EMBED_ARTWORK:
            artwork_path = find_thumbnail(destination.stem, staging_folder)
            if artwork_path:
                embed_artwork(mp3_path, artwork_path)
        publish_mp3(mp3_path, destination, target["id"])

    print(f"Saved: {destination.name}")

    print()
    print("DONE")

    return "downloaded"


def main():

    print_header()

    # --------------------------------------------------------
    # Check dependencies
    # --------------------------------------------------------

    check_yt_dlp()
    check_ffmpeg()

    # Check Mutagen.
    try:
        import mutagen  # noqa: F401
    except ImportError:
        print()
        print("ERROR: Mutagen is not installed.")
        print()
        print("Install it with:")
        print("    python -m pip install mutagen")
        print()
        sys.exit(1)

    # --------------------------------------------------------
    # Destination
    # --------------------------------------------------------

    try:
        DESTINATION_PATH.mkdir(
            parents=True,
            exist_ok=True
        )
    except Exception as error:
        print()
        print("ERROR: Could not create destination folder.")
        print(error)
        sys.exit(1)

    print(f"Destination:")
    print(f"  {DESTINATION_PATH}")
    print()

    # --------------------------------------------------------
    # Input
    # --------------------------------------------------------

    try:
        input_file = find_input_file()
        input_file, songs = prepare_input_file(input_file)
    except Exception as error:
        print()
        print("ERROR reading input file:")
        print(error)
        print()
        input("Press Enter to exit...")
        return

    print(f"Input file:")
    print(f"  {input_file.name}")
    print()
    print(f"Songs found: {len(songs)}")
    print()

    # --------------------------------------------------------
    # Confirmation
    # --------------------------------------------------------

    print("The following songs will be checked and downloaded if matched:")
    print()

    for number, item in enumerate(songs, 1):
        print(
            f"{number:3}. "
            f"{item['track_name']} - {item['artist_name']}"
        )

    print()
    print(f"Destination: {DESTINATION_PATH}")
    print()

    answer = input("Start downloading? [Y/n]: ").strip().lower()

    if answer not in ("", "y", "yes"):
        print("Cancelled.")
        return

    # --------------------------------------------------------
    # Process songs
    # --------------------------------------------------------

    successful = 0
    skipped = 0
    failed = 0

    # Clear old error log.
    if ERROR_LOG.exists():
        ERROR_LOG.unlink()

    for number, item in enumerate(songs, 1):

        try:

            result = process_song(
                number,
                len(songs),
                item,
            )
            if result == "skipped":
                skipped += 1
            else:
                successful += 1

        except KeyboardInterrupt:

            print()
            print("Download interrupted by user.")

            with open(
                ERROR_LOG,
                "a",
                encoding="utf-8"
            ) as log:
                log.write(
                    "Download interrupted by user.\n"
                )

            break

        except MatchError as error:
            skipped += 1
            print(f"SKIPPED: {error}")
            with open(ERROR_LOG, "a", encoding="utf-8") as log:
                log.write(
                    f"Line {item['source_line']}: {item['track_name']} - {item['artist_name']}\n"
                    f"Skipped: {error}\n{'-' * 60}\n"
                )

        except Exception as error:

            failed += 1

            error_message = (
                f"{item['track_name']} - {item['artist_name']}\n"
                f"{error}\n"
                f"{'-' * 60}\n"
            )

            print()
            print("FAILED")
            print(error)

            with open(
                ERROR_LOG,
                "a",
                encoding="utf-8"
            ) as log:
                log.write(error_message)

    # --------------------------------------------------------
    # Finished
    # --------------------------------------------------------

    print()
    print("=" * 65)
    print("                     FINISHED")
    print("=" * 65)
    print()
    print(f"Successful: {successful}")
    print(f"Skipped:    {skipped}")
    print(f"Failed:     {failed}")
    print(f"Destination: {DESTINATION_PATH}")

    if ERROR_LOG.exists():
        print()
        print("Skipped rows and errors were saved to:")
        print(f"  {ERROR_LOG}")

    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
