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
        'headers': ['customer_code', 'name', 'contact_name', 'email', 'phone', 'address_line1', 'address_line2', 'city', 'postcode', 'country', 'credit_terms', 'notes'],
        'required': ['customer_code', 'name'],
        'example': ['CUST001', 'Acme Manufacturing Ltd', 'John Smith', 'john@acme.com', '01onal 123456', '123 Industrial Way', '', 'Birmingham', 'B1 1AA', 'UK', '30', 'Good customer']
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
        'headers': ['code', 'name', 'color', 'color_code', 'cost_per_kg', 'typical_ratio_percent', 'compatible_materials', 'supplier_code', 'min_stock_kg', 'notes'],
        'required': ['code', 'name', 'cost_per_kg'],
        'example': ['MB-BLK-01', 'Carbon Black Masterbatch', 'Black', 'RAL 9005', '8.50', '3', 'PP,PE,HDPE', 'CABOT-BK40', '25', 'Standard black for PP']
    },
    'moulds': {
        'name': 'Moulds',
        'filename': 'moulds_template.csv',
        'headers': ['mould_number', 'name', 'num_cavities', 'material_compatibility', 'tonnage_required', 'cycle_time_seconds', 'status', 'storage_location', 'notes'],
        'required': ['mould_number', 'num_cavities'],
        'example': ['M001', 'Widget Housing', '4', 'PP', '150', '25', 'available', 'Tool Store A', 'Single cavity prototype']
    },
    'machines': {
        'name': 'Machines',
        'filename': 'machines_template.csv',
        'headers': ['machine_code', 'name', 'manufacturer', 'model', 'tonnage', 'status', 'notes'],
        'required': ['machine_code', 'name'],
        'example': ['INJ-01', 'Borche 80T', 'Borche', 'BH-80', '80', 'idle', 'Small parts machine']
    },
    'locations': {
        'name': 'Locations',
        'filename': 'locations_template.csv',
        'headers': ['code', 'name', 'zone', 'location_type', 'max_capacity', 'notes'],
        'required': ['code', 'name', 'location_type'],
        'example': ['CON1-R01-B01', 'Container 1 Row 1 Bay 1', 'CON1', 'container', '10', 'Standard pallet location']
    },
    'items': {
        'name': 'Inventory Items (Parts)',
        'filename': 'items_template.csv',
        'headers': ['sku', 'name', 'description', 'item_type', 'customer_code', 'unit_of_measure', 'part_weight_grams', 'runner_weight_grams', 'cavities', 'cycle_time_seconds', 'material_cost_per_kg', 'mould_number', 'color', 'min_stock_level', 'unit_cost', 'selling_price', 'notes'],
        'required': ['sku', 'name'],
        'example': ['WIDGET-001', 'Widget Housing Blue', 'Injection moulded widget housing', 'finished_goods', 'CUST001', 'parts', '45.5', '12', '4', '22', '2.50', 'M001', 'Blue', '1000', '0.15', '0.35', 'Main production item']
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


def _safe_int(value, default=None):
    """Safely convert to int, returning default on failure"""
    if not value or not str(value).strip():
        return default
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return default


def _safe_float(value, default=None):
    """Safely convert to float, returning default on failure"""
    if not value or not str(value).strip():
        return default
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return default


# Column alias mappings — common alternative names for expected columns
COLUMN_ALIASES = {
    'code': 'customer_code',
    'address': 'address_line1',
    'address1': 'address_line1',
    'address2': 'address_line2',
    'special_requirements': 'notes',
}


def _normalise_row(row):
    """Apply column aliases to handle common alternative header names"""
    normalised = {}
    for key, value in row.items():
        clean_key = key.strip().lower().replace('*', '') if key else ''
        # Apply alias if it exists, otherwise use original
        mapped_key = COLUMN_ALIASES.get(clean_key, clean_key)
        # Don't overwrite if the canonical name already exists with a value
        if mapped_key not in normalised or not normalised.get(mapped_key):
            normalised[mapped_key] = value
    return normalised


def import_records(data_type, rows):
    """Import records from CSV rows"""
    result = {'created': 0, 'updated': 0, 'errors': 0, 'error_messages': []}

    for i, row in enumerate(rows, start=2):  # Start at 2 (header is row 1)
        try:
            # Normalise column names to handle common aliases
            row = _normalise_row(row)
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

    customer_code = row.get('customer_code', '').strip().upper() or None
    if not customer_code:
        raise ValueError("Customer code is required")

    # Check for existing
    existing = Customer.query.filter_by(customer_code=customer_code).first()

    if existing:
        # Update
        existing.name = name
        existing.contact_name = row.get('contact_name', '').strip() or existing.contact_name
        existing.email = row.get('email', '').strip() or existing.email
        existing.phone = row.get('phone', '').strip() or existing.phone
        existing.address_line1 = row.get('address_line1', '').strip() or existing.address_line1
        existing.address_line2 = row.get('address_line2', '').strip() or existing.address_line2
        existing.city = row.get('city', '').strip() or existing.city
        existing.postcode = row.get('postcode', '').strip() or existing.postcode
        existing.country = row.get('country', '').strip() or existing.country
        existing.credit_terms = _safe_int(row.get('credit_terms')) or existing.credit_terms
        existing.special_requirements = row.get('notes', '').strip() or existing.special_requirements
        result['updated'] += 1
    else:
        # Create
        customer = Customer(
            customer_code=customer_code,
            name=name,
            contact_name=row.get('contact_name', '').strip() or None,
            email=row.get('email', '').strip() or None,
            phone=row.get('phone', '').strip() or None,
            address_line1=row.get('address_line1', '').strip() or None,
            address_line2=row.get('address_line2', '').strip() or None,
            city=row.get('city', '').strip() or None,
            postcode=row.get('postcode', '').strip() or None,
            country=row.get('country', '').strip() or 'United Kingdom',
            credit_terms=_safe_int(row.get('credit_terms'), 30),
            special_requirements=row.get('notes', '').strip() or None
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
        existing.lead_time_days = _safe_int(row.get('lead_time_days')) or existing.lead_time_days
        existing.minimum_order_kg = _safe_float(row.get('minimum_order_kg')) or existing.minimum_order_kg
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
            lead_time_days=_safe_int(row.get('lead_time_days')),
            minimum_order_kg=_safe_float(row.get('minimum_order_kg')),
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
        existing.mfi = _safe_float(row.get('mfi')) or existing.mfi
        existing.density = _safe_float(row.get('density')) or existing.density
        existing.barrel_temp_min = _safe_int(row.get('barrel_temp_min')) or existing.barrel_temp_min
        existing.barrel_temp_max = _safe_int(row.get('barrel_temp_max')) or existing.barrel_temp_max
        existing.mould_temp_min = _safe_int(row.get('mould_temp_min')) or existing.mould_temp_min
        existing.mould_temp_max = _safe_int(row.get('mould_temp_max')) or existing.mould_temp_max
        existing.drying_required = row.get('drying_required', '').upper() == 'TRUE'
        existing.drying_temp = _safe_int(row.get('drying_temp')) or existing.drying_temp
        existing.drying_time_hours = _safe_float(row.get('drying_time_hours')) or existing.drying_time_hours
        existing.min_stock_kg = _safe_float(row.get('min_stock_kg')) or existing.min_stock_kg
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
            mfi=_safe_float(row.get('mfi')),
            density=_safe_float(row.get('density')),
            barrel_temp_min=_safe_int(row.get('barrel_temp_min')),
            barrel_temp_max=_safe_int(row.get('barrel_temp_max')),
            mould_temp_min=_safe_int(row.get('mould_temp_min')),
            mould_temp_max=_safe_int(row.get('mould_temp_max')),
            drying_required=row.get('drying_required', '').upper() == 'TRUE',
            drying_temp=_safe_int(row.get('drying_temp')),
            drying_time_hours=_safe_float(row.get('drying_time_hours')),
            min_stock_kg=_safe_float(row.get('min_stock_kg')),
            notes=row.get('notes', '').strip() or None,
            last_price_update=datetime.utcnow()
        )
        db.session.add(material)
        result['created'] += 1


def import_masterbatch(row, result):
    """Import a masterbatch record"""
    code = row.get('code', '').strip().upper()
    name = row.get('name', '').strip()
    cost = row.get('cost_per_kg', '').strip()

    if not code or not name or not cost:
        raise ValueError("Code, name, and cost_per_kg are required")

    cost_per_kg = float(cost)

    existing = Masterbatch.query.filter_by(code=code).first()

    if existing:
        existing.name = name
        existing.color = row.get('color', '').strip() or existing.color
        existing.color_code = row.get('color_code', '').strip() or existing.color_code
        existing.cost_per_kg = cost_per_kg
        existing.typical_ratio_percent = _safe_float(row.get('typical_ratio_percent')) or existing.typical_ratio_percent
        existing.compatible_materials = row.get('compatible_materials', '').strip() or existing.compatible_materials
        existing.supplier_code = row.get('supplier_code', '').strip() or existing.supplier_code
        existing.min_stock_kg = _safe_float(row.get('min_stock_kg')) or existing.min_stock_kg
        existing.notes = row.get('notes', '').strip() or existing.notes
        result['updated'] += 1
    else:
        masterbatch = Masterbatch(
            code=code,
            name=name,
            color=row.get('color', '').strip() or None,
            color_code=row.get('color_code', '').strip() or None,
            cost_per_kg=cost_per_kg,
            typical_ratio_percent=_safe_float(row.get('typical_ratio_percent'), 3),
            compatible_materials=row.get('compatible_materials', '').strip() or None,
            supplier_code=row.get('supplier_code', '').strip() or None,
            min_stock_kg=_safe_float(row.get('min_stock_kg')),
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

    existing = Mould.query.filter_by(mould_number=mould_number).first()

    if existing:
        existing.name = row.get('name', '').strip() or existing.name
        existing.num_cavities = int(num_cavities)
        existing.material_compatibility = row.get('material_compatibility', '').strip() or existing.material_compatibility
        existing.tonnage_required = _safe_int(row.get('tonnage_required')) or existing.tonnage_required
        existing.cycle_time_seconds = _safe_float(row.get('cycle_time_seconds')) or existing.cycle_time_seconds
        existing.status = row.get('status', '').strip() or existing.status
        existing.storage_location = row.get('storage_location', '').strip() or existing.storage_location
        existing.notes = row.get('notes', '').strip() or existing.notes
        result['updated'] += 1
    else:
        mould = Mould(
            mould_number=mould_number,
            name=row.get('name', '').strip() or None,
            num_cavities=int(num_cavities),
            material_compatibility=row.get('material_compatibility', '').strip() or None,
            tonnage_required=_safe_int(row.get('tonnage_required')),
            cycle_time_seconds=_safe_float(row.get('cycle_time_seconds')),
            status=row.get('status', '').strip() or 'available',
            storage_location=row.get('storage_location', '').strip() or None,
            notes=row.get('notes', '').strip() or None
        )
        db.session.add(mould)
        result['created'] += 1


def import_machine(row, result):
    """Import a machine record"""
    machine_code = row.get('machine_code', '').strip().upper()
    name = row.get('name', '').strip()

    if not machine_code or not name:
        raise ValueError("Machine code and name are required")

    existing = Machine.query.filter_by(machine_code=machine_code).first()

    if existing:
        existing.name = name
        existing.manufacturer = row.get('manufacturer', '').strip() or existing.manufacturer
        existing.model = row.get('model', '').strip() or existing.model
        existing.tonnage = _safe_int(row.get('tonnage')) or existing.tonnage
        existing.status = row.get('status', '').strip() or existing.status
        existing.notes = row.get('notes', '').strip() or existing.notes
        result['updated'] += 1
    else:
        machine = Machine(
            machine_code=machine_code,
            name=name,
            manufacturer=row.get('manufacturer', '').strip() or 'Borche',
            model=row.get('model', '').strip() or None,
            tonnage=_safe_int(row.get('tonnage')),
            status=row.get('status', '').strip() or 'idle',
            notes=row.get('notes', '').strip() or None
        )
        db.session.add(machine)
        result['created'] += 1


def import_location(row, result):
    """Import a location record"""
    code = row.get('code', '').strip().upper()
    name = row.get('name', '').strip()
    location_type = row.get('location_type', '').strip()

    if not code or not name or not location_type:
        raise ValueError("Code, name, and location_type are required")

    existing = Location.query.filter_by(code=code).first()

    if existing:
        existing.name = name
        existing.zone = row.get('zone', '').strip() or existing.zone
        existing.location_type = location_type
        existing.max_capacity = _safe_float(row.get('max_capacity')) or existing.max_capacity
        existing.description = row.get('notes', '').strip() or existing.description
        result['updated'] += 1
    else:
        location = Location(
            code=code,
            name=name,
            zone=row.get('zone', '').strip() or None,
            location_type=location_type,
            max_capacity=_safe_float(row.get('max_capacity'), 0),
            description=row.get('notes', '').strip() or None
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
        customer = Customer.query.filter_by(customer_code=customer_code).first()
        if customer:
            customer_id = customer.id

    mould_id = None
    mould_number = row.get('mould_number', '').strip().upper()
    if mould_number:
        mould = Mould.query.filter_by(mould_number=mould_number).first()
        if mould:
            mould_id = mould.id

    existing = Item.query.filter_by(sku=sku).first()

    if existing:
        existing.name = name
        existing.description = row.get('description', '').strip() or existing.description
        existing.item_type = row.get('item_type', '').strip() or existing.item_type
        existing.customer_id = customer_id or existing.customer_id
        existing.unit_of_measure = row.get('unit_of_measure', '').strip() or existing.unit_of_measure
        existing.part_weight_grams = _safe_float(row.get('part_weight_grams')) or existing.part_weight_grams
        existing.runner_weight_grams = _safe_float(row.get('runner_weight_grams')) or existing.runner_weight_grams
        existing.cavities = _safe_int(row.get('cavities')) or existing.cavities
        existing.cycle_time_seconds = _safe_float(row.get('cycle_time_seconds')) or existing.cycle_time_seconds
        existing.material_cost_per_kg = _safe_float(row.get('material_cost_per_kg')) or existing.material_cost_per_kg
        existing.default_mould_id = mould_id or existing.default_mould_id
        existing.color = row.get('color', '').strip() or existing.color
        existing.min_stock_level = _safe_float(row.get('min_stock_level')) or existing.min_stock_level
        existing.unit_cost = _safe_float(row.get('unit_cost')) or existing.unit_cost
        existing.selling_price = _safe_float(row.get('selling_price')) or existing.selling_price
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
            part_weight_grams=_safe_float(row.get('part_weight_grams')),
            runner_weight_grams=_safe_float(row.get('runner_weight_grams')),
            cavities=_safe_int(row.get('cavities'), 1),
            cycle_time_seconds=_safe_float(row.get('cycle_time_seconds')),
            material_cost_per_kg=_safe_float(row.get('material_cost_per_kg')),
            default_mould_id=mould_id,
            color=row.get('color', '').strip() or None,
            min_stock_level=_safe_float(row.get('min_stock_level'), 0),
            unit_cost=_safe_float(row.get('unit_cost'), 0),
            selling_price=_safe_float(row.get('selling_price'), 0),
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
            writer.writerow([c.customer_code, c.name, c.contact_name, c.email, c.phone, c.address_line1, c.address_line2, c.city, c.postcode, c.country, c.credit_terms, c.special_requirements])

    elif data_type == 'materials':
        for m in Material.query.order_by(Material.code).all():
            writer.writerow([m.code, m.name, m.material_type, m.grade, m.manufacturer, m.supplier_code, m.color, m.cost_per_kg, m.mfi, m.density, m.barrel_temp_min, m.barrel_temp_max, m.mould_temp_min, m.mould_temp_max, 'TRUE' if m.drying_required else 'FALSE', m.drying_temp, m.drying_time_hours, m.min_stock_kg, m.notes])

    elif data_type == 'suppliers':
        for s in MaterialSupplier.query.order_by(MaterialSupplier.name).all():
            writer.writerow([s.code, s.name, s.contact_name, s.email, s.phone, s.website, s.address_line1, s.address_line2, s.city, s.postcode, s.country, s.account_number, s.payment_terms, s.lead_time_days, s.minimum_order_kg, s.notes])

    elif data_type == 'masterbatches':
        for mb in Masterbatch.query.order_by(Masterbatch.code).all():
            writer.writerow([mb.code, mb.name, mb.color, mb.color_code, mb.cost_per_kg, mb.typical_ratio_percent, mb.compatible_materials, mb.supplier_code, mb.min_stock_kg, mb.notes])

    elif data_type == 'moulds':
        for m in Mould.query.order_by(Mould.mould_number).all():
            writer.writerow([m.mould_number, m.name, m.num_cavities, m.material_compatibility, m.tonnage_required, m.cycle_time_seconds, m.status, m.storage_location, m.notes])

    elif data_type == 'machines':
        for m in Machine.query.order_by(Machine.machine_code).all():
            writer.writerow([m.machine_code, m.name, m.manufacturer, m.model, m.tonnage, m.status, m.notes])

    elif data_type == 'locations':
        for l in Location.query.order_by(Location.code).all():
            writer.writerow([l.code, l.name, l.zone, l.location_type, l.max_capacity, l.description])

    elif data_type == 'items':
        for i in Item.query.filter_by(is_active=True).order_by(Item.sku).all():
            customer_code = i.customer.customer_code if i.customer else ''
            mould_number = i.default_mould.mould_number if i.default_mould else ''
            writer.writerow([i.sku, i.name, i.description, i.item_type, customer_code, i.unit_of_measure, i.part_weight_grams, i.runner_weight_grams, i.cavities, i.cycle_time_seconds, i.material_cost_per_kg, mould_number, i.color, i.min_stock_level, i.unit_cost, i.selling_price, i.notes])

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
                    writer.writerow([c.customer_code, c.name, c.contact_name, c.email, c.phone, c.address_line1, c.address_line2, c.city, c.postcode, c.country, c.credit_terms, c.special_requirements])

            elif data_type == 'materials':
                for m in Material.query.order_by(Material.code).all():
                    writer.writerow([m.code, m.name, m.material_type, m.grade, m.manufacturer, m.supplier_code, m.color, m.cost_per_kg, m.mfi, m.density, m.barrel_temp_min, m.barrel_temp_max, m.mould_temp_min, m.mould_temp_max, 'TRUE' if m.drying_required else 'FALSE', m.drying_temp, m.drying_time_hours, m.min_stock_kg, m.notes])

            elif data_type == 'suppliers':
                for s in MaterialSupplier.query.order_by(MaterialSupplier.name).all():
                    writer.writerow([s.code, s.name, s.contact_name, s.email, s.phone, s.website, s.address_line1, s.address_line2, s.city, s.postcode, s.country, s.account_number, s.payment_terms, s.lead_time_days, s.minimum_order_kg, s.notes])

            elif data_type == 'masterbatches':
                for mb in Masterbatch.query.order_by(Masterbatch.code).all():
                    writer.writerow([mb.code, mb.name, mb.color, mb.color_code, mb.cost_per_kg, mb.typical_ratio_percent, mb.compatible_materials, mb.supplier_code, mb.min_stock_kg, mb.notes])

            elif data_type == 'moulds':
                for m in Mould.query.order_by(Mould.mould_number).all():
                    writer.writerow([m.mould_number, m.name, m.num_cavities, m.material_compatibility, m.tonnage_required, m.cycle_time_seconds, m.status, m.storage_location, m.notes])

            elif data_type == 'machines':
                for m in Machine.query.order_by(Machine.machine_code).all():
                    writer.writerow([m.machine_code, m.name, m.manufacturer, m.model, m.tonnage, m.status, m.notes])

            elif data_type == 'locations':
                for l in Location.query.order_by(Location.code).all():
                    writer.writerow([l.code, l.name, l.zone, l.location_type, l.max_capacity, l.description])

            elif data_type == 'items':
                for i in Item.query.filter_by(is_active=True).order_by(Item.sku).all():
                    customer_code = i.customer.customer_code if i.customer else ''
                    mould_number = i.default_mould.mould_number if i.default_mould else ''
                    writer.writerow([i.sku, i.name, i.description, i.item_type, customer_code, i.unit_of_measure, i.part_weight_grams, i.runner_weight_grams, i.cavities, i.cycle_time_seconds, i.material_cost_per_kg, mould_number, i.color, i.min_stock_level, i.unit_cost, i.selling_price, i.notes])

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
