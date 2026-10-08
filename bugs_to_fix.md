# Bug report

## Current status

The three bugs found after the CSV input milestone are fixed and have regression tests. The full local suite passes in both the system Python and the project virtual environment. Tests mock MusicBrainz and YouTube; they do not prove live YouTube access or audio identity. A live download remains untested because this computer's YouTube connection is blocked.

## Resolved bugs

### First YouTube result was downloaded without verification

**Previous behavior:** `search_youtube()` returned `entries[0]`, which could be a cover, live version, or unrelated upload.

**Fix:** The program first identifies a MusicBrainz recording, inspects up to five YouTube results, scores title, artist, duration, explicit album and ISRC evidence, rejects unwanted versions, and skips weak or close matches. Tests cover a first-result cover with a better later match, weak candidates, ties, and a requested live version.

### Different songs could share one MP3 filename

**Previous behavior:** The output filename used only the title, so `Same.mp3` could stand for different artists or recordings.

**Fix:** Output starts with `Artist - Track.mp3`. The saved MusicBrainz recording ID identifies repeats; another or unverified recording gets a stable ID suffix. New files are created exclusively, and an existing file is replaced only when its ID matches. Tests cover different artists, same-artist recordings, legacy files, case and cleaned-name collisions, repeat rows, and both `SKIP_EXISTING` settings.

### Disabling YouTube search made every new song fail

**Previous behavior:** `SEARCH_YOUTUBE = False` raised before a URL could be supplied.

**Fix:** The unsupported switch and dead branch were removed. Search is the only supported input path, and the README describes that path.

## Diagnosed environment issue

The `HTTP Error 403: Forbidden` recorded for `Hailing Taquitos - Parry Gripp` was traced by the user to a network block preventing access to YouTube. Restore YouTube access before retrying that song. Other 403 responses should be diagnosed separately.

## Earlier CSV input fixes

The first milestone fixed misleading `.txt` picker behavior, malformed CSV line reporting, a `.txt` conversion collision race, and leading blank CSV rows. Their regression tests remain in the suite.
