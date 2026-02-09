"""
Materials Management Routes
Manage raw materials, suppliers, and pricing
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from sqlalchemy import desc
from app import db
from app.models.materials import MaterialSupplier, Material, MaterialPriceHistory, Masterbatch

bp = Blueprint('materials', __name__, url_prefix='/materials')


# ============== MATERIALS LIST & DASHBOARD ==============

@bp.route('/')
@login_required
def material_list():
    """List all materials with filtering"""
    material_type = request.args.get('type', '')
    supplier_id = request.args.get('supplier', type=int)
    search = request.args.get('search', '')

    query = Material.query.filter_by(is_active=True)

    if material_type:
        query = query.filter_by(material_type=material_type)
    if supplier_id:
        query = query.filter_by(supplier_id=supplier_id)
    if search:
        query = query.filter(db.or_(
            Material.name.ilike(f'%{search}%'),
            Material.code.ilike(f'%{search}%'),
            Material.grade.ilike(f'%{search}%')
        ))

    materials = query.order_by(Material.material_type, Material.code).all()
    suppliers = MaterialSupplier.query.filter_by(is_active=True).order_by(MaterialSupplier.name).all()

    # Get unique material types for filter
    material_types = db.session.query(Material.material_type).distinct().order_by(Material.material_type).all()
    material_types = [mt[0] for mt in material_types if mt[0]]

    # Stats
    stats = {
        'total_materials': Material.query.filter_by(is_active=True).count(),
        'total_suppliers': MaterialSupplier.query.filter_by(is_active=True).count(),
        'low_stock': Material.query.filter(
            Material.is_active == True,
            Material.min_stock_kg.isnot(None),
            Material.current_stock_kg < Material.min_stock_kg
        ).count()
    }

    return render_template('materials/list.html',
                           materials=materials,
                           suppliers=suppliers,
                           material_types=material_types,
                           selected_type=material_type,
                           selected_supplier=supplier_id,
                           search=search,
                           stats=stats)


# ============== MATERIAL CRUD ==============

@bp.route('/new', methods=['GET', 'POST'])
@login_required
def material_new():
    """Create new material"""
    if request.method == 'POST':
        # Check for duplicate code
        code = request.form.get('code', '').strip().upper()
        if Material.query.filter_by(code=code).first():
            flash(f'Material code {code} already exists', 'error')
            suppliers = MaterialSupplier.query.filter_by(is_active=True).order_by(MaterialSupplier.name).all()
            return render_template('materials/form.html', material=None, suppliers=suppliers)

        material = Material(
            code=code,
            name=request.form.get('name', '').strip(),
            material_type=request.form.get('material_type', ''),
            grade=request.form.get('grade', '').strip(),
            manufacturer=request.form.get('manufacturer', '').strip(),
            supplier_id=request.form.get('supplier_id', type=int) or None,
            supplier_code=request.form.get('supplier_code', '').strip(),
            mfi=request.form.get('mfi', type=float),
            density=request.form.get('density', type=float),
            color=request.form.get('color', '').strip() or 'Natural',
            cost_per_kg=request.form.get('cost_per_kg', type=float) or 0,
            last_price_update=date.today(),
            min_stock_kg=request.form.get('min_stock_kg', type=float),
            reorder_qty_kg=request.form.get('reorder_qty_kg', type=float),
            barrel_temp_min=request.form.get('barrel_temp_min', type=int),
            barrel_temp_max=request.form.get('barrel_temp_max', type=int),
            mould_temp_min=request.form.get('mould_temp_min', type=int),
            mould_temp_max=request.form.get('mould_temp_max', type=int),
            drying_required=request.form.get('drying_required') == 'on',
            drying_temp=request.form.get('drying_temp', type=int),
            drying_time_hours=request.form.get('drying_time_hours', type=float),
            notes=request.form.get('notes', '').strip()
        )

        db.session.add(material)
        db.session.flush()

        # Record initial price in history
        price_history = MaterialPriceHistory(
            material_id=material.id,
            cost_per_kg=material.cost_per_kg,
            effective_date=date.today(),
            reason='Initial price',
            created_by=current_user.username
        )
        db.session.add(price_history)
        db.session.commit()

        flash(f'Material {code} created successfully', 'success')
        return redirect(url_for('materials.material_detail', material_id=material.id))

    suppliers = MaterialSupplier.query.filter_by(is_active=True).order_by(MaterialSupplier.name).all()
    return render_template('materials/form.html', material=None, suppliers=suppliers)


@bp.route('/<int:material_id>')
@login_required
def material_detail(material_id):
    """View material details"""
    material = Material.query.get_or_404(material_id)
    price_history = material.price_history.limit(20).all()

    # Find items using this material (via the material's linked inventory item)
    from app.models.inventory import Item
    items_using = []
    if material.item_id:
        items_using = Item.query.filter_by(material_id=material.item_id, is_active=True).all()

    return render_template('materials/detail.html',
                           material=material,
                           price_history=price_history,
                           items_using=items_using)


@bp.route('/<int:material_id>/edit', methods=['GET', 'POST'])
@login_required
def material_edit(material_id):
    """Edit material"""
    material = Material.query.get_or_404(material_id)

    if request.method == 'POST':
        old_price = material.cost_per_kg
        new_price = request.form.get('cost_per_kg', type=float) or 0

        material.name = request.form.get('name', '').strip()
        material.material_type = request.form.get('material_type', '')
        material.grade = request.form.get('grade', '').strip()
        material.manufacturer = request.form.get('manufacturer', '').strip()
        material.supplier_id = request.form.get('supplier_id', type=int) or None
        material.supplier_code = request.form.get('supplier_code', '').strip()
        material.mfi = request.form.get('mfi', type=float)
        material.density = request.form.get('density', type=float)
        material.color = request.form.get('color', '').strip() or 'Natural'
        material.cost_per_kg = new_price
        material.min_stock_kg = request.form.get('min_stock_kg', type=float)
        material.reorder_qty_kg = request.form.get('reorder_qty_kg', type=float)
        material.barrel_temp_min = request.form.get('barrel_temp_min', type=int)
        material.barrel_temp_max = request.form.get('barrel_temp_max', type=int)
        material.mould_temp_min = request.form.get('mould_temp_min', type=int)
        material.mould_temp_max = request.form.get('mould_temp_max', type=int)
        material.drying_required = request.form.get('drying_required') == 'on'
        material.drying_temp = request.form.get('drying_temp', type=int)
        material.drying_time_hours = request.form.get('drying_time_hours', type=float)
        material.notes = request.form.get('notes', '').strip()

        # Record price change if different
        if new_price != old_price:
            material.last_price_update = date.today()
            price_history = MaterialPriceHistory(
                material_id=material.id,
                cost_per_kg=new_price,
                effective_date=date.today(),
                reason=request.form.get('price_change_reason', 'Price update'),
                created_by=current_user.username
            )
            db.session.add(price_history)

        db.session.commit()
        flash(f'Material {material.code} updated', 'success')
        return redirect(url_for('materials.material_detail', material_id=material.id))

    suppliers = MaterialSupplier.query.filter_by(is_active=True).order_by(MaterialSupplier.name).all()
    return render_template('materials/form.html', material=material, suppliers=suppliers)


@bp.route('/<int:material_id>/delete', methods=['POST'])
@login_required
def material_delete(material_id):
    """Delete (deactivate) material"""
    if not current_user.is_admin():
        flash('Admin access required', 'error')
        return redirect(url_for('materials.material_list'))

    material = Material.query.get_or_404(material_id)

    # Check if any active items are linked to this material (via the material's linked inventory item)
    from app.models.inventory import Item
    linked_items = 0
    if material.item_id:
        linked_items = Item.query.filter_by(material_id=material.item_id, is_active=True).count()
    if linked_items > 0:
        flash(f'Cannot delete {material.code} — {linked_items} active part(s) still linked to this material', 'error')
        return redirect(url_for('materials.material_detail', material_id=material.id))

    material.is_active = False
    db.session.commit()
    flash(f'Material {material.code} has been deactivated', 'success')
    return redirect(url_for('materials.material_list'))


@bp.route('/<int:material_id>/update-price', methods=['POST'])
@login_required
def material_update_price(material_id):
    """Quick price update"""
    material = Material.query.get_or_404(material_id)

    new_price = request.form.get('cost_per_kg', type=float)
    if new_price and new_price != material.cost_per_kg:
        material.cost_per_kg = new_price
        material.last_price_update = date.today()

        price_history = MaterialPriceHistory(
            material_id=material.id,
            cost_per_kg=new_price,
            effective_date=date.today(),
            reason=request.form.get('reason', 'Price update'),
            created_by=current_user.username
        )
        db.session.add(price_history)
        db.session.commit()

        flash(f'Price updated to £{new_price:.2f}/kg', 'success')

    return redirect(url_for('materials.material_detail', material_id=material.id))


# ============== SUPPLIERS ==============

@bp.route('/suppliers')
@login_required
def supplier_list():
    """List all suppliers"""
    suppliers = MaterialSupplier.query.filter_by(is_active=True).order_by(MaterialSupplier.name).all()
    return render_template('materials/suppliers.html', suppliers=suppliers)


@bp.route('/suppliers/new', methods=['GET', 'POST'])
@login_required
def supplier_new():
    """Create new supplier"""
    if request.method == 'POST':
        supplier = MaterialSupplier(
            name=request.form.get('name', '').strip(),
            code=request.form.get('code', '').strip().upper() or None,
            contact_name=request.form.get('contact_name', '').strip(),
            email=request.form.get('email', '').strip(),
            phone=request.form.get('phone', '').strip(),
            website=request.form.get('website', '').strip(),
            address_line1=request.form.get('address_line1', '').strip(),
            address_line2=request.form.get('address_line2', '').strip(),
            city=request.form.get('city', '').strip(),
            postcode=request.form.get('postcode', '').strip(),
            account_number=request.form.get('account_number', '').strip(),
            payment_terms=request.form.get('payment_terms', '').strip(),
            lead_time_days=request.form.get('lead_time_days', type=int),
            minimum_order_kg=request.form.get('minimum_order_kg', type=float),
            notes=request.form.get('notes', '').strip()
        )
        db.session.add(supplier)
        db.session.commit()

        flash(f'Supplier {supplier.name} created', 'success')
        return redirect(url_for('materials.supplier_list'))

    return render_template('materials/supplier_form.html', supplier=None)


@bp.route('/suppliers/<int:supplier_id>/delete', methods=['POST'])
@login_required
def supplier_delete(supplier_id):
    """Delete (deactivate) supplier"""
    if not current_user.is_admin():
        flash('Admin access required', 'error')
        return redirect(url_for('materials.supplier_list'))

    supplier = MaterialSupplier.query.get_or_404(supplier_id)

    # Check if any active materials are linked
    linked_materials = Material.query.filter_by(supplier_id=supplier.id, is_active=True).count()
    if linked_materials > 0:
        flash(f'Cannot delete {supplier.name} — {linked_materials} active material(s) still linked to this supplier', 'error')
        return redirect(url_for('materials.supplier_list'))

    supplier.is_active = False
    db.session.commit()
    flash(f'Supplier {supplier.name} has been deactivated', 'success')
    return redirect(url_for('materials.supplier_list'))


@bp.route('/suppliers/<int:supplier_id>/edit', methods=['GET', 'POST'])
@login_required
def supplier_edit(supplier_id):
    """Edit supplier"""
    supplier = MaterialSupplier.query.get_or_404(supplier_id)

    if request.method == 'POST':
        supplier.name = request.form.get('name', '').strip()
        supplier.code = request.form.get('code', '').strip().upper() or None
        supplier.contact_name = request.form.get('contact_name', '').strip()
        supplier.email = request.form.get('email', '').strip()
        supplier.phone = request.form.get('phone', '').strip()
        supplier.website = request.form.get('website', '').strip()
        supplier.address_line1 = request.form.get('address_line1', '').strip()
        supplier.address_line2 = request.form.get('address_line2', '').strip()
        supplier.city = request.form.get('city', '').strip()
        supplier.postcode = request.form.get('postcode', '').strip()
        supplier.account_number = request.form.get('account_number', '').strip()
        supplier.payment_terms = request.form.get('payment_terms', '').strip()
        supplier.lead_time_days = request.form.get('lead_time_days', type=int)
        supplier.minimum_order_kg = request.form.get('minimum_order_kg', type=float)
        supplier.notes = request.form.get('notes', '').strip()

        db.session.commit()
        flash(f'Supplier {supplier.name} updated', 'success')
        return redirect(url_for('materials.supplier_list'))

    return render_template('materials/supplier_form.html', supplier=supplier)


# ============== MASTERBATCHES ==============

@bp.route('/masterbatches')
@login_required
def masterbatch_list():
    """List all masterbatches"""
    masterbatches = Masterbatch.query.filter_by(is_active=True).order_by(Masterbatch.color, Masterbatch.code).all()
    return render_template('materials/masterbatches.html', masterbatches=masterbatches)


@bp.route('/masterbatches/new', methods=['GET', 'POST'])
@login_required
def masterbatch_new():
    """Create new masterbatch"""
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        if Masterbatch.query.filter_by(code=code).first():
            flash(f'Code {code} already exists', 'error')
            suppliers = MaterialSupplier.query.filter_by(is_active=True).order_by(MaterialSupplier.name).all()
            return render_template('materials/masterbatch_form.html', masterbatch=None, suppliers=suppliers)

        masterbatch = Masterbatch(
            code=code,
            name=request.form.get('name', '').strip(),
            color=request.form.get('color', '').strip(),
            color_code=request.form.get('color_code', '').strip(),
            supplier_id=request.form.get('supplier_id', type=int) or None,
            supplier_code=request.form.get('supplier_code', '').strip(),
            compatible_materials=request.form.get('compatible_materials', '').strip(),
            typical_ratio_percent=request.form.get('typical_ratio_percent', type=float) or 3,
            min_ratio_percent=request.form.get('min_ratio_percent', type=float),
            max_ratio_percent=request.form.get('max_ratio_percent', type=float),
            cost_per_kg=request.form.get('cost_per_kg', type=float),
            min_stock_kg=request.form.get('min_stock_kg', type=float),
            notes=request.form.get('notes', '').strip()
        )
        db.session.add(masterbatch)
        db.session.commit()

        flash(f'Masterbatch {code} created', 'success')
        return redirect(url_for('materials.masterbatch_list'))

    suppliers = MaterialSupplier.query.filter_by(is_active=True).order_by(MaterialSupplier.name).all()
    return render_template('materials/masterbatch_form.html', masterbatch=None, suppliers=suppliers)


@bp.route('/masterbatches/<int:masterbatch_id>/delete', methods=['POST'])
@login_required
def masterbatch_delete(masterbatch_id):
    """Delete (deactivate) masterbatch"""
    if not current_user.is_admin():
        flash('Admin access required', 'error')
        return redirect(url_for('materials.masterbatch_list'))

    masterbatch = Masterbatch.query.get_or_404(masterbatch_id)
    masterbatch.is_active = False
    db.session.commit()
    flash(f'Masterbatch {masterbatch.code} has been deactivated', 'success')
    return redirect(url_for('materials.masterbatch_list'))


@bp.route('/masterbatches/<int:masterbatch_id>/edit', methods=['GET', 'POST'])
@login_required
def masterbatch_edit(masterbatch_id):
    """Edit masterbatch"""
    masterbatch = Masterbatch.query.get_or_404(masterbatch_id)

    if request.method == 'POST':
        masterbatch.name = request.form.get('name', '').strip()
        masterbatch.color = request.form.get('color', '').strip()
        masterbatch.color_code = request.form.get('color_code', '').strip()
        masterbatch.supplier_id = request.form.get('supplier_id', type=int) or None
        masterbatch.supplier_code = request.form.get('supplier_code', '').strip()
        masterbatch.compatible_materials = request.form.get('compatible_materials', '').strip()
        masterbatch.typical_ratio_percent = request.form.get('typical_ratio_percent', type=float) or 3
        masterbatch.min_ratio_percent = request.form.get('min_ratio_percent', type=float)
        masterbatch.max_ratio_percent = request.form.get('max_ratio_percent', type=float)
        masterbatch.cost_per_kg = request.form.get('cost_per_kg', type=float)
        masterbatch.min_stock_kg = request.form.get('min_stock_kg', type=float)
        masterbatch.notes = request.form.get('notes', '').strip()

        db.session.commit()
        flash(f'Masterbatch {masterbatch.code} updated', 'success')
        return redirect(url_for('materials.masterbatch_list'))

    suppliers = MaterialSupplier.query.filter_by(is_active=True).order_by(MaterialSupplier.name).all()
    return render_template('materials/masterbatch_form.html', masterbatch=masterbatch, suppliers=suppliers)


# ============== API ENDPOINTS ==============

@bp.route('/api/materials')
@login_required
def api_materials():
    """Get materials as JSON for dropdowns"""
    materials = Material.query.filter_by(is_active=True).order_by(Material.material_type, Material.code).all()
    return jsonify([{
        'id': m.id,
        'code': m.code,
        'name': m.name,
        'material_type': m.material_type,
        'grade': m.grade,
        'cost_per_kg': m.cost_per_kg,
        'supplier': m.supplier.name if m.supplier else None,
        'display': f"{m.code} - {m.material_type} {m.grade or ''} (£{m.cost_per_kg:.2f}/kg)"
    } for m in materials])


@bp.route('/api/masterbatches')
@login_required
def api_masterbatches():
    """Get masterbatches as JSON for dropdowns"""
    masterbatches = Masterbatch.query.filter_by(is_active=True).order_by(Masterbatch.color, Masterbatch.code).all()
    return jsonify([{
        'id': mb.id,
        'code': mb.code,
        'name': mb.name,
        'color': mb.color,
        'cost_per_kg': mb.cost_per_kg,
        'typical_ratio': mb.typical_ratio_percent,
        'display': f"{mb.code} - {mb.name} ({mb.color})"
    } for mb in masterbatches])
