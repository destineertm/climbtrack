"""
One-off merge script.

Consolidates duplicate Gym rows by moving all sessions/routes to a
target Gym, then deleting the source Gyms.

Edit MERGES below for your needs.

Usage:
    python merge_gyms.py
"""

from app import app, db, Gym, Session, Route


# (target_name, [source_names]) — sources will be merged into target and then deleted.
# All names are matched case-insensitively + stripped.
MERGES = [
    ("Climb Bentonville", ["72719", "Centerton AR", "Arkansas"]),
]


def find_gym(name):
    """Case-insensitive lookup."""
    return Gym.query.filter(db.func.lower(Gym.name) == name.strip().lower()).first()


def merge():
    with app.app_context():
        for target_name, source_names in MERGES:
            target = find_gym(target_name)
            if not target:
                print(f"❌ Target gym '{target_name}' not found — skipping this group.")
                continue

            print(f"\nMerging into '{target.name}' (id={target.id}):")

            for src_name in source_names:
                src = find_gym(src_name)
                if not src:
                    print(f"  - '{src_name}' not found, skipping")
                    continue
                if src.id == target.id:
                    print(f"  - '{src_name}' IS the target, skipping")
                    continue

                # Move sessions
                moved_sessions = 0
                for s in Session.query.filter_by(gym_id=src.id).all():
                    s.gym_id = target.id
                    moved_sessions += 1

                # Move routes
                moved_routes = 0
                for r in Route.query.filter_by(gym_id=src.id).all():
                    r.gym_id = target.id
                    moved_routes += 1

                db.session.flush()
                db.session.delete(src)
                print(f"  - '{src.name}' merged: {moved_sessions} session(s), {moved_routes} route(s) moved; gym deleted")

        db.session.commit()
        print("\nDone!")

        # Show remaining gyms for sanity check
        print("\nGyms now in database:")
        for g in Gym.query.order_by(Gym.name).all():
            n_sessions = Session.query.filter_by(gym_id=g.id).count()
            n_routes = Route.query.filter_by(gym_id=g.id).count()
            print(f"  · {g.name} ({n_sessions} session(s), {n_routes} route(s))")


if __name__ == "__main__":
    merge()