"""HTML metadata and crawler response builders."""

import html as html_module
import json as json_module
from urllib.parse import quote as url_quote

from backend.config import settings


def _html_escape(s: str) -> str:
    """Escape string for safe injection into HTML attributes."""
    return html_module.escape(s, quote=True)


def _inject_meta(template: str, replacements: dict[str, str]) -> str:
    """Replace placeholder tokens in a template with escaped values."""
    result = template
    for token, value in replacements.items():
        result = result.replace(token, value)
    return result


def _video_fallback_meta(video_id: str) -> dict[str, str]:
    """Default meta tokens when a video is not yet in the DB."""
    base = settings.BASE_URL
    thumbnail = f"https://img.youtube.com/vi/{url_quote(video_id)}/hqdefault.jpg"
    canonical = f"{base}/video/{url_quote(video_id)}"
    return {
        "__META_TITLE__": "Video Fact Check — YouTube Fact Checker",
        "__META_DESCRIPTION__": "AI-powered fact-check with accuracy scores and sourced evidence for every claim.",
        "__OG_TITLE__": "Video Fact Check — YouTube Fact Checker",
        "__OG_DESCRIPTION__": "AI-powered fact-check with accuracy scores and sourced evidence for every claim.",
        "__OG_IMAGE__": thumbnail,
        "__OG_URL__": canonical,
        "__CANONICAL_URL__": canonical,
        "__JSON_LD__": "",
    }


def _channel_fallback_meta(channel_name: str) -> dict[str, str]:
    """Default meta tokens when a channel is not found."""
    base = settings.BASE_URL
    canonical = f"{base}/channel/{url_quote(channel_name)}"
    return {
        "__META_TITLE__": f"{_html_escape(channel_name)} — YouTube Fact Checker",
        "__META_DESCRIPTION__": "See all fact-checked videos and average accuracy scores for this YouTube channel.",
        "__OG_TITLE__": f"{_html_escape(channel_name)} — YouTube Fact Checker",
        "__OG_DESCRIPTION__": "See all fact-checked videos and average accuracy scores for this YouTube channel.",
        "__OG_IMAGE__": "",
        "__OG_URL__": canonical,
        "__CANONICAL_URL__": canonical,
        "__JSON_LD__": "",
    }


def _iso_duration(seconds: int | float | None) -> str:
    """Convert seconds to ISO 8601 duration (PT#M#S)."""
    if not seconds:
        return "PT0S"
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"PT{hours}H{minutes}M{secs}S"
    if minutes:
        return f"PT{minutes}M{secs}S"
    return f"PT{secs}S"


def _video_jsonld(video: dict, canonical: str, thumbnail: str, score: int) -> str:
    """Build a <script type="application/ld+json"> block with VideoObject schema."""
    ld = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": video.get("title", ""),
        "description": video.get("summary", ""),
        "thumbnailUrl": thumbnail,
        "uploadDate": video.get("created_at", ""),
        "duration": _iso_duration(video.get("duration_seconds")),
        "url": canonical,
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": score,
            "bestRating": 100,
            "worstRating": 0,
            "ratingCount": 1,
        },
    }
    serialized = json_module.dumps(ld, ensure_ascii=False)
    serialized = serialized.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f'<script type="application/ld+json">{serialized}</script>'


def _channel_jsonld(name: str, count: int, avg_score: float, canonical: str) -> str:
    """Build a <script type="application/ld+json"> block with ProfilePage schema."""
    ld = {
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        "name": name,
        "url": canonical,
        "description": f"{count} fact-checked videos with {avg_score:.0f}% average accuracy.",
        "mainEntity": {
            "@type": "Person",
            "name": name,
        },
    }
    serialized = json_module.dumps(ld, ensure_ascii=False)
    serialized = serialized.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f'<script type="application/ld+json">{serialized}</script>'


def build_robots():
    return (
        "User-agent: *\nAllow: /\nAllow: /videos\nAllow: /video/\nAllow: /channel/\nDisallow: /api/\n"
        f"\nSitemap: {settings.BASE_URL}/sitemap.xml\n"
    )


def build_sitemap(videos, channels):
    base = settings.BASE_URL
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f"  <url><loc>{base}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>",
        f"  <url><loc>{base}/videos</loc><changefreq>daily</changefreq><priority>0.8</priority></url>",
        f"  <url><loc>{base}/about</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>",
    ]
    for video in videos:
        vid = _html_escape(video["id"])
        lastmod = f"<lastmod>{_html_escape(video['created_at'][:10])}</lastmod>" if video.get("created_at") else ""
        parts.append(
            f"  <url><loc>{base}/video/{vid}</loc>{lastmod}<changefreq>monthly</changefreq><priority>0.7</priority></url>"
        )
    for channel in channels:
        name = _html_escape(url_quote(channel["channel"]))
        parts.append(
            f"  <url><loc>{base}/channel/{name}</loc><changefreq>weekly</changefreq><priority>0.6</priority></url>"
        )
    return "\n".join([*parts, "</urlset>"])
