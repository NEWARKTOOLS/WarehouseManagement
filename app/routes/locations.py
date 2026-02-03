from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.location import Location
from app.models.inventory import StockLevel, StockMovement

locations_bp = Blueprint('locations', __name__)


@locations_bp.route('/')
@login_required
def location_list():
    """List all locations with zone filtering"""
    from app.models.inventory import StockLevel

    current_zone = request.args.get('zone', '').strip().upper()

    # Get all zones for filter buttons
    zones = db.session.query(Location.zone).filter(
        Location.is_active == True,
        Location.zone != None,
        Location.zone != ''
    ).distinct().order_by(Location.zone).all()
    zones = [z[0] for z in zones]

    # Query locations
    query = Location.query.filter_by(is_active=True)
    if current_zone:
        query = query.filter_by(zone=current_zone)

    locations = query.order_by(Location.zone, Location.code).all()

    # Add item count to each location
    for loc in locations:
        loc.item_count = StockLevel.query.filter(
            StockLevel.location_id == loc.id,
            StockLevel.quantity > 0
        ).count()

    return render_template('locations/list.html',
                           locations=locations,
                           zones=zones,
                           current_zone=current_zone)


@locations_bp.route('/new', methods=['GET', 'POST'])
@login_required
def location_create():
    """Create new location"""
    # Get existing zones for dropdown
    zones = db.session.query(Location.zone).filter(
        Location.is_active == True,
        Location.zone != None,
        Location.zone != ''
    ).distinct().order_by(Location.zone).all()
    zones = [z[0] for z in zones]

    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        name = request.form.get('name', '').strip()
        location_type = request.form.get('location_type', '')
        zone = request.form.get('zone', '').strip().upper()
        row = request.form.get('row', '').strip()
        bay = request.form.get('bay', '').strip()
        shelf = request.form.get('shelf', '').strip()
        description = request.form.get('description', '').strip()
        capacity_units = request.form.get('capacity_units', 'pallets')
        max_capacity = request.form.get('max_capacity', 0, type=float)

        # Validation
        if not code or not name:
            flash('Code and name are required', 'error')
            return render_template('locations/form.html', location=None, zones=zones)

        if Location.query.filter_by(code=code).first():
            flash('Location code already exists', 'error')
            return render_template('locations/form.html', location=None, zones=zones)

        location = Location(
            code=code,
            name=name,
            location_type=location_type,
            zone=zone,
            row=row,
            bay=bay,
            shelf=shelf,
            description=description,
            capacity_units=capacity_units,
            max_capacity=max_capacity
        )

        db.session.add(location)
        db.session.commit()

        flash(f'Location {code} created successfully', 'success')
        return redirect(url_for('locations.location_list'))

    return render_template('locations/form.html', location=None, zones=zones)


@locations_bp.route('/<int:location_id>')
@login_required
def location_detail(location_id):
    """View location details and contents"""
    location = Location.query.get_or_404(location_id)
    stock_levels = StockLevel.query.filter(
        StockLevel.location_id == location_id,
        StockLevel.quantity > 0
    ).all()

    return render_template('locations/detail.html', location=location, stock_levels=stock_levels)


@locations_bp.route('/<int:location_id>/edit', methods=['GET', 'POST'])
@login_required
def location_edit(location_id):
    """Edit location"""
    location = Location.query.get_or_404(location_id)

    # Get existing zones for dropdown
    zones = db.session.query(Location.zone).filter(
        Location.is_active == True,
        Location.zone != None,
        Location.zone != ''
    ).distinct().order_by(Location.zone).all()
    zones = [z[0] for z in zones]

    if request.method == 'POST':
        location.name = request.form.get('name', '').strip()
        location.location_type = request.form.get('location_type', '')
        location.zone = request.form.get('zone', '').strip().upper()
        location.row = request.form.get('row', '').strip()
        location.bay = request.form.get('bay', '').strip()
        location.shelf = request.form.get('shelf', '').strip()
        location.description = request.form.get('description', '').strip()
        location.capacity_units = request.form.get('capacity_units', 'pallets')
        location.max_capacity = request.form.get('max_capacity', 0, type=float)

        db.session.commit()
        flash(f'Location {location.code} updated successfully', 'success')
        return redirect(url_for('locations.location_list'))

    return render_template('locations/form.html', location=location, zones=zones)


@locations_bp.route('/<int:location_id>/delete', methods=['POST'])
@login_required
def location_delete(location_id):
    """Delete (deactivate) location - zeroes any stock with warning"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('locations.location_list'))

    location = Location.query.get_or_404(location_id)
    code = location.code

    # Check if location has stock and zero it out
    stock_zeroed = 0
    for sl in location.stock_levels.all():
        if sl.quantity > 0:
            # Record adjustment movement
            movement = StockMovement(
                item_id=sl.item_id,
                movement_type='adjustment',
                quantity=-sl.quantity,
                from_location_id=location.id,
                reason='Location deleted',
                notes=f'Stock removed due to location {code} deletion',
                user_id=current_user.id
            )
            db.session.add(movement)
            stock_zeroed += sl.quantity
            sl.quantity = 0

    location.is_active = False
    db.session.commit()

    if stock_zeroed > 0:
        flash(f'Location {code} deleted. {int(stock_zeroed)} units of stock were removed.', 'warning')
    else:
        flash(f'Location {code} has been deactivated', 'success')
    return redirect(url_for('locations.location_list'))


@locations_bp.route('/delete-zone', methods=['POST'])
@login_required
def delete_zone():
    """Delete all locations in a single zone (that have no stock)"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('locations.location_list'))

    zone = request.form.get('zone', '').strip().upper()
    if not zone:
        flash('Zone is required', 'error')
        return redirect(url_for('locations.location_list'))

    # Get all locations in zone
    locations = Location.query.filter_by(zone=zone, is_active=True).all()

    deleted = 0
    skipped = 0
    for loc in locations:
        has_stock = any(sl.quantity > 0 for sl in loc.stock_levels.all())
        if has_stock:
            skipped += 1
        else:
            loc.is_active = False
            deleted += 1

    db.session.commit()

    if deleted > 0:
        flash(f'Deleted {deleted} locations from zone {zone}. Skipped {skipped} with stock.', 'success')
    else:
        flash(f'No locations deleted. {skipped} locations have stock.', 'warning')

    return redirect(url_for('locations.location_list'))


@locations_bp.route('/delete-zones', methods=['POST'])
@login_required
def delete_zones():
    """Delete all locations in multiple zones - zeroes any stock"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('locations.location_list'))

    # Get list of zones from checkboxes
    zones_to_delete = request.form.getlist('zones')
    force_delete = request.form.get('force_delete') == '1'

    if not zones_to_delete:
        flash('No zones selected', 'error')
        return redirect(url_for('locations.location_list'))

    total_deleted = 0
    total_stock_removed = 0
    zones_processed = []

    for zone in zones_to_delete:
        zone = zone.strip().upper()
        if not zone:
            continue

        # Get all locations in zone
        locations = Location.query.filter_by(zone=zone, is_active=True).all()

        for loc in locations:
            # Zero out any stock
            for sl in loc.stock_levels.all():
                if sl.quantity > 0:
                    movement = StockMovement(
                        item_id=sl.item_id,
                        movement_type='adjustment',
                        quantity=-sl.quantity,
                        from_location_id=loc.id,
                        reason='Zone deleted',
                        notes=f'Stock removed due to zone {zone} deletion',
                        user_id=current_user.id
                    )
                    db.session.add(movement)
                    total_stock_removed += sl.quantity
                    sl.quantity = 0

            loc.is_active = False
            total_deleted += 1

        zones_processed.append(zone)

    db.session.commit()

    if total_stock_removed > 0:
        flash(f'Deleted {total_deleted} locations from {len(zones_processed)} zone(s). {int(total_stock_removed)} units of stock were removed.', 'warning')
    else:
        flash(f'Deleted {total_deleted} locations from {len(zones_processed)} zone(s): {", ".join(zones_processed)}', 'success')

    return redirect(url_for('locations.location_list'))


@locations_bp.route('/bulk-create', methods=['GET', 'POST'])
@login_required
def bulk_create():
    """Bulk create locations (for racking systems)"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('locations.location_list'))

    if request.method == 'POST':
        zone = request.form.get('zone', '').strip().upper()
        location_type = request.form.get('location_type', 'rack')
        rows = request.form.get('rows', 1, type=int)
        bays = request.form.get('bays', 1, type=int)
        shelves = request.form.get('shelves', 1, type=int)
        capacity_units = request.form.get('capacity_units', 'boxes')
        max_capacity = request.form.get('max_capacity', 1, type=float)

        if not zone:
            flash('Zone is required', 'error')
            return render_template('locations/bulk_create.html')

        created = 0
        skipped = 0

        for r in range(1, rows + 1):
            for b in range(1, bays + 1):
                for s in range(1, shelves + 1):
                    code = Location.generate_code(zone, str(r), str(b), str(s))

                    if Location.query.filter_by(code=code).first():
                        skipped += 1
                        continue

                    location = Location(
                        code=code,
                        name=f'{zone} Row {r} Bay {b} Shelf {s}',
                        location_type=location_type,
                        zone=zone,
                        row=str(r).zfill(2),
                        bay=str(b).zfill(2),
                        shelf=str(s).zfill(2),
                        capacity_units=capacity_units,
                        max_capacity=max_capacity
                    )
                    db.session.add(location)
                    created += 1

        db.session.commit()
        flash(f'Created {created} locations. Skipped {skipped} existing.', 'success')
        return redirect(url_for('locations.location_list'))

    return render_template('locations/bulk_create.html')


# API endpoints for AJAX
@locations_bp.route('/api/search')
@login_required
def api_search():
    """Search locations via API"""
    query = request.args.get('q', '').strip()

    locations = Location.query.filter(
        Location.is_active == True,
        db.or_(
            Location.code.ilike(f'%{query}%'),
            Location.name.ilike(f'%{query}%')
        )
    ).limit(20).all()

    return jsonify([{
        'id': loc.id,
        'code': loc.code,
        'name': loc.name,
        'type': loc.location_type
    } for loc in locations])


@locations_bp.route('/api/<int:location_id>/contents')
@login_required
def api_contents(location_id):
    """Get location contents via API"""
    location = Location.query.get_or_404(location_id)

    from app.models.inventory import StockLevel
    stock_levels = StockLevel.query.filter_by(
        location_id=location_id
    ).filter(StockLevel.quantity > 0).all()

    return jsonify({
        'location': {
            'id': location.id,
            'code': location.code,
            'name': location.name
        },
        'contents': [{
            'item_id': sl.item.id,
            'sku': sl.item.sku,
            'name': sl.item.name,
            'quantity': sl.quantity,
            'unit': sl.item.unit_of_measure
        } for sl in stock_levels]
    })
