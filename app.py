from flask import Flask, render_template, request, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///climbs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database + migrations
db = SQLAlchemy(app)
migrate = Migrate(app, db, render_as_batch=True)

# File upload config
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file):
    """Save an uploaded file and return the filename. Returns None if no file."""
    if not file or file.filename == '':
        return None
    if not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return filename


# --- Models ---

class Gym(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    address = db.Column(db.String(200))
    is_outdoor = db.Column(db.Boolean, default=False)
    image_filename = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sessions = db.relationship('Session', backref='gym', lazy=True)
    routes = db.relationship('Route', backref='gym', lazy=True)


class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    gym_id = db.Column(db.Integer, db.ForeignKey('gym.id'), nullable=True)
    location = db.Column(db.String(100))
    session_type = db.Column(db.String(20), default='indoor')
    notes = db.Column(db.String(300))
    climbs = db.relationship('Climb', backref='session', lazy=True)


class Route(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    gym_id = db.Column(db.Integer, db.ForeignKey('gym.id'), nullable=True)
    location = db.Column(db.String(100))
    discipline = db.Column(db.String(20), default='boulder')
    grade = db.Column(db.String(20))
    is_project = db.Column(db.Boolean, default=False)
    image_filename = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    climbs = db.relationship('Climb', backref='route', lazy=True)


RESULT_TYPES = ['attempt', 'send', 'flash', 'onsight']

RESULT_LABELS = {
    'attempt':  '🔄 Attempt',
    'send':     '✅ Send',
    'flash':    '⚡ Flash',
    'onsight':  '👁️ Onsight',
}

STYLE_TAGS = [
    'crimp', 'slab', 'overhang', 'pinch', 'dyno',
    'compression', 'crack', 'mantle', 'jump',
    'coordination', 'power', 'endurance',
]

# Anything that isn't an "attempt" counts as a successful send
SEND_RESULTS = {'send', 'flash', 'onsight'}


# --- Grade systems ---

# V-scale (bouldering). Order = easiest -> hardest.
V_GRADES_COMMON = ['VB', 'V0', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6', 'V7', 'V8', 'V9', 'V10']
V_GRADES_FULL = V_GRADES_COMMON + ['V11', 'V12', 'V13', 'V14', 'V15', 'V16', 'V17']

# YDS (routes). Order = easiest -> hardest.
YDS_GRADES_COMMON = [
    '5.6', '5.7', '5.8', '5.9',
    '5.10a', '5.10b', '5.10c', '5.10d',
    '5.11a', '5.11b', '5.11c', '5.11d',
    '5.12a', '5.12b', '5.12c', '5.12d',
]
YDS_GRADES_FULL = ['5.5'] + YDS_GRADES_COMMON + [
    '5.13a', '5.13b', '5.13c', '5.13d',
    '5.14a', '5.14b', '5.14c', '5.14d',
    '5.15a', '5.15b', '5.15c', '5.15d',
]

# Map (discipline, session_type) -> grade list
def get_grade_list(discipline, session_type):
    if discipline == 'boulder':
        return V_GRADES_FULL if session_type == 'outdoor' else V_GRADES_COMMON
    else:  # route
        return YDS_GRADES_FULL if session_type == 'outdoor' else YDS_GRADES_COMMON


# Build a single index for ranking *any* grade across both scales.
# Boulders and routes get ranked separately; we use this when finding "hardest sent".
GRADE_RANK = {}
for i, g in enumerate(V_GRADES_FULL):
    GRADE_RANK[('boulder', g)] = i
for i, g in enumerate(YDS_GRADES_FULL):
    GRADE_RANK[('route', g)] = i


def compute_stats(climbs):
    """Return a dict of stats for a list of climbs."""
    total = len(climbs)
    sends = sum(1 for c in climbs if c.result in SEND_RESULTS)
    send_rate = round((sends / total) * 100) if total > 0 else 0

    # Hardest grade sent — ranked per-discipline so V and YDS don't get mixed
    sent_climbs = [c for c in climbs if c.result in SEND_RESULTS and c.grade]

    def find_hardest(discipline):
        candidates = [c.grade for c in sent_climbs if c.discipline == discipline]
        if not candidates:
            return None
        return max(candidates, key=lambda g: GRADE_RANK.get((discipline, g), -1))

    hardest_boulder = find_hardest('boulder')
    hardest_route = find_hardest('route')

    # Breakdown by result type
    breakdown = {rt: sum(1 for c in climbs if c.result == rt) for rt in RESULT_TYPES}

    return {
        'total': total,
        'sends': sends,
        'send_rate': send_rate,
        'hardest_boulder': hardest_boulder,
        'hardest_route': hardest_route,
        'breakdown': breakdown,
    }

class Climb(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=True)
    route_id = db.Column(db.Integer, db.ForeignKey('route.id'), nullable=True)
    climb_name = db.Column(db.String(100))
    discipline = db.Column(db.String(20), default='boulder')  # 'boulder' or 'route'
    grade = db.Column(db.String(20))
    attempts = db.Column(db.Integer)
    result = db.Column(db.String(20), default='attempt')
    notes = db.Column(db.String(500))
    style_tags = db.Column(db.String(300))  # comma-separated e.g. "crimp,overhang"

    def get_style_tags(self):
        """Return style_tags as a list."""
        if not self.style_tags:
            return []
        return [t.strip() for t in self.style_tags.split(',') if t.strip()]


def find_or_create_gym(name, is_outdoor=False):
    """Find a Gym by case-insensitive name, or create one."""
    if not name:
        return None
    name = name.strip()
    existing = Gym.query.filter(db.func.lower(Gym.name) == name.lower()).first()
    if existing:
        return existing
    gym = Gym(name=name, is_outdoor=is_outdoor)
    db.session.add(gym)
    db.session.flush()
    return gym


# --- Gyms ---

@app.route("/gyms")
def gyms_list():
    gyms = Gym.query.order_by(Gym.name).all()
    gym_data = []
    for g in gyms:
        sessions = list(g.sessions)
        all_climbs = [c for s in sessions for c in s.climbs]
        stats = compute_stats(all_climbs)
        last_visit = max((s.date for s in sessions), default=None)
        gym_data.append({
            'gym': g,
            'session_count': len(sessions),
            'climb_count': stats['total'],
            'send_count': stats['sends'],
            'last_visit': last_visit,
        })
    gym_data.sort(key=lambda d: -(d['last_visit'].timestamp() if d['last_visit'] else 0))
    return render_template("gyms.html", gym_data=gym_data)


@app.route("/gym/<int:gym_id>")
def view_gym(gym_id):
    gym = Gym.query.get_or_404(gym_id)
    sessions = sorted(gym.sessions, key=lambda s: s.date, reverse=True)
    routes = list(gym.routes)
    all_climbs = [c for s in sessions for c in s.climbs]
    stats = compute_stats(all_climbs)
    return render_template(
        "gym_detail.html",
        gym=gym,
        sessions=sessions,
        routes=routes,
        stats=stats,
        result_labels=RESULT_LABELS,
    )


@app.route("/gym/<int:gym_id>/edit", methods=["GET", "POST"])
def edit_gym(gym_id):
    gym = Gym.query.get_or_404(gym_id)
    if request.method == "POST":
        gym.name = request.form.get("name", gym.name).strip()
        gym.address = request.form.get("address", "").strip() or None
        gym.is_outdoor = bool(request.form.get("is_outdoor"))
        file = request.files.get("image")
        filename = save_upload(file)
        if filename:
            gym.image_filename = filename
        db.session.commit()
        return redirect(f"/gym/{gym_id}")
    return render_template("edit_gym.html", gym=gym)


# --- Home ---

@app.route("/")
def home():
    sessions = Session.query.order_by(Session.date.desc()).all()

    # Per-session stats
    session_stats = {s.id: compute_stats(s.climbs) for s in sessions}

    # All-time stats across every climb
    all_climbs = Climb.query.all()
    all_time = compute_stats(all_climbs)
    all_time['total_sessions'] = len(sessions)

    return render_template(
        "index.html",
        sessions=sessions,
        session_stats=session_stats,
        all_time=all_time
    )


# --- Sessions ---

@app.route("/session/new", methods=["GET", "POST"])
def new_session():
    if request.method == "POST":
        gym_name = request.form.get("gym_name", "").strip()
        session_type = request.form.get("session_type", "indoor")
        if session_type not in ("indoor", "outdoor"):
            session_type = "indoor"
        notes = request.form.get("notes", "")

        gym = find_or_create_gym(gym_name, is_outdoor=(session_type == "outdoor"))

        session = Session(
            location=gym.name if gym else gym_name,  # keep legacy field for fallback
            gym_id=gym.id if gym else None,
            session_type=session_type,
            notes=notes,
        )
        db.session.add(session)
        db.session.commit()
        return redirect(f"/session/{session.id}")

    existing_gyms = Gym.query.order_by(Gym.name).all()
    return render_template("new_session.html", existing_gyms=existing_gyms)


@app.route("/session/<int:session_id>")
def view_session(session_id):
    session = Session.query.get_or_404(session_id)
    stats = compute_stats(session.climbs)
    return render_template(
        "session.html",
        session=session,
        result_labels=RESULT_LABELS,
        stats=stats
    )


@app.route("/route/<int:route_id>")
def view_route(route_id):
    route = Route.query.get_or_404(route_id)

    # Sort climbs oldest-first for the timeline
    climbs = sorted(
        [c for c in route.climbs if c.session],
        key=lambda c: c.session.date
    )

    total_attempts = sum(c.attempts for c in climbs)
    session_ids = {c.session_id for c in climbs}

    # Best result (highest tier achieved)
    best_result = None
    for priority in ['onsight', 'flash', 'send', 'attempt']:
        if any(c.result == priority for c in climbs):
            best_result = priority
            break

    # Days between first and most recent session (project duration)
    days_worked = None
    if len(climbs) >= 2:
        days_worked = (climbs[-1].session.date - climbs[0].session.date).days

    return render_template(
        "route_detail.html",
        route=route,
        climbs=climbs,
        total_attempts=total_attempts,
        session_count=len(session_ids),
        best_result=best_result,
        days_worked=days_worked,
        result_labels=RESULT_LABELS,
    )


@app.route("/route/<int:route_id>/toggle_project", methods=["POST"])
def toggle_project(route_id):
    route = Route.query.get_or_404(route_id)
    route.is_project = not route.is_project
    db.session.commit()
    return redirect(f"/route/{route_id}")


@app.route("/route/<int:route_id>/edit", methods=["GET", "POST"])
def edit_route(route_id):
    route = Route.query.get_or_404(route_id)
    if request.method == "POST":
        route.name = request.form.get("name", route.name).strip()
        route.grade = request.form.get("grade", route.grade)
        file = request.files.get("image")
        filename = save_upload(file)
        if filename:
            route.image_filename = filename
        db.session.commit()
        return redirect(f"/route/{route_id}")
    return render_template("edit_route.html", route=route,
                           boulder_grades=V_GRADES_FULL,
                           route_grades=YDS_GRADES_FULL)


@app.route("/projects")
def projects():
    project_routes = Route.query.filter_by(is_project=True).order_by(Route.created_at.desc()).all()

    project_data = []
    for r in project_routes:
        climbs = r.climbs
        total_attempts = sum(c.attempts for c in climbs) if climbs else 0
        session_ids = {c.session_id for c in climbs}
        is_sent = any(c.result in SEND_RESULTS for c in climbs)

        # Find best result achieved
        best_result = None
        for priority in ['onsight', 'flash', 'send', 'attempt']:
            if any(c.result == priority for c in climbs):
                best_result = priority
                break

        # First and most recent attempt dates
        dated_climbs = [c for c in climbs if c.session]
        first_date = min((c.session.date for c in dated_climbs), default=None)
        last_date = max((c.session.date for c in dated_climbs), default=None)

        project_data.append({
            'route': r,
            'total_attempts': total_attempts,
            'session_count': len(session_ids),
            'is_sent': is_sent,
            'best_result': best_result,
            'first_date': first_date,
            'last_date': last_date,
        })

    # Active projects first, sent projects after
    project_data.sort(key=lambda p: (p['is_sent'], -(p['last_date'].timestamp() if p['last_date'] else 0)))

    return render_template(
        "projects.html",
        project_data=project_data,
        result_labels=RESULT_LABELS,
    )


# --- Climbs ---

def find_or_create_route(name, gym, discipline, grade, is_project=False):
    """
    Find an existing Route by (name, gym, discipline) — case-insensitive on name —
    or create a new one. Always returns a Route instance.
    """
    if not name:
        return None
    gym_id = gym.id if gym else None
    existing = Route.query.filter(
        db.func.lower(Route.name) == name.strip().lower(),
        Route.gym_id == gym_id,
        Route.discipline == discipline,
    ).first()
    if existing:
        if is_project and not existing.is_project:
            existing.is_project = True
        return existing
    route = Route(
        name=name.strip(),
        gym_id=gym_id,
        location=gym.name if gym else None,  # legacy field, kept for fallback
        discipline=discipline,
        grade=grade,
        is_project=is_project,
    )
    db.session.add(route)
    db.session.flush()
    return route


@app.route("/api/routes/search")
def api_routes_search():
    """Return up to 8 routes matching a name fragment, optionally scoped by discipline."""
    q = (request.args.get("q") or "").strip().lower()
    discipline = request.args.get("discipline")
    if not q:
        return jsonify([])

    query = Route.query.filter(db.func.lower(Route.name).like(f"%{q}%"))
    if discipline:
        query = query.filter(Route.discipline == discipline)

    results = query.limit(8).all()
    return jsonify([
        {
            "id": r.id,
            "name": r.name,
            "grade": r.grade,
            "discipline": r.discipline,
            "location": r.gym.name if r.gym else r.location,
            "is_project": r.is_project,
        }
        for r in results
    ])


@app.route("/session/<int:session_id>/add", methods=["GET", "POST"])
def add_climb(session_id):
    session = Session.query.get_or_404(session_id)

    if request.method == "POST":
        climb_name = request.form["climb_name"].strip()
        discipline = request.form.get("discipline", "boulder")
        if discipline not in ("boulder", "route"):
            discipline = "boulder"
        grade = request.form["grade"]
        attempts = int(request.form["attempts"])
        result = request.form.get("result", "attempt")
        if result not in RESULT_TYPES:
            result = "attempt"
        is_project = bool(request.form.get("is_project"))
        notes = request.form.get("notes", "").strip() or None
        selected_tags = request.form.getlist("style_tags")
        style_tags = ','.join(t for t in selected_tags if t in STYLE_TAGS) or None

        # Link to an existing route (if user clicked a suggestion) or find-or-create
        route_id_raw = request.form.get("route_id")
        if route_id_raw:
            route = Route.query.get(int(route_id_raw))
            if route and is_project and not route.is_project:
                route.is_project = True
        else:
            route = find_or_create_route(
                name=climb_name,
                gym=session.gym,
                discipline=discipline,
                grade=grade,
                is_project=is_project,
            )

        new_climb = Climb(
            session_id=session_id,
            route_id=route.id if route else None,
            climb_name=climb_name,
            discipline=discipline,
            grade=grade,
            attempts=attempts,
            result=result,
            notes=notes,
            style_tags=style_tags,
        )
        db.session.add(new_climb)
        db.session.commit()
        return redirect(f"/session/{session_id}")

    return render_template(
        "add_climb.html",
        session=session,
        result_types=RESULT_TYPES,
        result_labels=RESULT_LABELS,
        boulder_grades=get_grade_list('boulder', session.session_type),
        route_grades=get_grade_list('route', session.session_type),
        style_tags=STYLE_TAGS,
    )


@app.route("/climb/<int:climb_id>/edit", methods=["GET", "POST"])
def edit_climb(climb_id):
    climb = Climb.query.get_or_404(climb_id)

    if request.method == "POST":
        climb.climb_name = request.form["climb_name"]
        discipline = request.form.get("discipline", "boulder")
        if discipline not in ("boulder", "route"):
            discipline = "boulder"
        climb.discipline = discipline
        climb.grade = request.form["grade"]
        climb.attempts = int(request.form["attempts"])
        result = request.form.get("result", "attempt")
        if result not in RESULT_TYPES:
            result = "attempt"
        climb.result = result
        climb.notes = request.form.get("notes", "").strip() or None
        selected_tags = request.form.getlist("style_tags")
        climb.style_tags = ','.join(t for t in selected_tags if t in STYLE_TAGS) or None

        db.session.commit()
        return redirect(f"/session/{climb.session_id}")

    return render_template(
        "edit_climb.html",
        climb=climb,
        result_types=RESULT_TYPES,
        result_labels=RESULT_LABELS,
        boulder_grades=get_grade_list('boulder', climb.session.session_type),
        route_grades=get_grade_list('route', climb.session.session_type),
        style_tags=STYLE_TAGS,
    )


@app.route("/climb/<int:climb_id>/delete", methods=["POST"])
def delete_climb(climb_id):
    climb = Climb.query.get_or_404(climb_id)
    session_id = climb.session_id
    db.session.delete(climb)
    db.session.commit()
    return redirect(f"/session/{session_id}")


@app.route("/insights")
def insights():
    all_climbs = Climb.query.join(Session).order_by(Session.date).all()
    all_sessions = Session.query.order_by(Session.date).all()

    # --- Grade progression ---
    # For each session, find the hardest grade sent (boulder + route separately)
    boulder_progression = []
    route_progression = []
    for s in all_sessions:
        session_climbs = [c for c in s.climbs if c.result in SEND_RESULTS]
        b = max(
            (c.grade for c in session_climbs if c.discipline == 'boulder' and c.grade),
            key=lambda g: GRADE_RANK.get(('boulder', g), -1),
            default=None
        )
        r = max(
            (c.grade for c in session_climbs if c.discipline == 'route' and c.grade),
            key=lambda g: GRADE_RANK.get(('route', g), -1),
            default=None
        )
        if b:
            boulder_progression.append({
                'date': s.date.strftime('%b %d'),
                'grade': b,
                'rank': GRADE_RANK.get(('boulder', b), 0),
            })
        if r:
            route_progression.append({
                'date': s.date.strftime('%b %d'),
                'grade': r,
                'rank': GRADE_RANK.get(('route', r), 0),
            })

    # --- Style breakdown ---
    # Count sends vs attempts per tag
    tag_stats = {tag: {'sends': 0, 'attempts': 0} for tag in STYLE_TAGS}
    for c in all_climbs:
        for tag in c.get_style_tags():
            if tag in tag_stats:
                if c.result in SEND_RESULTS:
                    tag_stats[tag]['sends'] += 1
                else:
                    tag_stats[tag]['attempts'] += 1

    # Only include tags that have been used
    tag_stats = {k: v for k, v in tag_stats.items() if v['sends'] + v['attempts'] > 0}

    # --- Send rate by grade (boulder) ---
    grade_send_rate = {}
    for c in all_climbs:
        if not c.grade or not c.discipline:
            continue
        key = (c.discipline, c.grade)
        if key not in grade_send_rate:
            grade_send_rate[key] = {'sends': 0, 'total': 0}
        grade_send_rate[key]['total'] += 1
        if c.result in SEND_RESULTS:
            grade_send_rate[key]['sends'] += 1

    boulder_send_rates = sorted(
        [{'grade': g, 'rate': round(v['sends'] / v['total'] * 100), 'total': v['total']}
         for (d, g), v in grade_send_rate.items() if d == 'boulder'],
        key=lambda x: GRADE_RANK.get(('boulder', x['grade']), -1)
    )
    route_send_rates = sorted(
        [{'grade': g, 'rate': round(v['sends'] / v['total'] * 100), 'total': v['total']}
         for (d, g), v in grade_send_rate.items() if d == 'route'],
        key=lambda x: GRADE_RANK.get(('route', x['grade']), -1)
    )

    # --- Most worked routes ---
    top_projects = sorted(
        [r for r in Route.query.all() if len(r.climbs) > 1],
        key=lambda r: sum(c.attempts for c in r.climbs),
        reverse=True
    )[:5]

    # --- Quick summary numbers ---
    total_climbs = len(all_climbs)
    total_sends = sum(1 for c in all_climbs if c.result in SEND_RESULTS)
    total_sessions = len(all_sessions)
    send_rate = round(total_sends / total_climbs * 100) if total_climbs else 0

    return render_template(
        "insights.html",
        boulder_progression=boulder_progression,
        route_progression=route_progression,
        tag_stats=tag_stats,
        boulder_send_rates=boulder_send_rates,
        route_send_rates=route_send_rates,
        top_projects=top_projects,
        total_climbs=total_climbs,
        total_sends=total_sends,
        total_sessions=total_sessions,
        send_rate=send_rate,
        style_tags=STYLE_TAGS,
    )


if __name__ == "__main__":
    app.run(debug=True, extra_files=[], exclude_patterns=["static/uploads/*"])