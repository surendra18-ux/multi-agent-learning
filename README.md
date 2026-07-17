# 🎓 AI Learning Coach — Multi-Agent Personalized Learning System

A minimal, terminal-runnable multi-agent AI system that creates a personalised
learning experience powered by Google Gemini.

---

## ✨ Features

| Agent | Role |
|---|---|
| **Assessment Agent** | Generates diagnostic questions and scores your answers (mastery 0–100) |
| **Curriculum Agent** | Builds an ordered topic list tailored to your goal |
| **Tutor Agent** | Runs a live chat session for the current topic, adapting to your mastery level |
| **Progress Agent** | Updates mastery scores (rolling average of last 3 quizzes) and advances topics |

---

## 🔑 Get a Gemini API Key

1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click **Create API key**
4. Copy the key — you'll need it in the next step

---

## 🚀 Quick Start

```bash
# 1. Clone / download this project, then cd into it
cd MULTI-AGENT-LEARNING

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your .env file
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux

# 4. Open .env and paste your key
#    GEMINI_API_KEY=AIza...

# 5. Run the app
streamlit run app.py
```

The app will open at **http://localhost:8501** in your browser.

---

## 📁 File Structure

```
MULTI-AGENT-LEARNING/
├── app.py              # Streamlit UI + orchestration
├── agents.py           # AssessmentAgent, CurriculumAgent, TutorAgent, ProgressAgent
├── storage.py          # load/save learner_data.json
├── learner_data.json   # auto-created on first run
├── .env                # your Gemini API key (create from .env.example)
├── .env.example        # template
├── requirements.txt
└── README.md
```

---

## 🔄 App Flow

```
Start
  │
  ├─ First visit → Enter name + learning goal
  │                   │
  │                   └─ Curriculum Agent builds topic list
  │
  ├─ No mastery yet? → Assessment Agent: diagnostic quiz
  │                         │
  │                         └─ Progress Agent stores score
  │
  ├─ Main panel: Tutor Agent chat (adapts to your mastery level)
  │
  └─ Sidebar "Quiz me" → Assessment Agent → Progress Agent
                              │
                              └─ If mastery ≥ 80 → advance to next topic 🎉
```

---

## ⚙️ Configuration

| Setting | Where | Default |
|---|---|---|
| Model | `agents.py` → `_MODEL_NAME` | `gemini-2.5-flash` |
| Mastery threshold to advance | `agents.py` → `ProgressAgent.MASTERY_THRESHOLD` | `80` |
| Max chat history sent to Gemini | `agents.py` → `TutorAgent.MAX_HISTORY` | `10 exchanges` |
| Data file location | `storage.py` → `DATA_FILE` | `learner_data.json` |

---

## 🛟 Troubleshooting

**`❌ GEMINI_API_KEY is not set`** — Make sure `.env` exists and contains your key.

**`❌ Could not build curriculum`** — Check your internet connection and that your API key is valid.

**App resets unexpectedly** — Streamlit reruns on every interaction; all state is kept in `st.session_state`.
