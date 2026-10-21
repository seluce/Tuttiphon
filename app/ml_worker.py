"""AI sound analysis (Essentia + TensorFlow) as a separate process – started by app/ml.py, never inside the server.

This keeps the server lean: TensorFlow takes a few hundred MB, which are free again when the process ends after the run.
Runs with low priority and on at most THREADS cores (Navidrome should stay smooth).

Protocol (one JSON line per message):
  stdin:  {"id": "...", "path": "/…/song.opus", "segments": [[start, length], …] or null}
  stdout: first {"ready": VERSION} (or {"fatal": "…"}), then per song {"id": "...", "ml": {...}, "sv": "..."} or
          {"id": "...", "error": "..."}
End: close stdin.

Result per song ("ml", strengths 0–1 with 3 decimals):
  m: happy, sad, relaxed, aggressive, party, acoustic, electronic, dance, voice   (probability per feature)
     approachable, engaging   (regression values, clamped to 0–1: how easy to listen to / how much for close listening)
  g: {Discogs style: strength}  the strongest styles (genre---style), at most TOP_GENRES
  t: {theme: strength}          the strongest themes/moods from MTG-Jamendo (christmas, children, calm …)
  i: {instrument: strength}     the strongest instruments from MTG-Jamendo (piano, electricguitar, violin …), at most
                                TOP_INSTRUMENTS, each at least INSTRUMENT_MIN
  k, ks: key ("A minor", "C# major" – Essentia's spelling) and its strength 0–1 (KeyExtractor, profile KEY_PROFILE)
  b, bc: tempo in BPM (PercivalBpmEstimator per window of about TEMPO_WINDOW s, then consensus) and the share of
         windows that agree (0–1)
Next to it "sv": the sound vector – mean of the embedding over all patches, projected to SOUND_DIM dimensions with a
fixed random matrix (sound_projection()), normalized to length 1 and stored as int8 (largest component = ±127),
base64. ml.py keeps it apart from ml.json (state/sound_vectors.json, see app/similar.py).

Texts: this file runs on its own (python3 app/ml_worker.py, also while the Docker image is built, before the rest of
the app is copied) and cannot use app.i18n. Its texts are English: the download output of the image build, and
"error" values in the protocol, which ml.py only counts and never shows.
"""
import base64
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time

VERSION = 3            # 2: instruments, key, tempo and sound vector · 3: approachability and engagement
SR = 16000
TOP_GENRES = 6
TOP_THEMES = 6
TOP_INSTRUMENTS = 5
INSTRUMENT_MIN = 0.1   # weaker instruments are noise (absent ones stay around 0.02–0.08)
KEY_PROFILE = "bgate"  # Essentia's default profile – on pop, rock and electronic the most reliable in our measurements
TEMPO_WINDOW = 30      # seconds per tempo estimate (several windows -> consensus and agreement)
SOUND_DIM = 128        # dimensions of the sound vector (int8: 128 bytes per song)
SOUND_SEED = b"tuttiphon-sound-1"   # seed of the projection – changing it makes all stored vectors incomparable
MAX_SECONDS = 600      # whole song at most 10 min (audio plays)
THREADS = max(1, int(os.environ.get("TUTTIPHON_ML_THREADS") or 2))
EMBEDDING = "discogs-effnet-bs64-1.pb"
PATCH_HOPS = (62, 128)   # distance between patches (mel steps): 62 = model default, 128 = no gaps (larger is not possible)
# head -> (model file, class stored as the value)
HEADS = {
    "happy": ("mood_happy-discogs-effnet-1", "happy"),
    "sad": ("mood_sad-discogs-effnet-1", "sad"),
    "relaxed": ("mood_relaxed-discogs-effnet-1", "relaxed"),
    "aggressive": ("mood_aggressive-discogs-effnet-1", "aggressive"),
    "party": ("mood_party-discogs-effnet-1", "party"),
    "acoustic": ("mood_acoustic-discogs-effnet-1", "acoustic"),
    "electronic": ("mood_electronic-discogs-effnet-1", "electronic"),
    "dance": ("danceability-discogs-effnet-1", "danceable"),
    "voice": ("voice_instrumental-discogs-effnet-1", "voice"),
}
# regression heads -> (model file, class stored as the value): no probability but a score, clamped to 0–1 (score()).
# approachable: mainstream and easy to get into (high) or demanding/experimental (low); engaging: music for close
# listening (high) or for the background (low). Kept apart from HEADS: entries of an older VERSION lack them, and a
# missing value must not count as a middle one (ml.py, audio.matches()).
SCORES = {
    "approachable": ("approachability_regression-discogs-effnet-1", "approachability"),
    "engaging": ("engagement_regression-discogs-effnet-1", "engagement"),
}
GENRES = "genre_discogs400-discogs-effnet-1"
THEMES = "mtg_jamendo_moodtheme-discogs-effnet-1"
INSTRUMENTS = "mtg_jamendo_instrument-discogs-effnet-1"
# head -> (model file, key in the result, how many, minimum strength) – classes stored as {name: strength}
TOPS = {"genres": (GENRES, "g", TOP_GENRES, 0.02), "themes": (THEMES, "t", TOP_THEMES, 0.02),
        "instruments": (INSTRUMENTS, "i", TOP_INSTRUMENTS, INSTRUMENT_MIN)}


def send(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


# Models of the Music Technology Group (Universitat Pompeu Fabra), license CC BY-NC-SA 4.0 – free for private use.
# Downloaded while the Docker image is built (python3 app/ml_worker.py --download /app/models) and checked against
# their checksums. If essentia.upf.edu does not answer, the rest comes from the copy in this project's releases
# (MIRROR, one zip – made by .github/workflows/models.yaml; TUTTIPHON_MODELS_MIRROR overrides it, empty: none).
SOURCE = "https://essentia.upf.edu/models/"
MIRROR = "https://github.com/seluce/tuttiphon/releases/download/ai-models-v1/tuttiphon-ai-models-v1.zip"
WAITS = (0, 10, 30)   # seconds before each attempt – a short outage of the server passes
FILES = {
    "discogs-effnet-bs64-1.pb": "3ed9af50d5367c0b9c795b294b00e7599e4943244f4cbd376869f3bfc87721b1",
    "danceability-discogs-effnet-1.json": "589e61dc05f0d7935be4b5fa7ab4341e5dc7cfecc6898f83503558564790cd75",
    "danceability-discogs-effnet-1.pb": "e1251f02cdc846445e2bc1fb3fe9963e32728c5c000e009188ae47c8963cb4c4",
    "approachability_regression-discogs-effnet-1.json": "39c033e4af6d4f543be420b92e17c8aa3feffe70a88caf2b152d91731320b73f",
    "approachability_regression-discogs-effnet-1.pb": "7ffc208865426fb3aa2842f676b42fc6128282088c9b1d1fd2aba14b17cd121c",
    "engagement_regression-discogs-effnet-1.json": "6dc6f93a5c023f74bcb4ba38297bf9a4fd9e106d2dd1f913b880ed87fcfbd958",
    "engagement_regression-discogs-effnet-1.pb": "43031d40b3a380e1995c8495a108d14ca74f620d924fad9b28df4189c84d20c5",
    "genre_discogs400-discogs-effnet-1.json": "2d367319d9b782ffa10f69abf0e805b3ac4e10899025e5bdbaceda3919b243e0",
    "genre_discogs400-discogs-effnet-1.pb": "3885ba078a35249af94b8e5e4247689afac40deca4401a4bc888daf5a579c01c",
    "mood_acoustic-discogs-effnet-1.json": "45f61055d1d87d5e7f8a413b06b57eca20c3af1a23cf8912e0d916422e5207e1",
    "mood_acoustic-discogs-effnet-1.pb": "96a48d403f52fe9047214437fe396dd2f46699da765c911cd6dfbd456a20f733",
    "mood_aggressive-discogs-effnet-1.json": "81773e95d78db1b93283d73b2d06344d1ff79685b57d9428a40d47fdfcf537b8",
    "mood_aggressive-discogs-effnet-1.pb": "7705284e3a67f23f04d3f2fd75e18a82c0e70db8875b7b6f7061f2432de80858",
    "mood_electronic-discogs-effnet-1.json": "150c21220b7f383868b60e495163498dbabfc4f73d4d1804f525ef352f2897b9",
    "mood_electronic-discogs-effnet-1.pb": "74cb244069c3803d86e6ee7c2817ecac46e37ac2759c457fa2f20d2132a8cb8b",
    "mood_happy-discogs-effnet-1.json": "ed4601bc396b23367d29cf45aa327366cdfdbd3e2baeb7a3f7893237f1ffd9e6",
    "mood_happy-discogs-effnet-1.pb": "de322aee7f4da29ecbd149c86e7964bd6fabe41ca85698a0be40a39d49e88633",
    "mood_party-discogs-effnet-1.json": "a7f15c6e05db7c3e9226646a87162ebb9cc00aea8bdbbc910aedafa7f4a8fdfb",
    "mood_party-discogs-effnet-1.pb": "bbd773a27002978179dd6fc5ffb75b7c41e6a7e412b5c5254d51a025e5b9373e",
    "mood_relaxed-discogs-effnet-1.json": "86c0fe1c2c6d49bf08537bc2d3a602204feaede011ed119c1fc6c36270f60e6a",
    "mood_relaxed-discogs-effnet-1.pb": "2c5aa6666b58fe80429a2dc677a135e9995922889b5a399af87d1c15f0ebb71d",
    "mood_sad-discogs-effnet-1.json": "7f2c00099ad8255af33e43ab77d1ac2c86a1dd9f46d3e5ea2a9a52246f5033d9",
    "mood_sad-discogs-effnet-1.pb": "4865cba49968b6ec295db3e8af6b4a7bb506b1a646628b9f07ee9910d52df82c",
    "mtg_jamendo_instrument-discogs-effnet-1.json": "7d02204c6451b5615e2968ec6364bbae3b915c886e608f05f00d3a38dc5177c4",
    "mtg_jamendo_instrument-discogs-effnet-1.pb": "2e8c3003c722e098da371b6a1f7ad0ce62fac0dcfc09c7c7997d430941196c2a",
    "mtg_jamendo_moodtheme-discogs-effnet-1.json": "d62cd90263e4d613fa7fcce7a831e339450394794af63685f96e065c1a896ab0",
    "mtg_jamendo_moodtheme-discogs-effnet-1.pb": "03f2b047020aee4ab39f8880da7bdae2a36d06a1508d656c6d424ad4d6de07a9",
    "voice_instrumental-discogs-effnet-1.json": "43ac2c3b055dfaed20f6232e0f10636c287f1c5a6e5bd02c5585860031964c8f",
    "voice_instrumental-discogs-effnet-1.pb": "c8033548e17c292874265db62e82a051247768d10375a35a769e7bf695f16acf",
}


def missing_models(folder):
    """Missing model files (empty = complete)."""
    return [n for n in FILES if not os.path.isfile(os.path.join(folder, n))]


def model_path(name):
    """Folder of a model file below SOURCE: the embedding in feature-extractors/, every head in classification-heads/
    under its name without the variant – approachability_regression-… lies in approachability/ (next to _2c and _3c)."""
    if name.startswith("discogs-effnet"):
        return "feature-extractors/discogs-effnet/"
    return f"classification-heads/{re.sub(r'_(regression|[0-9]+c)$', '', name.split('-discogs')[0])}/"


def score(x):
    """Output of a regression head -> 0–1 with 3 decimals (None if not a number)."""
    x = float(x)
    return round(min(1.0, max(0.0, x)), 3) if math.isfinite(x) else None


def _fetch(url, timeout=60):
    import urllib.request
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def _store(folder, name, data):
    """Keep a model file if its checksum matches. -> True if stored"""
    if hashlib.sha256(data).hexdigest() != FILES[name]:
        print(f"  ⚠ {name}: checksum does not match")   # i18n-ignore
        return False
    target = os.path.join(folder, name)
    with open(target + ".part", "wb") as f:
        f.write(data)
    os.replace(target + ".part", target)
    print(f"  ✓ {name} ({len(data) // 1024} KB)")   # i18n-ignore
    return True


def _from_mirror(folder, names):
    """The missing files from the copy (one zip with all models) – only files whose checksum matches."""
    import io
    import zipfile
    url = os.environ.get("TUTTIPHON_MODELS_MIRROR", MIRROR)
    if not url:
        return
    print(f"  … the rest from the copy: {url}")   # i18n-ignore
    for k, wait in enumerate(WAITS):
        time.sleep(wait)
        try:
            with zipfile.ZipFile(io.BytesIO(_fetch(url, timeout=180))) as z:
                inside = set(z.namelist())
                for name in names:
                    if name in inside:
                        _store(folder, name, z.read(name))
            return
        except (OSError, ValueError, zipfile.BadZipFile) as e:
            print(f"  ⚠ copy: {e}" + (" – trying again" if k < len(WAITS) - 1 else ""))   # i18n-ignore


def download(folder):
    """Download and check the models (while building the image): each file up to three times with a pause; if
    essentia.upf.edu does not answer at all, the rest from the copy (MIRROR). -> True if all are there."""
    os.makedirs(folder, exist_ok=True)
    down = False
    for name in FILES:
        if os.path.isfile(os.path.join(folder, name)) or down:
            continue
        for k, wait in enumerate(WAITS):
            time.sleep(wait)
            try:
                if _store(folder, name, _fetch(SOURCE + model_path(name) + name)):
                    break
            except (OSError, ValueError) as e:
                print(f"  ⚠ {name}: {e}" + (" – trying again" if k < len(WAITS) - 1 else ""))   # i18n-ignore
        else:
            down = True   # not even after the pauses: do not wait for every further file
            print("  ⚠ essentia.upf.edu does not answer")   # i18n-ignore
    left = missing_models(folder)
    if left:
        _from_mirror(folder, left)
        left = missing_models(folder)
    print("AI models complete." if not left else f"AI models incomplete – {len(left)} files missing.")   # i18n-ignore
    return not left


def decode(path, start=None, length=None):
    """ffmpeg -> mono samples (16 kHz, float32). Essentia's own loader cannot read Opus."""
    import numpy as np
    cmd = ["ffmpeg", "-nostdin", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.1f}", "-t", f"{length:.1f}"]
    else:
        cmd += ["-t", str(MAX_SECONDS)]
    cmd += ["-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=300)
    if out.returncode != 0:
        raise RuntimeError((out.stderr.decode(errors="replace").strip().splitlines() or ["ffmpeg error"])[-1][:200])   # i18n-ignore
    return np.frombuffer(out.stdout, dtype=np.float32)


def sound_projection(dims, out=SOUND_DIM, seed=SOUND_SEED):
    """Fixed random projection dims -> out with entries ±1 (Achlioptas): the bits come from SHA-256 in counter mode, so
    the matrix is the same on every machine and with every numpy version – stored vectors stay comparable. Random
    projections keep the angles between vectors (Johnson–Lindenstrauss): measured on our songs, the cosines after
    projection and int8 correlate with those of the full 1280 dimensions at about 0.95."""
    import numpy as np
    need = dims * out // 8
    blocks = (hashlib.sha256(seed + k.to_bytes(4, "big")).digest() for k in range(-(-need // 32)))
    bits = np.unpackbits(np.frombuffer(b"".join(blocks)[:need], dtype=np.uint8)).astype(np.float32)
    return (bits * 2 - 1).reshape(dims, out)


def consensus(tempi):
    """Tempo from several windows: the largest group of values at most 4 % apart wins (first one on a tie).
    -> (bpm, share of the windows in the group) or (None, 0)"""
    tempi = [b for b in tempi if b and 40 <= b <= 250]
    if not tempi:
        return None, 0.0
    best = max(([b for b in tempi if abs(b / b0 - 1) <= 0.04] for b0 in tempi), key=len)
    return round(sum(best) / len(best), 1), round(len(best) / len(tempi), 2)


class Models:
    def __init__(self, folder):
        import essentia
        import essentia.standard as es
        essentia.log.warningActive = False
        essentia.log.infoActive = False
        self.np = __import__("numpy")
        self.es, self.folder = es, folder
        self.embedders = {}
        self.heads = {}
        tops = [(key, (name, None)) for key, (name, *_rest) in TOPS.items()]
        for key, (name, cls) in list(HEADS.items()) + list(SCORES.items()) + tops:
            with open(os.path.join(folder, name + ".json"), encoding="utf-8") as f:
                meta = json.load(f)
            schema = meta["schema"]
            out = next((o for o in schema["outputs"] if o.get("output_purpose") == "predictions"), schema["outputs"][0])
            model = es.TensorflowPredict2D(graphFilename=os.path.join(folder, name + ".pb"),
                                           input=schema["inputs"][0]["name"], output=out["name"])
            index = meta["classes"].index(cls) if cls else None
            self.heads[key] = (model, meta["classes"], index)
        self.key = es.KeyExtractor(profileType=KEY_PROFILE, sampleRate=SR)
        self.tempo = es.PercivalBpmEstimator(sampleRate=SR)   # RhythmExtractor2013 would need 44.1 kHz
        self.projection = None
        self.embedder(SR * 60)   # load the usual case right away (an error at startup instead of at the first song)

    def embedder(self, samples):
        """The network always computes 64 patches (~2 s each) at once – the distance between patches is chosen so that a
        song with up to ~130 s of listening time fits into one round (overlapping up to ~64 s, above that without gaps)."""
        frames = samples / 256   # mel spectrum: 256 samples per step
        hop = next(h for h in PATCH_HOPS if (frames - 128) / h + 1 <= 64 or h == PATCH_HOPS[-1])
        if hop not in self.embedders:
            self.embedders[hop] = self.es.TensorflowPredictEffnetDiscogs(
                graphFilename=os.path.join(self.folder, EMBEDDING), output="PartitionedCall:1", patchHopSize=hop)
        return self.embedders[hop]

    def sound_vector(self, emb):
        """Mean embedding -> fixed projection -> length 1 -> int8 (base64) or None."""
        np = self.np
        if self.projection is None:
            self.projection = sound_projection(emb.shape[1])
        v = emb.mean(axis=0) @ self.projection
        top = float(np.abs(v).max()) if len(v) else 0.0
        if not np.isfinite(v).all() or top <= 0:
            return None
        q = np.round(v * (127 / top)).astype(np.int8)   # the length is lost – only the direction counts (cosine)
        return base64.b64encode(q.tobytes()).decode("ascii")

    def tempo_of(self, parts):
        """Percival per window of about TEMPO_WINDOW s (a 60 s section gives two), then consensus."""
        win = TEMPO_WINDOW * SR
        windows = []
        for part in parts:
            n = max(1, len(part) // win)
            step = len(part) // n
            windows += [part[k * step:(k + 1) * step] for k in range(n)]
        tempi = []
        for w in windows:
            if len(w) >= SR * 8:
                self.tempo.reset()   # keeps the result of the first call otherwise
                tempi.append(float(self.tempo(w)))
        return consensus(tempi)

    def analyse(self, path, segments):
        np = self.np
        # join the sections and compute them in one pass (instead of one round per section)
        parts = [decode(path, *(seg or (None, None))) for seg in segments or [None]]
        audio = np.concatenate(parts)
        if len(audio) < SR * 3:
            raise RuntimeError("too short")   # i18n-ignore
        emb = self.embedder(len(audio))(audio)
        res = {"m": {}}
        for key, (model, classes, index) in self.heads.items():
            pred = model(emb).mean(axis=0)
            if key in SCORES:
                value = score(pred[index])
                if value is not None:
                    res["m"][key] = value
                continue
            if index is not None:
                res["m"][key] = round(float(pred[index]), 3)
                continue
            _name, field, n, low = TOPS[key]
            top = sorted(range(len(classes)), key=lambda k: -pred[k])[:n]
            res[field] = {classes[k]: round(float(pred[k]), 3) for k in top if pred[k] >= low}
        try:   # key and tempo are extras – a failure there must not cost the rest of the song
            key, scale, strength = self.key(audio)
            if key and scale and strength > 0:
                res["k"], res["ks"] = f"{key} {scale}", round(float(strength), 2)
        except Exception:   # noqa: BLE001
            pass
        try:
            bpm, agree = self.tempo_of(parts)
            if bpm:
                res["b"], res["bc"] = bpm, agree
        except Exception:   # noqa: BLE001
            pass
        return res, self.sound_vector(emb)


def main():
    if sys.argv[1:2] == ["--download"]:
        sys.exit(0 if download(sys.argv[2]) else 1)
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
    for k, v in (("TF_CPP_MIN_LOG_LEVEL", "3"), ("CUDA_VISIBLE_DEVICES", ""), ("TF_NUM_INTRAOP_THREADS", str(THREADS)),
                 ("TF_NUM_INTEROP_THREADS", "1"), ("OMP_NUM_THREADS", str(THREADS))):
        os.environ.setdefault(k, v)   # before TensorFlow is loaded
    try:
        os.nice(10)
    except OSError:
        pass
    try:   # at most THREADS cores
        cpus = sorted(os.sched_getaffinity(0))
        if len(cpus) > THREADS:
            os.sched_setaffinity(0, set(cpus[-THREADS:]))
    except (AttributeError, OSError):
        pass
    try:
        models = Models(folder)
    except Exception as e:   # noqa: BLE001 – Essentia missing, model missing …
        send({"fatal": f"{type(e).__name__}: {e}"[:300]})
        sys.stdout.flush()
        os._exit(0)
    send({"ready": VERSION})
    for line in sys.stdin:
        try:
            job = json.loads(line)
        except ValueError:
            continue
        try:
            res, vector = models.analyse(job["path"], job.get("segments"))
            send({"id": job["id"], "ml": res, **({"sv": vector} if vector else {})})
        except Exception as e:   # noqa: BLE001 – one broken file must not hold up the rest
            send({"id": job.get("id"), "error": f"{e}"[:200]})
    sys.stdout.flush()
    os._exit(0)   # TensorFlow tends to crash on a regular exit – that would only be noise in the log


if __name__ == "__main__":
    main()
