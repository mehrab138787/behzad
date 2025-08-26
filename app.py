from flask import Flask, render_template, request, redirect, url_for, flash, session
from kavenegar import KavenegarAPI
from datetime import datetime
import jdatetime  # برای تاریخ شمسی

app = Flask(__name__)
app.secret_key = "supersecretkey"

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

# --- DATA ---
classes = ["310"]
students = [
    {"class": "310", "firstname": "مهراب", "lastname": "عزیزی", "parent_number": "09962935294"}
]
absents_today = []

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
            error = "یوزر یا پسورد اشتباه است!"
    return '''
        <h2>Login</h2>
        <form method="post">
            <input type="text" name="username" placeholder="Username" required><br>
            <input type="password" name="password" placeholder="Password" required><br>
            <input type="submit" value="Login">
        </form>
        <p style="color:red;">{}</p>
    '''.format(error or '')

@app.route("/logout")
@login_required
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route("/")
@login_required
def index():
    students_sorted = sorted(students, key=lambda x: x['firstname'])
    return render_template("index.html", classes=classes, students=students_sorted, absents_today=absents_today)

@app.route("/add_class", methods=["GET", "POST"])
@login_required
def add_class():
    if request.method == "POST":
        classname = request.form["classname"]
        if classname and classname not in classes:
            classes.append(classname)
            flash(f"کلاس {classname} با موفقیت اضافه شد ✅", "success")
        return redirect(url_for("index"))
    return render_template("add_class.html")

@app.route("/add_student", methods=["GET", "POST"])
@login_required
def add_student():
    if request.method == "POST":
        firstname = request.form["firstname"]
        lastname = request.form["lastname"]
        parent_number = request.form["parent_number"]
        class_selected = request.form["class_selected"]

        if firstname and lastname and parent_number and class_selected:
            students.append({
                "class": class_selected,
                "firstname": firstname,
                "lastname": lastname,
                "parent_number": parent_number
            })
            flash(f"دانش‌آموز {firstname} {lastname} به کلاس {class_selected} اضافه شد ✅", "success")
        return redirect(url_for("index"))

    return render_template("add_student.html", classes=classes)

@app.route("/absent/<int:index>")
@login_required
def absent(index):
    student = students[index]
    current_time = datetime.now()
    current_time_str = current_time.strftime("%H:%M")
    persian_date = jdatetime.datetime.fromgregorian(datetime=current_time).strftime("%Y/%m/%d")

    message_text = (
        f"درود و وقت بخیر 🌹\n"
        f"فرزند شما ({student['firstname']} {student['lastname']} - کلاس {student['class']}) "
        f"در ساعت {current_time_str} در مدرسه حضور نداشتند.\n"
        f"لطفا فردا به مدرسه مراجعه نمایید.\n"
        f"با تشکر از شما 🙏\n"
        f"معاونت دبیرستان - استاد بهزاد کیومرث نجفی"
    )

    params = {
        'sender': '2000660110',
        'receptor': student["parent_number"],
        'message': message_text
    }
    try:
        api.sms_send(params)

        absents_today.append({
            "firstname": student["firstname"],
            "lastname": student["lastname"],
            "class": student["class"],
            "time": current_time_str,
            "date": persian_date
        })

        flash(f"✅ پیام غیبت برای {student['firstname']} {student['lastname']} ارسال شد.", "success")
    except Exception as e:
        flash(f"❌ خطا در ارسال پیام: {e}", "danger")

    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
