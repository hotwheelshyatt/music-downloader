"""Conservative recording and YouTube matching for the local downloader.

MusicBrainz API: https://musicbrainz.org/doc/MusicBrainz_API
Search fields: https://musicbrainz.org/doc/MusicBrainz_API/Search
Rate limits: https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting
"""

import json
import re
import time
import unicodedata
from difflib import SequenceMatcher
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


MB_ROOT = "https://musicbrainz.org/ws/2/"
MB_USER_AGENT = "MusicDownloader/0.2 (https://github.com/hotwheelshyatt/music-downloader)"
MB_REQUEST_INTERVAL = 1.1
MIN_RECORDING_SCORE = 80
MIN_YOUTUBE_SCORE = 80
MIN_SCORE_LEAD = 10
_last_mb_request = 0.0
_mb_cache = {}


class MatchError(RuntimeError):
    """No verified recording or confident video match was available."""


def normalized(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.findall(r"\w+", value))


def similarity(left, right):
    return SequenceMatcher(None, normalized(left), normalized(right)).ratio()


def version_markers(value):
    text = normalized(value)
    markers = set()
    patterns = {
        "live": r"\blive\b",
        "cover": r"\bcover\b",
        "remix": r"\b(remix|mix)\b",
        "slowed": r"\b(slowed|slow)\b",
        "sped up": r"\b(sped up|speed up|spedup)\b",
        "nightcore": r"\bnightcore\b",
        "karaoke": r"\bkaraoke\b",
        "instrumental": r"\binstrumental\b",
    }
    for marker, pattern in patterns.items():
        if re.search(pattern, text):
            markers.add(marker)
    return markers


def artist_credit(recording):
    credit = recording.get("artist-credit") or []
    if isinstance(credit, str):
        return credit
    return "".join(
        part if isinstance(part, str) else part.get("name", "") + part.get("joinphrase", "")
        for part in credit
    ).strip()


def valid_isrc(value):
    code = re.sub(r"[\s-]", "", str(value or "")).upper()
    return code if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}\d{7}", code) else None


def musicbrainz_get(path, params=None):
    """Read JSON, throttle each request, and retry one transient 503/429."""
    global _last_mb_request
    query = urlencode({**(params or {}), "fmt": "json"})
    url = MB_ROOT + path + ("?" + query if query else "")
    for attempt in range(2):
        wait = MB_REQUEST_INTERVAL - (time.monotonic() - _last_mb_request)
        if wait > 0:
            time.sleep(wait)
        request = Request(url, headers={"User-Agent": MB_USER_AGENT, "Accept": "application/json"})
        _last_mb_request = time.monotonic()
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code in (429, 503) and attempt == 0:
                time.sleep(2)
                continue
            raise MatchError(f"MusicBrainz request failed (HTTP {error.code}).") from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise MatchError(f"MusicBrainz is unavailable: {error}.") from error
    raise MatchError("MusicBrainz is unavailable after a retry.")


def recording_score(row, candidate, expected_isrc=None):
    title = candidate.get("title", "")
    artist = artist_credit(candidate)
    title_match = similarity(row["track_name"], title)
    artist_match = similarity(row["artist_name"], artist)
    if title_match < 0.78 or artist_match < 0.75:
        return 0
    if version_markers(title) != version_markers(row["track_name"]):
        return 0
    score = round(45 * title_match + 35 * artist_match)
    if expected_isrc and expected_isrc in candidate.get("isrcs", []):
        score += 20
    album = normalized(row.get("album"))
    if album:
        releases = candidate.get("releases") or []
        if any(normalized(release.get("title")) == album for release in releases):
            score += 10
    return min(score, 100)


def _search_recordings(row):
    # Lucene field queries use quoted text; escape syntax inside each value.
    def quoted(value):
        return '"' + re.sub(r'([+\-!(){}\[\]^"~*?:\\/|&])', r'\\\1', value) + '"'

    query = f'recording:{quoted(row["track_name"])} AND artist:{quoted(row["artist_name"])}'
    data = musicbrainz_get("recording/", {"query": query, "limit": 10})
    return data.get("recordings", [])


def _pick_release(row, recording):
    album = normalized(row.get("album"))
    if not album:
        return None
    matches = [release for release in recording.get("releases", [])
               if normalized(release.get("title")) == album]
    return matches[0] if len(matches) == 1 else None


def identify_recording(row):
    """Return a verified recording and optional release, or refuse ambiguity."""
    key = (row["track_name"], row["artist_name"], row.get("album"), row.get("isrc"))
    if key in _mb_cache:
        return _mb_cache[key]
    isrc = valid_isrc(row.get("isrc"))
    if isrc:
        candidates = musicbrainz_get(f"isrc/{isrc}", {"inc": "artist-credits"}).get("recordings", [])
        if not candidates:
            raise MatchError(f"ISRC {isrc} was not found in MusicBrainz; check the CSV value.")
    else:
        candidates = _search_recordings(row)
    unique = {candidate.get("id"): candidate for candidate in candidates if candidate.get("id")}
    ranked = sorted(
        ((recording_score(row, candidate, isrc if isrc else None), candidate)
         for candidate in unique.values()),
        key=lambda pair: pair[0], reverse=True,
    )
    if not ranked or ranked[0][0] < MIN_RECORDING_SCORE:
        raise MatchError("No MusicBrainz recording matches the requested title and artist confidently.")
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < MIN_SCORE_LEAD:
        raise MatchError("MusicBrainz found multiple plausible recordings; no automatic download.")
    chosen_id = ranked[0][1]["id"]
    recording = musicbrainz_get(
        f"recording/{chosen_id}",
        {"inc": "artist-credits+releases+release-groups+isrcs"},
    )
    if isrc and isrc not in recording.get("isrcs", []):
        raise MatchError("MusicBrainz recording lookup disagrees with the CSV ISRC.")
    if recording_score(row, recording, isrc) < MIN_RECORDING_SCORE:
        raise MatchError("MusicBrainz recording details do not verify the requested song.")
    release = _pick_release(row, recording)
    target = {
        "id": recording["id"],
        "title": recording["title"],
        "artist": artist_credit(recording),
        "length": recording.get("length"),
        "isrc": isrc,
        "release": release,
        "confidence": ranked[0][0],
    }
    _mb_cache[key] = target
    return target


def youtube_score(row, target, video):
    title = video.get("title") or ""
    if not title:
        return 0, ["missing video title"]
    wanted_versions = version_markers(row["track_name"]) | version_markers(target["title"])
    unwanted = version_markers(title) - wanted_versions
    if unwanted:
        return 0, ["unrequested version: " + ", ".join(sorted(unwanted))]
    title_text = normalized(title)
    target_title = normalized(target["title"])
    if target_title and target_title in title_text:
        score = 45
        reasons = ["matching title"]
    elif similarity(target["title"], title) >= 0.8:
        score = 30
        reasons = ["similar title"]
    else:
        return 0, ["title does not match"]
    artist = normalized(target["artist"])
    source_text = normalized(" ".join(str(video.get(key) or "") for key in
                                      ("title", "artist", "uploader", "channel", "description")))
    if artist and artist in source_text:
        score += 30
        reasons.append("artist found in video metadata")
    else:
        return 0, ["artist cannot be verified"]
    length = target.get("length")
    duration = video.get("duration")
    if isinstance(length, (int, float)) and isinstance(duration, (int, float)):
        difference = abs(length / 1000 - duration)
        if difference <= 5:
            score += 15
            reasons.append("duration within 5 seconds")
        elif difference <= 15:
            score += 8
            reasons.append("duration within 15 seconds")
        elif difference > 30:
            score -= 30
            reasons.append("duration differs by over 30 seconds")
    release = target.get("release")
    album_name = normalized(release.get("title")) if release else ""
    album_evidence = normalized(video.get("album"))
    if album_name and album_name in album_evidence:
        score += 5
        reasons.append("album mentioned")
    isrc = target.get("isrc")
    if isrc and isrc.casefold() in str(video.get("description") or "").casefold():
        score += 10
        reasons.append("ISRC mentioned")
    return min(max(score, 0), 100), reasons


def choose_youtube_video(row, target, entries, metadata_for_url):
    """Inspect multiple videos and require a clear high-confidence winner."""
    ranked = []
    for entry in entries:
        video_id = entry.get("id")
        if not video_id or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            continue
        url = f"https://www.youtube.com/watch?v={video_id}"
        details = metadata_for_url(url)
        if not details:
            continue
        score, reasons = youtube_score(row, target, details)
        ranked.append((score, url, details, reasons))
    ranked.sort(key=lambda result: result[0], reverse=True)
    if not ranked or ranked[0][0] < MIN_YOUTUBE_SCORE:
        raise MatchError("No YouTube candidate reached the confidence threshold; no download.")
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < MIN_SCORE_LEAD:
        raise MatchError("YouTube candidates are too close to choose safely; no download.")
    return ranked[0]
