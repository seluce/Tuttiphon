"""Ready-made playlist suggestions and the "to review" list for ongoing care."""
import datetime as dt
import json
import math

from . import rules, scenes
from .i18n import _, _n, _s
from .rules import ALL, BuildContext, join_and

MIN_SONGS = 25


MORNING_SHARE = 0.2   # "Good morning": a world counts with this share of the morning plays


def key_of(p):
    w = p.get("welt", ALL)
    w = "+".join(sorted(w)) if isinstance(w, list) else w
    radio = "|radio:" + "+".join(sorted((p.get("radio") or {}).get("seed", []))) if p.get("radio") else ""
    special = ("|fav" if p.get("fav") else "") + (f"|review:{p['review'].get('period', 'month')}" if p.get("review") else "") \
        + ("|together" if p.get("together") else "") + ("|sound" if p.get("sound") else "") \
        + (f"|daytime:{p['daytime']}" if p.get("daytime") else "")
    return f"{p.get('person')}|{w}|{p.get('stil', ALL)}|{'hits' if p.get('hits') else ''}" + ("|mix" if p.get("type") == "mix" else "") + radio + special


def _content_key(p):
    """Like key_of, but without the person: the same music, no matter for whom."""
    return key_of({**p, "person": None})


def dislikes_of(person):
    return set((person.get("dislikes") or {}).get("artists", []))


def _existing_keys(cfg):
    return {key_of(p) for p in cfg["playlists"] if p.get("status") != "papierkorb" and p.get("rules") is None}   # i18n-ignore: stored value


def _shared_content(cfg, handmade_list):
    """Content that already exists as a public playlist (visible to everyone) – including handmade ones."""
    from .playlists import guess_mapping
    public = {p["id"] for p in cfg.get("personen", []) if p.get("public")}
    keys = {_content_key(p) for p in cfg["playlists"]
            if p.get("status") != "papierkorb" and p.get("rules") is None and p.get("person") in public}   # i18n-ignore: stored value
    for h in handmade_list:
        m = guess_mapping(cfg, h.get("nsp", {}))
        if m:
            keys.add(_content_key(m))
    for p in cfg["playlists"]:   # taken-over playlists with their own rules
        if p.get("rules") is not None and p.get("takeover"):
            m = guess_mapping(cfg, {"all": p["rules"], "name": p.get("originalName")})
            if m:
                keys.add(_content_key(m))
    return keys


def _by_artist(lib, ids):
    from collections import Counter
    return Counter(lib.songs[i].get("displayAlbumArtist") or lib.songs[i].get("artist") for i in ids)


def coherence(cfg, lib, ctx, p):
    """Share of the songs whose artists mostly (≥ 50 %) belong to this vibe."""
    combo = _by_artist(lib, lib.match(rules.build_nsp(cfg, p, ctx)))
    base = _by_artist(lib, lib.match(rules.build_nsp(cfg, {**p, "stil": ALL}, ctx)))
    n = sum(combo.values())
    if not n:
        return 0
    return sum(c for a, c in combo.items() if base.get(a) and c / base[a] >= 0.5) / n


def possessive(name):
    """German genitive of a name ("Annas", "Jonas’") – passed to the texts as {owner}; English uses {name}’s."""
    return f"{name}’" if name[-1:].lower() in "sßxz" else f"{name}s"   # i18n-ignore: German grammar


def rename_all_sorts(cfg, lang):
    """Configuration v8: the personal smart playlist across all favorite worlds was stored as “{name}’s mix”
    (German “Niklas’ Mix”), although it is no mix. It becomes “{name}’s All Sorts” (“Niklas’ Querbeet”) in the server
    language – only while it still has the name the suggestion gave it; a name someone typed stays.
    The file stays the same, so it remains the same playlist in Navidrome. -> renamed playlists"""
    from .i18n import tr
    persons = {p.get("id"): p for p in cfg.get("personen", [])}
    default = (cfg.get("settings") or {}).get("defaultPerson")
    renamed = []
    for p in cfg.get("playlists", []):
        who = (persons.get(p.get("person") or default) or {}).get("name") or ""
        if (not who or p.get("rules") is not None or p.get("type") == "mix" or p.get("stil", ALL) != ALL
                or any(p.get(k) for k in ("hits", "radio", "fav", "review", "together"))):
            continue
        if p.get("name") in (f"{who}’s mix", f"{possessive(who)} Mix"):   # i18n-ignore: names as stored before (data)
            p["name"] = tr("{name}’s All Sorts", lang, name=who, owner=possessive(who))
            renamed.append(p)
    return renamed


def _reason(top, n):
    names = [a for a, _ in top[:3] if a]
    more = " …" if len(top) > 3 else ""
    if names:
        return _n(n, "{n} song by {artists}", "{n} songs by {artists}", artists=", ".join(names) + more)
    return _n(n, "{n} song", "{n} songs")


def suggestions(cfg, lib, today=None, per_person=10, handmade_list=(), only_person=None):
    """only_person: only ideas for this person – including those that already exist visible to everyone
    (marked "shared"), e.g. for the "New person" assistant."""
    today = today or dt.date.today()
    ctx = BuildContext(lib, today)
    existing = _existing_keys(cfg) | set(cfg.get("dismissed", []))
    shared = _shared_content(cfg, handmade_list)
    welten = {w["id"]: w for w in cfg["welten"]}
    stile = cfg["stile"]
    has_plays = sum(1 for s in lib.songs if s.get("played")) >= 100
    has_loved = sum(1 for s in lib.songs if s.get("starred")) >= 15
    default = cfg["settings"].get("defaultPerson")
    persons = sorted(cfg.get("personen", []), key=lambda p: p["id"] != default)   # shared person first
    mix_cache = {}
    out = []
    # taste per account from what is played in Navidrome/Symfonium (taste.py) – adds to the preferences set by hand
    from . import taste
    profiles = {}
    for person in persons:
        if person.get("user") and (not only_person or person["id"] == only_person):
            try:
                prof = taste.profile(cfg, lib, person["user"], today)
            except Exception:   # noqa: BLE001 – suggestions must never fail because of one profile
                prof = None
            if prof and prof.get("enough"):
                profiles[person["id"]] = prof

    def add(p, score, title=None, why=None, group=None, because=None):
        if rules.sound_of(cfg, p) and p.get("type") != "mix":   # sound vibes only exist as mixes
            p = {**p, "type": "mix", "mix": p.get("mix") or {"size": 50, "perArtist": 3, "every": "week"}}
        k = key_of(p)
        if k in existing:
            return
        person = next((x for x in persons if x["id"] == p.get("person")), {})
        has_dislikes = any(person.get("dislikes", {}).values())
        is_shared = _content_key(p) in shared and not (has_dislikes and not person.get("public"))
        if is_shared and not only_person:
            return   # already exists visible to everyone (or as a handmade playlist)
        nsp = rules.build_nsp(cfg, p, ctx)
        ids = rules.apply_sound(cfg, lib, p, lib.match(nsp))
        n = len(ids)
        if n < MIN_SONGS:
            return
        top = lib.top_artists(ids, 6)
        distinct = len(top)
        if distinct < 2 or (top and top[0][1] / n > 0.8 and distinct < 4):
            return   # basically just one artist
        existing.add(k)
        if person.get("public"):
            shared.add(_content_key(p))
        # sound taste (soundtaste.py): what sounds more like what the person plays than the library on average moves up
        heard = (profiles.get(p.get("person")) or {}).get("soundTaste")
        if heard:
            bonus = heard.bonus(lib, ids)
            score += bonus
            if bonus >= 0.15 and not because:
                because = _("From listening")
        out.append({"key": k, "playlist": p, "name": nsp["name"], "title": title or nsp["name"],
                    "why": why or _reason(top, n), "count": n, "topArtists": lib.artist_rows(ids, 6),
                    "covers": lib.covers(ids), "score": round(score, 3) - (1 if is_shared else 0), "group": group,
                    "person": p.get("person"), "shared": is_shared, "because": because})

    def mix_count(person, wid):
        k = (person, wid)
        if k not in mix_cache:
            mix_cache[k] = rules.count(cfg, lib, {"person": person, "welt": wid, "stil": ALL}, ctx)
        return mix_cache[k]

    def offer(p, score, title, why, group, because=None, min_songs=8):
        """Suggestion without the rules for normal playlists (minimum count, several bands) – for favorite bands and recap."""
        k = key_of(p)
        if k in existing:
            return
        from .mixer import pick
        nsp = rules.build_nsp(cfg, p, ctx)
        ids = frozenset(pick(cfg, lib, p, nsp)[0]) if p.get("type") == "mix" else lib.match(nsp)
        if len(ids) < min_songs:
            return
        existing.add(k)
        out.append({"key": k, "playlist": p, "name": nsp["name"], "title": title, "why": why, "count": len(ids),
                    "topArtists": lib.artist_rows(ids, 6), "covers": lib.covers(ids), "score": score, "group": group,
                    "person": p.get("person"), "shared": False, "because": because})

    def special(person, prof):
        pid = person["id"]
        own = pid == default
        favs = rules.favorite_artists(cfg, person, ctx)
        if favs:
            # name: goes to Navidrome (server language); title: the card (language of the page)
            name = _s("New from our favorite bands") if own else \
                _s("New from {name}’s favorite bands", name=person["name"], owner=possessive(person["name"]))
            title = _("New from our favorite bands") if own else \
                _("New from {name}’s favorite bands", name=person["name"], owner=possessive(person["name"]))
            offer({"person": pid, "welt": ALL, "stil": ALL, "fav": {"days": 60}, "sort": "neu", "minRating": 0, "name": name},   # i18n-ignore: stored value
                  2.3, title, _("what the favorite bands added in the last two months – newest first"), pid,
                  because=_("From listening") if prof else None, min_songs=5)
        if person.get("user"):
            from .mixer import mix_day
            for period, score, why in (("month", 2.0, _("the most played songs of last month – changes on the first of the "
                                                        "month, it stays one playlist")),
                                       ("year", 1.4, _("the most played songs of the year – in January the whole previous year"))):
                p = {"person": pid, "welt": ALL, "stil": ALL, "type": "mix", "review": {"period": period},
                     "mix": {"size": 50, "perArtist": 0, "perAlbum": 0, "every": "month"}}
                offer(p, score, rules.review_name(cfg, p, mix_day()), why, pid, because=_("From listening"), min_songs=20)

    def car_mix(owner, members):
        """Car ride: an hour from the family's worlds – with kids' songs, without songs for falling asleep, new every day."""
        wl = []
        for x in [owner] + members:
            wl += [w for w in (x.get("likes") or {}).get("welten", []) if w in welten]
            wl += [w for w, share in profiles.get(x["id"], {}).get("welten", []) if share >= 0.08 and w in welten]
        wl = list(dict.fromkeys(wl))
        if not wl:
            return
        p = {"person": owner["id"], "welt": wl, "stil": ALL, "type": "mix", "name": _s("Car ride"),
             "sound": {"arousal": [0.35, 1]}, "mix": {"size": 60, "minutes": 60, "perArtist": 2, "every": "day", "avoidRecent": 7}}
        if len(members) >= 2:
            p["together"] = [x["id"] for x in members]
        add(p, 2.0, title=_("Car ride"), why=_("an hour for the road every day – music everyone likes, kids’ songs included, nothing "
                                      "to fall asleep to"),
            group=owner["id"], because=_("From listening") if members else None)

    def morning_mix(person):
        """"Good morning" from the listening clock (listenclock.py): only if the account really listens in the
        morning – with its usual length, the worlds of its mornings and their sound (mixer.morning_sound)."""
        from . import listenclock
        info = listenclock.morning_of(cfg, lib, person["user"], today)
        if not info:
            return
        pid = person["id"]
        index = lib.index_of()
        plays = {index[sid]: n for sid, n in info["songs"].items() if sid in index}
        total = sum(plays.values()) or 1
        shares = []
        for w in cfg["welten"]:   # worlds that make up at least a fifth of the morning plays – otherwise everything
            block = rules.welt_block(w, ctx)
            if block:
                ids = lib.ids({"any": block})
                share = sum(n for i, n in plays.items() if i in ids) / total
                if share >= MORNING_SHARE:
                    shares.append((share, w["id"]))
        wl = [wid for _share, wid in sorted(shares, reverse=True)[:3]]
        own = pid == default
        name = _s("Good morning") if own else _s("Good morning, {name}", name=person["name"])
        title = _("Good morning") if own else _("Good morning, {name}", name=person["name"])
        why = _("{minutes} minutes every morning, for the usual listening on weekdays around {time} – starts calm, gets "
                "livelier and sounds like the mornings.", minutes=info["minutes"], time=info["at"]) if info["weekdays"] else \
            _("{minutes} minutes every morning, for the usual listening around {time} – starts calm, gets livelier and "
              "sounds like the mornings.", minutes=info["minutes"], time=info["at"])
        add({"person": pid, "welt": wl or ALL, "stil": ALL, "type": "mix", "daytime": "morning", "name": name,
             "mix": {"size": 40, "minutes": info["minutes"], "perArtist": 2, "every": "day", "avoidRecent": 3}},
            2.3, title=title, why=why, group=pid, because=_("From listening"))

    def family_mix(owner):
        """What everyone likes: the taste of all accounts with enough listening counts the same."""
        if not owner:
            return
        members, users = [], set()
        for x in sorted(persons, key=lambda x: x["id"] == default):   # one person per account, own before the shared one
            u = (x.get("user") or "").lower()
            if u and u not in users and x["id"] in profiles:
                users.add(u)
                members.append(x)
        car_mix(owner, members)
        if len(members) < 2:
            return
        wl = []
        for x in [owner] + members:
            wl += [w for w in (x.get("likes") or {}).get("welten", []) if w in welten]
            wl += [w for w, share in profiles.get(x["id"], {}).get("welten", []) if share >= 0.08 and w in welten]
        names = [x["name"] for x in members]
        add({"person": owner["id"], "welt": list(dict.fromkeys(wl)) or ALL, "stil": ALL, "type": "mix",
             "name": _s("What everyone likes"), "together": [x["id"] for x in members],
             "mix": {"size": 50, "perArtist": 2, "every": "week", "flavor": "ausgewogen"}},
            2.5, title=_("What everyone likes"),
            why=_("Songs that {names} all like – new every week, good for the car ride", names=join_and(names)),
            group=owner["id"], because=_("From listening"))

    # daily routines from the listening clock: one person per account – its own profile before the shared one
    routine = {}
    for x in sorted(persons, key=lambda x: x["id"] == default):
        if x.get("user") and x["id"] in profiles:
            routine.setdefault(x["user"].lower(), x["id"])

    for person in persons:
        pid = person["id"]
        if only_person and pid != only_person:
            continue
        likes = person.get("likes", {})
        prof = profiles.get(pid)
        liked_w = [w for w in likes.get("welten", []) if w in welten]
        # favorite worlds recognized from listening (at least 8 % of what was played), at most three
        heard_w = [w for w, share in (prof or {}).get("welten", []) if share >= 0.08 and w in welten and w not in liked_w][:3]
        liked_w = liked_w + heard_w
        liked_s = set(likes.get("stile", []))
        if not liked_w and not liked_s and pid != default:
            k = f"likes|{pid}"
            if k not in existing:
                out.append({"key": k, "kind": "likes", "person": pid, "group": pid, "score": 3.0,
                            "title": _("What does {name} like to listen to?", name=person["name"]),
                            "why": _("Choose favorite worlds and vibes – then matching suggestions show up here."),
                            "count": None, "topArtists": []})
            continue
        for wid in liked_w:
            w = welten[wid]
            base = 1.0 + (0.4 if wid in likes.get("welten", []) or wid in heard_w else 0)
            because = _("Played often") if wid in heard_w else None
            # mix and hits of the world
            add({"person": pid, "welt": wid, "stil": ALL}, base + 0.5, group=pid, because=because)
            total = mix_count(pid, wid) or 1
            hits = {"person": pid, "welt": wid, "stil": ALL, "hits": True}
            if rules.count(cfg, lib, hits, ctx) <= 0.75 * total:   # otherwise the mix already is "the hits"
                add(hits, base + 0.45, title=_("{world} – The Hits", world=w["name"]),
                    why=_("the most popular songs of the typical bands"), group=pid)
            max_share = 0.85 if w.get("separate") else 0.6   # kids × rock yes, indie × pop rather not
            for s in stile:
                if s.get("group") in ("Zeitreise", "Spezial") or s["id"] in ("klang-schlaf", "klang-morgen"):   # daily-routine mixes further down
                    continue
                seasonal = bool(s.get("season")) or s.get("kind") == "season"
                if seasonal and s.get("kind") != "season" and not rules.season_soon(s.get("season"), today):
                    continue
                p = {"person": pid, "welt": wid, "stil": s["id"]}
                n = rules.count(cfg, lib, p, ctx)
                if n < MIN_SONGS or (n / total > max_share and not seasonal):
                    continue   # almost the same as the mix
                if not w.get("separate") and not seasonal and coherence(cfg, lib, ctx, p) < 0.5:
                    continue   # only randomly tagged single albums (e.g. "Indie × Jazz")
                score = base + 0.25 * min(1, math.log10(n) / 2.5) + (0.5 if s["id"] in liked_s else 0)
                if s.get("group") == "Thema":
                    score += 0.3 if w.get("separate") else 0.05
                if seasonal:
                    score += 0.6
                add(p, score, group="saison" if seasonal else pid)

        # "all" playlists only for the shared person or with matching preferences
        if pid == cfg["settings"].get("defaultPerson") or liked_s:
            for s in stile:
                if s.get("kind") == "season" or s.get("excludeElsewhere", {}).get("albums") and not s.get("season"):
                    continue
                if s.get("season") and not rules.season_soon(s.get("season"), today):
                    continue
                if s["id"] == "wiederentdecken" and not has_plays:
                    continue
                if s["id"] == "lieblinge" and not has_loved:
                    continue
                if liked_s and s["id"] not in liked_s and pid != cfg["settings"].get("defaultPerson"):
                    continue
                score = 0.8 + (0.5 if s["id"] in liked_s else 0) + (0.6 if s.get("season") else 0) \
                    + (0.15 if s.get("group") in ("Zeitreise", "Spezial") else 0)
                add({"person": pid, "welt": ALL, "stil": s["id"]}, score,
                    group="saison" if s.get("season") else pid)

        # Daily Mixes: one per favorite world, new every day, at most 3 per band
        for wid in liked_w:
            if pid != default and wid not in likes.get("welten", []) and wid not in heard_w:
                continue
            w = welten[wid]
            add({"person": pid, "welt": wid, "stil": ALL, "type": "mix", "mix": {"size": 50, "perArtist": 3}},
                1.75 + (0.3 if w.get("separate") else 0), title=f"Daily Mix · {w['name']}",
                why=_("50 new songs every day – at most 3 per band, never twice in a row"), group=pid)
        if len(liked_w) >= 2 and pid != default:
            add({"person": pid, "welt": liked_w, "stil": ALL, "type": "mix",
                 "name": _s("{name}’s Daily Mix", name=person["name"], owner=possessive(person["name"])),
                 "mix": {"size": 60, "perArtist": 2, "flavor": "ausgewogen"}},
                2.1, title=_("{name}’s Daily Mix", name=person["name"], owner=possessive(person["name"])),
                why=_("new every day from all favorite worlds, at most 2 per band"), group=pid)
            add({"person": pid, "welt": liked_w, "stil": ALL, "type": "mix", "name": _s("Discoveries for {name}", name=person["name"]),
                 "mix": {"size": 40, "perArtist": 2, "flavor": "entdecken", "avoidRecent": 30}},
                1.6, title=_("Discoveries for {name}", name=person["name"]), why=_("Songs that rarely or never played – different ones every day"), group=pid)

        # Radio: favorite bands (or the biggest bands of the favorite worlds) + similar bands – new every week
        seeds = [a for a in likes.get("artists", []) if a not in dislikes_of(person)][:3]
        heard_seeds = set()
        if not seeds and prof:   # the most played bands
            seeds = [a for a, _ in prof["artists"] if a not in dislikes_of(person)][:3]
            heard_seeds = set(seeds)
        if not seeds and liked_w:
            seeds = [a for a, _ in lib.top_artists(lib.match(rules.build_nsp(cfg, {"person": pid, "welt": liked_w[0], "stil": ALL}, ctx)), 2)]
        for seed in seeds:
            add({"person": pid, "welt": ALL, "stil": ALL, "type": "mix", "radio": {"seed": [seed]},
                 "mix": {"size": 50, "perArtist": 3, "every": "week"}}, 1.65 + (0.3 if seed in heard_seeds else 0),
                title=f"Radio · {seed}", why=_("{band} and similar bands from your library – new every week", band=seed), group=pid,
                because=_("Played often") if seed in heard_seeds else None)

        if prof:
            # "Your sound": what sounds like the person's taste, from the whole library (sound, AI style, bands)
            sound_name = _s("Our sound") if pid == default else \
                _s("{name}’s sound", name=person["name"], owner=possessive(person["name"]))
            sound_title = _("Our sound") if pid == default else \
                _("{name}’s sound", name=person["name"], owner=possessive(person["name"]))
            add({"person": pid, "welt": ALL, "stil": ALL, "type": "mix", "minRating": 0, "name": sound_name,
                 "mix": {"size": 50, "perArtist": 2, "every": "day", "flavor": "geschmack", "avoidRecent": 14}},
                2.4, title=sound_title,
                why=_("Songs from the whole library that sound like what gets listened to and liked – new every day"),
                group=pid, because=_("From listening"))
            if any(x["id"] == "wiederentdecken" for x in stile):
                add({"person": pid, "welt": ALL, "stil": "wiederentdecken"}, 1.7,
                    why=_("Favorite songs that haven’t played for a long time"), group=pid, because=_("From listening"))

        # sound mixes (from the sound analysis): for falling asleep, for running wild, good mood – per favorite world
        for wid in liked_w[:2]:
            for sid, why in (("klang-schlaf", _("half an hour every evening that gets calmer and calmer and fades out "
                                                "without vocals if possible")),
                             ("klang-morgen", _("half an hour every morning that starts friendly and calm and gets livelier")),
                             ("klang-toben", _("fast, loud and danceable – recognized by the sound")),
                             ("klang-gute-laune", _("happy songs, recognized by the sound and the Last.fm mood"))):
                st_ = next((x for x in cfg["stile"] if x["id"] == sid), None)
                if not st_ or (sid == "klang-morgen" and prof):   # with listening data only from the clock (morning_mix)
                    continue
                if sid in ("klang-schlaf", "klang-morgen"):   # daily routine: fixed length instead of a song count, new every day
                    title = _("Good night · {world}", world=welten[wid]["name"]) if sid == "klang-schlaf" else \
                        _("Good morning · {world}", world=welten[wid]["name"])
                    stored = _s("Good night · {world}", world=welten[wid]["name"]) if sid == "klang-schlaf" else \
                        _s("Good morning · {world}", world=welten[wid]["name"])
                    add({"person": pid, "welt": wid, "stil": sid, "type": "mix", "name": stored,
                         "mix": {"size": 40, "minutes": 30, "perArtist": 2, "every": "day", "avoidRecent": 3}},
                        (1.7 if sid == "klang-schlaf" else 1.65) + (0.3 if welten[wid].get("separate") else 0), title=title, why=why, group=pid)
                    continue
                add({"person": pid, "welt": wid, "stil": sid, "type": "mix", "mix": {"size": 40, "perArtist": 3, "every": "week"}},
                    1.55, title=f"{st_['name']} · {welten[wid]['name']}", why=why, group=pid)

        # new from the favorite bands, recap "Your October" – from what is played and liked
        special(person, prof)
        if prof and routine.get((person.get("user") or "").lower()) == pid:
            morning_mix(person)

        # personal smart playlist across all favorite worlds (“All Sorts” – not a mix: “Mix” is for real mixes)
        if len(liked_w) >= 2 and pid != default:
            add({"person": pid, "welt": liked_w, "stil": ALL, "minRating": 3,
                 "name": _s("{name}’s All Sorts", name=person["name"], owner=possessive(person["name"]))},
                2.2, title=_("{name}’s All Sorts", name=person["name"], owner=possessive(person["name"])),
                why=_("across all favorite worlds, from ★★★"), group=pid)
            add({"person": pid, "welt": liked_w, "stil": "neu", "name": _s("New for {name}", name=person["name"])},   # i18n-ignore: stored value
                1.9, title=_("New for {name}", name=person["name"]), why=_("what is new in the favorite worlds"), group=pid)

    # family mix "What everyone likes": for the shared person as soon as at least two accounts have listened enough
    if not only_person and default:
        family_mix(next((x for x in persons if x["id"] == default), None))

    # new music worlds from the scene catalog
    linked = {w.get("scene") for w in cfg["welten"]}
    index = lib.artist_index()
    auto_welten = (cfg["settings"].get("welten") or {}).get("auto", True)
    for sc in ([] if only_person or auto_welten else scenes.catalog()):
        k = f"scene|{sc['id']}"
        if sc["id"] in linked or k in existing:
            continue
        present = scenes.members(sc["id"], index)
        if len(present) < 4:
            continue
        welt = {"id": sc["id"], "name": sc["name"], "icon": sc["icon"], "artists": [], "albums": [], "genres": [],
                "excludeTitles": [], "excludeAlbums": [], "minRating": 3, "minDuration": None, "separate": False,
                "scene": sc["id"], "autoScene": True, "excludedArtists": []}
        tmp = {**cfg, "welten": cfg["welten"] + [welt]}
        ids = lib.match(rules.build_nsp(tmp, {"person": cfg["settings"].get("defaultPerson"), "welt": sc["id"],
                                              "stil": ALL}, BuildContext(lib, today)))
        if len(ids) < MIN_SONGS:
            continue
        aid = lib.artist_ids()
        # does the scene fit what someone plays often? Then further up and with a reason
        present_set, heard_here, boost = set(present), [], 0.0
        for prof in profiles.values():
            hits = [(a, sh) for a, sh in prof["artists"] if a in present_set]
            boost = max(boost, sum(sh for _, sh in hits))
            heard_here += [a for a, _ in hits if a not in heard_here]
        out.append({"key": k, "kind": "scene", "scene": sc["id"], "welt": welt, "name": sc["name"],
                    "title": _("New music world: {name}", name=sc["name"]), "why": sc.get("description", ""),
                    "count": len(ids), "topArtists": [[a, 0, aid.get(a)] for a in present[:8]], "bands": present,
                    "bandIds": [aid.get(a) for a in present], "covers": lib.covers(ids),
                    "score": 1.5 + 0.1 * min(len(present), 10) + (1.0 + 3 * boost if boost >= 0.03 else 0),
                    "group": "welten", "person": None,
                    "because": _("Played often: {bands}", bands=", ".join(heard_here[:3])) if boost >= 0.03 else None})

    out.sort(key=lambda x: -x["score"])
    # limit per person so the list stays clear
    seen, result = {}, []
    for s in out:
        g = s["group"]
        seen[g] = seen.get(g, 0) + 1
        if seen[g] <= (per_person if g not in ("saison", "welten") else 12):
            result.append(s)
    return result


UNUSED_DAYS = 90


def unused_playlists(cfg, lib, only_persons=None, today=None):
    """Active playlists from which not a single song has played for 90 days – on any account. Only once Tuttiphon
    has been counting that long (recap), and only for playlists that are at least that old. -> [playlist]"""
    from . import rueckblick
    today = today or dt.date.today()
    start = today - dt.timedelta(days=UNUSED_DAYS)
    users = {(p.get("user") or "").strip() for p in cfg["personen"] if p.get("user")}
    played, counted = set(), False
    for u in users:
        snap = rueckblick.last_snapshot(u)
        if snap and (snap.get("since") or "9999")[:10] <= start.isoformat():
            counted = True
        played |= set(rueckblick.plays_between(u, start, today)[0])
    if not counted:
        return []
    ctx = BuildContext(lib, today)
    seasonal = {s["id"] for s in cfg["stile"] if s.get("season")}
    out = []
    for p in cfg["playlists"]:
        if p.get("status", "aktiv") != "aktiv" or (p.get("created") or "") > start.isoformat():   # i18n-ignore: stored value
            continue
        if p.get("stil") in seasonal:   # seasonal playlists rest part of the year – unplayed is normal there
            continue
        if only_persons is not None and (p.get("person") or cfg["settings"].get("defaultPerson")) not in only_persons:
            continue
        try:
            pool = lib.match(rules.build_nsp(cfg, p, ctx))
        except (KeyError, ValueError, TypeError):
            continue
        if pool and not any(lib.songs[i]["id"] in played for i in pool):
            out.append(p)
    return out


# What a playlist selects and orders – everything else (name, file, cover, visibility …) does not count when comparing
CONTENT_FIELDS = ("welt", "stil", "type", "hits", "radio", "fav", "review", "together", "minRating", "minDuration",
                  "notPlayedDays", "addArtists", "excludeArtists", "sound", "mix", "sort", "sortRaw", "limit",
                  "rulesExtra", "rulesOp", "yearRound")


def duplicate_playlists(cfg):
    """Active playlists of the same person with exactly the same selection. -> [[playlist, playlist, …]]"""
    groups = {}

    def norm(v):   # the order in lists does not matter
        if isinstance(v, list) and all(isinstance(x, str) for x in v):
            return sorted(v)
        return v
    for p in cfg["playlists"]:
        if p.get("status", "aktiv") == "aktiv" and p.get("rules") is None:   # i18n-ignore: stored value
            k = json.dumps({"person": p.get("person") or cfg["settings"].get("defaultPerson"),
                            **{f: norm(p.get(f)) for f in CONTENT_FIELDS}}, sort_keys=True, default=str)
            groups.setdefault(k, []).append(p)
    return [g for g in groups.values() if len(g) > 1]


def playlist_tidy_items(cfg, lib, only_persons=None, user=False):
    """"To review" entries for tidying up: (key, level, title, text, actions). user=True: for users (links instead of
    buttons)."""
    from .rules import playlist_name
    out = []
    unused = unused_playlists(cfg, lib, only_persons)
    if len(unused) > 3:
        names = [playlist_name(cfg, p) for p in unused]
        out.append(("unused|" + "+".join(sorted(p["id"] for p in unused)), "info",
                    _("Nobody listens to {n} playlists", n=len(unused)),
                    _("Not a single song from them has played for three months: {names}. Pausing takes them out of "
                      "Symfonium, they stay saved here.", names=", ".join(names[:5]) + (" …" if len(names) > 5 else ""))
                    .replace("….", "…"),   # a cut list ends in “…”, not in “….”
                    [{"label": _("View"), "do": "goto", "href": "#/playlists"}] if user else
                    [{"label": _("Pause all"), "do": "pauseAll", "ids": [p["id"] for p in unused]},
                     {"label": _("View"), "do": "goto", "href": "#/playlists"}]))
    else:
        for p in unused:
            out.append((f"unused|{p['id']}", "info", _("Nobody listens to “{name}”", name=playlist_name(cfg, p)),
                        _("Not a single song from it has played for three months. Pausing takes it out of Symfonium, "
                          "here it stays kept."),
                        [{"label": _("View"), "do": "goto", "href": f"#/playlist/{p['id']}"}] if user else
                        [{"label": _("Pause"), "do": "pause", "id": p["id"]},
                         {"label": _("View"), "do": "goto", "href": f"#/playlist/{p['id']}"}]))
    for group in duplicate_playlists(cfg):
        if only_persons is not None and (group[0].get("person") or cfg["settings"].get("defaultPerson")) not in only_persons:
            continue
        names = [playlist_name(cfg, p) for p in group]
        out.append(("dup|" + "+".join(sorted(p["id"] for p in group)), "info", _("Duplicate playlist"),
                    _("“{first}” and “{second}” have exactly the same selection. One of them is enough.",
                      first=names[0], second=names[1]),
                    [{"label": _("View"), "do": "goto", "href": f"#/playlist/{group[1]['id']}"}]))
    return out


def inbox(cfg, lib, env, deezer_stats, handmade_list, users_ok):
    """What needs attention for ongoing care."""
    ctx = BuildContext(lib)
    ignored = set(cfg.get("ignored", []))
    items = []

    def item(key, level, title, text, actions=()):
        if key not in ignored:
            items.append({"key": key, "level": level, "title": title, "text": text, "actions": list(actions)})

    missing = [u for u, ok in users_ok.items() if not ok]
    if missing:
        item("cred", "warn", _("Passwords missing"),
             _("Without a password for {users}, Deezer cannot set stars and the preview is only approximate.",
               users=", ".join(missing)),
             [{"label": _("Enter"), "do": "settings"}])
    new = (deezer_stats or {}).get("new")
    if new:
        item(f"deezer-{new}", "info", _n(new, "{n} new song without a rating", "{n} new songs without a rating"),
             _("Deezer can rate them in a few seconds."),
             [{"label": _("Rate now"), "do": "task", "steps": ["deezer"]}])
    for h in handmade_list:
        item(f"hand|{h['file']}", "info", _("Handmade playlist “{name}”", name=h["name"]),
             _("Take it over into the tool to edit it here. It stays the same playlist in Navidrome."),
             [{"label": _("Take over …"), "do": "takeover", "file": h["file"]}])

    count, genres, _untagged, first = rules.artist_stats(lib.songs)
    in_welt = {a for w in cfg["welten"] for a in rules.welt_artists(w, ctx)}
    in_welt |= {a for w in cfg["welten"] for a in w.get("excludedArtists", [])}
    recent = (dt.date.today() - dt.timedelta(days=45)).isoformat()
    # classification: Last.fm tags, similar bands, genres, scenes (classify.py) – with a confidence
    from . import classify
    use_classify = (cfg["settings"].get("analysis") or {}).get("classify", "suggest") != "off"
    guesses = {x["artist"]: x for x in classify.suggestions(cfg, lib, ctx)} if use_classify else {}
    auto_welten = (cfg["settings"].get("welten") or {}).get("auto", True)
    welt_name = {w["id"]: w["name"] for w in cfg["welten"]}
    shown = set()
    for artist, since in sorted(first.items(), key=lambda x: x[1], reverse=True):
        if since < recent or artist in in_welt or count[artist] < 3:
            continue
        actions = []
        guess = guesses.get(artist)
        unlinked = [] if auto_welten else [scenes.scene(s) for s in scenes.scenes_for_artist(artist)
                                           if s not in {w.get("scene") for w in cfg["welten"]}]
        if unlinked:
            sc = unlinked[0]
            actions.append({"label": _("fits {name} (new world)", name=sc["name"]), "do": "goto", "tab": "vorschlaege"})
        elif guess:
            actions.append({"label": f"→ {welt_name[guess['welt']]} ({int(guess['score'] * 100)} %)", "do": "addToWelt",
                            "welt": guess["welt"], "artist": artist})
        actions.append({"label": _("Assign music world …"), "do": "artist", "artist": artist})   # opens the band window
        shown.add(artist)
        # the date is formatted by the text itself: {date:%d.%m.} in German, {date:%b %-d} in English
        day = dt.date.fromisoformat(since)
        if genres[artist]:
            text = _("{n} songs since {date:%b %-d} · {genres} – not in any music world yet.", n=count[artist], date=day,
                     genres=", ".join(g for g, _c in genres[artist].most_common(2)))
        else:
            text = _("{n} songs since {date:%b %-d} – not in any music world yet.", n=count[artist], date=day)
        if guess:
            text += " " + _("Reason for the suggestion: {why}.", why=guess["why"])
        item(f"new|{artist}", "info", _("New: {artist}", artist=artist), text, actions)
    # automatically classified new bands of the last 14 days – to look through, with "Undo"
    cutoff = (dt.datetime.now() - dt.timedelta(days=14)).isoformat(timespec="seconds")
    for e in classify.auto_log().values():
        w = next((x for x in cfg["welten"] if x["id"] == e.get("welt")), None)
        if w and (e.get("at") or "") >= cutoff and e.get("name") in w.get("artists", []):
            item(f"auto|{e['name']}", "info", _("“{artist}” is now in {world}", artist=e["name"], world=w["name"]),
                 _("Classified automatically by sound, tags and similar bands – confidence {pct} %.",
                   pct=int((e.get("score") or 0) * 100)),
                 [{"label": _("Undo"), "do": "undoAssign", "welt": w["id"], "artist": e["name"]}])

    # older bands without a world whose classification is fairly certain
    for g in [x for x in guesses.values() if x["artist"] not in shown and x["score"] >= 0.6][:5]:
        item(f"class|{g['artist']}", "info", _("“{artist}” fits {world} ({pct} %)", artist=g["artist"],
                                               world=welt_name[g["welt"]], pct=int(g["score"] * 100)),
             _n(g["songs"], "{n} song, not in any music world yet – {why}.", "{n} songs, not in any music world yet – {why}.",
                why=g["why"]),
             [{"label": _("Add to {world}", world=welt_name[g["welt"]]), "do": "addToWelt", "welt": g["welt"],
               "artist": g["artist"]}])

    linked = {w.get("scene") for w in cfg["welten"]}
    index = lib.artist_index()
    fresh = [] if auto_welten else [
        sc for sc in scenes.catalog() if sc["id"] not in linked and len(scenes.members(sc["id"], index)) >= 4
        and f"scene|{sc['id']}" not in set(cfg.get("dismissed", []))]
    # music worlds created automatically in the last 14 days – to look through
    from . import autowelten
    made = autowelten.recent(cfg)
    if len(made) == 1:
        w = made[0]
        bands = rules.welt_artists(w, ctx)
        if bands:
            text = _n(len(bands), "Recognized in your library: {n} band, for example {bands}. New bands of this kind are "
                      "added automatically.", "Recognized in your library: {n} bands, for example {bands}. New bands of "
                      "this kind are added automatically.", bands=", ".join(bands[:3]))
        else:
            text = _("Recognized in your library: {n} bands. New bands of this kind are added automatically.", n=len(bands))
        item(f"autowelt|{w['id']}", "info", _("New music world “{name}”", name=w["name"]), text,
             [{"label": _("View"), "do": "goto", "href": f"#/welt/{w['id']}"}])
    elif made:
        item("autowelten|" + "+".join(sorted(w["id"] for w in made)), "info",
             _("{n} new music worlds from your library", n=len(made)),
             _("{names}. New bands of this kind are added automatically; just delete what doesn’t fit.",
               names=", ".join(w["name"] for w in made[:8]) + (" …" if len(made) > 8 else "")).replace("….", "…"),
             [{"label": _("View"), "do": "goto", "href": "#/welten"}])
    if fresh:
        item(f"scenes-{len(fresh)}", "info", _n(len(fresh), "{n} music world discovered in your library",
                                                "{n} music worlds discovered in your library"),
             ", ".join(s["name"] for s in fresh[:6]) + (" …" if len(fresh) > 6 else ""),
             [{"label": _("View"), "do": "goto", "tab": "vorschlaege"}])

    # tidy up: what nobody listens to, what exists twice – so Symfonium stays clear
    for x in playlist_tidy_items(cfg, lib):
        item(*x)

    from . import selfcheck   # self-check after the last scan: Navidrome returns something other than expected
    for x in selfcheck.load().get("problems", []):
        item(f"check|{x['id']}|{x['actual']}", "warn",
             _("“{name}”: Navidrome shows {actual} instead of {expected} songs", name=x["name"], actual=x["actual"],
               expected=x["expected"]),
             _("The mix file contains songs Navidrome cannot find – usually the file paths are wrong (e.g. after renaming).")
             if x["kind"] == "mix" else
             _("Tuttiphon evaluates the rules differently from Navidrome. View it and save the playlist again if needed; if it "
               "stays that way, it is a case for the administrator."),
             [{"label": _("View"), "do": "edit", "id": x["id"]}])

    for p in cfg["playlists"]:
        if p.get("status", "aktiv") != "aktiv":   # i18n-ignore: stored value
            continue
        try:
            n = rules.count(cfg, lib, p, ctx)
        except KeyError:
            continue
        if n < 15:
            item(f"low|{p['id']}|{n}", "warn",
                 _n(n, "“{name}” has only {n} song", "“{name}” has only {n} songs", name=rules.playlist_name(cfg, p)),
                 _("Maybe lower the minimum rating or add more bands."),
                 [{"label": _("Edit"), "do": "edit", "id": p["id"]}])

    names = {n for v in index.values() for n in v}
    for w in cfg["welten"]:
        gone = [a for a in w.get("artists", []) if a not in names]
        if gone:
            item(f"gone|{w['id']}|{len(gone)}", "info",
                 _n(len(gone), "{world}: {n} band no longer there", "{world}: {n} bands no longer there", world=w["name"]),
                 _("{names} – maybe moved to the archive.", names=", ".join(gone[:5]) + (" …" if len(gone) > 5 else "")),
                 [{"label": _("Remove from the list"), "do": "removeGone", "welt": w["id"], "artists": gone}])

    untagged = [x for x in rules.untagged_artists(cfg, lib.songs) if not x["stile"]]
    if untagged:
        item(f"untagged-{len(untagged)}", "info",
             _n(len(untagged), "{n} band without genre tags", "{n} bands without genre tags"),
             _("{names} – they don’t show up in vibes like Rock or Pop.", names=", ".join(x["artist"] for x in untagged[:6])),
             [{"label": _("Assign"), "do": "goto", "tab": "richtungen"}])
    return items
