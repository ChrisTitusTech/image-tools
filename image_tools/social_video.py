"""HandBrake social-video conversion with cancellable desktop progress."""

import argparse
from collections import deque
import json
import errno
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading

TITLE = "Convert to Social Video"


class Cancelled(Exception):
    pass


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


class Progress:
    def __init__(self, terminal=False):
        self.dialog = None
        if not terminal:
            self.dialog = subprocess.Popen(
                ["zenity", "--progress", "--title=" + TITLE, "--width=520",
                 "--percentage=0", "--text=Preparing videos...", "--auto-close",
                 "--no-markup"], stdin=subprocess.PIPE, text=True,
            )

    def check(self):
        if self.dialog and self.dialog.poll() is not None:
            raise Cancelled()

    def update(self, percent, message):
        self.check()
        message = " ".join(message.splitlines())
        if self.dialog:
            try:
                self.dialog.stdin.write(f"{int(percent)}\n# {message}\n")
                self.dialog.stdin.flush()
            except (BrokenPipeError, OSError):
                raise Cancelled() from None
        else:
            print(f"{percent:5.1f}% {message}", flush=True)

    def close(self):
        if self.dialog:
            stop(self.dialog)
            try:
                self.dialog.stdin.close()
            except BrokenPipeError:
                pass


def read_events(stream, events):
    """HandBrake prefixes multiline JSON objects with a record name."""
    buffer = ""
    for line in stream:
        if not buffer:
            if ": {" not in line:
                continue
            buffer = line[line.index("{"):]
        else:
            buffer += line
        try:
            value = json.loads(buffer)
        except json.JSONDecodeError:
            continue
        events.put(value)
        buffer = ""
    events.put(None)


def handbrake(arguments, progress, on_event):
    events = queue.Queue()
    # Separate stderr so diagnostics cannot corrupt the JSON stream.
    with tempfile.TemporaryFile(mode="w+t") as log:
        process = subprocess.Popen(
            ["HandBrakeCLI", "--json", *arguments], stdout=subprocess.PIPE,
            stderr=log, text=True, encoding="utf-8", errors="replace",
        )
        reader = threading.Thread(target=read_events, args=(process.stdout, events), daemon=True)
        reader.start()
        try:
            while True:
                progress.check()
                try:
                    event = events.get(timeout=0.1)
                except queue.Empty:
                    continue
                if event is None:
                    break
                on_event(event)
            result = process.wait()
            if result:
                log.seek(0)
                detail = "".join(deque(log, maxlen=15))
                raise RuntimeError(f"HandBrake failed (exit {result}):\n{detail}")
        finally:
            stop(process)
            reader.join()
            process.stdout.close()


def dimensions(title):
    geometry = title["Geometry"]
    ratio = (geometry["Width"] * geometry["PAR"]["Num"]
             / geometry["PAR"]["Den"] / geometry["Height"])
    if not 1 / 2.39 <= ratio <= 2.39:
        raise ValueError("Aspect ratio is outside X's 1:2.39 to 2.39:1 range. Reframe the video first.")
    if ratio > 1:
        return 1920, 1080
    if ratio < 1:
        return 1080, 1900
    return 1080, 1080


def encode_arguments(source, output, title):
    width, height = dimensions(title)
    return [
        "--input", str(source), "--output", str(output),
        "--preset", "Fast 1080p30", "--format", "av_mp4", "--optimize",
        "--encoder", "x264", "--encoder-preset", "medium",
        "--encoder-profile", "high", "--encoder-level", "4.0",
        "--vb", "6000", "--encopts", "vbv-maxrate=8000:vbv-bufsize=8000:keyint=60:open-gop=0",
        "--rate", "30", "--cfr", "--crop", "0:0:0:0",
        "--non-anamorphic", "--modulus", "2",
        "--maxWidth", str(width), "--maxHeight", str(height),
        "--colorspace", "bt709", "--comb-detect", "--decomb",
        "--audio", "1" if title.get("AudioList") else "none",
        "--aencoder", "av_aac", "--ab", "128", "--mixdown", "stereo", "--arate", "48",
        "--subtitle", "none", "--no-markers",
    ]


def publish(temporary, source, progress=None):
    # Hard-link publication is atomic and never overwrites an existing file,
    # including when two right-click conversions run concurrently.
    counter = 0
    while True:
        suffix = f"-{counter}" if counter else ""
        output = source.with_name(f"{source.stem}-social{suffix}.mp4")
        try:
            os.link(temporary, output)
            return output
        except FileExistsError:
            counter += 1
        except OSError as error:
            if error.errno not in (errno.EPERM, errno.EOPNOTSUPP, errno.ENOSYS, errno.EXDEV):
                raise
            # exFAT/FAT lack hard links. Reserve the name exclusively before copying.
            try:
                destination = output.open("xb")
            except FileExistsError:
                counter += 1
                continue
            try:
                with destination, temporary.open("rb") as incoming:
                    while True:
                        if progress:
                            progress.check()
                        chunk = incoming.read(1024 * 1024)
                        if not chunk:
                            break
                        destination.write(chunk)
            except BaseException:
                output.unlink()
                raise
            return output


def convert(source, progress, index, total):
    if not source.is_file():
        raise ValueError(f"Not a file: {source}")
    label = f"{index + 1}/{total}: {source.name}"
    base = index * 100 / total
    progress.update(base, f"Scanning {label} - estimating time...")
    titles = []
    handbrake(["--scan", "--min-duration", "0", "--input", str(source)],
              progress, lambda event: titles.extend(event.get("TitleList", [])))
    if not titles:
        raise ValueError("No video track found, or this format is unsupported by HandBrake.")
    title = titles[0]
    dimensions(title)

    def update(event):
        working = event.get("Working")
        if working:
            fraction = max(0, min(0.99, working.get("Progress", 0)))
            seconds = working.get("ETASeconds", -1)
            eta = f"{seconds // 60:.0f}m {seconds % 60:.0f}s remaining" if seconds >= 0 else "estimating time..."
            progress.update(base + fraction * 100 / total, f"{label} - {fraction:.0%} - {eta} (this video)")
        elif event.get("State") == "MUXING":
            progress.update(base + 99 / total, f"{label} - finalizing MP4...")

    with tempfile.TemporaryDirectory(prefix=".social-video-", dir=source.parent) as directory:
        temporary = Path(directory) / "output.mp4"
        handbrake(encode_arguments(source, temporary, title), progress, update)
        progress.check()
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise RuntimeError("Output is missing or empty.")
        return publish(temporary, source, progress)


def main():
    parser = argparse.ArgumentParser(description=TITLE + " using HandBrake (X-based encoding defaults).")
    parser.add_argument("--no-gui", action="store_true", help="Print progress to the terminal instead of Zenity")
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    gui = not args.no_gui
    missing = [name for name in (["HandBrakeCLI", "zenity"] if gui else ["HandBrakeCLI"]) if not shutil.which(name)]
    if missing:
        message = "Missing " + ", ".join(missing) + ". Run install.sh to install dependencies."
        print(message, file=sys.stderr)
        if gui and shutil.which("zenity"):
            subprocess.run(["zenity", "--error", "--no-markup", "--text=" + message], check=False)
        return 1
    progress = Progress(args.no_gui)
    errors = []
    outputs = []
    try:
        for index, source in enumerate(args.files):
            try:
                output = convert(source.absolute(), progress, index, len(args.files))
                outputs.append(output)
                print(f"Saved: {output}", flush=True)
            except (OSError, ValueError, RuntimeError, KeyError) as error:
                errors.append(f"{source.name}: {error}")
        progress.update(100, "Finished")
    except (Cancelled, KeyboardInterrupt):
        print("Conversion cancelled. Completed files were kept; partial output was removed.", file=sys.stderr)
        return 130
    finally:
        progress.close()
    message = f"Converted {len(outputs)} of {len(args.files)} video(s). Files saved beside the originals."
    if errors:
        message += "\n\n" + "\n\n".join(errors)
        print(message, file=sys.stderr)
    if gui:
        subprocess.run(["zenity", "--error" if errors else "--info", "--no-markup",
                        "--title=" + TITLE, "--width=520", "--text=" + message], check=False)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
