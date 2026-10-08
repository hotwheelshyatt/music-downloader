# Music Downloader

`main.py` reads a song list from a CSV file, searches YouTube, downloads MP3s with `yt-dlp`, and adds available tags and artwork. Download only audio you have permission to use.

## Set up

1. Install Python 3, FFmpeg, and [Deno](https://docs.deno.com/runtime/getting_started/installation/) for YouTube support. Check them with `ffmpeg -version` and `deno --version`.
2. In this folder, create a virtual environment and install the Python packages:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   python -m pip install -U "yt-dlp[default]" mutagen
   ```

   On Windows, use `py -m venv venv` and `venv\Scripts\activate` instead of the first two commands.
3. Open `main.py` and set `DESTINATION` to the folder where MP3s should be saved. Set `INPUT_FILE` to your CSV filename, or to `None` to choose from files beside the script.

## Prepare a CSV

Put the CSV beside `main.py`. It needs these exact column headers:

```csv
Track name,Artist name
Bohemian Rhapsody,Queen
Take On Me,a-ha
```

The included `songs.csv` is a small example. `My Spotify Library.csv` also has the required headers and can be selected by setting `INPUT_FILE = "My Spotify Library.csv"`. Its extra columns are currently ignored; using them for better searches and tags is planned in [todo.md](todo.md).

## Run

With the virtual environment active, run `python main.py` from this folder. Review the song list and confirm when prompted. Finished MP3s go to `DESTINATION`. The program skips an existing MP3 with the same track-name filename when `SKIP_EXISTING = True`.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `yt-dlp` or Mutagen is missing | Activate the virtual environment, then run `python -m pip install -U "yt-dlp[default]" mutagen`. |
| FFmpeg was not found | Install FFmpeg and confirm `ffmpeg -version` works in the same terminal. |
| YouTube reports missing JavaScript support | Check `deno --version` and reinstall `yt-dlp` with the command above. See the [yt-dlp setup guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS). |
| Input file not found | Check `INPUT_FILE` in `main.py` and put that CSV beside the script. With `INPUT_FILE = None`, the script asks which file to use if it finds several. |
| CSV load fails | Use the exact headers `Track name,Artist name` and fill both columns. `.txt` files are offered by the picker but currently fail to load. |
| Wrong recording downloaded | The current search takes the first YouTube result. Check the `Selected:` URL shown in the terminal; improved matching is on the todo list. |
| YouTube search fails with HTTP 403 | Check whether this computer can access YouTube. The 403 recorded in `download_errors.txt` was caused by a network block; restore access before retrying. Diagnose other 403 errors separately. |
| A song fails while others continue | Read `download_errors.txt` beside the script. Correct the issue and rerun; existing MP3s are normally skipped. |

Metadata and artwork depend on what the selected YouTube upload provides. Songs with the same title currently use the same output filename, even when their artists differ; this is tracked in [todo.md](todo.md).
