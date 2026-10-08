# Metadata provider decision

MusicBrainz is the initial metadata source for this personal downloader. Its documented read-only API supports recording searches, ISRC lookups, recording details, artist credits, and linked releases. The API is free for non-commercial use, requires a meaningful User-Agent, and asks clients to stay at or below one request per second. The implementation uses a 1.1-second gap between requests, a 20-second timeout, and one retry for HTTP 429 or 503.

| Provider | What was verified | Decision |
| --- | --- | --- |
| [MusicBrainz](https://musicbrainz.org/doc/MusicBrainz_API) | [Recording search fields](https://musicbrainz.org/doc/MusicBrainz_API/Search), [ISRC and recording relationships](https://musicbrainz.org/doc/Recording), JSON responses, read-only access, and [rate limits](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting). Live read-only responses confirmed the expected JSON fields. | Use for recording identification and a release only when one linked release clearly matches the CSV album. |
| [Discogs](https://www.discogs.com/developers) | Its developer page was unavailable from this environment (HTTP 403). Authentication, current limits, license, and field coverage were not verified. | No integration yet. Revisit only if MusicBrainz coverage proves insufficient. |
| [Gracenote](https://developer.gracenote.com/) | Developer access and current API terms could not be verified from this environment. | No integration planned without verified access and terms. |

## Identity and confidence rules

MusicBrainz distinguishes a **recording** (the audio performance), a **release** (a specific issue), and a **release group** (related issues). An ISRC helps identify a recording, but does not prove which release a user owns. The program therefore keeps the MusicBrainz recording ID as the file identity and sets a release ID only when a single linked release matches the CSV album. A release with multiple matching editions remains unknown.

The program accepts a MusicBrainz candidate only when title and artist are sufficiently similar, the requested version agrees, its score is at least 80, and it leads the next candidate by at least 10 points. An explicit, valid ISRC must appear in the detailed recording response. Missing or invalid ISRCs use title and artist search; ambiguous search results are skipped.

For YouTube, the program inspects up to five search results and fetches each result's details before scoring. The title and artist must agree. Close duration (15 points within five seconds, 8 within 15), explicit album metadata (5), and ISRC in the description (10) add evidence. A mismatch over 30 seconds subtracts 30. Unrequested live, cover, remix, slowed, sped-up, nightcore, karaoke, or instrumental versions are rejected. The winning result needs at least 80 points and a lead of at least 10; otherwise the row is skipped. These are conservative metadata checks, not proof from an audio fingerprint.

CSV track name and artist remain the MP3 title and artist. CSV album takes priority over a uniquely identified MusicBrainz release; other metadata falls back to the selected video's fields where available. `Playlist name` is never used as the MP3 album.
