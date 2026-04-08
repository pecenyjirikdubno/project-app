
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
    return redirect(url_for("materials"))


@app.route("/close/<int:job_id>")
@login_required
def close_job(job_id):
    job = Job.query.get(job_id)

    if job and current_user.role == "admin":
        job.closed = True
        db.session.commit()

    return redirect(url_for("materials"))


@app.route("/export/<int:job_id>")
@login_required
def export(job_id):
    rows = JobRow.query.filter_by(job_id=job_id).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Materiál"

    ws.append([
        "Datum",
        "Materiál",
        "Množství",
        "Číslo dokladu",
        "Km",
        "Čas na cestě",
        "Odpracované hodiny",
    ])

    for r in rows:
        ws.append([
            r.date,
            r.material_name,
            r.quantity,
            r.document_number,
            r.km,
            r.travel_time,
            r.work_hours,
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"zakazka_{job_id}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# =====================
# DOCHÁZKA
# =====================


@app.route("/attendance")
@login_required
def attendance():
    selected_month = request.args.get("month")

    if selected_month:
        try:
            year, month = map(int, selected_month.split("-"))
        except ValueError:
            current = today_local()
            year, month = current.year, current.month
    else:
        current = today_local()
        year, month = current.year, current.month

    month_start = first_day_of_month(year, month)
    month_end = next_month_first_day(year, month)

    if current_user.role == "admin":
        records = (
            Attendance.query.filter(
                Attendance.work_date >= month_start,
                Attendance.work_date < month_end,
            )
            .order_by(Attendance.work_date.desc(), Attendance.id.desc())
            .all()
        )
    else:
        records = (
            Attendance.query.filter(
                Attendance.user_id == current_user.id,
                Attendance.work_date >= month_start,
                Attendance.work_date < month_end,
            )
            .order_by(Attendance.work_date.desc(), Attendance.id.desc())
            .all()
        )

    user_map = {}
    if current_user.role == "admin":
        user_ids = {r.user_id for r in records}
        if user_ids:
            users = User.query.filter(User.id.in_(user_ids)).all()
            user_map = {u.id: u.username for u in users}

    return render_template(
        "attendance.html",
        records=records,
        today=today_local().isoformat(),
        selected_month=f"{year:04d}-{month:02d}",
        user_map=user_map,
        can_user_edit_attendance=can_user_edit_attendance,
        time_to_str=time_to_str,
    )


@app.route("/attendance/create_day", methods=["POST"])
@login_required
def create_attendance_day():
    work_date_raw = request.form.get("work_date", "").strip()

    if not work_date_raw:
        flash("Vyber datum.", "error")
        return redirect(url_for("attendance"))

    try:
        work_date = datetime.strptime(work_date_raw, "%Y-%m-%d").date()
    except ValueError:
        flash("Neplatné datum.", "error")
        return redirect(url_for("attendance"))

    existing = Attendance.query.filter_by(
        user_id=current_user.id,
        work_date=work_date
    ).first()

    if existing:
        flash("Záznam pro toto datum už existuje.", "error")
        return redirect(url_for("attendance"))

    record = Attendance(
        user_id=current_user.id,
        work_date=work_date,
        created_at=now_local(),
        updated_at=now_local(),
    )
    db.session.add(record)
    db.session.commit()

    flash("Den docházky byl vytvořen.", "success")
    return redirect(url_for("attendance"))


@app.route("/attendance/user_update/<int:record_id>", methods=["POST"])
@login_required
def attendance_user_update(record_id):
    record = Attendance.query.get_or_404(record_id)

    if not can_user_edit_attendance(record):
        flash("Tento záznam už nemůžeš upravovat.", "error")
        return redirect(url_for("attendance"))

    start_time_raw = request.form.get("start_time", "").strip()
    end_time_raw = request.form.get("end_time", "").strip()

    new_start = parse_time_hhmm(start_time_raw)
    new_end = parse_time_hhmm(end_time_raw)

    if start_time_raw and new_start is None:
        flash("Neplatný čas nástupu.", "error")
        return redirect(url_for("attendance"))

    if end_time_raw and new_end is None:
        flash("Neplatný čas ukončení.", "error")
        return redirect(url_for("attendance"))

    if record.start_time != new_start and new_start is not None:
        record.start_recorded_at = now_local()

    if record.end_time != new_end and new_end is not None:
        record.end_recorded_at = now_local()

    record.start_time = new_start
    record.end_time = new_end
    record.updated_at = now_local()

    db.session.commit()
    flash("Docházka uložena.", "success")
    return redirect(url_for("attendance"))


@app.route("/attendance/admin_update/<int:record_id>", methods=["POST"])
@login_required
def attendance_admin_update(record_id):
    if not admin_required():
        return redirect(url_for("attendance"))

    record = Attendance.query.get_or_404(record_id)

    work_date_raw = request.form.get("work_date", "").strip()
    start_time_raw = request.form.get("start_time", "").strip()
    end_time_raw = request.form.get("end_time", "").strip()

    try:
        record.work_date = datetime.strptime(work_date_raw, "%Y-%m-%d").date()
    except ValueError:
        flash("Neplatné datum.", "error")
        return redirect(url_for("attendance"))

    new_start = parse_time_hhmm(start_time_raw)
    new_end = parse_time_hhmm(end_time_raw)

    if start_time_raw and new_start is None:
        flash("Neplatný čas nástupu.", "error")
        return redirect(url_for("attendance"))

    if end_time_raw and new_end is None:
        flash("Neplatný čas ukončení.", "error")
        return redirect(url_for("attendance"))

    if record.start_time != new_start and new_start is not None:
        record.start_recorded_at = now_local()

    if record.end_time != new_end and new_end is not None:
        record.end_recorded_at = now_local()

    record.start_time = new_start
    record.end_time = new_end
    record.updated_at = now_local()

    db.session.commit()
    flash("Docházka upravena.", "success")
    return redirect(url_for("attendance"))


@app.route("/attendance/export/all/excel")
@login_required
def attendance_export_all_excel():
    if not admin_required():
        return redirect(url_for("attendance"))

    records = Attendance.query.order_by(Attendance.work_date.desc(), Attendance.id.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Docházka"

    ws.append([
        "Uživatel",
        "Datum docházky",
        "Nástup",
        "Ukončení",
        "Vytvořeno",
        "Naposledy upraveno",
        "Zápis nástupu proveden",
        "Zápis ukončení proveden",
    ])

    user_ids = {r.user_id for r in records}
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {u.id: u.username for u in users}

    for r in records:
        ws.append([
            user_map.get(r.user_id, ""),
            r.work_date.isoformat() if r.work_date else "",
            time_to_str(r.start_time),
            time_to_str(r.end_time),
            datetime_to_str(r.created_at),
            datetime_to_str(r.updated_at),
            datetime_to_str(r.start_recorded_at),
            datetime_to_str(r.end_recorded_at),
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="dochazka_vse.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/attendance/export/monthly/excel")
@login_required
def attendance_export_monthly_excel():
    if not admin_required():
        return redirect(url_for("attendance"))

    month_raw = request.args.get("month")
    if not month_raw:
        month_raw = today_local().strftime("%Y-%m")

    year, month = map(int, month_raw.split("-"))
    month_start = first_day_of_month(year, month)
    month_end = next_month_first_day(year, month)

    records = (
        Attendance.query.filter(
            Attendance.work_date >= month_start,
            Attendance.work_date < month_end,
        )
        .order_by(Attendance.work_date.asc(), Attendance.id.asc())
        .all()
    )

    user_ids = {r.user_id for r in records}
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {u.id: u.username for u in users}

    wb = Workbook()
    ws = wb.active
    ws.title = f"{year}-{month:02d}"

    ws.append([
        "Uživatel",
        "Datum docházky",
        "Nástup",
        "Ukončení",
        "Vytvořeno",
        "Naposledy upraveno",
        "Zápis nástupu proveden",
        "Zápis ukončení proveden",
    ])

    for r in records:
        ws.append([
            user_map.get(r.user_id, ""),
            r.work_date.isoformat() if r.work_date else "",
            time_to_str(r.start_time),
            time_to_str(r.end_time),
            datetime_to_str(r.created_at),
            datetime_to_str(r.updated_at),
            datetime_to_str(r.start_recorded_at),
            datetime_to_str(r.end_recorded_at),
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"dochazka_{year}_{month:02d}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/attendance/export/monthly/pdf")
@login_required
def attendance_export_monthly_pdf():
    if not admin_required():
        return redirect(url_for("attendance"))

    month_raw = request.args.get("month")
    if not month_raw:
        month_raw = today_local().strftime("%Y-%m")

    year, month = map(int, month_raw.split("-"))
    month_start = first_day_of_month(year, month)
    month_end = next_month_first_day(year, month)

    records = (
        Attendance.query.filter(
            Attendance.work_date >= month_start,
            Attendance.work_date < month_end,
        )
        .order_by(Attendance.work_date.asc(), Attendance.id.asc())
        .all()
    )

    user_ids = {r.user_id for r in records}
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {u.id: u.username for u in users}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Paragraph(f"Docházka za měsíc {year}-{month:02d}", styles["Title"]))
    elements.append(Spacer(1, 12))

    table_data = [[
        "Uživatel",
        "Datum",
        "Nástup",
        "Ukončení",
        "Vytvořeno",
        "Upraveno",
        "Zápis nástupu",
        "Zápis ukončení",
    ]]

    for r in records:
        table_data.append([
            user_map.get(r.user_id, ""),
            r.work_date.isoformat() if r.work_date else "",
            time_to_str(r.start_time),
            time_to_str(r.end_time),
            datetime_to_str(r.created_at),
            datetime_to_str(r.updated_at),
            datetime_to_str(r.start_recorded_at),
            datetime_to_str(r.end_recorded_at),
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"dochazka_{year}_{month:02d}.pdf",
        mimetype="application/pdf",
    )

# =====================
# ADMIN SQL BACKUP / RESTORE
# =====================


@app.route("/admin/db-backup")
@login_required
def admin_db_backup():
    if not admin_required():
        return redirect(url_for("dashboard"))

    if not ensure_pg_tool("pg_dump"):
        flash("Na serveru není dostupný nástroj pg_dump.", "error")
        return redirect(url_for("dashboard"))

    conn = get_pg_connection_parts()
    dump_name = f"backup_{now_local().strftime('%Y-%m-%d_%H-%M-%S')}.sql"

    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        env = os.environ.copy()
        if conn["password"]:
            env["PGPASSWORD"] = conn["password"]

        cmd = [
            "pg_dump",
            "-h", conn["host"],
            "-p", conn["port"],
            "-U", conn["user"],
            "-d", conn["dbname"],
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "-f", tmp_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, env=env)

        if result.returncode != 0:
            flash(f"Záloha databáze selhala: {result.stderr}", "error")
            return redirect(url_for("dashboard"))

        with open(tmp_path, "rb") as f:
            data = io.BytesIO(f.read())

        data.seek(0)
        return send_file(
            data,
            as_attachment=True,
            download_name=dump_name,
            mimetype="application/sql",
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.route("/admin/db-restore", methods=["POST"])
@login_required
def admin_db_restore():
    if not admin_required():
        return redirect(url_for("dashboard"))

    if not ensure_pg_tool("psql"):
        flash("Na serveru není dostupný nástroj psql.", "error")
        return redirect(url_for("dashboard"))

    uploaded_file = request.files.get("backup_file")

    if not uploaded_file or uploaded_file.filename == "":
        flash("Vyber SQL soubor pro obnovu.", "error")
        return redirect(url_for("dashboard"))

    if not uploaded_file.filename.lower().endswith(".sql"):
        flash("Obnovit lze jen ze souboru .sql", "error")
        return redirect(url_for("dashboard"))

    conn = get_pg_connection_parts()

    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
        tmp_path = tmp.name
        uploaded_file.save(tmp_path)

    try:
        db.session.remove()
        db.engine.dispose()

        env = os.environ.copy()
        if conn["password"]:
            env["PGPASSWORD"] = conn["password"]

        cmd = [
            "psql",
            "-h", conn["host"],
            "-p", conn["port"],
            "-U", conn["user"],
            "-d", conn["dbname"],
            "-v", "ON_ERROR_STOP=1",
            "-f", tmp_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, env=env)

        db.engine.dispose()

        if result.returncode != 0:
            flash(f"Obnova databáze selhala: {result.stderr}", "error")
            return redirect(url_for("dashboard"))

        flash("Databáze byla úspěšně obnovena ze SQL dumpu.", "success")
        return redirect(url_for("dashboard"))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# =====================
# USER MANAGEMENT
# =====================


@app.route("/users")
@login_required
def users():
    if current_user.role != "admin":
        flash("Do správy uživatelů má přístup jen admin.", "error")
        return redirect(url_for("dashboard"))

    all_users = User.query.order_by(User.id.asc()).all()
    return render_template("users.html", users=all_users)


@app.route("/add_user", methods=["POST"])
@login_required
def add_user():
    if current_user.role != "admin":
        flash("Do správy uživatelů má přístup jen admin.", "error")
        return redirect(url_for("dashboard"))

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
        return redirect(url_for("dashboard"))

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
