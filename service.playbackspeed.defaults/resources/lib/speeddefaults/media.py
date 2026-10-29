"""Describe the playing video (or a library item) as a resolver.MediaInfo."""

from urllib.parse import unquote

import xbmc

from .kodiutils import log, rpc
from .resolver import LIBRARY_PATH, LIBRARY_TAG, LibraryRule, MediaInfo


def _tvshow_details(tvshowid):
    result = rpc("VideoLibrary.GetTVShowDetails", tvshowid=tvshowid,
                 properties=["title", "genre", "tag"])
    return (result or {}).get("tvshowdetails")


def _episode_tvshowid(episodeid):
    result = rpc("VideoLibrary.GetEpisodeDetails", episodeid=episodeid,
                 properties=["tvshowid"])
    details = (result or {}).get("episodedetails") or {}
    return details.get("tvshowid", -1)


def _movie_details(movieid):
    result = rpc("VideoLibrary.GetMovieDetails", movieid=movieid, properties=["genre", "tag"])
    return (result or {}).get("moviedetails")


def from_player(player=None):
    player = player or xbmc.Player()
    if not player.isPlayingVideo():
        return None
    tag = player.getVideoInfoTag()
    mediatype = tag.getMediaType()
    dbid = tag.getDbId()
    info = MediaInfo(
        title=tag.getTitle(),
        series_title=tag.getTVShowTitle(),
        genres=list(tag.getGenres()),
        path=player.getPlayingFile(),
    )
    if mediatype == "episode" or info.series_title:
        info.kind = "episode"
        # Episodes rarely carry the show's genres and never its tags, so look
        # up the show when the episode is in the library.
        if mediatype == "episode" and dbid > 0:
            tvshowid = _episode_tvshowid(dbid)
            show = _tvshow_details(tvshowid) if tvshowid > 0 else None
            if show:
                info.series_title = show.get("title") or info.series_title
                info.genres = show.get("genre") or info.genres
                info.tags = show.get("tag") or []
    elif mediatype == "movie":
        info.kind = "movie"
        if dbid > 0:
            movie = _movie_details(dbid)
            if movie:
                info.genres = movie.get("genre") or info.genres
                info.tags = movie.get("tag") or []
    log("Playing: {}".format(info))
    return info


def series_title_from_listitem(listitem):
    """Show title for a tvshow/season/episode list item (context menu)."""
    tag = listitem.getVideoInfoTag()
    if tag.getMediaType() == "tvshow":
        return tag.getTitle() or listitem.getLabel()
    return tag.getTVShowTitle() or xbmc.getInfoLabel("ListItem.TVShowTitle")


def _split_multipath(path):
    if not path.startswith("multipath://"):
        return [path]
    parts = path[len("multipath://"):].split("/")
    return [unquote(part) for part in parts if part]


def video_sources():
    """Kodi video sources as (label, path), with multipath sources expanded."""
    result = rpc("Files.GetSources", media="video")
    sources = []
    for source in (result or {}).get("sources", []):
        for path in _split_multipath(source.get("file", "")):
            sources.append((source.get("label") or path, path))
    return sources


def library_tags():
    """Tags used in the video library. Jellyfin for Kodi tags every synced
    show and movie with its Jellyfin library name."""
    tags = set()
    for media_type in ("tvshow", "movie"):
        result = rpc("VideoLibrary.GetTags", type=media_type)
        tags.update(tag["label"] for tag in (result or {}).get("tags", []) if tag.get("label"))
    return sorted(tags, key=str.casefold)


def library_candidates(info=None):
    """Libraries the user can give a default, as LibraryRule templates (speed 0).

    With `info`, only those that apply to that video.
    """
    tags = info.tags if info is not None else library_tags()
    candidates = [LibraryRule(LIBRARY_TAG, tag, 0, tag) for tag in tags]
    candidates += [LibraryRule(LIBRARY_PATH, path, 0, label) for label, path in video_sources()]
    if info is not None:
        candidates = [c for c in candidates if c.matches(info)]
    return candidates
