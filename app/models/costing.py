"""
Job Costing & Profitability Models
Track true costs and margins on every job
"""
from datetime import datetime
from app import db


class JobCosting(db.Model):
    """Track actual costs for each production order"""
    __tablename__ = 'job_costings'

    id = db.Column(db.Integer, primary_key=True)
    production_order_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'), nullable=False, unique=True)

    # Quoted/Expected costs (from quote or estimate)
    quoted_material_cost = db.Column(db.Float, default=0)
    quoted_labour_cost = db.Column(db.Float, default=0)
    quoted_machine_cost = db.Column(db.Float, default=0)
    quoted_overhead_cost = db.Column(db.Float, default=0)
    quoted_total_cost = db.Column(db.Float, default=0)
    quoted_selling_price = db.Column(db.Float, default=0)

    # Actual costs (tracked during production)
    actual_material_cost = db.Column(db.Float, default=0)
    actual_material_kg = db.Column(db.Float, default=0)
    actual_labour_cost = db.Column(db.Float, default=0)
    actual_labour_hours = db.Column(db.Float, default=0)
    actual_machine_cost = db.Column(db.Float, default=0)
    actual_machine_hours = db.Column(db.Float, default=0)
    actual_setup_hours = db.Column(db.Float, default=0)
    actual_overhead_cost = db.Column(db.Float, default=0)

    # Scrap/waste tracking
    scrap_quantity = db.Column(db.Float, default=0)
    scrap_cost = db.Column(db.Float, default=0)
    rework_hours = db.Column(db.Float, default=0)
    rework_cost = db.Column(db.Float, default=0)

    # Energy tracking
    energy_kwh = db.Column(db.Float, default=0)
    energy_cost = db.Column(db.Float, default=0)

    # Tooling costs for this job
    tooling_cost = db.Column(db.Float, default=0)

    # Final selling price (may differ from quote)
    actual_selling_price = db.Column(db.Float, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    # Relationships
    production_order = db.relationship('ProductionOrder', backref=db.backref('costing', uselist=False))

    @property
    def actual_total_cost(self):
        """Calculate total actual cost"""
        return (
            (self.actual_material_cost or 0) +
            (self.actual_labour_cost or 0) +
            (self.actual_machine_cost or 0) +
            (self.actual_overhead_cost or 0) +
            (self.scrap_cost or 0) +
            (self.rework_cost or 0) +
            (self.energy_cost or 0) +
            (self.tooling_cost or 0)
        )

    @property
    def gross_profit(self):
        """Calculate gross profit"""
        selling = self.actual_selling_price or self.quoted_selling_price or 0
        return selling - self.actual_total_cost

    @property
    def gross_margin_percent(self):
        """Calculate gross margin percentage"""
        selling = self.actual_selling_price or self.quoted_selling_price or 0
        if selling <= 0:
            return 0
        return (self.gross_profit / selling) * 100

    @property
    def cost_variance(self):
        """Difference between quoted and actual cost"""
        return self.actual_total_cost - (self.quoted_total_cost or 0)

    @property
    def cost_variance_percent(self):
        """Cost variance as percentage"""
        if not self.quoted_total_cost or self.quoted_total_cost <= 0:
            return 0
        return (self.cost_variance / self.quoted_total_cost) * 100


class MaterialUsage(db.Model):
    """Track material usage per job for accurate costing"""
    __tablename__ = 'material_usage'

    id = db.Column(db.Integer, primary_key=True)
    production_order_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))  # Raw material item

    # Material details
    material_type = db.Column(db.String(100))  # PP, ABS, PA66, etc.
    material_grade = db.Column(db.String(100))
    supplier = db.Column(db.String(200))
    batch_number = db.Column(db.String(100))

    # Quantities
    quantity_issued_kg = db.Column(db.Float, default=0)
    quantity_used_kg = db.Column(db.Float, default=0)
    quantity_returned_kg = db.Column(db.Float, default=0)
    quantity_scrap_kg = db.Column(db.Float, default=0)

    # Costs
    cost_per_kg = db.Column(db.Float, default=0)
    total_cost = db.Column(db.Float, default=0)

    # Masterbatch/colorant
    masterbatch_type = db.Column(db.String(100))
    masterbatch_ratio = db.Column(db.String(50))  # e.g., "2%"
    masterbatch_kg = db.Column(db.Float, default=0)
    masterbatch_cost = db.Column(db.Float, default=0)

    # Regrind usage
    regrind_percentage = db.Column(db.Float, default=0)
    regrind_kg = db.Column(db.Float, default=0)

    # Timestamps
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    production_order = db.relationship('ProductionOrder', backref='material_usage')
    material_item = db.relationship('Item', backref='material_usage')


class MachineRate(db.Model):
    """Hourly rates for machines - used for costing"""
    __tablename__ = 'machine_rates'

    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)

    # Rates
    hourly_rate = db.Column(db.Float, default=0)  # Machine hour rate
    setup_rate = db.Column(db.Float, default=0)  # Setup/changeover rate
    energy_rate_per_kwh = db.Column(db.Float, default=0.15)  # Electricity cost

    # Estimated energy consumption
    idle_kw = db.Column(db.Float, default=0)  # Power when idle
    running_kw = db.Column(db.Float, default=0)  # Power when running

    # Overhead allocation
    overhead_rate_per_hour = db.Column(db.Float, default=0)

    # Effective dates
    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    machine = db.relationship('Machine', backref='rates')


class LabourRate(db.Model):
    """Labour rates for costing"""
    __tablename__ = 'labour_rates'

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(100), nullable=False)  # Operator, Setter, QC, etc.
    hourly_rate = db.Column(db.Float, default=0)
    overtime_multiplier = db.Column(db.Float, default=1.5)

    # Effective dates
    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Quote(db.Model):
    """Customer quotes with full cost breakdown"""
    __tablename__ = 'quotes'

    id = db.Column(db.Integer, primary_key=True)
    quote_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))

    # Quote details
    description = db.Column(db.String(500))
    quantity = db.Column(db.Float, nullable=False)
    annual_volume = db.Column(db.Float)  # Expected annual usage

    # Part details
    part_weight_g = db.Column(db.Float)
    runner_weight_g = db.Column(db.Float)
    cycle_time_seconds = db.Column(db.Float)
    cavities = db.Column(db.Integer, default=1)

    # Material costs
    material_type = db.Column(db.String(100))
    material_cost_per_kg = db.Column(db.Float, default=0)
    material_cost_per_part = db.Column(db.Float, default=0)

    # Production costs
    machine_rate_per_hour = db.Column(db.Float, default=0)
    labour_rate_per_hour = db.Column(db.Float, default=0)
    cycle_cost_per_part = db.Column(db.Float, default=0)

    # Setup/changeover
    setup_hours = db.Column(db.Float, default=0)
    setup_cost = db.Column(db.Float, default=0)
    setup_cost_per_part = db.Column(db.Float, default=0)  # Amortized over quantity

    # Secondary operations
    secondary_ops_cost = db.Column(db.Float, default=0)  # Degating, assembly, etc.

    # Overheads
    overhead_percent = db.Column(db.Float, default=20)
    overhead_cost_per_part = db.Column(db.Float, default=0)

    # Packaging
    packaging_cost_per_part = db.Column(db.Float, default=0)

    # Totals
    total_cost_per_part = db.Column(db.Float, default=0)
    target_margin_percent = db.Column(db.Float, default=30)
    quoted_price_per_part = db.Column(db.Float, default=0)
    quoted_total = db.Column(db.Float, default=0)

    # Tooling (if new mould required)
    tooling_cost = db.Column(db.Float, default=0)
    tooling_amortization_qty = db.Column(db.Float)  # Qty to spread tooling cost over

    # Status
    status = db.Column(db.String(30), default='draft')  # draft, sent, accepted, rejected, expired
    valid_until = db.Column(db.Date)

    # Notes
    notes = db.Column(db.Text)
    internal_notes = db.Column(db.Text)

    # Converted to order
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = db.Column(db.DateTime)

    # Relationships
    customer = db.relationship('Customer', backref='quotes')
    item = db.relationship('Item', backref='quotes')
    sales_order = db.relationship('SalesOrder', backref='quote')

    def calculate_costs(self):
        """Calculate all cost fields based on inputs"""
        # Material cost per part
        part_weight_kg = (self.part_weight_g or 0) / 1000
        runner_weight_kg = (self.runner_weight_g or 0) / 1000
        total_shot_weight_kg = part_weight_kg + runner_weight_kg
        cavities = self.cavities or 1

        self.material_cost_per_part = (total_shot_weight_kg / cavities) * (self.material_cost_per_kg or 0)

        # Cycle cost per part (machine + labour)
        cycle_time_hours = (self.cycle_time_seconds or 0) / 3600
        machine_cost_per_cycle = cycle_time_hours * (self.machine_rate_per_hour or 0)
        labour_cost_per_cycle = cycle_time_hours * (self.labour_rate_per_hour or 0)
        self.cycle_cost_per_part = (machine_cost_per_cycle + labour_cost_per_cycle) / cavities

        # Setup cost amortized
        self.setup_cost = (self.setup_hours or 0) * ((self.machine_rate_per_hour or 0) + (self.labour_rate_per_hour or 0))
        if self.quantity and self.quantity > 0:
            self.setup_cost_per_part = self.setup_cost / self.quantity
        else:
            self.setup_cost_per_part = 0

        # Total cost per part before overhead
        direct_cost = (
            self.material_cost_per_part +
            self.cycle_cost_per_part +
            self.setup_cost_per_part +
            (self.secondary_ops_cost or 0) +
            (self.packaging_cost_per_part or 0)
        )

        # Overhead
        self.overhead_cost_per_part = direct_cost * ((self.overhead_percent or 0) / 100)

        # Total cost
        self.total_cost_per_part = direct_cost + self.overhead_cost_per_part

        # Selling price with margin
        margin = self.target_margin_percent if self.target_margin_percent is not None else 30
        if margin <= 0:
            self.quoted_price_per_part = self.total_cost_per_part
        elif margin < 100:
            self.quoted_price_per_part = self.total_cost_per_part / (1 - margin / 100)
        else:
            self.quoted_price_per_part = self.total_cost_per_part * 2

        # Total quote value
        self.quoted_total = self.quoted_price_per_part * (self.quantity or 0)

    @staticmethod
    def generate_quote_number():
        """Generate unique quote number"""
        today = datetime.now().strftime('%y%m%d')
        count = Quote.query.filter(
            Quote.quote_number.like(f'QT-{today}%')
        ).count()
        return f'QT-{today}-{str(count + 1).zfill(4)}'


class CustomerProfitability(db.Model):
    """Aggregated customer profitability metrics - updated periodically"""
    __tablename__ = 'customer_profitability'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    period_year = db.Column(db.Integer, nullable=False)
    period_month = db.Column(db.Integer)  # NULL for yearly totals

    # Revenue
    total_revenue = db.Column(db.Float, default=0)
    order_count = db.Column(db.Integer, default=0)

    # Costs
    total_material_cost = db.Column(db.Float, default=0)
    total_labour_cost = db.Column(db.Float, default=0)
    total_machine_cost = db.Column(db.Float, default=0)
    total_overhead_cost = db.Column(db.Float, default=0)
    total_cost = db.Column(db.Float, default=0)

    # Profitability
    gross_profit = db.Column(db.Float, default=0)
    gross_margin_percent = db.Column(db.Float, default=0)

    # Efficiency metrics
    avg_order_value = db.Column(db.Float, default=0)
    on_time_delivery_percent = db.Column(db.Float, default=0)
    reject_rate_percent = db.Column(db.Float, default=0)

    # Updated timestamp
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    customer = db.relationship('Customer', backref='profitability_records')
