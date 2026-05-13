from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///climbs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database + migrations
db = SQLAlchemy(app)
migrate = Migrate(app, db, render_as_batch=True)

# Flask-Login
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access ClimbTrack.'

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


def get_embed_url(url):
    """
    Convert a raw YouTube or Vimeo URL to an embeddable iframe URL.
    Returns None if the URL is not a supported video platform.
    """
    if not url:
        return None
    url = url.strip()

    # YouTube — handle youtu.be, youtube.com/watch, youtube.com/shorts
    import re
    yt_patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
    ]
    for pat in yt_patterns:
        m = re.search(pat, url)
        if m:
            return f"https://www.youtube.com/embed/{m.group(1)}"

    # Vimeo
    m = re.search(r'vimeo\.com/(\d+)', url)
    if m:
        return f"https://player.vimeo.com/video/{m.group(1)}"

    # Not a recognized embeddable platform — store as plain link
    return None


# --- Models ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sessions = db.relationship('Session', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
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
    photo_filename = db.Column(db.String(200))
    video_url = db.Column(db.String(500))

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
@login_required
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
@login_required
def view_gym(gym_id):
    gym = Gym.query.get_or_404(gym_id)
    sessions = sorted(gym.sessions, key=lambda s: s.date, reverse=True)
    routes = list(gym.routes)
    all_climbs = [c for s in sessions for c in s.climbs]
    stats = compute_stats(all_climbs)

    # Style breakdown for this gym
    tag_stats = {tag: {'sends': 0, 'attempts': 0} for tag in STYLE_TAGS}
    for c in all_climbs:
        for tag in c.get_style_tags():
            if tag in tag_stats:
                if c.result in SEND_RESULTS:
                    tag_stats[tag]['sends'] += 1
                else:
                    tag_stats[tag]['attempts'] += 1
    tag_stats = {k.capitalize(): v for k, v in tag_stats.items() if v['sends'] + v['attempts'] > 0}

    return render_template(
        "gym_detail.html",
        gym=gym,
        sessions=sessions,
        routes=routes,
        stats=stats,
        tag_stats=tag_stats,
        result_labels=RESULT_LABELS,
    )


@app.route("/gym/<int:gym_id>/edit", methods=["GET", "POST"])
@login_required
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


# --- Auth ---

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not email or not display_name or not password:
            flash("All fields are required.")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.")
            return render_template("register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.")
            return render_template("register.html")

        user = User(email=email, display_name=display_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect("/")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.")
            return render_template("login.html")
        login_user(user)
        next_page = request.args.get("next")
        return redirect(next_page or "/")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")


# --- Home ---

@app.route("/")
@login_required
def home():
    sessions = Session.query.order_by(Session.date.desc()).all()

    # Per-session stats
    session_stats = {s.id: compute_stats(s.climbs) for s in sessions}

    # All-time stats across every climb
    all_climbs = Climb.query.all()
    all_time = compute_stats(all_climbs)
    all_time['total_sessions'] = len(sessions)

    # --- Monthly trends ---
    from datetime import date
    today = datetime.utcnow()
    this_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (this_month_start.replace(day=1) - __import__('datetime').timedelta(days=1)).replace(day=1)

    this_month_climbs = [c for c in all_climbs if c.session and c.session.date >= this_month_start]
    last_month_climbs = [c for c in all_climbs if c.session and last_month_start <= c.session.date < this_month_start]

    this_month_stats = compute_stats(this_month_climbs)
    last_month_stats = compute_stats(last_month_climbs)

    # Send rate trend
    rate_diff = this_month_stats['send_rate'] - last_month_stats['send_rate'] if last_month_climbs else None

    # Most active style tag this month
    tag_counts = {}
    for c in this_month_climbs:
        for tag in c.get_style_tags():
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    top_tag = max(tag_counts, key=tag_counts.get) if tag_counts else None

    # Climbing streak — consecutive days with at least one session
    session_dates = sorted(set(s.date.date() for s in sessions), reverse=True)
    streak = 0
    if session_dates:
        from datetime import date, timedelta
        check = date.today()
        for d in session_dates:
            if d == check or d == check - timedelta(days=1):
                streak += 1
                check = d
            else:
                break

    trends = {
        'this_month_climbs': this_month_stats['total'],
        'last_month_climbs': last_month_stats['total'],
        'this_month_sends': this_month_stats['sends'],
        'this_month_send_rate': this_month_stats['send_rate'],
        'rate_diff': rate_diff,
        'top_tag': top_tag,
        'streak': streak,
    }

    return render_template(
        "index.html",
        sessions=sessions,
        session_stats=session_stats,
        all_time=all_time,
        trends=trends,
    )


# --- Sessions ---

@app.route("/session/new", methods=["GET", "POST"])
@login_required
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
            user_id=current_user.id,
            session_type=session_type,
            notes=notes,
        )
        db.session.add(session)
        db.session.commit()
        return redirect(f"/session/{session.id}")

    existing_gyms = Gym.query.order_by(Gym.name).all()
    return render_template("new_session.html", existing_gyms=existing_gyms)


@app.route("/session/<int:session_id>")
@login_required
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
@login_required
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


@app.route("/route/<int:route_id>/story")
@login_required
def route_story(route_id):
    route = Route.query.get_or_404(route_id)
    climbs = sorted(
        [c for c in route.climbs if c.session],
        key=lambda c: c.session.date,
        reverse=True
    )
    total_attempts = sum(c.attempts for c in climbs)
    is_sent = any(c.result in SEND_RESULTS for c in climbs)
    best_result = None
    for priority in ['onsight', 'flash', 'send', 'attempt']:
        if any(c.result == priority for c in climbs):
            best_result = priority
            break
    days_on_route = None
    if len(climbs) >= 2:
        days_on_route = (climbs[-1].session.date - climbs[0].session.date).days

    return render_template(
        "route_story.html",
        route=route,
        climbs=climbs,
        total_attempts=total_attempts,
        is_sent=is_sent,
        best_result=best_result,
        days_on_route=days_on_route,
        result_labels=RESULT_LABELS,
    )


@app.route("/route/<int:route_id>/toggle_project", methods=["POST"])
@login_required
def toggle_project(route_id):
    route = Route.query.get_or_404(route_id)
    route.is_project = not route.is_project
    db.session.commit()
    return redirect(f"/route/{route_id}")


@app.route("/route/<int:route_id>/edit", methods=["GET", "POST"])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
        photo_filename = save_upload(request.files.get("photo"))
        video_url = request.form.get("video_url", "").strip() or None

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
            photo_filename=photo_filename,
            video_url=video_url,
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
@login_required
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
        photo = request.files.get("photo")
        if photo and photo.filename:
            filename = save_upload(photo)
            if filename:
                climb.photo_filename = filename
        video_url = request.form.get("video_url", "").strip() or None
        climb.video_url = video_url

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


@app.route("/training")
@login_required
def training_page():
    all_climbs = Climb.query.join(Session).order_by(Session.date).all()
    all_sessions = Session.query.order_by(Session.date).all()
    total_sessions = len(all_sessions)
    total_climbs = len(all_climbs)
    total_sends = sum(1 for c in all_climbs if c.result in SEND_RESULTS)
    send_rate = round(total_sends / total_climbs * 100) if total_climbs else 0

    # Reuse tag_stats for weakness detection
    tag_stats = {tag: {'sends': 0, 'attempts': 0} for tag in STYLE_TAGS}
    for c in all_climbs:
        for tag in c.get_style_tags():
            if tag in tag_stats:
                if c.result in SEND_RESULTS:
                    tag_stats[tag]['sends'] += 1
                else:
                    tag_stats[tag]['attempts'] += 1
    tag_stats = {k: v for k, v in tag_stats.items() if v['sends'] + v['attempts'] > 0}

    training = None
    if total_sessions >= 10:
        from datetime import date, timedelta

        recent_sessions = all_sessions[-5:]

        def best_grade(sessions, discipline):
            grades = [
                c.grade for s in sessions for c in s.climbs
                if c.result in SEND_RESULTS and c.discipline == discipline and c.grade
            ]
            if not grades:
                return None, -1
            best = max(grades, key=lambda g: GRADE_RANK.get((discipline, g), -1))
            return best, GRADE_RANK.get((discipline, best), -1)

        # All-time peak (across all sessions)
        peak_b, peak_b_rank = best_grade(all_sessions, 'boulder')
        peak_r, peak_r_rank = best_grade(all_sessions, 'route')

        # Recent best (last 5 sessions)
        recent_b, recent_b_rank = best_grade(recent_sessions, 'boulder')
        recent_r, recent_r_rank = best_grade(recent_sessions, 'route')

        # Progressing = recent best matches or exceeds all-time peak
        # Plateaued = recent best is more than 1 grade below all-time peak
        boulder_progressing = recent_b and peak_b and recent_b_rank >= peak_b_rank
        route_progressing = recent_r and peak_r and recent_r_rank >= peak_r_rank
        boulder_plateau = recent_b and peak_b and recent_b_rank < peak_b_rank - 1
        route_plateau = recent_r and peak_r and recent_r_rank < peak_r_rank - 1

        overall_send_rate = send_rate / 100 if total_climbs else 0
        tag_send_rates = {}
        for tag, data in tag_stats.items():
            total_tag = data['sends'] + data['attempts']
            if total_tag >= 3:
                tag_send_rates[tag] = data['sends'] / total_tag

        weaknesses = sorted(
            [t for t, r in tag_send_rates.items() if r < overall_send_rate - 0.05],
            key=lambda t: tag_send_rates[t]
        )[:3]

        strengths = sorted(
            [t for t, r in tag_send_rates.items() if r > overall_send_rate + 0.05],
            key=lambda t: tag_send_rates[t],
            reverse=True
        )[:3]

        today = datetime.utcnow().date()
        recent_dates = sorted(set(
            s.date.date() for s in all_sessions
            if (today - s.date.date()).days <= 7
        ), reverse=True)

        days_since_last = (today - all_sessions[-1].date.date()).days if all_sessions else 999
        sessions_last_7 = len(recent_dates)

        streak = 0
        check = today
        for d in recent_dates:
            if d == check or d == check - timedelta(days=1):
                streak += 1
                check = d
            else:
                break

        if streak >= 3:
            fatigue = 'high'
            fatigue_msg = f"You've climbed {streak} days in a row. Your body needs rest to adapt."
        elif days_since_last >= 5:
            fatigue = 'low'
            fatigue_msg = f"It's been {days_since_last} days since your last session. Time to get back on the wall!"
        elif sessions_last_7 >= 4:
            fatigue = 'moderate'
            fatigue_msg = f"{sessions_last_7} sessions this week. Consider an easy session or rest day soon."
        else:
            fatigue = 'good'
            fatigue_msg = "Your training load looks balanced. Keep it up."

        if fatigue == 'high':
            primary_rec = "Rest day recommended"
            primary_detail = "Take 1-2 days off. Finger tendons adapt slower than muscle — rest is when you get stronger."
        elif boulder_plateau and route_plateau:
            primary_rec = "You may be plateaued"
            primary_detail = f"Your top grades haven't improved in 5 sessions (boulder: {recent_b}, route: {recent_r}). Try targeting your weaknesses: {', '.join(weaknesses[:2]) if weaknesses else 'vary your style'}."
        elif weaknesses:
            primary_rec = f"Focus on your weaknesses: {', '.join(weaknesses)}"
            primary_detail = "Your send rate on these styles is below your average. Deliberately targeting weaknesses is the fastest path to improvement."
        elif boulder_progressing or route_progressing:
            primary_rec = "You're progressing — keep pushing grades"
            primary_detail = f"{'Boulder grades improving. ' if boulder_progressing else ''}{'Route grades improving. ' if route_progressing else ''}Maintain the momentum."
        else:
            primary_rec = "Solid foundation — vary your sessions"
            primary_detail = "Mix hard project sessions with volume days to build both strength and endurance."

        focus_styles = weaknesses[:2] if weaknesses else ['overhang', 'slab']

        if fatigue == 'high':
            weekly_plan = [
                {'day': 'Today', 'type': 'Rest', 'detail': 'Full rest. Stretch if you want.'},
                {'day': 'Tomorrow', 'type': 'Rest', 'detail': 'Light activity only — walk, yoga.'},
                {'day': 'Day 3', 'type': 'Easy session', 'detail': 'Low volume, easy grades. Focus on footwork and technique.'},
                {'day': 'Day 4', 'type': 'Rest', 'detail': 'Rest day.'},
                {'day': 'Day 5', 'type': 'Project session', 'detail': 'Back to full strength. Work your projects.'},
                {'day': 'Day 6', 'type': 'Volume session', 'detail': f'High volume, moderate grades. Focus on {focus_styles[0]}.'},
                {'day': 'Day 7', 'type': 'Rest', 'detail': 'End the week with rest.'},
            ]
        elif fatigue == 'low':
            weekly_plan = [
                {'day': 'Today', 'type': 'Get on the wall', 'detail': 'Any session — just climb. Momentum matters.'},
                {'day': 'Tomorrow', 'type': 'Rest', 'detail': 'Rest day.'},
                {'day': 'Day 3', 'type': 'Project session', 'detail': 'Work your hardest projects with fresh skin.'},
                {'day': 'Day 4', 'type': 'Rest', 'detail': 'Rest day.'},
                {'day': 'Day 5', 'type': 'Weakness session', 'detail': f'Deliberately target {", ".join(focus_styles)} problems.'},
                {'day': 'Day 6', 'type': 'Rest', 'detail': 'Rest day.'},
                {'day': 'Day 7', 'type': 'Volume session', 'detail': 'High volume at comfortable grades. Build endurance.'},
            ]
        else:
            weekly_plan = [
                {'day': 'Today', 'type': 'Project session', 'detail': 'Push your limit grades. Aim for sends.'},
                {'day': 'Tomorrow', 'type': 'Rest', 'detail': 'Rest day. Let the tendons recover.'},
                {'day': 'Day 3', 'type': 'Weakness session', 'detail': f'Focus on {", ".join(focus_styles)}. Pick problems that specifically target these styles.'},
                {'day': 'Day 4', 'type': 'Rest', 'detail': 'Rest day.'},
                {'day': 'Day 5', 'type': 'Volume session', 'detail': 'High volume at 2 grades below your max. Build a base.'},
                {'day': 'Day 6', 'type': 'Rest or easy', 'detail': 'Light session or rest — listen to your body.'},
                {'day': 'Day 7', 'type': 'Rest', 'detail': 'End the week with rest.'},
            ]

        training = {
            'boulder_plateau': boulder_plateau,
            'route_plateau': route_plateau,
            'boulder_progressing': boulder_progressing,
            'route_progressing': route_progressing,
            'recent_boulder': recent_b,
            'peak_boulder': peak_b,
            'recent_route': recent_r,
            'peak_route': peak_r,
            'weaknesses': weaknesses,
            'strengths': strengths,
            'fatigue': fatigue,
            'fatigue_msg': fatigue_msg,
            'primary_rec': primary_rec,
            'primary_detail': primary_detail,
            'weekly_plan': weekly_plan,
            'sessions_last_7': sessions_last_7,
            'days_since_last': days_since_last,
        }

    return render_template(
        "training.html",
        training=training,
        total_sessions=total_sessions,
    )


@app.route("/climb/<int:climb_id>/delete", methods=["POST"])
@login_required
def delete_climb(climb_id):
    climb = Climb.query.get_or_404(climb_id)
    session_id = climb.session_id
    db.session.delete(climb)
    db.session.commit()
    return redirect(f"/session/{session_id}")


@app.route("/insights")
@login_required
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

    # Only include tags that have been used — as ordered list for safe JS rendering
    tag_stats_list = [
        {'tag': tag.capitalize(), 'sends': data['sends'], 'attempts': data['attempts']}
        for tag, data in tag_stats.items()
        if data['sends'] + data['attempts'] > 0
    ]
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

    # --- Training intelligence (requires 10+ sessions) ---
    training = None
    if total_sessions >= 10:
        from datetime import date, timedelta

        # 1. Plateau detection — all-time peak vs recent best (last 5 sessions)
        recent_sessions = all_sessions[-5:]

        def best_grade_in(sessions, discipline):
            grades = [
                c.grade for s in sessions for c in s.climbs
                if c.result in SEND_RESULTS and c.discipline == discipline and c.grade
            ]
            if not grades:
                return None, -1
            best = max(grades, key=lambda g: GRADE_RANK.get((discipline, g), -1))
            return best, GRADE_RANK.get((discipline, best), -1)

        peak_b, peak_b_rank = best_grade_in(all_sessions, 'boulder')
        peak_r, peak_r_rank = best_grade_in(all_sessions, 'route')
        recent_b, recent_b_rank = best_grade_in(recent_sessions, 'boulder')
        recent_r, recent_r_rank = best_grade_in(recent_sessions, 'route')

        boulder_progressing = recent_b and peak_b and recent_b_rank >= peak_b_rank
        route_progressing = recent_r and peak_r and recent_r_rank >= peak_r_rank
        boulder_plateau = recent_b and peak_b and recent_b_rank < peak_b_rank - 1
        route_plateau = recent_r and peak_r and recent_r_rank < peak_r_rank - 1

        # 2. Weakness detection — tags with below-average send rate
        overall_send_rate = send_rate / 100 if total_climbs else 0
        tag_send_rates = {}
        for tag, data in tag_stats.items():
            total_tag = data['sends'] + data['attempts']
            if total_tag >= 3:  # need at least 3 data points
                tag_send_rates[tag] = data['sends'] / total_tag

        weaknesses = sorted(
            [t for t, r in tag_send_rates.items() if r < overall_send_rate - 0.05],
            key=lambda t: tag_send_rates[t]
        )[:3]

        strengths = sorted(
            [t for t, r in tag_send_rates.items() if r > overall_send_rate + 0.05],
            key=lambda t: tag_send_rates[t],
            reverse=True
        )[:3]

        # 3. Fatigue signal — sessions in last 7 days
        today = datetime.utcnow().date()
        recent_dates = sorted(set(
            s.date.date() for s in all_sessions
            if (today - s.date.date()).days <= 7
        ), reverse=True)

        days_since_last = (today - all_sessions[-1].date.date()).days if all_sessions else 999
        sessions_last_7 = len(recent_dates)

        # Consecutive day streak
        streak = 0
        check = today
        for d in recent_dates:
            if d == check or d == check - timedelta(days=1):
                streak += 1
                check = d
            else:
                break

        if streak >= 3:
            fatigue = 'high'
            fatigue_msg = f"You've climbed {streak} days in a row. Your body needs rest to adapt."
        elif days_since_last >= 5:
            fatigue = 'low'
            fatigue_msg = f"It's been {days_since_last} days since your last session. Time to get back on the wall!"
        elif sessions_last_7 >= 4:
            fatigue = 'moderate'
            fatigue_msg = f"{sessions_last_7} sessions this week. Consider an easy session or rest day soon."
        else:
            fatigue = 'good'
            fatigue_msg = "Your training load looks balanced. Keep it up."

        # 4. Primary recommendation
        if fatigue == 'high':
            primary_rec = "Rest day recommended"
            primary_detail = "Take 1-2 days off. Finger tendons adapt slower than muscle — rest is when you get stronger."
        elif boulder_plateau and route_plateau:
            primary_rec = "You may be plateaued"
            primary_detail = f"Your top grades haven't improved in 5 sessions (boulder: {recent_b}, route: {recent_r}). Try targeting your weaknesses: {', '.join(weaknesses[:2]) if weaknesses else 'vary your style'}."
        elif weaknesses:
            primary_rec = f"Focus on your weaknesses: {', '.join(weaknesses)}"
            primary_detail = "Your send rate on these styles is below your average. Deliberately targeting weaknesses is the fastest path to improvement."
        elif boulder_progressing or route_progressing:
            primary_rec = "You're progressing — keep pushing grades"
            primary_detail = f"{'Boulder grades improving. ' if boulder_progressing else ''}{'Route grades improving. ' if route_progressing else ''}Maintain the momentum."
        else:
            primary_rec = "Solid foundation — vary your sessions"
            primary_detail = "Mix hard project sessions with volume days to build both strength and endurance."

        # 5. Weekly plan
        focus_styles = weaknesses[:2] if weaknesses else ['overhang', 'slab']
        weekly_plan = []

        if fatigue == 'high':
            weekly_plan = [
                {'day': 'Today', 'type': 'Rest', 'detail': 'Full rest. Stretch if you want.'},
                {'day': 'Tomorrow', 'type': 'Rest', 'detail': 'Light activity only — walk, yoga.'},
                {'day': 'Day 3', 'type': 'Easy session', 'detail': f'Low volume, easy grades. Focus on footwork and technique.'},
                {'day': 'Day 4', 'type': 'Rest', 'detail': 'Rest day.'},
                {'day': 'Day 5', 'type': 'Project session', 'detail': f'Back to full strength. Work your projects.'},
                {'day': 'Day 6', 'type': 'Volume session', 'detail': f'High volume, moderate grades. Focus on {focus_styles[0]}.'},
                {'day': 'Day 7', 'type': 'Rest', 'detail': 'End the week with rest.'},
            ]
        elif fatigue == 'low':
            weekly_plan = [
                {'day': 'Today', 'type': 'Get on the wall', 'detail': 'Any session — just climb. Momentum matters.'},
                {'day': 'Tomorrow', 'type': 'Rest', 'detail': 'Rest day.'},
                {'day': 'Day 3', 'type': 'Project session', 'detail': 'Work your hardest projects with fresh skin.'},
                {'day': 'Day 4', 'type': 'Rest', 'detail': 'Rest day.'},
                {'day': 'Day 5', 'type': 'Weakness session', 'detail': f'Deliberately target {", ".join(focus_styles)} problems.'},
                {'day': 'Day 6', 'type': 'Rest', 'detail': 'Rest day.'},
                {'day': 'Day 7', 'type': 'Volume session', 'detail': 'High volume at comfortable grades. Build endurance.'},
            ]
        else:
            weekly_plan = [
                {'day': 'Today', 'type': 'Project session', 'detail': 'Push your limit grades. Aim for sends.'},
                {'day': 'Tomorrow', 'type': 'Rest', 'detail': 'Rest day. Let the tendons recover.'},
                {'day': 'Day 3', 'type': 'Weakness session', 'detail': f'Focus on {", ".join(focus_styles)}. Pick problems that specifically target these styles.'},
                {'day': 'Day 4', 'type': 'Rest', 'detail': 'Rest day.'},
                {'day': 'Day 5', 'type': 'Volume session', 'detail': 'High volume at 2 grades below your max. Build a base.'},
                {'day': 'Day 6', 'type': 'Rest or easy', 'detail': 'Light session or rest — listen to your body.'},
                {'day': 'Day 7', 'type': 'Rest', 'detail': 'End the week with rest.'},
            ]

        training = {
            'boulder_plateau': boulder_plateau,
            'route_plateau': route_plateau,
            'boulder_progressing': boulder_progressing,
            'route_progressing': route_progressing,
            'recent_boulder': recent_b,
            'peak_boulder': peak_b,
            'recent_route': recent_r,
            'peak_route': peak_r,
            'weaknesses': weaknesses,
            'strengths': strengths,
            'fatigue': fatigue,
            'fatigue_msg': fatigue_msg,
            'primary_rec': primary_rec,
            'primary_detail': primary_detail,
            'weekly_plan': weekly_plan,
            'sessions_last_7': sessions_last_7,
            'days_since_last': days_since_last,
        }

    return render_template(
        "insights.html",
        boulder_progression=boulder_progression,
        route_progression=route_progression,
        tag_stats=tag_stats,
        tag_stats_list=tag_stats_list,
        boulder_send_rates=boulder_send_rates,
        route_send_rates=route_send_rates,
        top_projects=top_projects,
        total_climbs=total_climbs,
        total_sends=total_sends,
        total_sessions=total_sessions,
        send_rate=send_rate,
        style_tags=STYLE_TAGS,
        training=training,
    )


if __name__ == "__main__":
    app.run(debug=True, extra_files=[], exclude_patterns=["static/uploads/*"])