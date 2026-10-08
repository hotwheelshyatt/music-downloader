# Music Downloader: implementation plan and bug report

## Current behavior and goal

`main.py` validates CSV input, preserves normalized and original row fields, and can convert CSV-formatted `.txt` files after confirmation. It now checks MusicBrainz for a recording, scores several YouTube candidates, and saves a matched MP3 under an artist-and-title name with recording-aware collision handling. Uncertain matches are skipped. Metadata and artwork work remains below.

**Target flow:** CSV validation → preserve and normalize row data → identify a recording and release with MusicBrainz → search and evaluate multiple YouTube candidates → download only a confident match → apply tags and artwork → record a clear outcome for every row.

**Non-negotiable rules**

- Keep the CSV's `Track name` and `Artist name` as the primary MP3 title and artist. A database or YouTube spelling must not silently replace them.
- For every other tag, prefer valid CSV data, then verified MusicBrainz data, then YouTube data. Leave an uncertain field empty.
- `Playlist name` is not the MP3 album.
- Do not automatically download when the target recording or YouTube candidate is ambiguous. Explain the reason and continue with later rows.
- Preserve the original CSV fields alongside normalized fields so no export data disappears.

## Completed bug-fix milestone

The three issues in [bugs_to_fix.md](bugs_to_fix.md) were addressed. [steps.md](steps.md) records the implementation and test results; [provider_research.md](provider_research.md) records the matching rules and source decision.

- [x] Remove the unsupported `SEARCH_YOUTUBE = False` setting and dead branch.
- [x] Use one artist-and-title naming rule and a MusicBrainz recording ID for duplicate checks.
- [x] Preserve the full CSV row, identify a MusicBrainz recording, evaluate multiple YouTube results, and skip weak or ambiguous matches.
- [x] Add regression tests for the three bugs, run the local test suite, and update the README and bug statuses.

The recorded HTTP 403 was caused by a network block on this computer and is not an open code bug. The `.txt` conversion issue is resolved.

## Implementation roadmap

### 1. Normalize and validate CSV input

**Decide first**

- [x] List supported header names and their normalized names. Specify how unknown columns and duplicate headers are retained or reported.
- [x] Define validation for missing title/artist, blank rows, malformed rows, and a likely missing header. Decide what the user sees before any proposed correction.
- [x] Define the `.txt` conversion flow: preview CSV-like text, validate it, ask before renaming to `.csv`, and refuse to overwrite an existing file. The picker must not claim that an unsupported file can be loaded directly.

**Implement**

- [x] Use `csv.DictReader` for the two-column `songs.csv` and wider TuneMyMusic/Spotify-style exports such as `My Spotify Library.csv`.
- [x] Handle quoted commas, UTF-8, and UTF-8 BOM. Report the row number and a specific fix for bad data.
- [x] If the first row appears to be song data, ask whether to treat it as data; never silently discard it as a header.
- [x] Remove the current per-row debug dump after useful import summaries and errors exist.

### 2. Preserve each row's metadata

**Decide first**

- [ ] Define one per-song record that holds normalized title/artist, every original CSV field, source row number, and later lookup/match decisions. Decide how blank or conflicting values are represented.

**Implement**

- [x] Keep the full per-song record available through matching and tagging. `process_song()` no longer reduces it to only title and artist.
- [x] Retain `Album`, `ISRC`, `Playlist name`, `Type`, `Spotify - id`, and other original export fields without treating all of them as MP3 tags.

### 3. Research music metadata providers

**Research and record a decision before integration**

- [ ] Compare MusicBrainz and Discogs, plus Gracenote if it is realistically accessible. For each, verify API availability, authentication, cost, rate limits, User-Agent requirements where applicable, usage/licensing restrictions, recording identification quality, release metadata quality, ISRC support, artwork availability, and suitability for this personal/local downloader.
- [x] Record verified findings and limits of the provider comparison in [provider_research.md](provider_research.md).
- [x] Use MusicBrainz as the initial source; defer other providers until their documentation and terms can be verified.

### 4. Integrate MusicBrainz lookup

**Decide first**

- [x] Verify the relevant MusicBrainz API endpoints, response fields, lookup/search behavior, rate limits, User-Agent requirements, and usage rules.
- [x] Use a valid ISRC first; otherwise search by title and artist and compare album where available. An invalid ISRC does not block title/artist search.
- [x] Use a 20-second timeout, one retry for throttling, and skip the row if MusicBrainz is unavailable.

**Implement**

- [x] Look up candidate MusicBrainz matches for each row while following the verified usage rules.
- [x] Retain recording and selected release identifiers and match evidence for later selection and tags.

### 5. Identify the intended recording and release

**Decide first**

- [ ] Document how MusicBrainz distinguishes recordings, releases, and release groups, and which one each CSV field can identify. Do not treat a release group as a specific release or an ISRC as proof of a particular album edition.
- [ ] Define how to score or otherwise evaluate multiple MusicBrainz matches using title, artist, ISRC, album, duration when available, and version clues. Decide tie-breaking and a minimum confidence rule.
- [ ] Define which release to use for release-specific tags and artwork when the recording appears on multiple releases. Decide how to report an ambiguous or absent match.

**Implement**

- [x] Select a recording and, where justified, a release with recorded evidence; reject ambiguous matches.
- [x] Skip the row before YouTube selection when no sufficiently identified recording exists.

### 6. Search YouTube for multiple candidates

**Decide first**

- [ ] Define search queries from the CSV and verified target metadata, including when album, ISRC, or version terms actually help.
- [ ] Decide how many results to inspect and which YouTube fields can be collected for comparison before download.

**Implement**

- [x] Search and retain multiple candidates rather than selecting `entries[0]`.

### 7. Score YouTube candidates

**Decide first**

- [ ] Define a readable score or equivalent rule using track title, artist, album, duration, ISRC or other identifiers when present, video title/description, channel information, and version indicators.
- [ ] Penalize or reject covers, live performances, remixes, slowed or sped-up versions, nightcore, karaoke, instrumentals, and unrelated videos unless the CSV explicitly requests that version.
- [ ] Decide how missing or unreliable YouTube metadata affects confidence. Do not treat a matching title alone as proof of the intended recording.

**Implement**

- [x] Rank candidates against the verified target and retain the evidence behind each score.

### 8. Apply confidence and ambiguity rules

**Decide first**

- [ ] Choose and document a reasonable minimum confidence threshold and tie/near-tie rule. Define whether ambiguous rows are skipped or offered for explicit user choice.

**Implement**

- [x] Download no candidate below the threshold. Report the selected URL, confidence, and main reasons; log ambiguous or rejected rows.

### 9. Download the selected audio

**Decide first**

- [ ] Define what download state is kept per row, including the selected source, failed attempts, and any partially created files.

**Implement**

- [ ] Pass only the accepted candidate to `yt-dlp`, convert to MP3, and continue processing later rows if one download fails.

### 10. Write MP3 metadata

**Decide first**

- [ ] Verify which MusicBrainz recording and release fields map to supported MP3 tags. Document field-by-field source priority and how conflicting or invalid values are handled.
- [ ] Keep CSV track name and artist as the MP3 title and artist. Exclude `Playlist name` from the album tag.

**Implement**

- [ ] Apply valid CSV metadata first, verified MusicBrainz metadata second, and YouTube metadata only for still-missing reliable fields. Leave unknown fields empty.
- [ ] Record the source of important tag values so incorrect metadata can be diagnosed later.

### 11. Select and embed artwork

**Decide first**

- [ ] Verify how to obtain appropriate MusicBrainz Cover Art Archive artwork for the selected release and any relevant usage conditions. Decide what counts as a reliable alternative release-art source.
- [ ] Set the artwork order: selected release's Cover Art Archive image → another justified release-art source → YouTube thumbnail → no artwork.

**Implement**

- [ ] Embed the highest-priority usable image. Do not automatically use a YouTube thumbnail when reliable release artwork is available. Handle missing or invalid images without failing the song.

### 12. Handle output names and duplicates

**Decide first**

- [ ] Define a filename using artist and title, with safe character handling and a stable way to distinguish multiple recordings by the same artist with the same title.
- [ ] Define when an existing file is truly the same recording, when to skip it, and when to choose another name. Never overwrite a different recording accidentally.

**Implement**

- [x] Keep `Artist A - Song.mp3` and `Artist B - Song.mp3` separate.
- [x] Use the MusicBrainz recording ID to skip a verified repeat or give a different recording a stable suffix.

### 13. Handle and log errors per row

**Decide first**

- [ ] Define actionable messages for CSV, MusicBrainz, YouTube search, low-confidence, download, tagging, and artwork failures. Decide which failures skip a row versus allow a partial MP3.

**Implement**

- [ ] Continue with later songs after a row fails. Log the row number, requested song, processing stage, reason, and next useful action without hiding the original error.
- [ ] Keep a clear end summary of downloaded, skipped, ambiguous, and failed rows.

### 14. Test the complete flow

- [ ] Cover the two-column sample and wider export; quoted commas; UTF-8/BOM; blank and malformed rows; missing headers; and `.txt` conversion confirmation/collision.
- [ ] Cover valid, invalid, and absent ISRC; multiple or ambiguous MusicBrainz matches; recording versus release selection; unavailable/rate-limited metadata service; and conflicting CSV/database values.
- [ ] Cover a correct YouTube match, each unwanted version type, an explicitly requested alternate version, ties, low confidence, missing metadata, and a failed search that does not stop later rows.
- [ ] Verify tag priority, artwork fallback, distinct-artist duplicate titles, same-artist multiple recordings, existing files, interrupted downloads, and continuation after a failure.

### 15. Optional later enhancement: audio fingerprinting

- [ ] Investigate AcoustID/Chromaprint only after the first implementation works. Proposed flow: YouTube candidate audio → audio fingerprint → AcoustID → MusicBrainz recording. Research cost, API/usage rules, added downloads, and whether it materially improves matching before adding it. This is not required for the first version.

## Issue history and open bugs

The three code issues and their regression evidence are tracked in [bugs_to_fix.md](bugs_to_fix.md). The bug-fix milestone above covers all three.

### Diagnosed network issue: YouTube search returned HTTP 403

- **Evidence:** `download_errors.txt` records `Hailing Taquitos - Parry Gripp` failing during YouTube search with `HTTP Error 403: Forbidden`.
- **Confirmed cause for this incident:** Testing found a network block on this computer that prevented access to YouTube. The recorded 403 came from unavailable YouTube connectivity; it is not an open `yt-dlp` bug to investigate.
- **Action:** No code fix is planned for this incident. Restore YouTube access on the network before retrying the song. Other HTTP 403 errors should be diagnosed separately rather than assumed to have the same cause.

### Resolved: picker offered `.txt` files that the loader rejected

- **Reproduction:** Set `INPUT_FILE = None`, select a `.txt` file, and load it.
- **Previous behavior:** `find_input_file()` offered the file; `load_songs()` raised `Input file must be CSV or TXT.`
- **Resolution:** The picker labels `.txt` as a conversion choice. The program previews and validates it, asks before conversion, and refuses to overwrite an existing `.csv` file.

### Resolved: different songs shared one output filename

- **Previous behavior:** `download_song()` named MP3s from the title alone, and `SKIP_EXISTING` checked that name.
- **Resolution:** Artist and title form the base name. Existing files are compared using their saved MusicBrainz recording ID; an unknown or different recording receives an ID suffix, and publishing refuses to overwrite a different file.
