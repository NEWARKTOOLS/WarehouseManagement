from datetime import datetime, timedelta, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.production import (
    ProductionOrder, Machine, Mould, ScheduledJob, AwaitingSorting,
    SetupSheet, ProductionLog
)
from app.models.inventory import Item, StockLevel, StockMovement
from app.models.location import Location
from app.models.orders import SalesOrder

scheduling_bp = Blueprint('scheduling', __name__)


def get_week_dates(target_date=None):
    """Get start and end dates for a week containing target_date"""
    if target_date is None:
        target_date = date.today()

    # Get Monday of the week
    start = target_date - timedelta(days=target_date.weekday())
    end = start + timedelta(days=6)

    return start, end


@scheduling_bp.route('/')
@login_required
def schedule_index():
    """Weekly schedule overview - calendar view"""
    # Get week from query params or default to current week
    week_offset = request.args.get('week', 0, type=int)
    today = date.today()
    target_date = today + timedelta(weeks=week_offset)
    week_start, week_end = get_week_dates(target_date)

    # Get all active machines ordered by display_order
    machines = Machine.query.filter_by(is_active=True).order_by(
        Machine.display_order, Machine.name
    ).all()

    # Get all scheduled jobs for this week
    jobs = ScheduledJob.query.filter(
        ScheduledJob.scheduled_date >= week_start,
        ScheduledJob.scheduled_date <= week_end
    ).all()

    # Organize jobs by machine and date
    schedule_grid = {}
    for machine in machines:
        schedule_grid[machine.id] = {
            'machine': machine,
            'days': {}
        }
        # Initialize each day
        current = week_start
        while current <= week_end:
            schedule_grid[machine.id]['days'][current.isoformat()] = []
            current += timedelta(days=1)

    # Populate jobs
    for job in jobs:
        if job.machine_id in schedule_grid:
            date_key = job.scheduled_date.isoformat()
            if date_key in schedule_grid[job.machine_id]['days']:
                schedule_grid[job.machine_id]['days'][date_key].append(job)

    # Sort jobs by sequence within each day
    for machine_id in schedule_grid:
        for date_key in schedule_grid[machine_id]['days']:
            schedule_grid[machine_id]['days'][date_key].sort(
                key=lambda j: j.sequence_order
            )

    # Generate week days list
    week_days = []
    current = week_start
    while current <= week_end:
        week_days.append({
            'date': current,
            'name': current.strftime('%A'),
            'short_name': current.strftime('%a'),
            'day_num': current.strftime('%d'),
            'is_today': current == today
        })
        current += timedelta(days=1)

    # Get unscheduled production orders for the sidebar
    unscheduled_orders = ProductionOrder.query.filter(
        ProductionOrder.status.in_(['planned', 'in_progress']),
        ~ProductionOrder.id.in_(
            db.session.query(ScheduledJob.production_order_id).filter(
                ScheduledJob.status.in_(['scheduled', 'in_progress'])
            )
        )
    ).order_by(ProductionOrder.due_date.asc().nullslast(), ProductionOrder.priority).all()

    # Get orders needing scheduling (sales orders with required dates)
    pending_sales_orders = SalesOrder.query.filter(
        SalesOrder.status.in_(['new', 'in_production'])
    ).order_by(SalesOrder.required_date.asc().nullslast()).all()

    # Count scheduled jobs this week
    scheduled_count = len(jobs)

    return render_template('scheduling/index.html',
                           machines=machines,
                           schedule_grid=schedule_grid,
                           week_days=week_days,
                           week_start=week_start,
                           week_end=week_end,
                           week_offset=week_offset,
                           today=today,
                           unscheduled_orders=unscheduled_orders,
                           pending_sales_orders=pending_sales_orders,
                           scheduled_count=scheduled_count)


@scheduling_bp.route('/day/<date_str>')
@login_required
def day_view(date_str):
    """Daily detail view for a specific date"""
    try:
        view_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format', 'error')
        return redirect(url_for('scheduling.schedule_index'))

    # Get all machines
    machines = Machine.query.filter_by(is_active=True).order_by(
        Machine.display_order, Machine.name
    ).all()

    # Get scheduled jobs for this day with related data
    jobs_by_machine = {}
    for machine in machines:
        jobs = ScheduledJob.query.filter_by(
            machine_id=machine.id,
            scheduled_date=view_date
        ).order_by(ScheduledJob.sequence_order).all()

        jobs_by_machine[machine.id] = {
            'machine': machine,
            'jobs': jobs
        }

    # Calculate previous and next day
    prev_date = view_date - timedelta(days=1)
    next_date = view_date + timedelta(days=1)

    return render_template('scheduling/day_view.html',
                           view_date=view_date,
                           machines=machines,
                           jobs_by_machine=jobs_by_machine,
                           prev_date=prev_date,
                           next_date=next_date,
                           today=date.today())


@scheduling_bp.route('/machine/<int:machine_id>')
@login_required
def machine_schedule(machine_id):
    """View schedule for a specific machine"""
    machine = Machine.query.get_or_404(machine_id)

    # Get upcoming jobs for this machine
    today = date.today()
    upcoming_jobs = ScheduledJob.query.filter(
        ScheduledJob.machine_id == machine_id,
        ScheduledJob.scheduled_date >= today,
        ScheduledJob.status.in_(['scheduled', 'in_progress'])
    ).order_by(ScheduledJob.scheduled_date, ScheduledJob.sequence_order).limit(20).all()

    # Get current job (in progress)
    current_job = ScheduledJob.query.filter_by(
        machine_id=machine_id,
        status='in_progress'
    ).first()

    # Get next job
    next_job = None
    if current_job:
        next_job = ScheduledJob.query.filter(
            ScheduledJob.machine_id == machine_id,
            ScheduledJob.status == 'scheduled',
            ScheduledJob.scheduled_date >= today
        ).order_by(ScheduledJob.scheduled_date, ScheduledJob.sequence_order).first()
    elif upcoming_jobs:
        next_job = upcoming_jobs[0] if upcoming_jobs else None

    return render_template('scheduling/machine_schedule.html',
                           machine=machine,
                           current_job=current_job,
                           next_job=next_job,
                           upcoming_jobs=upcoming_jobs,
                           today=today)


@scheduling_bp.route('/job/<int:job_id>')
@login_required
def job_detail(job_id):
    """View details of a scheduled job"""
    job = ScheduledJob.query.get_or_404(job_id)

    # Get setup sheet if exists
    setup_sheet = None
    if job.production_order and job.production_order.item_id and job.production_order.mould_id:
        setup_sheet = SetupSheet.query.filter_by(
            item_id=job.production_order.item_id,
            mould_id=job.production_order.mould_id,
            is_current=True
        ).first()

    # Get what's next on this machine
    next_job = ScheduledJob.query.filter(
        ScheduledJob.machine_id == job.machine_id,
        ScheduledJob.scheduled_date >= job.scheduled_date,
        ScheduledJob.id != job.id,
        ScheduledJob.status == 'scheduled'
    ).order_by(ScheduledJob.scheduled_date, ScheduledJob.sequence_order).first()

    # Check for changeover needed
    changeover_info = None
    if next_job and job.production_order and next_job.production_order:
        current_mould = job.production_order.mould
        next_mould = next_job.production_order.mould
        current_item = job.production_order.item
        next_item = next_job.production_order.item

        changeover_info = {
            'mould_change': current_mould != next_mould if current_mould and next_mould else False,
            'current_mould': current_mould,
            'next_mould': next_mould,
            'material_change': (current_item.material_grade != next_item.material_grade) if current_item and next_item and current_item.material_grade and next_item.material_grade else False,
            'color_change': (current_item.color != next_item.color) if current_item and next_item and current_item.color and next_item.color else False,
        }

    return render_template('scheduling/job_detail.html',
                           job=job,
                           setup_sheet=setup_sheet,
                           next_job=next_job,
                           changeover_info=changeover_info)


@scheduling_bp.route('/job/<int:job_id>/start', methods=['POST'])
@login_required
def start_job(job_id):
    """Start a scheduled job"""
    job = ScheduledJob.query.get_or_404(job_id)

    if job.status != 'scheduled':
        flash('Job cannot be started - invalid status', 'error')
        return redirect(url_for('scheduling.job_detail', job_id=job.id))

    job.status = 'in_progress'
    job.actual_start_time = datetime.utcnow()

    # Update production order status
    if job.production_order:
        job.production_order.status = 'in_progress'
        job.production_order.start_date = datetime.utcnow()

    # Update machine status
    if job.machine:
        job.machine.status = 'running'
        if job.production_order and job.production_order.mould_id:
            job.machine.current_mould_id = job.production_order.mould_id

    # Log the start
    log = ProductionLog(
        production_order_id=job.production_order_id,
        machine_id=job.machine_id,
        operator_id=current_user.id,
        log_type='start',
        notes=f'Job started by {current_user.username}'
    )
    db.session.add(log)
    db.session.commit()

    flash('Job started successfully', 'success')
    return redirect(url_for('scheduling.job_detail', job_id=job.id))


@scheduling_bp.route('/job/<int:job_id>/complete', methods=['GET', 'POST'])
@login_required
def complete_job(job_id):
    """Complete a job - ask where parts are going"""
    job = ScheduledJob.query.get_or_404(job_id)

    if job.status not in ['in_progress', 'scheduled']:
        flash('Job cannot be completed - invalid status', 'error')
        return redirect(url_for('scheduling.job_detail', job_id=job.id))

    if request.method == 'POST':
        destination = request.form.get('destination')
        quantity_produced = request.form.get('quantity_produced', type=float)
        notes = request.form.get('notes', '').strip()

        job.status = 'completed'
        job.actual_end_time = datetime.utcnow()
        job.completed_by_id = current_user.id
        job.output_destination = destination

        # Update production order
        if job.production_order:
            if quantity_produced:
                job.production_order.quantity_produced += quantity_produced

            # Check if fully complete
            if job.production_order.quantity_produced >= job.production_order.quantity_required:
                job.production_order.status = 'completed'
                job.production_order.end_date = datetime.utcnow()

        # Handle destination
        if destination == 'awaiting_sorting':
            # Create awaiting sorting record
            sorting = AwaitingSorting(
                production_order_id=job.production_order_id,
                scheduled_job_id=job.id,
                item_id=job.production_order.item_id,
                sorting_type='counting',
                estimated_quantity=quantity_produced or job.production_order.quantity_required,
                status='pending',
                notes=notes
            )
            db.session.add(sorting)
            flash('Job completed - parts added to sorting queue', 'success')

        elif destination == 'awaiting_degating':
            sorting = AwaitingSorting(
                production_order_id=job.production_order_id,
                scheduled_job_id=job.id,
                item_id=job.production_order.item_id,
                sorting_type='degating',
                estimated_quantity=quantity_produced or job.production_order.quantity_required,
                status='pending',
                notes=notes
            )
            db.session.add(sorting)
            flash('Job completed - parts added to degating queue', 'success')

        elif destination == 'awaiting_assembly':
            sorting = AwaitingSorting(
                production_order_id=job.production_order_id,
                scheduled_job_id=job.id,
                item_id=job.production_order.item_id,
                sorting_type='assembly',
                estimated_quantity=quantity_produced or job.production_order.quantity_required,
                status='pending',
                notes=notes
            )
            db.session.add(sorting)
            flash('Job completed - parts added to assembly queue', 'success')

        elif destination.startswith('location_'):
            # Direct to location - add to stock
            location_id = int(destination.replace('location_', ''))
            location = Location.query.get(location_id)

            if location and job.production_order and quantity_produced:
                # Add to stock
                stock = StockLevel.query.filter_by(
                    item_id=job.production_order.item_id,
                    location_id=location_id
                ).first()

                if stock:
                    stock.quantity += quantity_produced
                else:
                    stock = StockLevel(
                        item_id=job.production_order.item_id,
                        location_id=location_id,
                        quantity=quantity_produced
                    )
                    db.session.add(stock)

                # Record movement
                movement = StockMovement(
                    item_id=job.production_order.item_id,
                    movement_type='production',
                    quantity=quantity_produced,
                    to_location_id=location_id,
                    reference=job.production_order.order_number,
                    notes=f'Production completed - {job.machine.name if job.machine else "Unknown"}',
                    user_id=current_user.id
                )
                db.session.add(movement)

                job.production_order.quantity_good = (job.production_order.quantity_good or 0) + quantity_produced

            flash(f'Job completed - {quantity_produced} parts added to {location.code if location else "location"}', 'success')

        # Log completion
        log = ProductionLog(
            production_order_id=job.production_order_id,
            machine_id=job.machine_id,
            operator_id=current_user.id,
            log_type='stop',
            quantity=quantity_produced,
            notes=f'Job completed by {current_user.username}. Destination: {destination}'
        )
        db.session.add(log)

        # Update machine status
        if job.machine:
            job.machine.status = 'idle'

        db.session.commit()

        return redirect(url_for('scheduling.machine_schedule', machine_id=job.machine_id))

    # GET - show completion form
    locations = Location.query.filter_by(is_active=True).order_by(Location.code).all()

    # Get next job
    next_job = ScheduledJob.query.filter(
        ScheduledJob.machine_id == job.machine_id,
        ScheduledJob.id != job.id,
        ScheduledJob.status == 'scheduled'
    ).order_by(ScheduledJob.scheduled_date, ScheduledJob.sequence_order).first()

    return render_template('scheduling/complete_job.html',
                           job=job,
                           locations=locations,
                           next_job=next_job)


@scheduling_bp.route('/schedule-job', methods=['POST'])
@login_required
def schedule_job():
    """Schedule a production order to a machine and date"""
    production_order_id = request.form.get('production_order_id', type=int)
    machine_id = request.form.get('machine_id', type=int)
    scheduled_date_str = request.form.get('scheduled_date')

    if not all([production_order_id, machine_id, scheduled_date_str]):
        flash('Missing required fields', 'error')
        return redirect(request.referrer or url_for('scheduling.schedule_index'))

    try:
        scheduled_date = datetime.strptime(scheduled_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format', 'error')
        return redirect(request.referrer or url_for('scheduling.schedule_index'))

    production_order = ProductionOrder.query.get_or_404(production_order_id)
    machine = Machine.query.get_or_404(machine_id)

    # Get next sequence number for this machine on this date
    max_seq = db.session.query(db.func.max(ScheduledJob.sequence_order)).filter_by(
        machine_id=machine_id,
        scheduled_date=scheduled_date
    ).scalar() or 0

    # Calculate estimated duration based on cycle time and quantity
    estimated_hours = None
    if production_order.item and production_order.mould:
        # Try to get cycle time from setup sheet or mould
        setup = SetupSheet.query.filter_by(
            item_id=production_order.item_id,
            mould_id=production_order.mould_id,
            is_current=True
        ).first()

        cycle_time = None
        if setup and setup.cycle_time:
            cycle_time = setup.cycle_time
        elif production_order.mould.cycle_time_seconds:
            cycle_time = production_order.mould.cycle_time_seconds

        if cycle_time and production_order.quantity_required:
            # Calculate hours: (quantity / cavities) * cycle_time_seconds / 3600
            cavities = production_order.mould.num_cavities or 1
            shots_needed = production_order.quantity_required / cavities
            estimated_hours = (shots_needed * cycle_time) / 3600

    # Create scheduled job
    job = ScheduledJob(
        production_order_id=production_order_id,
        machine_id=machine_id,
        scheduled_date=scheduled_date,
        sequence_order=max_seq + 1,
        estimated_duration_hours=estimated_hours,
        status='scheduled'
    )
    db.session.add(job)
    db.session.commit()

    flash(f'Job scheduled on {machine.name} for {scheduled_date.strftime("%d/%m/%Y")}', 'success')
    return redirect(request.referrer or url_for('scheduling.schedule_index'))


@scheduling_bp.route('/unschedule-job/<int:job_id>', methods=['POST'])
@login_required
def unschedule_job(job_id):
    """Remove a job from the schedule"""
    job = ScheduledJob.query.get_or_404(job_id)

    if job.status not in ['scheduled']:
        flash('Cannot unschedule a job that has started', 'error')
        return redirect(request.referrer or url_for('scheduling.schedule_index'))

    db.session.delete(job)
    db.session.commit()

    flash('Job removed from schedule', 'success')
    return redirect(request.referrer or url_for('scheduling.schedule_index'))


@scheduling_bp.route('/move-job/<int:job_id>', methods=['POST'])
@login_required
def move_job(job_id):
    """Move a job to a different date or machine"""
    job = ScheduledJob.query.get_or_404(job_id)

    new_machine_id = request.form.get('machine_id', type=int)
    new_date_str = request.form.get('scheduled_date')
    new_sequence = request.form.get('sequence_order', type=int)

    if new_machine_id:
        job.machine_id = new_machine_id

    if new_date_str:
        try:
            job.scheduled_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    if new_sequence:
        job.sequence_order = new_sequence

    db.session.commit()

    flash('Job moved successfully', 'success')
    return redirect(request.referrer or url_for('scheduling.schedule_index'))


@scheduling_bp.route('/sorting')
@login_required
def sorting_queue():
    """View items awaiting sorting"""
    status_filter = request.args.get('status', 'pending')
    type_filter = request.args.get('type', '')

    query = AwaitingSorting.query

    if status_filter:
        query = query.filter_by(status=status_filter)

    if type_filter:
        query = query.filter_by(sorting_type=type_filter)

    items = query.order_by(AwaitingSorting.created_at.desc()).all()

    # Get counts by type
    counts = {
        'counting': AwaitingSorting.query.filter_by(status='pending', sorting_type='counting').count(),
        'degating': AwaitingSorting.query.filter_by(status='pending', sorting_type='degating').count(),
        'assembly': AwaitingSorting.query.filter_by(status='pending', sorting_type='assembly').count(),
        'quality_check': AwaitingSorting.query.filter_by(status='pending', sorting_type='quality_check').count(),
    }

    # Get locations for the complete modal
    locations = Location.query.filter_by(is_active=True).order_by(Location.code).all()

    return render_template('scheduling/sorting_queue.html',
                           items=items,
                           counts=counts,
                           status_filter=status_filter,
                           type_filter=type_filter,
                           locations=locations)


@scheduling_bp.route('/sorting/<int:sorting_id>/complete', methods=['POST'])
@login_required
def complete_sorting(sorting_id):
    """Complete a sorting task"""
    sorting = AwaitingSorting.query.get_or_404(sorting_id)

    actual_quantity = request.form.get('actual_quantity', type=float)
    rejected_quantity = request.form.get('rejected_quantity', 0, type=float)
    location_id = request.form.get('location_id', type=int)

    if not actual_quantity or not location_id:
        flash('Quantity and location are required', 'error')
        return redirect(url_for('scheduling.sorting_queue'))

    sorting.actual_quantity = actual_quantity
    sorting.rejected_quantity = rejected_quantity
    sorting.destination_location_id = location_id
    sorting.status = 'completed'
    sorting.completed_at = datetime.utcnow()
    sorting.completed_by_id = current_user.id

    # Add to stock
    stock = StockLevel.query.filter_by(
        item_id=sorting.item_id,
        location_id=location_id
    ).first()

    if stock:
        stock.quantity += actual_quantity
    else:
        stock = StockLevel(
            item_id=sorting.item_id,
            location_id=location_id,
            quantity=actual_quantity
        )
        db.session.add(stock)

    # Record movement
    movement = StockMovement(
        item_id=sorting.item_id,
        movement_type='production',
        quantity=actual_quantity,
        to_location_id=location_id,
        reference=sorting.production_order.order_number if sorting.production_order else '',
        notes=f'Sorted and counted - {sorting.sorting_type}',
        user_id=current_user.id
    )
    db.session.add(movement)

    # Update production order quantities
    if sorting.production_order:
        sorting.production_order.quantity_good = (sorting.production_order.quantity_good or 0) + actual_quantity
        sorting.production_order.quantity_rejected = (sorting.production_order.quantity_rejected or 0) + rejected_quantity

    db.session.commit()

    flash(f'Sorting complete - {actual_quantity} parts added to stock', 'success')
    return redirect(url_for('scheduling.sorting_queue'))


# API endpoints for drag and drop
@scheduling_bp.route('/api/schedule-job', methods=['POST'])
@login_required
def api_schedule_job():
    """API endpoint for drag-and-drop scheduling"""
    data = request.get_json()

    production_order_id = data.get('production_order_id')
    machine_id = data.get('machine_id')
    scheduled_date = data.get('scheduled_date')

    if not all([production_order_id, machine_id, scheduled_date]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    try:
        scheduled_date = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date format'}), 400

    production_order = ProductionOrder.query.get(production_order_id)
    machine = Machine.query.get(machine_id)

    if not production_order or not machine:
        return jsonify({'success': False, 'error': 'Invalid order or machine'}), 404

    # Get next sequence
    max_seq = db.session.query(db.func.max(ScheduledJob.sequence_order)).filter_by(
        machine_id=machine_id,
        scheduled_date=scheduled_date
    ).scalar() or 0

    job = ScheduledJob(
        production_order_id=production_order_id,
        machine_id=machine_id,
        scheduled_date=scheduled_date,
        sequence_order=max_seq + 1,
        status='scheduled'
    )
    db.session.add(job)
    db.session.commit()

    return jsonify({
        'success': True,
        'job_id': job.id,
        'message': f'Job scheduled on {machine.name}'
    })


@scheduling_bp.route('/api/move-job', methods=['POST'])
@login_required
def api_move_job():
    """API endpoint for drag-and-drop job moving"""
    data = request.get_json()

    job_id = data.get('job_id')
    new_machine_id = data.get('machine_id')
    new_date = data.get('scheduled_date')
    new_sequence = data.get('sequence_order')

    job = ScheduledJob.query.get(job_id)
    if not job:
        return jsonify({'success': False, 'error': 'Job not found'}), 404

    if job.status != 'scheduled':
        return jsonify({'success': False, 'error': 'Cannot move started job'}), 400

    if new_machine_id:
        job.machine_id = new_machine_id

    if new_date:
        try:
            job.scheduled_date = datetime.strptime(new_date, '%Y-%m-%d').date()
        except ValueError:
            pass

    if new_sequence:
        job.sequence_order = new_sequence

    db.session.commit()

    return jsonify({'success': True, 'message': 'Job moved'})


@scheduling_bp.route('/api/unscheduled-orders')
@login_required
def api_unscheduled_orders():
    """Get list of unscheduled production orders"""
    orders = ProductionOrder.query.filter(
        ProductionOrder.status.in_(['planned', 'in_progress']),
        ~ProductionOrder.id.in_(
            db.session.query(ScheduledJob.production_order_id).filter(
                ScheduledJob.status.in_(['scheduled', 'in_progress'])
            )
        )
    ).order_by(ProductionOrder.due_date.asc().nullslast(), ProductionOrder.priority).all()

    return jsonify([{
        'id': o.id,
        'order_number': o.order_number,
        'item_sku': o.item.sku if o.item else '',
        'item_name': o.item.name if o.item else '',
        'quantity': o.quantity_required,
        'due_date': o.due_date.isoformat() if o.due_date else None,
        'priority': o.priority,
        'customer': o.sales_order.customer.name if o.sales_order and o.sales_order.customer else None
    } for o in orders])


# Technician Views - Mobile Optimized Shop Floor Interface
@scheduling_bp.route('/technician')
@login_required
def technician_view():
    """Shop floor view for technicians - select machine"""
    today = date.today()

    machines = Machine.query.filter_by(is_active=True).order_by(
        Machine.display_order, Machine.name
    ).all()

    # Today's jobs across all machines
    todays_jobs = ScheduledJob.query.filter(
        ScheduledJob.scheduled_date == today,
        ScheduledJob.status.in_(['scheduled', 'in_progress'])
    ).order_by(ScheduledJob.machine_id, ScheduledJob.sequence_order).all()

    # Sorting queue count
    sorting_count = AwaitingSorting.query.filter_by(status='pending').count()

    return render_template('scheduling/technician.html',
                          machines=machines,
                          todays_jobs=todays_jobs,
                          sorting_count=sorting_count,
                          today=today)


@scheduling_bp.route('/technician/machine/<int:machine_id>')
@login_required
def technician_machine(machine_id):
    """Shop floor view for a specific machine"""
    machine = Machine.query.get_or_404(machine_id)
    today = date.today()

    # Get current job (in progress)
    current_job = ScheduledJob.query.filter_by(
        machine_id=machine_id,
        status='in_progress'
    ).first()

    # Get upcoming jobs for this machine
    upcoming_jobs = ScheduledJob.query.filter(
        ScheduledJob.machine_id == machine_id,
        ScheduledJob.scheduled_date >= today,
        ScheduledJob.status.in_(['scheduled', 'in_progress'])
    ).order_by(ScheduledJob.scheduled_date, ScheduledJob.sequence_order).limit(10).all()

    # Get next job (first scheduled job)
    next_job = None
    if not current_job and upcoming_jobs:
        next_job = upcoming_jobs[0]
    elif current_job:
        for job in upcoming_jobs:
            if job.status == 'scheduled':
                next_job = job
                break

    return render_template('scheduling/technician_machine.html',
                          machine=machine,
                          current_job=current_job,
                          next_job=next_job,
                          upcoming_jobs=upcoming_jobs,
                          today=today)
