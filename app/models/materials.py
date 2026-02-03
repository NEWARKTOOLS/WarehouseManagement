"""
Materials Management Models
Manage raw materials, suppliers, grades, and pricing
"""
from datetime import datetime, date
from app import db


class MaterialSupplier(db.Model):
    """Material supplier/vendor"""
    __tablename__ = 'material_suppliers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), unique=True)

    # Contact info
    contact_name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    website = db.Column(db.String(200))

    # Address
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    postcode = db.Column(db.String(20))
    country = db.Column(db.String(100), default='UK')

    # Account info
    account_number = db.Column(db.String(50))
    payment_terms = db.Column(db.String(100))  # e.g. "Net 30"
    lead_time_days = db.Column(db.Integer)  # Typical lead time
    minimum_order_kg = db.Column(db.Float)

    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    materials = db.relationship('Material', backref='supplier', lazy='dynamic')

    def __repr__(self):
        return f'<MaterialSupplier {self.name}>'


class Material(db.Model):
    """Raw material with supplier, grade, and pricing"""
    __tablename__ = 'materials'

    id = db.Column(db.Integer, primary_key=True)

    # Basic info
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Internal code

    # Material type
    material_type = db.Column(db.String(50), nullable=False)  # PP, ABS, PA6, etc
    grade = db.Column(db.String(100))  # Supplier's grade name
    manufacturer = db.Column(db.String(100))  # e.g. SABIC, BASF, etc

    # Supplier
    supplier_id = db.Column(db.Integer, db.ForeignKey('material_suppliers.id'))
    supplier_code = db.Column(db.String(100))  # Supplier's product code

    # Physical properties
    mfi = db.Column(db.Float)  # Melt Flow Index
    density = db.Column(db.Float)  # g/cm³
    color = db.Column(db.String(50))  # Natural, Black, etc

    # Pricing
    cost_per_kg = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='GBP')
    last_price_update = db.Column(db.Date)

    # Stock tracking (optional - can also use Item)
    current_stock_kg = db.Column(db.Float, default=0)
    min_stock_kg = db.Column(db.Float)
    reorder_qty_kg = db.Column(db.Float)

    # Linked inventory item (if tracking in main inventory)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))

    # Processing info
    barrel_temp_min = db.Column(db.Integer)  # Min barrel temp °C
    barrel_temp_max = db.Column(db.Integer)  # Max barrel temp °C
    mould_temp_min = db.Column(db.Integer)
    mould_temp_max = db.Column(db.Integer)
    drying_required = db.Column(db.Boolean, default=False)
    drying_temp = db.Column(db.Integer)  # °C
    drying_time_hours = db.Column(db.Float)

    # Technical datasheet
    datasheet_filename = db.Column(db.String(255))

    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    item = db.relationship('Item', backref='linked_material', foreign_keys=[item_id])
    price_history = db.relationship('MaterialPriceHistory', backref='material', lazy='dynamic', order_by='MaterialPriceHistory.effective_date.desc()')

    def __repr__(self):
        return f'<Material {self.code}: {self.name}>'

    @property
    def full_name(self):
        """Full descriptive name"""
        parts = [self.material_type]
        if self.grade:
            parts.append(self.grade)
        if self.color and self.color != 'Natural':
            parts.append(self.color)
        return ' '.join(parts)

    @property
    def display_name(self):
        """Display name for dropdowns"""
        return f"{self.code} - {self.material_type} {self.grade or ''} ({self.supplier.name if self.supplier else 'No supplier'})"


class MaterialPriceHistory(db.Model):
    """Track material price changes over time"""
    __tablename__ = 'material_price_history'

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('materials.id'), nullable=False)

    cost_per_kg = db.Column(db.Float, nullable=False)
    effective_date = db.Column(db.Date, nullable=False, default=date.today)

    reason = db.Column(db.String(200))  # e.g. "Supplier price increase", "New contract"
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))

    def __repr__(self):
        return f'<MaterialPriceHistory {self.material_id}: £{self.cost_per_kg}/kg from {self.effective_date}>'


class Masterbatch(db.Model):
    """Masterbatch/colorant for injection moulding"""
    __tablename__ = 'masterbatches'

    id = db.Column(db.Integer, primary_key=True)

    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    color = db.Column(db.String(50))
    color_code = db.Column(db.String(20))  # RAL, Pantone, etc

    # Supplier
    supplier_id = db.Column(db.Integer, db.ForeignKey('material_suppliers.id'))
    supplier_code = db.Column(db.String(100))

    # Compatibility
    compatible_materials = db.Column(db.String(200))  # e.g. "PP, PE, ABS"

    # Usage
    typical_ratio_percent = db.Column(db.Float, default=3)  # Typical loading %
    min_ratio_percent = db.Column(db.Float)
    max_ratio_percent = db.Column(db.Float)

    # Pricing
    cost_per_kg = db.Column(db.Float)

    # Stock
    current_stock_kg = db.Column(db.Float, default=0)
    min_stock_kg = db.Column(db.Float)

    # Linked inventory item
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))

    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    supplier = db.relationship('MaterialSupplier', backref='masterbatches')
    item = db.relationship('Item', backref='linked_masterbatch', foreign_keys=[item_id])

    def __repr__(self):
        return f'<Masterbatch {self.code}: {self.name}>'
