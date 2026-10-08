import contextlib
import io
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import main


PROJECT = Path(main.__file__).resolve().parent


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.folder = Path(self.temporary_directory.name)

    def make_file(self, name, contents):
        path = self.folder / name
        path.write_text(contents, encoding="utf-8")
        return path

    def read_quietly(self, path):
        with contextlib.redirect_stdout(io.StringIO()):
            return main.load_songs(path)

    def test_supplied_two_column_csv_and_trimmed_artist(self):
        songs = self.read_quietly(PROJECT / "songs.csv")
        self.assertEqual(len(songs), 2)
        self.assertEqual(songs[0]["track_name"], "Hailing Taquitos")
        self.assertEqual(songs[0]["artist_name"], "Parry Gripp")
        self.assertEqual(songs[1]["artist_name"], "by EXTRA SPACES.")
        self.assertTrue(songs[1]["original_fields"]["Artist name"].startswith(" "))
        self.assertEqual(songs[1]["source_line"], 3)

    def test_supplied_export_retains_all_fields_and_bom(self):
        songs = self.read_quietly(PROJECT / "My Spotify Library.csv")
        self.assertEqual(len(songs), 120)
        self.assertEqual(songs[0]["track_name"], "Awake")
        self.assertEqual(songs[0]["album"], "Awake")
        self.assertEqual(songs[0]["playlist_name"], "ADHD Focus Music (No Lyrics)")
        self.assertEqual(songs[0]["isrc"], "US2J71309901")
        self.assertEqual(len(songs[0]["original_fields"]), 7)
        self.assertIn("Spotify - id", songs[0]["original_fields"])
        self.assertNotIn("\ufeffTrack name", songs[0]["original_fields"])

    def test_quoted_comma_unicode_unknown_field_and_multiline(self):
        path = self.make_file(
            "unicode.csv",
            'Track name,Artist name,Album,Custom\n"Café, reprise","Björk","One, Two",kept\n'
            '"Line one\nline two",Artist,Album,also kept\n',
        )
        songs = self.read_quietly(path)
        self.assertEqual(songs[0]["track_name"], "Café, reprise")
        self.assertEqual(songs[0]["artist_name"], "Björk")
        self.assertEqual(songs[0]["album"], "One, Two")
        self.assertEqual(songs[0]["original_fields"]["Custom"], "kept")
        self.assertEqual(songs[1]["track_name"], "Line one\nline two")
        self.assertEqual(songs[1]["source_line"], 4)

    def test_header_whitespace_is_normalized_but_original_kept(self):
        path = self.make_file("spaces.csv", " Track name , Artist name \nSong,Artist\n")
        song = self.read_quietly(path)[0]
        self.assertEqual(song["track_name"], "Song")
        self.assertEqual(song["original_fields"][" Track name "], "Song")

    def test_missing_header_reports_name(self):
        path = self.make_file("missing.csv", "Track name,Album\nSong,Album\n")
        with self.assertRaisesRegex(ValueError, "Artist name"):
            self.read_quietly(path)

    def test_duplicate_header_rejected_before_dictreader_loses_data(self):
        path = self.make_file("duplicate.csv", "Track name,Artist name, Artist name \nSong,A,B\n")
        with self.assertRaisesRegex(ValueError, "Duplicate CSV header.*Artist name"):
            self.read_quietly(path)

    def test_empty_header_rejected(self):
        path = self.make_file("empty_header.csv", "Track name,Artist name,\nSong,Artist,x\n")
        with self.assertRaisesRegex(ValueError, "empty column header"):
            self.read_quietly(path)

    def test_headerless_first_song_is_kept_after_confirmation(self):
        path = self.make_file("headerless.csv", "First Song,First Artist\nSecond Song,Second Artist\n")
        with patch("builtins.input", return_value="y"):
            songs = self.read_quietly(path)
        self.assertEqual([song["track_name"] for song in songs], ["First Song", "Second Song"])
        self.assertEqual(songs[0]["source_line"], 1)
        self.assertEqual(path.read_text(encoding="utf-8").splitlines()[0], "First Song,First Artist")

    def test_headerless_decline_stops_without_losing_first_row(self):
        path = self.make_file("headerless.csv", "First Song,First Artist\n")
        with patch("builtins.input", return_value="n"):
            with self.assertRaisesRegex(ValueError, "Missing required CSV header"):
                self.read_quietly(path)
        self.assertEqual(path.read_text(encoding="utf-8"), "First Song,First Artist\n")

    def test_blank_rows_are_ignored_but_missing_required_values_are_reported(self):
        path = self.make_file(
            "invalid.csv", "Track name,Artist name\n\n,\nSong,\n,Artist\nGood,Artist\n"
        )
        with self.assertRaises(ValueError) as error:
            self.read_quietly(path)
        self.assertIn("Line 4: empty required field(s): Artist name", str(error.exception))
        self.assertIn("Line 5: empty required field(s): Track name", str(error.exception))

    def test_blank_rows_before_header_are_ignored_with_correct_line_numbers(self):
        path = self.make_file(
            "leading_blank.csv", "\n,\nTrack name,Artist name\nSong,Artist\n"
        )
        songs = self.read_quietly(path)
        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0]["source_line"], 4)

    def test_too_many_and_too_few_cells_report_lines(self):
        path = self.make_file(
            "width.csv", "Track name,Artist name,Album\nToo many,Artist,Album,extra\nToo few,Artist\n"
        )
        with self.assertRaises(ValueError) as error:
            self.read_quietly(path)
        self.assertIn("Line 2: too many columns", str(error.exception))
        self.assertIn("Line 3: too few columns", str(error.exception))

    def test_invalid_utf8_and_bad_quotes_are_reported(self):
        bad_encoding = self.folder / "latin1.csv"
        bad_encoding.write_bytes(b"Track name,Artist name\nCaf\xe9,Artist\n")
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            self.read_quietly(bad_encoding)
        bad_quotes = self.make_file("quotes.csv", 'Track name,Artist name\n"Never closes,Artist\n')
        with self.assertRaisesRegex(ValueError, "Malformed CSV.*line 2.*Check quoting"):
            self.read_quietly(bad_quotes)

    def test_empty_file_and_no_songs_stop(self):
        with self.assertRaisesRegex(ValueError, "empty or has no header"):
            self.read_quietly(self.make_file("empty.csv", ""))
        with self.assertRaisesRegex(ValueError, "No songs"):
            self.read_quietly(self.make_file("no_songs.csv", "Track name,Artist name\n\n"))

    def test_txt_requires_conversion_for_public_loader(self):
        path = self.make_file("songs.txt", "Track name,Artist name\nSong,Artist\n")
        with self.assertRaisesRegex(ValueError, "confirmed conversion"):
            main.load_songs(path)

    def test_txt_conversion_accepts_and_keeps_data(self):
        path = self.make_file("songs.txt", "Track name,Artist name\nSong,Artist\n")
        output = io.StringIO()
        with patch("builtins.input", return_value="yes"), contextlib.redirect_stdout(output):
            converted, songs = main.prepare_input_file(path)
        self.assertEqual(converted, self.folder / "songs.csv")
        self.assertFalse(path.exists())
        self.assertEqual(converted.read_text(encoding="utf-8"), "Track name,Artist name\nSong,Artist\n")
        self.assertEqual(songs[0]["track_name"], "Song")
        self.assertIn("Preview", output.getvalue())

    def test_txt_headerless_asks_once_and_keeps_first_song(self):
        path = self.make_file("songs.txt", "Song,Artist\nOther,Other Artist\n")
        with patch("builtins.input", side_effect=["y", "y"]) as response, contextlib.redirect_stdout(io.StringIO()):
            converted, songs = main.prepare_input_file(path)
        self.assertEqual(response.call_count, 2)
        self.assertEqual(converted.suffix, ".csv")
        self.assertEqual(songs[0]["track_name"], "Song")

    def test_txt_decline_leaves_file_untouched(self):
        path = self.make_file("songs.txt", "Track name,Artist name\nSong,Artist\n")
        with patch("builtins.input", return_value="n"), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "cancelled"):
                main.prepare_input_file(path)
        self.assertTrue(path.exists())
        self.assertFalse((self.folder / "songs.csv").exists())

    def test_txt_invalid_data_does_not_rename(self):
        path = self.make_file("songs.txt", "Track name,Artist name\nSong\n")
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "too few columns"):
                main.prepare_input_file(path)
        self.assertTrue(path.exists())
        self.assertFalse((self.folder / "songs.csv").exists())

    def test_txt_destination_collision_does_not_overwrite(self):
        path = self.make_file("songs.txt", "Track name,Artist name\nSong,Artist\n")
        target = self.make_file("songs.csv", "existing data")
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                main.prepare_input_file(path)
        self.assertTrue(path.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), "existing data")

    def test_txt_destination_created_after_check_is_not_deleted(self):
        path = self.make_file("songs.txt", "Track name,Artist name\nSong,Artist\n")
        target = self.folder / "songs.csv"
        original_open = Path.open

        def create_competing_file(file_path, mode="r", *args, **kwargs):
            if file_path == target and mode == "xb":
                with original_open(target, "w", encoding="utf-8") as file:
                    file.write("created by another process")
                raise FileExistsError(target)
            return original_open(file_path, mode, *args, **kwargs)

        with patch("builtins.input", return_value="y"), \
             patch.object(Path, "open", create_competing_file), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(FileExistsError):
                main.prepare_input_file(path)
        self.assertTrue(path.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), "created by another process")

    def test_txt_failed_copy_keeps_source_and_removes_partial_target(self):
        path = self.make_file("songs.txt", "Track name,Artist name\nSong,Artist\n")
        target = self.folder / "songs.csv"
        with patch("builtins.input", return_value="y"), \
             patch.object(main.shutil, "copyfileobj", side_effect=OSError("copy failed")), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(OSError, "copy failed"):
                main.prepare_input_file(path)
        self.assertTrue(path.exists())
        self.assertFalse(target.exists())

    def test_file_picker_rejects_zero_negative_and_out_of_range(self):
        self.make_file("a.csv", "Track name,Artist name\nA,B\n")
        self.make_file("b.csv", "Track name,Artist name\nC,D\n")
        with patch.object(main, "SCRIPT_FOLDER", self.folder), patch.object(main, "INPUT_FILE", None):
            for choice in ("0", "-1", "3", "abc"):
                with self.subTest(choice=choice):
                    with patch("builtins.input", return_value=choice), contextlib.redirect_stdout(io.StringIO()):
                        with self.assertRaisesRegex(ValueError, "Invalid input file selection"):
                            main.find_input_file()

    def test_picker_excludes_error_log_and_labels_txt(self):
        path = self.make_file("songs.txt", "Track name,Artist name\nA,B\n")
        self.make_file("download_errors.txt", "an error")
        with patch.object(main, "SCRIPT_FOLDER", self.folder), patch.object(main, "INPUT_FILE", None):
            self.assertEqual(main.find_input_file(), path)
        self.make_file("another.csv", "Track name,Artist name\nC,D\n")
        output = io.StringIO()
        with patch.object(main, "SCRIPT_FOLDER", self.folder), patch.object(main, "INPUT_FILE", None):
            with patch("builtins.input", return_value="2"), contextlib.redirect_stdout(output):
                self.assertEqual(main.find_input_file(), path)
        self.assertIn("validate and convert", output.getvalue())
        self.assertNotIn("download_errors.txt", output.getvalue())

    def test_configured_missing_file_reports_path_and_error_log_is_rejected(self):
        with patch.object(main, "SCRIPT_FOLDER", self.folder), patch.object(main, "INPUT_FILE", "missing.csv"):
            with self.assertRaisesRegex(FileNotFoundError, "missing.csv"):
                main.find_input_file()
        self.make_file("download_errors.txt", "error")
        with patch.object(main, "SCRIPT_FOLDER", self.folder), patch.object(main, "INPUT_FILE", "download_errors.txt"):
            with self.assertRaisesRegex(ValueError, "not a song list"):
                main.find_input_file()

    def test_main_displays_songs_and_can_cancel_without_network(self):
        self.make_file("songs.csv", "Track name,Artist name\nSong, Artist \n")
        output = io.StringIO()
        with patch.object(main, "SCRIPT_FOLDER", self.folder), \
             patch.object(main, "DESTINATION_PATH", self.folder / "output"), \
             patch.object(main, "INPUT_FILE", "songs.csv"), \
             patch.object(main, "ERROR_LOG", self.folder / "download_errors.txt"), \
             patch.object(main, "check_yt_dlp"), patch.object(main, "check_ffmpeg"), \
             patch.dict("sys.modules", {"mutagen": types.ModuleType("mutagen")}), \
             patch("builtins.input", return_value="n"), \
             patch.object(main, "process_song") as download, \
             contextlib.redirect_stdout(output):
            main.main()
        self.assertIn("1. Song - Artist", output.getvalue())
        self.assertNotIn("original_fields", output.getvalue())
        download.assert_not_called()

    def test_invalid_input_prevents_download(self):
        self.make_file("songs.csv", "Track name,Artist name\nSong\n")
        with patch.object(main, "SCRIPT_FOLDER", self.folder), \
             patch.object(main, "DESTINATION_PATH", self.folder / "output"), \
             patch.object(main, "INPUT_FILE", "songs.csv"), \
             patch.object(main, "ERROR_LOG", self.folder / "download_errors.txt"), \
             patch.object(main, "check_yt_dlp"), patch.object(main, "check_ffmpeg"), \
             patch.dict("sys.modules", {"mutagen": types.ModuleType("mutagen")}), \
             patch("builtins.input", return_value=""), \
             patch.object(main, "process_song") as download, \
             contextlib.redirect_stdout(io.StringIO()):
            main.main()
        download.assert_not_called()

    def test_main_uses_normalized_songs_and_continues_after_failure(self):
        self.make_file(
            "songs.csv", "Track name,Artist name\nFirst, Artist A \nSecond,Artist B\n"
        )
        error_log = self.folder / "download_errors.txt"
        output = io.StringIO()
        with patch.object(main, "SCRIPT_FOLDER", self.folder), \
             patch.object(main, "DESTINATION_PATH", self.folder / "output"), \
             patch.object(main, "INPUT_FILE", "songs.csv"), \
             patch.object(main, "ERROR_LOG", error_log), \
             patch.object(main, "check_yt_dlp"), patch.object(main, "check_ffmpeg"), \
             patch.dict("sys.modules", {"mutagen": types.ModuleType("mutagen")}), \
             patch("builtins.input", side_effect=["y", ""]), \
             patch.object(main, "process_song", side_effect=[RuntimeError("test failure"), True]) as download, \
             contextlib.redirect_stdout(output):
            main.main()
        self.assertEqual(download.call_count, 2)
        self.assertEqual(download.call_args_list[0].args, (1, 2, "First", "Artist A"))
        self.assertEqual(download.call_args_list[1].args, (2, 2, "Second", "Artist B"))
        self.assertIn("First - Artist A", error_log.read_text(encoding="utf-8"))
        self.assertIn("Successful: 1", output.getvalue())
        self.assertIn("Failed:     1", output.getvalue())


if __name__ == "__main__":
    unittest.main()
