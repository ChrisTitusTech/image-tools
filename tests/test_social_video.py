import io
import errno
import json
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from image_tools import social_video as video


class Progress:
    def __init__(self):
        self.messages = []

    def check(self):
        pass

    def update(self, percent, message):
        self.messages.append((percent, message))


class SocialVideoTests(unittest.TestCase):
    def test_json_records(self):
        events = queue.Queue()
        video.read_events(io.StringIO('Version: {\n"Name": "HandBrake"\n}\nProgress: {\n"Working": {"Progress": 0.5, "ETASeconds": 32}\n}\n'), events)
        self.assertEqual(events.get()["Name"], "HandBrake")
        self.assertEqual(events.get()["Working"]["ETASeconds"], 32)
        self.assertIsNone(events.get())

    def test_duration_and_size_do_not_limit_conversion(self):
        for duration in (0.25, 141, 3600):
            with self.subTest(duration=duration), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "video.mp4"
                source.touch()
                calls = []
                def handbrake(arguments, progress, callback):
                    calls.append(arguments)
                    if "--scan" in arguments:
                        callback({"TitleList": [{"Duration": {"Ticks": duration * 90000},
                                  "Geometry": {"Width": 640, "Height": 360,
                                               "PAR": {"Num": 1, "Den": 1}}}]})
                    else:
                        output = Path(arguments[arguments.index("--output") + 1])
                        with output.open("wb") as stream:
                            stream.truncate(513_000_000)  # Sparse file above the old cap.
                with patch.object(video, "handbrake", side_effect=handbrake):
                    output = video.convert(source, Progress(), 0, 1)
                self.assertEqual(output.stat().st_size, 513_000_000)
                self.assertEqual(len(calls), 2)
                self.assertNotIn("--stop-at", calls[1])
                self.assertTrue(source.exists())

    def test_publish_preserves_existing(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "-clip & quote's.mp4"
            source.write_bytes(b"original")
            temporary = Path(directory) / "temp.mp4"
            temporary.write_bytes(b"converted")
            first = video.publish(temporary, source)
            with patch.object(video.os, "link", side_effect=OSError(errno.EOPNOTSUPP, "No hard links")):
                second = video.publish(temporary, source)
            self.assertNotEqual(first, second)
            self.assertEqual(source.read_bytes(), b"original")
            self.assertEqual(first.read_bytes(), b"converted")

    def test_cancel_during_fallback_copy_removes_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mp4"
            source.write_bytes(b"original")
            temporary = Path(directory) / "temporary.mp4"
            with temporary.open("wb") as stream:
                stream.truncate(3 * 1024 * 1024)
            progress = Progress()
            with patch.object(video.os, "link", side_effect=OSError(errno.EOPNOTSUPP, "No hard links")), patch.object(
                    progress, "check", side_effect=[None, video.Cancelled()]):
                with self.assertRaises(video.Cancelled):
                    video.publish(temporary, source, progress)
            self.assertFalse((Path(directory) / "source-social.mp4").exists())
            self.assertEqual(source.read_bytes(), b"original")

    def test_installer_registration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            installer = Path(__file__).resolve().parents[1] / "install.sh"
            script = installer.read_text().rsplit('main "$@"', 1)[0]
            script += '\nTHUNAR_CONFIG_DIR="$1/Thunar"\nTHUNAR_UCA_FILE="$THUNAR_CONFIG_DIR/uca.xml"\n'
            script += 'update_thunar_action custom "Existing" "Keep" icon "/tmp/custom"\n'
            command = 'update_thunar_action "$ACTION_SOCIAL_ID" "$ACTION_SOCIAL_NAME" "$ACTION_SOCIAL_DESCRIPTION" "$ACTION_SOCIAL_ICON" "/tmp/bin with spaces/convert-to-social-video" "<video-files/>"\n'
            test_script = Path(directory) / "installer-test.sh"
            test_script.write_text(script + command + command)
            subprocess.run(["bash", str(test_script), directory], check=True)
            import xml.etree.ElementTree as ET
            root = ET.parse(Path(directory) / "Thunar/uca.xml").getroot()
            self.assertEqual(len(root.findall("action")), 2)
            action = root.findall("action")[1]
            self.assertEqual(action.findtext("name"), video.TITLE)
            self.assertEqual(action.findtext("command"), '"/tmp/bin with spaces/convert-to-social-video" %F')
            self.assertIsNotNone(action.find("video-files"))
            self.assertIsNone(action.find("image-files"))

    @unittest.skipUnless(all(shutil.which(tool) for tool in ("HandBrakeCLI", "ffmpeg", "ffprobe")), "Requires video tools")
    def test_real_encodes_and_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, size, expected in [("landscape", "1920x1080", (1920, 1080)),
                                         ("portrait", "1080x1920", (1068, 1900)),
                                         ("square", "1200x1200", (1080, 1080))]:
                with self.subTest(name=name):
                    source = root / f"{name} & space.mkv"
                    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                                    f"color=size={size}:rate=24", "-t", "2", "-c:v", "libx264",
                                    str(source)], check=True)
                    progress = Progress()
                    output = video.convert(source, progress, 0, 1)
                    data = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)]))
                    stream = data["streams"][0]
                    self.assertEqual((stream["width"], stream["height"]), expected)
                    self.assertEqual(stream["codec_name"], "h264")
                    self.assertEqual(stream["pix_fmt"], "yuv420p")
                    self.assertEqual(stream["r_frame_rate"], "30/1")
                    self.assertTrue(any("remaining" in message or "%" in message for _, message in progress.messages))
                    content = output.read_bytes()
                    self.assertLess(content.index(b"moov"), content.index(b"mdat"))
            rotated = root / "rotated.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-display_rotation", "90", "-i", str(root / "landscape & space.mkv"),
                            "-c", "copy", str(rotated)], check=True)
            rotated_output = video.convert(rotated, Progress(), 0, 1)
            rotated_stream = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(rotated_output)]))["streams"][0]
            self.assertEqual((rotated_stream["width"], rotated_stream["height"]), (1068, 1900))
            class CancelProgress(Progress):
                def update(self, percent, message):
                    if "%" in message:
                        raise video.Cancelled()
            with self.assertRaises(video.Cancelled):
                video.convert(source, CancelProgress(), 0, 1)
            self.assertFalse(list(root.glob(".social-video-*")))
            self.assertFalse(list(root.glob("*-social-1.mp4")))
            broken = root / "broken.mp4"
            broken.write_bytes(b"not a video")
            with self.assertRaises((ValueError, RuntimeError)):
                video.convert(broken, Progress(), 0, 1)


if __name__ == "__main__":
    unittest.main()
