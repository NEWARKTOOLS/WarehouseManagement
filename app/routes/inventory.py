import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.inventory import Item, Category, StockLevel, StockMovement
from app.models.location import Location
from app.models.orders import Customer
from app.models.production import Mould
from app.models.materials import Material, Masterbatch
from app.utils.barcode import generate_barcode

inventory_bp = Blueprint('inventory', __name__)


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@inventory_bp.route('/')
@login_required
def item_list():
    """List all inventory items"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    search = request.args.get('search', '').strip()
    customer_id = request.args.get('customer', type=int)
    item_type = request.args.get('type', '')
    low_stock = request.args.get('low_stock', '')

    query = Item.query.filter_by(is_active=True)

    if search:
        query = query.filter(db.or_(
            Item.sku.ilike(f'%{search}%'),
            Item.name.ilike(f'%{search}%'),
            Item.barcode.ilike(f'%{search}%')
        ))

    if customer_id:
        query = query.filter_by(customer_id=customer_id)

    if item_type:
        query = query.filter_by(item_type=item_type)

    query = query.order_by(Item.sku)
    items = query.paginate(page=page, per_page=per_page, error_out=False)

    # Filter low stock in Python (since it's a computed property)
    if low_stock == 'true':
        items_list = [item for item in Item.query.filter_by(is_active=True).all() if item.is_low_stock]
    else:
        items_list = None

    categories = Category.query.order_by(Category.name).all()
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()

    return render_template('inventory/list.html',
                           items=items if not items_list else None,
                           items_list=items_list,
                           categories=categories,
                           customers=customers,
                           search=search,
                           customer_id=customer_id,
                           item_type=item_type,
                           low_stock=low_stock)


def get_form_context():
    """Get common context for item form"""
    return {
        'categories': Category.query.order_by(Category.name).all(),
        'locations': Location.query.filter_by(is_active=True).order_by(Location.code).all(),
        'customers': Customer.query.filter_by(is_active=True).order_by(Customer.name).all(),
        'moulds': Mould.query.filter_by(is_active=True).order_by(Mould.mould_number).all(),
        'raw_materials': Item.query.filter_by(is_active=True, item_type='raw_material').order_by(Item.sku).all(),
        'masterbatches': Item.query.filter_by(is_active=True, item_type='masterbatch').order_by(Item.sku).all(),
        # New materials system
        'materials': Material.query.filter_by(is_active=True).order_by(Material.code).all(),
        'masterbatch_materials': Masterbatch.query.filter_by(is_active=True).order_by(Masterbatch.code).all(),
    }


@inventory_bp.route('/new', methods=['GET', 'POST'])
@login_required
def item_create():
    """Create new inventory item"""
    mode = request.args.get('mode', request.form.get('mode', 'simple'))
    if request.method == 'POST':
        sku = request.form.get('sku', '').strip().upper()
        name = request.form.get('name', '').strip()

        # Validation
        if not sku or not name:
            flash('SKU and name are required', 'error')
            return render_template('inventory/form.html', item=None, mode=mode, **get_form_context())

        if Item.query.filter_by(sku=sku).first():
            flash('SKU already exists', 'error')
            return render_template('inventory/form.html', item=None, mode=mode, **get_form_context())

        item = Item(
            sku=sku,
            name=name,
            description=request.form.get('description', '').strip(),
            customer_id=request.form.get('customer_id', type=int) or None,
            category_id=request.form.get('category_id', type=int) or None,
            item_type=request.form.get('item_type', ''),
            unit_of_measure=request.form.get('unit_of_measure', 'parts'),
            weight_kg=request.form.get('weight_kg', type=float),
            length_mm=request.form.get('length_mm', type=float),
            width_mm=request.form.get('width_mm', type=float),
            height_mm=request.form.get('height_mm', type=float),
            color=request.form.get('color', '').strip(),
            default_location_id=request.form.get('default_location_id', type=int) or None,
            min_stock_level=request.form.get('min_stock_level', 0, type=float),
            max_stock_level=request.form.get('max_stock_level', type=float),
            reorder_point=request.form.get('reorder_point', type=float),
            reorder_quantity=request.form.get('reorder_quantity', type=float),
            material_grade=request.form.get('material_grade', '').strip(),
            supplier=request.form.get('supplier', '').strip(),
            cycle_time_seconds=request.form.get('cycle_time_seconds', type=float),
            parts_per_cycle=request.form.get('parts_per_cycle', 1, type=int),
            unit_cost=request.form.get('unit_cost', 0, type=float),
            selling_price=request.form.get('selling_price', 0, type=float),
            # New production/costing fields
            default_mould_id=request.form.get('default_mould_id', type=int) or None,
            part_weight_grams=request.form.get('part_weight_grams', type=float),
            runner_weight_grams=request.form.get('runner_weight_grams', type=float),
            cavities=request.form.get('cavities', 1, type=int),
            setup_time_hours=request.form.get('setup_time_hours', type=float),
            material_type=request.form.get('material_type', ''),
            material_id=request.form.get('material_id', type=int) or None,
            masterbatch_id=request.form.get('masterbatch_id', type=int) or None,
            masterbatch_ratio=request.form.get('masterbatch_ratio', ''),
            regrind_percent=request.form.get('regrind_percent', 0, type=float),
            material_cost_per_kg=request.form.get('material_cost_per_kg', type=float),
            target_machine_rate=request.form.get('target_machine_rate', type=float),
            target_margin_percent=request.form.get('target_margin_percent', 30, type=float),
        )

        # Generate barcode
        item.barcode = sku
        barcode_path = generate_barcode(sku, current_app.config['BARCODE_FOLDER'])
        if barcode_path:
            item.barcode_image = os.path.basename(barcode_path)

        # Handle image upload
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{sku}_{file.filename}")
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                item.image_filename = filename

        db.session.add(item)
        db.session.commit()

        flash(f'Item {sku} created successfully', 'success')
        return redirect(url_for('inventory.item_detail', item_id=item.id))

    return render_template('inventory/form.html', item=None, mode=mode, **get_form_context())


@inventory_bp.route('/<int:item_id>')
@login_required
def item_detail(item_id):
    """View item details"""
    item = Item.query.get_or_404(item_id)
    stock_levels = item.stock_levels.filter(StockLevel.quantity > 0).all()
    recent_movements = item.stock_movements.order_by(StockMovement.created_at.desc()).limit(20).all()

    return render_template('inventory/detail.html',
                           item=item,
                           stock_levels=stock_levels,
                           recent_movements=recent_movements)


@inventory_bp.route('/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def item_edit(item_id):
    """Edit inventory item"""
    item = Item.query.get_or_404(item_id)

    if request.method == 'POST':
        item.name = request.form.get('name', '').strip()
        item.description = request.form.get('description', '').strip()
        item.customer_id = request.form.get('customer_id', type=int) or None
        item.category_id = request.form.get('category_id', type=int) or None
        item.item_type = request.form.get('item_type', '')
        item.unit_of_measure = request.form.get('unit_of_measure', 'parts')
        item.weight_kg = request.form.get('weight_kg', type=float)
        item.length_mm = request.form.get('length_mm', type=float)
        item.width_mm = request.form.get('width_mm', type=float)
        item.height_mm = request.form.get('height_mm', type=float)
        item.color = request.form.get('color', '').strip()
        item.default_location_id = request.form.get('default_location_id', type=int) or None
        item.min_stock_level = request.form.get('min_stock_level', 0, type=float)
        item.max_stock_level = request.form.get('max_stock_level', type=float)
        item.reorder_point = request.form.get('reorder_point', type=float)
        item.reorder_quantity = request.form.get('reorder_quantity', type=float)
        item.material_grade = request.form.get('material_grade', '').strip()
        item.supplier = request.form.get('supplier', '').strip()
        item.cycle_time_seconds = request.form.get('cycle_time_seconds', type=float)
        item.parts_per_cycle = request.form.get('parts_per_cycle', 1, type=int)
        item.unit_cost = request.form.get('unit_cost', 0, type=float)
        item.selling_price = request.form.get('selling_price', 0, type=float)

        # Production/costing fields
        item.default_mould_id = request.form.get('default_mould_id', type=int) or None
        item.part_weight_grams = request.form.get('part_weight_grams', type=float)
        item.runner_weight_grams = request.form.get('runner_weight_grams', type=float)
        item.cavities = request.form.get('cavities', 1, type=int)
        item.setup_time_hours = request.form.get('setup_time_hours', type=float)
        item.material_type = request.form.get('material_type', '')
        item.material_id = request.form.get('material_id', type=int) or None
        item.masterbatch_id = request.form.get('masterbatch_id', type=int) or None
        item.masterbatch_ratio = request.form.get('masterbatch_ratio', '')
        item.regrind_percent = request.form.get('regrind_percent', 0, type=float)
        item.material_cost_per_kg = request.form.get('material_cost_per_kg', type=float)
        item.target_machine_rate = request.form.get('target_machine_rate', type=float)
        item.target_margin_percent = request.form.get('target_margin_percent', 30, type=float)
        # Handle image upload
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{item.sku}_{file.filename}")
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                item.image_filename = filename

        db.session.commit()
        flash(f'Item {item.sku} updated successfully', 'success')
        return redirect(url_for('inventory.item_detail', item_id=item.id))

    return render_template('inventory/form.html', item=item, mode='advanced', **get_form_context())


@inventory_bp.route('/<int:item_id>/delete', methods=['POST'])
@login_required
def item_delete(item_id):
    """Delete (deactivate) item"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('inventory.item_list'))

    item = Item.query.get_or_404(item_id)
    sku = item.sku
    had_stock = item.total_stock > 0

    # Zero out any stock levels
    if had_stock:
        for sl in item.stock_levels.all():
            if sl.quantity > 0:
                # Record adjustment movement
                movement = StockMovement(
                    item_id=item.id,
                    movement_type='adjustment',
                    quantity=-sl.quantity,
                    from_location_id=sl.location_id,
                    reason='Item deleted',
                    notes='Stock removed due to item deletion',
                    user_id=current_user.id
                )
                db.session.add(movement)
                sl.quantity = 0

    item.is_active = False
    # Free up the SKU and barcode so they can be reused
    item.sku = f"DELETED_{item.id}_{sku}"
    if item.barcode:
        item.barcode = f"DELETED_{item.id}_{item.barcode}"
    db.session.commit()

    if had_stock:
        flash(f'Item {sku} has been deleted and stock zeroed', 'success')
    else:
        flash(f'Item {sku} has been deleted', 'success')
    return redirect(url_for('inventory.item_list'))


# Stock operations
@inventory_bp.route('/receive', methods=['GET', 'POST'])
@login_required
def receive_stock():
    """Receive stock into warehouse"""
    if request.method == 'POST':
        item_id = request.form.get('item_id', type=int)
        location_id = request.form.get('location_id', type=int)
        quantity = request.form.get('quantity', 0, type=float)
        batch_number = request.form.get('batch_number', '').strip()
        reference = request.form.get('reference', '').strip()
        notes = request.form.get('notes', '').strip()

        if not item_id or not location_id or quantity <= 0:
            flash('Item, location, and valid quantity are required', 'error')
            return redirect(url_for('inventory.receive_stock'))

        item = Item.query.get_or_404(item_id)
        location = Location.query.get_or_404(location_id)

        # Update or create stock level
        stock_level = StockLevel.query.filter_by(
            item_id=item_id,
            location_id=location_id
        ).first()

        if stock_level:
            stock_level.quantity += quantity
            stock_level.batch_number = batch_number or stock_level.batch_number
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
            reference=reference,
            notes=notes,
            user_id=current_user.id
        )
        db.session.add(movement)
        db.session.commit()

        flash(f'Received {quantity} {item.unit_of_measure} of {item.sku} at {location.code}', 'success')
        return redirect(url_for('inventory.item_detail', item_id=item_id))

    items = Item.query.filter_by(is_active=True).order_by(Item.sku).all()
    locations = Location.query.filter_by(is_active=True).order_by(Location.code).all()
    return render_template('inventory/receive.html', items=items, locations=locations)


@inventory_bp.route('/move', methods=['GET', 'POST'])
@login_required
def move_stock():
    """Move stock between locations"""
    if request.method == 'POST':
        item_id = request.form.get('item_id', type=int)
        from_location_id = request.form.get('from_location_id', type=int)
        to_location_id = request.form.get('to_location_id', type=int)
        quantity = request.form.get('quantity', 0, type=float)
        reason = request.form.get('reason', '').strip()
        notes = request.form.get('notes', '').strip()

        if not item_id or not from_location_id or not to_location_id or quantity <= 0:
            flash('All fields are required', 'error')
            return redirect(url_for('inventory.move_stock'))

        if from_location_id == to_location_id:
            flash('From and To locations must be different', 'error')
            return redirect(url_for('inventory.move_stock'))

        item = Item.query.get_or_404(item_id)

        # Check source stock
        from_stock = StockLevel.query.filter_by(
            item_id=item_id,
            location_id=from_location_id
        ).first()

        if not from_stock or from_stock.quantity < quantity:
            flash('Insufficient stock at source location', 'error')
            return redirect(url_for('inventory.move_stock'))

        # Update source
        from_stock.quantity -= quantity

        # Update or create destination
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
            reason=reason,
            notes=notes,
            user_id=current_user.id
        )
        db.session.add(movement)
        db.session.commit()

        from_loc = Location.query.get(from_location_id)
        to_loc = Location.query.get(to_location_id)
        flash(f'Moved {quantity} {item.unit_of_measure} of {item.sku} from {from_loc.code} to {to_loc.code}', 'success')
        return redirect(url_for('inventory.item_detail', item_id=item_id))

    items = Item.query.filter_by(is_active=True).order_by(Item.sku).all()
    locations = Location.query.filter_by(is_active=True).order_by(Location.code).all()
    return render_template('inventory/move.html', items=items, locations=locations)


@inventory_bp.route('/adjust', methods=['GET', 'POST'])
@login_required
def adjust_stock():
    """Adjust stock (cycle count, damage, etc.)"""
    if request.method == 'POST':
        item_id = request.form.get('item_id', type=int)
        location_id = request.form.get('location_id', type=int)
        new_quantity = request.form.get('new_quantity', 0, type=float)
        reason = request.form.get('reason', '').strip()
        notes = request.form.get('notes', '').strip()

        if not item_id or not location_id:
            flash('Item and location are required', 'error')
            return redirect(url_for('inventory.adjust_stock'))

        if not reason:
            flash('Reason for adjustment is required', 'error')
            return redirect(url_for('inventory.adjust_stock'))

        item = Item.query.get_or_404(item_id)

        # Get or create stock level
        stock_level = StockLevel.query.filter_by(
            item_id=item_id,
            location_id=location_id
        ).first()

        old_quantity = stock_level.quantity if stock_level else 0
        adjustment = new_quantity - old_quantity

        if stock_level:
            stock_level.quantity = new_quantity
            stock_level.last_count_date = datetime.utcnow()
        else:
            stock_level = StockLevel(
                item_id=item_id,
                location_id=location_id,
                quantity=new_quantity,
                last_count_date=datetime.utcnow()
            )
            db.session.add(stock_level)

        # Record movement
        movement = StockMovement(
            item_id=item_id,
            movement_type='adjustment',
            quantity=adjustment,
            to_location_id=location_id if adjustment > 0 else None,
            from_location_id=location_id if adjustment < 0 else None,
            reason=reason,
            notes=f'Adjusted from {old_quantity} to {new_quantity}. {notes}',
            user_id=current_user.id
        )
        db.session.add(movement)
        db.session.commit()

        location = Location.query.get(location_id)
        flash(f'Stock adjusted for {item.sku} at {location.code}: {old_quantity} -> {new_quantity}', 'success')
        return redirect(url_for('inventory.item_detail', item_id=item_id))

    items = Item.query.filter_by(is_active=True).order_by(Item.sku).all()
    locations = Location.query.filter_by(is_active=True).order_by(Location.code).all()
    return render_template('inventory/adjust.html', items=items, locations=locations)


# Categories
@inventory_bp.route('/categories')
@login_required
def category_list():
    """List categories"""
    categories = Category.query.order_by(Category.name).all()
    return render_template('inventory/categories.html', categories=categories)


@inventory_bp.route('/categories/new', methods=['GET', 'POST'])
@login_required
def category_create():
    """Create new category"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        category_type = request.form.get('category_type', '')

        if not name:
            flash('Category name is required', 'error')
            return render_template('inventory/category_form.html', category=None)

        if Category.query.filter_by(name=name).first():
            flash('Category name already exists', 'error')
            return render_template('inventory/category_form.html', category=None)

        category = Category(
            name=name,
            description=description,
            category_type=category_type
        )
        db.session.add(category)
        db.session.commit()

        flash(f'Category {name} created successfully', 'success')
        return redirect(url_for('inventory.category_list'))

    return render_template('inventory/category_form.html', category=None)


@inventory_bp.route('/categories/<int:category_id>/delete', methods=['POST'])
@login_required
def category_delete(category_id):
    """Delete a category"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('inventory.category_list'))

    category = Category.query.get_or_404(category_id)
    name = category.name

    # Check if category has items
    item_count = category.items.count()
    if item_count > 0:
        # Remove category from items (set to NULL)
        for item in category.items.all():
            item.category_id = None
        flash(f'Category "{name}" deleted. {item_count} item(s) are now uncategorized.', 'warning')
    else:
        flash(f'Category "{name}" deleted successfully', 'success')

    db.session.delete(category)
    db.session.commit()

    return redirect(url_for('inventory.category_list'))


# API endpoints
@inventory_bp.route('/api/search')
@login_required
def api_search():
    """Search items via API"""
    query = request.args.get('q', '').strip()

    items = Item.query.filter(
        Item.is_active == True,
        db.or_(
            Item.sku.ilike(f'%{query}%'),
            Item.name.ilike(f'%{query}%'),
            Item.barcode.ilike(f'%{query}%')
        )
    ).limit(20).all()

    return jsonify([{
        'id': item.id,
        'sku': item.sku,
        'name': item.name,
        'barcode': item.barcode,
        'total_stock': item.total_stock,
        'unit': item.unit_of_measure
    } for item in items])


@inventory_bp.route('/api/barcode/<barcode>')
@login_required
def api_barcode_lookup(barcode):
    """Lookup item by barcode"""
    item = Item.query.filter(
        db.or_(
            Item.barcode == barcode,
            Item.sku == barcode
        ),
        Item.is_active == True
    ).first()

    if not item:
        return jsonify({'error': 'Item not found'}), 404

    stock_levels = [{
        'location_id': sl.location.id,
        'location_code': sl.location.code,
        'location_name': sl.location.name,
        'quantity': sl.quantity,
        'available': sl.available_quantity
    } for sl in item.stock_levels.filter(StockLevel.quantity > 0).all()]

    return jsonify({
        'id': item.id,
        'sku': item.sku,
        'name': item.name,
        'description': item.description,
        'barcode': item.barcode,
        'total_stock': item.total_stock,
        'unit': item.unit_of_measure,
        'image': item.image_filename,
        'stock_levels': stock_levels
    })


@inventory_bp.route('/api/<int:item_id>/stock')
@login_required
def api_item_stock(item_id):
    """Get item stock levels"""
    item = Item.query.get_or_404(item_id)

    stock_levels = [{
        'location_id': sl.location.id,
        'location_code': sl.location.code,
        'location_name': sl.location.name,
        'quantity': sl.quantity,
        'available': sl.available_quantity,
        'batch': sl.batch_number
    } for sl in item.stock_levels.all()]

    return jsonify({
        'item_id': item.id,
        'sku': item.sku,
        'total_stock': item.total_stock,
        'available_stock': item.available_stock,
        'stock_levels': stock_levels
    })


# Quick Stock Update Page
@inventory_bp.route('/stock-update')
@login_required
def stock_update():
    """Quick stock update page - easy add/remove/move stock"""
    items = Item.query.filter_by(is_active=True).order_by(Item.sku).all()
    locations = Location.query.filter_by(is_active=True).order_by(Location.code).all()

    # Group locations by zone for better UX
    zones = {}
    for loc in locations:
        zone = loc.zone or 'Other'
        if zone not in zones:
            zones[zone] = []
        zones[zone].append(loc)

    # Get recent movements for display
    recent_movements = StockMovement.query.order_by(
        StockMovement.created_at.desc()
    ).limit(10).all()

    return render_template('inventory/stock_update.html',
                           items=items,
                           locations=locations,
                           zones=zones,
                           recent_movements=recent_movements)


@inventory_bp.route('/quick-add-stock', methods=['POST'])
@login_required
def quick_add_stock():
    """Quick add stock from stock update page"""
    item_id = request.form.get('item_id', type=int)
    location_id = request.form.get('location_id', type=int)
    quantity = request.form.get('quantity', 0, type=float)
    notes = request.form.get('notes', '').strip()

    if not item_id or not location_id or quantity <= 0:
        flash('Item, location, and valid quantity are required', 'error')
        return redirect(url_for('inventory.stock_update'))

    item = Item.query.get_or_404(item_id)
    location = Location.query.get_or_404(location_id)

    # Update or create stock level
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
            quantity=quantity
        )
        db.session.add(stock_level)

    # Record movement
    movement = StockMovement(
        item_id=item_id,
        movement_type='receipt',
        quantity=quantity,
        to_location_id=location_id,
        notes=notes or 'Quick stock add',
        user_id=current_user.id
    )
    db.session.add(movement)
    db.session.commit()

    flash(f'Added {int(quantity)} {item.unit_of_measure} of {item.sku} to {location.code}', 'success')
    return redirect(url_for('inventory.stock_update'))


@inventory_bp.route('/quick-remove-stock', methods=['POST'])
@login_required
def quick_remove_stock():
    """Quick remove stock from stock update page"""
    item_id = request.form.get('item_id', type=int)
    location_id = request.form.get('location_id', type=int)
    quantity = request.form.get('quantity', 0, type=float)
    reason = request.form.get('reason', '').strip()
    notes = request.form.get('notes', '').strip()

    if not item_id or not location_id or quantity <= 0:
        flash('Item, location, and valid quantity are required', 'error')
        return redirect(url_for('inventory.stock_update'))

    item = Item.query.get_or_404(item_id)
    location = Location.query.get_or_404(location_id)

    # Check stock level
    stock_level = StockLevel.query.filter_by(
        item_id=item_id,
        location_id=location_id
    ).first()

    if not stock_level or stock_level.quantity < quantity:
        available = stock_level.quantity if stock_level else 0
        flash(f'Insufficient stock. Only {int(available)} available at {location.code}', 'error')
        return redirect(url_for('inventory.stock_update'))

    stock_level.quantity -= quantity

    # Record movement
    movement = StockMovement(
        item_id=item_id,
        movement_type='adjustment',
        quantity=-quantity,
        from_location_id=location_id,
        reason=reason or 'Stock removal',
        notes=notes,
        user_id=current_user.id
    )
    db.session.add(movement)
    db.session.commit()

    flash(f'Removed {int(quantity)} {item.unit_of_measure} of {item.sku} from {location.code}', 'success')
    return redirect(url_for('inventory.stock_update'))


@inventory_bp.route('/quick-move-stock', methods=['POST'])
@login_required
def quick_move_stock():
    """Quick move stock between locations"""
    item_id = request.form.get('item_id', type=int)
    from_location_id = request.form.get('from_location_id', type=int)
    to_location_id = request.form.get('to_location_id', type=int)
    quantity = request.form.get('quantity', 0, type=float)
    notes = request.form.get('notes', '').strip()

    if not item_id or not from_location_id or not to_location_id or quantity <= 0:
        flash('All fields are required', 'error')
        return redirect(url_for('inventory.stock_update'))

    if from_location_id == to_location_id:
        flash('From and To locations must be different', 'error')
        return redirect(url_for('inventory.stock_update'))

    item = Item.query.get_or_404(item_id)
    from_loc = Location.query.get_or_404(from_location_id)
    to_loc = Location.query.get_or_404(to_location_id)

    # Check source stock
    from_stock = StockLevel.query.filter_by(
        item_id=item_id,
        location_id=from_location_id
    ).first()

    if not from_stock or from_stock.quantity < quantity:
        available = from_stock.quantity if from_stock else 0
        flash(f'Insufficient stock. Only {int(available)} available at {from_loc.code}', 'error')
        return redirect(url_for('inventory.stock_update'))

    # Update source
    from_stock.quantity -= quantity

    # Update or create destination
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
        notes=notes or 'Quick stock move',
        user_id=current_user.id
    )
    db.session.add(movement)
    db.session.commit()

    flash(f'Moved {int(quantity)} {item.unit_of_measure} of {item.sku} from {from_loc.code} to {to_loc.code}', 'success')
    return redirect(url_for('inventory.stock_update'))
