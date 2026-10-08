# Music Downloader

`main.py` reads a CSV song list, verifies each recording with MusicBrainz, compares several YouTube results, and saves confident matches as tagged MP3s. Download only audio you have permission to use.

## Set up and run

1. Install Python 3, FFmpeg, and [Deno](https://docs.deno.com/runtime/getting_started/installation/). Check `ffmpeg -version` and `deno --version`.
2. Install the Python packages:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   python -m pip install -U "yt-dlp[default]" mutagen
   ```

   On Windows, use `py -m venv venv` and `venv\Scripts\activate`.
3. Set `DESTINATION` and `INPUT_FILE` near the top of `main.py`. Set `INPUT_FILE = None` to choose a file beside the script.
4. Run `python main.py`, review the list, and confirm.

The CSV needs `Track name,Artist name` headers. `Album` and `ISRC` can help identify the recording; other export fields remain available but are not automatically written as tags. `songs.csv` and `My Spotify Library.csv` are examples. CSV-formatted `.txt` files can be previewed and converted with confirmation.

Songs without a clear MusicBrainz recording or YouTube match are skipped and recorded in `download_errors.txt`. Saved files use `Artist - Track.mp3`; a MusicBrainz ID suffix distinguishes recordings with the same name. `SKIP_EXISTING = True` skips only a file tagged with the same recording ID. Matching rules and provider limits are in [provider_research.md](provider_research.md).

## Troubleshooting

| Problem | What to do |
| --- | --- |
| Python package or FFmpeg missing | Activate `venv`, reinstall the packages above, and check `ffmpeg -version` in that terminal. |
| YouTube says JavaScript support is missing | Check `deno --version` and update `yt-dlp`; see its [JavaScript setup guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS). |
| CSV fails to load | Use the required headers, fill title and artist, and correct the line named in the error. |
| MusicBrainz is unavailable or a row is ambiguous | Check connectivity and the row's title, artist, album, and ISRC. Ambiguous rows are skipped instead of guessed. |
| YouTube search reports HTTP 403 | Check whether this computer can reach YouTube. The 403 previously recorded for `Hailing Taquitos - Parry Gripp` came from a network block; diagnose other 403 errors separately. |
| A song was skipped or failed | Read `download_errors.txt` for the row and reason, then correct the issue and rerun. |

The automated suite runs with `python -B -m unittest discover -s tests -q`. It uses mocked services; live downloads require reachable YouTube access.
