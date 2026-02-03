import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.user import User

auth_bp = Blueprint('auth', __name__)


def allowed_image(filename):
    """Check if file extension is allowed for images"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'}


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash('Invalid username or password', 'error')
            return render_template('auth/login.html')

        if not user.is_active:
            flash('Your account has been deactivated. Contact administrator.', 'error')
            return render_template('auth/login.html')

        login_user(user, remember=remember)
        user.last_login = datetime.utcnow()
        db.session.commit()

        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('main.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page"""
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', '').strip()
        current_user.last_name = request.form.get('last_name', '').strip()
        current_user.email = request.form.get('email', '').strip()

        # Handle avatar upload
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename and allowed_image(file.filename):
                # Delete old avatar if exists
                if current_user.avatar_filename:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_user.avatar_filename)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except:
                            pass  # Ignore errors deleting old file

                # Save new avatar
                filename = secure_filename(f"avatar_{current_user.id}_{file.filename}")
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                current_user.avatar_filename = filename

        # Password change
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if current_password and new_password:
            if not current_user.check_password(current_password):
                flash('Current password is incorrect', 'error')
                return render_template('auth/profile.html')

            if new_password != confirm_password:
                flash('New passwords do not match', 'error')
                return render_template('auth/profile.html')

            if len(new_password) < 6:
                flash('Password must be at least 6 characters', 'error')
                return render_template('auth/profile.html')

            current_user.set_password(new_password)
            flash('Password updated successfully', 'success')

        db.session.commit()
        flash('Profile updated successfully', 'success')

    return render_template('auth/profile.html')


@auth_bp.route('/users')
@login_required
def user_list():
    """List all users (admin only)"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.dashboard'))

    users = User.query.order_by(User.username).all()
    return render_template('auth/user_list.html', users=users)


@auth_bp.route('/users/new', methods=['GET', 'POST'])
@login_required
def user_create():
    """Create new user (admin only)"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'worker')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()

        # Validation
        if not username or not email or not password:
            flash('Username, email, and password are required', 'error')
            return render_template('auth/user_form.html', user=None)

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('auth/user_form.html', user=None)

        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return render_template('auth/user_form.html', user=None)

        user = User(
            username=username,
            email=email,
            role=role,
            first_name=first_name,
            last_name=last_name
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash(f'User {username} created successfully', 'success')
        return redirect(url_for('auth.user_list'))

    return render_template('auth/user_form.html', user=None)


@auth_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def user_edit(user_id):
    """Edit user (admin only)"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.dashboard'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.email = request.form.get('email', '').strip()
        user.role = request.form.get('role', 'worker')
        user.first_name = request.form.get('first_name', '').strip()
        user.last_name = request.form.get('last_name', '').strip()
        user.is_active = request.form.get('is_active') == 'on'

        # Password change (optional)
        new_password = request.form.get('password', '')
        if new_password:
            user.set_password(new_password)

        db.session.commit()
        flash(f'User {user.username} updated successfully', 'success')
        return redirect(url_for('auth.user_list'))

    return render_template('auth/user_form.html', user=user)


@auth_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
def user_toggle_active(user_id):
    """Toggle user active status (admin only)"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.dashboard'))

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('You cannot deactivate your own account', 'error')
        return redirect(url_for('auth.user_list'))

    user.is_active = not user.is_active
    db.session.commit()

    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.username} has been {status}', 'success')
    return redirect(url_for('auth.user_list'))
