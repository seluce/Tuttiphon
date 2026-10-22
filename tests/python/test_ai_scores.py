"""How easy a song is to listen to (approachable) and how much it asks for close listening (engaging) – two regression
heads of the AI sound analysis: the worker's output with fake Essentia/numpy modules, the state (ml.scores()), merged
features, sound filters (audio.matches(), config validation), the delivered vibes “In the background” and “For
listening closely” (default configuration), summary and search words.
Temp folders only, no network, no Essentia."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import json
import math
import sys
import types
import unittest
from unittest import mock

from app import audio, classify, config, lastfm, ml, ml_worker, rules
from app.rules import BuildContext, Library
from tests.python.factory import base_config, song
from tests.python.test_ml import TMP, FakeLib, MlTest, mtuple, values

BACKGROUND, CLOSE = "klang-hintergrund", "klang-zuhoeren"


def delivered(vid):
    return copy.deepcopy(next(s for s in config.default_config()["stile"] if s["id"] == vid))


# ---------------------------------------------------------------------------- Worker (fake Essentia and numpy)

class FakeOut:
    """What a TensorflowPredict2D model returns: one row per patch – mean(axis=0) like numpy."""

    def __init__(self, rows):
        self.rows = rows

    def mean(self, axis=0):
        return [sum(col) / len(col) for col in zip(*self.rows)]


class FakeEssentia:
    """essentia + essentia.standard with the algorithms Models uses; OUT: graph file name -> rows of the prediction."""

    def __init__(self, out):
        self.out, self.created = out, []
        self.standard = types.SimpleNamespace(TensorflowPredict2D=self.head, KeyExtractor=self.key,
                                              PercivalBpmEstimator=self.tempo,
                                              TensorflowPredictEffnetDiscogs=self.embedding)

    def head(self, graphFilename, input, output):
        self.created.append({"graph": graphFilename.rsplit("/", 1)[-1], "input": input, "output": output})
        name = graphFilename.rsplit("/", 1)[-1]
        return lambda emb: FakeOut(self.out[name])

    @staticmethod
    def key(profileType, sampleRate):
        return lambda audio: ("A", "minor", 0.8)

    @staticmethod
    def tempo(sampleRate):
        return _Tempo()

    @staticmethod
    def embedding(graphFilename, output, patchHopSize):
        return lambda audio: "emb"

    def modules(self):
        ess = types.ModuleType("essentia")
        ess.log = types.SimpleNamespace(warningActive=True, infoActive=True)
        std = types.ModuleType("essentia.standard")
        for k, v in vars(self.standard).items():
            setattr(std, k, v)
        ess.standard = std
        numpy = types.ModuleType("numpy")
        numpy.concatenate = lambda parts: [x for p in parts for x in p]
        return {"essentia": ess, "essentia.standard": std, "numpy": numpy}


class _Tempo:
    def reset(self):
        pass

    def __call__(self, window):
        return 120.0


def write_models(folder):
    """Metadata of every head as the models page describes them (the regression heads: one class, a linear output
    "model/Identity" for the predictions next to the penultimate layer)."""
    folder.mkdir(parents=True, exist_ok=True)
    for name, cls in ml_worker.HEADS.values():
        meta = {"classes": [cls, "other"], "schema": {"inputs": [{"name": "model/Placeholder"}],
                                                       "outputs": [{"name": "model/Softmax", "output_purpose": "predictions"}]}}
        (folder / f"{name}.json").write_text(json.dumps(meta))
    for name, cls in ml_worker.SCORES.values():
        meta = {"classes": [cls], "schema": {"inputs": [{"name": "model/Placeholder"}], "outputs": [
            {"name": "model/dense/BiasAdd", "output_purpose": ""},          # penultimate layer first: must not be taken
            {"name": "model/Identity", "output_purpose": "predictions"}]}}
        (folder / f"{name}.json").write_text(json.dumps(meta))
    for name, *_rest in ml_worker.TOPS.values():
        meta = {"classes": ["Rock---Power Metal", "Pop---Schlager", "piano"],
                "schema": {"inputs": [{"name": "model/Placeholder"}], "outputs": [{"name": "model/Sigmoid"}]}}
        (folder / f"{name}.json").write_text(json.dumps(meta))


class TestWorker(unittest.TestCase):
    def setUp(self):
        self.folder = TMP / "fake-models"
        self.addCleanup(lambda: __import__("shutil").rmtree(TMP, ignore_errors=True))
        write_models(self.folder)
        self.out = {f"{name}.pb": [[0.7, 0.3], [0.5, 0.5]] for name, _cls in ml_worker.HEADS.values()}
        self.out.update({f"{name}.pb": [[0.6, 0.3, 0.2]] for name, *_rest in ml_worker.TOPS.values()})
        self.out["approachability_regression-discogs-effnet-1.pb"] = [[1.3], [1.1]]     # mean 1.2 -> 1.0
        self.out["engagement_regression-discogs-effnet-1.pb"] = [[-0.2], [0.1]]          # mean -0.05 -> 0.0
        self.ess = FakeEssentia(self.out)

    def models(self):
        with mock.patch.dict(sys.modules, self.ess.modules()):
            return ml_worker.Models(str(self.folder))

    def analyse(self, models):
        with mock.patch.object(ml_worker, "decode", return_value=[0.0] * (ml_worker.SR * 10)):
            models.sound_vector = lambda emb: None   # needs numpy – tested in test_ml (Docker image)
            return models.analyse("song.opus", None)

    def test_version_and_files(self):
        self.assertEqual(ml_worker.VERSION, 3)   # songs analyzed before are due again – one pass covers everything
        for name, _cls in ml_worker.SCORES.values():
            for ext in (".json", ".pb"):
                self.assertRegex(ml_worker.FILES[name + ext], r"^[0-9a-f]{64}$")
        self.assertEqual(set(ml_worker.SCORES), {"approachable", "engaging"})
        self.assertFalse(set(ml_worker.SCORES) & set(ml.KEYS))   # not in the tuple of fused values (no 0.5 default)

    def test_download_paths(self):
        self.assertEqual(ml_worker.model_path("approachability_regression-discogs-effnet-1.pb"),
                         "classification-heads/approachability/")
        self.assertEqual(ml_worker.model_path("engagement_regression-discogs-effnet-1.json"),
                         "classification-heads/engagement/")
        self.assertEqual(ml_worker.model_path("approachability_2c-discogs-effnet-1.pb"), "classification-heads/approachability/")
        self.assertEqual(ml_worker.model_path("mood_happy-discogs-effnet-1.pb"), "classification-heads/mood_happy/")
        self.assertEqual(ml_worker.model_path("genre_discogs400-discogs-effnet-1.pb"), "classification-heads/genre_discogs400/")
        self.assertEqual(ml_worker.model_path("mtg_jamendo_instrument-discogs-effnet-1.json"),
                         "classification-heads/mtg_jamendo_instrument/")
        self.assertEqual(ml_worker.model_path("discogs-effnet-bs64-1.pb"), "feature-extractors/discogs-effnet/")

    def test_score_is_clamped_to_0_1(self):
        self.assertEqual(ml_worker.score(1.2), 1.0)
        self.assertEqual(ml_worker.score(-0.05), 0.0)
        self.assertEqual(ml_worker.score(0.61234), 0.612)
        self.assertIsNone(ml_worker.score(math.nan))
        self.assertIsNone(ml_worker.score(math.inf))

    def test_regression_heads_are_loaded_with_their_prediction_output(self):
        m = self.models()
        made = {x["graph"]: x for x in self.ess.created}
        for name, _cls in ml_worker.SCORES.values():
            self.assertEqual((made[name + ".pb"]["input"], made[name + ".pb"]["output"]),
                             ("model/Placeholder", "model/Identity"))
        self.assertEqual(m.heads["approachable"][1:], (["approachability"], 0))
        self.assertEqual(m.heads["engaging"][1:], (["engagement"], 0))

    def test_answer_contains_both_values(self):
        res, vector = self.analyse(self.models())
        self.assertEqual((res["m"]["approachable"], res["m"]["engaging"]), (1.0, 0.0))   # clamped
        self.assertEqual(res["m"]["happy"], 0.6)                                         # classification: unchanged
        self.assertEqual(set(res["m"]), set(ml_worker.HEADS) | set(ml_worker.SCORES))
        self.assertEqual((res["b"], res["bc"], res["k"]), (120.0, 1.0, "A minor"))
        self.assertIsNone(vector)

    def test_values_in_range_and_a_broken_output(self):
        self.out["approachability_regression-discogs-effnet-1.pb"] = [[0.61234]]
        self.out["engagement_regression-discogs-effnet-1.pb"] = [[math.nan]]
        res, _vector = self.analyse(self.models())
        self.assertEqual(res["m"]["approachable"], 0.612)
        self.assertNotIn("engaging", res["m"])   # not a number: left out rather than stored as a middle value


# ---------------------------------------------------------------------------- State and features

class TestScores(MlTest):
    def setUp(self):
        super().setUp()
        self.lib = FakeLib([song("leise", artist="Band A"), song("laut", artist="Band B"), song("alt", artist="Band C"),
                            song("halb", artist="Band D"), song("kaputt", artist="Band E")])
        self.write_audio(["leise", "laut", "alt", "halb", "kaputt"])
        self.write_ml({
            "leise": {"v": ml.VERSION, "path": "x", "m": values(approachable=0.85, engaging=0.3)},
            "laut": {"v": ml.VERSION, "path": "x", "m": values(approachable=0.2, engaging=0.95)},
            "alt": {"v": 2, "path": "x", "m": values()},                                   # before VERSION 3
            "halb": {"v": ml.VERSION, "path": "x", "m": values(approachable=0.7)},
            "kaputt": {"v": ml.VERSION, "path": "x", "m": values(approachable=True, engaging="hoch")},
        })

    def feats(self):
        classify._memo.clear()
        with mock.patch.object(lastfm, "artist", return_value=None):
            return classify.song_features(self.lib)

    def test_state_is_read(self):
        self.assertEqual(ml.scores(), {"leise": {"approachable": 0.85, "engaging": 0.3},
                                       "laut": {"approachable": 0.2, "engaging": 0.95}, "halb": {"approachable": 0.7}})
        self.assertEqual((ml.approachable("leise"), ml.engaging("laut")), (0.85, 0.95))
        self.assertIsNone(ml.approachable("alt"))
        self.assertIsNone(ml.engaging("halb"))
        self.assertEqual(ml.features()["leise"], mtuple())   # the fused values do not change
        self.assertIn("alt", ml.features())                  # older entries stay usable

    def test_song_features_carry_them(self):
        f = self.feats()
        self.assertEqual((f[0]["approachable"], f[0]["engaging"]), (0.85, 0.3))
        self.assertNotIn("approachable", f[2])
        self.assertEqual(f[3]["approachable"], 0.7)
        self.assertNotIn("engaging", f[3])
        self.assertNotIn("approachable", f[4])

    def test_sound_filters(self):
        f = self.feats()
        background = {"approachable": [0.6, 1], "engaging": [0, 0.6]}
        self.assertTrue(audio.matches(f[0], background))
        self.assertFalse(audio.matches(f[1], background))
        self.assertTrue(audio.matches(f[1], {"engaging": [0.75, 1]}))
        self.assertFalse(audio.matches(f[2], {"approachable": [0, 1]}))     # not analyzed again yet: does not fit
        self.assertTrue(audio.matches(f[3], {"approachable": [0.6, 1]}))
        self.assertFalse(audio.matches(f[3], background))                   # one value missing
        self.assertTrue(audio.matches(f[2], {"energy": [0, 1]}))            # other ranges as before

    def test_delivered_vibes(self):
        f = {**self.feats()[0], "arousal": 0.4, "dance": 0.3}
        self.assertTrue(audio.matches(f, delivered(BACKGROUND)["sound"]))
        self.assertFalse(audio.matches({**f, "arousal": 0.7}, delivered(BACKGROUND)["sound"]))   # not wound up
        self.assertFalse(audio.matches(f, delivered(CLOSE)["sound"]))
        loud = {**self.feats()[1], "dance": 0.3}
        self.assertTrue(audio.matches(loud, delivered(CLOSE)["sound"]))
        self.assertFalse(audio.matches({**loud, "dance": 0.9}, delivered(CLOSE)["sound"]))      # dance floor


@env.german   # checks the German output of existing installations
class TestValidationAndSummary(unittest.TestCase):
    def cfg(self, sound):
        cfg = base_config()
        cfg["stile"].append({"id": "x", "name": "X", "sound": sound})
        return cfg

    def test_ranges(self):
        for ok in ({"approachable": [0.6, 1]}, {"engaging": [0, 0.6], "arousal": [0, 0.55]}, {"engaging": [0.75, 1.0]}):
            config.validate_config(self.cfg(ok))
        for bad in ({"approachable": [0.8, 0.2]}, {"engaging": [0, 1.5]}, {"approachable": [-0.1, 0.5]},
                    {"engaging": [True, 1]}, {"engaging": "hoch"}, {"approachable": [0.5]}):
            with self.assertRaises(ValueError, msg=bad) as ctx:
                config.validate_config(self.cfg(bad))
            self.assertIn("Bereich", str(ctx.exception))

    def test_delivered_vibes_are_valid_sound_vibes(self):
        cfg = base_config()
        cfg["stile"] += [delivered(BACKGROUND), delivered(CLOSE)]
        config.validate_config(cfg)
        self.assertEqual({BACKGROUND, CLOSE} - {s["id"] for s in config.default_config()["stile"]}, set())
        self.assertEqual(config.default_config()["version"], config.CONFIG_VERSION)

    def test_summary(self):
        cfg = base_config()
        cfg["stile"] += [delivered(BACKGROUND), delivered(CLOSE)]
        lines = rules.summary(cfg, {"id": "t", "welt": "kinder", "stil": BACKGROUND, "type": "mix"}, BuildContext(None))
        sound = next(x for x in lines if x.startswith("Klang:"))
        self.assertIn("Eingängig 60–100 %", sound)
        self.assertIn("Zum genauen Zuhören 0–60 %", sound)
        lines = rules.summary(cfg, {"id": "t", "welt": "kinder", "stil": CLOSE, "type": "mix"}, BuildContext(None))
        self.assertIn("Zum genauen Zuhören 75–100 %", next(x for x in lines if x.startswith("Klang:")))


# ---------------------------------------------------------------------------- Search

@env.german   # checks the German output of existing installations
class TestSearchWords(unittest.TestCase):
    def setUp(self):
        from app import auth, web
        self.web = web
        self.cfg = base_config()
        self.cfg["stile"] += [{**delivered(BACKGROUND), "name": "Im Hintergrund"}, {**delivered(CLOSE), "name": "Zum Zuhören"}]
        auth.set_current({"user": "Jonas", "role": "user", "own": "jonas", "persons": ["jonas"], "local": False})
        self.addCleanup(auth.set_current, {"user": None, "role": "none", "own": None, "persons": [], "local": False})

    def combos(self, q, cfg=None):
        with mock.patch.object(self.web.rules, "count", return_value=50):
            return self.web._search_combos(q, cfg or self.cfg, Library([song("s1")]))

    def test_words(self):
        for q, vid in (("hintergrundmusik", BACKGROUND), ("background music", BACKGROUND), ("easy listening", BACKGROUND),
                       ("musik für nebenbei", BACKGROUND), ("zum zuhören", CLOSE), ("listening closely", CLOSE),
                       ("hinter", BACKGROUND), ("zuhören", CLOSE), ("im hintergrund", BACKGROUND)):
            self.assertEqual([x["id"] for x in self.web._listen_vibes(q, self.cfg)], [vid], q)
        for q in ("hin", "kinder", "ruhig", "easy", "close"):
            self.assertEqual(self.web._listen_vibes(q, self.cfg), [], q)

    def test_deleted_vibe_is_not_offered(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["stile"] = [s for s in cfg["stile"] if s["id"] != BACKGROUND]
        self.assertEqual(self.web._listen_vibes("hintergrundmusik", cfg), [])
        self.assertEqual(self.combos("kinder hintergrundmusik", cfg), [])

    def test_combos(self):
        out = self.combos("kinder hintergrundmusik")
        self.assertEqual([c["title"] for c in out], ["Kinder · Im Hintergrund"])
        self.assertEqual((out[0]["playlist"]["welt"], out[0]["playlist"]["stil"]), ("kinder", BACKGROUND))
        self.assertNotIn("sound", out[0]["playlist"])   # the vibe brings its filter along
        calm = self.combos("ruhige musik zum zuhören")
        self.assertEqual(calm[0]["title"], "Zum Zuhören · ruhig & sanft")
        self.assertEqual(calm[0]["playlist"]["sound"], {**delivered(CLOSE)["sound"], "moods": ["ruhig"]})
        self.assertEqual(calm[0]["playlist"]["stil"], CLOSE)
        config.validate_config({**self.cfg, "playlists": [{**calm[0]["playlist"], "id": "neu"}]})
        named = self.combos("kinder weihnachten hintergrund")   # a vibe named by name comes first
        self.assertEqual([c["playlist"]["stil"] for c in named], ["weihnachten"])


if __name__ == "__main__":
    unittest.main()
