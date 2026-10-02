"""Seed reproducible reports into a local demo database."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import database as db  # noqa: E402


async def seed(db_path):
    previous = db._DB_PATH
    db._DB_PATH = str(db_path)
    try:
        await db.init_db()
        video_id = "dQw4w9WgXcQ"
        if await db.get_video(video_id):
            return
        await db.create_video(video_id, f"https://www.youtube.com/watch?v={video_id}")
        await db.update_video_results(
            video_id,
            title="The science of everyday life: eight claims worth checking",
            channel="Demo Channel",
            duration_seconds=842,
            transcript_text="Demo transcript for a local interface fixture.",
            overall_truth_percentage=52,
            summary="The video gets several basic science facts right, but overstates what we know about memory and the ocean. The strongest evidence contradicts its claim that humans use only ten percent of their brains.",
            processing_time_seconds=72,
            pipeline_version=2,
            published_at="2026-09-18",
            key_issues=["The ten-percent brain claim is false.", "The ocean figure lacks the context needed to interpret it."],
            model="demo-fixture",
            cost_usd=0.14,
            input_tokens=5400,
            output_tokens=1800,
            search_requests=16,
        )
        texts = [
            ("true", "Earth takes roughly one year to orbit the Sun.", "The orbital period is approximately 365.25 days. The claim accurately describes a year.", 95),
            ("mostly_true", "Water boils at 100°C.", "This is accurate at standard atmospheric pressure. Altitude changes the boiling point.", 75),
            ("mixed", "We have explored five percent of the ocean.", "The figure depends on what counts as exploration. Mapping the seafloor and directly observing it are different measures.", 50),
            ("mostly_false", "A goldfish remembers things for only a few seconds.", "Goldfish have relatively small brains, but studies demonstrate learning and memory over much longer periods.", 25),
            ("false", "Humans use only ten percent of their brains.", "Brain imaging shows activity across the brain, even during routine tasks. The ten-percent figure is a persistent myth.", 5),
            ("unverifiable", "This new supplement doubles everyone's memory.", "No sufficiently reliable evidence supports the stated effect for everyone. The product and study are not identified.", 50),
            ("opinion", "Space exploration is humanity's most worthwhile ambition.", "This is a value judgment about priorities, not a claim that evidence can establish as true or false.", 50),
            ("true", "The Moon's gravity causes tides on Earth.", "The Moon is a primary driver of tides. The Sun also contributes to tidal forces.", 95),
        ]
        claims = []
        for i, (verdict, text, reasoning, score) in enumerate(texts):
            refutes = verdict in {"false", "mostly_false"}
            claims.append(dict(
                text=text, quote=text, verdict=verdict, reasoning=reasoning,
                timestamp_seconds=25 + i * 75, truth_percentage=score,
                confidence=0.9 if i != 5 else 0.4,
                confidence_label="low" if i == 5 else "high",
                speaker="guest" if i == 2 else "quoted" if i == 3 else "creator",
                topic="Neuroscience" if i == 4 else "Science",
                checkworthiness=5 if refutes else 3,
                category="opinion" if verdict == "opinion" else "fact",
                corrected_claim="Humans use many regions throughout the brain." if i == 4 else "",
                relies_on_general_knowledge=i == 6,
                sources=[] if i in (5, 6) else [
                    dict(title="Understanding the evidence", url="https://www.nasa.gov/", domain="nasa.gov",
                         reliability="high", stance="refutes" if refutes else "context" if i == 2 else "supports",
                         quote="This is a demo evidence passage for interface testing, not a published quotation.", kind="web"),
                    dict(title="A closer look at the claim", url="https://fullfact.org/", domain="fullfact.org",
                         reliability="factchecker", stance="refutes" if refutes else "context",
                         quote="Demo fact-check quotation: the evidence does not support the claim as stated.",
                         kind="factcheck", rating="False" if refutes else "Needs context"),
                    dict(title="Further reading", url="https://www.britannica.com/", domain="britannica.com",
                         reliability="medium"),
                ],
            ))
        await db.create_claims(video_id, claims)
        legacy = "jNQXAC9IVRw"
        await db.create_video(legacy, f"https://www.youtube.com/watch?v={legacy}")
        await db.update_video_results(
            legacy, title="A short introduction to our planet", channel="Archive Channel", duration_seconds=19,
            transcript_text="Legacy demo transcript.", overall_truth_percentage=68,
            summary="An earlier report, with verdicts mapped from the original accuracy scale.",
            processing_time_seconds=12, pipeline_version=1,
        )
        await db.create_claims(legacy, [dict(text=text, timestamp_seconds=i * 5, truth_percentage=score,
                                           confidence=0.8, reasoning="An assessment from the original pipeline.",
                                           category="fact", verdict=None)
                                        for i, (text, score) in enumerate([
                                            ("Earth orbits the Sun.", 95),
                                            ("Every year has exactly 365 days.", 50),
                                            ("Earth has one natural moon.", 75),
                                        ])])
        await db.create_video("aaaaaaaaaaa", "https://www.youtube.com/watch?v=aaaaaaaaaaa")
        await db.update_video_status("aaaaaaaaaaa", "failed", "Captions could not be retrieved for this video.")
    finally:
        db._DB_PATH = previous


if __name__ == "__main__":
    asyncio.run(seed(sys.argv[1] if len(sys.argv) > 1 else "data/demo.db"))
