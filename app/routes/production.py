import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.production import Machine, Mould, MouldMaintenance, SetupSheet, ProductionOrder, ProductionLog
from app.models.inventory import Item, StockLevel, StockMovement
from app.models.location import Location
from app.models.orders import SalesOrder, Customer

production_bp = Blueprint('production', __name__)


# Machines
@production_bp.route('/machines')
@login_required
def machine_list():
    """List all machines"""
    machines = Machine.query.filter_by(is_active=True).order_by(Machine.name).all()
    return render_template('production/machines.html', machines=machines)


@production_bp.route('/machines/new', methods=['GET', 'POST'])
@login_required
def machine_create():
    """Create new machine"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        machine_code = request.form.get('machine_code', '').strip().upper()
        tonnage = request.form.get('tonnage', type=int)
        manufacturer = request.form.get('manufacturer', 'Borche').strip()
        model = request.form.get('model', '').strip()
        notes = request.form.get('notes', '').strip()

        if not name or not machine_code:
            flash('Name and machine code are required', 'error')
            return render_template('production/machine_form.html', machine=None)

        machine = Machine(
            name=name,
            machine_code=machine_code,
            tonnage=tonnage,
            manufacturer=manufacturer,
            model=model,
            notes=notes
        )
        db.session.add(machine)
        db.session.commit()

        flash(f'Machine {name} created successfully', 'success')
        return redirect(url_for('production.machine_list'))

    return render_template('production/machine_form.html', machine=None)


@production_bp.route('/machines/<int:machine_id>/edit', methods=['GET', 'POST'])
@login_required
def machine_edit(machine_id):
    """Edit machine"""
    machine = Machine.query.get_or_404(machine_id)

    if request.method == 'POST':
        machine.name = request.form.get('name', '').strip()
        machine.tonnage = request.form.get('tonnage', type=int)
        machine.manufacturer = request.form.get('manufacturer', 'Borche').strip()
        machine.model = request.form.get('model', '').strip()
        machine.status = request.form.get('status', 'idle')
        machine.notes = request.form.get('notes', '').strip()

        db.session.commit()
        flash(f'Machine {machine.name} updated successfully', 'success')
        return redirect(url_for('production.machine_list'))

    return render_template('production/machine_form.html', machine=machine)


# Production Orders
@production_bp.route('/orders')
@login_required
def order_list():
    """List production orders"""
    status = request.args.get('status', '')

    query = ProductionOrder.query

    if status:
        query = query.filter_by(status=status)

    orders = query.order_by(ProductionOrder.priority, ProductionOrder.due_date).all()
    return render_template('production/orders.html', orders=orders, status=status)


@production_bp.route('/orders/new', methods=['GET', 'POST'])
@login_required
def order_create():
    """Create production order"""
    # Pre-fill from sales order if specified
    sales_order_id = request.args.get('sales_order_id', type=int)
    prefill_item_id = request.args.get('item_id', type=int)
    prefill_quantity = request.args.get('quantity', type=float)

    if request.method == 'POST':
        item_id = request.form.get('item_id', type=int)
        mould_id = request.form.get('mould_id', type=int) or None
        machine_id = request.form.get('machine_id', type=int) or None
        quantity_required = request.form.get('quantity_required', 0, type=float)
        order_type = request.form.get('order_type', 'make_to_stock')
        priority = request.form.get('priority', 5, type=int)
        due_date_str = request.form.get('due_date', '')
        notes = request.form.get('notes', '').strip()
        sales_order_id = request.form.get('sales_order_id', type=int) or None
        customer_id = request.form.get('customer_id', type=int) or None

        if not item_id or quantity_required <= 0:
            flash('Item and valid quantity are required', 'error')
            items = Item.query.filter_by(is_active=True).order_by(Item.sku).all()
            moulds = Mould.query.filter_by(is_active=True).order_by(Mould.mould_number).all()
            machines = Machine.query.filter_by(is_active=True).order_by(Machine.name).all()
            customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
            sales_orders = SalesOrder.query.filter(SalesOrder.status.in_(['new', 'in_production'])).order_by(SalesOrder.required_date).all()
            return render_template('production/order_form.html', order=None, items=items, moulds=moulds,
                                   machines=machines, customers=customers, sales_orders=sales_orders)

        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        # Auto-select mould for item if not specified
        if not mould_id:
            item = Item.query.get(item_id)
            if item and item.default_mould_id:
                mould_id = item.default_mould_id

        order = ProductionOrder(
            order_number=ProductionOrder.generate_order_number(),
            item_id=item_id,
            mould_id=mould_id,
            machine_id=machine_id,
            quantity_required=quantity_required,
            order_type=order_type,
            priority=priority,
            due_date=due_date,
            notes=notes,
            sales_order_id=sales_order_id,
            customer_id=customer_id
        )
        db.session.add(order)
        db.session.commit()

        flash(f'Production order {order.order_number} created successfully', 'success')
        return redirect(url_for('production.order_detail', order_id=order.id))

    # GET - show form
    items = Item.query.filter_by(is_active=True).order_by(Item.sku).all()
    moulds = Mould.query.filter_by(is_active=True).order_by(Mould.mould_number).all()
    machines = Machine.query.filter_by(is_active=True).order_by(Machine.name).all()
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    sales_orders = SalesOrder.query.filter(SalesOrder.status.in_(['new', 'in_production'])).order_by(SalesOrder.required_date).all()

    # Pre-fill data
    prefill = {}
    if sales_order_id:
        sales_order = SalesOrder.query.get(sales_order_id)
        if sales_order:
            prefill['sales_order_id'] = sales_order_id
            prefill['customer_id'] = sales_order.customer_id
            prefill['due_date'] = sales_order.required_date
            # Set priority based on urgency
            if sales_order.required_date:
                from datetime import date, timedelta
                days_until = (sales_order.required_date - date.today()).days
                if days_until <= 1:
                    prefill['priority'] = 1
                elif days_until <= 3:
                    prefill['priority'] = 2
                elif days_until <= 7:
                    prefill['priority'] = 3
                else:
                    prefill['priority'] = 5
    if prefill_item_id:
        prefill['item_id'] = prefill_item_id
    if prefill_quantity:
        prefill['quantity'] = prefill_quantity

    return render_template('production/order_form.html',
                          order=None,
                          items=items,
                          moulds=moulds,
                          machines=machines,
                          customers=customers,
                          sales_orders=sales_orders,
                          prefill=prefill)


@production_bp.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    """View production order details"""
    order = ProductionOrder.query.get_or_404(order_id)
    logs = order.production_logs.order_by(ProductionLog.created_at.desc()).all()

    # Get setup sheet if available
    setup_sheet = None
    if order.item_id and order.mould_id:
        setup_sheet = SetupSheet.query.filter_by(
            item_id=order.item_id,
            mould_id=order.mould_id,
            is_current=True
        ).first()

    # Get machines and locations for forms
    machines = Machine.query.filter_by(is_active=True).order_by(Machine.name).all()
    locations = Location.query.filter_by(is_active=True).order_by(Location.code).all()

    return render_template('production/order_detail.html',
                           order=order,
                           logs=logs,
                           setup_sheet=setup_sheet,
                           machines=machines,
                           locations=locations)


@production_bp.route('/orders/<int:order_id>/start', methods=['POST'])
@login_required
def order_start(order_id):
    """Start production"""
    order = ProductionOrder.query.get_or_404(order_id)

    if order.status != 'planned':
        flash('Can only start planned orders', 'error')
        return redirect(url_for('production.order_detail', order_id=order.id))

    machine_id = request.form.get('machine_id', type=int)
    if not machine_id:
        flash('Please select a machine', 'error')
        return redirect(url_for('production.order_detail', order_id=order.id))

    machine = Machine.query.get_or_404(machine_id)

    order.status = 'in_progress'
    order.machine_id = machine_id
    order.start_date = datetime.utcnow()

    machine.status = 'running'
    machine.current_mould_id = order.mould_id

    # Log the start
    log = ProductionLog(
        production_order_id=order.id,
        machine_id=machine_id,
        operator_id=current_user.id,
        log_type='start',
        notes=f'Production started on {machine.name}'
    )
    db.session.add(log)
    db.session.commit()

    flash(f'Production started for {order.order_number} on {machine.name}', 'success')
    return redirect(url_for('production.order_detail', order_id=order.id))


@production_bp.route('/orders/<int:order_id>/update-quantity', methods=['POST'])
@login_required
def order_update_quantity(order_id):
    """Update production quantity"""
    order = ProductionOrder.query.get_or_404(order_id)

    if order.status != 'in_progress':
        flash('Can only update in-progress orders', 'error')
        return redirect(url_for('production.order_detail', order_id=order.id))

    good_quantity = request.form.get('good_quantity', 0, type=float)
    rejected_quantity = request.form.get('rejected_quantity', 0, type=float)
    notes = request.form.get('notes', '').strip()

    order.quantity_produced += (good_quantity + rejected_quantity)
    order.quantity_good += good_quantity
    order.quantity_rejected += rejected_quantity

    # Log the update
    log = ProductionLog(
        production_order_id=order.id,
        machine_id=order.machine_id,
        operator_id=current_user.id,
        log_type='quantity_update',
        quantity=good_quantity + rejected_quantity,
        good_quantity=good_quantity,
        rejected_quantity=rejected_quantity,
        notes=notes
    )
    db.session.add(log)
    db.session.commit()

    flash(f'Quantity updated: +{good_quantity} good, +{rejected_quantity} rejected', 'success')
    return redirect(url_for('production.order_detail', order_id=order.id))


@production_bp.route('/orders/<int:order_id>/complete', methods=['POST'])
@login_required
def order_complete(order_id):
    """Complete production order"""
    order = ProductionOrder.query.get_or_404(order_id)

    if order.status != 'in_progress':
        flash('Can only complete in-progress orders', 'error')
        return redirect(url_for('production.order_detail', order_id=order.id))

    location_id = request.form.get('location_id', type=int)
    final_good_quantity = request.form.get('final_good_quantity', type=float)
    notes = request.form.get('notes', '').strip()

    if final_good_quantity is not None:
        order.quantity_good = final_good_quantity

    order.status = 'completed'
    order.end_date = datetime.utcnow()

    # Update machine status
    if order.machine:
        order.machine.status = 'idle'
        order.machine.current_mould_id = None

    # Add to inventory if location specified
    if location_id and order.quantity_good > 0:
        stock_level = StockLevel.query.filter_by(
            item_id=order.item_id,
            location_id=location_id
        ).first()

        if stock_level:
            stock_level.quantity += order.quantity_good
        else:
            stock_level = StockLevel(
                item_id=order.item_id,
                location_id=location_id,
                quantity=order.quantity_good
            )
            db.session.add(stock_level)

        # Record movement
        movement = StockMovement(
            item_id=order.item_id,
            movement_type='production',
            quantity=order.quantity_good,
            to_location_id=location_id,
            reference=order.order_number,
            notes=f'Production complete: {notes}',
            user_id=current_user.id
        )
        db.session.add(movement)

    # Log completion
    log = ProductionLog(
        production_order_id=order.id,
        machine_id=order.machine_id,
        operator_id=current_user.id,
        log_type='stop',
        quantity=order.quantity_good,
        good_quantity=order.quantity_good,
        rejected_quantity=order.quantity_rejected,
        notes=f'Production completed. {notes}'
    )
    db.session.add(log)
    db.session.commit()

    flash(f'Production order {order.order_number} completed', 'success')
    return redirect(url_for('production.order_detail', order_id=order.id))


@production_bp.route('/orders/<int:order_id>/report-issue', methods=['POST'])
@login_required
def order_report_issue(order_id):
    """Report production issue"""
    order = ProductionOrder.query.get_or_404(order_id)

    issue_type = request.form.get('issue_type', '').strip()
    description = request.form.get('description', '').strip()

    if not issue_type or not description:
        flash('Issue type and description are required', 'error')
        return redirect(url_for('production.order_detail', order_id=order.id))

    log = ProductionLog(
        production_order_id=order.id,
        machine_id=order.machine_id,
        operator_id=current_user.id,
        log_type='issue',
        issue_type=issue_type,
        issue_description=description
    )
    db.session.add(log)
    db.session.commit()

    flash('Issue reported successfully', 'success')
    return redirect(url_for('production.order_detail', order_id=order.id))


# Setup Sheets
@production_bp.route('/setup-sheets')
@login_required
def setup_sheet_list():
    """List all setup sheets"""
    setup_sheets = SetupSheet.query.filter_by(is_current=True).all()
    return render_template('production/setup_sheets.html', setup_sheets=setup_sheets)


@production_bp.route('/setup-sheets/new', methods=['GET', 'POST'])
@login_required
def setup_sheet_create():
    """Create new setup sheet"""
    if request.method == 'POST':
        item_id = request.form.get('item_id', type=int)
        mould_id = request.form.get('mould_id', type=int)

        if not item_id or not mould_id:
            flash('Item and mould are required', 'error')
            items = Item.query.filter_by(is_active=True).order_by(Item.sku).all()
            moulds = Mould.query.filter_by(is_active=True).order_by(Mould.mould_number).all()
            return render_template('production/setup_sheet_form.html', setup_sheet=None, items=items, moulds=moulds)

        # Mark existing as not current
        existing = SetupSheet.query.filter_by(
            item_id=item_id,
            mould_id=mould_id,
            is_current=True
        ).first()
        if existing:
            existing.is_current = False

        setup_sheet = SetupSheet(
            item_id=item_id,
            mould_id=mould_id,
            program_number=request.form.get('program_number', '').strip(),
            barrel_temp_zone1=request.form.get('barrel_temp_zone1', type=float),
            barrel_temp_zone2=request.form.get('barrel_temp_zone2', type=float),
            barrel_temp_zone3=request.form.get('barrel_temp_zone3', type=float),
            barrel_temp_zone4=request.form.get('barrel_temp_zone4', type=float),
            mould_temp=request.form.get('mould_temp', type=float),
            nozzle_temp=request.form.get('nozzle_temp', type=float),
            injection_pressure=request.form.get('injection_pressure', type=float),
            injection_speed=request.form.get('injection_speed', type=float),
            injection_time=request.form.get('injection_time', type=float),
            holding_pressure=request.form.get('holding_pressure', type=float),
            holding_time=request.form.get('holding_time', type=float),
            cooling_time=request.form.get('cooling_time', type=float),
            cycle_time=request.form.get('cycle_time', type=float),
            material_type=request.form.get('material_type', '').strip(),
            material_grade=request.form.get('material_grade', '').strip(),
            color=request.form.get('color', '').strip(),
            masterbatch_ratio=request.form.get('masterbatch_ratio', '').strip(),
            quality_checks=request.form.get('quality_checks', '').strip(),
            notes=request.form.get('notes', '').strip(),
            special_instructions=request.form.get('special_instructions', '').strip(),
            version=(existing.version + 1) if existing else 1
        )

        db.session.add(setup_sheet)
        db.session.commit()

        flash('Setup sheet created successfully', 'success')
        return redirect(url_for('production.setup_sheet_view', setup_sheet_id=setup_sheet.id))

    items = Item.query.filter_by(is_active=True).order_by(Item.sku).all()
    moulds = Mould.query.filter_by(is_active=True).order_by(Mould.mould_number).all()
    return render_template('production/setup_sheet_form.html', setup_sheet=None, items=items, moulds=moulds)


@production_bp.route('/setup-sheets/<int:setup_sheet_id>')
@login_required
def setup_sheet_view(setup_sheet_id):
    """View setup sheet (mobile-friendly)"""
    setup_sheet = SetupSheet.query.get_or_404(setup_sheet_id)
    return render_template('production/setup_sheet_view.html', setup_sheet=setup_sheet)


# API endpoints
@production_bp.route('/api/active-jobs')
@login_required
def api_active_jobs():
    """Get active production jobs"""
    orders = ProductionOrder.query.filter_by(status='in_progress').all()

    return jsonify([{
        'id': o.id,
        'order_number': o.order_number,
        'item_sku': o.item.sku,
        'item_name': o.item.name,
        'machine': o.machine.name if o.machine else None,
        'quantity_required': o.quantity_required,
        'quantity_produced': o.quantity_produced,
        'completion': o.completion_percentage
    } for o in orders])


@production_bp.route('/api/machines/status')
@login_required
def api_machines_status():
    """Get all machine statuses"""
    machines = Machine.query.filter_by(is_active=True).all()

    return jsonify([{
        'id': m.id,
        'name': m.name,
        'code': m.machine_code,
        'tonnage': m.tonnage,
        'status': m.status,
        'current_mould': m.current_mould.mould_number if m.current_mould else None
    } for m in machines])
