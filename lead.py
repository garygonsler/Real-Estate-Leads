from app.database import db, BaseModel
from sqlalchemy.dialects.postgresql import ARRAY
from datetime import datetime


class Lead(BaseModel):
    """Lead/Buyer model"""
    __tablename__ = 'leads'
    
    # Basic info
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20))
    
    # Source tracking
    source = db.Column(db.String(50))  # Zillow, Realtor.com, referral, etc.
    source_url = db.Column(db.String(500))
    
    # Status
    status = db.Column(db.String(50), default='active', index=True)
    # Status options: active, nurture, dormant, converted, unsubscribed
    
    # Engagement metrics
    engagement_score = db.Column(db.Integer, default=0)
    last_contact = db.Column(db.DateTime, default=datetime.utcnow)
    last_opened = db.Column(db.DateTime)
    last_clicked = db.Column(db.DateTime)
    
    # CRM sync
    crm_id = db.Column(db.String(100), index=True)
    crm_last_sync = db.Column(db.DateTime)
    
    # Agent assignment
    assigned_agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))
    
    # Relationships
    criteria = db.relationship('BuyerCriteria', backref='lead', uselist=False, cascade='all, delete-orphan')
    matches = db.relationship('Match', backref='lead', lazy='dynamic', cascade='all, delete-orphan')
    nurture_touches = db.relationship('NurtureTouch', backref='lead', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Lead {self.first_name} {self.last_name} - {self.email}>'
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def update_engagement_score(self, action_type):
        """Update engagement score based on action"""
        score_map = {
            'email_open': 5,
            'email_click': 15,
            'listing_view': 20,
            'showing_request': 50,
            'offer_submitted': 100
        }
        self.engagement_score += score_map.get(action_type, 0)
        self.last_contact = datetime.utcnow()
        db.session.commit()


class BuyerCriteria(BaseModel):
    """Buyer search criteria"""
    __tablename__ = 'buyer_criteria'
    
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False, unique=True)
    
    # Price range
    min_price = db.Column(db.Numeric(12, 2))
    max_price = db.Column(db.Numeric(12, 2))
    
    # Property specs
    bedrooms = db.Column(db.Integer)
    bathrooms = db.Column(db.Numeric(3, 1))
    min_sqft = db.Column(db.Integer)
    max_sqft = db.Column(db.Integer)
    
    # Location
    location_preferences = db.Column(ARRAY(db.String))  # Array of cities/neighborhoods
    zip_codes = db.Column(ARRAY(db.String))
    
    # Property types
    property_types = db.Column(ARRAY(db.String))  # single-family, condo, townhouse, etc.
    
    # Special requirements (natural language)
    must_haves = db.Column(db.Text)  # "home office, pool, good schools"
    nice_to_haves = db.Column(db.Text)
    
    # Timeline
    timeline = db.Column(db.String(50))  # immediate, 3-6 months, exploring, etc.
    
    # Financing
    financing_type = db.Column(db.String(50))  # cash, conventional, FHA, VA
    pre_approved = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<BuyerCriteria for Lead {self.lead_id}>'


class Agent(BaseModel):
    """Real estate agent model"""
    __tablename__ = 'agents'
    
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    
    # License info
    license_number = db.Column(db.String(50))
    license_state = db.Column(db.String(2))
    
    # Specialization
    specialties = db.Column(ARRAY(db.String))  # buyer's agent, seller's agent, luxury, etc.
    service_areas = db.Column(ARRAY(db.String))  # Cities/neighborhoods they cover
    
    # Status
    active = db.Column(db.Boolean, default=True)
    
    # CRM sync
    crm_id = db.Column(db.String(100))
    
    # Relationships
    leads = db.relationship('Lead', backref='agent', lazy='dynamic')
    
    def __repr__(self):
        return f'<Agent {self.first_name} {self.last_name}>'
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
