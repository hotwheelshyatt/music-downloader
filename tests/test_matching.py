import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
import matching
import output_files


ROW = {
    "track_name": "Awake",
    "artist_name": "Tycho",
    "album": "Awake",
    "isrc": "US2J71309901",
    "original_fields": {"Track name": "Awake", "Artist name": "Tycho", "Album": "Awake"},
    "source_line": 2,
}
RECORDING_ID = "5b44c236-cbb0-4e54-a8b1-c344b76e1b8f"
SECOND_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
TARGET = {
    "id": RECORDING_ID, "title": "Awake", "artist": "Tycho", "length": 283000,
    "isrc": "US2J71309901", "release": {"id": "release-1", "title": "Awake", "date": "2014-03-18"},
}


def recording(recording_id=RECORDING_ID, title="Awake", artist="Tycho", releases=None):
    return {
        "id": recording_id, "title": title,
        "artist-credit": [{"name": artist}], "isrcs": ["US2J71309901"],
        "length": 283000,
        "releases": releases if releases is not None else [{"id": "release-1", "title": "Awake", "date": "2014-03-18"}],
    }


class MatchingTests(unittest.TestCase):
    def setUp(self):
        matching._mb_cache.clear()

    def test_isrc_lookup_identifies_recording_and_release(self):
        calls = []

        def response(path, params=None):
            calls.append(path)
            if path.startswith("isrc/"):
                return {"recordings": [recording()]}
            return recording()

        with patch.object(matching, "musicbrainz_get", side_effect=response):
            target = matching.identify_recording(ROW)
        self.assertEqual(calls, ["isrc/US2J71309901", f"recording/{RECORDING_ID}"])
        self.assertEqual(target["id"], RECORDING_ID)
        self.assertEqual(target["release"]["title"], "Awake")
        self.assertEqual(target["confidence"], 100)

    def test_invalid_isrc_uses_recording_search(self):
        row = {**ROW, "isrc": "invalid"}
        with patch.object(matching, "musicbrainz_get", side_effect=[
            {"recordings": [recording()]}, recording()
        ]) as request:
            matching.identify_recording(row)
        self.assertEqual(request.call_args_list[0].args[0], "recording/")
        self.assertIn('recording:"Awake"', request.call_args_list[0].args[1]["query"])

    def test_isrc_not_found_does_not_select_unverified_recording(self):
        with patch.object(matching, "musicbrainz_get", return_value={"recordings": []}):
            with self.assertRaisesRegex(matching.MatchError, "ISRC.*not found"):
                matching.identify_recording(ROW)

    def test_multiple_musicbrainz_matches_are_ambiguous(self):
        row = {**ROW, "isrc": ""}
        with patch.object(matching, "musicbrainz_get", return_value={"recordings": [
            recording(RECORDING_ID), recording(SECOND_ID)
        ]}):
            with self.assertRaisesRegex(matching.MatchError, "multiple plausible"):
                matching.identify_recording(row)

    def test_wrong_musicbrainz_title_is_rejected(self):
        with patch.object(matching, "musicbrainz_get", return_value={"recordings": [
            recording(title="Different Song")
        ]}):
            with self.assertRaisesRegex(matching.MatchError, "No MusicBrainz recording"):
                matching.identify_recording(ROW)

    def test_release_is_not_guessed_when_editions_are_ambiguous(self):
        detail = recording(releases=[
            {"id": "edition-1", "title": "Awake"},
            {"id": "edition-2", "title": "Awake"},
        ])
        with patch.object(matching, "musicbrainz_get", side_effect=[
            {"recordings": [recording()]}, detail
        ]):
            target = matching.identify_recording(ROW)
        self.assertIsNone(target["release"])

    def test_youtube_later_official_result_beats_first_cover(self):
        entries = [{"id": "aaaaaaaaaaa"}, {"id": "bbbbbbbbbbb"}]
        videos = {
            "https://www.youtube.com/watch?v=aaaaaaaaaaa": {
                "title": "Awake - Tycho (cover)", "duration": 283, "channel": "Other"
            },
            "https://www.youtube.com/watch?v=bbbbbbbbbbb": {
                "title": "Tycho - Awake", "duration": 283, "channel": "Tycho"
            },
        }
        score, url, _, reasons = matching.choose_youtube_video(ROW, TARGET, entries, videos.get)
        self.assertEqual(url, "https://www.youtube.com/watch?v=bbbbbbbbbbb")
        self.assertGreaterEqual(score, matching.MIN_YOUTUBE_SCORE)
        self.assertIn("matching title", reasons)

    def test_low_confidence_or_tied_youtube_results_are_rejected(self):
        entries = [{"id": "aaaaaaaaaaa"}, {"id": "bbbbbbbbbbb"}]
        with self.assertRaisesRegex(matching.MatchError, "confidence threshold"):
            matching.choose_youtube_video(ROW, TARGET, entries, lambda _: {
                "title": "Unrelated upload", "duration": 900, "channel": "Nobody"
            })
        with self.assertRaisesRegex(matching.MatchError, "too close"):
            matching.choose_youtube_video(ROW, TARGET, entries, lambda _: {
                "title": "Tycho - Awake", "duration": 283, "channel": "Tycho"
            })

    def test_title_and_artist_without_duration_or_album_are_insufficient(self):
        score, _ = matching.youtube_score(ROW, TARGET, {
            "title": "Tycho - Awake", "channel": "Tycho"
        })
        self.assertLess(score, matching.MIN_YOUTUBE_SCORE)

    def test_explicit_live_version_is_allowed(self):
        row = {**ROW, "track_name": "Awake (Live)"}
        target = {**TARGET, "title": "Awake (Live)", "length": 285000}
        score, reasons = matching.youtube_score(row, target, {
            "title": "Tycho - Awake (Live)", "duration": 285, "channel": "Tycho"
        })
        self.assertGreaterEqual(score, matching.MIN_YOUTUBE_SCORE)
        self.assertNotIn("unrequested version", " ".join(reasons))

    def test_unrequested_alternate_versions_are_rejected(self):
        for version in ("Live", "Cover", "Remix", "Slowed", "Sped Up",
                        "Nightcore", "Karaoke", "Instrumental"):
            with self.subTest(version=version):
                score, reasons = matching.youtube_score(ROW, TARGET, {
                    "title": f"Tycho - Awake ({version})", "duration": 283,
                    "channel": "Tycho",
                })
                self.assertEqual(score, 0)
                self.assertIn("unrequested version", reasons[0])

    def test_unavailable_musicbrainz_is_reported(self):
        row = {**ROW, "isrc": ""}
        with patch.object(matching, "musicbrainz_get", side_effect=matching.MatchError("MusicBrainz unavailable")):
            with self.assertRaisesRegex(matching.MatchError, "unavailable"):
                matching.identify_recording(row)

    def test_search_youtube_returns_multiple_candidates(self):
        payload = {"entries": [{"id": "aaaaaaaaaaa"}, {"id": "bbbbbbbbbbb"}]}
        with patch.object(main.subprocess, "run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = json.dumps(payload)
            entries = main.search_youtube("Awake", "Tycho", "Awake")
        self.assertEqual(entries, payload["entries"])
        self.assertIn("ytsearch", run.call_args.args[0][-1])

    def test_process_song_does_not_download_ambiguous_match(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(main, "DESTINATION_PATH", Path(folder)), \
                 patch.object(main, "identify_recording", return_value=TARGET), \
                 patch.object(main, "search_youtube", return_value=[{"id": "aaaaaaaaaaa"}]), \
                 patch.object(main, "choose_youtube_video", side_effect=matching.MatchError("ambiguous")), \
                 patch.object(main, "download_song") as download, \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(matching.MatchError, "ambiguous"):
                    main.process_song(1, 1, ROW)
            download.assert_not_called()

    def test_process_song_passes_full_row_and_saves_named_mp3(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder)
            def fake_download(url, staging_folder, stem):
                path = staging_folder / (stem + ".mp3")
                path.write_bytes(b"test audio")
                return path
            with patch.object(main, "DESTINATION_PATH", destination), \
                 patch.object(main, "EMBED_ARTWORK", False), \
                 patch.object(main, "identify_recording", return_value=TARGET) as identify, \
                 patch.object(main, "search_youtube", return_value=[{"id": "bbbbbbbbbbb"}]), \
                 patch.object(main, "choose_youtube_video", return_value=(90, "https://www.youtube.com/watch?v=bbbbbbbbbbb", {"title": "Tycho - Awake"}, ["match"])), \
                 patch.object(main, "download_song", side_effect=fake_download), \
                 patch.object(main, "apply_metadata") as tags, \
                 contextlib.redirect_stdout(io.StringIO()):
                result = main.process_song(1, 1, ROW)
            self.assertEqual(result, "downloaded")
            identify.assert_called_once_with(ROW)
            self.assertTrue((destination / "Tycho - Awake.mp3").exists())
            self.assertEqual(tags.call_args.kwargs["metadata"]["musicbrainz_recording_id"], RECORDING_ID)
            self.assertEqual(tags.call_args.kwargs["metadata"]["album"], "Awake")


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.row = {"artist_name": "Artist A", "track_name": "Same"}

    def test_different_artists_have_distinct_names(self):
        a, _ = output_files.choose_output_path(self.row, RECORDING_ID, self.folder, True)
        b, _ = output_files.choose_output_path({**self.row, "artist_name": "Artist B"}, SECOND_ID, self.folder, True)
        self.assertEqual(a.name, "Artist A - Same.mp3")
        self.assertEqual(b.name, "Artist B - Same.mp3")

    def test_legacy_file_gets_stable_recording_suffix(self):
        (self.folder / "Artist A - Same.mp3").write_bytes(b"legacy")
        path, skip = output_files.choose_output_path(self.row, RECORDING_ID, self.folder, True)
        self.assertEqual(path.name, "Artist A - Same [5b44c236].mp3")
        self.assertFalse(skip)

    def test_same_recording_skips_only_when_setting_enabled(self):
        base = self.folder / "Artist A - Same.mp3"
        base.write_bytes(b"same")
        with patch.object(output_files, "read_recording_id", return_value=RECORDING_ID):
            self.assertEqual(output_files.choose_output_path(self.row, RECORDING_ID, self.folder, True), (base, True))
            self.assertEqual(output_files.choose_output_path(self.row, RECORDING_ID, self.folder, False), (base, False))

    def test_same_artist_different_recordings_do_not_collide(self):
        base = self.folder / "Artist A - Same.mp3"
        base.write_bytes(b"other")
        with patch.object(output_files, "read_recording_id", return_value=SECOND_ID):
            path, skip = output_files.choose_output_path(self.row, RECORDING_ID, self.folder, False)
        self.assertEqual(path.name, "Artist A - Same [5b44c236].mp3")
        self.assertFalse(skip)

    def test_cleaned_or_casefolded_name_collision_is_not_overwritten(self):
        (self.folder / "ARTIST A - SAME.mp3").write_bytes(b"other")
        path, _ = output_files.choose_output_path(self.row, RECORDING_ID, self.folder, True)
        self.assertIn("[5b44c236]", path.name)
        self.assertEqual(output_files.base_stem({"artist_name": "A/B", "track_name": "X:Y"}), "AB - XY")

    def test_publish_new_file_and_refuse_different_existing_recording(self):
        staged = self.folder / "staged.mp3"
        staged.write_bytes(b"new")
        destination = self.folder / "Artist A - Same.mp3"
        output_files.publish_mp3(staged, destination, RECORDING_ID)
        self.assertEqual(destination.read_bytes(), b"new")
        staged.write_bytes(b"replacement")
        with patch.object(output_files, "read_recording_id", return_value=SECOND_ID):
            with self.assertRaises(output_files.OutputCollisionError):
                output_files.publish_mp3(staged, destination, RECORDING_ID)
        self.assertEqual(destination.read_bytes(), b"new")

    def test_publish_replaces_only_verified_same_recording(self):
        destination = self.folder / "Artist A - Same.mp3"
        destination.write_bytes(b"old")
        staged = self.folder / "staged.mp3"
        staged.write_bytes(b"new")
        with patch.object(output_files, "read_recording_id", return_value=RECORDING_ID):
            output_files.publish_mp3(staged, destination, RECORDING_ID)
        self.assertEqual(destination.read_bytes(), b"new")
        self.assertFalse(staged.exists())

    @unittest.skipUnless(importlib.util.find_spec("mutagen"), "Mutagen is not installed")
    def test_read_recording_id_from_real_id3_tag(self):
        from mutagen.id3 import ID3, TXXX

        path = self.folder / "tagged.mp3"
        tags = ID3()
        tags.add(TXXX(encoding=3, desc="MUSICBRAINZ_RECORDING_ID", text=RECORDING_ID))
        tags.save(path)
        self.assertEqual(output_files.read_recording_id(path), RECORDING_ID)


if __name__ == "__main__":
    unittest.main()
