"""
agents.py — Assessment, Curriculum, Tutor, and Progress agents.

Uses Groq Cloud (OpenAI-compatible API) for all LLM calls.
Model: llama-3.3-70b-versatile (ultra-fast on Groq hardware)
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_MODEL = "llama-3.3-70b-versatile"   # fast + high-quality; swap to e.g. "mixtral-8x7b-32768" if needed


# ---------------------------------------------------------------------------
# Helper — build a fresh OpenAI client pointed at Groq
# ---------------------------------------------------------------------------

def _client() -> OpenAI:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. Add it to your .env file."
        )
    return OpenAI(
        api_key=key,
        base_url=_GROQ_BASE_URL,
    )


def _chat(messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
    """Send *messages* to Groq and return the assistant reply text."""
    client = _client()
    response = client.chat.completions.create(
        model=_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=4096,   # cap tokens — prevents 402 budget errors
    )
    return response.choices[0].message.content.strip()


def _extract_json(text: str) -> Any:
    """
    Try to parse the first JSON object/array found in *text*.
    Handles fenced code blocks, bare JSON, or the whole string.
    """
    # Strip fenced code block
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Bare JSON object / array
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return json.loads(text)  # raises if still broken


# ---------------------------------------------------------------------------
# Assessment Agent
# ---------------------------------------------------------------------------

class AssessmentAgent:
    """Generates diagnostic questions and scores learner answers."""

    def generate_questions(self, topic: str, num: int = 4) -> List[Dict[str, Any]]:
        """
        Returns a list of question dicts:
          {"question": str, "type": "open"|"mcq",
           "options": [...],   # MCQ only
           "answer": "A"}      # MCQ only
        """
        prompt = f"""You are an expert educator creating a short diagnostic quiz.

Topic: {topic}
Number of questions: {num}

Generate exactly {num} questions that test understanding of "{topic}".
Mix at least one multiple-choice question (type "mcq") and at least one
open-ended question (type "open").

Return ONLY valid JSON — no markdown, no explanation:
[
  {{
    "question": "<question text>",
    "type": "open"
  }},
  {{
    "question": "<question text>",
    "type": "mcq",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "answer": "A"
  }}
]"""
        reply = _chat([{"role": "user", "content": prompt}], temperature=0.5)
        return _extract_json(reply)

    def score_answers(
        self,
        topic: str,
        questions: List[Dict[str, Any]],
        answers: List[str],
    ) -> Tuple[int, str]:
        """Score the learner's answers. Returns (mastery 0-100, feedback str)."""
        qa_block = "\n".join(
            f"Q{i+1}: {q['question']}\nLearner answered: {a}"
            for i, (q, a) in enumerate(zip(questions, answers))
        )
        prompt = f"""You are an expert educator scoring a learner's quiz on "{topic}".

{qa_block}

Evaluate how well the learner understands "{topic}".
Return ONLY valid JSON (no markdown, no extra text):
{{
  "mastery": <integer 0-100>,
  "feedback": "<2-3 sentence summary of strengths and gaps>"
}}"""
        reply = _chat([{"role": "user", "content": prompt}], temperature=0.3)
        result = _extract_json(reply)
        mastery = max(0, min(100, int(result.get("mastery", 50))))
        feedback = result.get("feedback", "Assessment complete.")
        return mastery, feedback


# ---------------------------------------------------------------------------
# Curriculum Agent
# ---------------------------------------------------------------------------

class CurriculumAgent:
    """Generates an ordered topic list for a learning goal."""

    def get_topics(
        self,
        goal: str,
        existing_topics: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Returns 5-8 ordered topic name strings."""
        existing_info = ""
        if existing_topics:
            existing_info = "\n\nCurrent learner mastery:\n" + "\n".join(
                f"  - {t['name']}: {t['mastery']}% mastery"
                for t in existing_topics
            )

        prompt = f"""You are a curriculum designer building a personalised learning path.

Learner goal: "{goal}"{existing_info}

Return an ordered JSON array of 5-8 topic name strings a learner should
study to achieve the goal, starting from fundamentals and progressing to
advanced concepts. Prerequisite topics must come before dependent ones.

Return ONLY a JSON array of strings, no markdown, no explanation:
["Topic 1", "Topic 2", ...]"""
        reply = _chat([{"role": "user", "content": prompt}], temperature=0.4)
        topics = _extract_json(reply)
        if not isinstance(topics, list):
            raise ValueError(f"Expected a JSON list, got: {type(topics)}")
        return [str(t) for t in topics]


# ---------------------------------------------------------------------------
# Tutor Agent
# ---------------------------------------------------------------------------

class TutorAgent:
    """Maintains conversation history and chats as an expert tutor."""

    MAX_HISTORY = 10  # max user+assistant pairs kept in context

    def __init__(self, topic: str, mastery: int):
        self.topic = topic
        self.mastery = mastery
        self.history: List[Dict[str, str]] = []  # {"role": "user"|"assistant", "content": "..."}

    def chat(self, user_message: str) -> str:
        """Send a message and return the tutor's reply."""
        messages = self._build_messages(user_message)
        reply = _chat(messages, temperature=0.7)

        # Append to capped history
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": reply})

        return reply

    def reset(self) -> None:
        """Clear conversation history."""
        self.history = []

    # ------------------------------------------------------------------
    def _system_prompt(self) -> str:
        level = (
            "beginner" if self.mastery < 30
            else "intermediate" if self.mastery < 70
            else "advanced"
        )
        return (
            f"You are a friendly, expert tutor helping a learner study '{self.topic}'. "
            f"The learner's mastery is {self.mastery}/100 ({level}). "
            f"For beginners use analogies and step-by-step explanations; "
            f"for advanced learners dive deeper and cover edge cases. "
            f"Keep replies focused, clear, and encouraging."
        )

    def _build_messages(self, user_message: str) -> List[Dict[str, str]]:
        """Build the full message list: system + capped history + new message."""
        # Cap to last MAX_HISTORY exchanges (each exchange = 2 messages)
        capped = self.history[-(self.MAX_HISTORY * 2):]

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": self._system_prompt()}
        ]
        messages.extend(capped)
        messages.append({"role": "user", "content": user_message})
        return messages


# ---------------------------------------------------------------------------
# Progress Agent
# ---------------------------------------------------------------------------

class ProgressAgent:
    """Updates mastery scores using a rolling average of the last 3 quizzes."""

    MASTERY_THRESHOLD = 80

    def update(
        self,
        profile: Dict[str, Any],
        topic_index: int,
        new_score: int,
    ) -> Dict[str, Any]:
        """
        Record *new_score*, recompute mastery as rolling avg of last 3,
        and advance current_topic_index if mastery >= MASTERY_THRESHOLD.
        Returns the mutated profile.
        """
        topic = profile["topics"][topic_index]
        history: List[int] = topic.setdefault("history", [])
        history.append(new_score)

        recent = history[-3:]
        topic["mastery"] = round(sum(recent) / len(recent))

        num_topics = len(profile["topics"])
        if (
            topic["mastery"] >= self.MASTERY_THRESHOLD
            and profile["current_topic_index"] == topic_index
            and topic_index < num_topics - 1
        ):
            profile["current_topic_index"] = topic_index + 1

        return profile
