from flask import (
    Flask,
    render_template,
    request,
    redirect,
    send_file,
    url_for,
    flash,
    send_from_directory,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    UserMixin,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret-key-change-this"

# =====================
# DATABASE
# =====================

database_url = os.environ.get("DATABASE_URL")

if not database_url:
    database_url = "sqlite:///database.db"

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =====================
# LOGIN MANAGER
# =====================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Nejdřív se prosím přihlas."

# =====================
# MODELY
# =====================

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    closed = db.Column(db.Boolean, default=False, nullable=False)


class JobRow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)

    date = db.Column(db.String(20))
    material_name = db.Column(db.String(200))
    quantity = db.Column(db.Float)
    document_number = db.Column(db.String(100))
    km = db.Column(db.Float)
    travel_time = db.Column(db.Float)
    work_hours = db.Column(db.Float)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# =====================
# INIT DB
# =====================

with app.app_context():
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()

# =====================
# PWA
# =====================

@app.route("/manifest.json")
def manifest():
    return send_from_directory(".", "manifest.json", mimetype="application/manifest+json")


@app.route("/service-worker.js")
def service_worker():
    return send_from_directory(".", "service-worker.js", mimetype="application/javascript")

# =====================
# AUTH
# =====================

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("index"))

        flash("Neplatné uživatelské jméno nebo heslo.", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# =====================
# JOBS
# =====================

@app.route("/")
@login_required
def index():
    jobs = Job.query.order_by(Job.id.desc()).all()

    for job in jobs:
        job.rows = JobRow.query.filter_by(job_id=job.id).all()
        job.total_quantity = sum((r.quantity or 0) for r in job.rows)
        job.total_km = sum((r.km or 0) for r in job.rows)
        job.total_travel_time = sum((r.travel_time or 0) for r in job.rows)
        job.total_work_hours = sum((r.work_hours or 0) for r in job.rows)

    return render_template("dashboard.html", jobs=jobs)


@app.route("/create_job", methods=["POST"])
@login_required
def create_job():
    name = request.form.get("name", "").strip()

    if not name:
        flash("Zadej název zakázky.", "error")
        return redirect(url_for("index"))

    new_job = Job(name=name)
    db.session.add(new_job)
    db.session.commit()

    return redirect(url_for("index"))


@app.route("/add_row/<int:job_id>", methods=["POST"])
@login_required
def add_row(job_id):
    job = Job.query.get(job_id)

    if not job or job.closed:
        return redirect(url_for("index"))

    new_row = JobRow(
        job_id=job_id,
        date="",
        material_name="",
        quantity=0,
        document_number="",
        km=0,
        travel_time=0,
        work_hours=0,
    )

    db.session.add(new_row)
    db.session.commit()

    return redirect(url_for("index"))


@app.route("/save/<int:job_id>", methods=["POST"])
@login_required
def save(job_id):
    job = Job.query.get(job_id)

    if not job or job.closed:
        return redirect(url_for("index"))

    rows = JobRow.query.filter_by(job_id=job_id).all()

    for row in rows:
        row.date = request.form.get(f"date_{row.id}")
        row.material_name = request.form.get(f"material_name_{row.id}")
        row.quantity = float(request.form.get(f"quantity_{row.id}") or 0)
        row.document_number = request.form.get(f"document_number_{row.id}")
        row.km = float(request.form.get(f"km_{row.id}") or 0)
        row.travel_time = float(request.form.get(f"travel_time_{row.id}") or 0)
        row.work_hours = float(request.form.get(f"work_hours_{row.id}") or 0)

    db.session.commit()
    flash("Zakázka uložena.", "success")
    return redirect(url_for("index"))


@app.route("/close/<int:job_id>")
@login_required
def close_job(job_id):
    job = Job.query.get(job_id)

    if job and current_user.role == "admin":
        job.closed = True
        db.session.commit()

    return redirect(url_for("index"))


@app.route("/export/<int:job_id>")
@login_required
def export(job_id):
    rows = JobRow.query.filter_by(job_id=job_id).all()

    data = []
    for r in rows:
        data.append({
            "Datum": r.date,
            "Materiál": r.material_name,
            "Množství": r.quantity,
            "Číslo dokladu": r.document_number,
            "Km": r.km,
            "Čas na cestě": r.travel_time,
            "Odpracované hodiny": r.work_hours,
        })

    df = pd.DataFrame(data)
    filename = f"zakazka_{job_id}.xlsx"
    df.to_excel(filename, index=False)

    return send_file(filename, as_attachment=True)

# =====================
# USER MANAGEMENT
# =====================

@app.route("/users")
@login_required
def users():
    if current_user.role != "admin":
        flash("Do správy uživatelů má přístup jen admin.", "error")
        return redirect(url_for("index"))

    all_users = User.query.order_by(User.id.asc()).all()
    return render_template("users.html", users=all_users)


@app.route("/add_user", methods=["POST"])
@login_required
def add_user():
    if current_user.role != "admin":
        flash("Do správy uživatelů má přístup jen admin.", "error")
        return redirect(url_for("index"))

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "user")

    if not username or not password:
        flash("Vyplň uživatelské jméno i heslo.", "error")
        return redirect(url_for("users"))

    if role not in {"admin", "user"}:
        role = "user"

    if User.query.filter_by(username=username).first():
        flash("Uživatel už existuje.", "error")
        return redirect(url_for("users"))

    new_user = User(username=username, role=role)
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    flash("Uživatel byl vytvořen.", "success")
    return redirect(url_for("users"))


@app.route("/delete_user/<int:user_id>")
@login_required
def delete_user(user_id):
    if current_user.role != "admin":
        flash("Do správy uživatelů má přístup jen admin.", "error")
        return redirect(url_for("index"))

    user = User.query.get_or_404(user_id)

    if user.username == "admin":
        flash("Hlavního admina nelze smazat.", "error")
        return redirect(url_for("users"))

    db.session.delete(user)
    db.session.commit()

    flash("Uživatel byl smazán.", "success")
    return redirect(url_for("users"))

# =====================
# RUN
# =====================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
