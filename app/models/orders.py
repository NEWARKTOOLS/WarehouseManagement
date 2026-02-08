from datetime import datetime
from app import db


class Customer(db.Model):
    """Customer model"""
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    customer_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    contact_name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))

    # Address
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    county = db.Column(db.String(100))
    postcode = db.Column(db.String(20))
    country = db.Column(db.String(100), default='United Kingdom')

    # Billing address (if different)
    billing_address_line1 = db.Column(db.String(200))
    billing_address_line2 = db.Column(db.String(200))
    billing_city = db.Column(db.String(100))
    billing_county = db.Column(db.String(100))
    billing_postcode = db.Column(db.String(20))
    billing_country = db.Column(db.String(100))

    # Business info
    credit_terms = db.Column(db.Integer, default=30)  # Days
    credit_limit = db.Column(db.Float)
    tax_number = db.Column(db.String(50))  # VAT number
    special_requirements = db.Column(db.Text)

    # Logo (stored as filename in static/img/customers/)
    logo_filename = db.Column(db.String(200))

    # Flags
    is_jit = db.Column(db.Boolean, default=False)  # Just-in-time customer
    is_active = db.Column(db.Boolean, default=True)

    # Xero integration
    xero_contact_id = db.Column(db.String(100))

    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    orders = db.relationship('SalesOrder', backref='customer', lazy='dynamic')

    def __repr__(self):
        return f'<Customer {self.customer_code}: {self.name}>'

    @property
    def full_address(self):
        """Return formatted address"""
        parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.county,
            self.postcode,
            self.country
        ]
        return '\n'.join(p for p in parts if p)

    @staticmethod
    def generate_customer_code():
        """Generate unique customer code"""
        count = Customer.query.count()
        return f'CUST{str(count + 1).zfill(5)}'


class SalesOrder(db.Model):
    """Sales order model"""
    __tablename__ = 'sales_orders'

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)

    # Order info
    order_date = db.Column(db.Date, default=datetime.utcnow)
    required_date = db.Column(db.Date)
    customer_po = db.Column(db.String(100))  # Customer's PO number

    # Delivery info
    delivery_method = db.Column(db.String(50))  # own_van, haulage, collection, postal
    delivery_address_line1 = db.Column(db.String(200))
    delivery_address_line2 = db.Column(db.String(200))
    delivery_city = db.Column(db.String(100))
    delivery_county = db.Column(db.String(100))
    delivery_postcode = db.Column(db.String(20))
    delivery_country = db.Column(db.String(100))
    delivery_instructions = db.Column(db.Text)

    # Status tracking
    status = db.Column(db.String(30), default='new')  # new, in_production, ready_to_ship, dispatched, delivered, cancelled

    # Financials
    subtotal = db.Column(db.Float, default=0)
    shipping_cost = db.Column(db.Float, default=0)  # Delivery/shipping charge
    tax_rate = db.Column(db.Float, default=20)  # VAT %
    tax_amount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)

    # Notes
    notes = db.Column(db.Text)
    internal_notes = db.Column(db.Text)

    # Xero integration
    xero_invoice_id = db.Column(db.String(100))

    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lines = db.relationship('SalesOrderLine', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    deliveries = db.relationship('Delivery', backref='order', lazy='dynamic')
    production_orders = db.relationship('ProductionOrder', backref='sales_order', lazy='dynamic')

    def __repr__(self):
        return f'<SalesOrder {self.order_number}>'

    def calculate_totals(self):
        """Calculate order totals from line items"""
        self.subtotal = sum((line.line_total or 0) for line in self.lines.all())
        shipping = self.shipping_cost or 0
        tax_rate = self.tax_rate or 0
        self.tax_amount = (self.subtotal + shipping) * (tax_rate / 100)
        self.total = self.subtotal + shipping + self.tax_amount

    @property
    def delivery_address(self):
        """Return formatted delivery address"""
        parts = [
            self.delivery_address_line1,
            self.delivery_address_line2,
            self.delivery_city,
            self.delivery_county,
            self.delivery_postcode,
            self.delivery_country
        ]
        return '\n'.join(p for p in parts if p)

    @staticmethod
    def generate_order_number():
        """Generate unique order number"""
        today = datetime.now().strftime('%y%m%d')
        count = SalesOrder.query.filter(
            SalesOrder.order_number.like(f'SO-{today}%')
        ).count()
        return f'SO-{today}-{str(count + 1).zfill(4)}'


class SalesOrderLine(db.Model):
    """Sales order line item"""
    __tablename__ = 'sales_order_lines'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=True)  # Nullable for custom items
    line_number = db.Column(db.Integer, default=1)

    # Custom item fields (used when item_id is NULL)
    custom_sku = db.Column(db.String(100))
    custom_description = db.Column(db.String(500))
    is_custom_item = db.Column(db.Boolean, default=False)

    # Quantities
    quantity_ordered = db.Column(db.Float, nullable=False)
    quantity_allocated = db.Column(db.Float, default=0)
    quantity_shipped = db.Column(db.Float, default=0)

    # Pricing
    unit_price = db.Column(db.Float, default=0)
    discount_percent = db.Column(db.Float, default=0)
    line_total = db.Column(db.Float, default=0)

    # Notes
    notes = db.Column(db.Text)

    # Relationships
    item = db.relationship('Item', backref='order_lines')

    def __repr__(self):
        return f'<SalesOrderLine {self.order_id}-{self.line_number}>'

    def calculate_line_total(self):
        """Calculate line total with discount"""
        qty = self.quantity_ordered or 0
        price = self.unit_price or 0
        discount_pct = self.discount_percent or 0
        gross = qty * price
        discount = gross * (discount_pct / 100)
        self.line_total = gross - discount

    @property
    def quantity_remaining(self):
        """Calculate quantity still to ship"""
        return self.quantity_ordered - self.quantity_shipped


class Delivery(db.Model):
    """Delivery/shipment model"""
    __tablename__ = 'deliveries'

    id = db.Column(db.Integer, primary_key=True)
    delivery_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'), nullable=False)

    # Delivery info
    delivery_method = db.Column(db.String(50))  # own_van, haulage, collection, postal
    carrier = db.Column(db.String(100))
    tracking_number = db.Column(db.String(100))
    driver = db.Column(db.String(100))

    # Dates
    dispatch_date = db.Column(db.DateTime)
    delivery_date = db.Column(db.DateTime)

    # Status
    status = db.Column(db.String(30), default='pending')  # pending, dispatched, delivered

    # Package info
    num_packages = db.Column(db.Integer, default=1)
    total_weight = db.Column(db.Float)

    # Notes
    notes = db.Column(db.Text)

    # Documentation
    packing_list_generated = db.Column(db.Boolean, default=False)
    signed_delivery_note = db.Column(db.String(255))  # Uploaded signed delivery note filename

    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Delivery {self.delivery_number}>'

    @staticmethod
    def generate_delivery_number():
        """Generate unique delivery number"""
        today = datetime.now().strftime('%y%m%d')
        count = Delivery.query.filter(
            Delivery.delivery_number.like(f'DEL-{today}%')
        ).count()
        return f'DEL-{today}-{str(count + 1).zfill(4)}'
