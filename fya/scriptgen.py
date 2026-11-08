"""Write the Short's script with Claude (structured output)."""
from __future__ import annotations

import random

import anthropic
from pydantic import BaseModel

from .topics import Topic


class Segment(BaseModel):
    narration: str
    visual_query: str


class ShortScript(BaseModel):
    title: str
    segments: list[Segment]
    description: str
    tags: list[str]

    @property
    def narration(self) -> str:
        return " ".join(s.narration for s in self.segments)


SYSTEM_PROMPT = """You write scripts for a faceless YouTube Shorts channel called "{channel}". \
Each Short is a 30-50 second voiceover over stock footage, aimed at regular people who like practical know-how.

What makes a script good here:
- The first sentence is the hook. It must earn the next 3 seconds on its own: a surprising claim, a \
mistake the viewer is probably making, or a specific question. Never open with "Did you know", \
"Hey guys", or the channel name.
- One idea per Short, delivered with a concrete, specific, accurate detail the viewer did not know. \
Real value, not filler. If you are not confident a fact is true, pick a different fact.
- Written for the ear: short sentences, plain words, no lists read aloud, no emojis, no stage directions. \
Spell numbers the way they should be spoken when it matters ("three hundred degrees").
- 85-125 words total. End with a one-line payoff or a natural loop back to the hook, not "like and subscribe".
- Split the narration into 5-8 segments of one or two sentences. For each, give visual_query: a 2-4 word \
stock-footage search that a site like Pexels will actually have (e.g. "trout river close", "mechanic engine bay", \
"green lawn sprinkler"). Concrete nouns, no people's names, no brands, no text.
- title: under 60 characters, curiosity-driven but honest (no clickbait the video doesn't pay off). No hashtags.
- description: 1-2 sentences expanding on the tip, then a blank line, then 3 relevant hashtags including #shorts.
- tags: 5-10 lowercase search phrases.

Every Short should feel different from the channel's earlier ones in angle, hook style and wording."""


def generate_script(topic: Topic, avoid_titles: list[str], *, model: str, channel: str) -> ShortScript:
    angle = random.choice(topic.angles) if topic.angles else "a useful tip"
    user = [
        f"Topic: {topic.name}",
        f"Angle for this one: {angle}",
        f"Suggested hashtags: {' '.join(topic.hashtags)}",
    ]
    if topic.guardrails:
        user.append(f"Guardrails for this topic: {topic.guardrails}")
    if avoid_titles:
        user.append("Already posted on this topic (do not repeat these ideas):\n- " + "\n- ".join(avoid_titles))
    user.append("Write the Short.")

    client = anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        # Server-side fallback: if a request is declined by a safety classifier, the API reruns it
        # on a suitable fallback model instead of failing the daily run.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM_PROMPT.format(channel=channel),
        messages=[{"role": "user", "content": "\n\n".join(user)}],
        output_format=ShortScript,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Script request was declined for topic {topic.id}")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError(f"Script generation did not finish (stop_reason={response.stop_reason})")

    script = response.parsed_output
    script.title = script.title.strip()[:95]
    script.segments = [s for s in script.segments if s.narration.strip()]
    if not 3 <= len(script.segments) <= 10:
        raise RuntimeError(f"Unexpected segment count: {len(script.segments)}")
    return script


def demo_script() -> ShortScript:
    """A canned script so the pipeline can be tested without an API key."""
    return ShortScript(
        title="You're mowing your Bermuda grass too high",
        segments=[
            Segment(narration="If your Bermuda lawn looks thin and stemmy, your mower is probably set too high.",
                    visual_query="lawn mower grass"),
            Segment(narration="Bermuda spreads sideways. It wants to be cut short, around one to two inches.",
                    visual_query="green lawn close"),
            Segment(narration="Let it grow tall and it shades its own runners, so you get brown stems instead of thick turf.",
                    visual_query="grass blades macro"),
            Segment(narration="The catch: never take off more than a third of the blade at once, or you'll scalp it.",
                    visual_query="cutting grass slow motion"),
            Segment(narration="In a Texas summer that can mean mowing every four or five days.",
                    visual_query="summer sun heat"),
            Segment(narration="Do that for a month and watch it thicken up like a golf course.",
                    visual_query="golf course green"),
        ],
        description="Bermuda grass grows thick when it's kept short and mowed often.\n\n#lawncare #bermudagrass #shorts",
        tags=["bermuda grass", "lawn care", "texas lawn", "mowing height", "lawn tips"],
    )
