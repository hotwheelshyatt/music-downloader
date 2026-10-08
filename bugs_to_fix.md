# Bugs to fix

## Test results for the CSV input milestone

`python3 -B -m unittest discover -s tests -q` and `venv/bin/python -B -m unittest discover -s tests -q` each passed **28 tests**. The suite covers both supplied CSVs, UTF-8/BOM, quoted commas, multiline values, missing and duplicate headers, malformed rows, headerless input, `.txt` conversion and collision safety, picker choices, and the main program's input and error-continuation paths. Those tests use temporary files and mocked download dependencies; they do not contact YouTube or download audio.

**No failing CSV input tests remain from this milestone.** The issues below were reproduced with local, non-network probes or are directly visible in the current downstream code. They are outside the completed input milestone.

## Input issues found and fixed during testing

- A malformed quoted CSV row initially reported the wrong line because `DictReader.line_num` was stale after a parsing exception. The error now uses the underlying CSV reader's line number; the regression test checks it.
- A `.txt` conversion failure could have removed a destination file created by another process after the initial existence check. Conversion now creates the destination exclusively and only removes a partial file it created itself; the race and failed-copy tests pass.
- Leading blank CSV rows initially prevented header detection. The loader now skips them and reports the correct physical line for later records.

## Open issues

### 1. YouTube search always chooses the first candidate

- **Evidence:** A mocked search with two candidates returned the first candidate's URL without evaluating the second. `search_youtube()` uses `entries[0]`.
- **Impact:** A cover, live recording, remix, or unrelated video can be downloaded even when a better result exists.
- **Fix:** Follow [todo.md](todo.md) steps 3–8: identify the intended recording, compare multiple YouTube results, and require a confident match before downloading.

### 2. Different songs can share the same MP3 filename

- **Evidence:** With an existing `Same.mp3`, a mocked call to `download_song("Same", "Different Artist", ...)` returned the existing file and never invoked the downloader. The output name uses only the track title.
- **Impact:** Songs by different artists, or different recordings with the same title, can be incorrectly skipped or overwritten.
- **Fix:** Follow [todo.md](todo.md) step 12: include artist and enough recording identity in filenames and duplicate checks.

### 3. Disabling YouTube search makes every new song fail

- **Evidence:** With `SEARCH_YOUTUBE = False`, `process_song()` raises `SEARCH_YOUTUBE is disabled, but no direct URL was supplied.` There is no direct-URL input path in the current song record.
- **Impact:** The configuration switch cannot be used to download new songs.
- **Fix:** Decide whether direct URLs will be supported. If so, validate and pass them into `process_song()`; otherwise remove or clearly disable this configuration option.

## Diagnosed environment issue

The HTTP 403 recorded for `Hailing Taquitos - Parry Gripp` was traced by the user to a network block preventing access to YouTube. It is not an open `yt-dlp` code bug. Other HTTP 403 errors should be diagnosed on their own evidence.
