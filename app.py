from flask import Flask, render_template, request, redirect, send_file
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key'

# =====================
# DATABASE (Railway SAFE)
# =====================

database_url = os.environ.get("DATABASE_URL")

# fallback pro lokální běh
if not database_url:
    database_url = "sqlite:///database.db"

# fix postgres:// → postgresql://
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://")

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# =====================
# MODELY
# =====================

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    closed = db.Column(db.Boolean, default=False)

class JobRow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))

    material_name = db.Column(db.String(200))
    material_cost = db.Column(db.Float)

    transport_cost = db.Column(db.Float)

    work_hours = db.Column(db.Float)
    work_rate = db.Column(db.Float)

# =====================
# INIT DB
# =====================

with app.app_context():
    db.create_all()

# =====================
# ROUTES
# =====================

@app.route('/')
def index():
    jobs = Job.query.all()

    for job in jobs:
        job.rows = JobRow.query.filter_by(job_id=job.id).all()

    return render_template('dashboard.html', jobs=jobs)

# =====================
# CREATE JOB
# =====================

@app.route('/create_job', methods=['POST'])
def create_job():
    name = request.form.get('name')

    if not name:
        return redirect('/')

    new_job = Job(name=name)
    db.session.add(new_job)
    db.session.commit()

    return redirect('/')

# =====================
# ADD ROW
# =====================

@app.route('/add_row/<int:job_id>', methods=['POST'])
def add_row(job_id):
    new_row = JobRow(
        job_id=job_id,
        material_name="",
        material_cost=0,
        transport_cost=0,
        work_hours=0,
        work_rate=0
    )

    db.session.add(new_row)
    db.session.commit()

    return redirect('/')

# =====================
# SAVE
# =====================

@app.route('/save/<int:job_id>', methods=['POST'])
def save(job_id):
    rows = JobRow.query.filter_by(job_id=job_id).all()

    for row in rows:
        row.material_name = request.form.get(f"material_name_{row.id}")
        row.material_cost = float(request.form.get(f"material_cost_{row.id}") or 0)
        row.transport_cost = float(request.form.get(f"transport_cost_{row.id}") or 0)
        row.work_hours = float(request.form.get(f"work_hours_{row.id}") or 0)
        row.work_rate = float(request.form.get(f"work_rate_{row.id}") or 0)

    db.session.commit()
    return redirect('/')

# =====================
# CLOSE JOB
# =====================

@app.route('/close/<int:job_id>')
def close_job(job_id):
    job = Job.query.get(job_id)
    if job:
        job.closed = True
        db.session.commit()
    return redirect('/')

# =====================
# EXPORT EXCEL
# =====================

@app.route('/export/<int:job_id>')
def export(job_id):
    rows = JobRow.query.filter_by(job_id=job_id).all()

    data = []
    for r in rows:
        total_work = (r.work_hours or 0) * (r.work_rate or 0)
        total = (r.material_cost or 0) + (r.transport_cost or 0) + total_work

        data.append({
            "Materiál": r.material_name,
            "Cena materiálu": r.material_cost,
            "Doprava": r.transport_cost,
            "Hodiny": r.work_hours,
            "Sazba": r.work_rate,
            "Cena práce": total_work,
            "Celkem": total
        })

    df = pd.DataFrame(data)

    filename = f"zakazka_{job_id}.xlsx"
    df.to_excel(filename, index=False)

    return send_file(filename, as_attachment=True)

# =====================
# RUN
# =====================

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
