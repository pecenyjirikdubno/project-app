from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import io
from openpyxl import Workbook

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret123'

# Railway DB automaticky nastaví DATABASE_URL
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///database.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# -----------------------
# MODELY
# -----------------------

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(10))  # admin / user


class Zakazka(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    closed = db.Column(db.Boolean, default=False)


class Zaznam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    zakazka_id = db.Column(db.Integer, db.ForeignKey('zakazka.id'))
    datum = db.Column(db.String(50))
    material_kod = db.Column(db.String(100))
    doklad = db.Column(db.String(100))
    dodavatel = db.Column(db.String(100))
    mnozstvi = db.Column(db.String(50))
    popis = db.Column(db.String(200))
    hodiny = db.Column(db.String(50))
    km = db.Column(db.String(50))
    cas_cesta = db.Column(db.String(50))


# -----------------------
# LOGIN
# -----------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -----------------------
# INIT DB
# -----------------------

with app.app_context():
    db.create_all()

    # vytvoření admina při prvním spuštění
    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            password=generate_password_hash("admin"),
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()


# -----------------------
# ROUTY
# -----------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and check_password_hash(user.password, request.form["password"]):
            login_user(user)
            return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    zakazky = Zakazka.query.all()
    return render_template("dashboard.html", zakazky=zakazky)


@app.route("/create", methods=["POST"])
@login_required
def create():
    name = request.form["name"]
    db.session.add(Zakazka(name=name))
    db.session.commit()
    return redirect(url_for("dashboard"))


@app.route("/zakazka/<int:id>")
@login_required
def zakazka(id):
    zakazka = Zakazka.query.get_or_404(id)
    zaznamy = Zaznam.query.filter_by(zakazka_id=id).all()
    return render_template("zakazka.html", zakazka=zakazka, zaznamy=zaznamy)


@app.route("/add/<int:id>", methods=["POST"])
@login_required
def add(id):
    if Zakazka.query.get(id).closed:
        return redirect(url_for("zakazka", id=id))

    z = Zaznam(
        zakazka_id=id,
        datum=request.form.get("datum"),
        material_kod=request.form.get("material_kod"),
        doklad=request.form.get("doklad"),
        dodavatel=request.form.get("dodavatel"),
        mnozstvi=request.form.get("mnozstvi"),
        popis=request.form.get("popis"),
        hodiny=request.form.get("hodiny"),
        km=request.form.get("km"),
        cas_cesta=request.form.get("cas_cesta")
    )
    db.session.add(z)
    db.session.commit()

    return redirect(url_for("zakazka", id=id))


@app.route("/delete/<int:id>")
@login_required
def delete(id):
    z = Zaznam.query.get_or_404(id)
    if current_user.role == "admin":
        db.session.delete(z)
        db.session.commit()
    return redirect(request.referrer)


@app.route("/close/<int:id>")
@login_required
def close(id):
    zakazka = Zakazka.query.get_or_404(id)
    if current_user.role == "admin":
        zakazka.closed = True
        db.session.commit()
    return redirect(url_for("zakazka", id=id))


# -----------------------
# EXPORT DO EXCELU
# -----------------------

@app.route('/export/<int:zakazka_id>')
@login_required
def export(zakazka_id):
    zakazka = Zakazka.query.get_or_404(zakazka_id)
    zaznamy = Zaznam.query.filter_by(zakazka_id=zakazka_id).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Zakázka"

    ws.append([
        "Datum",
        "Kód materiálu",
        "Číslo dokladu",
        "Dodavatel",
        "Množství",
        "Popis",
        "Hodiny",
        "Km",
        "Čas na cestě"
    ])

    for z in zaznamy:
        ws.append([
            z.datum,
            z.material_kod,
            z.doklad,
            z.dodavatel,
            z.mnozstvi,
            z.popis,
            z.hodiny,
            z.km,
            z.cas_cesta
        ])

    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    return send_file(
        file_stream,
        as_attachment=True,
        download_name=f"zakazka_{zakazka_id}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# -----------------------
# RUN
# -----------------------

if __name__ == "__main__":
    app.run(debug=True)
