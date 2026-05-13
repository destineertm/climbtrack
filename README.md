# ClimbTrack

A personal climbing tracker built with Flask. Log sessions, track projects across multiple visits, and monitor your progression over time.

## What it does

ClimbTrack is built around the idea that a single climbing session is just one data point. The app connects your attempts on the same route across different sessions, so you can see how long a project actually took, what your send rate looks like at a given gym, and which grades you are consistently climbing.

Core features:

- **Session logging** - Start a session at a gym or crag, then log every climb within it. Sessions track the date, location, and whether you were indoors or outdoors.
- **Route tracking** - As you type a climb name, the app suggests routes you have logged before. Linking attempts across sessions builds a full history for each route.
- **Project mode** - Flag any route as a project. A dedicated projects page shows your active and completed projects with attempt counts, session counts, and dates.
- **Grade system** - Supports V-scale (bouldering) and YDS (routes). Dropdowns adapt based on whether the session is indoor or outdoor, showing a common range for gym climbing and the full range for outdoor.
- **Stats** - Each session shows a send rate, top grade sent, and a breakdown by result type (send, flash, onsight, attempt). The home dashboard shows the same stats across all time.
- **Gym pages** - Each gym has its own page with a full session history and route list.

## Tech stack

- Python / Flask
- SQLAlchemy (ORM)
- Flask-Migrate / Alembic (database migrations)
- SQLite (local database)
- Plain HTML, CSS, and vanilla JavaScript (no frontend framework)

## Getting started

**Prerequisites:** Python 3.10 or higher

**1. Clone the repo**

```bash
git clone https://github.com/yourusername/climbtrack.git
cd climbtrack
```

**2. Create and activate a virtual environment**

```bash
python -m venv venv

# Mac / Linux
source venv/bin/activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Set up the database**

```bash
flask db upgrade
```

**5. Run the app**

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## Project structure

```
climbtrack/
├── app.py                  # Routes, models, and application logic
├── migrations/             # Alembic migration scripts
├── static/
│   └── style.css           # Stylesheet
├── templates/
│   ├── index.html          # Home dashboard
│   ├── new_session.html    # Start a session
│   ├── session.html        # Session detail
│   ├── add_climb.html      # Log a climb
│   ├── edit_climb.html     # Edit a climb
│   ├── projects.html       # Projects list
│   ├── route_detail.html   # Route history and timeline
│   ├── gyms.html           # Gyms list
│   └── gym_detail.html     # Gym detail
└── README.md
```

## Database migrations

The app uses Flask-Migrate to handle schema changes without losing data. Whenever the models in `app.py` change, run:

```bash
flask db migrate -m "describe the change"
flask db upgrade
```

## Roadmap

This project is being built in phases. The current build covers phases 1 and 2 of the original roadmap.

- Phase 1 - Session logging, quick climb entry, basic stats
- Phase 2 - Route tracking, project mode, per-attempt notes, gym pages
- Phase 3 - Insights: grade progression charts, style breakdown, weakness detection
- Phase 4 - Training intelligence: suggested sessions, plateau detection, weekly plans
- Phase 5 - Media: photo and video per attempt
- Phase 6 - Social: gym activity feed, beta sharing

## Notes

- The app runs locally by default and is not configured for production deployment. Debug mode is on. Turn it off before deploying anywhere public.
- SQLite works well for personal use. If you plan to run this for multiple users, consider switching to PostgreSQL.
- There are no user accounts yet. Everyone who accesses the app shares the same database.

## License

MIT
