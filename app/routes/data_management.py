"""
Data Import/Export Routes
CSV templates, import, and backup functionality
"""
import os
import csv
import io
import zipfile
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, Response, current_app
from flask_login import login_required, current_user
from app import db
from app.models.orders import Customer
from app.models.inventory import Item, Category
from app.models.production import Mould, Machine
from app.models.materials import Material, MaterialSupplier, Masterbatch
from app.models.location import Location
from app.models.costing import Quote

bp = Blueprint('data_management', __name__, url_prefix='/data')


# ============== CSV TEMPLATE DEFINITIONS ==============

CSV_TEMPLATES = {
    'customers': {
        'name': 'Customers',
        'filename': 'customers_template.csv',
        'headers': ['code', 'name', 'contact_name', 'email', 'phone', 'address', 'city', 'postcode', 'country', 'payment_terms', 'notes'],
        'required': ['name'],
        'example': ['CUST001', 'Acme Manufacturing Ltd', 'John Smith', 'john@acme.com', '01onal 123456', '123 Industrial Way', 'Birmingham', 'B1 1AA', 'UK', 'Net 30', 'Good customer']
    },
    'materials': {
        'name': 'Materials',
        'filename': 'materials_template.csv',
        'headers': ['code', 'name', 'material_type', 'grade', 'manufacturer', 'supplier_code', 'color', 'cost_per_kg', 'mfi', 'density', 'barrel_temp_min', 'barrel_temp_max', 'mould_temp_min', 'mould_temp_max', 'drying_required', 'drying_temp', 'drying_time_hours', 'min_stock_kg', 'notes'],
        'required': ['code', 'name', 'material_type', 'cost_per_kg'],
        'example': ['PP-H450', 'Polypropylene Homopolymer', 'PP', 'H450J', 'SABIC', 'SABIC-PP-450', 'Natural', '2.50', '12', '0.905', '200', '240', '20', '50', 'FALSE', '', '', '500', 'General purpose PP']
    },
    'suppliers': {
        'name': 'Material Suppliers',
        'filename': 'suppliers_template.csv',
        'headers': ['code', 'name', 'contact_name', 'email', 'phone', 'website', 'address_line1', 'address_line2', 'city', 'postcode', 'country', 'account_number', 'payment_terms', 'lead_time_days', 'minimum_order_kg', 'notes'],
        'required': ['name'],
        'example': ['DIST', 'Distrupol Ltd', 'Sales Team', 'sales@distrupol.com', '01234 999888', 'https://distrupol.com', '1 Polymer Park', '', 'Birmingham', 'B1 1AA', 'UK', 'ACC-12345', 'Net 30', '5', '25', 'Primary PP supplier']
    },
    'masterbatches': {
        'name': 'Masterbatches',
        'filename': 'masterbatches_template.csv',
        'headers': ['code', 'name', 'masterbatch_type', 'color', 'color_hex', 'cost_per_kg', 'typical_loading_percent', 'compatible_materials', 'supplier_code', 'min_stock_kg', 'notes'],
        'required': ['code', 'name', 'masterbatch_type', 'cost_per_kg'],
        'example': ['MB-BLK-01', 'Carbon Black Masterbatch', 'Colour', 'Black', '#000000', '8.50', '3', 'PP,PE,HDPE', 'CABOT-BK40', '25', 'Standard black for PP']
    },
    'moulds': {
        'name': 'Moulds',
        'filename': 'moulds_template.csv',
        'headers': ['mould_number', 'name', 'num_cavities', 'material_type', 'runner_type', 'customer_code', 'machine_tonnage_required', 'cycle_time_target', 'status', 'location', 'notes'],
        'required': ['mould_number', 'num_cavities'],
        'example': ['M001', 'Widget Housing', '4', 'PP', 'cold', 'CUST001', '150', '25', 'active', 'Tool Store A', 'Single cavity prototype']
    },
    'machines': {
        'name': 'Machines',
        'filename': 'machines_template.csv',
        'headers': ['code', 'name', 'machine_type', 'manufacturer', 'model', 'tonnage', 'shot_size_g', 'screw_diameter_mm', 'max_mould_width_mm', 'max_mould_height_mm', 'hourly_rate', 'status', 'notes'],
        'required': ['code', 'name'],
        'example': ['INJ-01', 'Borche 80T', 'injection', 'Borche', 'BH-80', '80', '150', '35', '400', '400', '45', 'available', 'Small parts machine']
    },
    'locations': {
        'name': 'Locations',
        'filename': 'locations_template.csv',
        'headers': ['code', 'name', 'zone', 'location_type', 'is_pickable', 'is_receivable', 'max_weight_kg', 'notes'],
        'required': ['code', 'name'],
        'example': ['A-01-01', 'Aisle A Row 1 Level 1', 'A', 'rack', 'TRUE', 'TRUE', '500', 'Standard pallet location']
    },
    'items': {
        'name': 'Inventory Items (Parts)',
        'filename': 'items_template.csv',
        'headers': ['sku', 'name', 'description', 'item_type', 'customer_code', 'unit_of_measure', 'part_weight_grams', 'runner_weight_grams', 'cavities', 'cycle_time_seconds', 'material_code', 'masterbatch_code', 'masterbatch_ratio', 'material_cost_per_kg', 'mould_number', 'color', 'min_stock_level', 'unit_cost', 'selling_price', 'notes'],
        'required': ['sku', 'name'],
        'example': ['WIDGET-001', 'Widget Housing Blue', 'Injection moulded widget housing', 'finished_goods', 'CUST001', 'parts', '45.5', '12', '4', '22', 'PP-H450', 'MB-BLU-01', '3', '2.50', 'M001', 'Blue', '1000', '0.15', '0.35', 'Main production item']
    },
    'categories': {
        'name': 'Categories',
        'filename': 'categories_template.csv',
        'headers': ['name', 'description', 'category_type'],
        'required': ['name'],
        'example': ['Automotive Parts', 'Parts for automotive industry', 'finished_goods']
    }
}


# ============== DOWNLOAD TEMPLATES ==============

@bp.route('/')
@login_required
def index():
    """Data management dashboard"""
    # Get counts for display
    stats = {
        'customers': Customer.query.count(),
        'materials': Material.query.count(),
        'suppliers': MaterialSupplier.query.count(),
        'masterbatches': Masterbatch.query.count(),
        'moulds': Mould.query.count(),
        'machines': Machine.query.count(),
        'locations': Location.query.count(),
        'item_count': Item.query.filter_by(is_active=True).count(),
        'categories': Category.query.count()
    }
    return render_template('data_management/index.html',
                           templates=CSV_TEMPLATES,
                           stats=stats)


@bp.route('/template/<template_type>')
@login_required
def download_template(template_type):
    """Download CSV template for a specific data type"""
    if template_type not in CSV_TEMPLATES:
        flash('Invalid template type', 'error')
        return redirect(url_for('data_management.index'))

    template = CSV_TEMPLATES[template_type]

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write headers with required markers
    header_row = []
    for h in template['headers']:
        if h in template['required']:
            header_row.append(f"{h}*")
        else:
            header_row.append(h)
    writer.writerow(header_row)

    # Write example row
    writer.writerow(template['example'])

    # Prepare response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={template["filename"]}'}
    )


@bp.route('/template/all')
@login_required
def download_all_templates():
    """Download all CSV templates as a ZIP file"""
    # Create ZIP in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for template_type, template in CSV_TEMPLATES.items():
            # Create CSV content
            output = io.StringIO()
            writer = csv.writer(output)

            # Headers with required markers
            header_row = []
            for h in template['headers']:
                if h in template['required']:
                    header_row.append(f"{h}*")
                else:
                    header_row.append(h)
            writer.writerow(header_row)
            writer.writerow(template['example'])

            # Add to ZIP
            zip_file.writestr(template['filename'], output.getvalue())

        # Add README
        readme = """WMS Import Templates - README
=============================

These CSV templates can be used to bulk import data into the WMS system.

IMPORT ORDER (Recommended):
1. suppliers_template.csv - Material suppliers first
2. materials_template.csv - Raw materials
3. masterbatches_template.csv - Colour/additive masterbatches
4. customers_template.csv - Customer information
5. categories_template.csv - Item categories
6. locations_template.csv - Warehouse locations
7. machines_template.csv - Injection moulding machines
8. moulds_template.csv - Moulds/tools
9. items_template.csv - Finished parts/products (depends on materials, customers, moulds)

NOTES:
- Fields marked with * are required
- Use codes (e.g., customer_code, material_code) to link records
- TRUE/FALSE for boolean fields
- Leave optional fields empty if not needed
- Dates should be in YYYY-MM-DD format
"""
        zip_file.writestr('README.txt', readme)

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='wms_import_templates.zip'
    )


# ============== IMPORT DATA ==============

@bp.route('/import', methods=['GET', 'POST'])
@login_required
def import_data():
    """Import data from CSV files"""
    if not current_user.is_admin():
        flash('Admin access required for data import', 'error')
        return redirect(url_for('data_management.index'))

    if request.method == 'POST':
        data_type = request.form.get('data_type')
        if data_type not in CSV_TEMPLATES:
            flash('Invalid data type', 'error')
            return redirect(url_for('data_management.import_data'))

        file = request.files.get('csv_file')
        if not file or not file.filename.endswith('.csv'):
            flash('Please upload a valid CSV file', 'error')
            return redirect(url_for('data_management.import_data'))

        try:
            # Read CSV
            content = file.read().decode('utf-8-sig')  # Handle BOM
            reader = csv.DictReader(io.StringIO(content))

            # Clean header names (remove * markers)
            if reader.fieldnames:
                reader.fieldnames = [f.replace('*', '').strip() for f in reader.fieldnames]

            # Process based on type
            result = import_records(data_type, list(reader))

            flash(f"Import complete: {result['created']} created, {result['updated']} updated, {result['errors']} errors",
                  'success' if result['errors'] == 0 else 'warning')

            if result['error_messages']:
                for msg in result['error_messages'][:10]:  # Show first 10 errors
                    flash(msg, 'error')

        except Exception as e:
            flash(f'Import failed: {str(e)}', 'error')
            db.session.rollback()

        return redirect(url_for('data_management.index'))

    return render_template('data_management/import.html', templates=CSV_TEMPLATES)


def import_records(data_type, rows):
    """Import records from CSV rows"""
    result = {'created': 0, 'updated': 0, 'errors': 0, 'error_messages': []}

    for i, row in enumerate(rows, start=2):  # Start at 2 (header is row 1)
        try:
            if data_type == 'customers':
                import_customer(row, result)
            elif data_type == 'materials':
                import_material(row, result)
            elif data_type == 'suppliers':
                import_supplier(row, result)
            elif data_type == 'masterbatches':
                import_masterbatch(row, result)
            elif data_type == 'moulds':
                import_mould(row, result)
            elif data_type == 'machines':
                import_machine(row, result)
            elif data_type == 'locations':
                import_location(row, result)
            elif data_type == 'items':
                import_item(row, result)
            elif data_type == 'categories':
                import_category(row, result)
        except Exception as e:
            result['errors'] += 1
            result['error_messages'].append(f"Row {i}: {str(e)}")

    db.session.commit()
    return result


def import_customer(row, result):
    """Import a customer record"""
    name = row.get('name', '').strip()
    if not name:
        raise ValueError("Name is required")

    code = row.get('code', '').strip().upper() or None

    # Check for existing
    existing = None
    if code:
        existing = Customer.query.filter_by(code=code).first()
    if not existing:
        existing = Customer.query.filter_by(name=name).first()

    if existing:
        # Update
        existing.name = name
        existing.code = code or existing.code
        existing.contact_name = row.get('contact_name', '').strip() or existing.contact_name
        existing.email = row.get('email', '').strip() or existing.email
        existing.phone = row.get('phone', '').strip() or existing.phone
        existing.address = row.get('address', '').strip() or existing.address
        existing.city = row.get('city', '').strip() or existing.city
        existing.postcode = row.get('postcode', '').strip() or existing.postcode
        existing.country = row.get('country', '').strip() or existing.country
        existing.payment_terms = row.get('payment_terms', '').strip() or existing.payment_terms
        existing.notes = row.get('notes', '').strip() or existing.notes
        result['updated'] += 1
    else:
        # Create
        customer = Customer(
            code=code,
            name=name,
            contact_name=row.get('contact_name', '').strip() or None,
            email=row.get('email', '').strip() or None,
            phone=row.get('phone', '').strip() or None,
            address=row.get('address', '').strip() or None,
            city=row.get('city', '').strip() or None,
            postcode=row.get('postcode', '').strip() or None,
            country=row.get('country', '').strip() or 'UK',
            payment_terms=row.get('payment_terms', '').strip() or None,
            notes=row.get('notes', '').strip() or None
        )
        db.session.add(customer)
        result['created'] += 1


def import_supplier(row, result):
    """Import a material supplier record"""
    name = row.get('name', '').strip()
    if not name:
        raise ValueError("Name is required")

    code = row.get('code', '').strip().upper() or None

    # Check for existing
    existing = MaterialSupplier.query.filter_by(name=name).first()

    if existing:
        existing.code = code or existing.code
        existing.contact_name = row.get('contact_name', '').strip() or existing.contact_name
        existing.email = row.get('email', '').strip() or existing.email
        existing.phone = row.get('phone', '').strip() or existing.phone
        existing.website = row.get('website', '').strip() or existing.website
        existing.address_line1 = row.get('address_line1', '').strip() or existing.address_line1
        existing.address_line2 = row.get('address_line2', '').strip() or existing.address_line2
        existing.city = row.get('city', '').strip() or existing.city
        existing.postcode = row.get('postcode', '').strip() or existing.postcode
        existing.country = row.get('country', '').strip() or existing.country
        existing.account_number = row.get('account_number', '').strip() or existing.account_number
        existing.payment_terms = row.get('payment_terms', '').strip() or existing.payment_terms
        existing.lead_time_days = int(row.get('lead_time_days') or 0) or existing.lead_time_days
        existing.minimum_order_kg = float(row.get('minimum_order_kg') or 0) or existing.minimum_order_kg
        existing.notes = row.get('notes', '').strip() or existing.notes
        result['updated'] += 1
    else:
        supplier = MaterialSupplier(
            code=code,
            name=name,
            contact_name=row.get('contact_name', '').strip() or None,
            email=row.get('email', '').strip() or None,
            phone=row.get('phone', '').strip() or None,
            website=row.get('website', '').strip() or None,
            address_line1=row.get('address_line1', '').strip() or None,
            address_line2=row.get('address_line2', '').strip() or None,
            city=row.get('city', '').strip() or None,
            postcode=row.get('postcode', '').strip() or None,
            country=row.get('country', '').strip() or 'UK',
            account_number=row.get('account_number', '').strip() or None,
            payment_terms=row.get('payment_terms', '').strip() or None,
            lead_time_days=int(row.get('lead_time_days') or 0) or None,
            minimum_order_kg=float(row.get('minimum_order_kg') or 0) or None,
            notes=row.get('notes', '').strip() or None
        )
        db.session.add(supplier)
        result['created'] += 1


def import_material(row, result):
    """Import a material record"""
    code = row.get('code', '').strip().upper()
    name = row.get('name', '').strip()
    material_type = row.get('material_type', '').strip().upper()
    cost = row.get('cost_per_kg', '').strip()

    if not code or not name or not material_type or not cost:
        raise ValueError("Code, name, material_type, and cost_per_kg are required")

    cost_per_kg = float(cost)

    # Check for existing
    existing = Material.query.filter_by(code=code).first()

    if existing:
        existing.name = name
        existing.material_type = material_type
        existing.grade = row.get('grade', '').strip() or existing.grade
        existing.manufacturer = row.get('manufacturer', '').strip() or existing.manufacturer
        existing.supplier_code = row.get('supplier_code', '').strip() or existing.supplier_code
        existing.color = row.get('color', '').strip() or existing.color
        existing.cost_per_kg = cost_per_kg
        existing.mfi = float(row.get('mfi') or 0) or existing.mfi
        existing.density = float(row.get('density') or 0) or existing.density
        existing.barrel_temp_min = int(row.get('barrel_temp_min') or 0) or existing.barrel_temp_min
        existing.barrel_temp_max = int(row.get('barrel_temp_max') or 0) or existing.barrel_temp_max
        existing.mould_temp_min = int(row.get('mould_temp_min') or 0) or existing.mould_temp_min
        existing.mould_temp_max = int(row.get('mould_temp_max') or 0) or existing.mould_temp_max
        existing.drying_required = row.get('drying_required', '').upper() == 'TRUE'
        existing.drying_temp = int(row.get('drying_temp') or 0) or existing.drying_temp
        existing.drying_time_hours = float(row.get('drying_time_hours') or 0) or existing.drying_time_hours
        existing.min_stock_kg = float(row.get('min_stock_kg') or 0) or existing.min_stock_kg
        existing.notes = row.get('notes', '').strip() or existing.notes
        existing.last_price_update = datetime.utcnow()
        result['updated'] += 1
    else:
        material = Material(
            code=code,
            name=name,
            material_type=material_type,
            grade=row.get('grade', '').strip() or None,
            manufacturer=row.get('manufacturer', '').strip() or None,
            supplier_code=row.get('supplier_code', '').strip() or None,
            color=row.get('color', '').strip() or 'Natural',
            cost_per_kg=cost_per_kg,
            mfi=float(row.get('mfi') or 0) or None,
            density=float(row.get('density') or 0) or None,
            barrel_temp_min=int(row.get('barrel_temp_min') or 0) or None,
            barrel_temp_max=int(row.get('barrel_temp_max') or 0) or None,
            mould_temp_min=int(row.get('mould_temp_min') or 0) or None,
            mould_temp_max=int(row.get('mould_temp_max') or 0) or None,
            drying_required=row.get('drying_required', '').upper() == 'TRUE',
            drying_temp=int(row.get('drying_temp') or 0) or None,
            drying_time_hours=float(row.get('drying_time_hours') or 0) or None,
            min_stock_kg=float(row.get('min_stock_kg') or 0) or None,
            notes=row.get('notes', '').strip() or None,
            last_price_update=datetime.utcnow()
        )
        db.session.add(material)
        result['created'] += 1


def import_masterbatch(row, result):
    """Import a masterbatch record"""
    code = row.get('code', '').strip().upper()
    name = row.get('name', '').strip()
    mb_type = row.get('masterbatch_type', '').strip()
    cost = row.get('cost_per_kg', '').strip()

    if not code or not name or not mb_type or not cost:
        raise ValueError("Code, name, masterbatch_type, and cost_per_kg are required")

    cost_per_kg = float(cost)

    existing = Masterbatch.query.filter_by(code=code).first()

    if existing:
        existing.name = name
        existing.masterbatch_type = mb_type
        existing.color = row.get('color', '').strip() or existing.color
        existing.color_hex = row.get('color_hex', '').strip() or existing.color_hex
        existing.cost_per_kg = cost_per_kg
        existing.typical_loading_percent = float(row.get('typical_loading_percent') or 0) or existing.typical_loading_percent
        existing.compatible_materials = row.get('compatible_materials', '').strip() or existing.compatible_materials
        existing.supplier_code = row.get('supplier_code', '').strip() or existing.supplier_code
        existing.min_stock_kg = float(row.get('min_stock_kg') or 0) or existing.min_stock_kg
        existing.notes = row.get('notes', '').strip() or existing.notes
        result['updated'] += 1
    else:
        masterbatch = Masterbatch(
            code=code,
            name=name,
            masterbatch_type=mb_type,
            color=row.get('color', '').strip() or None,
            color_hex=row.get('color_hex', '').strip() or None,
            cost_per_kg=cost_per_kg,
            typical_loading_percent=float(row.get('typical_loading_percent') or 0) or None,
            compatible_materials=row.get('compatible_materials', '').strip() or None,
            supplier_code=row.get('supplier_code', '').strip() or None,
            min_stock_kg=float(row.get('min_stock_kg') or 0) or None,
            notes=row.get('notes', '').strip() or None
        )
        db.session.add(masterbatch)
        result['created'] += 1


def import_mould(row, result):
    """Import a mould record"""
    mould_number = row.get('mould_number', '').strip().upper()
    num_cavities = row.get('num_cavities', '').strip()

    if not mould_number or not num_cavities:
        raise ValueError("Mould number and num_cavities are required")

    # Look up customer by code
    customer_id = None
    customer_code = row.get('customer_code', '').strip().upper()
    if customer_code:
        customer = Customer.query.filter_by(code=customer_code).first()
        if customer:
            customer_id = customer.id

    existing = Mould.query.filter_by(mould_number=mould_number).first()

    if existing:
        existing.name = row.get('name', '').strip() or existing.name
        existing.num_cavities = int(num_cavities)
        existing.material_type = row.get('material_type', '').strip() or existing.material_type
        existing.runner_type = row.get('runner_type', '').strip() or existing.runner_type
        existing.customer_id = customer_id or existing.customer_id
        existing.machine_tonnage_required = int(row.get('machine_tonnage_required') or 0) or existing.machine_tonnage_required
        existing.cycle_time_target = float(row.get('cycle_time_target') or 0) or existing.cycle_time_target
        existing.status = row.get('status', '').strip() or existing.status
        existing.location = row.get('location', '').strip() or existing.location
        existing.notes = row.get('notes', '').strip() or existing.notes
        result['updated'] += 1
    else:
        mould = Mould(
            mould_number=mould_number,
            name=row.get('name', '').strip() or None,
            num_cavities=int(num_cavities),
            material_type=row.get('material_type', '').strip() or None,
            runner_type=row.get('runner_type', '').strip() or 'cold',
            customer_id=customer_id,
            machine_tonnage_required=int(row.get('machine_tonnage_required') or 0) or None,
            cycle_time_target=float(row.get('cycle_time_target') or 0) or None,
            status=row.get('status', '').strip() or 'active',
            location=row.get('location', '').strip() or None,
            notes=row.get('notes', '').strip() or None
        )
        db.session.add(mould)
        result['created'] += 1


def import_machine(row, result):
    """Import a machine record"""
    code = row.get('code', '').strip().upper()
    name = row.get('name', '').strip()

    if not code or not name:
        raise ValueError("Code and name are required")

    existing = Machine.query.filter_by(code=code).first()

    if existing:
        existing.name = name
        existing.machine_type = row.get('machine_type', '').strip() or existing.machine_type
        existing.manufacturer = row.get('manufacturer', '').strip() or existing.manufacturer
        existing.model = row.get('model', '').strip() or existing.model
        existing.tonnage = int(row.get('tonnage') or 0) or existing.tonnage
        existing.shot_size_g = float(row.get('shot_size_g') or 0) or existing.shot_size_g
        existing.screw_diameter_mm = float(row.get('screw_diameter_mm') or 0) or existing.screw_diameter_mm
        existing.max_mould_width_mm = float(row.get('max_mould_width_mm') or 0) or existing.max_mould_width_mm
        existing.max_mould_height_mm = float(row.get('max_mould_height_mm') or 0) or existing.max_mould_height_mm
        existing.hourly_rate = float(row.get('hourly_rate') or 0) or existing.hourly_rate
        existing.status = row.get('status', '').strip() or existing.status
        existing.notes = row.get('notes', '').strip() or existing.notes
        result['updated'] += 1
    else:
        machine = Machine(
            code=code,
            name=name,
            machine_type=row.get('machine_type', '').strip() or 'injection',
            manufacturer=row.get('manufacturer', '').strip() or None,
            model=row.get('model', '').strip() or None,
            tonnage=int(row.get('tonnage') or 0) or None,
            shot_size_g=float(row.get('shot_size_g') or 0) or None,
            screw_diameter_mm=float(row.get('screw_diameter_mm') or 0) or None,
            max_mould_width_mm=float(row.get('max_mould_width_mm') or 0) or None,
            max_mould_height_mm=float(row.get('max_mould_height_mm') or 0) or None,
            hourly_rate=float(row.get('hourly_rate') or 0) or None,
            status=row.get('status', '').strip() or 'available',
            notes=row.get('notes', '').strip() or None
        )
        db.session.add(machine)
        result['created'] += 1


def import_location(row, result):
    """Import a location record"""
    code = row.get('code', '').strip().upper()
    name = row.get('name', '').strip()

    if not code or not name:
        raise ValueError("Code and name are required")

    existing = Location.query.filter_by(code=code).first()

    if existing:
        existing.name = name
        existing.zone = row.get('zone', '').strip() or existing.zone
        existing.location_type = row.get('location_type', '').strip() or existing.location_type
        existing.is_pickable = row.get('is_pickable', '').upper() != 'FALSE'
        existing.is_receivable = row.get('is_receivable', '').upper() != 'FALSE'
        existing.max_weight_kg = float(row.get('max_weight_kg') or 0) or existing.max_weight_kg
        existing.notes = row.get('notes', '').strip() or existing.notes
        result['updated'] += 1
    else:
        location = Location(
            code=code,
            name=name,
            zone=row.get('zone', '').strip() or None,
            location_type=row.get('location_type', '').strip() or 'rack',
            is_pickable=row.get('is_pickable', '').upper() != 'FALSE',
            is_receivable=row.get('is_receivable', '').upper() != 'FALSE',
            max_weight_kg=float(row.get('max_weight_kg') or 0) or None,
            notes=row.get('notes', '').strip() or None
        )
        db.session.add(location)
        result['created'] += 1


def import_category(row, result):
    """Import a category record"""
    name = row.get('name', '').strip()

    if not name:
        raise ValueError("Name is required")

    existing = Category.query.filter_by(name=name).first()

    if existing:
        existing.description = row.get('description', '').strip() or existing.description
        existing.category_type = row.get('category_type', '').strip() or existing.category_type
        result['updated'] += 1
    else:
        category = Category(
            name=name,
            description=row.get('description', '').strip() or None,
            category_type=row.get('category_type', '').strip() or None
        )
        db.session.add(category)
        result['created'] += 1


def import_item(row, result):
    """Import an inventory item record"""
    sku = row.get('sku', '').strip().upper()
    name = row.get('name', '').strip()

    if not sku or not name:
        raise ValueError("SKU and name are required")

    # Look up related records by code
    customer_id = None
    customer_code = row.get('customer_code', '').strip().upper()
    if customer_code:
        customer = Customer.query.filter_by(code=customer_code).first()
        if customer:
            customer_id = customer.id

    mould_id = None
    mould_number = row.get('mould_number', '').strip().upper()
    if mould_number:
        mould = Mould.query.filter_by(mould_number=mould_number).first()
        if mould:
            mould_id = mould.id

    material_id = None
    material_code = row.get('material_code', '').strip().upper()
    if material_code:
        material = Material.query.filter_by(code=material_code).first()
        if material:
            material_id = material.id

    masterbatch_id = None
    masterbatch_code = row.get('masterbatch_code', '').strip().upper()
    if masterbatch_code:
        masterbatch = Masterbatch.query.filter_by(code=masterbatch_code).first()
        if masterbatch:
            masterbatch_id = masterbatch.id

    existing = Item.query.filter_by(sku=sku).first()

    if existing:
        existing.name = name
        existing.description = row.get('description', '').strip() or existing.description
        existing.item_type = row.get('item_type', '').strip() or existing.item_type
        existing.customer_id = customer_id or existing.customer_id
        existing.unit_of_measure = row.get('unit_of_measure', '').strip() or existing.unit_of_measure
        existing.part_weight_grams = float(row.get('part_weight_grams') or 0) or existing.part_weight_grams
        existing.runner_weight_grams = float(row.get('runner_weight_grams') or 0) or existing.runner_weight_grams
        existing.cavities = int(row.get('cavities') or 0) or existing.cavities
        existing.cycle_time_seconds = float(row.get('cycle_time_seconds') or 0) or existing.cycle_time_seconds
        existing.linked_material_id = material_id or existing.linked_material_id
        existing.linked_masterbatch_id = masterbatch_id or existing.linked_masterbatch_id
        existing.masterbatch_ratio = row.get('masterbatch_ratio', '').strip() or existing.masterbatch_ratio
        existing.material_cost_per_kg = float(row.get('material_cost_per_kg') or 0) or existing.material_cost_per_kg
        existing.default_mould_id = mould_id or existing.default_mould_id
        existing.color = row.get('color', '').strip() or existing.color
        existing.min_stock_level = float(row.get('min_stock_level') or 0) or existing.min_stock_level
        existing.unit_cost = float(row.get('unit_cost') or 0) or existing.unit_cost
        existing.selling_price = float(row.get('selling_price') or 0) or existing.selling_price
        existing.notes = row.get('notes', '').strip() or existing.notes
        result['updated'] += 1
    else:
        item = Item(
            sku=sku,
            name=name,
            description=row.get('description', '').strip() or None,
            item_type=row.get('item_type', '').strip() or 'finished_goods',
            customer_id=customer_id,
            unit_of_measure=row.get('unit_of_measure', '').strip() or 'parts',
            part_weight_grams=float(row.get('part_weight_grams') or 0) or None,
            runner_weight_grams=float(row.get('runner_weight_grams') or 0) or None,
            cavities=int(row.get('cavities') or 0) or 1,
            cycle_time_seconds=float(row.get('cycle_time_seconds') or 0) or None,
            linked_material_id=material_id,
            linked_masterbatch_id=masterbatch_id,
            masterbatch_ratio=row.get('masterbatch_ratio', '').strip() or None,
            material_cost_per_kg=float(row.get('material_cost_per_kg') or 0) or None,
            default_mould_id=mould_id,
            color=row.get('color', '').strip() or None,
            min_stock_level=float(row.get('min_stock_level') or 0) or 0,
            unit_cost=float(row.get('unit_cost') or 0) or 0,
            selling_price=float(row.get('selling_price') or 0) or 0,
            notes=row.get('notes', '').strip() or None,
            barcode=sku
        )
        db.session.add(item)
        result['created'] += 1


# ============== EXPORT / BACKUP ==============

@bp.route('/export/<data_type>')
@login_required
def export_data(data_type):
    """Export data as CSV"""
    if data_type not in CSV_TEMPLATES and data_type != 'all':
        flash('Invalid export type', 'error')
        return redirect(url_for('data_management.index'))

    if data_type == 'all':
        return export_all_data()

    # Get records based on type
    output = io.StringIO()
    writer = csv.writer(output)

    template = CSV_TEMPLATES[data_type]
    writer.writerow(template['headers'])

    if data_type == 'customers':
        for c in Customer.query.order_by(Customer.name).all():
            writer.writerow([c.code, c.name, c.contact_name, c.email, c.phone, c.address, c.city, c.postcode, c.country, c.payment_terms, c.notes])

    elif data_type == 'materials':
        for m in Material.query.order_by(Material.code).all():
            writer.writerow([m.code, m.name, m.material_type, m.grade, m.manufacturer, m.supplier_code, m.color, m.cost_per_kg, m.mfi, m.density, m.barrel_temp_min, m.barrel_temp_max, m.mould_temp_min, m.mould_temp_max, 'TRUE' if m.drying_required else 'FALSE', m.drying_temp, m.drying_time_hours, m.min_stock_kg, m.notes])

    elif data_type == 'suppliers':
        for s in MaterialSupplier.query.order_by(MaterialSupplier.name).all():
            writer.writerow([s.code, s.name, s.contact_name, s.email, s.phone, s.website, s.address_line1, s.address_line2, s.city, s.postcode, s.country, s.account_number, s.payment_terms, s.lead_time_days, s.minimum_order_kg, s.notes])

    elif data_type == 'masterbatches':
        for mb in Masterbatch.query.order_by(Masterbatch.code).all():
            writer.writerow([mb.code, mb.name, mb.masterbatch_type, mb.color, mb.color_hex, mb.cost_per_kg, mb.typical_loading_percent, mb.compatible_materials, mb.supplier_code, mb.min_stock_kg, mb.notes])

    elif data_type == 'moulds':
        for m in Mould.query.order_by(Mould.mould_number).all():
            customer_code = m.customer.code if m.customer else ''
            writer.writerow([m.mould_number, m.name, m.num_cavities, m.material_type, m.runner_type, customer_code, m.machine_tonnage_required, m.cycle_time_target, m.status, m.location, m.notes])

    elif data_type == 'machines':
        for m in Machine.query.order_by(Machine.code).all():
            writer.writerow([m.code, m.name, m.machine_type, m.manufacturer, m.model, m.tonnage, m.shot_size_g, m.screw_diameter_mm, m.max_mould_width_mm, m.max_mould_height_mm, m.hourly_rate, m.status, m.notes])

    elif data_type == 'locations':
        for l in Location.query.order_by(Location.code).all():
            writer.writerow([l.code, l.name, l.zone, l.location_type, 'TRUE' if l.is_pickable else 'FALSE', 'TRUE' if l.is_receivable else 'FALSE', l.max_weight_kg, l.notes])

    elif data_type == 'items':
        for i in Item.query.filter_by(is_active=True).order_by(Item.sku).all():
            customer_code = i.customer.code if i.customer else ''
            mould_number = i.default_mould.mould_number if i.default_mould else ''
            material_code = i.linked_material.code if i.linked_material else ''
            masterbatch_code = i.linked_masterbatch.code if i.linked_masterbatch else ''
            writer.writerow([i.sku, i.name, i.description, i.item_type, customer_code, i.unit_of_measure, i.part_weight_grams, i.runner_weight_grams, i.cavities, i.cycle_time_seconds, material_code, masterbatch_code, i.masterbatch_ratio, i.material_cost_per_kg, mould_number, i.color, i.min_stock_level, i.unit_cost, i.selling_price, i.notes])

    elif data_type == 'categories':
        for c in Category.query.order_by(Category.name).all():
            writer.writerow([c.name, c.description, c.category_type])

    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={data_type}_export_{timestamp}.csv'}
    )


@bp.route('/backup')
@login_required
def export_all_data():
    """Export all data as ZIP backup"""
    if not current_user.is_admin():
        flash('Admin access required for full backup', 'error')
        return redirect(url_for('data_management.index'))

    zip_buffer = io.BytesIO()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Export each data type
        for data_type, template in CSV_TEMPLATES.items():
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(template['headers'])

            if data_type == 'customers':
                for c in Customer.query.order_by(Customer.name).all():
                    writer.writerow([c.code, c.name, c.contact_name, c.email, c.phone, c.address, c.city, c.postcode, c.country, c.payment_terms, c.notes])

            elif data_type == 'materials':
                for m in Material.query.order_by(Material.code).all():
                    writer.writerow([m.code, m.name, m.material_type, m.grade, m.manufacturer, m.supplier_code, m.color, m.cost_per_kg, m.mfi, m.density, m.barrel_temp_min, m.barrel_temp_max, m.mould_temp_min, m.mould_temp_max, 'TRUE' if m.drying_required else 'FALSE', m.drying_temp, m.drying_time_hours, m.min_stock_kg, m.notes])

            elif data_type == 'suppliers':
                for s in MaterialSupplier.query.order_by(MaterialSupplier.name).all():
                    writer.writerow([s.code, s.name, s.contact_name, s.email, s.phone, s.website, s.address_line1, s.address_line2, s.city, s.postcode, s.country, s.account_number, s.payment_terms, s.lead_time_days, s.minimum_order_kg, s.notes])

            elif data_type == 'masterbatches':
                for mb in Masterbatch.query.order_by(Masterbatch.code).all():
                    writer.writerow([mb.code, mb.name, mb.masterbatch_type, mb.color, mb.color_hex, mb.cost_per_kg, mb.typical_loading_percent, mb.compatible_materials, mb.supplier_code, mb.min_stock_kg, mb.notes])

            elif data_type == 'moulds':
                for m in Mould.query.order_by(Mould.mould_number).all():
                    customer_code = m.customer.code if m.customer else ''
                    writer.writerow([m.mould_number, m.name, m.num_cavities, m.material_type, m.runner_type, customer_code, m.machine_tonnage_required, m.cycle_time_target, m.status, m.location, m.notes])

            elif data_type == 'machines':
                for m in Machine.query.order_by(Machine.code).all():
                    writer.writerow([m.code, m.name, m.machine_type, m.manufacturer, m.model, m.tonnage, m.shot_size_g, m.screw_diameter_mm, m.max_mould_width_mm, m.max_mould_height_mm, m.hourly_rate, m.status, m.notes])

            elif data_type == 'locations':
                for l in Location.query.order_by(Location.code).all():
                    writer.writerow([l.code, l.name, l.zone, l.location_type, 'TRUE' if l.is_pickable else 'FALSE', 'TRUE' if l.is_receivable else 'FALSE', l.max_weight_kg, l.notes])

            elif data_type == 'items':
                for i in Item.query.filter_by(is_active=True).order_by(Item.sku).all():
                    customer_code = i.customer.code if i.customer else ''
                    mould_number = i.default_mould.mould_number if i.default_mould else ''
                    material_code = i.linked_material.code if i.linked_material else ''
                    masterbatch_code = i.linked_masterbatch.code if i.linked_masterbatch else ''
                    writer.writerow([i.sku, i.name, i.description, i.item_type, customer_code, i.unit_of_measure, i.part_weight_grams, i.runner_weight_grams, i.cavities, i.cycle_time_seconds, material_code, masterbatch_code, i.masterbatch_ratio, i.material_cost_per_kg, mould_number, i.color, i.min_stock_level, i.unit_cost, i.selling_price, i.notes])

            elif data_type == 'categories':
                for c in Category.query.order_by(Category.name).all():
                    writer.writerow([c.name, c.description, c.category_type])

            zip_file.writestr(f'{data_type}_backup_{timestamp}.csv', output.getvalue())

        # Add backup info
        info = f"""WMS Backup
==========
Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
User: {current_user.username}

Contents:
- customers_backup_{timestamp}.csv
- suppliers_backup_{timestamp}.csv
- materials_backup_{timestamp}.csv
- masterbatches_backup_{timestamp}.csv
- categories_backup_{timestamp}.csv
- locations_backup_{timestamp}.csv
- machines_backup_{timestamp}.csv
- moulds_backup_{timestamp}.csv
- items_backup_{timestamp}.csv

To restore: Use the Import function in Settings > Data Management
"""
        zip_file.writestr('BACKUP_INFO.txt', info)

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'wms_backup_{timestamp}.zip'
    )


# ============== QUOTE PDF ==============

@bp.route('/quote/<int:quote_id>/pdf')
@login_required
def quote_pdf(quote_id):
    """Generate PDF for quote (customer-facing, no cost breakdown)"""
    quote = Quote.query.get_or_404(quote_id)

    # Render HTML template for PDF
    html_content = render_template('data_management/quote_pdf.html',
                                   quote=quote,
                                   show_breakdown=False)

    # For now, return HTML that can be printed to PDF
    # In production, you'd use weasyprint or similar
    return render_template('data_management/quote_pdf.html',
                           quote=quote,
                           show_breakdown=False,
                           print_mode=True)


@bp.route('/quote/<int:quote_id>/pdf/internal')
@login_required
def quote_pdf_internal(quote_id):
    """Generate internal PDF for quote (with cost breakdown)"""
    quote = Quote.query.get_or_404(quote_id)

    return render_template('data_management/quote_pdf.html',
                           quote=quote,
                           show_breakdown=True,
                           print_mode=True)
