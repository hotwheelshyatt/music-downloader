# Next step: fix the open bugs

The CSV input milestone is complete. The next milestone is to resolve **all three open issues** in [bugs_to_fix.md](bugs_to_fix.md): first-result YouTube selection, MP3 filename collisions, and the unusable `SEARCH_YOUTUBE = False` setting. This is a plan for the next implementation pass; none of these fixes is marked complete yet.

The recorded YouTube HTTP 403 came from a network block on this computer. The `.txt` conversion bug is already fixed. Neither belongs in this bug-fix pass unless new evidence shows a separate problem.

## 1. Keep a baseline and settle the behavior

Before changing the download path, run `python3 -B -m unittest discover -s tests -q` (and the same command with `venv/bin/python`). Keep the existing CSV tests passing. Add focused tests that reproduce each of the three open bugs without contacting YouTube or writing music into the real destination folder.

Decide these behaviors explicitly and record them in code comments or documentation:

- **Unavailable direct-URL mode:** Recommended choice: remove the `SEARCH_YOUTUBE` switch for now and always use the supported search path. If direct URLs are needed instead, first define their CSV column, validation, and how a row chooses between search and a supplied URL. Do not leave a switch that makes every new song fail.
- **Same filename:** Define when an existing MP3 is the *same recording* and may be skipped, and when it is a different recording that needs a distinct name. An existing filename alone is insufficient evidence.
- **Uncertain match:** Define a minimum confidence rule and what happens when the best YouTube results are tied or below that rule. The safe outcome is to report the row and avoid an automatic download.

## 2. Fix the unusable YouTube-search setting

In `main.py`, `process_song()` currently raises when `SEARCH_YOUTUBE` is false because no direct URL can reach it. Apply the decision from step 1:

1. If removing the switch, remove its configuration line and dead branch, keep the working search path, and update README guidance. Do not suggest that users can disable search.
2. If supporting direct URLs, carry a validated URL from the CSV row through `main()` into `process_song()`. Define what happens when the URL is blank, invalid, or present alongside search metadata.
3. Test the selected behavior and confirm that no documented configuration value causes every song to fail before downloading.

## 3. Fix output filenames and duplicate checks

`process_song()` and `download_song()` currently use a title-only MP3 filename. Both must use one shared naming and identity rule; otherwise one function may skip a file that the other would name differently.

1. Start with a safe `Artist - Track name.mp3` base name. Apply the same filename cleaning in the early skip check, the `yt-dlp` output template, and the final MP3 lookup.
2. Decide how to distinguish two recordings by the same artist with the same title. Prefer a stable, verified recording identifier once one is available. If the program cannot prove two files are the same recording, do not overwrite or silently skip one as a duplicate; report the collision or choose an unambiguous stable suffix.
3. Decide how `SKIP_EXISTING = True` and `False` behave for a verified same recording and for a different recording. Neither setting should overwrite a different recording accidentally.
4. Consider filenames that become equal after cleaning, case differences on different filesystems, and repeated rows in the input CSV.
5. Test different artists with one title, one artist with multiple recordings of one title, a true repeated song, and both values of `SKIP_EXISTING` using a temporary destination.

## 4. Replace first-result selection with verified matching

This bug needs more than changing `entries[0]`. Complete the relevant work in [todo.md](todo.md) steps 2–8 before allowing automatic selection. Keep the CSV's track name and artist as the requested title and artist.

1. **Carry the full row:** Pass the normalized title and artist plus original CSV fields (including album and ISRC when present) through the lookup and search flow. Do not discard them at `process_song()`.
2. **Research the metadata provider:** Compare MusicBrainz and Discogs, and Gracenote only if access is realistic. Verify MusicBrainz API endpoints, fields, rate limits, User-Agent and usage rules from primary documentation. Use MusicBrainz as the initial provider if that research supports it.
3. **Identify the target:** Use valid CSV identifiers, title, artist, album, and version clues to evaluate multiple MusicBrainz matches. Keep recordings, releases, and release groups distinct. Record why a recording and release were selected; stop the row when no reliable target can be identified.
4. **Inspect several YouTube results:** Return candidate information rather than one URL. Gather only fields actually available to the search flow, and document which fields need a further metadata lookup.
5. **Score candidates:** Compare each candidate with the verified target using title, artist, duration, album or identifiers when available, description, channel, and version clues. Penalize covers, live performances, remixes, slowed or sped-up versions, nightcore, karaoke, instrumentals, and unrelated videos unless the CSV asks for that version. Do not treat a matching title alone as proof.
6. **Apply a confidence rule:** Download only a candidate that clears the documented threshold and is clearly better than alternatives. Report the chosen URL, score, and main reasons. For a tie, weak match, or missing target, report the ambiguity and continue to the next row without downloading.

Keep metadata source priority from [todo.md](todo.md): CSV first, verified MusicBrainz second, YouTube third, and empty when uncertain. Do not put `Playlist name` in the album tag. Later tag and artwork improvements remain separate TODO work unless they are needed to verify the selected recording.

## 5. Test the combined download path

Use mocked MusicBrainz and YouTube responses for repeatable tests; do not make the automated suite depend on live services. Check at least:

- The first YouTube result is a cover or live version and a later result matches the target; only the later result can be selected.
- No result reaches the threshold, or two results are too close; no download occurs and the reason is shown.
- A CSV row explicitly requests an alternate version; the matcher does not incorrectly reject that version.
- MusicBrainz is unavailable or returns ambiguous matches; the row is reported and later rows continue.
- Two artists share a title, one artist has two recordings with one title, and an MP3 already exists; no different recording is skipped or overwritten.
- The chosen `SEARCH_YOUTUBE` configuration behavior works as documented.
- The existing CSV input suite still passes, including the supplied `songs.csv` and `My Spotify Library.csv` fixtures.

A live end-to-end check can be done only where YouTube is reachable and with a small, permitted test song. Record separately whether it was run; mocked tests do not prove live site access.

## Done when

All three open issues in [bugs_to_fix.md](bugs_to_fix.md) have a verified fix or a documented removal of the unsupported setting, and their regression tests pass. Update [todo.md](todo.md), [bugs_to_fix.md](bugs_to_fix.md), and the README to match the implemented behavior. Leave the network-block 403 classified as an environment issue unless new testing identifies another cause.
