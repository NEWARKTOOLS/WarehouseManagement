"""
OEE (Overall Equipment Effectiveness) Tracking
Track machine availability, performance, and quality for profitability insights
"""
from datetime import datetime, date
from app import db


class ShiftLog(db.Model):
    """Daily shift log for each machine - tracks OEE metrics"""
    __tablename__ = 'shift_logs'

    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)
    shift_date = db.Column(db.Date, nullable=False, default=date.today)
    shift = db.Column(db.String(20), default='day')  # day, night, etc.

    # Planned production time
    planned_production_minutes = db.Column(db.Float, default=480)  # 8 hours default

    # Availability losses
    breakdown_minutes = db.Column(db.Float, default=0)
    setup_changeover_minutes = db.Column(db.Float, default=0)
    material_shortage_minutes = db.Column(db.Float, default=0)
    other_downtime_minutes = db.Column(db.Float, default=0)
    downtime_notes = db.Column(db.Text)

    # Performance tracking
    ideal_cycle_time_seconds = db.Column(db.Float)  # From setup sheet
    actual_cycles = db.Column(db.Integer, default=0)
    parts_per_cycle = db.Column(db.Integer, default=1)  # Cavities

    # Quality tracking
    total_parts_produced = db.Column(db.Integer, default=0)
    good_parts = db.Column(db.Integer, default=0)
    scrap_parts = db.Column(db.Integer, default=0)
    rework_parts = db.Column(db.Integer, default=0)

    # Scrap reasons breakdown
    scrap_startup = db.Column(db.Integer, default=0)
    scrap_colour = db.Column(db.Integer, default=0)
    scrap_short_shot = db.Column(db.Integer, default=0)
    scrap_flash = db.Column(db.Integer, default=0)
    scrap_sink_marks = db.Column(db.Integer, default=0)
    scrap_warp = db.Column(db.Integer, default=0)
    scrap_other = db.Column(db.Integer, default=0)
    scrap_notes = db.Column(db.Text)

    # Production order being run
    production_order_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'))

    # Operator
    operator_name = db.Column(db.String(100))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    machine = db.relationship('Machine', backref='shift_logs')
    production_order = db.relationship('ProductionOrder', backref='shift_logs')

    @property
    def total_downtime_minutes(self):
        """Total unplanned downtime"""
        return (
            (self.breakdown_minutes or 0) +
            (self.setup_changeover_minutes or 0) +
            (self.material_shortage_minutes or 0) +
            (self.other_downtime_minutes or 0)
        )

    @property
    def operating_time_minutes(self):
        """Actual operating time"""
        return (self.planned_production_minutes or 0) - self.total_downtime_minutes

    @property
    def availability_percent(self):
        """Availability = Operating Time / Planned Production Time"""
        if not self.planned_production_minutes or self.planned_production_minutes <= 0:
            return 0
        return (self.operating_time_minutes / self.planned_production_minutes) * 100

    @property
    def theoretical_output(self):
        """How many parts should have been made in operating time"""
        if not self.ideal_cycle_time_seconds or self.ideal_cycle_time_seconds <= 0:
            return 0
        cycles_possible = (self.operating_time_minutes * 60) / self.ideal_cycle_time_seconds
        return cycles_possible * (self.parts_per_cycle or 1)

    @property
    def performance_percent(self):
        """Performance = Actual Output / Theoretical Output"""
        theoretical = self.theoretical_output
        if theoretical <= 0:
            return 0
        return ((self.total_parts_produced or 0) / theoretical) * 100

    @property
    def quality_percent(self):
        """Quality = Good Parts / Total Parts"""
        if not self.total_parts_produced or self.total_parts_produced <= 0:
            return 0
        return ((self.good_parts or 0) / self.total_parts_produced) * 100

    @property
    def oee_percent(self):
        """OEE = Availability x Performance x Quality"""
        return (
            (self.availability_percent / 100) *
            (self.performance_percent / 100) *
            (self.quality_percent / 100)
        ) * 100

    @property
    def scrap_percent(self):
        """Scrap rate percentage"""
        if not self.total_parts_produced or self.total_parts_produced <= 0:
            return 0
        return ((self.scrap_parts or 0) / self.total_parts_produced) * 100


class DowntimeReason(db.Model):
    """Standardized downtime reasons for analysis"""
    __tablename__ = 'downtime_reasons'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))  # planned, unplanned, quality
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DowntimeEvent(db.Model):
    """Individual downtime events for detailed tracking"""
    __tablename__ = 'downtime_events'

    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)
    shift_log_id = db.Column(db.Integer, db.ForeignKey('shift_logs.id'))
    reason_id = db.Column(db.Integer, db.ForeignKey('downtime_reasons.id'))

    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Float)

    notes = db.Column(db.Text)
    reported_by = db.Column(db.String(100))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    machine = db.relationship('Machine', backref='downtime_events')
    shift_log = db.relationship('ShiftLog', backref='downtime_events')
    reason = db.relationship('DowntimeReason', backref='events')

    def calculate_duration(self):
        """Calculate duration if end time is set"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            self.duration_minutes = delta.total_seconds() / 60


class ScrapReason(db.Model):
    """Standardized scrap reasons for pareto analysis"""
    __tablename__ = 'scrap_reasons'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))  # process, material, operator, tooling
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ScrapEvent(db.Model):
    """Individual scrap events for detailed tracking"""
    __tablename__ = 'scrap_events'

    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)
    production_order_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'))
    shift_log_id = db.Column(db.Integer, db.ForeignKey('shift_logs.id'))
    reason_id = db.Column(db.Integer, db.ForeignKey('scrap_reasons.id'))

    quantity = db.Column(db.Integer, nullable=False)
    weight_kg = db.Column(db.Float)
    estimated_cost = db.Column(db.Float)

    occurred_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    reported_by = db.Column(db.String(100))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    machine = db.relationship('Machine', backref='scrap_events')
    production_order = db.relationship('ProductionOrder', backref='scrap_events')
    shift_log = db.relationship('ShiftLog', backref='scrap_events_list')
    reason = db.relationship('ScrapReason', backref='events')
