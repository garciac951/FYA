"""Write the Short's script with Claude (structured output), in English and Spanish."""
from __future__ import annotations

import random
from dataclasses import dataclass

import anthropic
from pydantic import BaseModel

from .topics import Topic


class Segment(BaseModel):
    narration: str
    narration_es: str
    visual_query: str


class ShortScript(BaseModel):
    title: str
    description: str
    tags: list[str]
    title_es: str
    description_es: str
    tags_es: list[str]
    segments: list[Segment]

    def localized(self, lang: str) -> "LocalizedScript":
        if lang == "en":
            return LocalizedScript("en", self.title, self.description, self.tags,
                                   [s.narration for s in self.segments])
        if lang == "es":
            return LocalizedScript("es", self.title_es, self.description_es, self.tags_es,
                                   [s.narration_es for s in self.segments])
        raise ValueError(f"Unsupported language '{lang}' (supported: en, es)")


@dataclass
class LocalizedScript:
    lang: str
    title: str
    description: str
    tags: list[str]
    narrations: list[str]


SYSTEM_PROMPT = """You write scripts for a faceless YouTube Shorts channel. Every Short is published twice: \
in English on "{channel_en}" and in Spanish on "{channel_es}". Each one is a voiceover over stock footage, \
aimed at regular people who like practical know-how.

What makes a script good here:
- The first sentence is the hook. It must earn the next 3 seconds on its own: a surprising claim, a \
mistake the viewer is probably making, or a specific question. Never open with "Did you know", \
"Hey guys", or the channel name.
- One idea per Short, delivered with a concrete, specific, accurate detail the viewer did not know. \
Real value, not filler. If you are not confident a fact is true, pick a different fact.
- Written for the ear: short sentences, plain words, no lists read aloud, no emojis, no stage directions. \
Spell numbers the way they should be spoken when it matters ("three hundred degrees").
- English narration: 85-125 words total. End with a one-line payoff or a natural loop back to the hook, \
not "like and subscribe".
- Split the narration into 5-8 segments of one or two sentences. For each, give visual_query: a 2-4 word \
English stock-footage search that a free library like Pixabay or Pexels will actually have (e.g. "trout river close", \
"mechanic engine bay", "smartphone settings screen"). Concrete nouns, no people's names, no brands, no text.
- title: under 60 characters, curiosity-driven but honest (no clickbait the video doesn't pay off). No hashtags.
- description: 1-2 sentences expanding on the tip, then a blank line, then 3 relevant hashtags including #shorts.
- tags: 5-10 lowercase search phrases.

Spanish version (narration_es, title_es, description_es, tags_es):
- Adapt, don't translate word for word. Write natural, conversational Spanish as spoken by Mexican and \
US Hispanic viewers, addressing the viewer as "tú". It should sound like it was written in Spanish first, \
with a hook that works just as hard in Spanish.
- Same facts and the same segment-by-segment meaning as the English, because both versions share the same \
footage: narration_es for each segment must match that segment's visual.
- Units: keep US units (Fahrenheit, inches, pounds) for US-specific topics such as Texas lawns or the NFL; \
otherwise use metric.
- Keep common English terms Spanish speakers actually use (e.g. "brisket", "app", "touchdown") when the \
Spanish word would sound stiff.
- title_es under 60 characters; description_es with Spanish hashtags including #shorts; tags_es in Spanish.

Every Short should feel different from the channel's earlier ones in angle, hook style and wording."""


def generate_script(topic: Topic, avoid_titles: list[str], *, model: str,
                    channel_en: str, channel_es: str) -> ShortScript:
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
        system=SYSTEM_PROMPT.format(channel_en=channel_en, channel_es=channel_es),
        messages=[{"role": "user", "content": "\n\n".join(user)}],
        output_format=ShortScript,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Script request was declined for topic {topic.id}")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError(f"Script generation did not finish (stop_reason={response.stop_reason})")

    script = response.parsed_output
    script.title = script.title.strip()[:95]
    script.title_es = script.title_es.strip()[:95]
    script.segments = [s for s in script.segments if s.narration.strip() and s.narration_es.strip()]
    if not 3 <= len(script.segments) <= 10:
        raise RuntimeError(f"Unexpected segment count: {len(script.segments)}")
    return script


def demo_script() -> ShortScript:
    """A canned script so the pipeline can be tested without an API key."""
    S = Segment
    return ShortScript(
        title="You're mowing your Bermuda grass too high",
        description="Bermuda grass grows thick when it's kept short and mowed often.\n\n#lawncare #bermudagrass #shorts",
        tags=["bermuda grass", "lawn care", "texas lawn", "mowing height", "lawn tips"],
        title_es="Estás cortando tu pasto Bermuda muy alto",
        description_es="El pasto Bermuda se pone tupido cuando lo mantienes corto y lo cortas seguido.\n\n#jardin #pastobermuda #shorts",
        tags_es=["pasto bermuda", "cuidado del pasto", "jardín texas", "altura de corte", "consejos de jardín"],
        segments=[
            S(narration="If your Bermuda lawn looks thin and stemmy, your mower is probably set too high.",
              narration_es="Si tu pasto Bermuda se ve ralo y con puro tallo, seguro tienes la podadora muy alta.",
              visual_query="lawn mower grass"),
            S(narration="Bermuda spreads sideways. It wants to be cut short, around one to two inches.",
              narration_es="El Bermuda crece hacia los lados. Le gusta corto, entre una y dos pulgadas.",
              visual_query="green lawn close"),
            S(narration="Let it grow tall and it shades its own runners, so you get brown stems instead of thick turf.",
              narration_es="Si lo dejas crecer, se hace sombra a sí mismo y en vez de pasto tupido te quedan tallos cafés.",
              visual_query="grass blades macro"),
            S(narration="The catch: never take off more than a third of the blade at once, or you'll scalp it.",
              narration_es="Eso sí: nunca le quites más de un tercio de la hoja de una vez, o lo vas a pelar.",
              visual_query="cutting grass slow motion"),
            S(narration="In a Texas summer that can mean mowing every four or five days.",
              narration_es="En un verano de Texas, eso puede ser cortarlo cada cuatro o cinco días.",
              visual_query="summer sun heat"),
            S(narration="Do that for a month and watch it thicken up like a golf course.",
              narration_es="Hazlo un mes y vas a ver cómo se pone tupido como campo de golf.",
              visual_query="golf course green"),
        ],
    )
