from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from kavenegar import *
from datetime import datetime
import jdatetime

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
api = KavenegarAPI('324B30764337784D544C6C356F426149734F71364B774D49565562737776797957675A63554643554C416B3D')

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
    return render_template("index.html", classes=classes)

@app.route("/class/<int:class_id>")
@login_required
def view_class(class_id):
    class_ = Class.query.get_or_404(class_id)
    students = Student.query.filter_by(class_id=class_id).order_by(Student.firstname).all()
    return render_template("class_detail.html", class_=class_, students=students)

@app.route("/add_class", methods=["GET", "POST"])
@login_required
def add_class():
    if request.method == "POST":
        classname = request.form["classname"]
        if classname:
            existing = Class.query.filter_by(name=classname).first()
            if not existing:
                new_class = Class(name=classname)
                db.session.add(new_class)
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
            student = Student(firstname=firstname, lastname=lastname,
                              parent_number=parent_number, class_id=class_id)
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

@app.route("/absent/<int:student_id>")
@login_required
def absent(student_id):
    student = Student.query.get_or_404(student_id)
    current_time = datetime.now()
    current_time_str = current_time.strftime("%H:%M")
    persian_date = jdatetime.datetime.fromgregorian(datetime=current_time).strftime("%Y/%m/%d")

    message_text = f"درود و وقت بخیر 🌹\nفرزند شما ({student.firstname} {student.lastname} - کلاس {student.class_.name}) در ساعت {current_time_str} در مدرسه حضور نداشتند.\nلطفا فردا به مدرسه مراجعه نمایید.\nبا تشکر 🙏"

    params = {
        'sender': '2000660110',
        'receptor': student.parent_number,
        'message': message_text
    }
    try:
        response = api.sms_send(params)
        flash(f"✅ پیام غیبت برای {student.firstname} {student.lastname} ارسال شد.", "success")
    except Exception as e:
        flash(f"❌ خطا در ارسال پیام: {e}", "danger")

    return redirect(url_for("view_class", class_id=student.class_id))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
