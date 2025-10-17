from flask import render_template, request, redirect, url_for, flash, jsonify, session
from app import app, db
from flask_login import current_user, login_required, login_user, logout_user
from models import LeaveRequest, LeaveBalance, User
from datetime import datetime

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email address already exists.', 'error')
            return redirect(url_for('register'))
        new_user = User(email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    balance = LeaveBalance.query.filter_by(user_id=current_user.id).first()
    if not balance:
        balance = LeaveBalance(user_id=current_user.id)
        db.session.add(balance)
        db.session.commit()
    
    leave_requests = LeaveRequest.query.filter_by(employee_id=current_user.id).order_by(LeaveRequest.created_at.desc()).all()
    
    return render_template('dashboard.html', user=current_user, balance=balance, leave_requests=leave_requests)

@app.route('/request-leave', methods=['GET', 'POST'])
@login_required
def request_leave():
    if request.method == 'POST':
        leave_type = request.form.get('leave_type')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        reason = request.form.get('reason')
        
        if start_date > end_date:
            flash('End date must be after start date', 'error')
            return redirect(url_for('request_leave'))
        
        days_count = (end_date - start_date).days + 1
        balance = LeaveBalance.query.filter_by(user_id=current_user.id).first()
        
        available_balance = 0
        if leave_type == 'sick':
            available_balance = balance.sick_leave
        elif leave_type == 'vacation':
            available_balance = balance.vacation_leave
        elif leave_type == 'personal':
            available_balance = balance.personal_leave
        
        if days_count > available_balance:
            flash(f'Insufficient {leave_type} leave balance. You have {available_balance} days available.', 'error')
            return redirect(url_for('request_leave'))
        
        leave_request = LeaveRequest(
            employee_id=current_user.id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason
        )
        db.session.add(leave_request)
        db.session.commit()
        
        flash('Leave request submitted successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    balance = LeaveBalance.query.filter_by(user_id=current_user.id).first()
    return render_template('request_leave.html', balance=balance)

@app.route('/manager')
@login_required
def manager_dashboard():
    if current_user.role != 'manager':
        flash('Access denied. Manager privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    pending_requests = LeaveRequest.query.filter_by(status='pending').order_by(LeaveRequest.created_at.desc()).all()
    all_requests = LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).limit(50).all()
    
    return render_template('manager_dashboard.html', pending_requests=pending_requests, all_requests=all_requests)

@app.route('/manager/approve/<int:request_id>', methods=['POST'])
@login_required
def approve_leave(request_id):
    if current_user.role != 'manager':
        return jsonify({'error': 'Unauthorized'}), 403
    
    leave_request = LeaveRequest.query.get_or_404(request_id)
    comments = request.form.get('comments', '')
    
    leave_request.status = 'approved'
    leave_request.manager_id = current_user.id
    leave_request.manager_comments = comments
    
    balance = LeaveBalance.query.filter_by(user_id=leave_request.employee_id).first()
    days_count = leave_request.days_count
    
    if leave_request.leave_type == 'sick':
        balance.sick_leave -= days_count
    elif leave_request.leave_type == 'vacation':
        balance.vacation_leave -= days_count
    elif leave_request.leave_type == 'personal':
        balance.personal_leave -= days_count
    
    db.session.commit()
    flash('Leave request approved successfully!', 'success')
    return redirect(url_for('manager_dashboard'))

@app.route('/manager/reject/<int:request_id>', methods=['POST'])
@login_required
def reject_leave(request_id):
    if current_user.role != 'manager':
        return jsonify({'error': 'Unauthorized'}), 403
    
    leave_request = LeaveRequest.query.get_or_404(request_id)
    comments = request.form.get('comments', '')
    
    leave_request.status = 'rejected'
    leave_request.manager_id = current_user.id
    leave_request.manager_comments = comments
    
    db.session.commit()
    flash('Leave request rejected.', 'success')
    return redirect(url_for('manager_dashboard'))

@app.route('/calendar')
@login_required
def calendar():
    approved_leaves = LeaveRequest.query.filter_by(status='approved').all()
    return render_template('calendar.html', approved_leaves=approved_leaves)

@app.route('/api/calendar-events')
@login_required
def calendar_events():
    approved_leaves = LeaveRequest.query.filter_by(status='approved').all()
    events = []
    
    for leave in approved_leaves:
        employee = User.query.get(leave.employee_id)
        events.append({
            'title': f"{employee.first_name or employee.email} - {leave.leave_type.capitalize()}",
            'start': leave.start_date.isoformat(),
            'end': leave.end_date.isoformat(),
            'color': '#3b82f6' if leave.leave_type == 'vacation' else '#ef4444' if leave.leave_type == 'sick' else '#8b5cf6'
        })
    
    return jsonify(events)

@app.route('/toggle-role')
@login_required
def toggle_role():
    if current_user.role == 'employee':
        current_user.role = 'manager'
    else:
        current_user.role = 'employee'
    db.session.commit()
    flash(f'Role switched to {current_user.role}', 'success')
    return redirect(url_for('dashboard'))

