from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, make_response
from flask_login import login_required
from sqlalchemy import func
from app import db
from app.models.inventory import Item, StockLevel, StockMovement, Category
from app.models.production import ProductionOrder, Machine, Mould
from app.models.orders import SalesOrder, Customer
from app.models.quality import NonConformance

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/')
@login_required
def report_index():
    """Reports landing page"""
    return render_template('reports/index.html')


# Inventory Reports
@reports_bp.route('/inventory/stock-on-hand')
@login_required
def stock_on_hand():
    """Stock on hand report"""
    category_id = request.args.get('category', type=int)
    location_id = request.args.get('location', type=int)
    item_type = request.args.get('type', '')

    query = db.session.query(
        Item, StockLevel
    ).outerjoin(StockLevel).filter(Item.is_active == True)

    if category_id:
        query = query.filter(Item.category_id == category_id)
    if item_type:
        query = query.filter(Item.item_type == item_type)

    results = query.all()

    # Aggregate by item
    stock_data = {}
    for item, stock_level in results:
        if item.id not in stock_data:
            stock_data[item.id] = {
                'item': item,
                'total_quantity': 0,
                'locations': []
            }
        if stock_level and stock_level.quantity > 0:
            if not location_id or stock_level.location_id == location_id:
                stock_data[item.id]['total_quantity'] += stock_level.quantity
                stock_data[item.id]['locations'].append({
                    'location': stock_level.location,
                    'quantity': stock_level.quantity
                })

    categories = Category.query.order_by(Category.name).all()
    from app.models.location import Location
    locations = Location.query.filter_by(is_active=True).order_by(Location.code).all()

    return render_template('reports/stock_on_hand.html',
                           stock_data=stock_data.values(),
                           categories=categories,
                           locations=locations,
                           category_id=category_id,
                           location_id=location_id,
                           item_type=item_type)


@reports_bp.route('/inventory/low-stock')
@login_required
def low_stock():
    """Low stock report"""
    items = Item.query.filter_by(is_active=True).all()
    low_stock_items = [item for item in items if item.is_low_stock]

    return render_template('reports/low_stock.html', items=low_stock_items)


@reports_bp.route('/inventory/stock-value')
@login_required
def stock_value():
    """Stock valuation report"""
    items = Item.query.filter_by(is_active=True).all()

    total_value = 0
    item_values = []

    for item in items:
        quantity = item.total_stock
        value = quantity * (item.unit_cost or 0)
        total_value += value

        if quantity > 0:
            item_values.append({
                'item': item,
                'quantity': quantity,
                'unit_cost': item.unit_cost or 0,
                'value': value
            })

    # Sort by value descending
    item_values.sort(key=lambda x: x['value'], reverse=True)

    return render_template('reports/stock_value.html',
                           item_values=item_values,
                           total_value=total_value)


@reports_bp.route('/inventory/movements')
@login_required
def stock_movements():
    """Stock movement history report"""
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    movement_type = request.args.get('type', '')
    item_id = request.args.get('item_id', type=int)

    query = StockMovement.query

    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(StockMovement.created_at >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(StockMovement.created_at < end)
        except ValueError:
            pass

    if movement_type:
        query = query.filter_by(movement_type=movement_type)

    if item_id:
        query = query.filter_by(item_id=item_id)

    movements = query.order_by(StockMovement.created_at.desc()).limit(500).all()
    items = Item.query.filter_by(is_active=True).order_by(Item.sku).all()

    return render_template('reports/stock_movements.html',
                           movements=movements,
                           items=items,
                           start_date=start_date,
                           end_date=end_date,
                           movement_type=movement_type,
                           item_id=item_id)


# Production Reports
@reports_bp.route('/production/summary')
@login_required
def production_summary():
    """Production summary report"""
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    # Default to current month
    if not start_date:
        start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')

    query = ProductionOrder.query.filter(ProductionOrder.status == 'completed')

    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(
            ProductionOrder.end_date >= start,
            ProductionOrder.end_date < end
        )
    except ValueError:
        pass

    orders = query.all()

    # Aggregate by item
    production_by_item = {}
    for order in orders:
        item_id = order.item_id
        if item_id not in production_by_item:
            production_by_item[item_id] = {
                'item': order.item,
                'total_produced': 0,
                'total_good': 0,
                'total_rejected': 0,
                'order_count': 0
            }
        production_by_item[item_id]['total_produced'] += order.quantity_produced
        production_by_item[item_id]['total_good'] += order.quantity_good
        production_by_item[item_id]['total_rejected'] += order.quantity_rejected
        production_by_item[item_id]['order_count'] += 1

    # Calculate totals
    totals = {
        'produced': sum(p['total_produced'] for p in production_by_item.values()),
        'good': sum(p['total_good'] for p in production_by_item.values()),
        'rejected': sum(p['total_rejected'] for p in production_by_item.values()),
        'orders': sum(p['order_count'] for p in production_by_item.values())
    }

    return render_template('reports/production_summary.html',
                           production_data=production_by_item.values(),
                           totals=totals,
                           start_date=start_date,
                           end_date=end_date)


@reports_bp.route('/production/machine-utilization')
@login_required
def machine_utilization():
    """Machine utilization report"""
    machines = Machine.query.filter_by(is_active=True).all()

    # Calculate utilization for each machine
    machine_stats = []
    for machine in machines:
        completed = machine.production_orders.filter_by(status='completed').count()
        in_progress = machine.production_orders.filter_by(status='in_progress').count()

        machine_stats.append({
            'machine': machine,
            'completed_jobs': completed,
            'active_jobs': in_progress,
            'status': machine.status
        })

    return render_template('reports/machine_utilization.html', machine_stats=machine_stats)


# Order Reports
@reports_bp.route('/orders/summary')
@login_required
def order_summary():
    """Order summary report"""
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    # Default to current month
    if not start_date:
        start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')

    query = SalesOrder.query

    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(
            SalesOrder.created_at >= start,
            SalesOrder.created_at < end
        )
    except ValueError:
        pass

    orders = query.all()

    # Stats by status
    status_counts = {}
    for order in orders:
        status = order.status
        if status not in status_counts:
            status_counts[status] = {'count': 0, 'value': 0}
        status_counts[status]['count'] += 1
        status_counts[status]['value'] += order.total

    # Top customers
    customer_totals = {}
    for order in orders:
        cid = order.customer_id
        if cid not in customer_totals:
            customer_totals[cid] = {
                'customer': order.customer,
                'order_count': 0,
                'total_value': 0
            }
        customer_totals[cid]['order_count'] += 1
        customer_totals[cid]['total_value'] += order.total

    top_customers = sorted(customer_totals.values(), key=lambda x: x['total_value'], reverse=True)[:10]

    return render_template('reports/order_summary.html',
                           orders=orders,
                           status_counts=status_counts,
                           top_customers=top_customers,
                           start_date=start_date,
                           end_date=end_date)


# Mould Reports
@reports_bp.route('/moulds/maintenance')
@login_required
def mould_maintenance():
    """Mould maintenance report"""
    moulds = Mould.query.filter_by(is_active=True).all()

    due = [m for m in moulds if m.is_maintenance_due]
    upcoming = [m for m in moulds if not m.is_maintenance_due and
                m.next_maintenance_date and
                m.next_maintenance_date <= (datetime.now() + timedelta(days=30)).date()]

    return render_template('reports/mould_maintenance.html',
                           due_moulds=due,
                           upcoming_moulds=upcoming)


# Quality Reports
@reports_bp.route('/quality/ncr')
@login_required
def quality_ncr():
    """Non-conformance report"""
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    status = request.args.get('status', '')

    query = NonConformance.query

    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(NonConformance.created_at >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(NonConformance.created_at < end)
        except ValueError:
            pass

    if status:
        query = query.filter_by(status=status)

    ncrs = query.order_by(NonConformance.created_at.desc()).all()

    return render_template('reports/quality_ncr.html',
                           ncrs=ncrs,
                           start_date=start_date,
                           end_date=end_date,
                           status=status)


# Dashboard Data API
@reports_bp.route('/api/dashboard-data')
@login_required
def dashboard_data():
    """Get dashboard data for charts"""
    # Production by day (last 7 days)
    production_by_day = []
    for i in range(6, -1, -1):
        day = datetime.now().date() - timedelta(days=i)
        next_day = day + timedelta(days=1)

        count = ProductionOrder.query.filter(
            ProductionOrder.status == 'completed',
            ProductionOrder.end_date >= datetime.combine(day, datetime.min.time()),
            ProductionOrder.end_date < datetime.combine(next_day, datetime.min.time())
        ).count()

        production_by_day.append({
            'date': day.strftime('%a'),
            'count': count
        })

    # Stock by category
    stock_by_category = []
    categories = Category.query.all()
    for cat in categories:
        items = Item.query.filter_by(category_id=cat.id, is_active=True).all()
        total = sum(item.total_stock for item in items)
        if total > 0:
            stock_by_category.append({
                'category': cat.name,
                'quantity': total
            })

    # Order status distribution
    order_status = db.session.query(
        SalesOrder.status,
        func.count(SalesOrder.id)
    ).group_by(SalesOrder.status).all()

    return {
        'production_by_day': production_by_day,
        'stock_by_category': stock_by_category,
        'order_status': [{'status': s, 'count': c} for s, c in order_status]
    }
