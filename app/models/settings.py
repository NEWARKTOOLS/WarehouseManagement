from datetime import datetime
from app import db


class CompanySettings(db.Model):
    """Company settings - singleton table"""
    __tablename__ = 'company_settings'

    id = db.Column(db.Integer, primary_key=True)

    # Company Details
    company_name = db.Column(db.String(200))
    trading_name = db.Column(db.String(200))
    company_number = db.Column(db.String(50))
    vat_number = db.Column(db.String(50))

    # Address
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    county = db.Column(db.String(100))
    postcode = db.Column(db.String(20))
    country = db.Column(db.String(100), default='United Kingdom')

    # Contact
    phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    website = db.Column(db.String(200))

    # Banking
    bank_name = db.Column(db.String(100))
    account_name = db.Column(db.String(200))
    sort_code = db.Column(db.String(20))
    account_number = db.Column(db.String(20))
    iban = db.Column(db.String(50))
    swift_bic = db.Column(db.String(20))

    # Logo (stored as filename)
    logo_filename = db.Column(db.String(200))

    # Packing List Settings
    packing_list_title = db.Column(db.String(100), default='PACKING LIST')
    packing_list_footer = db.Column(db.Text)
    packing_list_terms = db.Column(db.Text)
    packing_list_show_prices = db.Column(db.Boolean, default=False)
    packing_list_show_signature = db.Column(db.Boolean, default=True)
    packing_list_show_bank_details = db.Column(db.Boolean, default=False)

    # Label Settings
    label_show_company = db.Column(db.Boolean, default=True)
    label_show_sku = db.Column(db.Boolean, default=True)
    label_show_name = db.Column(db.Boolean, default=True)
    label_show_barcode = db.Column(db.Boolean, default=True)
    label_show_quantity = db.Column(db.Boolean, default=True)
    label_width = db.Column(db.Integer, default=89)  # mm (Dymo 99012 large address)
    label_height = db.Column(db.Integer, default=36)  # mm

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_settings(cls):
        """Get or create company settings (singleton)"""
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings

    @property
    def full_address(self):
        """Return formatted full address"""
        parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.county,
            self.postcode,
            self.country
        ]
        return ', '.join(p for p in parts if p)

    def __repr__(self):
        return f'<CompanySettings {self.company_name}>'
