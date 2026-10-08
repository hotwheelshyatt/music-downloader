import csv
import json
import os
import re
import sys
import subprocess
from pathlib import Path

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
# If this is None, the script automatically searches the same
# folder as this Python file for the first CSV or TXT file.
#
# Examples:
# INPUT_FILE = "songs.csv"
# INPUT_FILE = "songs.txt"
# INPUT_FILE = None
INPUT_FILE = "songs.csv"

# Whether to search YouTube automatically.
SEARCH_YOUTUBE = True

# Download artwork and embed it into the MP3.
EMBED_ARTWORK = True

# Maximum number of search results to examine.
# Usually 5 is plenty.
SEARCH_RESULTS = 5

# Skip a song if an MP3 with the exact same filename already exists.
SKIP_EXISTING = True

# ============================================================
# END CONFIGURATION
# ============================================================


SCRIPT_FOLDER = Path(__file__).resolve().parent
DESTINATION_PATH = Path(DESTINATION)
ERROR_LOG = SCRIPT_FOLDER / "download_errors.txt"


# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------

def print_header():
    print()
    print("=" * 65)
    print("                 MUSIC DOWNLOADER")
    print("=" * 65)
    print()


def clean_filename(name):
    """
    Remove characters that Windows does not allow in filenames.
    """
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = name.strip().rstrip(".")
    return name


def find_input_file():
    """
    Find the input CSV/TXT file next to this Python script.
    """

    if INPUT_FILE:
        path = SCRIPT_FOLDER / INPUT_FILE

        if not path.exists():
            raise FileNotFoundError(
                f"Configured input file does not exist:\n{path}"
            )

        return path

    files = []

    for extension in ("*.csv", "*.txt"):
        files.extend(SCRIPT_FOLDER.glob(extension))

    # Don't accidentally use our own error log.
    files = [
        f for f in files
        if f.name.lower() != ERROR_LOG.name.lower()
    ]

    if not files:
        raise FileNotFoundError(
            "No CSV or TXT input file was found next to the Python script."
        )

    if len(files) > 1:
        print("Multiple input files were found:")
        for i, file in enumerate(files, 1):
            print(f"  {i}. {file.name}")

        print()
        choice = input("Enter the number of the input file: ").strip()

        try:
            index = int(choice) - 1
            return files[index]
        except (ValueError, IndexError):
            raise ValueError("Invalid input file selection.")
    return files[0]


def load_songs(input_file):
    """
    Read songs from CSV or TXT.

    Expected format:

    Track name,Artist name,
    Song One,Artist One
    Song Two,Artist Two

    OR
    (example from https://www.tunemymusic.com/transfer)
    Track name,Artist name,Album,Playlist name,Type,ISRC,Spotify - id
    "Awake","Tycho","Awake","ADHD Focus Music (No Lyrics)","Playlist","US2J71309901","5lB3bZKPhng9s4hKB1sSIe"
    "I Came Running","Ancient Astronauts","We Are To Answer","ADHD Focus Music (No Lyrics)","Playlist","USESL0914702","62e6CJOmmYiiwS9yKE5Gg6"

    """

    songs = []

    if input_file.suffix.lower() == ".csv":

        with open(input_file, "r", encoding="utf-8-sig", newline="") as file:

            reader = csv.DictReader(file)

            for row in reader:
                # Track name,Artist name

                # cleans up trailing+leading white space in first 2 colloms
                row['Track name'] = row['Track name'].strip()
                row['Artist name'] = row['Artist name'].strip()

                songs.append(row)
                print(f"{row}\n{songs}")

    else:
        raise ValueError("Input file must be CSV or TXT.")
    return songs


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


def search_youtube(song, artist):
    """
    Search YouTube and return the best result URL.
    """

    query = f"ytsearch{SEARCH_RESULTS}:{song} {artist}"

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

    # First result is normally the best match.
    entry = entries[0]

    video_id = entry.get("id")

    if not video_id:
        raise RuntimeError("YouTube result did not contain a video ID.")

    return f"https://www.youtube.com/watch?v={video_id}"


# ------------------------------------------------------------
# Download
# ------------------------------------------------------------

def download_song(song, artist, url):
    """
    Download a song and return the resulting MP3 path.
    """

    expected_filename = clean_filename(song) + ".mp3"
    expected_path = DESTINATION_PATH / expected_filename

    if SKIP_EXISTING and expected_path.exists():
        print("Already exists - skipping.")
        return expected_path

    # Temporary filename.
    output_template = str(
        DESTINATION_PATH / f"{clean_filename(song)}.%(ext)s"
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
    possible_mp3s = list(DESTINATION_PATH.glob("*.mp3"))

    matching = [
        p for p in possible_mp3s
        if p.stem.lower() == clean_filename(song).lower()
    ]

    if matching:
        return matching[0]

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

    # Save metadata.
    audio.save()

    return audio


# ------------------------------------------------------------
# Artwork
# ------------------------------------------------------------

def find_thumbnail(song):
    """
    Find a thumbnail temporarily downloaded by yt-dlp.
    """

    base = clean_filename(song)

    possible_extensions = [
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    ]

    for extension in possible_extensions:

        path = DESTINATION_PATH / (base + extension)

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


def remove_thumbnail(artwork_path):
    """
    Delete the temporary thumbnail.
    """

    if artwork_path and artwork_path.exists():

        try:
            artwork_path.unlink()
        except Exception:
            pass


# ------------------------------------------------------------
# Main processing
# ------------------------------------------------------------

def process_song(song_number, total_songs, song, artist):
    """
    Process one song.
    """

    print()
    print("=" * 65)
    print(f"SONG {song_number} / {total_songs}")
    print("=" * 65)
    print(f"Track name : {song}")
    print(f"Artist: {artist}")
    print()

    filename = clean_filename(song) + ".mp3"
    destination_file = DESTINATION_PATH / filename

    if SKIP_EXISTING and destination_file.exists():
        print(f"Already exists: {filename}")
        return True

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    if SEARCH_YOUTUBE:
        print("Searching YouTube...")

        url = search_youtube(
            song,
            artist
        )

        print(f"Selected: {url}")

    else:
        raise RuntimeError(
            "SEARCH_YOUTUBE is disabled, but no direct URL was supplied."
        )

    # --------------------------------------------------------
    # Get metadata before downloading
    # --------------------------------------------------------

    print("Reading metadata...")

    metadata = get_metadata(url)

    found_title = safe_metadata_value(
        metadata,
        "title"
    )

    found_artist = safe_metadata_value(
        metadata,
        "artist",
        "uploader"
    )

    if found_title:
        print(f"Found title : {found_title}")

    if found_artist:
        print(f"Found artist: {found_artist}")

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    mp3_path = download_song(
        song,
        artist,
        url
    )

    print(f"Downloaded: {mp3_path.name}")

    # --------------------------------------------------------
    # Artwork
    # --------------------------------------------------------

    artwork_path = None

    if EMBED_ARTWORK:
        artwork_path = find_thumbnail(song)

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    print("Writing metadata...")

    apply_metadata(
        mp3_path,
        requested_title=song,
        requested_artist=artist,
        metadata=metadata
    )

    if artwork_path:
        embed_artwork(
            mp3_path,
            artwork_path
        )

        remove_thumbnail(artwork_path)

    print()
    print("DONE")

    return True


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
    except Exception as error:
        print()
        print("ERROR:")
        print(error)
        print()
        input("Press Enter to exit...")
        return

    print(f"Input file:")
    print(f"  {input_file.name}")
    print()

    try:
        songs = load_songs(input_file)
    except Exception as error:
        print()
        print("ERROR reading input file:")
        print(error)
        print()
        input("Press Enter to exit...")
        return

    if not songs:
        print("No songs were found in the input file.")
        input("Press Enter to exit...")
        return

    print(f"Songs found: {len(songs)}")
    print()

    # --------------------------------------------------------
    # Confirmation
    # --------------------------------------------------------

    print("The following songs will be downloaded:")
    print()

    for number, item in enumerate(songs, 1):
        print(
            f"{number:3}. "
            f"{item['Track name']} - {item['Artist name']}"
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
    failed = 0

    # Clear old error log.
    if ERROR_LOG.exists():
        ERROR_LOG.unlink()

    for number, item in enumerate(songs, 1):

        try:

            process_song(
                number,
                len(songs),
                item["Track name"],
                item["Artist name"]
            )

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

        except Exception as error:

            failed += 1

            error_message = (
                f"{item['Track name']} - {item['Artist name']}\n"
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
    print(f"Failed:     {failed}")
    print(f"Destination: {DESTINATION_PATH}")

    if failed:
        print()
        print(f"Errors were saved to:")
        print(f"  {ERROR_LOG}")

    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()