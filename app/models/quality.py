from datetime import datetime
from app import db


class Batch(db.Model):
    """Batch/lot tracking for traceability"""
    __tablename__ = 'batches'

    id = db.Column(db.Integer, primary_key=True)
    batch_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    production_order_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'))

    # Production info
    production_date = db.Column(db.Date, default=datetime.utcnow)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'))
    mould_id = db.Column(db.Integer, db.ForeignKey('moulds.id'))
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Material traceability
    material_batch_number = db.Column(db.String(100))  # Raw material batch used

    # Quantities
    quantity_produced = db.Column(db.Float, default=0)
    quantity_good = db.Column(db.Float, default=0)
    quantity_rejected = db.Column(db.Float, default=0)
    quantity_remaining = db.Column(db.Float, default=0)

    # Quality status
    quality_status = db.Column(db.String(30), default='pending')  # pending, passed, hold, rejected

    # Location
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))

    # Expiry (if applicable)
    expiry_date = db.Column(db.Date)

    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    item = db.relationship('Item', backref='batches')
    machine = db.relationship('Machine', backref='batches')
    mould = db.relationship('Mould', backref='batches')
    operator = db.relationship('User', backref='batches')
    location = db.relationship('Location', backref='batches')
    quality_checks = db.relationship('QualityCheck', backref='batch', lazy='dynamic')

    def __repr__(self):
        return f'<Batch {self.batch_number}>'

    @staticmethod
    def generate_batch_number(sku):
        """Generate unique batch number: YYMMDD-SKU-SEQ"""
        today = datetime.now().strftime('%y%m%d')
        prefix = f'{today}-{sku}'
        count = Batch.query.filter(
            Batch.batch_number.like(f'{prefix}%')
        ).count()
        return f'{prefix}-{str(count + 1).zfill(3)}'


class QualityCheck(db.Model):
    """Quality inspection record"""
    __tablename__ = 'quality_checks'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'))
    production_order_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'))

    # Check type
    check_type = db.Column(db.String(50), nullable=False)  # first_article, in_process, final
    check_name = db.Column(db.String(100))

    # Results
    result = db.Column(db.String(20))  # pass, fail, conditional
    measurements = db.Column(db.Text)  # JSON string of measurements
    notes = db.Column(db.Text)

    # Inspector
    inspector_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Images
    image_filename = db.Column(db.String(255))

    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    inspector = db.relationship('User', backref='quality_checks')
    production_order = db.relationship('ProductionOrder', backref='quality_checks')

    def __repr__(self):
        return f'<QualityCheck {self.check_type}: {self.result}>'


class NonConformance(db.Model):
    """Non-conformance report (NCR)"""
    __tablename__ = 'non_conformances'

    id = db.Column(db.Integer, primary_key=True)
    ncr_number = db.Column(db.String(50), unique=True, nullable=False, index=True)

    # Related records
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    production_order_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'))
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'))

    # Issue details
    issue_type = db.Column(db.String(50))  # visual_defect, dimensional, contamination, etc.
    description = db.Column(db.Text, nullable=False)
    quantity_affected = db.Column(db.Float)

    # Root cause analysis
    root_cause = db.Column(db.Text)
    corrective_action = db.Column(db.Text)

    # Disposition
    disposition = db.Column(db.String(30))  # rework, scrap, credit, use_as_is

    # Status
    status = db.Column(db.String(30), default='open')  # open, investigating, resolved, closed

    # Reporter
    reported_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Images
    image_filename = db.Column(db.String(255))

    # Customer return info (if applicable)
    is_customer_return = db.Column(db.Boolean, default=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    return_reason = db.Column(db.Text)

    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    batch = db.relationship('Batch', backref='non_conformances')
    item = db.relationship('Item', backref='non_conformances')
    production_order = db.relationship('ProductionOrder', backref='non_conformances')
    sales_order = db.relationship('SalesOrder', backref='non_conformances')
    reported_by = db.relationship('User', backref='reported_ncrs')
    customer = db.relationship('Customer', backref='non_conformances')

    def __repr__(self):
        return f'<NonConformance {self.ncr_number}>'

    @staticmethod
    def generate_ncr_number():
        """Generate unique NCR number"""
        today = datetime.now().strftime('%y%m%d')
        count = NonConformance.query.filter(
            NonConformance.ncr_number.like(f'NCR-{today}%')
        ).count()
        return f'NCR-{today}-{str(count + 1).zfill(4)}'
