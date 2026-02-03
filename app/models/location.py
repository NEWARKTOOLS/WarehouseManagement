from datetime import datetime
from app import db


class Location(db.Model):
    """Warehouse location model"""
    __tablename__ = 'locations'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

    # Location hierarchy
    location_type = db.Column(db.String(50), nullable=False)  # container, outdoor, upstairs, rack
    zone = db.Column(db.String(50))  # CON1, CON2, OUT, UP
    row = db.Column(db.String(10))
    bay = db.Column(db.String(10))
    shelf = db.Column(db.String(10))

    # Capacity tracking
    capacity_units = db.Column(db.String(20), default='pallets')  # pallets, boxes, units
    max_capacity = db.Column(db.Float, default=0)
    current_usage = db.Column(db.Float, default=0)

    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    stock_levels = db.relationship('StockLevel', backref='location', lazy='dynamic')

    def __repr__(self):
        return f'<Location {self.code}>'

    @property
    def available_capacity(self):
        """Calculate available capacity"""
        return max(0, self.max_capacity - self.current_usage)

    @property
    def usage_percentage(self):
        """Calculate usage percentage"""
        if self.max_capacity <= 0:
            return 0
        return min(100, (self.current_usage / self.max_capacity) * 100)

    @staticmethod
    def generate_code(zone, row=None, bay=None, shelf=None):
        """Generate location code based on components"""
        code_parts = [zone]
        if row:
            code_parts.append(f'R{row.zfill(2)}')
        if bay:
            code_parts.append(f'B{bay.zfill(2)}')
        if shelf:
            code_parts.append(f'S{shelf.zfill(2)}')
        return '-'.join(code_parts)

    def get_contents(self):
        """Get all items at this location with quantities"""
        return self.stock_levels.filter(db.StockLevel.quantity > 0).all()
