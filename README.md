# ClimbTrack

> "Just one more attempt." — every climber, forever.

A personal climbing tracker built with Flask. Log sessions, track projects, analyze your style, and get personalized training recommendations — all in a clean, mobile-friendly interface.

---

## Why does this exist?

Because spreadsheets are for accountants, not climbers. And because "I think I've tried this one before" is not a training strategy.

![Climber meme](https://www.active-traveller.com/images/mpora-archive/best-rock-climbing-memes-1.jpg)

> *You, logging your 47th attempt on the same V6: "I'm basically a different person than when I started this project."*

---

## What it does

ClimbTrack turns your climbing attempts into progression intelligence. It connects attempts on the same route across different sessions, so you can see how long a project actually took, where your grade ceiling is, and what styles you need to work on.

### Core features

**Session logging**
Start a session at a gym or crag and log every climb within it. Sessions track date, location, type (indoor or outdoor), and notes. The gym picker remembers your locations and suggests them as you type.

**Route tracking**
As you type a climb name, the app suggests routes you have logged before — across all gyms. Linking attempts across sessions builds a full history per route, including a timeline of every attempt with results, notes, photos, and video.

**Project mode**
Flag any route as a project. A dedicated projects page shows active and completed projects with attempt counts, session counts, and dates worked. Sent projects get a visual distinction from active ones.

**Grade system**
Supports V-scale (bouldering) and YDS (sport routes). Grade dropdowns adapt based on session type — common range for indoor, full range for outdoor.

**Style tags**
Tag each climb with styles: crimp, slab, overhang, pinch, dyno, compression, crack, mantle, jump, coordination, power, endurance. Tags feed into insights and training recommendations.

**Media**
Attach a photo or YouTube/Vimeo video link to each climb attempt. Photos and embedded videos appear on the route detail timeline and story mode.

**Story mode**
Every route has a story mode view — a cinematic, chapter-by-chapter history of your attempts, newest first, with photos and video inline.

**Gym pages**
Each gym is a first-class entity with its own page, session history, route list, style breakdown chart, and optional cover photo. Routes can have cover photos too.

**Insights**
Grade progression charts, send rate by grade, style breakdown (sends vs attempts per tag), and most worked routes — all visualized with Chart.js. Charts sit side by side on desktop.

**Training intelligence**
Personalized recommendations based on your history: plateau detection (all-time peak vs recent sends), weakness detection by style tag, fatigue signals from session frequency, and a suggested 7-day training plan. Requires 10+ sessions to activate.

**Climb of the Month**
The home dashboard highlights your best send of the month — scored by grade difficulty, result type (onsight > flash > send), and attempt count.

**User accounts**
Register and log in with email, password, and a display name. All routes protected behind login. Data is currently shared across all users (social-first design).

**Responsive design**
Mobile: bottom navigation bar with a large center Log button. Desktop: fixed top nav with logo, centered links, and a Log Climb CTA. Cards stack on mobile and go side by side on desktop.

## Tech stack

- Python / Flask
- SQLAlchemy (ORM)
- Flask-Login (authentication)
- Flask-Migrate / Alembic (database migrations)
- SQLite (local) / PostgreSQL (production)
- Chart.js (data visualization)
- Vanilla HTML, CSS, JavaScript — no frontend framework

## Getting started

> "Works on my machine." — this README, probably.

**Prerequisites:** Python 3.10+

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

```powershell
$env:FLASK_APP = "app.py"
python -m flask db upgrade
```

**5. Run the app**

```bash
python app.py
```

Open `http://127.0.0.1:5000` and register an account.

## Project structure

```
climbtrack/
├── app.py                       # Routes, models, application logic
├── migrations/                  # Alembic migration scripts
├── static/
│   ├── style.css                # Stylesheet
│   └── uploads/                 # Uploaded photos (auto-created)
├── templates/
│   ├── index.html               # Home dashboard
│   ├── login.html               # Login (split-screen with climbing photo)
│   ├── register.html            # Register
│   ├── new_session.html         # Start a session (gym combobox)
│   ├── session.html             # Session detail
│   ├── add_climb.html           # Log a climb (autocomplete + style tags)
│   ├── edit_climb.html          # Edit a climb
│   ├── projects.html            # Projects list
│   ├── route_detail.html        # Route history and timeline
│   ├── route_story.html         # Story mode (cinematic attempt history)
│   ├── edit_route.html          # Edit route + cover photo
│   ├── gyms.html                # Gyms list (photo cards)
│   ├── gym_detail.html          # Gym detail with stats and style chart
│   ├── edit_gym.html            # Edit gym + cover photo
│   ├── insights.html            # Charts and data visualization
│   └── training.html            # Training recommendations and weekly plan
├── backfill_gyms.py             # One-off: migrate location strings to Gym rows
├── backfill_climb_routes.py     # One-off: link existing climbs to routes by name
├── merge_gyms.py                # One-off: merge duplicate gym entries
├── seed_data.py                 # Dev: generate realistic fake climbing data
├── check_db.py                  # Dev: inspect database tables
└── README.md
```

## Database migrations

Uses Flask-Migrate for safe schema changes. When models in `app.py` change:

```powershell
$env:FLASK_APP = "app.py"
python -m flask db migrate -m "describe the change"
python -m flask db upgrade
```

**SQLite note:** when adding foreign keys to existing tables, open the generated migration file and replace any `create_foreign_key(None, ...)` with a named string (e.g. `'fk_climb_route_id'`). SQLite requires named constraints in batch mode.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-secret-change-in-production` | Flask session secret — change before deploying |

## Seeding test data

> "I need data to test the insights page." — you, about to lie to yourself about sending V10.

```bash
python seed_data.py
```

Generates ~60-80 sessions, 28 routes, and 400-500 climbs across 3 gyms spanning 6 months. Safe to run alongside existing data.

## Roadmap

> "It's not scope creep if you're having fun." — this project

- Phase 1 — Session logging, climb entry, basic stats ✅
- Phase 2 — Route tracking, project mode, notes, gym pages ✅
- Phase 3 — Insights: grade progression, style breakdown, send rate analysis ✅
- Phase 4 — Training intelligence: plateau detection, weakness analysis, weekly plan ✅
- Phase 5 — Media: photo and video per attempt, story mode ✅
- Phase 6 — Social: gym activity feed, beta sharing *(coming soon™)*
- Phase 7 — Route intelligence: style fingerprinting, similar climb recommendations *(eventually™)*
- Phase 8 — Long-term climber identity: multi-year progression, climber profile *(when we stop adding features™)*

## Deployment notes

> "It works locally" is not a deployment strategy.

- Set `SECRET_KEY` to a real secret in production
- Turn off `debug=True` in `app.run()`
- Switch from SQLite to PostgreSQL for multi-user production use
- Back up `static/uploads/` separately — it contains user-uploaded photos

## License

MIT

---

*Built by a climber who got tired of forgetting which problems they've tried. If this helps you send your project, we accept thank-you notes in the form of beta.*

> "The best climbing app is the one you actually use." — probably someone wise
