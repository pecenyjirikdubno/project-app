rom flask import Flask, render_template, request, redirect, send_file
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key'

# =====================
# DATABASE (Railway SAFE)
# =====================

database_url = os.environ.get("DATABASE_URL")

if not database_url:
    database_url = "sqlite:///database.db"

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

    date = db.Column(db.String(20))             # datum
    material_name = db.Column(db.String(200))

    quantity = db.Column(db.Float)              # množství
    document_number = db.Column(db.String(100))# číslo dokladu

    km = db.Column(db.Float)                   # km
    travel_time = db.Column(db.Float)          # čas na cestě

    work_hours = db.Column(db.Float)           # odpracované hodiny

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
        date="",
        material_name="",
        quantity=0,
        document_number="",
        km=0,
        travel_time=0,
        work_hours=0
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
        row.date = request.form.get(f"date_{row.id}")
        row.material_name = request.form.get(f"material_name_{row.id}")
        row.quantity = float(request.form.get(f"quantity_{row.id}") or 0)
        row.document_number = request.form.get(f"document_number_{row.id}")
        row.km = float(request.form.get(f"km_{row.id}") or 0)
        row.travel_time = float(request.form.get(f"travel_time_{row.id}") or 0)
        row.work_hours = float(request.form.get(f"work_hours_{row.id}") or 0)

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
        data.append({
            "Datum": r.date,
            "Materiál": r.material_name,
            "Množství": r.quantity,
            "Číslo dokladu": r.document_number,
            "Km": r.km,
            "Čas na cestě": r.travel_time,
            "Odpracované hodiny": r.work_hours
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
