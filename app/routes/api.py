from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db
from app.models.inventory import Item, StockLevel, StockMovement
from app.models.location import Location
from app.models.production import ProductionOrder, Machine

api_bp = Blueprint('api', __name__)


@api_bp.route('/scan', methods=['POST'])
@login_required
def scan_barcode():
    """
    Process scanned barcode and return item/location info
    This is the main endpoint for the mobile scanning feature
    """
    data = request.get_json()
    barcode = data.get('barcode', '').strip()
    context = data.get('context', 'lookup')  # lookup, receive, move, pick

    if not barcode:
        return jsonify({'error': 'No barcode provided'}), 400

    # Try to find as item
    item = Item.query.filter(
        db.or_(
            Item.barcode == barcode,
            Item.sku == barcode
        ),
        Item.is_active == True
    ).first()

    if item:
        stock_levels = [{
            'location_id': sl.location.id,
            'location_code': sl.location.code,
            'location_name': sl.location.name,
            'quantity': sl.quantity,
            'available': sl.available_quantity
        } for sl in item.stock_levels.filter(StockLevel.quantity > 0).all()]

        return jsonify({
            'type': 'item',
            'id': item.id,
            'sku': item.sku,
            'name': item.name,
            'description': item.description,
            'barcode': item.barcode,
            'total_stock': item.total_stock,
            'available_stock': item.available_stock,
            'unit': item.unit_of_measure,
            'image': item.image_filename,
            'is_low_stock': item.is_low_stock,
            'stock_levels': stock_levels,
            'context': context
        })

    # Try to find as location
    location = Location.query.filter(
        Location.code == barcode.upper(),
        Location.is_active == True
    ).first()

    if location:
        contents = [{
            'item_id': sl.item.id,
            'sku': sl.item.sku,
            'name': sl.item.name,
            'quantity': sl.quantity,
            'unit': sl.item.unit_of_measure
        } for sl in location.stock_levels.filter(StockLevel.quantity > 0).all()]

        return jsonify({
            'type': 'location',
            'id': location.id,
            'code': location.code,
            'name': location.name,
            'zone': location.zone,
            'location_type': location.location_type,
            'capacity': location.max_capacity,
            'current_usage': location.current_usage,
            'contents': contents,
            'context': context
        })

    return jsonify({'error': 'Barcode not found', 'barcode': barcode}), 404


@api_bp.route('/quick-receive', methods=['POST'])
@login_required
def quick_receive():
    """Quick stock receive via mobile"""
    data = request.get_json()
    item_id = data.get('item_id')
    location_id = data.get('location_id')
    quantity = data.get('quantity', 0)
    batch_number = data.get('batch_number', '')

    if not item_id or not location_id or quantity <= 0:
        return jsonify({'error': 'Invalid data'}), 400

    item = Item.query.get(item_id)
    location = Location.query.get(location_id)

    if not item or not location:
        return jsonify({'error': 'Item or location not found'}), 404

    # Update stock level
    stock_level = StockLevel.query.filter_by(
        item_id=item_id,
        location_id=location_id
    ).first()

    if stock_level:
        stock_level.quantity += quantity
    else:
        stock_level = StockLevel(
            item_id=item_id,
            location_id=location_id,
            quantity=quantity,
            batch_number=batch_number
        )
        db.session.add(stock_level)

    # Record movement
    movement = StockMovement(
        item_id=item_id,
        movement_type='receipt',
        quantity=quantity,
        to_location_id=location_id,
        batch_number=batch_number,
        notes='Quick receive via mobile',
        user_id=current_user.id
    )
    db.session.add(movement)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Received {quantity} {item.unit_of_measure} of {item.sku} at {location.code}',
        'new_quantity': stock_level.quantity
    })


@api_bp.route('/quick-move', methods=['POST'])
@login_required
def quick_move():
    """Quick stock move via mobile"""
    data = request.get_json()
    item_id = data.get('item_id')
    from_location_id = data.get('from_location_id')
    to_location_id = data.get('to_location_id')
    quantity = data.get('quantity', 0)

    if not all([item_id, from_location_id, to_location_id]) or quantity <= 0:
        return jsonify({'error': 'Invalid data'}), 400

    if from_location_id == to_location_id:
        return jsonify({'error': 'From and To locations must be different'}), 400

    item = Item.query.get(item_id)
    from_location = Location.query.get(from_location_id)
    to_location = Location.query.get(to_location_id)

    if not all([item, from_location, to_location]):
        return jsonify({'error': 'Item or location not found'}), 404

    # Check source stock
    from_stock = StockLevel.query.filter_by(
        item_id=item_id,
        location_id=from_location_id
    ).first()

    if not from_stock or from_stock.quantity < quantity:
        return jsonify({'error': 'Insufficient stock at source location'}), 400

    # Update source
    from_stock.quantity -= quantity

    # Update destination
    to_stock = StockLevel.query.filter_by(
        item_id=item_id,
        location_id=to_location_id
    ).first()

    if to_stock:
        to_stock.quantity += quantity
    else:
        to_stock = StockLevel(
            item_id=item_id,
            location_id=to_location_id,
            quantity=quantity,
            batch_number=from_stock.batch_number
        )
        db.session.add(to_stock)

    # Record movement
    movement = StockMovement(
        item_id=item_id,
        movement_type='movement',
        quantity=quantity,
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        notes='Quick move via mobile',
        user_id=current_user.id
    )
    db.session.add(movement)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Moved {quantity} {item.unit_of_measure} of {item.sku} from {from_location.code} to {to_location.code}'
    })


@api_bp.route('/production/start', methods=['POST'])
@login_required
def start_production():
    """Start production job via mobile"""
    data = request.get_json()
    order_id = data.get('order_id')
    machine_id = data.get('machine_id')

    if not order_id or not machine_id:
        return jsonify({'error': 'Order and machine are required'}), 400

    order = ProductionOrder.query.get(order_id)
    machine = Machine.query.get(machine_id)

    if not order or not machine:
        return jsonify({'error': 'Order or machine not found'}), 404

    if order.status != 'planned':
        return jsonify({'error': 'Can only start planned orders'}), 400

    from datetime import datetime
    from app.models.production import ProductionLog

    order.status = 'in_progress'
    order.machine_id = machine_id
    order.start_date = datetime.utcnow()

    machine.status = 'running'
    machine.current_mould_id = order.mould_id

    log = ProductionLog(
        production_order_id=order.id,
        machine_id=machine_id,
        operator_id=current_user.id,
        log_type='start',
        notes=f'Started via mobile by {current_user.username}'
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Production started for {order.order_number} on {machine.name}',
        'order_number': order.order_number
    })


@api_bp.route('/production/update', methods=['POST'])
@login_required
def update_production():
    """Update production quantity via mobile"""
    data = request.get_json()
    order_id = data.get('order_id')
    good_quantity = data.get('good_quantity', 0)
    rejected_quantity = data.get('rejected_quantity', 0)

    if not order_id:
        return jsonify({'error': 'Order is required'}), 400

    order = ProductionOrder.query.get(order_id)

    if not order:
        return jsonify({'error': 'Order not found'}), 404

    if order.status != 'in_progress':
        return jsonify({'error': 'Can only update in-progress orders'}), 400

    from app.models.production import ProductionLog

    order.quantity_produced += (good_quantity + rejected_quantity)
    order.quantity_good += good_quantity
    order.quantity_rejected += rejected_quantity

    log = ProductionLog(
        production_order_id=order.id,
        machine_id=order.machine_id,
        operator_id=current_user.id,
        log_type='quantity_update',
        quantity=good_quantity + rejected_quantity,
        good_quantity=good_quantity,
        rejected_quantity=rejected_quantity,
        notes='Updated via mobile'
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Updated: +{good_quantity} good, +{rejected_quantity} rejected',
        'total_produced': order.quantity_produced,
        'completion': order.completion_percentage
    })


@api_bp.route('/dashboard-stats')
@login_required
def dashboard_stats():
    """Get dashboard statistics for mobile"""
    from sqlalchemy import func

    # Inventory stats
    total_items = Item.query.filter_by(is_active=True).count()

    items_with_reorder = Item.query.filter(
        Item.is_active == True,
        Item.reorder_point != None
    ).all()
    low_stock_count = sum(1 for item in items_with_reorder if item.is_low_stock)

    # Production stats
    active_jobs = ProductionOrder.query.filter_by(status='in_progress').count()
    planned_jobs = ProductionOrder.query.filter_by(status='planned').count()

    # Order stats
    from app.models.orders import SalesOrder
    pending_orders = SalesOrder.query.filter(
        SalesOrder.status.in_(['new', 'in_production'])
    ).count()
    ready_to_ship = SalesOrder.query.filter_by(status='ready_to_ship').count()

    # Machine status
    machines = Machine.query.filter_by(is_active=True).all()
    machines_running = sum(1 for m in machines if m.status == 'running')

    return jsonify({
        'inventory': {
            'total_items': total_items,
            'low_stock': low_stock_count
        },
        'production': {
            'active_jobs': active_jobs,
            'planned_jobs': planned_jobs
        },
        'orders': {
            'pending': pending_orders,
            'ready_to_ship': ready_to_ship
        },
        'machines': {
            'total': len(machines),
            'running': machines_running,
            'idle': len(machines) - machines_running
        }
    })
