# Completed step: fix the three reported bugs

This milestone followed the previous plan in [bugs_to_fix.md](bugs_to_fix.md). The implementation is complete and the local regression suite passes.

1. Removed the unsupported `SEARCH_YOUTUBE` switch. New rows use the documented search path.
2. Kept each validated CSV row intact through processing. MusicBrainz identifies a recording by ISRC when valid, otherwise by title and artist, then checks the detailed recording. Ambiguous or unavailable results skip the row. [Provider research and confidence rules](provider_research.md) describe the decision.
3. Changed YouTube search to return several candidates. The program reads their details and requires a score of at least 80 with a lead of at least 10 over the runner-up. It rejects unrequested covers, live versions, remixes, and other altered versions before downloading.
4. Moved downloads into a temporary directory, then tags and publishes the accepted MP3. Filenames use `Artist - Track.mp3`; a different or unverified existing recording leads to a stable MusicBrainz ID suffix. Existing recordings are skipped only when `SKIP_EXISTING` is enabled. Publishing refuses to overwrite a different recording.
5. Added MusicBrainz recording and release identifiers and a verified ISRC to tags when available. CSV title, artist, and album retain priority.

## Verification

- The original 28 CSV input tests still pass.
- The expanded suite covers MusicBrainz selection, invalid and absent ISRC behavior, ambiguous results, a later good YouTube result after a cover, low confidence, ties, requested live versions, full-row processing, filenames, collisions, and ID3 recording identity.
- Run the full suite with `python3 -B -m unittest discover -s tests -q` and `venv/bin/python -B -m unittest discover -s tests -q`. The virtual environment also verifies a real Mutagen ID3 round trip.
- Automated tests use temporary files and mocked service responses. No live YouTube download was run because YouTube access is blocked on this computer. The previously reported 403 remains an environment issue.

## Next development step

Continue the remaining [todo.md](todo.md) roadmap: finish metadata source and tag decisions, verify release artwork through the Cover Art Archive, improve per-row error reporting, and then run a permitted live end-to-end download when YouTube access is available. Keep ambiguous recording and release data empty until it can be justified.
