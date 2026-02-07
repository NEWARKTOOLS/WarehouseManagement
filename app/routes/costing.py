"""
Costing & Profitability Routes
Quoting, job costing, and business intelligence
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc
from app import db
from app.models.costing import JobCosting, MaterialUsage, MachineRate, LabourRate, Quote, CustomerProfitability
from app.models.oee import ShiftLog, DowntimeReason, DowntimeEvent, ScrapReason, ScrapEvent
from app.models.orders import Customer, SalesOrder
from app.models.production import ProductionOrder, Machine
from app.models.inventory import Item

bp = Blueprint('costing', __name__, url_prefix='/costing')


@bp.before_request
@login_required
def check_pricing_access():
    """Block operational roles (picker/setter) from accessing costing pages"""
    if not current_user.can_view_pricing():
        flash('Access denied. Your role does not have access to financial data.', 'error')
        return redirect(url_for('main.dashboard'))


# ============== QUOTES ==============

@bp.route('/quotes')
@login_required
def quote_list():
    """List all quotes"""
    status_filter = request.args.get('status', 'all')
    customer_id = request.args.get('customer_id', type=int)

    query = Quote.query

    if status_filter != 'all':
        query = query.filter(Quote.status == status_filter)

    if customer_id:
        query = query.filter(Quote.customer_id == customer_id)

    quotes = query.order_by(Quote.created_at.desc()).all()
    customers = Customer.query.order_by(Customer.name).all()

    # Stats
    stats = {
        'draft': Quote.query.filter_by(status='draft').count(),
        'sent': Quote.query.filter_by(status='sent').count(),
        'accepted': Quote.query.filter_by(status='accepted').count(),
        'total_value': db.session.query(func.sum(Quote.quoted_total)).filter(Quote.status == 'sent').scalar() or 0
    }

    return render_template('costing/quotes.html',
                           quotes=quotes,
                           customers=customers,
                           status_filter=status_filter,
                           customer_id=customer_id,
                           stats=stats,
                           today=date.today())


@bp.route('/quotes/new', methods=['GET', 'POST'])
@login_required
def quote_new():
    """Create new quote"""
    if request.method == 'POST':
        quote = Quote(
            quote_number=Quote.generate_quote_number(),
            customer_id=request.form.get('customer_id', type=int),
            item_id=request.form.get('item_id', type=int) or None,
            description=request.form.get('description'),
            quantity=request.form.get('quantity', type=float) or 1000,
            annual_volume=request.form.get('annual_volume', type=float),
            part_weight_g=request.form.get('part_weight_g', type=float),
            runner_weight_g=request.form.get('runner_weight_g', type=float),
            cycle_time_seconds=request.form.get('cycle_time_seconds', type=float),
            cavities=request.form.get('cavities', type=int) or 1,
            material_type=request.form.get('material_type'),
            material_cost_per_kg=request.form.get('material_cost_per_kg', type=float) or 0,
            machine_rate_per_hour=request.form.get('machine_rate_per_hour', type=float) or 45,
            labour_rate_per_hour=request.form.get('labour_rate_per_hour', type=float) or 15,
            setup_hours=request.form.get('setup_hours', type=float) or 2,
            secondary_ops_cost=request.form.get('secondary_ops_cost', type=float) or 0,
            overhead_percent=request.form.get('overhead_percent', type=float) or 20,
            packaging_cost_per_part=request.form.get('packaging_cost_per_part', type=float) or 0,
            target_margin_percent=request.form.get('target_margin_percent', type=float) or 30,
            tooling_cost=request.form.get('tooling_cost', type=float) or 0,
            tooling_amortization_qty=request.form.get('tooling_amortization_qty', type=float),
            valid_until=datetime.strptime(request.form.get('valid_until'), '%Y-%m-%d').date() if request.form.get('valid_until') else None,
            notes=request.form.get('notes'),
            internal_notes=request.form.get('internal_notes'),
            status='draft'
        )

        # Calculate all costs
        quote.calculate_costs()

        db.session.add(quote)
        db.session.commit()

        flash(f'Quote {quote.quote_number} created successfully', 'success')
        return redirect(url_for('costing.quote_detail', quote_id=quote.id))

    customers = Customer.query.order_by(Customer.name).all()
    # Get all finished goods items (also include items without type set but with production data)
    items = Item.query.filter(
        db.or_(
            Item.item_type == 'finished_goods',
            Item.item_type == 'finished_good',
            db.and_(Item.part_weight_grams.isnot(None), Item.part_weight_grams > 0)
        )
    ).filter_by(is_active=True).order_by(Item.sku).all()

    # Default rates
    default_machine_rate = 45  # GBP/hour
    default_labour_rate = 15   # GBP/hour

    return render_template('costing/quote_form.html',
                           customers=customers,
                           items=items,
                           quote=None,
                           default_machine_rate=default_machine_rate,
                           default_labour_rate=default_labour_rate)


@bp.route('/quotes/<int:quote_id>')
@login_required
def quote_detail(quote_id):
    """View quote details"""
    quote = Quote.query.get_or_404(quote_id)
    return render_template('costing/quote_detail.html', quote=quote)


@bp.route('/quotes/<int:quote_id>/edit', methods=['GET', 'POST'])
@login_required
def quote_edit(quote_id):
    """Edit quote"""
    quote = Quote.query.get_or_404(quote_id)

    if request.method == 'POST':
        quote.customer_id = request.form.get('customer_id', type=int)
        quote.item_id = request.form.get('item_id', type=int) or None
        quote.description = request.form.get('description')
        quote.quantity = request.form.get('quantity', type=float) or 1000
        quote.annual_volume = request.form.get('annual_volume', type=float)
        quote.part_weight_g = request.form.get('part_weight_g', type=float)
        quote.runner_weight_g = request.form.get('runner_weight_g', type=float)
        quote.cycle_time_seconds = request.form.get('cycle_time_seconds', type=float)
        quote.cavities = request.form.get('cavities', type=int) or 1
        quote.material_type = request.form.get('material_type')
        quote.material_cost_per_kg = request.form.get('material_cost_per_kg', type=float) or 0
        quote.machine_rate_per_hour = request.form.get('machine_rate_per_hour', type=float) or 45
        quote.labour_rate_per_hour = request.form.get('labour_rate_per_hour', type=float) or 15
        quote.setup_hours = request.form.get('setup_hours', type=float) or 2
        quote.secondary_ops_cost = request.form.get('secondary_ops_cost', type=float) or 0
        quote.overhead_percent = request.form.get('overhead_percent', type=float) or 20
        quote.packaging_cost_per_part = request.form.get('packaging_cost_per_part', type=float) or 0
        quote.target_margin_percent = request.form.get('target_margin_percent', type=float) or 30
        quote.tooling_cost = request.form.get('tooling_cost', type=float) or 0
        quote.tooling_amortization_qty = request.form.get('tooling_amortization_qty', type=float)
        quote.valid_until = datetime.strptime(request.form.get('valid_until'), '%Y-%m-%d').date() if request.form.get('valid_until') else None
        quote.notes = request.form.get('notes')
        quote.internal_notes = request.form.get('internal_notes')

        # Recalculate costs
        quote.calculate_costs()
        quote.updated_at = datetime.utcnow()

        db.session.commit()
        flash('Quote updated', 'success')
        return redirect(url_for('costing.quote_detail', quote_id=quote.id))

    customers = Customer.query.order_by(Customer.name).all()
    items = Item.query.filter_by(item_type='finished_good').order_by(Item.sku).all()

    return render_template('costing/quote_form.html',
                           customers=customers,
                           items=items,
                           quote=quote,
                           default_machine_rate=45,
                           default_labour_rate=15)


@bp.route('/quotes/<int:quote_id>/recalculate', methods=['POST'])
@login_required
def quote_recalculate(quote_id):
    """Recalculate quote costs (AJAX)"""
    quote = Quote.query.get_or_404(quote_id)
    quote.calculate_costs()
    db.session.commit()

    return jsonify({
        'material_cost_per_part': round(quote.material_cost_per_part, 4),
        'cycle_cost_per_part': round(quote.cycle_cost_per_part, 4),
        'setup_cost_per_part': round(quote.setup_cost_per_part, 4),
        'overhead_cost_per_part': round(quote.overhead_cost_per_part, 4),
        'total_cost_per_part': round(quote.total_cost_per_part, 4),
        'quoted_price_per_part': round(quote.quoted_price_per_part, 4),
        'quoted_total': round(quote.quoted_total, 2)
    })


@bp.route('/quotes/<int:quote_id>/status', methods=['POST'])
@login_required
def quote_status(quote_id):
    """Update quote status"""
    quote = Quote.query.get_or_404(quote_id)
    new_status = request.form.get('status')

    if new_status in ['draft', 'sent', 'accepted', 'rejected', 'expired']:
        quote.status = new_status
        if new_status == 'sent':
            quote.sent_at = datetime.utcnow()
        db.session.commit()
        flash(f'Quote marked as {new_status}', 'success')

    return redirect(url_for('costing.quote_detail', quote_id=quote.id))


@bp.route('/quotes/<int:quote_id>/convert', methods=['POST'])
@login_required
def quote_convert_to_order(quote_id):
    """Convert accepted quote to sales order"""
    quote = Quote.query.get_or_404(quote_id)

    if quote.status != 'accepted':
        flash('Only accepted quotes can be converted to orders', 'warning')
        return redirect(url_for('costing.quote_detail', quote_id=quote.id))

    # Create sales order
    order = SalesOrder(
        order_number=SalesOrder.generate_order_number() if hasattr(SalesOrder, 'generate_order_number') else f"SO-{datetime.now().strftime('%y%m%d%H%M%S')}",
        customer_id=quote.customer_id,
        order_date=date.today(),
        status='new',
        notes=f"Converted from quote {quote.quote_number}"
    )
    db.session.add(order)
    db.session.flush()

    # Link quote to order
    quote.sales_order_id = order.id
    db.session.commit()

    flash(f'Created order {order.order_number} from quote', 'success')
    return redirect(url_for('orders.order_detail', order_id=order.id))


# ============== BUSINESS INTELLIGENCE DASHBOARD ==============

@bp.route('/dashboard')
@login_required
def bi_dashboard():
    """Business intelligence dashboard - profitability overview"""
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    # This month's production orders
    month_orders = ProductionOrder.query.filter(
        ProductionOrder.created_at >= month_start
    ).all()

    # Revenue from completed orders this month
    month_completed = SalesOrder.query.filter(
        SalesOrder.status.in_(['delivered', 'dispatched']),
        SalesOrder.updated_at >= month_start
    ).all()
    month_revenue = sum(o.total or 0 for o in month_completed)

    # Customer profitability ranking
    customer_stats = db.session.query(
        Customer.id,
        Customer.name,
        func.count(SalesOrder.id).label('order_count'),
        func.sum(SalesOrder.subtotal).label('revenue')
    ).join(SalesOrder).filter(
        SalesOrder.order_date >= year_start
    ).group_by(Customer.id).order_by(desc('revenue')).limit(10).all()

    # Top items by revenue
    top_items = db.session.query(
        Item.id,
        Item.sku,
        Item.name,
        func.count(ProductionOrder.id).label('production_count')
    ).join(ProductionOrder).filter(
        ProductionOrder.created_at >= year_start
    ).group_by(Item.id).order_by(desc('production_count')).limit(10).all()

    # Machine utilization - based on actual in_progress production orders
    machines = Machine.query.filter_by(is_active=True).all()
    machine_stats = []
    for m in machines:
        running_jobs = ProductionOrder.query.filter(
            ProductionOrder.machine_id == m.id,
            ProductionOrder.status == 'in_progress'
        ).count()
        # Determine actual status from running jobs, not just machine.status
        if running_jobs > 0:
            actual_status = 'running'
        elif m.status == 'maintenance':
            actual_status = 'maintenance'
        else:
            actual_status = 'idle'
        machine_stats.append({
            'machine': m,
            'running_jobs': running_jobs,
            'status': actual_status
        })

    # Quote conversion rate
    total_quotes = Quote.query.filter(Quote.created_at >= year_start).count()
    accepted_quotes = Quote.query.filter(
        Quote.created_at >= year_start,
        Quote.status == 'accepted'
    ).count()
    conversion_rate = (accepted_quotes / total_quotes * 100) if total_quotes > 0 else 0

    # Pending quote value
    pending_quote_value = db.session.query(func.sum(Quote.quoted_total)).filter(
        Quote.status == 'sent'
    ).scalar() or 0

    return render_template('costing/dashboard.html',
                           today=today,
                           month_revenue=month_revenue,
                           customer_stats=customer_stats,
                           top_items=top_items,
                           machine_stats=machine_stats,
                           conversion_rate=conversion_rate,
                           pending_quote_value=pending_quote_value,
                           total_quotes=total_quotes,
                           accepted_quotes=accepted_quotes)


# ============== JOB COSTING ==============

@bp.route('/jobs')
@login_required
def job_costing_list():
    """List production orders with costing data"""
    # Get production orders with their costing
    orders = ProductionOrder.query.filter(
        ProductionOrder.status.in_(['completed', 'in_progress'])
    ).order_by(ProductionOrder.created_at.desc()).limit(50).all()

    return render_template('costing/jobs.html', orders=orders)


@bp.route('/jobs/<int:order_id>')
@login_required
def job_costing_detail(order_id):
    """View job costing details"""
    order = ProductionOrder.query.get_or_404(order_id)

    # Get or create costing record
    costing = JobCosting.query.filter_by(production_order_id=order.id).first()
    if not costing:
        costing = JobCosting(production_order_id=order.id)
        db.session.add(costing)
        db.session.commit()

    # Get material usage
    materials = MaterialUsage.query.filter_by(production_order_id=order.id).all()

    return render_template('costing/job_detail.html',
                           order=order,
                           costing=costing,
                           materials=materials)


@bp.route('/jobs/<int:order_id>/update', methods=['POST'])
@login_required
def job_costing_update(order_id):
    """Update job costing data"""
    order = ProductionOrder.query.get_or_404(order_id)
    costing = JobCosting.query.filter_by(production_order_id=order.id).first()

    if not costing:
        costing = JobCosting(production_order_id=order.id)
        db.session.add(costing)

    # Update actual costs
    costing.actual_material_cost = request.form.get('actual_material_cost', type=float) or 0
    costing.actual_material_kg = request.form.get('actual_material_kg', type=float) or 0
    costing.actual_labour_hours = request.form.get('actual_labour_hours', type=float) or 0
    costing.actual_machine_hours = request.form.get('actual_machine_hours', type=float) or 0
    costing.actual_setup_hours = request.form.get('actual_setup_hours', type=float) or 0
    costing.scrap_quantity = request.form.get('scrap_quantity', type=float) or 0
    costing.scrap_cost = request.form.get('scrap_cost', type=float) or 0
    costing.actual_selling_price = request.form.get('actual_selling_price', type=float) or 0

    # Calculate labour and machine costs based on hours
    labour_rate = 15  # Default GBP/hour
    machine_rate = 45  # Default GBP/hour

    costing.actual_labour_cost = costing.actual_labour_hours * labour_rate
    costing.actual_machine_cost = costing.actual_machine_hours * machine_rate

    costing.updated_at = datetime.utcnow()
    db.session.commit()

    flash('Job costing updated', 'success')
    return redirect(url_for('costing.job_costing_detail', order_id=order.id))


# ============== RATES MANAGEMENT ==============

@bp.route('/rates')
@login_required
def rates_list():
    """Manage machine and labour rates"""
    machine_rates = MachineRate.query.order_by(MachineRate.effective_from.desc()).all()
    labour_rates = LabourRate.query.order_by(LabourRate.effective_from.desc()).all()
    machines = Machine.query.filter_by(is_active=True).all()

    return render_template('costing/rates.html',
                           machine_rates=machine_rates,
                           labour_rates=labour_rates,
                           machines=machines,
                           today=date.today())


@bp.route('/rates/machine', methods=['POST'])
@login_required
def add_machine_rate():
    """Add new machine rate"""
    rate = MachineRate(
        machine_id=request.form.get('machine_id', type=int),
        hourly_rate=request.form.get('hourly_rate', type=float) or 0,
        setup_rate=request.form.get('setup_rate', type=float) or 0,
        energy_rate_per_kwh=request.form.get('energy_rate_per_kwh', type=float) or 0.15,
        running_kw=request.form.get('running_kw', type=float) or 0,
        overhead_rate_per_hour=request.form.get('overhead_rate_per_hour', type=float) or 0,
        effective_from=datetime.strptime(request.form.get('effective_from'), '%Y-%m-%d').date()
    )
    db.session.add(rate)
    db.session.commit()
    flash('Machine rate added', 'success')
    return redirect(url_for('costing.rates_list'))


@bp.route('/rates/labour', methods=['POST'])
@login_required
def add_labour_rate():
    """Add new labour rate"""
    rate = LabourRate(
        role=request.form.get('role'),
        hourly_rate=request.form.get('hourly_rate', type=float) or 0,
        overtime_multiplier=request.form.get('overtime_multiplier', type=float) or 1.5,
        effective_from=datetime.strptime(request.form.get('effective_from'), '%Y-%m-%d').date()
    )
    db.session.add(rate)
    db.session.commit()
    flash('Labour rate added', 'success')
    return redirect(url_for('costing.rates_list'))


# ============== OEE TRACKING ==============

@bp.route('/oee')
@login_required
def oee_dashboard():
    """OEE Dashboard - overall equipment effectiveness"""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    machines = Machine.query.filter_by(is_active=True).all()

    # Get today's shift logs for each machine
    machine_oee = []
    for machine in machines:
        today_log = ShiftLog.query.filter_by(
            machine_id=machine.id,
            shift_date=today
        ).first()

        # Get last 7 days average
        week_logs = ShiftLog.query.filter(
            ShiftLog.machine_id == machine.id,
            ShiftLog.shift_date >= week_start
        ).all()

        week_oee = sum(log.oee_percent for log in week_logs) / len(week_logs) if week_logs else 0
        week_scrap = sum(log.scrap_percent for log in week_logs) / len(week_logs) if week_logs else 0

        machine_oee.append({
            'machine': machine,
            'today_log': today_log,
            'today_oee': today_log.oee_percent if today_log else 0,
            'today_availability': today_log.availability_percent if today_log else 0,
            'today_performance': today_log.performance_percent if today_log else 0,
            'today_quality': today_log.quality_percent if today_log else 0,
            'week_oee': week_oee,
            'week_scrap': week_scrap
        })

    # Overall plant OEE
    today_logs = ShiftLog.query.filter_by(shift_date=today).all()
    plant_oee = sum(log.oee_percent for log in today_logs) / len(today_logs) if today_logs else 0

    # Top scrap reasons this month
    scrap_by_reason = db.session.query(
        ScrapReason.name,
        func.sum(ScrapEvent.quantity).label('total_qty')
    ).join(ScrapEvent).filter(
        ScrapEvent.occurred_at >= month_start
    ).group_by(ScrapReason.id).order_by(desc('total_qty')).limit(5).all()

    # Top downtime reasons this month
    downtime_by_reason = db.session.query(
        DowntimeReason.name,
        func.sum(DowntimeEvent.duration_minutes).label('total_minutes')
    ).join(DowntimeEvent).filter(
        DowntimeEvent.start_time >= month_start
    ).group_by(DowntimeReason.id).order_by(desc('total_minutes')).limit(5).all()

    return render_template('costing/oee_dashboard.html',
                           today=today,
                           machine_oee=machine_oee,
                           plant_oee=plant_oee,
                           scrap_by_reason=scrap_by_reason,
                           downtime_by_reason=downtime_by_reason)


@bp.route('/oee/log/<int:machine_id>', methods=['GET', 'POST'])
@login_required
def oee_log_shift(machine_id):
    """Log shift data for OEE calculation"""
    machine = Machine.query.get_or_404(machine_id)
    log_date = request.args.get('date', date.today().isoformat())
    log_date = datetime.strptime(log_date, '%Y-%m-%d').date()

    # Get or create shift log
    shift_log = ShiftLog.query.filter_by(
        machine_id=machine_id,
        shift_date=log_date
    ).first()

    if request.method == 'POST':
        if not shift_log:
            shift_log = ShiftLog(machine_id=machine_id, shift_date=log_date)
            db.session.add(shift_log)

        # Update log data
        shift_log.planned_production_minutes = request.form.get('planned_production_minutes', type=float) or 480
        shift_log.breakdown_minutes = request.form.get('breakdown_minutes', type=float) or 0
        shift_log.setup_changeover_minutes = request.form.get('setup_changeover_minutes', type=float) or 0
        shift_log.material_shortage_minutes = request.form.get('material_shortage_minutes', type=float) or 0
        shift_log.other_downtime_minutes = request.form.get('other_downtime_minutes', type=float) or 0
        shift_log.downtime_notes = request.form.get('downtime_notes')

        shift_log.ideal_cycle_time_seconds = request.form.get('ideal_cycle_time_seconds', type=float)
        shift_log.parts_per_cycle = request.form.get('parts_per_cycle', type=int) or 1

        shift_log.total_parts_produced = request.form.get('total_parts_produced', type=int) or 0
        shift_log.good_parts = request.form.get('good_parts', type=int) or 0
        shift_log.scrap_parts = request.form.get('scrap_parts', type=int) or 0
        shift_log.rework_parts = request.form.get('rework_parts', type=int) or 0

        shift_log.scrap_startup = request.form.get('scrap_startup', type=int) or 0
        shift_log.scrap_short_shot = request.form.get('scrap_short_shot', type=int) or 0
        shift_log.scrap_flash = request.form.get('scrap_flash', type=int) or 0
        shift_log.scrap_other = request.form.get('scrap_other', type=int) or 0
        shift_log.scrap_notes = request.form.get('scrap_notes')

        shift_log.operator_name = request.form.get('operator_name')
        shift_log.production_order_id = request.form.get('production_order_id', type=int) or None

        db.session.commit()
        flash(f'Shift log saved for {machine.name}', 'success')
        return redirect(url_for('costing.oee_dashboard'))

    # Get active production orders for this machine
    active_orders = ProductionOrder.query.filter(
        ProductionOrder.machine_id == machine_id,
        ProductionOrder.status.in_(['scheduled', 'in_progress'])
    ).all()

    return render_template('costing/oee_log.html',
                           machine=machine,
                           log_date=log_date,
                           shift_log=shift_log,
                           active_orders=active_orders)


@bp.route('/oee/history/<int:machine_id>')
@login_required
def oee_history(machine_id):
    """View OEE history for a machine"""
    machine = Machine.query.get_or_404(machine_id)

    # Get last 30 days of logs
    thirty_days_ago = date.today() - timedelta(days=30)
    logs = ShiftLog.query.filter(
        ShiftLog.machine_id == machine_id,
        ShiftLog.shift_date >= thirty_days_ago
    ).order_by(ShiftLog.shift_date.desc()).all()

    # Calculate averages
    if logs:
        avg_oee = sum(log.oee_percent for log in logs) / len(logs)
        avg_availability = sum(log.availability_percent for log in logs) / len(logs)
        avg_performance = sum(log.performance_percent for log in logs) / len(logs)
        avg_quality = sum(log.quality_percent for log in logs) / len(logs)
        avg_scrap = sum(log.scrap_percent for log in logs) / len(logs)
    else:
        avg_oee = avg_availability = avg_performance = avg_quality = avg_scrap = 0

    return render_template('costing/oee_history.html',
                           machine=machine,
                           logs=logs,
                           avg_oee=avg_oee,
                           avg_availability=avg_availability,
                           avg_performance=avg_performance,
                           avg_quality=avg_quality,
                           avg_scrap=avg_scrap)


@bp.route('/scrap/log', methods=['POST'])
@login_required
def log_scrap():
    """Quick log scrap event"""
    event = ScrapEvent(
        machine_id=request.form.get('machine_id', type=int),
        production_order_id=request.form.get('production_order_id', type=int) or None,
        reason_id=request.form.get('reason_id', type=int) or None,
        quantity=request.form.get('quantity', type=int) or 0,
        weight_kg=request.form.get('weight_kg', type=float),
        notes=request.form.get('notes'),
        reported_by=request.form.get('reported_by')
    )
    db.session.add(event)
    db.session.commit()
    flash('Scrap logged', 'success')

    return redirect(request.referrer or url_for('costing.oee_dashboard'))
