from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.production import Mould, MouldMaintenance, Machine

moulds_bp = Blueprint('moulds', __name__)


@moulds_bp.route('/')
@login_required
def mould_list():
    """List all moulds"""
    status = request.args.get('status', '')
    mould_type = request.args.get('type', '')

    query = Mould.query.filter_by(is_active=True)

    if status:
        query = query.filter_by(status=status)
    if mould_type:
        query = query.filter_by(mould_type=mould_type)

    moulds = query.order_by(Mould.mould_number).all()

    # Get maintenance due count
    maintenance_due = sum(1 for m in moulds if m.is_maintenance_due)

    return render_template('moulds/list.html',
                           moulds=moulds,
                           status=status,
                           mould_type=mould_type,
                           maintenance_due=maintenance_due)


@moulds_bp.route('/new', methods=['GET', 'POST'])
@login_required
def mould_create():
    """Create new mould"""
    if request.method == 'POST':
        mould_number = request.form.get('mould_number', '').strip().upper()
        name = request.form.get('name', '').strip()

        if not mould_number:
            flash('Mould number is required', 'error')
            return render_template('moulds/form.html', mould=None)

        if Mould.query.filter_by(mould_number=mould_number).first():
            flash('Mould number already exists', 'error')
            return render_template('moulds/form.html', mould=None)

        mould = Mould(
            mould_number=mould_number,
            name=name,
            description=request.form.get('description', '').strip(),
            mould_type=request.form.get('mould_type', 'individual'),
            bolster_number=request.form.get('bolster_number', '').strip(),
            tonnage_required=request.form.get('tonnage_required', type=int),
            num_cavities=request.form.get('num_cavities', 1, type=int),
            cycle_time_seconds=request.form.get('cycle_time_seconds', type=float),
            material_compatibility=request.form.get('material_compatibility', '').strip(),
            storage_location=request.form.get('storage_location', '').strip(),
            maintenance_interval_months=request.form.get('maintenance_interval_months', 12, type=int),
            notes=request.form.get('notes', '').strip()
        )

        # Set next maintenance date
        interval = mould.maintenance_interval_months
        mould.next_maintenance_date = (datetime.now() + timedelta(days=interval * 30)).date()

        db.session.add(mould)
        db.session.commit()

        flash(f'Mould {mould_number} created successfully', 'success')
        return redirect(url_for('moulds.mould_detail', mould_id=mould.id))

    return render_template('moulds/form.html', mould=None)


@moulds_bp.route('/<int:mould_id>')
@login_required
def mould_detail(mould_id):
    """View mould details"""
    mould = Mould.query.get_or_404(mould_id)
    maintenance_logs = mould.maintenance_logs.order_by(MouldMaintenance.created_at.desc()).limit(10).all()
    recent_production = mould.production_orders.order_by(db.desc('created_at')).limit(10).all()

    return render_template('moulds/detail.html',
                           mould=mould,
                           maintenance_logs=maintenance_logs,
                           recent_production=recent_production)


@moulds_bp.route('/<int:mould_id>/edit', methods=['GET', 'POST'])
@login_required
def mould_edit(mould_id):
    """Edit mould"""
    mould = Mould.query.get_or_404(mould_id)

    if request.method == 'POST':
        mould.name = request.form.get('name', '').strip()
        mould.description = request.form.get('description', '').strip()
        mould.mould_type = request.form.get('mould_type', 'individual')
        mould.bolster_number = request.form.get('bolster_number', '').strip()
        mould.tonnage_required = request.form.get('tonnage_required', type=int)
        mould.num_cavities = request.form.get('num_cavities', 1, type=int)
        mould.cycle_time_seconds = request.form.get('cycle_time_seconds', type=float)
        mould.material_compatibility = request.form.get('material_compatibility', '').strip()
        mould.storage_location = request.form.get('storage_location', '').strip()
        mould.status = request.form.get('status', 'available')
        mould.maintenance_interval_months = request.form.get('maintenance_interval_months', 12, type=int)
        mould.notes = request.form.get('notes', '').strip()

        db.session.commit()
        flash(f'Mould {mould.mould_number} updated successfully', 'success')
        return redirect(url_for('moulds.mould_detail', mould_id=mould.id))

    machines = Machine.query.filter_by(is_active=True).order_by(Machine.name).all()
    return render_template('moulds/form.html', mould=mould, machines=machines)


@moulds_bp.route('/<int:mould_id>/maintenance', methods=['GET', 'POST'])
@login_required
def record_maintenance(mould_id):
    """Record maintenance activity"""
    mould = Mould.query.get_or_404(mould_id)

    if request.method == 'POST':
        maintenance_type = request.form.get('maintenance_type', 'pm')
        description = request.form.get('description', '').strip()
        work_performed = request.form.get('work_performed', '').strip()
        technician = request.form.get('technician', '').strip()
        cost = request.form.get('cost', type=float)

        log = MouldMaintenance(
            mould_id=mould.id,
            maintenance_type=maintenance_type,
            description=description,
            work_performed=work_performed,
            technician=technician,
            shots_at_maintenance=mould.total_shots,
            cost=cost
        )
        db.session.add(log)

        # Update mould maintenance dates
        mould.last_maintenance_date = datetime.now().date()
        interval = mould.maintenance_interval_months
        mould.next_maintenance_date = (datetime.now() + timedelta(days=interval * 30)).date()

        if maintenance_type == 'repair':
            mould.status = 'available'

        db.session.commit()

        flash('Maintenance recorded successfully', 'success')
        return redirect(url_for('moulds.mould_detail', mould_id=mould.id))

    return render_template('moulds/maintenance_form.html', mould=mould)


@moulds_bp.route('/<int:mould_id>/report-issue', methods=['POST'])
@login_required
def report_issue(mould_id):
    """Report mould issue (mobile-friendly)"""
    mould = Mould.query.get_or_404(mould_id)

    issue_type = request.form.get('issue_type', '').strip()
    description = request.form.get('description', '').strip()

    if not issue_type or not description:
        flash('Issue type and description are required', 'error')
        return redirect(url_for('moulds.mould_detail', mould_id=mould.id))

    # Create maintenance request
    log = MouldMaintenance(
        mould_id=mould.id,
        maintenance_type='repair',
        description=f'Issue reported: {issue_type}',
        work_performed=description
    )
    db.session.add(log)

    # Update mould status
    mould.status = 'awaiting_repair'

    db.session.commit()

    flash('Issue reported successfully. Mould marked for repair.', 'success')
    return redirect(url_for('moulds.mould_detail', mould_id=mould.id))


@moulds_bp.route('/<int:mould_id>/set-status', methods=['POST'])
@login_required
def set_status(mould_id):
    """Change mould status"""
    mould = Mould.query.get_or_404(mould_id)
    new_status = request.form.get('status', '')

    valid_statuses = ['available', 'in_use', 'maintenance', 'awaiting_repair', 'retired']
    if new_status not in valid_statuses:
        flash('Invalid status', 'error')
        return redirect(url_for('moulds.mould_detail', mould_id=mould.id))

    old_status = mould.status
    mould.status = new_status

    # If marking as repaired/available from awaiting_repair, log it
    if old_status == 'awaiting_repair' and new_status == 'available':
        log = MouldMaintenance(
            mould_id=mould.id,
            maintenance_type='repair',
            description='Repair completed - mould returned to service',
            work_performed='Marked as repaired'
        )
        db.session.add(log)

    db.session.commit()

    flash(f'Mould status changed to {new_status.replace("_", " ").title()}', 'success')
    return redirect(url_for('moulds.mould_detail', mould_id=mould.id))


@moulds_bp.route('/maintenance-due')
@login_required
def maintenance_due():
    """List moulds with maintenance due"""
    moulds = Mould.query.filter(
        Mould.is_active == True,
        Mould.next_maintenance_date != None
    ).all()

    due_moulds = [m for m in moulds if m.is_maintenance_due]
    upcoming = [m for m in moulds if not m.is_maintenance_due and
                m.next_maintenance_date <= (datetime.now() + timedelta(days=30)).date()]

    return render_template('moulds/maintenance_due.html',
                           due_moulds=due_moulds,
                           upcoming=upcoming)


# API endpoints
@moulds_bp.route('/api/search')
@login_required
def api_search():
    """Search moulds via API"""
    query = request.args.get('q', '').strip()

    moulds = Mould.query.filter(
        Mould.is_active == True,
        db.or_(
            Mould.mould_number.ilike(f'%{query}%'),
            Mould.name.ilike(f'%{query}%')
        )
    ).limit(20).all()

    return jsonify([{
        'id': m.id,
        'mould_number': m.mould_number,
        'name': m.name,
        'tonnage': m.tonnage_required,
        'status': m.status
    } for m in moulds])


@moulds_bp.route('/api/<int:mould_id>')
@login_required
def api_mould_detail(mould_id):
    """Get mould details via API"""
    mould = Mould.query.get_or_404(mould_id)

    return jsonify({
        'id': mould.id,
        'mould_number': mould.mould_number,
        'name': mould.name,
        'type': mould.mould_type,
        'tonnage': mould.tonnage_required,
        'cavities': mould.num_cavities,
        'cycle_time': mould.cycle_time_seconds,
        'status': mould.status,
        'storage_location': mould.storage_location,
        'maintenance_due': mould.is_maintenance_due,
        'next_maintenance': mould.next_maintenance_date.isoformat() if mould.next_maintenance_date else None
    })
