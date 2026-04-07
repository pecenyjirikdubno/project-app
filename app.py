from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pandas as pd
import os

app = Flask(__name__)

# ---------------- CONFIG ----------------
app.config['SECRET_KEY'] = 'your_secret_key'

# Railway / local fallback
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    "DATABASE_URL",
    "sqlite:///database.db"
)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# ---------------- MODELY ----------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(10))


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    closed = db.Column(db.Boolean, default=False)


class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20))
    material_code = db.Column(db.String(50))
    document_number = db.Column(db.String(50))
    supplier = db.Column(db.String(100))
    quantity = db.Column(db.Float)
    description = db.Column(db.String(200))
    hours = db.Column(db.Float)
    km = db.Column(db.Float)
    travel_time = db.Column(db.String(20))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))


# ---------------- LOGIN ----------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(
            username=request.form['username'],
            password=request.form['password']
        ).first()

        if user:
            login_user(user)
            return redirect(url_for('dashboard'))

        flash('Chybné údaje')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ---------------- DASHBOARD ----------------
@app.route('/')
@login_required
def dashboard():
    projects = Project.query.all()
    return render_template('dashboard.html', projects=projects)


@app.route('/create_project', methods=['POST'])
@login_required
def create_project():
    name = request.form['name']
    db.session.add(Project(name=name))
    db.session.commit()
    return redirect(url_for('dashboard'))


# ---------------- PROJECT ----------------
@app.route('/project/<int:project_id>')
@login_required
def project(project_id):
    project = Project.query.get_or_404(project_id)
    entries = Entry.query.filter_by(project_id=project_id).all()
    return render_template('project.html', project=project, entries=entries)


# ---------------- ADD ENTRY ----------------
@app.route('/add_empty_entry/<int:project_id>')
@login_required
def add_empty_entry(project_id):
    project = Project.query.get(project_id)

    if project and not project.closed:
        new_entry = Entry(
            date='',
            material_code='',
            document_number='',
            supplier='',
            quantity=0,
            description='',
            hours=0,
            km=0,
            travel_time='',
            project_id=project_id
        )
        db.session.add(new_entry)
        db.session.commit()

    return redirect(url_for('project', project_id=project_id))


# ---------------- EDIT ENTRY (AUTOSAVE) ----------------
@app.route('/edit_entry/<int:id>', methods=['POST'])
@login_required
def edit_entry(id):
    entry = Entry.query.get(id)

    if entry:
        entry.date = request.form['date']
        entry.material_code = request.form['material_code']
        entry.document_number = request.form['document_number']
        entry.supplier = request.form['supplier']
        entry.quantity = request.form['quantity']
        entry.description = request.form['description']
        entry.hours = request.form['hours']
        entry.km = request.form['km']
        entry.travel_time = request.form['travel_time']

        db.session.commit()

    return '', 204


# ---------------- DELETE ENTRY ----------------
@app.route('/delete_entry/<int:id>')
@login_required
def delete_entry(id):
    if current_user.role == 'admin':
        entry = Entry.query.get(id)
        if entry:
            db.session.delete(entry)
            db.session.commit()

    return redirect(request.referrer)


# ---------------- CLOSE PROJECT ----------------
@app.route('/close_project/<int:project_id>')
@login_required
def close_project(project_id):
    project = Project.query.get(project_id)

    if current_user.role == 'admin' and project:
        project.closed = True
        db.session.commit()

    return redirect(url_for('project', project_id=project_id))


# ---------------- EXPORT ----------------
@app.route('/export/<int:project_id>')
@login_required
def export(project_id):
    entries = Entry.query.filter_by(project_id=project_id).all()

    data = []
    for e in entries:
        data.append({
            'Datum': e.date,
            'Kód materiálu': e.material_code,
            'Doklad': e.document_number,
            'Dodavatel': e.supplier,
            'Množství': e.quantity,
            'Popis': e.description,
            'Hodiny': e.hours,
            'KM': e.km,
            'Cesta': e.travel_time
        })

    if not data:
        return "Žádná data k exportu"

    df = pd.DataFrame(data)
    filename = f'export_{project_id}.xlsx'
    df.to_excel(filename, index=False)

    return f"Export hotov: {filename}"


# ---------------- INIT DB ----------------
with app.app_context():
    db.create_all()

    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password='admin123', role='admin')
        db.session.add(admin)
        db.session.commit()


# ---------------- START ----------------
if __name__ == "__main__":
    app.run()