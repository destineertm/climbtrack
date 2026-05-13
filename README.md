# ClimbTrack

A personal climbing tracker built with Flask. Log sessions, track projects across multiple visits, analyze your style strengths and weaknesses, and get personalized training recommendations based on your climbing history.

## What it does

ClimbTrack is built around the idea that a single climbing session is just one data point. The app connects your attempts on the same route across different sessions, so you can see how long a project actually took, what your send rate looks like at a given gym, and which grades you are consistently climbing.

### Core features

**Session logging**
Start a session at a gym or crag, then log every climb within it. Sessions track the date, location, session type (indoor or outdoor), and optional notes.

**Route tracking**
As you type a climb name, the app suggests routes you have logged before. Linking attempts across sessions builds a full history for each route, including a timeline of every attempt with results and notes.

**Project mode**
Flag any route as a project. A dedicated projects page shows your active and completed projects with attempt counts, session counts, and dates worked.

**Grade system**
Supports V-scale (bouldering) and YDS (sport routes). Dropdowns adapt based on whether the session is indoor or outdoor, showing a common range for gym climbing and the full range for outdoor.

**Style tags**
Tag each climb with one or more styles: crimp, slab, overhang, pinch, dyno, compression, crack, mantle, jump, coordination, power, endurance. Tags feed into the insights and training pages.

**Gym pages**
Each gym is a first-class entity with its own page, session history, route list, style breakdown chart, and optional cover photo.

**Insights**
Grade progression charts, send rate by grade, style breakdown (sends vs attempts per tag), and most worked routes — all visualized with Chart.js.

**Training intelligence**
Personalized recommendations based on your history: plateau detection (all-time peak vs recent sends), weakness detection by style tag, fatigue signals based on session frequency, and a suggested 7-day training plan. Requires 10 or more sessions to activate.

## Tech stack

- Python / Flask
- SQLAlchemy (ORM)
- Flask-Migrate / Alembic (database migrations)
- SQLite (local database)
- Chart.js (grade progression and style breakdown charts)
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
├── app.py                    # Routes, models, and application logic
├── migrations/               # Alembic migration scripts
├── static/
│   ├── style.css             # Stylesheet
│   └── uploads/              # Uploaded cover photos (auto-created)
├── templates/
│   ├── index.html            # Home dashboard
│   ├── new_session.html      # Start a session
│   ├── session.html          # Session detail
│   ├── add_climb.html        # Log a climb
│   ├── edit_climb.html       # Edit a climb
│   ├── projects.html         # Projects list
│   ├── route_detail.html     # Route history and timeline
│   ├── edit_route.html       # Edit a route + cover photo
│   ├── gyms.html             # Gyms list
│   ├── gym_detail.html       # Gym detail with stats and style chart
│   ├── edit_gym.html         # Edit a gym + cover photo
│   ├── insights.html         # Charts and data visualization
│   └── training.html         # Training recommendations and weekly plan
├── backfill_gyms.py          # One-off: migrate location strings to Gym rows
├── backfill_climb_routes.py  # One-off: link existing climbs to routes by name
├── merge_gyms.py             # One-off: merge duplicate gym entries
├── seed_data.py              # Development: generate realistic fake data
└── README.md
```

## Database migrations

The app uses Flask-Migrate to handle schema changes without losing data. When models in `app.py` change, run:

```powershell
$env:FLASK_APP = "app.py"
python -m flask db migrate -m "describe the change"
python -m flask db upgrade
```

**SQLite note:** when adding foreign keys to existing tables, open the generated migration file and replace any `create_foreign_key(None, ...)` calls with a named string (e.g. `'fk_climb_route_id'`). SQLite requires named constraints in batch mode.

## Seeding test data

To populate the app with realistic fake data for testing:

```bash
python seed_data.py
```

This generates roughly 60-80 sessions, 28 routes, and 400-500 climbs across 3 gyms spanning 6 months. Safe to run alongside existing data.

To clear seeded data and start fresh, delete `instance/climbs.db` and run `flask db upgrade`.

## Roadmap

- Phase 1 - Session logging, quick climb entry, basic stats
- Phase 2 - Route tracking, project mode, per-attempt notes, gym pages
- Phase 3 - Insights: grade progression charts, style breakdown, send rate analysis
- Phase 4 - Training intelligence: plateau detection, weakness analysis, weekly plan
- Phase 5 - Media: photo and video per attempt (upcoming)
- Phase 6 - Social: gym activity feed, beta sharing
- Phase 7 - Route intelligence: style fingerprinting, similar climb recommendations
- Phase 8 - Long-term climber identity: multi-year progression, climber profile

## Notes

- The app runs locally by default. Debug mode is on — turn it off before deploying anywhere public.
- SQLite works well for personal use. For multiple concurrent users, switch to PostgreSQL.
- There are no user accounts yet. Everyone who accesses the app shares the same database.
- Uploaded images are stored in `static/uploads/`. Back this folder up separately if you care about preserving cover photos.

## License

MIT
