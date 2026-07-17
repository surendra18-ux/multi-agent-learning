"""
app.py — Streamlit orchestration layer for the multi-agent learning system.

Flow:
  1. Sidebar: enter/load learner profile
  2. If topics have no mastery data → Assessment Agent flow
  3. Curriculum Agent → sidebar topic list with progress bars
  4. Main panel → Tutor Agent chat
  5. "Quiz me" sidebar button → Assessment Agent → Progress Agent update
"""

from __future__ import annotations

import os
from typing import Any, Dict

import streamlit as st
from dotenv import load_dotenv

from agents import AssessmentAgent, CurriculumAgent, ProgressAgent, TutorAgent
from storage import load_profile, profile_exists, reset_profile, save_profile

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Learning Coach",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_dotenv()

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Dark gradient background */
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        color: #e8e8f0;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(255,255,255,0.1);
    }

    /* Cards */
    .card {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 16px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1rem;
    }

    /* Chat bubbles */
    [data-testid="stChatMessage"] {
        background: rgba(255,255,255,0.06) !important;
        border-radius: 12px !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        margin-bottom: 0.5rem !important;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 1.2rem;
        font-weight: 600;
        transition: transform 0.15s, box-shadow 0.15s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102,126,234,0.4);
    }

    /* Topic badge */
    .topic-done   { color: #4ade80; font-weight: 600; }
    .topic-active { color: #fbbf24; font-weight: 700; }
    .topic-todo   { color: #9ca3af; }

    /* Header */
    .hero-title {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #a78bfa, #60a5fa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* Progress bar override */
    .stProgress > div > div { background: linear-gradient(90deg, #667eea, #764ba2); }

    /* Input */
    .stTextInput > div > div > input,
    .stTextArea textarea {
        background: rgba(255,255,255,0.08) !important;
        color: #e8e8f0 !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 10px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session-state helpers
# ---------------------------------------------------------------------------

def _init_session():
    """Initialise all session-state keys we rely on."""
    ss = st.session_state
    ss.setdefault("profile", None)          # learner profile dict
    ss.setdefault("tutor", None)            # TutorAgent instance
    ss.setdefault("chat_history", [])       # displayed chat messages
    ss.setdefault("assessment_qs", None)    # generated question dicts
    ss.setdefault("assessment_submitted", False)
    ss.setdefault("assessment_feedback", "")
    ss.setdefault("quiz_mode", False)       # sidebar quiz trigger
    ss.setdefault("setup_done", False)      # has the profile been set up?


_init_session()

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _current_topic(profile: Dict[str, Any]) -> Dict[str, Any]:
    idx = profile["current_topic_index"]
    return profile["topics"][idx]


def _ensure_tutor(profile: Dict[str, Any]):
    """Create or recreate TutorAgent when topic changes."""
    topic = _current_topic(profile)
    ss = st.session_state
    if ss.tutor is None or ss.tutor.topic != topic["name"]:
        ss.tutor = TutorAgent(topic["name"], topic["mastery"])
        ss.chat_history = []


# ---------------------------------------------------------------------------
# Sidebar — profile setup
# ---------------------------------------------------------------------------

def _sidebar_setup():
    ss = st.session_state
    with st.sidebar:
        st.markdown("## 🎓 AI Learning Coach")
        st.markdown("---")

        if not ss.setup_done:
            st.markdown("### 👋 Welcome! Let's set up your profile")
            with st.form("setup_form"):
                name = st.text_input("Your name", placeholder="e.g. Alex")
                goal = st.text_input(
                    "What do you want to learn?",
                    placeholder="e.g. Machine Learning fundamentals",
                )
                load_existing = profile_exists()
                col1, col2 = st.columns(2)
                submitted = col1.form_submit_button("🚀 Start")
                load_btn = col2.form_submit_button("📂 Load saved") if load_existing else False

            if submitted and name and goal:
                _create_new_profile(name, goal)
            elif load_btn and load_existing:
                ss.profile = load_profile()
                ss.setup_done = True
                st.rerun()
            elif submitted and (not name or not goal):
                st.warning("Please fill in both fields.")
        else:
            _sidebar_progress()


def _create_new_profile(name: str, goal: str):
    ss = st.session_state
    with st.spinner("🤖 Building your curriculum…"):
        try:
            agent = CurriculumAgent()
            topic_names = agent.get_topics(goal)
            profile = {
                "learner_id": name,
                "goal": goal,
                "topics": [
                    {"name": t, "mastery": 0, "history": []}
                    for t in topic_names
                ],
                "current_topic_index": 0,
            }
            save_profile(profile)
            ss.profile = profile
            ss.setup_done = True
            st.rerun()
        except Exception as exc:
            st.error(f"❌ Could not build curriculum: {exc}")


def _sidebar_progress():
    ss = st.session_state
    profile = ss.profile
    st.markdown(f"### 👤 {profile['learner_id']}")
    st.markdown(f"**Goal:** {profile['goal']}")
    st.markdown("---")

    st.markdown("### 📚 Your Learning Path")
    idx = profile["current_topic_index"]
    for i, topic in enumerate(profile["topics"]):
        m = topic["mastery"]
        if i < idx:
            label = f"✅ {topic['name']}"
            css = "topic-done"
        elif i == idx:
            label = f"▶ {topic['name']}"
            css = "topic-active"
        else:
            label = f"○ {topic['name']}"
            css = "topic-todo"
        st.markdown(f'<span class="{css}">{label}</span>', unsafe_allow_html=True)
        st.progress(m / 100, text=f"{m}%")

    st.markdown("---")

    # Quiz me button
    if st.button("🧠 Quiz me on current topic", key="quiz_btn"):
        ss.quiz_mode = True
        ss.assessment_qs = None
        ss.assessment_submitted = False
        st.rerun()

    # Reset button
    if st.button("🔄 Start over", key="reset_btn"):
        reset_profile()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ---------------------------------------------------------------------------
# Assessment flow
# ---------------------------------------------------------------------------

def _run_assessment(profile: Dict[str, Any], topic_index: int, quiz_mode: bool = False):
    ss = st.session_state
    topic = profile["topics"][topic_index]
    topic_name = topic["name"]

    header = "🧠 Quiz: " if quiz_mode else "📋 Initial Assessment: "
    st.markdown(f'<div class="hero-title">{header}{topic_name}</div>', unsafe_allow_html=True)
    st.markdown("Answer the questions below so I can personalise your learning path.")
    st.markdown("---")

    # Generate questions once
    if ss.assessment_qs is None:
        with st.spinner("✨ Generating personalised questions…"):
            try:
                agent = AssessmentAgent()
                ss.assessment_qs = agent.generate_questions(topic_name)
            except Exception as exc:
                st.error(f"❌ Could not generate questions: {exc}")
                return

    questions = ss.assessment_qs

    if not ss.assessment_submitted:
        with st.form("assessment_form"):
            for i, q in enumerate(questions):
                st.markdown(f"**Q{i+1}. {q['question']}**")
                if q.get("type") == "mcq" and q.get("options"):
                    st.radio(
                        label="",
                        options=q["options"],
                        key=f"assess_q_{i}",
                        label_visibility="collapsed",
                    )
                else:
                    st.text_area(
                        label="",
                        key=f"assess_q_{i}",
                        placeholder="Type your answer here…",
                        label_visibility="collapsed",
                    )
                st.markdown("")

            submitted = st.form_submit_button("✅ Submit answers")

        if submitted:
            # Read answers from session_state using the widget keys
            answers = [
                str(st.session_state.get(f"assess_q_{i}", ""))
                for i in range(len(questions))
            ]
            with st.spinner("🤖 Scoring your answers…"):
                try:
                    agent = AssessmentAgent()
                    mastery, feedback = agent.score_answers(topic_name, questions, answers)

                    # Update via Progress Agent
                    progress_agent = ProgressAgent()
                    profile = progress_agent.update(profile, topic_index, mastery)
                    save_profile(profile)
                    ss.profile = profile
                    ss.assessment_submitted = True
                    ss.assessment_feedback = feedback
                    ss.quiz_mode = False
                    st.rerun()
                except Exception as exc:
                    st.error(f"❌ Scoring failed: {exc}")
    else:
        # Show result
        topic_mastery = profile["topics"][topic_index]["mastery"]
        st.success(f"✅ Assessment complete — Mastery: **{topic_mastery}%**")
        st.info(ss.assessment_feedback)

        if topic_mastery >= ProgressAgent.MASTERY_THRESHOLD:
            new_idx = profile["current_topic_index"]
            new_topic = profile["topics"][new_idx]["name"]
            st.balloons()
            st.success(f"🎉 Topic mastered! Moving on to **{new_topic}**")

        if st.button("📖 Start tutoring session", key="goto_tutor"):
            ss.assessment_submitted = False
            ss.assessment_qs = None
            ss.quiz_mode = False
            st.rerun()


# ---------------------------------------------------------------------------
# Tutor chat
# ---------------------------------------------------------------------------

def _run_tutor(profile: Dict[str, Any]):
    ss = st.session_state
    topic = _current_topic(profile)
    _ensure_tutor(profile)

    st.markdown(
        f'<div class="hero-title">📖 Tutor: {topic["name"]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="card">Mastery: <strong>{topic["mastery"]}%</strong> &nbsp;|&nbsp; '
        f'Topic {profile["current_topic_index"]+1} of {len(profile["topics"])}</div>',
        unsafe_allow_html=True,
    )

    # Render chat history
    for msg in ss.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Intro message if history empty
    if not ss.chat_history:
        with st.chat_message("assistant"):
            intro = (
                f"Hi {profile['learner_id']}! I'm your tutor for **{topic['name']}**. "
                f"Ask me anything — explanations, examples, practice problems — I'm here to help! 🚀"
            )
            st.markdown(intro)

    # Chat input
    user_input = st.chat_input(
        placeholder=f"Ask about {topic['name']}…",
        disabled=False,
        key="chat_input",
    )

    if user_input:
        ss.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("🤖 Thinking…"):
                try:
                    reply = ss.tutor.chat(user_input)
                    st.markdown(reply)
                    ss.chat_history.append({"role": "assistant", "content": reply})
                except Exception as exc:
                    st.error(f"❌ Tutor error: {exc}")


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main():
    ss = st.session_state
    _sidebar_setup()

    if not ss.setup_done or ss.profile is None:
        # Landing / setup screen
        st.markdown(
            """
            <div style="text-align:center; padding: 4rem 2rem;">
              <div class="hero-title" style="font-size:3rem;">🎓 AI Learning Coach</div>
              <p style="font-size:1.2rem; color:#9ca3af; margin-top:1rem;">
                A personalised, multi-agent AI system that adapts to <em>you</em>.<br>
                Fill in your profile on the left to get started.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    profile = ss.profile
    idx = profile["current_topic_index"]
    topic = profile["topics"][idx]

    # ── Decide what to show in the main panel ─────────────────────────────

    if ss.quiz_mode:
        # Sidebar quiz triggered
        _run_assessment(profile, idx, quiz_mode=True)
        return

    needs_initial_assessment = topic["mastery"] == 0 and not topic.get("history")
    if needs_initial_assessment and not ss.assessment_submitted:
        _run_assessment(profile, idx, quiz_mode=False)
        return

    if ss.assessment_submitted and not ss.quiz_mode:
        # Show result then fall through to tutor on next rerun
        _run_assessment(profile, idx, quiz_mode=False)
        return

    _run_tutor(profile)


if __name__ == "__main__":
    main()
