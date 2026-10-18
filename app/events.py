"""Messages for the server log (in the container: docker logs or UGOS → Container → Log).

Short and with a timestamp: what Tuttiphon is doing right now – start, runs and their results, schedules, logins,
errors. The detailed logs of the runs stay in logs/ (interface: History). Callers translate with _s().
"""
import re
import threading
import time

_lock = threading.Lock()
# control characters (also the Unicode line and paragraph separators and the invisible direction marks) – values
# from outside (a sign-in name, a file name) must not fake log lines or move the terminal's cursor
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f​-‏  ‪-‮⁦-⁩]")


def clean(text, keep_lines=True):
    """Text without control characters; keep_lines=False: also without line breaks and tabs."""
    text = _CONTROL.sub("", str(text))
    return text if keep_lines else re.sub(r"[\t\n]+", " ", text)


def say(text):
    stamp = time.strftime("%d.%m. %H:%M:%S")
    with _lock:
        for line in clean(text).splitlines() or [""]:
            print(f"[{stamp}] {line}", flush=True)
