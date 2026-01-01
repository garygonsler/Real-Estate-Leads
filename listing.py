from app.database import db, BaseModel
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from datetime import datetime


class Listing(BaseModel):
    """MLS Listing model"""
    __tablename__ = 'listings'
    
    # MLS info
    mls_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    mls_source = db.Column(db.String(50))  # Which MLS it came from
    
    # Address
    address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False, index=True)
    state = db.Column(db.String(2), nullable=False)
    zip_code = db.Column(db.String(10), index=True)
    latitude = db.Column(db.Numeric(10, 7))
    longitude = db.Column(db.Numeric(10, 7))
    
    # Property details
    price = db.Column(db.Numeric(12, 2), nullable=False, index=True)
    original_price = db.Column(db.Numeric(12, 2))
    bedrooms = db.Column(db.Integer, index=True)
    bathrooms = db.Column(db.Numeric(3, 1), index=True)
    sqft = db.Column(db.Integer)
    lot_size = db.Column(db.Integer)  # in square feet
    year_built = db.Column(db.Integer)
    
    # Property type
    property_type = db.Column(db.String(50), index=True)
    # single-family, condo, townhouse, multi-family, land, etc.
    property_subtype = db.Column(db.String(50))
    
    # Features
    garage_spaces = db.Column(db.Integer)
    stories = db.Column(db.Integer)
    pool = db.Column(db.Boolean, default=False)
    
    # Listing details
    listing_date = db.Column(db.DateTime, index=True)
    status = db.Column(db.String(50), default='Active', index=True)
    # Status: Active, Pending, Sold, Expired, Withdrawn
    status_date = db.Column(db.DateTime)
    
    days_on_market = db.Column(db.Integer)
    price_per_sqft = db.Column(db.Numeric(10, 2))
    
    # Description & media
    description = db.Column(db.Text)
    photos = db.Column(ARRAY(db.String))  # Array of photo URLs
    virtual_tour_url = db.Column(db.String(500))
    
    # HOA
    hoa_fee = db.Column(db.Numeric(10, 2))
    hoa_frequency = db.Column(db.String(20))  # monthly, quarterly, annually
    
    # Schools
    elementary_school = db.Column(db.String(100))
    middle_school = db.Column(db.String(100))
    high_school = db.Column(db.String(100))
    school_district = db.Column(db.String(100))
    
    # Agent/Office
    listing_agent_name = db.Column(db.String(200))
    listing_agent_phone = db.Column(db.String(20))
    listing_office = db.Column(db.String(200))
    
    # Raw MLS data (for fields we don't explicitly model)
    raw_data = db.Column(JSONB)
    
    # Sync tracking
    last_synced = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    matches = db.relationship('Match', backref='listing', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Listing {self.address} - ${self.price}>'
    
    @property
    def full_address(self):
        return f"{self.address}, {self.city}, {self.state} {self.zip_code}"
    
    def calculate_price_per_sqft(self):
        """Calculate and update price per square foot"""
        if self.sqft and self.sqft > 0:
            self.price_per_sqft = self.price / self.sqft
            db.session.commit()
    
    def is_price_reduced(self):
        """Check if price was reduced"""
        if self.original_price and self.price < self.original_price:
            reduction = self.original_price - self.price
            percentage = (reduction / self.original_price) * 100
            return True, reduction, percentage
        return False, 0, 0


class ListingHistory(BaseModel):
    """Track listing changes over time"""
    __tablename__ = 'listing_history'
    
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=False)
    
    # What changed
    change_type = db.Column(db.String(50))  # price_change, status_change, etc.
    
    # Old and new values
    old_value = db.Column(db.String(255))
    new_value = db.Column(db.String(255))
    
    # Timestamp
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ListingHistory {self.change_type} for Listing {self.listing_id}>'
