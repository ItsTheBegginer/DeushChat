# Deutschfreund 🇩🇪

A local, offline-capable German practice partner built for one student preparing to move to Germany. It runs entirely on your own laptop — no subscription, no cloud, no data leaving your machine.

The AI is powered by [Ollama](https://ollama.com) running a small open-weight Gemma model, so it works without an internet connection once set up.

---

## Prerequisites

- macOS (tested on macOS 13+)
- Python 3.11 or newer
- ~2 GB of free disk space for the Gemma model

---

## Install steps

### 1. Install Ollama and pull the model

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start the Ollama server in the background
ollama serve &

# Download the model (~1.6 GB — only needed once)
ollama pull gemma2:2b
```

### 2. Get the project

```bash
# Unzip or clone into a folder of your choice, then enter it
cd /path/to/Deushchat
```

### 3. Install Python dependencies

```bash
pip3 install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

The app opens in your browser at `http://localhost:8501`. On the first run you will see a short onboarding form — fill it in once and you go straight to the practice screens on every subsequent launch.

---

## Pages overview

- **Home / Onboarding** — set your name, level (A0–B1), city, and learning goal once; afterwards shows a dashboard of cards due today.
- **Scenarios** — pick a real-life situation (bank, visa office, supermarket, …), chat with an AI character in German, and see corrections after each message.
- **Mistake Deck** — spaced-repetition flashcard review of every correction saved from your chat sessions, plus an error-pattern dashboard.
- **Words from Life** — paste any German word or phrase you encountered in the wild; get the meaning, gender, and an example sentence, then save it to your deck automatically.

---

## Troubleshooting

**"Ollama is not running" error in the app**

The app shows this message when it cannot reach the Ollama server. Fix:

```bash
ollama serve
```

Leave that terminal window open (or run it in the background with `ollama serve &`). Refresh the browser tab and try again.

**Database location**

The SQLite database is stored at `~/.deutschfreund/deutschfreund.db`. To reset all progress, delete that file and restart the app.

**Model is slow**

`gemma2:2b` is the fastest option for most laptops. If responses still feel slow, make sure no other GPU-intensive applications are running alongside the app.
