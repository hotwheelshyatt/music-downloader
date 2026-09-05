
# Music Downloader

A Python program that reads a list of songs and artists from a CSV or TXT file, searches YouTube with `yt-dlp`, downloads the best available audio, converts it to MP3, and adds as much available metadata as possible.

> Only download audio that you have permission to download and use.

## Features

- Reads songs from a CSV or TXT file.
- Searches YouTube automatically.
- Downloads the best available audio.
- Converts the audio to MP3.
- Uses the song name from the input file as the MP3 title.
- Adds artist information and other available metadata.
- Attempts to embed artwork.
- Saves files to a destination you choose, including an SD card.
- Skips MP3s that already exist.
- Continues downloading if one song fails.
- Creates an error log for failed downloads.

## Folder Setup

Put the files together like this:

```text
MusicDownloader/
├── music_downloader.py
├── songs.csv
└── download_errors.txt    # created automatically if needed
```

The input file can also be a TXT file:

```text
MusicDownloader/
├── music_downloader.py
└── songs.txt
```

## 1. Install Python

Install Python 3 from the official Python website.

During installation on Windows, make sure the option to add Python to PATH is enabled.

Check that Python works:

```bash
python --version
```

## 1.1 make venv folder

```bash
python -m venv venv
. venv/bin/activate
```

## 2. Install the Python Packages

Open a terminal or Command Prompt in the MusicDownloader folder and run:

```bash
python -m pip install -U yt-dlp mutagen yt-dlp-ejs
npm install -g deno
```

The program uses:

- `yt-dlp` — searches YouTube and downloads the audio.
- `mutagen` — writes MP3 metadata.

## 3. Install FFmpeg

FFmpeg is required to convert the downloaded audio to MP3 and process artwork.

Install FFmpeg and make sure the `ffmpeg` command works from a terminal:

```bash
ffmpeg -version
```

If that command is not recognized, FFmpeg is not installed correctly or is not in PATH.

## 4. Create the Input File

The input file must contain the song name and artist.

### CSV

Example `songs.csv`:

```csv
Songname,Artist
Bohemian Rhapsody,Queen
Take On Me,a-ha
Billie Jean,Michael Jackson
```

The first line is a header and is automatically ignored.

### TXT

Example `songs.txt`:

```text
Bohemian Rhapsody,Queen
Take On Me,a-ha
Billie Jean,Michael Jackson
```

Each song goes on its own line.

The format is:

```text
Songname,Artist
```

You can use commas inside the song name only with care because the program treats the first comma as the separator.

## 5. Set the Destination Folder

Open `music_downloader.py` in a text editor.

Near the top you will find:

```python
DESTINATION = r"E:\Music"
```

Change this to the folder where you want your music saved.

### Example: Windows drive

```python
DESTINATION = r"D:\Music"
```

### Example: SD card

If your SD card is drive `E:`:

```python
DESTINATION = r"E:\Music"
```

### Example: another folder

```python
DESTINATION = r"C:\Users\YourName\Music"
```

The destination folder will be created automatically if it does not already exist.

## 6. Choose the Input File

You can let the program find the input file automatically:

```python
INPUT_FILE = None
```

If there is exactly one CSV or TXT file next to the Python script, it will use that file.

You can also specify the filename directly:

```python
INPUT_FILE = "songs.csv"
```

or:

```python
INPUT_FILE = "songs.txt"
```

If multiple CSV/TXT files are present and `INPUT_FILE` is `None`, the program will ask you which one to use.

## 7. Run the Downloader

Open a terminal in the folder containing `music_downloader.py`.

Run:

```bash
python music_downloader.py
```

The program will:

1. Check that the required software is installed.
2. Find the input file.
3. Read the song list.
4. Show the songs it found.
5. Ask for confirmation.
6. Search YouTube.
7. Download each song.
8. Convert it to MP3.
9. Add metadata.
10. Embed artwork when available.
11. Save the finished MP3 to the destination folder.

## MP3 Metadata

The program attempts to save information such as:

- Title
- Artist
- Album
- Album artist
- Track number
- Disc number
- Release date
- Genre
- Composer
- Language
- Copyright
- Publisher
- Description/comment
- YouTube uploader
- YouTube channel URL
- YouTube video ID
- Source URL
- Duration
- Cover artwork

Not every YouTube upload provides all of this information, so some fields may be missing.

### Title

The title is intentionally taken directly from your input file.

For example:

```csv
Bohemian Rhapsody,Queen
```

produces:

```text
Title: Bohemian Rhapsody
Artist: Queen
```

The program does not intentionally add the artist, uploader, channel name, or other information to the title.

## Output

A song such as:

```text
Bohemian Rhapsody,Queen
```

will normally become:

```text
Bohemian Rhapsody.mp3
```

with metadata similar to:

```text
Title:        Bohemian Rhapsody
Artist:       Queen
Album:        ...
Album Artist: ...
Track:        ...
Year:         ...
Genre:        ...
Artwork:      Embedded
```

## Existing Files

By default:

```python
SKIP_EXISTING = True
```

If `Bohemian Rhapsody.mp3` already exists in the destination folder, the program skips downloading it again.

To allow existing files to be replaced, change it to:

```python
SKIP_EXISTING = False
```

## Artwork

Artwork embedding is enabled by default:

```python
EMBED_ARTWORK = True
```

If artwork processing causes problems, it can be disabled:

```python
EMBED_ARTWORK = False
```

## Troubleshooting

### `yt-dlp is not installed`

Run:

```bash
python -m pip install -U yt-dlp
```

### `Mutagen is not installed`

Run:

```bash
python -m pip install mutagen
```

### `ffmpeg was not found`

Install FFmpeg and make sure this works:

```bash
ffmpeg -version
```

### No CSV or TXT file was found

Make sure your input file is in the same folder as:

```text
music_downloader.py
```

For example:

```text
MusicDownloader/
├── music_downloader.py
└── songs.csv
```

### A song downloads incorrectly

YouTube search results are not guaranteed to be perfect. A song may have multiple uploads, covers, live versions, remixes, or unrelated videos with similar names.

Check the selected YouTube result printed by the program.

### A song fails but others continue

The program records failed downloads in:

```text
download_errors.txt
```

Fix the problem and run the program again. Existing successful downloads will normally be skipped.

## Recommended Settings

For a normal music library, these settings are recommended:

```python
DESTINATION = r"E:\Music"
INPUT_FILE = None
SEARCH_YOUTUBE = True
EMBED_ARTWORK = True
SEARCH_RESULTS = 5
SKIP_EXISTING = True
```

## Important Notes

- Internet access is required for YouTube searches and downloads.
- YouTube metadata is not always complete or accurate.
- The program cannot create metadata that was never provided by the source.
- Keep backups of your music library.
- Respect copyright and the terms of the services you use.

## Updating yt-dlp

YouTube can change over time, so keeping `yt-dlp` updated is recommended:

```bash
python -m pip install -U yt-dlp
```

## Quick Start

After everything is installed:

1. Put `music_downloader.py` and your CSV/TXT file in the same folder.
2. Open `music_downloader.py`.
3. Set `DESTINATION`.
4. Save the file.
5. Open a terminal in that folder.
6. Run:

```bash
python music_downloader.py
```

7. Confirm the download.
8. Your MP3 files will appear in the destination folder.
