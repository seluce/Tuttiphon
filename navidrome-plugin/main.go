// Tuttiphon plugin for Navidrome: similar songs, similar artists and sonic similarity, answered by Tuttiphon from the
// sound of the music files (its AI sound analysis) – and, as Navidrome's scrobbler, every play passed on to Tuttiphon
// as it happens. The plugin only passes things on: it asks Tuttiphon's /api/sonic/… with the key from the plugin
// settings and hands the answer back to Navidrome; plays go to /api/sonic/listen. See README.md.
package main

import (
	"encoding/json"
	"fmt"
	"net/url"
	"strconv"
	"strings"

	"github.com/navidrome/navidrome/plugins/pdk/go/host"
	"github.com/navidrome/navidrome/plugins/pdk/go/metadata"
	"github.com/navidrome/navidrome/plugins/pdk/go/pdk"
	"github.com/navidrome/navidrome/plugins/pdk/go/scrobbler"
	"github.com/navidrome/navidrome/plugins/pdk/go/sonicsimilarity"
)

const timeoutMs = 20000

type plugin struct{}

// song as Tuttiphon sends it (app/sonic.py as_songs)
type song struct {
	ID         string  `json:"id"`
	Title      string  `json:"title"`
	Artist     string  `json:"artist"`
	Album      string  `json:"album"`
	DurationMs uint32  `json:"durationMs"`
	Similarity float64 `json:"similarity"`
}

type answer struct {
	Songs   []song `json:"songs"`
	Artists []struct {
		ID   string `json:"id"`
		Name string `json:"name"`
	} `json:"artists"`
}

func config(key string) string {
	v, _ := host.ConfigGet(key)
	return strings.TrimSpace(v)
}

// ask sends one question to Tuttiphon: GET <url>/api/sonic/<what>?<params>.
func ask(what string, params url.Values) (*answer, error) {
	base := strings.TrimRight(config("url"), "/")
	key := config("key")
	if base == "" || key == "" {
		return nil, fmt.Errorf("Tuttiphon address or key missing in the plugin settings")
	}
	resp, err := host.HTTPSend(host.HTTPRequest{
		Method:    "GET",
		URL:       base + "/api/sonic/" + what + "?" + params.Encode(),
		Headers:   map[string]string{"Authorization": "Bearer " + key, "Accept": "application/json"},
		TimeoutMs: timeoutMs,
	})
	if err != nil {
		return nil, fmt.Errorf("Tuttiphon not reachable: %w", err)
	}
	if resp == nil {
		return nil, fmt.Errorf("Tuttiphon sent no answer")
	}
	if resp.StatusCode != 200 {
		text := strings.TrimSpace(string(resp.Body))
		if len(text) > 200 {
			text = text[:200]
		}
		return nil, fmt.Errorf("Tuttiphon answered %d: %s", resp.StatusCode, text)
	}
	var out answer
	if err := json.Unmarshal(resp.Body, &out); err != nil {
		return nil, fmt.Errorf("Tuttiphon's answer cannot be read: %w", err)
	}
	return &out, nil
}

func count(n int32, fallback int) string {
	if n <= 0 {
		return strconv.Itoa(fallback)
	}
	return strconv.Itoa(int(n))
}

func refs(songs []song) []metadata.SongRef {
	out := make([]metadata.SongRef, 0, len(songs))
	for _, s := range songs {
		out = append(out, metadata.SongRef{ID: s.ID, Name: s.Title, Artist: s.Artist, Album: s.Album, DurationMs: s.DurationMs})
	}
	return out
}

func matches(songs []song) []sonicsimilarity.SonicMatch {
	out := make([]sonicsimilarity.SonicMatch, 0, len(songs))
	for _, s := range songs {
		out = append(out, sonicsimilarity.SonicMatch{
			Song:       sonicsimilarity.SongRef{ID: s.ID, Name: s.Title, Artist: s.Artist, Album: s.Album, DurationMs: s.DurationMs},
			Similarity: s.Similarity,
		})
	}
	return out
}

// similarSongs: "nothing found" is an empty answer without an error (Navidrome then asks the next agent);
// an error only when Tuttiphon cannot be reached.
func similarSongs(what string, params url.Values) (*metadata.SimilarSongsResponse, error) {
	got, err := ask(what, params)
	if err != nil {
		pdk.Log(pdk.LogWarn, "[Tuttiphon] "+err.Error())
		return nil, err
	}
	if len(got.Songs) == 0 {
		return nil, nil
	}
	return &metadata.SimilarSongsResponse{Songs: refs(got.Songs)}, nil
}

// Instant Mix and song radio
func (plugin) GetSimilarSongsByTrack(req metadata.SimilarSongsByTrackRequest) (*metadata.SimilarSongsResponse, error) {
	return similarSongs("similar", url.Values{"id": {req.ID}, "count": {count(req.Count, 50)}})
}

func (plugin) GetSimilarSongsByAlbum(req metadata.SimilarSongsByAlbumRequest) (*metadata.SimilarSongsResponse, error) {
	return similarSongs("album", url.Values{"id": {req.ID}, "name": {req.Name}, "artist": {req.Artist},
		"count": {count(req.Count, 50)}})
}

// artist radio
func (plugin) GetSimilarSongsByArtist(req metadata.SimilarSongsByArtistRequest) (*metadata.SimilarSongsResponse, error) {
	return similarSongs("artist", url.Values{"id": {req.ID}, "name": {req.Name}, "count": {count(req.Count, 50)}})
}

// related artists (getArtistInfo)
func (plugin) GetSimilarArtists(req metadata.SimilarArtistsRequest) (*metadata.SimilarArtistsResponse, error) {
	got, err := ask("artists", url.Values{"id": {req.ID}, "name": {req.Name}, "count": {count(req.Limit, 20)}})
	if err != nil {
		pdk.Log(pdk.LogWarn, "[Tuttiphon] "+err.Error())
		return nil, err
	}
	if len(got.Artists) == 0 {
		return nil, nil
	}
	out := &metadata.SimilarArtistsResponse{}
	for _, a := range got.Artists {
		out.Artists = append(out.Artists, metadata.ArtistRef{ID: a.ID, Name: a.Name})
	}
	return out, nil
}

// OpenSubsonic sonicSimilarity: getSonicSimilarTracks
func (plugin) GetSonicSimilarTracks(req sonicsimilarity.GetSonicSimilarTracksRequest) (sonicsimilarity.SonicSimilarityResponse, error) {
	got, err := ask("similar", url.Values{"id": {req.Song.ID}, "count": {count(req.Count, 50)}})
	if err != nil {
		pdk.Log(pdk.LogWarn, "[Tuttiphon] "+err.Error())
		return sonicsimilarity.SonicSimilarityResponse{}, err
	}
	return sonicsimilarity.SonicSimilarityResponse{Matches: matches(got.Songs)}, nil
}

// OpenSubsonic sonicSimilarity: findSonicPath
func (plugin) FindSonicPath(req sonicsimilarity.FindSonicPathRequest) (sonicsimilarity.SonicSimilarityResponse, error) {
	got, err := ask("path", url.Values{"from": {req.StartSong.ID}, "to": {req.EndSong.ID}, "count": {count(req.Count, 25)}})
	if err != nil {
		pdk.Log(pdk.LogWarn, "[Tuttiphon] "+err.Error())
		return sonicsimilarity.SonicSimilarityResponse{}, err
	}
	return sonicsimilarity.SonicSimilarityResponse{Matches: matches(got.Songs)}, nil
}

// ---- plays, as Navidrome's scrobbler (only for the users assigned to the plugin in Navidrome)

// listenEvent as Tuttiphon takes it (POST /api/sonic/listen, app/listen.py)
type listenEvent struct {
	Event    string   `json:"event"`
	User     string   `json:"user"`
	ID       string   `json:"id"`
	Time     int64    `json:"time,omitempty"`
	Position *float64 `json:"position,omitempty"`
	State    string   `json:"state,omitempty"`
	Player   string   `json:"player,omitempty"`
}

// tell passes a play on. -> nil, or the HTTP status (0: Tuttiphon not reachable) with the error
func tell(e listenEvent) (int32, error) {
	base := strings.TrimRight(config("url"), "/")
	key := config("key")
	if base == "" || key == "" {
		return 400, fmt.Errorf("Tuttiphon address or key missing in the plugin settings")
	}
	body, err := json.Marshal(e)
	if err != nil {
		return 400, err
	}
	resp, err := host.HTTPSend(host.HTTPRequest{
		Method:    "POST",
		URL:       base + "/api/sonic/listen",
		Headers:   map[string]string{"Authorization": "Bearer " + key, "Content-Type": "application/json"},
		Body:      body,
		TimeoutMs: 10000,
	})
	if err != nil || resp == nil {
		return 0, fmt.Errorf("Tuttiphon not reachable: %v", err)
	}
	if resp.StatusCode != 200 {
		return resp.StatusCode, fmt.Errorf("Tuttiphon answered %d: %s", resp.StatusCode, strings.TrimSpace(string(resp.Body)))
	}
	return 200, nil
}

// quietly: a start or a player's report that does not arrive is not worth retrying
func quietly(_ int32, err error) error {
	if err != nil {
		pdk.Log(pdk.LogWarn, "[Tuttiphon] "+err.Error())
	}
	return nil
}

func (plugin) IsAuthorized(req scrobbler.IsAuthorizedRequest) (bool, error) {
	return config("url") != "" && config("key") != "", nil
}

func (plugin) NowPlaying(req scrobbler.NowPlayingRequest) error {
	pos := float64(req.Position)
	return quietly(tell(listenEvent{Event: "start", User: req.Username, ID: req.Track.ID, Position: &pos}))
}

func (plugin) PlaybackReport(req scrobbler.PlaybackReportRequest) error {
	pos := float64(req.PositionMs) / 1000
	player := req.PlayerId
	if player == "" {
		player = req.PlayerName
	}
	return quietly(tell(listenEvent{Event: "report", User: req.Username, ID: req.Track.ID, Position: &pos,
		State: req.State, Player: player}))
}

// Scrobble: a play – if Tuttiphon cannot be reached, Navidrome tries again later; a refusal (wrong key) is final
func (plugin) Scrobble(req scrobbler.ScrobbleRequest) error {
	status, err := tell(listenEvent{Event: "play", User: req.Username, ID: req.Track.ID, Time: req.Timestamp})
	if err == nil {
		return nil
	}
	pdk.Log(pdk.LogWarn, "[Tuttiphon] "+err.Error())
	if status == 0 || status >= 500 || status == 429 {
		return scrobbler.ScrobblerErrorRetryLater
	}
	return scrobbler.ScrobblerErrorUnrecoverable
}

func init() {
	metadata.Register(plugin{})
	sonicsimilarity.Register(plugin{})
	scrobbler.Register(plugin{})
}

func main() {}
