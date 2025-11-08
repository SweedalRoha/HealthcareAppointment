from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ----------------- Models -----------------=
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # patient, doctor, admin

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    time = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')

class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'))
    file_url = db.Column(db.String(200))

# ----------------- Login Manager -----------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ----------------- Initialize DB and Default Admin -----------------
with app.app_context():
    db.create_all()
    if not User.query.filter_by(role='admin').first():
        default_admin = User(
            username='admin',
            password=generate_password_hash('admin123', method='pbkdf2:sha256'),
            role='admin'
        )
        db.session.add(default_admin)
        db.session.commit()

# ----------------- Routes -----------------
@app.route('/')
def index():
    return render_template('index.html')

# ----------------- Patient Registration/Login -----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password, role='patient')
        db.session.add(new_user)
        db.session.commit()
        flash('Patient registered successfully!', 'success')
        return redirect(url_for('login'))
    return render_template('register_patient.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.role == 'patient':
                return redirect(url_for('patient_dashboard'))
            elif user.role == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            elif user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ----------------- Admin -----------------
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, role='admin').first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials', 'danger')
    return render_template('admin_login.html')

@app.route('/admin_dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    doctors = User.query.filter_by(role='doctor').all()
    patients = User.query.filter_by(role='patient').all()
    return render_template('admin_dashboard.html', doctors=doctors, patients=patients)

@app.route('/add_doctor', methods=['POST'])
@login_required
def add_doctor():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    username = request.form['username']
    password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
    new_doctor = User(username=username, password=password, role='doctor')
    db.session.add(new_doctor)
    db.session.commit()
    flash('Doctor added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# ----------------- Patient Dashboard -----------------
@app.route('/patient_dashboard')
@login_required
def patient_dashboard():
    if current_user.role != 'patient':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    doctors = User.query.filter_by(role='doctor').all()
    appointments = Appointment.query.filter_by(patient_id=current_user.id).all()
    return render_template('patient_dashboard.html', doctors=doctors, appointments=appointments)

@app.route('/book_appointment', methods=['POST'])
@login_required
def book_appointment():
    doctor_id = request.form['doctor_id']
    time = request.form['time']
    new_appointment = Appointment(patient_id=current_user.id, doctor_id=doctor_id, time=time)
    db.session.add(new_appointment)
    db.session.commit()
    flash('Appointment booked!', 'success')
    return redirect(url_for('patient_dashboard'))

@app.route('/view_history')
@login_required
def view_history():
    if current_user.role != 'patient':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    appointments = Appointment.query.filter_by(patient_id=current_user.id).all()
    prescriptions = Prescription.query.all()
    return render_template('view_history.html', appointments=appointments, prescriptions=prescriptions)

# ----------------- Doctor Dashboard -----------------
@app.route('/doctor_dashboard')
@login_required
def doctor_dashboard():
    if current_user.role != 'doctor':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    appointments = Appointment.query.filter_by(doctor_id=current_user.id).all()
    return render_template('doctor_dashboard.html', appointments=appointments)

@app.route('/update_appointment/<int:id>/<action>')
@login_required
def update_appointment(id, action):
    appointment = Appointment.query.get_or_404(id)
    if current_user.role != 'doctor' or appointment.doctor_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    if action == 'accept':
        appointment.status = 'accepted'
    elif action == 'reject':
        appointment.status = 'rejected'
    db.session.commit()
    return redirect(url_for('doctor_dashboard'))

# ----------------- Upload Prescription -----------------
@app.route('/upload_prescription/<int:appointment_id>', methods=['GET', 'POST'])
@login_required
def upload_prescription(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    if current_user.role != 'doctor' or appointment.doctor_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filename = f"{appointment_id}_{file.filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            new_presc = Prescription(appointment_id=appointment.id, file_url=filename)
            db.session.add(new_presc)
            db.session.commit()
            flash('Prescription uploaded!', 'success')
            return redirect(url_for('doctor_dashboard'))
    return render_template('upload_prescription.html', appointment=appointment)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ----------------- Run App -----------------
if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
