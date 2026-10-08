# Next step: make CSV input reliable

This document expands **step 1, “Normalize and validate CSV input,”** in [todo.md](todo.md). Complete this milestone before adding MusicBrainz lookup or changing YouTube matching. The result should be a trustworthy list of songs for the later stages to use.

**Status:** Completed in `main.py`; the input checks are covered by `tests/test_input.py`. Step 2 in [todo.md](todo.md) remains next. The sections below record the implementation checklist and its acceptance criteria.

## Why this was next

Before this milestone, `find_input_file()` offered `.csv` and `.txt` files, while `load_songs()` rejected `.txt` files. The loader expected the exact headers `Track name` and `Artist name`, printed every row and the growing song list, and could produce an unhelpful `.strip()` error for missing data. The work below addressed those input problems.

The two included examples should both remain usable:

| File | Headers | Important detail |
| --- | --- | --- |
| `songs.csv` | `Track name`, `Artist name` | One artist value has extra surrounding spaces. |
| `My Spotify Library.csv` | The two required headers plus `Album`, `Playlist name`, `Type`, `ISRC`, `Spotify - id` | It has a UTF-8 byte-order mark (BOM) and extra fields to preserve for step 2. |

## 1. Set the input contract before editing code

Write down the agreed behavior in the loader's documentation and tests:

- **Required data:** Each nonblank song row needs a nonempty track name and artist name. A CSV with no valid songs should stop with a clear message.
- **Supported headers:** Start with the exact headers used by the supplied files. Define any additional aliases explicitly; do not guess that arbitrary column names mean title or artist. Normalize supported names to internal names such as `track_name` and `artist_name`.
- **Original data:** Keep the original headers and values alongside normalized fields. For example, a trimmed `artist_name` may be used for matching, while the original `Artist name` cell remains available. Unknown extra columns must not disappear.
- **Duplicate or missing headers:** Reject them with a message naming the problem. A simple dictionary can overwrite duplicate column names, so detect duplicates before building per-row dictionaries.
- **Malformed rows:** Decide and document how to handle too many or too few cells. Recommended rule: report every bad row found, then stop the import before any download; never silently drop a song or start a partial download run.
- **Blank rows:** Ignore fully empty rows, but report an incomplete row that has only a track or only an artist.
- **Row location:** Give an understandable record number or source line in each error. Quoted fields can span physical lines, so label the number accurately.

Use an explicit initial mapping for the known export fields:

| CSV header | Internal name | Meaning |
| --- | --- | --- |
| `Track name` | `track_name` | Required song title. |
| `Artist name` | `artist_name` | Required artist. |
| `Album` | `album` | Album information, if supplied. |
| `Playlist name` | `playlist_name` | Playlist context; never the MP3 album. |
| `Type` | `export_type` | Keep as export context. |
| `ISRC` | `isrc` | Keep for later recording lookup. |
| `Spotify - id` | `spotify_id` | Keep as a source identifier. |

Preserve the original labels and values, including unknown columns. This milestone does not use the extra fields for lookup or MP3 tags.

## 2. Make file selection match the supported format

Update `find_input_file()` and its messages so users are offered CSV files as normal inputs. If `INPUT_FILE` names a missing file, show that filename and where the program looked. If several CSV files are found, show numbered choices and reject `0`, negative numbers, nonnumbers, and choices beyond the list.

For a `.txt` file that appears to contain CSV data:

1. Preview its first few rows without changing the file.
2. Validate its encoding, headers, column structure, and required values with the same rules used for `.csv`.
3. Explain that the program uses CSV files and ask whether to rename this file with a `.csv` extension.
4. If the user declines, leave the file untouched and end input selection without downloading.
5. If a destination `.csv` already exists, leave both files untouched and explain the collision. Rename only after explicit confirmation and successful validation.

Do not show `.txt` as directly supported if the program has not performed this conversion. Do not change `download_errors.txt` or mistake it for a song list.

## 3. Read and validate the CSV

Keep `csv.DictReader` for the actual rows. Open files as UTF-8 with BOM handling and the correct CSV newline handling; do not split lines on commas. Inspect the header before iterating rows so missing and duplicate names can be reported clearly. Validate every row before returning the song list.

If the first row appears to contain a song rather than headers, show that row in a preview and ask whether to treat it as data. For an unambiguous two-column list, a confirmed choice may supply the two required column names in memory. Otherwise, ask the user to fix the file. Never silently treat the first song as a header or rewrite the CSV without permission.

Remove the current `print(f"{row}\n{songs}")` debug output. After loading, show a short summary: input filename, number of valid songs, and any errors. Keep the existing confirmation before downloads.

## 4. Define the handoff to the following milestone

The loader should return each song with its normalized track and artist, the original CSV fields, and its source row location. Step 2 of [todo.md](todo.md) will carry that whole record through matching, downloading, and tagging. Do not add MusicBrainz calls, change YouTube selection, or write MP3 tags as part of this input milestone.

If the old download loop still reads `item['Track name']` and `item['Artist name']`, either keep those keys available during this milestone or update the loop to read the normalized names. The program must still show the same title and artist for the supplied CSV files.

## 5. Verify the milestone

Use temporary test CSVs and exercise the loader without contacting YouTube or downloading audio. Check at least:

- `songs.csv` loads both songs and trims the example artist in its normalized value.
- `My Spotify Library.csv` loads with its BOM and retains all extra fields per row.
- A quoted comma in a title or album stays within one field; UTF-8 characters survive unchanged.
- Missing, duplicate, and likely headerless headers receive distinct, useful messages. A headerless first song is never lost.
- Blank rows are ignored; missing title/artist and rows with too many or too few cells report the correct location and prevent a partial download run.
- `.txt` conversion handles accept, decline, invalid content, and an existing `.csv` destination without losing either file.
- The chooser rejects invalid numbers and never offers `download_errors.txt` as input.
- The on-screen song list remains correct and no full-row debug dump appears.

**Done when:** both supplied CSVs load correctly, invalid input cannot silently lose songs, file selection tells the truth about supported formats, and the input path can be checked without invoking the downloader. Then mark step 1 complete in [todo.md](todo.md) and move to its step 2, preserving row metadata throughout the program.
