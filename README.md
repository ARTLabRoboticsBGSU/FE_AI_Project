# FE-AI — Falcon Engineering AI

This repository contains the FE-AI (Falcon Engineering AI) project tailored for Bowling Green State University's School of Engineering. The README below focuses the project documentation on the FE-AI instructional deployment used in the ECE and ROBO courses at BGSU.

## Purpose

FE-AI provides an instructor-facing analytics dashboard and student-facing AI assistant tailored for three undergraduate courses:

- ECE (Electrical & Computer Engineering topics as taught in the course context)
- ROBO (Robotics and automation course topics)
- SYE (Systems Engineering and Engineering Management course topics)

The system is designed for classroom use: it helps instructors monitor misconceptions, difficulty across topics, and Bloom-level distributions while providing students with guided AI interactions and study aids.

## What’s Included

- Streamlit-based web app with instructor analytics pages and student modules
- Topic difficulty heatmap, misconception/error patterns, Bloom distributions, at-risk student lists
- Local RAG retrieval with TF‑IDF fallback for offline resilience
- Optional local Ollama integration if a compatible model is available
- Scripts to refresh analytics: `scripts/compute_counts.py`, `scripts/compute_topic_difficulty.py`, `scripts/compute_errors.py`

## Quick Start (development)

1. Create and activate your Python environment (recommended: venv or conda)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the app locally

```bash
streamlit run chatgpt.py
```

3. Open a browser to `http://localhost:8501` and choose the Instructor Dashboard to access course analytics.

## Course Configuration

- Default course selection is persisted in session state; switch between `ECE`, `ROBO`, and `SYE` using the course radio control on the Instructor Dashboard.
- Topic and subtopic lists are defined in `lib/home_views.py` — update those mappings if your syllabus differs from the defaults.

## Data & Privacy

FE-AI is intended for classroom analytics and respects student privacy guidelines. Interaction logs are stored in `data/sessions.json` and `logs/activity_log.json`. Before using the system in a live course, confirm institutional policies and obtain any necessary approvals.

## Maintenance Notes

- The app includes an HTTP guard that blocks outbound HTTP by default and can be configured to allow a local Ollama daemon for on-prem embeddings.
- If you need offline vector retrieval, ensure `scikit-learn` is available for the TF‑IDF fallback.

### Locking exact environment from an existing `.venv`

If you already have a `.venv` with all required packages installed and want to produce an exact `requirements.txt` from it, run:

```bash
# activate the same virtualenv used for development
source .venv/bin/activate
pip freeze --exclude-editable > requirements.txt
```

This will overwrite `requirements.txt` with exact package versions from `.venv`. Commit the updated file if you want reproducible installs.

## Authors & Contact

Maintained by Instructor / Course Team — contact course administrators for deployment help.

## License

This project is distributed under the MIT License. See the `LICENSE` file for details.

---

If you'd like, I can further tailor the README with course-specific syllabus links, instructor names, or local deployment notes for your environment (SSL, service user, or Windows service instructions).
</div>
