from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from kavenegar import *
from datetime import datetime, date
import jdatetime
import pytz  # برای تایم زون تهران
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# --- DATABASE CONFIG ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELS ---
class Class(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    students = db.relationship("Student", backref="class_", lazy=True, cascade="all, delete")

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(50), nullable=False)
    lastname = db.Column(db.String(50), nullable=False)
    parent_number = db.Column(db.String(20), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("class.id"), nullable=False)
    attendances = db.relationship("Attendance", backref="student", lazy=True, cascade="all, delete")

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)

# --- تابع ساعت تهران ---
def now_tehran():
    tz = pytz.timezone("Asia/Tehran")
    return datetime.now(tz)

# --- فیلتر تبدیل تاریخ میلادی به شمسی ---
def to_jalali(date_obj):
    if not date_obj:
        return ""
    if hasattr(date_obj, "tzinfo"):
        date_obj = date_obj.replace(tzinfo=None)
    return jdatetime.datetime.fromgregorian(datetime=date_obj).strftime('%Y/%m/%d')

app.jinja_env.filters['to_jalali'] = to_jalali

# --- LOGIN CONFIG ---
USERNAME = 'mehrab'
PASSWORD = '13878700'

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- KAVENEGAR CONFIG ---
api = KavenegarAPI('44357543787965376E467856632B64397A4E59592F6E6170665172726B4C4B33513345432F35775A4B65303D')

# --- ROUTES ---
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for("index"))
        else:
            error = "نام کاربری یا رمز عبور اشتباه است!"
            flash(error, "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route("/")
@login_required
def index():
    classes = Class.query.order_by(Class.name).all()
    today = now_tehran().date()
    absents_today = Attendance.query.join(Student).join(Class).filter(Attendance.date==today).all()
    return render_template("index.html", classes=classes, absents_today=absents_today)

# --- VIEW CLASS با جستجوی اختصاصی ---
@app.route("/class/<int:class_id>")
@login_required
def view_class(class_id):
    class_ = Class.query.get_or_404(class_id)
    search_query = request.args.get("search", "").strip()

    query = Student.query.filter_by(class_id=class_id)
    if search_query:
        query = query.filter(
            (Student.firstname.ilike(f"%{search_query}%")) |
            (Student.lastname.ilike(f"%{search_query}%"))
        )

    # --- تابع مرتب‌سازی فارسی ---
    def farsi_sort_key(text):
        alphabet = "اآبپتثجچحخدذرزسشصضطظعغفقکگلمنوهی"
        order = {ch: i for i, ch in enumerate(alphabet)}
        return [order.get(ch, len(alphabet)) for ch in text]

    # ابتدا همه دانش‌آموزها رو بگیر
    students = query.all()

    # مرتب‌سازی بر اساس نام خانوادگی سپس نام (بر اساس الفبای فارسی)
    students = sorted(
        students,
        key=lambda s: (farsi_sort_key(s.lastname), farsi_sort_key(s.firstname))
    )

    return render_template("class_detail.html", class_=class_, students=students)

@app.route("/add_class", methods=["GET", "POST"])
@login_required
def add_class():
    if request.method == "POST":
        classname = request.form["classname"]
        if classname and not Class.query.filter_by(name=classname).first():
            db.session.add(Class(name=classname))
            db.session.commit()
            flash(f"کلاس {classname} اضافه شد ✅", "success")
        return redirect(url_for("index"))
    return render_template("add_class.html")

@app.route("/delete_class/<int:id>")
@login_required
def delete_class(id):
    class_ = Class.query.get_or_404(id)
    db.session.delete(class_)
    db.session.commit()
    flash("کلاس حذف شد ❌", "danger")
    return redirect(url_for("index"))

@app.route("/add_student/<int:class_id>", methods=["GET", "POST"])
@login_required
def add_student(class_id):
    class_ = Class.query.get_or_404(class_id)
    if request.method == "POST":
        firstname = request.form["firstname"]
        lastname = request.form["lastname"]
        parent_number = request.form["parent_number"]
        if firstname and lastname and parent_number:
            student = Student(firstname=firstname, lastname=lastname, parent_number=parent_number, class_id=class_id)
            db.session.add(student)
            db.session.commit()
            flash(f"دانش‌آموز {firstname} {lastname} اضافه شد ✅", "success")
        return redirect(url_for("view_class", class_id=class_id))
    return render_template("add_student.html", class_=class_)

@app.route("/delete_student/<int:id>")
@login_required
def delete_student(id):
    student = Student.query.get_or_404(id)
    class_id = student.class_id
    db.session.delete(student)
    db.session.commit()
    flash("دانش‌آموز حذف شد ❌", "danger")
    return redirect(url_for("view_class", class_id=class_id))

@app.route("/edit_student/<int:id>", methods=["GET", "POST"])
@login_required
def edit_student(id):
    student = Student.query.get_or_404(id)
    if request.method == "POST":
        student.firstname = request.form["firstname"]
        student.lastname = request.form["lastname"]
        student.parent_number = request.form["parent_number"]
        db.session.commit()
        flash("✅ اطلاعات دانش‌آموز ویرایش شد", "success")
        return redirect(url_for("view_class", class_id=student.class_id))
    return render_template("edit_student.html", student=student)

# --- مسیر غیبت AJAX ---
@app.route("/absent/<int:student_id>", methods=["POST"])
@login_required
def absent(student_id):
    student = Student.query.get_or_404(student_id)
    today = now_tehran().date()
    now_time = now_tehran().time()
    attendance = Attendance(student_id=student.id, date=today, time=now_time)
    db.session.add(attendance)
    db.session.commit()

    dt = now_tehran().replace(tzinfo=None)
    persian_datetime = jdatetime.datetime.fromgregorian(datetime=dt)
    persian_date_str = persian_datetime.strftime("%Y/%m/%d")
    persian_time_str = persian_datetime.strftime("%H:%M")

    message_text = f"درود 🌹\nفرزند شما ({student.firstname} {student.lastname} - کلاس {student.class_.name}) در تاریخ {persian_date_str} ساعت {persian_time_str} در مدرسه حضور نداشتند.\nبا تشکر 🙏"
    try:
        api.sms_send({
            'sender': '2000300261',
            'receptor': student.parent_number,
            'message': message_text
        })
        flash(f"✅ پیام غیبت برای {student.firstname} ارسال شد.", "success")
    except Exception as e:
        flash(f"❌ خطا در ارسال پیام: {e}", "danger")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return '', 204
    return redirect(url_for("view_class", class_id=student.class_id))

@app.route("/send_message", methods=["POST"])
@login_required
def send_message():
    parent_number = request.form["parent_number"]
    message = request.form["message"]
    try:
        api.sms_send({
            'sender': '2000300261',
            'receptor': parent_number,
            'message': message
        })
        flash("✅ پیام شما با موفقیت برای والدین ارسال شد.", "success")
    except Exception as e:
        flash(f"❌ خطا در ارسال پیام: {e}", "danger")
    return redirect(request.referrer)

# --- پیام گروهی برای یک کلاس ---
@app.route("/send_class_message/<int:class_id>", methods=["GET", "POST"])
@login_required
def send_class_message(class_id):
    class_ = Class.query.get_or_404(class_id)
    if request.method == "POST":
        message = request.form["message"]
        if not message.strip():
            flash("❌ متن پیام نمی‌تواند خالی باشد", "danger")
            return redirect(url_for("send_class_message", class_id=class_id))

        parent_numbers = [s.parent_number for s in class_.students if s.parent_number]

        if not parent_numbers:
            flash("❌ شماره‌ای برای والدین این کلاس ثبت نشده است", "danger")
            return redirect(url_for("view_class", class_id=class_id))

        try:
            api.sms_send({
                'sender': '2000300261',
                'receptor': ",".join(parent_numbers),
                'message': message
            })
            flash(f"✅ پیام برای همه والدین کلاس {class_.name} ارسال شد.", "success")
        except Exception as e:
            flash(f"❌ خطا در ارسال پیام: {e}", "danger")

        return redirect(url_for("view_class", class_id=class_id))

    return render_template("send_class_message.html", class_=class_)

# --- جستجوی غیبت دانش‌آموز ---
@app.route("/student_absences", methods=["GET", "POST"])
@login_required
def student_absences():
    search_query = request.form.get("search", "").strip() if request.method == "POST" else ""
    class_query = request.form.get("class_name", "").strip() if request.method == "POST" else ""

    student_attendance_list = []

    query = Student.query.join(Class)

    if search_query:
        query = query.filter(
            (Student.firstname.ilike(f"%{search_query}%")) |
            (Student.lastname.ilike(f"%{search_query}%"))
        )
    if class_query:
        query = query.filter(Class.name.ilike(f"%{class_query}%"))

    students = query.order_by(Student.firstname, Student.lastname).all()

    for student in students:
        attendances = Attendance.query.filter_by(student_id=student.id).order_by(
            Attendance.date.desc(), Attendance.time.desc()
        ).all()
        student_attendance_list.append({"student": student, "attendances": attendances})

    return render_template("student_absences.html",
                           student_attendance_list=student_attendance_list,
                           search_query=search_query,
                           class_query=class_query)

# --- حذف غیبت ---
@app.route("/delete_absence", methods=["POST"])
@login_required
def delete_absence():
    data = request.get_json()
    if not data or 'id' not in data:
        return {"success": False, "error": "missing id"}, 400

    absence_id = data['id']
    absence = Attendance.query.get(absence_id)
    if not absence:
        return {"success": False, "error": "not found"}, 404

    db.session.delete(absence)
    db.session.commit()
    return {"success": True}

# --- جابجایی دانش‌آموز بین کلاس‌ها ---
@app.route("/get_classes_for_transfer/<int:student_id>")
@login_required
def get_classes_for_transfer(student_id):
    student = Student.query.get_or_404(student_id)
    classes = Class.query.filter(Class.id != student.class_id).all()
    return jsonify({
        "classes": [{"id": c.id, "name": c.name} for c in classes]
    })

@app.route("/transfer_student_ajax/<int:student_id>", methods=["POST"])
@login_required
def transfer_student_ajax(student_id):
    student = Student.query.get_or_404(student_id)
    data = request.get_json()
    new_class_id = data.get("new_class_id")
    if not new_class_id:
        return jsonify({"success": False, "error": "کلاس جدید انتخاب نشده"}), 400
    student.class_id = int(new_class_id)
    db.session.commit()
    return jsonify({"success": True})

# --- دانلود دیتابیس ---
@app.route("/download_db")
@login_required
def download_db():
    db_path = os.path.join(app.root_path, "school.db")
    if os.path.exists(db_path):
        return send_file(db_path, as_attachment=True)
    else:
        flash("❌ دیتابیس پیدا نشد.", "danger")
        return redirect(url_for("index"))

# --- ROUTE PING ---
@app.route("/ping")
def ping():
    return "pong", 200

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)
