from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import sqlite3
import os
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'vision-academy-secret-2024-xyz')
DB_PATH = os.environ.get('DB_PATH', 'vision_academy.db')

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_no TEXT UNIQUE NOT NULL,
            standard TEXT NOT NULL,
            medium TEXT DEFAULT 'English',
            stream TEXT DEFAULT '',
            parent_name TEXT DEFAULT '',
            contact TEXT DEFAULT '',
            email TEXT DEFAULT '',
            address TEXT DEFAULT '',
            admission_date TEXT DEFAULT (date('now')),
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            due_date TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            grade TEXT DEFAULT '',
            assigned_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        );
        CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            standard TEXT NOT NULL,
            test_date TEXT NOT NULL,
            total_marks INTEGER NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            test_id INTEGER NOT NULL,
            marks_obtained REAL NOT NULL,
            grade TEXT DEFAULT '',
            remarks TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (test_id) REFERENCES tests(id)
        );
    ''')
    conn.commit()
    conn.close()

def grade_from_percent(p):
    if p >= 90: return 'A+'
    if p >= 80: return 'A'
    if p >= 70: return 'B+'
    if p >= 60: return 'B'
    if p >= 50: return 'C'
    if p >= 40: return 'D'
    return 'F'

class User(UserMixin):
    def __init__(self, id, name, email, password, role, created_at):
        self.id = id; self.name = name; self.email = email
        self.password = password; self.role = role; self.created_at = created_at

def get_user_by_id(uid):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
    conn.close()
    return User(row['id'],row['name'],row['email'],row['password'],row['role'],row['created_at']) if row else None

def get_user_by_email(email):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
    conn.close()
    return User(row['id'],row['name'],row['email'],row['password'],row['role'],row['created_at']) if row else None

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id))

@app.route('/')
def index():
    return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower()
        password=request.form.get('password',''); confirm=request.form.get('confirm_password','')
        if not name or not email or not password: flash('All fields are required.','danger')
        elif password != confirm: flash('Passwords do not match.','danger')
        elif len(password) < 6: flash('Password must be at least 6 characters.','danger')
        elif get_user_by_email(email): flash('Email already registered.','danger')
        else:
            conn=get_db(); count=conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            role='admin' if count==0 else 'user'
            conn.execute('INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)',
                         (name,email,generate_password_hash(password),role))
            conn.commit(); conn.close()
            flash(f'Account created! Role: {role.title()}. Please login.','success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        u=get_user_by_email(email)
        if u and check_password_hash(u.password, password):
            login_user(u, remember=True); flash(f'Welcome back, {u.name}!','success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.','danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user(); flash('Logged out successfully.','success'); return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn=get_db()
    total_students=conn.execute("SELECT COUNT(*) FROM students WHERE is_active=1").fetchone()[0]
    total_tests=conn.execute("SELECT COUNT(*) FROM tests").fetchone()[0]
    pending_hw=conn.execute("SELECT COUNT(*) FROM homework WHERE status='Pending'").fetchone()[0]
    total_results=conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    standards=['Nursery','LKG','UKG','1','2','3','4','5','6','7','8','9','10','11','12']
    std_counts=[conn.execute("SELECT COUNT(*) FROM students WHERE standard=? AND is_active=1",(s,)).fetchone()[0] for s in standards]
    recent_students=conn.execute("SELECT * FROM students WHERE is_active=1 ORDER BY created_at DESC LIMIT 8").fetchall()
    upcoming_tests=conn.execute("SELECT * FROM tests WHERE test_date >= ? ORDER BY test_date LIMIT 5",(str(date.today()),)).fetchall()
    hw_pending=conn.execute("SELECT COUNT(*) FROM homework WHERE status='Pending'").fetchone()[0]
    hw_submitted=conn.execute("SELECT COUNT(*) FROM homework WHERE status='Submitted'").fetchone()[0]
    hw_graded=conn.execute("SELECT COUNT(*) FROM homework WHERE status='Graded'").fetchone()[0]
    conn.close()
    return render_template('dashboard.html',
        total_students=total_students,total_tests=total_tests,pending_hw=pending_hw,total_results=total_results,
        recent_students=recent_students,upcoming_tests=upcoming_tests,
        standards=json.dumps(standards),std_counts=json.dumps(std_counts),
        hw_data=json.dumps([hw_pending,hw_submitted,hw_graded]))

@app.route('/students')
@login_required
def students():
    q=request.args.get('q',''); std_filter=request.args.get('standard','')
    conn=get_db()
    base="SELECT * FROM students WHERE is_active=1"
    params=[]
    if std_filter: base+=" AND standard=?"; params.append(std_filter)
    if q: base+=" AND (name LIKE ? OR roll_no LIKE ? OR contact LIKE ?)"; params+=[f'%{q}%',f'%{q}%',f'%{q}%']
    rows=conn.execute(base+" ORDER BY name",params).fetchall(); conn.close()
    standards=['Nursery','LKG','UKG']+[str(i) for i in range(1,13)]
    return render_template('students.html',students=rows,standards=standards,q=q,std_filter=std_filter)

@app.route('/students/add', methods=['GET','POST'])
@login_required
def add_student():
    standards=['Nursery','LKG','UKG']+[str(i) for i in range(1,13)]
    if request.method=='POST':
        roll=request.form.get('roll_no','').strip(); conn=get_db()
        if conn.execute("SELECT id FROM students WHERE roll_no=?",(roll,)).fetchone():
            conn.close(); flash('Roll number already exists.','danger')
        else:
            conn.execute('''INSERT INTO students (name,roll_no,standard,medium,stream,parent_name,contact,email,address,admission_date)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (request.form['name'].strip(),roll,request.form['standard'],
                 request.form.get('medium','English'),request.form.get('stream',''),
                 request.form.get('parent_name','').strip(),request.form.get('contact','').strip(),
                 request.form.get('email','').strip(),request.form.get('address','').strip(),
                 request.form.get('admission_date','') or str(date.today())))
            conn.commit(); conn.close(); flash('Student added!','success')
            return redirect(url_for('students'))
    return render_template('add_student.html',standards=standards)

@app.route('/students/edit/<int:sid>', methods=['GET','POST'])
@login_required
def edit_student(sid):
    standards=['Nursery','LKG','UKG']+[str(i) for i in range(1,13)]
    conn=get_db(); s=conn.execute("SELECT * FROM students WHERE id=?",(sid,)).fetchone()
    if request.method=='POST':
        conn.execute('''UPDATE students SET name=?,standard=?,medium=?,stream=?,parent_name=?,contact=?,email=?,address=? WHERE id=?''',
            (request.form['name'].strip(),request.form['standard'],request.form.get('medium','English'),
             request.form.get('stream',''),request.form.get('parent_name','').strip(),
             request.form.get('contact','').strip(),request.form.get('email','').strip(),
             request.form.get('address','').strip(),sid))
        conn.commit(); conn.close(); flash('Student updated!','success')
        return redirect(url_for('students'))
    conn.close()
    return render_template('edit_student.html',student=s,standards=standards)

@app.route('/students/delete/<int:sid>', methods=['POST'])
@login_required
def delete_student(sid):
    conn=get_db(); conn.execute("UPDATE students SET is_active=0 WHERE id=?",(sid,)); conn.commit(); conn.close()
    flash('Student removed.','success'); return redirect(url_for('students'))

@app.route('/students/view/<int:sid>')
@login_required
def view_student(sid):
    conn=get_db()
    s=conn.execute("SELECT * FROM students WHERE id=?",(sid,)).fetchone()
    hw=conn.execute("SELECT * FROM homework WHERE student_id=? ORDER BY due_date DESC",(sid,)).fetchall()
    rs=conn.execute('''SELECT r.*,t.title as test_title,t.subject,t.test_date,t.total_marks
                       FROM results r JOIN tests t ON r.test_id=t.id WHERE r.student_id=? ORDER BY t.test_date DESC''',(sid,)).fetchall()
    conn.close()
    return render_template('view_student.html',student=s,homeworks=hw,results=rs)

@app.route('/homework')
@login_required
def homework():
    q=request.args.get('q',''); sf=request.args.get('status','')
    conn=get_db()
    sql='''SELECT h.*,s.name as student_name FROM homework h JOIN students s ON h.student_id=s.id WHERE 1=1'''
    params=[]
    if sf: sql+=" AND h.status=?"; params.append(sf)
    if q: sql+=" AND (h.title LIKE ? OR h.subject LIKE ?)"; params+=[f'%{q}%',f'%{q}%']
    rows=conn.execute(sql+" ORDER BY h.due_date",params).fetchall(); conn.close()
    return render_template('homework.html',homeworks=rows,q=q,status_filter=sf)

@app.route('/homework/add', methods=['GET','POST'])
@login_required
def add_homework():
    conn=get_db()
    sl=conn.execute("SELECT id,name,roll_no,standard FROM students WHERE is_active=1 ORDER BY name").fetchall()
    if request.method=='POST':
        conn.execute('INSERT INTO homework (student_id,subject,title,description,due_date,assigned_by) VALUES (?,?,?,?,?,?)',
            (int(request.form['student_id']),request.form['subject'].strip(),request.form['title'].strip(),
             request.form.get('description','').strip(),request.form['due_date'],
             request.form.get('assigned_by',current_user.name).strip()))
        conn.commit(); conn.close(); flash('Homework assigned!','success')
        return redirect(url_for('homework'))
    conn.close()
    return render_template('add_homework.html',students=sl)

@app.route('/homework/update/<int:hid>', methods=['POST'])
@login_required
def update_homework(hid):
    conn=get_db()
    conn.execute("UPDATE homework SET status=?,grade=? WHERE id=?",(request.form.get('status','Pending'),request.form.get('grade',''),hid))
    conn.commit(); conn.close(); flash('Homework updated!','success')
    return redirect(url_for('homework'))

@app.route('/homework/delete/<int:hid>', methods=['POST'])
@login_required
def delete_homework(hid):
    conn=get_db(); conn.execute("DELETE FROM homework WHERE id=?",(hid,)); conn.commit(); conn.close()
    flash('Homework deleted.','success'); return redirect(url_for('homework'))

@app.route('/tests')
@login_required
def tests():
    q=request.args.get('q',''); conn=get_db()
    if q: rows=conn.execute("SELECT * FROM tests WHERE title LIKE ? OR subject LIKE ? ORDER BY test_date DESC",(f'%{q}%',f'%{q}%')).fetchall()
    else: rows=conn.execute("SELECT * FROM tests ORDER BY test_date DESC").fetchall()
    conn.close()
    return render_template('tests.html',tests=rows,q=q,today=str(date.today()))

@app.route('/tests/add', methods=['GET','POST'])
@login_required
def add_test():
    standards=['Nursery','LKG','UKG']+[str(i) for i in range(1,13)]
    if request.method=='POST':
        conn=get_db()
        conn.execute('INSERT INTO tests (title,subject,standard,test_date,total_marks,description) VALUES (?,?,?,?,?,?)',
            (request.form['title'].strip(),request.form['subject'].strip(),request.form['standard'],
             request.form['test_date'],int(request.form['total_marks']),request.form.get('description','').strip()))
        conn.commit(); conn.close(); flash('Test scheduled!','success')
        return redirect(url_for('tests'))
    return render_template('add_test.html',standards=standards)

@app.route('/tests/delete/<int:tid>', methods=['POST'])
@login_required
def delete_test(tid):
    conn=get_db(); conn.execute("DELETE FROM tests WHERE id=?",(tid,)); conn.commit(); conn.close()
    flash('Test deleted.','success'); return redirect(url_for('tests'))

@app.route('/results')
@login_required
def results():
    q=request.args.get('q',''); conn=get_db()
    sql='''SELECT r.*,s.name as student_name,s.roll_no,t.title as test_title,t.subject,t.total_marks,t.test_date
           FROM results r JOIN students s ON r.student_id=s.id JOIN tests t ON r.test_id=t.id WHERE 1=1'''
    params=[]
    if q: sql+=" AND (s.name LIKE ? OR s.roll_no LIKE ? OR t.title LIKE ?)"; params+=[f'%{q}%',f'%{q}%',f'%{q}%']
    rows=conn.execute(sql+" ORDER BY r.created_at DESC",params).fetchall(); conn.close()
    return render_template('results.html',results=rows,q=q)

@app.route('/results/add', methods=['GET','POST'])
@login_required
def add_result():
    conn=get_db()
    sl=conn.execute("SELECT id,name,roll_no FROM students WHERE is_active=1 ORDER BY name").fetchall()
    tl=conn.execute("SELECT * FROM tests ORDER BY test_date DESC").fetchall()
    if request.method=='POST':
        t=conn.execute("SELECT total_marks FROM tests WHERE id=?",(int(request.form['test_id']),)).fetchone()
        marks=float(request.form['marks_obtained']); pct=(marks/t['total_marks'])*100 if t else 0
        conn.execute('INSERT INTO results (student_id,test_id,marks_obtained,grade,remarks) VALUES (?,?,?,?,?)',
            (int(request.form['student_id']),int(request.form['test_id']),marks,grade_from_percent(pct),request.form.get('remarks','').strip()))
        conn.commit(); conn.close(); flash('Result added!','success')
        return redirect(url_for('results'))
    conn.close()
    return render_template('add_result.html',students=sl,tests=tl)

@app.route('/results/delete/<int:rid>', methods=['POST'])
@login_required
def delete_result(rid):
    conn=get_db(); conn.execute("DELETE FROM results WHERE id=?",(rid,)); conn.commit(); conn.close()
    flash('Result deleted.','success'); return redirect(url_for('results'))

@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin': flash('Admin access required.','danger'); return redirect(url_for('dashboard'))
    conn=get_db()
    users=conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    total_students=conn.execute("SELECT COUNT(*) FROM students WHERE is_active=1").fetchone()[0]
    total_tests=conn.execute("SELECT COUNT(*) FROM tests").fetchone()[0]
    total_hw=conn.execute("SELECT COUNT(*) FROM homework").fetchone()[0]
    total_results=conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    months_labels=[]; months_data=[]; today=date.today()
    for i in range(5,-1,-1):
        m=(today.month-i-1)%12+1; y=today.year-((today.month-i-1)//12)
        cnt=conn.execute("SELECT COUNT(*) FROM students WHERE strftime('%m',admission_date)=? AND strftime('%Y',admission_date)=?",(f'{m:02d}',str(y))).fetchone()[0]
        months_labels.append(datetime(y,m,1).strftime('%b %Y')); months_data.append(cnt)
    conn.close()
    return render_template('admin.html',users=users,total_students=total_students,
        total_tests=total_tests,total_hw=total_hw,total_results=total_results,
        months_labels=json.dumps(months_labels),months_data=json.dumps(months_data))

@app.route('/admin/toggle_role/<int:uid>', methods=['POST'])
@login_required
def toggle_role(uid):
    if current_user.role!='admin': return redirect(url_for('dashboard'))
    if uid==current_user.id: flash("Can't change your own role.",'warning')
    else:
        conn=get_db(); u=conn.execute("SELECT role FROM users WHERE id=?",(uid,)).fetchone()
        new_role='user' if u['role']=='admin' else 'admin'
        conn.execute("UPDATE users SET role=? WHERE id=?",(new_role,uid)); conn.commit(); conn.close()
        flash(f'Role updated to {new_role}.','success')
    return redirect(url_for('admin'))

@app.route('/admin/delete_user/<int:uid>', methods=['POST'])
@login_required
def delete_user(uid):
    if current_user.role!='admin': return redirect(url_for('dashboard'))
    if uid==current_user.id: flash("Can't delete yourself.",'warning')
    else:
        conn=get_db(); conn.execute("DELETE FROM users WHERE id=?",(uid,)); conn.commit(); conn.close()
        flash('User deleted.','success')
    return redirect(url_for('admin'))

init_db()

if __name__ == '__main__':
    app.run(debug=False)
