import os
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, make_response, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.orders import SalesOrder, SalesOrderLine, Delivery, Customer
from app.models.inventory import Item, StockLevel, StockMovement
from app.models.production import ProductionOrder
from app.utils.pdf import generate_packing_list, generate_delivery_note

orders_bp = Blueprint('orders', __name__)


@orders_bp.route('/')
@login_required
def order_list():
    """List sales orders"""
    status = request.args.get('status', '')
    customer_id = request.args.get('customer_id', type=int)
    show_archived = request.args.get('archived', '') == '1'

    query = SalesOrder.query

    if status:
        query = query.filter_by(status=status)
    elif not show_archived:
        # Hide archived orders by default unless specifically filtering
        query = query.filter(SalesOrder.status != 'archived')

    if customer_id:
        query = query.filter_by(customer_id=customer_id)

    orders = query.order_by(SalesOrder.created_at.desc()).all()
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()

    # Count archived orders
    archived_count = SalesOrder.query.filter_by(status='archived').count()

    return render_template('orders/list.html',
                           orders=orders,
                           customers=customers,
                           status=status,
                           customer_id=customer_id,
                           show_archived=show_archived,
                           archived_count=archived_count)


@orders_bp.route('/new', methods=['GET', 'POST'])
@login_required
def order_create():
    """Create new sales order"""
    if request.method == 'POST':
        customer_id = request.form.get('customer_id', type=int)

        if not customer_id:
            flash('Customer is required', 'error')
            customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
            return render_template('orders/form.html', order=None, customers=customers)

        customer = Customer.query.get_or_404(customer_id)

        # Parse required date
        required_date_str = request.form.get('required_date', '')
        required_date = None
        if required_date_str:
            try:
                required_date = datetime.strptime(required_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        order = SalesOrder(
            order_number=SalesOrder.generate_order_number(),
            customer_id=customer_id,
            customer_po=request.form.get('customer_po', '').strip(),
            required_date=required_date,
            delivery_method=request.form.get('delivery_method', ''),
            delivery_address_line1=request.form.get('delivery_address_line1', '').strip() or customer.address_line1,
            delivery_address_line2=request.form.get('delivery_address_line2', '').strip() or customer.address_line2,
            delivery_city=request.form.get('delivery_city', '').strip() or customer.city,
            delivery_county=request.form.get('delivery_county', '').strip() or customer.county,
            delivery_postcode=request.form.get('delivery_postcode', '').strip() or customer.postcode,
            delivery_country=request.form.get('delivery_country', '').strip() or customer.country,
            delivery_instructions=request.form.get('delivery_instructions', '').strip(),
            notes=request.form.get('notes', '').strip(),
            internal_notes=request.form.get('internal_notes', '').strip()
        )

        db.session.add(order)
        db.session.commit()

        flash(f'Order {order.order_number} created. Now add line items.', 'success')
        return redirect(url_for('orders.order_edit', order_id=order.id))

    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    return render_template('orders/form.html', order=None, customers=customers)


@orders_bp.route('/<int:order_id>')
@login_required
def order_detail(order_id):
    """View order details"""
    order = SalesOrder.query.get_or_404(order_id)
    return render_template('orders/detail.html', order=order)


@orders_bp.route('/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required
def order_edit(order_id):
    """Edit order and manage line items"""
    order = SalesOrder.query.get_or_404(order_id)

    if request.method == 'POST':
        # Update order header
        order.customer_po = request.form.get('customer_po', '').strip()
        order.delivery_method = request.form.get('delivery_method', '')
        order.shipping_cost = request.form.get('shipping_cost', 0, type=float)
        order.delivery_address_line1 = request.form.get('delivery_address_line1', '').strip()
        order.delivery_address_line2 = request.form.get('delivery_address_line2', '').strip()
        order.delivery_city = request.form.get('delivery_city', '').strip()
        order.delivery_county = request.form.get('delivery_county', '').strip()
        order.delivery_postcode = request.form.get('delivery_postcode', '').strip()
        order.delivery_country = request.form.get('delivery_country', '').strip()
        order.delivery_instructions = request.form.get('delivery_instructions', '').strip()
        order.notes = request.form.get('notes', '').strip()
        order.internal_notes = request.form.get('internal_notes', '').strip()

        required_date_str = request.form.get('required_date', '')
        if required_date_str:
            try:
                order.required_date = datetime.strptime(required_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        # Recalculate totals with new shipping cost
        order.calculate_totals()
        db.session.commit()
        flash('Order updated successfully', 'success')
        return redirect(url_for('orders.order_detail', order_id=order.id))

    items = Item.query.filter_by(is_active=True).order_by(Item.sku).all()
    return render_template('orders/edit.html', order=order, items=items)


@orders_bp.route('/<int:order_id>/add-line', methods=['POST'])
@login_required
def add_line(order_id):
    """Add line item to order"""
    order = SalesOrder.query.get_or_404(order_id)

    if order.status not in ['new', 'in_production']:
        flash('Cannot modify order in current status', 'error')
        return redirect(url_for('orders.order_edit', order_id=order.id))

    is_custom = request.form.get('is_custom', '0') == '1'
    quantity = request.form.get('quantity', 0, type=float)
    unit_price = request.form.get('unit_price', 0, type=float)

    if quantity <= 0:
        flash('Valid quantity is required', 'error')
        return redirect(url_for('orders.order_edit', order_id=order.id))

    # Get next line number
    max_line = db.session.query(db.func.max(SalesOrderLine.line_number)).filter_by(order_id=order.id).scalar()
    line_number = (max_line or 0) + 1

    if is_custom:
        # Custom item - no item_id, use custom fields
        custom_description = request.form.get('custom_description', '').strip()
        if not custom_description:
            flash('Description is required for custom items', 'error')
            return redirect(url_for('orders.order_edit', order_id=order.id))

        if not unit_price:
            flash('Unit price is required for custom items', 'error')
            return redirect(url_for('orders.order_edit', order_id=order.id))

        line = SalesOrderLine(
            order_id=order.id,
            item_id=None,
            line_number=line_number,
            is_custom_item=True,
            custom_sku=request.form.get('custom_sku', '').strip(),
            custom_description=custom_description,
            quantity_ordered=quantity,
            unit_price=unit_price,
            notes=request.form.get('notes', '').strip()
        )
        line.calculate_line_total()

        db.session.add(line)
        order.calculate_totals()
        db.session.commit()

        flash(f'Added custom item to order', 'success')
    else:
        # Stock item
        item_id = request.form.get('item_id', type=int)
        if not item_id:
            flash('Item is required', 'error')
            return redirect(url_for('orders.order_edit', order_id=order.id))

        item = Item.query.get_or_404(item_id)

        line = SalesOrderLine(
            order_id=order.id,
            item_id=item_id,
            line_number=line_number,
            is_custom_item=False,
            quantity_ordered=quantity,
            unit_price=unit_price or item.selling_price or 0,
            notes=request.form.get('notes', '').strip()
        )
        line.calculate_line_total()

        db.session.add(line)
        order.calculate_totals()
        db.session.commit()

        flash(f'Added {quantity} x {item.sku} to order', 'success')

    return redirect(url_for('orders.order_edit', order_id=order.id))


@orders_bp.route('/<int:order_id>/remove-line/<int:line_id>', methods=['POST'])
@login_required
def remove_line(order_id, line_id):
    """Remove line item from order"""
    order = SalesOrder.query.get_or_404(order_id)
    line = SalesOrderLine.query.get_or_404(line_id)

    if line.order_id != order.id:
        flash('Line does not belong to this order', 'error')
        return redirect(url_for('orders.order_edit', order_id=order.id))

    if order.status not in ['new', 'in_production']:
        flash('Cannot modify order in current status', 'error')
        return redirect(url_for('orders.order_edit', order_id=order.id))

    db.session.delete(line)
    order.calculate_totals()
    db.session.commit()

    flash('Line removed from order', 'success')
    return redirect(url_for('orders.order_edit', order_id=order.id))


@orders_bp.route('/<int:order_id>/update-status', methods=['POST'])
@login_required
def update_status(order_id):
    """Update order status"""
    order = SalesOrder.query.get_or_404(order_id)
    new_status = request.form.get('status', '')

    valid_transitions = {
        'new': ['in_production', 'ready_to_ship', 'cancelled'],
        'in_production': ['ready_to_ship', 'new', 'cancelled'],
        'ready_to_ship': ['dispatched', 'partially_shipped', 'in_production'],
        'partially_shipped': ['dispatched', 'ready_to_ship'],
        'dispatched': ['delivered'],
        'delivered': ['archived'],
        'cancelled': ['new', 'archived'],
        'archived': []
    }

    if new_status not in valid_transitions.get(order.status, []):
        flash(f'Cannot change status from {order.status} to {new_status}', 'error')
        return redirect(url_for('orders.order_detail', order_id=order.id))

    order.status = new_status
    db.session.commit()

    flash(f'Order status updated to {new_status}', 'success')
    return redirect(url_for('orders.order_detail', order_id=order.id))


@orders_bp.route('/<int:order_id>/check-stock')
@login_required
def check_stock(order_id):
    """Check stock levels for all items in order"""
    order = SalesOrder.query.get_or_404(order_id)

    stock_status = []
    all_in_stock = True
    total_shortfall = 0

    for line in order.lines:
        if line.is_custom_item:
            # Custom items don't have stock
            stock_status.append({
                'line': line,
                'item': None,
                'sku': line.custom_sku or 'CUSTOM',
                'name': line.custom_description,
                'required': line.quantity_ordered,
                'available': None,
                'shortfall': 0,
                'status': 'custom'
            })
        else:
            item = line.item
            available = item.total_stock if item else 0
            required = line.quantity_ordered - line.quantity_shipped
            shortfall = max(0, required - available)

            if shortfall > 0:
                all_in_stock = False
                total_shortfall += shortfall

            stock_status.append({
                'line': line,
                'item': item,
                'sku': item.sku if item else 'N/A',
                'name': item.name if item else 'Unknown',
                'required': required,
                'available': available,
                'shortfall': shortfall,
                'status': 'ok' if shortfall == 0 else 'short'
            })

    return render_template('orders/check_stock.html',
                          order=order,
                          stock_status=stock_status,
                          all_in_stock=all_in_stock,
                          total_shortfall=total_shortfall)


@orders_bp.route('/<int:order_id>/process', methods=['POST'])
@login_required
def process_order(order_id):
    """Process order - check stock and auto-create production orders for shortfalls"""
    order = SalesOrder.query.get_or_404(order_id)

    if order.status not in ['new', 'in_production']:
        flash('Order cannot be processed in current status', 'error')
        return redirect(url_for('orders.order_detail', order_id=order.id))

    production_orders_created = []
    items_in_stock = []
    items_short = []

    for line in order.lines:
        if line.is_custom_item:
            continue

        item = line.item
        if not item:
            continue

        available = item.total_stock
        required = line.quantity_ordered - line.quantity_shipped
        shortfall = max(0, required - available)

        if shortfall > 0:
            items_short.append({'item': item, 'shortfall': shortfall})

            # Check if production order already exists for this item linked to this sales order
            existing_po = ProductionOrder.query.filter_by(
                item_id=item.id,
                sales_order_id=order.id,
                status='planned'
            ).first()

            if existing_po:
                # Update quantity if needed
                if existing_po.quantity_required < shortfall:
                    existing_po.quantity_required = shortfall
                    production_orders_created.append({
                        'order': existing_po,
                        'action': 'updated',
                        'item': item
                    })
            else:
                # Create new production order
                # Calculate priority based on due date
                priority = 5
                if order.required_date:
                    days_until = (order.required_date - date.today()).days
                    if days_until <= 1:
                        priority = 1
                    elif days_until <= 3:
                        priority = 2
                    elif days_until <= 7:
                        priority = 3

                po = ProductionOrder(
                    order_number=ProductionOrder.generate_order_number(),
                    item_id=item.id,
                    mould_id=item.default_mould_id,
                    quantity_required=shortfall,
                    order_type='make_to_order',
                    priority=priority,
                    due_date=order.required_date,
                    sales_order_id=order.id,
                    customer_id=order.customer_id,
                    notes=f'Auto-created for order {order.order_number}'
                )
                db.session.add(po)
                production_orders_created.append({
                    'order': po,
                    'action': 'created',
                    'item': item
                })
        else:
            items_in_stock.append({'item': item, 'available': available})

    # Update order status
    if items_short:
        order.status = 'in_production'
    else:
        order.status = 'ready_to_ship'

    db.session.commit()

    # Build flash message
    if production_orders_created:
        po_list = ', '.join([f"{po['item'].sku} ({int(po['order'].quantity_required)} pcs)" for po in production_orders_created])
        flash(f'Created {len(production_orders_created)} production order(s): {po_list}', 'success')

    if items_in_stock and not items_short:
        flash('All items in stock - order ready to ship!', 'success')
    elif items_in_stock:
        in_stock_list = ', '.join([f"{item['item'].sku}" for item in items_in_stock])
        flash(f'Items in stock: {in_stock_list}', 'info')

    return redirect(url_for('orders.order_detail', order_id=order.id))


@orders_bp.route('/<int:order_id>/allocate-stock', methods=['POST'])
@login_required
def allocate_stock(order_id):
    """Allocate available stock to order lines"""
    order = SalesOrder.query.get_or_404(order_id)

    if order.status not in ['new', 'in_production', 'ready_to_ship']:
        flash('Cannot allocate stock in current status', 'error')
        return redirect(url_for('orders.order_detail', order_id=order.id))

    allocated_count = 0

    for line in order.lines:
        if line.is_custom_item:
            continue

        item = line.item
        if not item:
            continue

        required = line.quantity_ordered - line.quantity_allocated
        if required <= 0:
            continue

        available = item.available_stock
        to_allocate = min(required, available)

        if to_allocate > 0:
            line.quantity_allocated += to_allocate
            allocated_count += 1

            # Update stock allocation
            remaining_to_allocate = to_allocate
            for sl in item.stock_levels.filter(StockLevel.quantity > StockLevel.allocated_quantity).all():
                if remaining_to_allocate <= 0:
                    break
                can_allocate = sl.quantity - sl.allocated_quantity
                allocate = min(can_allocate, remaining_to_allocate)
                sl.allocated_quantity += allocate
                remaining_to_allocate -= allocate

    db.session.commit()

    if allocated_count > 0:
        flash(f'Allocated stock for {allocated_count} line(s)', 'success')
    else:
        flash('No stock available to allocate', 'warning')

    return redirect(url_for('orders.order_detail', order_id=order.id))


@orders_bp.route('/<int:order_id>/packing-list')
@login_required
def packing_list(order_id):
    """Generate packing list PDF"""
    order = SalesOrder.query.get_or_404(order_id)

    pdf_buffer = generate_packing_list(order)

    response = make_response(pdf_buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=packing_list_{order.order_number}.pdf'

    return response


@orders_bp.route('/<int:order_id>/delivery-note')
@login_required
def delivery_note(order_id):
    """Generate delivery note PDF (customer-facing, for signing)"""
    order = SalesOrder.query.get_or_404(order_id)

    pdf_buffer = generate_delivery_note(order)

    response = make_response(pdf_buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=delivery_note_{order.order_number}.pdf'

    return response


@orders_bp.route('/delivery/<int:delivery_id>/upload-signed', methods=['POST'])
@login_required
def upload_signed_delivery_note(delivery_id):
    """Upload a signed delivery note (photo/scan) for a delivery"""
    delivery = Delivery.query.get_or_404(delivery_id)

    if 'signed_note' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('orders.order_detail', order_id=delivery.order_id))

    file = request.files['signed_note']
    if not file or not file.filename:
        flash('No file selected', 'error')
        return redirect(url_for('orders.order_detail', order_id=delivery.order_id))

    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext not in current_app.config['ALLOWED_EXTENSIONS']:
        flash('Invalid file type. Allowed: PNG, JPG, PDF', 'error')
        return redirect(url_for('orders.order_detail', order_id=delivery.order_id))

    filename = secure_filename(f"signed_{delivery.delivery_number}_{file.filename}")
    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
    delivery.signed_delivery_note = filename
    db.session.commit()

    flash(f'Signed delivery note uploaded for {delivery.delivery_number}', 'success')
    return redirect(url_for('orders.order_detail', order_id=delivery.order_id))


@orders_bp.route('/<int:order_id>/dispatch', methods=['GET', 'POST'])
@login_required
def dispatch(order_id):
    """Dispatch order (create delivery record) - supports partial deliveries"""
    order = SalesOrder.query.get_or_404(order_id)

    # Allow dispatch from ready_to_ship or partially_shipped status
    if order.status not in ['ready_to_ship', 'partially_shipped']:
        flash('Order must be ready to ship before dispatching', 'error')
        return redirect(url_for('orders.order_detail', order_id=order.id))

    if request.method == 'POST':
        # Check if any quantities to ship
        total_shipping = 0
        line_quantities = {}

        for line in order.lines:
            qty_key = f'qty_{line.id}'
            qty_to_ship = request.form.get(qty_key, 0, type=float)
            remaining = line.quantity_ordered - line.quantity_shipped

            # Cap at remaining quantity
            qty_to_ship = min(qty_to_ship, remaining)
            if qty_to_ship > 0:
                line_quantities[line.id] = qty_to_ship
                total_shipping += qty_to_ship

        if total_shipping <= 0:
            flash('No items selected for dispatch', 'error')
            return redirect(url_for('orders.dispatch', order_id=order.id))

        # Create delivery record
        delivery = Delivery(
            delivery_number=Delivery.generate_delivery_number(),
            order_id=order.id,
            delivery_method=request.form.get('delivery_method', order.delivery_method),
            carrier=request.form.get('carrier', '').strip(),
            tracking_number=request.form.get('tracking_number', '').strip(),
            driver=request.form.get('driver', '').strip(),
            num_packages=request.form.get('num_packages', 1, type=int),
            total_weight=request.form.get('total_weight', type=float),
            notes=request.form.get('notes', '').strip(),
            dispatch_date=datetime.utcnow(),
            status='dispatched'
        )
        db.session.add(delivery)

        # Process each line with quantities to ship
        all_complete = True
        for line in order.lines:
            qty_to_ship = line_quantities.get(line.id, 0)
            if qty_to_ship <= 0:
                # Check if this line is already complete
                if line.quantity_shipped < line.quantity_ordered:
                    all_complete = False
                continue

            # Update shipped quantity
            line.quantity_shipped += qty_to_ship

            # Check if line is complete
            if line.quantity_shipped < line.quantity_ordered:
                all_complete = False

            # Deduct from inventory (only for stock items, not custom items)
            if not line.is_custom_item and line.item:
                item = line.item
                quantity_to_deduct = qty_to_ship

                for sl in item.stock_levels.filter(StockLevel.quantity > 0).all():
                    if quantity_to_deduct <= 0:
                        break

                    deduct = min(sl.quantity, quantity_to_deduct)
                    sl.quantity -= deduct
                    quantity_to_deduct -= deduct

                    # Record movement
                    movement = StockMovement(
                        item_id=item.id,
                        movement_type='shipment',
                        quantity=-deduct,
                        from_location_id=sl.location_id,
                        reference=order.order_number,
                        notes=f'Dispatched to {order.customer.name} ({delivery.delivery_number})',
                        user_id=current_user.id
                    )
                    db.session.add(movement)

        # Update order status based on completion
        if all_complete:
            order.status = 'dispatched'
            flash(f'Order fully dispatched. Delivery number: {delivery.delivery_number}', 'success')
        else:
            order.status = 'partially_shipped'
            flash(f'Partial shipment created. Delivery number: {delivery.delivery_number}. Order remains open for remaining items.', 'success')

        db.session.commit()
        return redirect(url_for('orders.order_detail', order_id=order.id))

    return render_template('orders/dispatch.html', order=order)


@orders_bp.route('/<int:order_id>/archive', methods=['POST'])
@login_required
def archive_order(order_id):
    """Archive a completed or cancelled order"""
    order = SalesOrder.query.get_or_404(order_id)

    if order.status not in ['delivered', 'cancelled']:
        flash('Only delivered or cancelled orders can be archived', 'error')
        return redirect(url_for('orders.order_detail', order_id=order.id))

    order.status = 'archived'
    db.session.commit()

    flash(f'Order {order.order_number} has been archived', 'success')
    return redirect(url_for('orders.order_list'))


@orders_bp.route('/archive-all', methods=['POST'])
@login_required
def archive_all_completed():
    """Archive all delivered and cancelled orders"""
    if not current_user.is_admin():
        flash('Admin access required', 'error')
        return redirect(url_for('orders.order_list'))

    # Archive all delivered and cancelled orders
    orders = SalesOrder.query.filter(
        SalesOrder.status.in_(['delivered', 'cancelled'])
    ).all()

    count = 0
    for order in orders:
        order.status = 'archived'
        count += 1

    db.session.commit()

    if count > 0:
        flash(f'Archived {count} orders', 'success')
    else:
        flash('No orders to archive', 'info')

    return redirect(url_for('orders.order_list'))


@orders_bp.route('/<int:order_id>/delete', methods=['POST'])
@login_required
def order_delete(order_id):
    """Delete an order permanently"""
    if not current_user.is_admin():
        flash('Admin access required to delete orders', 'error')
        return redirect(url_for('orders.order_list'))

    order = SalesOrder.query.get_or_404(order_id)
    order_number = order.order_number

    # Delete all order lines first
    for line in order.lines:
        db.session.delete(line)

    # Delete any deliveries
    for delivery in order.deliveries:
        db.session.delete(delivery)

    # Delete the order
    db.session.delete(order)
    db.session.commit()

    flash(f'Order {order_number} has been permanently deleted', 'success')
    return redirect(url_for('orders.order_list'))


# API endpoints
@orders_bp.route('/api/search')
@login_required
def api_search():
    """Search orders via API"""
    query = request.args.get('q', '').strip()

    orders = SalesOrder.query.filter(
        db.or_(
            SalesOrder.order_number.ilike(f'%{query}%'),
            SalesOrder.customer_po.ilike(f'%{query}%')
        )
    ).limit(20).all()

    return jsonify([{
        'id': o.id,
        'order_number': o.order_number,
        'customer': o.customer.name,
        'status': o.status,
        'total': o.total
    } for o in orders])


@orders_bp.route('/api/<int:order_id>')
@login_required
def api_order_detail(order_id):
    """Get order details via API"""
    order = SalesOrder.query.get_or_404(order_id)

    return jsonify({
        'id': order.id,
        'order_number': order.order_number,
        'customer': {
            'id': order.customer.id,
            'name': order.customer.name
        },
        'status': order.status,
        'required_date': order.required_date.isoformat() if order.required_date else None,
        'subtotal': order.subtotal,
        'tax_amount': order.tax_amount,
        'total': order.total,
        'lines': [{
            'item_sku': line.custom_sku if line.is_custom_item else line.item.sku,
            'item_name': line.custom_description if line.is_custom_item else line.item.name,
            'is_custom': line.is_custom_item,
            'quantity': line.quantity_ordered,
            'shipped': line.quantity_shipped,
            'unit_price': line.unit_price,
            'line_total': line.line_total
        } for line in order.lines]
    })
