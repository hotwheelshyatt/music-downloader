# Music Downloader: development TODO

## Current status

CSV input, MusicBrainz recording lookup, multiple YouTube candidate scoring, and recording-aware MP3 filenames are implemented. Uncertain matches are skipped. The remaining work is to improve tag sources, release artwork, per-row reporting, and end-to-end verification.

**Target flow:** CSV validation → preserve and normalize row data → identify a recording and release with MusicBrainz → search and evaluate multiple YouTube candidates → download only a confident match → apply tags and artwork → record a clear outcome for every row.

**Non-negotiable rules**

- Keep the CSV's `Track name` and `Artist name` as the primary MP3 title and artist. A database or YouTube spelling must not silently replace them.
- For every other tag, prefer valid CSV data, then verified MusicBrainz data, then YouTube data. Leave an uncertain field empty.
- `Playlist name` is not the MP3 album.
- Do not automatically download when the target recording or YouTube candidate is ambiguous. Explain the reason and continue with later rows.
- Preserve the original CSV fields alongside normalized fields so no export data disappears.

## Next step: finish metadata and artwork

- [ ] Map each supported MP3 tag to a source and priority: CSV first, verified MusicBrainz second, reliable YouTube metadata last. Keep uncertain fields empty.
- [ ] Verify Cover Art Archive access and use artwork from the selected release when available. Use a YouTube thumbnail only when no reliable release image is available.
- [ ] Add focused tests for tag priority, conflicting values, missing artwork, artwork fallback, and failures that should not stop later songs.
- [ ] Improve the per-row log and end summary so skipped, ambiguous, and failed rows have clear reasons and next actions.
- [ ] Run a permitted live end-to-end download when YouTube access is available. Automated tests currently use mocked services.

Matching rules and the provider decision are in [provider_research.md](provider_research.md). Track any newly discovered code bugs in [bugs_to_fix.md](bugs_to_fix.md). The earlier YouTube HTTP 403 was caused by a network block on this computer.

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

- [x] Document how MusicBrainz distinguishes recordings, releases, and release groups, and why an ISRC does not prove a particular album edition. See [provider_research.md](provider_research.md).
- [ ] Define how to score or otherwise evaluate multiple MusicBrainz matches using title, artist, ISRC, album, duration when available, and version clues. Decide tie-breaking and a minimum confidence rule.
- [x] Use a release only when one linked release clearly matches the CSV album; otherwise leave the release unknown. Skip when the recording itself is ambiguous.

**Implement**

- [x] Select a recording and, where justified, a release with recorded evidence; reject ambiguous matches.
- [x] Skip the row before YouTube selection when no sufficiently identified recording exists.

### 6. Search YouTube for multiple candidates

**Decide first**

- [x] Search from the CSV title, artist, and optional album; use the ISRC and version clues for verification rather than assuming they work as YouTube search terms.
- [x] Inspect up to five results and fetch each candidate's available video metadata before selection.

**Implement**

- [x] Search and retain multiple candidates rather than selecting `entries[0]`.

### 7. Score YouTube candidates

**Decide first**

- [x] Define the title, artist, duration, explicit album, ISRC, and version checks in [provider_research.md](provider_research.md).
- [x] Reject unrequested covers, live performances, remixes, slowed or sped-up versions, nightcore, karaoke, instrumentals, and unrelated videos.
- [x] Require evidence beyond title and artist; skip weak candidates when metadata is missing.

**Implement**

- [x] Rank candidates against the verified target and retain the evidence behind each score.

### 8. Apply confidence and ambiguity rules

**Decide first**

- [x] Require a score of at least 80 and a lead of at least 10 points; skip ambiguous rows.

**Implement**

- [x] Download no candidate below the threshold. Report the selected URL, confidence, and main reasons; log ambiguous or rejected rows.

### 9. Download the selected audio

**Decide first**

- [ ] Record the selected source and processing stage per row so a failed attempt is easy to diagnose.

**Implement**

- [x] Pass only the accepted candidate to `yt-dlp`, convert to MP3 in a temporary folder, and continue after a row fails.

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

- [x] Use a safe artist-and-title filename and a stable recording ID suffix when names collide.
- [x] Skip only a file with the same saved recording ID; give a different or unidentified recording a separate name.

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
