"""
ClimbTrack — Data Seeder

Generates realistic fake climbing data for testing and development.
Creates sessions, climbs, routes, and projects spanning several months.

Usage:
    python seed_data.py

WARNING: This adds data to your existing database. It does NOT wipe
existing data first. Run once, or run multiple times if you want more.

To clear all seeded data, delete climbs.db and run flask db upgrade.
"""

import random
from datetime import datetime, timedelta
from app import app, db, Gym, Session, Route, Climb, find_or_create_gym

# ── Config ──────────────────────────────────────────────────────────────────

GYMS = [
    {"name": "Climb Bentonville", "is_outdoor": False},
    {"name": "Fitz", "is_outdoor": True},
    {"name": "The Spot", "is_outdoor": False},
]

BOULDER_GRADES = ["VB", "V0", "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"]
ROUTE_GRADES = [
    "5.6", "5.7", "5.8", "5.9",
    "5.10a", "5.10b", "5.10c", "5.10d",
    "5.11a", "5.11b", "5.11c", "5.11d",
    "5.12a", "5.12b",
]

STYLE_TAGS = [
    "crimp", "slab", "overhang", "pinch", "dyno",
    "compression", "crack", "mantle", "jump",
    "coordination", "power", "endurance",
]

RESULT_WEIGHTS = {
    "attempt": 0.45,
    "send":    0.35,
    "flash":   0.12,
    "onsight": 0.08,
}

ROUTE_NAMES_BOULDER = [
    "Crimpy Crusher", "The Mantle Problem", "Slopers Anonymous",
    "Deadpoint Direct", "Heel Hook Heaven", "Pocket Rocket",
    "The Compression Test", "Volume Control", "Dyno Dave",
    "Pinch Perfect", "Slabmaster General", "The Overhang",
    "Power Endurance", "Coordination Station", "Flash Dance",
    "The Warm-Up", "Project Fear", "Beta Spray",
    "Campus Problem", "Footwork 101",
]

ROUTE_NAMES_ROUTE = [
    "Thin Air", "Finger Crack", "The Long Haul", "Sustained Suffering",
    "Crimpy Arête", "Power Enduro", "Technical Slab", "The Jugfest",
    "Redpoint Ready", "Flash Machine", "Onsight Special",
    "The Warmup Route", "Endurance Test", "Campus Crack",
    "Pumpy McPumpface", "Layback Attack", "Stemming for Days",
    "Rest Step", "Clip and Go", "Power Scream",
]

SESSION_NOTES = [
    "Feeling strong today", "A bit tired from yesterday",
    "Great session, everything clicking", "Skin hurts but worth it",
    "Cold temps made crimps feel amazing", "Humid — holds felt greasy",
    "Rest day turned into a session", "Tried some new problems",
    "Projecting hard today", "Easy session, just moving",
    "", "", "",  # Empty notes are realistic too
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def weighted_result():
    r = random.random()
    cumulative = 0
    for result, weight in RESULT_WEIGHTS.items():
        cumulative += weight
        if r < cumulative:
            return result
    return "attempt"


def random_tags(n=None):
    if n is None:
        n = random.randint(0, 3)
    return random.sample(STYLE_TAGS, min(n, len(STYLE_TAGS)))


def random_date_in_range(start, end):
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))


# ── Seeder ───────────────────────────────────────────────────────────────────

def seed():
    with app.app_context():

        # Date range: last 6 months
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=180)

        print("Creating gyms...")
        gyms = []
        for g in GYMS:
            gym = find_or_create_gym(g["name"], is_outdoor=g["is_outdoor"])
            gyms.append(gym)
        db.session.commit()

        # Pre-create a pool of routes per gym
        print("Creating routes...")
        gym_routes = {}
        for gym in gyms:
            routes = []

            # Boulder routes
            boulder_names = random.sample(ROUTE_NAMES_BOULDER, min(10, len(ROUTE_NAMES_BOULDER)))
            for name in boulder_names:
                grade = random.choice(BOULDER_GRADES)
                existing = Route.query.filter_by(name=name, gym_id=gym.id, discipline='boulder').first()
                if not existing:
                    r = Route(
                        name=name,
                        gym_id=gym.id,
                        location=gym.name,
                        discipline='boulder',
                        grade=grade,
                        is_project=random.random() < 0.2,
                    )
                    db.session.add(r)
                    routes.append(r)
                else:
                    routes.append(existing)

            # Sport routes (only indoor gyms)
            if not gym.is_outdoor:
                route_names = random.sample(ROUTE_NAMES_ROUTE, min(8, len(ROUTE_NAMES_ROUTE)))
                for name in route_names:
                    grade = random.choice(ROUTE_GRADES)
                    existing = Route.query.filter_by(name=name, gym_id=gym.id, discipline='route').first()
                    if not existing:
                        r = Route(
                            name=name,
                            gym_id=gym.id,
                            location=gym.name,
                            discipline='route',
                            grade=grade,
                            is_project=random.random() < 0.15,
                        )
                        db.session.add(r)
                        routes.append(r)
                    else:
                        routes.append(existing)

            db.session.flush()
            gym_routes[gym.id] = routes

        db.session.commit()

        # Generate sessions
        print("Creating sessions and climbs...")
        total_sessions = 0
        total_climbs = 0

        # ~3 sessions per week over 6 months = ~72 sessions
        session_dates = sorted([
            random_date_in_range(start_date, end_date)
            for _ in range(random.randint(55, 80))
        ])

        for session_date in session_dates:
            gym = random.choice(gyms)
            session_type = 'outdoor' if gym.is_outdoor else 'indoor'

            s = Session(
                date=session_date,
                gym_id=gym.id,
                location=gym.name,
                session_type=session_type,
                notes=random.choice(SESSION_NOTES),
            )
            db.session.add(s)
            db.session.flush()

            # 4-12 climbs per session
            routes_this_session = random.sample(
                gym_routes[gym.id],
                min(random.randint(4, 12), len(gym_routes[gym.id]))
            )

            for route in routes_this_session:
                result = weighted_result()

                # More attempts on projects
                if route.is_project:
                    attempts = random.randint(2, 8)
                    # Projects are harder to send
                    if result in ('flash', 'onsight'):
                        result = random.choice(['attempt', 'send'])
                else:
                    attempts = random.randint(1, 4)

                tags = random_tags()

                c = Climb(
                    session_id=s.id,
                    route_id=route.id,
                    climb_name=route.name,
                    discipline=route.discipline,
                    grade=route.grade,
                    attempts=attempts,
                    result=result,
                    style_tags=','.join(tags) if tags else None,
                )
                db.session.add(c)
                total_climbs += 1

            total_sessions += 1

        db.session.commit()

        print()
        print(f"Seeded:")
        print(f"  {len(gyms)} gym(s)")
        print(f"  {sum(len(r) for r in gym_routes.values())} route(s)")
        print(f"  {total_sessions} session(s)")
        print(f"  {total_climbs} climb(s)")
        print()
        print("Done! Start the app and check /insights.")


if __name__ == "__main__":
    seed()