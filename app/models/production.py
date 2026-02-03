from datetime import datetime
from app import db


class Machine(db.Model):
    """Injection moulding machine model"""
    __tablename__ = 'machines'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    machine_code = db.Column(db.String(20), unique=True, nullable=False)
    tonnage = db.Column(db.Integer)  # 80T-500T
    manufacturer = db.Column(db.String(100), default='Borche')
    model = db.Column(db.String(100))

    # Factory layout position (for future 2D view)
    display_order = db.Column(db.Integer, default=0)  # Order in lists
    position_x = db.Column(db.Integer)  # For 2D factory view
    position_y = db.Column(db.Integer)  # For 2D factory view

    # Status
    status = db.Column(db.String(30), default='idle')  # running, idle, maintenance, offline
    current_mould_id = db.Column(db.Integer, db.ForeignKey('moulds.id'))

    # Tracking
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    production_orders = db.relationship('ProductionOrder', backref='machine', lazy='dynamic')
    production_logs = db.relationship('ProductionLog', backref='machine', lazy='dynamic')

    def __repr__(self):
        return f'<Machine {self.name} ({self.tonnage}T)>'


class Mould(db.Model):
    """Mould/tool model"""
    __tablename__ = 'moulds'

    id = db.Column(db.Integer, primary_key=True)
    mould_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200))
    description = db.Column(db.Text)

    # Type
    mould_type = db.Column(db.String(30), default='individual')  # individual, family
    bolster_number = db.Column(db.String(50))  # For family moulds

    # Technical specs
    tonnage_required = db.Column(db.Integer)
    num_cavities = db.Column(db.Integer, default=1)
    cycle_time_seconds = db.Column(db.Float)
    material_compatibility = db.Column(db.String(200))  # PP, ABS, etc.

    # Storage
    storage_location = db.Column(db.String(100))

    # Status
    status = db.Column(db.String(30), default='available')  # available, in_use, maintenance, awaiting_repair
    current_machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'))

    # Maintenance tracking
    last_maintenance_date = db.Column(db.Date)
    next_maintenance_date = db.Column(db.Date)
    maintenance_interval_months = db.Column(db.Integer, default=12)
    total_shots = db.Column(db.Integer, default=0)

    # Images
    image_filename = db.Column(db.String(255))

    # Tracking
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    current_machine = db.relationship('Machine', foreign_keys=[current_machine_id], backref='current_mould')
    setup_sheets = db.relationship('SetupSheet', backref='mould', lazy='dynamic')
    production_orders = db.relationship('ProductionOrder', backref='mould', lazy='dynamic')
    maintenance_logs = db.relationship('MouldMaintenance', backref='mould', lazy='dynamic')

    def __repr__(self):
        return f'<Mould {self.mould_number}>'

    @property
    def is_maintenance_due(self):
        """Check if maintenance is overdue"""
        if self.next_maintenance_date:
            return datetime.now().date() >= self.next_maintenance_date
        return False


class MouldMaintenance(db.Model):
    """Mould maintenance log"""
    __tablename__ = 'mould_maintenance'

    id = db.Column(db.Integer, primary_key=True)
    mould_id = db.Column(db.Integer, db.ForeignKey('moulds.id'), nullable=False)
    maintenance_type = db.Column(db.String(50), nullable=False)  # pm, repair, modification
    description = db.Column(db.Text)
    work_performed = db.Column(db.Text)
    technician = db.Column(db.String(100))
    shots_at_maintenance = db.Column(db.Integer)
    cost = db.Column(db.Float)
    image_filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<MouldMaintenance {self.mould_id}: {self.maintenance_type}>'


class SetupSheet(db.Model):
    """Digital setup sheet for product-mould combinations"""
    __tablename__ = 'setup_sheets'

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    mould_id = db.Column(db.Integer, db.ForeignKey('moulds.id'), nullable=False)

    # Machine settings
    program_number = db.Column(db.String(50))
    barrel_temp_zone1 = db.Column(db.Float)
    barrel_temp_zone2 = db.Column(db.Float)
    barrel_temp_zone3 = db.Column(db.Float)
    barrel_temp_zone4 = db.Column(db.Float)
    mould_temp = db.Column(db.Float)
    nozzle_temp = db.Column(db.Float)

    # Injection parameters
    injection_pressure = db.Column(db.Float)
    injection_speed = db.Column(db.Float)
    injection_time = db.Column(db.Float)
    holding_pressure = db.Column(db.Float)
    holding_time = db.Column(db.Float)
    cooling_time = db.Column(db.Float)
    cycle_time = db.Column(db.Float)

    # Material
    material_type = db.Column(db.String(100))
    material_grade = db.Column(db.String(100))
    color = db.Column(db.String(50))
    masterbatch_ratio = db.Column(db.String(50))

    # Quality checkpoints
    quality_checks = db.Column(db.Text)  # JSON string of quality checkpoints

    # Notes and images
    notes = db.Column(db.Text)
    special_instructions = db.Column(db.Text)
    image_filename = db.Column(db.String(255))
    setup_sheet_pdf = db.Column(db.String(255))  # PDF file upload

    # Version control
    version = db.Column(db.Integer, default=1)
    is_current = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    item = db.relationship('Item', backref='setup_sheets')

    def __repr__(self):
        return f'<SetupSheet Item:{self.item_id} Mould:{self.mould_id}>'


class ProductionOrder(db.Model):
    """Production order model"""
    __tablename__ = 'production_orders'

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    mould_id = db.Column(db.Integer, db.ForeignKey('moulds.id'))
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'))

    # Order details
    order_type = db.Column(db.String(30), default='make_to_stock')  # make_to_stock, make_to_order
    quantity_required = db.Column(db.Float, nullable=False)
    quantity_produced = db.Column(db.Float, default=0)
    quantity_good = db.Column(db.Float, default=0)
    quantity_rejected = db.Column(db.Float, default=0)

    # Linked sales order and customer (if make_to_order)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))

    # Scheduling
    priority = db.Column(db.Integer, default=5)  # 1=highest, 10=lowest
    due_date = db.Column(db.Date)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)

    # Status
    status = db.Column(db.String(30), default='planned')  # planned, in_progress, completed, cancelled

    # Notes
    notes = db.Column(db.Text)

    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    production_logs = db.relationship('ProductionLog', backref='production_order', lazy='dynamic')
    batches = db.relationship('Batch', backref='production_order', lazy='dynamic')
    # Note: sales_order relationship defined in SalesOrder model (backref='sales_order')
    customer = db.relationship('Customer', backref='production_orders')

    def __repr__(self):
        return f'<ProductionOrder {self.order_number}>'

    @property
    def completion_percentage(self):
        """Calculate completion percentage"""
        if self.quantity_required <= 0:
            return 0
        return min(100, (self.quantity_produced / self.quantity_required) * 100)

    @staticmethod
    def generate_order_number():
        """Generate unique order number"""
        today = datetime.now().strftime('%y%m%d')
        count = ProductionOrder.query.filter(
            ProductionOrder.order_number.like(f'PO-{today}%')
        ).count()
        return f'PO-{today}-{str(count + 1).zfill(4)}'


class ScheduledJob(db.Model):
    """Scheduled production job for a machine on a specific date"""
    __tablename__ = 'scheduled_jobs'

    id = db.Column(db.Integer, primary_key=True)
    production_order_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'), nullable=False)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)

    # Scheduling
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    sequence_order = db.Column(db.Integer, default=1)  # Order in the day's queue

    # Time estimates
    estimated_start_time = db.Column(db.Time)
    estimated_duration_hours = db.Column(db.Float)  # Based on cycle time x quantity

    # Status
    status = db.Column(db.String(30), default='scheduled')  # scheduled, in_progress, completed, skipped

    # Completion tracking
    actual_start_time = db.Column(db.DateTime)
    actual_end_time = db.Column(db.DateTime)
    completed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # What happens to the parts after completion
    output_destination = db.Column(db.String(50))  # location_id, awaiting_sorting, awaiting_degating, awaiting_assembly

    # Notes
    notes = db.Column(db.Text)

    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    production_order = db.relationship('ProductionOrder', backref='scheduled_jobs')
    machine = db.relationship('Machine', backref='scheduled_jobs')
    completed_by = db.relationship('User', backref='completed_jobs')

    def __repr__(self):
        return f'<ScheduledJob {self.id} on {self.machine.name if self.machine else "?"} for {self.scheduled_date}>'

    @property
    def is_urgent(self):
        """Check if job is urgent (due within 2 days)"""
        if self.production_order and self.production_order.due_date:
            days_until_due = (self.production_order.due_date - datetime.now().date()).days
            return days_until_due <= 2
        return False

    @property
    def is_warning(self):
        """Check if job needs attention (due within 5 days)"""
        if self.production_order and self.production_order.due_date:
            days_until_due = (self.production_order.due_date - datetime.now().date()).days
            return 2 < days_until_due <= 5
        return False

    @property
    def urgency_class(self):
        """Return CSS class based on urgency"""
        if self.is_urgent:
            return 'danger'
        elif self.is_warning:
            return 'warning'
        return 'primary'


class AwaitingSorting(db.Model):
    """Items awaiting sorting/counting after production"""
    __tablename__ = 'awaiting_sorting'

    id = db.Column(db.Integer, primary_key=True)
    production_order_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'), nullable=False)
    scheduled_job_id = db.Column(db.Integer, db.ForeignKey('scheduled_jobs.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)

    # Sorting type
    sorting_type = db.Column(db.String(50), default='counting')  # counting, degating, assembly, quality_check

    # Quantity estimates
    estimated_quantity = db.Column(db.Float)
    actual_quantity = db.Column(db.Float)
    rejected_quantity = db.Column(db.Float, default=0)

    # Status
    status = db.Column(db.String(30), default='pending')  # pending, in_progress, completed

    # Location
    current_location = db.Column(db.String(100))  # Where the unsorted parts are

    # Assignment
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Completion
    destination_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    completed_at = db.Column(db.DateTime)
    completed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Notes
    notes = db.Column(db.Text)

    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    production_order = db.relationship('ProductionOrder', backref='awaiting_sorting')
    scheduled_job = db.relationship('ScheduledJob', backref='awaiting_sorting')
    item = db.relationship('Item', backref='awaiting_sorting')
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id], backref='assigned_sorting')
    completed_by = db.relationship('User', foreign_keys=[completed_by_id], backref='completed_sorting')
    destination_location = db.relationship('Location', backref='sorted_items')

    def __repr__(self):
        return f'<AwaitingSorting {self.id}: {self.sorting_type}>'


class ProductionLog(db.Model):
    """Production activity log"""
    __tablename__ = 'production_logs'

    id = db.Column(db.Integer, primary_key=True)
    production_order_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'), nullable=False)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'))
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Log type
    log_type = db.Column(db.String(30), nullable=False)  # start, stop, quantity_update, issue

    # Production data
    quantity = db.Column(db.Float)
    good_quantity = db.Column(db.Float)
    rejected_quantity = db.Column(db.Float)

    # Issue tracking
    issue_type = db.Column(db.String(50))
    issue_description = db.Column(db.Text)

    # Notes
    notes = db.Column(db.Text)

    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ProductionLog {self.log_type} for order {self.production_order_id}>'
