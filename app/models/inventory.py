from datetime import datetime
from app import db


class Category(db.Model):
    """Product category model"""
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    category_type = db.Column(db.String(50))  # raw_material, masterbatch, finished_goods, regrind

    # Relationships
    items = db.relationship('Item', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'


class Item(db.Model):
    """Inventory item model"""
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    # Classification
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))  # Link to customer for customer-specific parts
    item_type = db.Column(db.String(50))  # raw_material, masterbatch, finished_goods, regrind

    # Physical properties
    unit_of_measure = db.Column(db.String(20), default='parts')  # parts, kg, box, pallet
    weight_kg = db.Column(db.Float)
    length_mm = db.Column(db.Float)
    width_mm = db.Column(db.Float)
    height_mm = db.Column(db.Float)
    color = db.Column(db.String(50))

    # Storage info
    default_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    default_mould_id = db.Column(db.Integer, db.ForeignKey('moulds.id'))  # Default mould for production
    min_stock_level = db.Column(db.Float, default=0)
    max_stock_level = db.Column(db.Float)
    reorder_point = db.Column(db.Float)
    reorder_quantity = db.Column(db.Float)

    # Material specs (for raw materials)
    material_grade = db.Column(db.String(100))
    supplier = db.Column(db.String(200))

    # Production info
    cycle_time_seconds = db.Column(db.Float)
    parts_per_cycle = db.Column(db.Integer, default=1)

    # Part weights (for costing)
    part_weight_grams = db.Column(db.Float)  # Weight of finished part
    runner_weight_grams = db.Column(db.Float)  # Runner/sprue weight (if any)
    shot_weight_grams = db.Column(db.Float)  # Total shot weight
    cavities = db.Column(db.Integer, default=1)  # Number of cavities
    ideal_cycle_time = db.Column(db.Float)  # Target cycle time in seconds
    setup_time_hours = db.Column(db.Float, default=2)  # Typical setup/changeover time

    # Material info (for costing)
    material_type = db.Column(db.String(50))  # PP, ABS, PA6, PA66, POM, PC, HDPE, PET
    material_id = db.Column(db.Integer, db.ForeignKey('items.id'))  # Link to raw material item
    masterbatch_id = db.Column(db.Integer, db.ForeignKey('items.id'))  # Link to masterbatch item
    masterbatch_ratio = db.Column(db.String(20))  # e.g. "3%"
    regrind_percent = db.Column(db.Float, default=0)  # Percentage of regrind used
    material_cost_per_kg = db.Column(db.Float)  # Cost per kg for costing

    # Costing defaults
    target_machine_rate = db.Column(db.Float)  # Target machine rate per hour
    target_margin_percent = db.Column(db.Float, default=30)  # Target profit margin

    # Pricing
    unit_cost = db.Column(db.Float, default=0)
    selling_price = db.Column(db.Float, default=0)

    # Images and files
    image_filename = db.Column(db.String(255))

    # Barcode
    barcode = db.Column(db.String(100), unique=True, index=True)
    barcode_image = db.Column(db.String(255))

    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    default_location = db.relationship('Location', foreign_keys=[default_location_id])
    default_mould = db.relationship('Mould', foreign_keys=[default_mould_id], backref='default_items')
    customer = db.relationship('Customer', backref='items')
    stock_levels = db.relationship('StockLevel', backref='item', lazy='dynamic')
    stock_movements = db.relationship('StockMovement', backref='item', lazy='dynamic')
    production_orders = db.relationship('ProductionOrder', backref='item', lazy='dynamic')
    material = db.relationship('Item', foreign_keys=[material_id], remote_side=[id], backref='parts_using_material')
    masterbatch = db.relationship('Item', foreign_keys=[masterbatch_id], remote_side=[id], backref='parts_using_masterbatch')

    def __repr__(self):
        return f'<Item {self.sku}: {self.name}>'

    @property
    def total_stock(self):
        """Calculate total stock across all locations"""
        return sum(sl.quantity for sl in self.stock_levels.all())

    @property
    def available_stock(self):
        """Calculate available stock (total - allocated)"""
        return sum(sl.available_quantity for sl in self.stock_levels.all())

    @property
    def is_low_stock(self):
        """Check if item is below reorder point or min stock level.
        Only flags items that have explicit reorder_point or min_stock_level > 0 set."""
        if self.reorder_point and self.reorder_point > 0:
            return self.total_stock <= self.reorder_point
        if self.min_stock_level and self.min_stock_level > 0:
            return self.total_stock <= self.min_stock_level
        # No tracking set - don't flag as low stock
        return False

    def get_stock_at_location(self, location_id):
        """Get stock level at specific location"""
        sl = self.stock_levels.filter_by(location_id=location_id).first()
        return sl.quantity if sl else 0

    @property
    def calculated_material_cost_per_part(self):
        """Calculate material cost per part based on weights and material cost"""
        if not self.part_weight_grams or not self.material_cost_per_kg:
            return None
        # Total weight per part including runner share
        runner_share = (self.runner_weight_grams or 0) / (self.cavities or 1)
        total_weight_g = self.part_weight_grams + runner_share
        # Convert to kg and multiply by cost
        return (total_weight_g / 1000) * self.material_cost_per_kg

    @property
    def calculated_cycle_cost_per_part(self):
        """Calculate machine/labour cost per part based on cycle time"""
        cycle_time = self.ideal_cycle_time or self.cycle_time_seconds
        if not cycle_time or not self.target_machine_rate:
            return None
        # Cost per hour / parts per hour
        parts_per_hour = (3600 / cycle_time) * (self.cavities or 1)
        return self.target_machine_rate / parts_per_hour if parts_per_hour > 0 else None

    @property
    def calculated_total_cost_per_part(self):
        """Calculate total cost per part"""
        material = self.calculated_material_cost_per_part or 0
        cycle = self.calculated_cycle_cost_per_part or 0
        return material + cycle if (material or cycle) else None

    @property
    def calculated_selling_price(self):
        """Calculate suggested selling price based on cost and margin"""
        cost = self.calculated_total_cost_per_part
        if not cost:
            return None
        margin = self.target_margin_percent or 30
        return cost / (1 - margin / 100) if margin < 100 else cost * 2


class StockLevel(db.Model):
    """Stock level by location"""
    __tablename__ = 'stock_levels'

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    quantity = db.Column(db.Float, default=0)
    allocated_quantity = db.Column(db.Float, default=0)  # Reserved for orders
    batch_number = db.Column(db.String(50))
    last_count_date = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint for item-location combination
    __table_args__ = (
        db.UniqueConstraint('item_id', 'location_id', name='unique_item_location'),
    )

    def __repr__(self):
        return f'<StockLevel {self.item_id}@{self.location_id}: {self.quantity}>'

    @property
    def available_quantity(self):
        """Calculate available quantity (not allocated)"""
        return max(0, self.quantity - self.allocated_quantity)


class StockMovement(db.Model):
    """Stock movement history"""
    __tablename__ = 'stock_movements'

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    movement_type = db.Column(db.String(30), nullable=False)  # receipt, movement, adjustment, production, shipment
    quantity = db.Column(db.Float, nullable=False)

    # Location info
    from_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    to_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))

    # Additional info
    reference = db.Column(db.String(100))  # PO number, order number, etc.
    batch_number = db.Column(db.String(50))
    reason = db.Column(db.String(200))
    notes = db.Column(db.Text)

    # Tracking
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    from_location = db.relationship('Location', foreign_keys=[from_location_id])
    to_location = db.relationship('Location', foreign_keys=[to_location_id])

    def __repr__(self):
        return f'<StockMovement {self.movement_type}: {self.quantity} of item {self.item_id}>'
