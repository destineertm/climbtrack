"""
One-off backfill script.

Links existing Climb rows to Route rows by matching on
climb_name + discipline (case-insensitive). Prefers routes
from the same gym as the session when there are multiple matches.

Run ONCE after the Route system was added. Safe to re-run
(only touches climbs where route_id IS NULL).

Usage:
    python backfill_climb_routes.py
"""

from app import app, db, Climb, Route


def normalize(name):
    return (name or "").strip().lower()


def backfill():
    with app.app_context():
        unlinked = Climb.query.filter(Climb.route_id.is_(None)).all()
        print(f"Found {len(unlinked)} unlinked climb(s).\n")

        linked = 0
        skipped = 0
        ambiguous = 0

        for climb in unlinked:
            if not climb.climb_name:
                skipped += 1
                continue

            # Find all routes matching name + discipline
            candidates = Route.query.filter(
                db.func.lower(Route.name) == normalize(climb.climb_name),
                Route.discipline == climb.discipline,
            ).all()

            if not candidates:
                skipped += 1
                continue

            if len(candidates) == 1:
                climb.route_id = candidates[0].id
                linked += 1
                print(f"  Linked: '{climb.climb_name}' -> route id {candidates[0].id}")

            else:
                # Multiple matches — prefer the one from the same gym as the session
                session_gym_id = climb.session.gym_id if climb.session else None
                gym_match = [r for r in candidates if r.gym_id == session_gym_id]

                if len(gym_match) == 1:
                    climb.route_id = gym_match[0].id
                    linked += 1
                    print(f"  Linked (gym match): '{climb.climb_name}' -> route id {gym_match[0].id}")
                else:
                    # Still ambiguous — skip and report
                    ambiguous += 1
                    print(f"  Ambiguous: '{climb.climb_name}' matched {len(candidates)} routes — skipping")

        db.session.commit()

        print()
        print(f"Linked:    {linked}")
        print(f"Skipped:   {skipped} (no matching route found)")
        print(f"Ambiguous: {ambiguous} (multiple matches, couldn't resolve)")
        print("Done!")


if __name__ == "__main__":
    backfill()