from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from app import db
from app.models.inventory import Item, StockLevel, StockMovement
from app.models.production import ProductionOrder, Machine, Mould, ScheduledJob, AwaitingSorting
from app.models.orders import SalesOrder, Customer
from app.models.settings import CompanySettings

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Landing page - redirect to dashboard if logged in"""
    if current_user.is_authenticated:
        return render_template('dashboard.html', **get_dashboard_data())
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard"""
    return render_template('dashboard.html', **get_dashboard_data())


def get_dashboard_data():
    """Get dashboard statistics for injection moulding operations"""
    today = datetime.now().date()

    # Inventory stats
    total_items = Item.query.filter_by(is_active=True).count()
    low_stock_items = Item.query.filter(
        Item.is_active == True,
        Item.reorder_point != None
    ).all()
    low_stock_count = sum(1 for item in low_stock_items if item.is_low_stock)

    # Calculate total stock value
    stock_value = db.session.query(
        func.sum(StockLevel.quantity * Item.unit_cost)
    ).join(Item).scalar() or 0

    # Production stats
    active_production = ProductionOrder.query.filter_by(status='in_progress').count()
    planned_production = ProductionOrder.query.filter_by(status='planned').count()

    # Order stats
    pending_orders = SalesOrder.query.filter(
        SalesOrder.status.in_(['new', 'in_production'])
    ).count()
    ready_to_ship = SalesOrder.query.filter_by(status='ready_to_ship').count()

    # Machine status
    machines = Machine.query.filter_by(is_active=True).order_by(Machine.display_order, Machine.name).all()
    machines_running = sum(1 for m in machines if m.status == 'running')
    machines_idle = sum(1 for m in machines if m.status == 'idle')

    # Moulds needing maintenance
    moulds_maintenance_due = Mould.query.filter(
        Mould.is_active == True,
        Mould.next_maintenance_date != None
    ).all()
    maintenance_overdue = sum(1 for m in moulds_maintenance_due if m.is_maintenance_due)

    # Today's scheduled jobs
    todays_jobs = ScheduledJob.query.filter(
        ScheduledJob.scheduled_date == today,
        ScheduledJob.status.in_(['scheduled', 'in_progress'])
    ).order_by(ScheduledJob.machine_id, ScheduledJob.sequence_order).all()

    # Urgent orders (due within 3 days)
    urgent_deadline = today + timedelta(days=3)
    urgent_orders = SalesOrder.query.filter(
        SalesOrder.status.in_(['new', 'in_production']),
        SalesOrder.required_date != None,
        SalesOrder.required_date <= urgent_deadline
    ).order_by(SalesOrder.required_date).all()

    # Items awaiting sorting
    awaiting_sorting_count = AwaitingSorting.query.filter_by(status='pending').count()

    # Recent activity
    recent_movements = StockMovement.query.order_by(
        StockMovement.created_at.desc()
    ).limit(10).all()

    recent_orders = SalesOrder.query.order_by(
        SalesOrder.created_at.desc()
    ).limit(5).all()

    # Get company settings
    company_settings = CompanySettings.get_settings()

    return {
        'total_items': total_items,
        'low_stock_count': low_stock_count,
        'stock_value': stock_value,
        'active_production': active_production,
        'planned_production': planned_production,
        'pending_orders': pending_orders,
        'ready_to_ship': ready_to_ship,
        'machines': machines,
        'machines_total': len(machines),
        'machines_running': machines_running,
        'machines_idle': machines_idle,
        'maintenance_overdue': maintenance_overdue,
        'todays_jobs': todays_jobs,
        'urgent_orders': urgent_orders,
        'awaiting_sorting_count': awaiting_sorting_count,
        'recent_movements': recent_movements,
        'recent_orders': recent_orders,
        'company_settings': company_settings,
        'today': today
    }


@main_bp.route('/scan')
@login_required
def scan():
    """Barcode scanning page"""
    return render_template('scan.html')


@main_bp.route('/quick-actions')
@login_required
def quick_actions():
    """Quick actions mobile page"""
    return render_template('quick_actions.html')


@main_bp.route('/manifest.json')
def manifest():
    """PWA manifest file"""
    return jsonify({
        "name": "Warehouse Management System",
        "short_name": "WMS",
        "description": "Warehouse and inventory management for injection moulding",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#2563eb",
        "icons": [
            {
                "src": "/static/img/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/img/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    })


@main_bp.route('/sw.js')
def service_worker():
    """Service worker for PWA offline capability"""
    return main_bp.send_static_file('js/sw.js')
