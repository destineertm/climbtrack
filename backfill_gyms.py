"""
One-off backfill script.

Reads all existing Session.location and Route.location strings,
creates a Gym row for each unique location, then links every
Session and Route to the matching Gym.

Run this ONCE after the Gym schema migration. Safe to re-run
(it skips rows that already have a gym_id).

Usage:
    python backfill_gyms.py
"""

from app import app, db, Gym, Session, Route


def normalize(name):
    """Lowercase + strip so 'Movement' == ' movement '."""
    return (name or "").strip().lower()


def backfill():
    with app.app_context():
        # Build a map of normalized name -> Gym
        gyms_by_key = {normalize(g.name): g for g in Gym.query.all()}

        # Gather unique locations from sessions + routes
        all_locations = set()
        for s in Session.query.all():
            if s.location:
                all_locations.add(s.location.strip())
        for r in Route.query.all():
            if r.location:
                all_locations.add(r.location.strip())

        # Create Gym rows for any not already represented
        created = 0
        for loc in all_locations:
            key = normalize(loc)
            if key not in gyms_by_key:
                gym = Gym(name=loc)
                db.session.add(gym)
                db.session.flush()  # gets us gym.id
                gyms_by_key[key] = gym
                created += 1
                print(f"  + created Gym: {loc}")

        # Link sessions
        session_links = 0
        for s in Session.query.filter(Session.gym_id.is_(None)).all():
            if s.location:
                gym = gyms_by_key.get(normalize(s.location))
                if gym:
                    s.gym_id = gym.id
                    session_links += 1

        # Link routes
        route_links = 0
        for r in Route.query.filter(Route.gym_id.is_(None)).all():
            if r.location:
                gym = gyms_by_key.get(normalize(r.location))
                if gym:
                    r.gym_id = gym.id
                    route_links += 1

        db.session.commit()

        print()
        print(f"Created {created} new Gym(s)")
        print(f"Linked {session_links} session(s)")
        print(f"Linked {route_links} route(s)")
        print("Done!")


if __name__ == "__main__":
    backfill()