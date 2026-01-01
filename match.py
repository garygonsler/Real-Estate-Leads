from app.database import db, BaseModel
from datetime import datetime


class Match(BaseModel):
    """Match between a lead and a listing"""
    __tablename__ = 'matches'
    
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False, index=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=False, index=True)
    
    # Match quality
    match_score = db.Column(db.Integer)  # 0-100
    match_reasons = db.Column(db.Text)  # Human-readable reasons
    match_details = db.Column(db.JSON)  # Structured match data
    
    # Status tracking
    status = db.Column(db.String(50), default='pending', index=True)
    # Status: pending, sent, opened, clicked, showing_requested, not_interested, converted
    
    # Engagement tracking
    sent_at = db.Column(db.DateTime)
    opened_at = db.Column(db.DateTime)
    clicked_at = db.Column(db.DateTime)
    responded_at = db.Column(db.DateTime)
    
    # Metadata
    alert_type = db.Column(db.String(50), default='email')  # email, sms, both
    message_id = db.Column(db.String(255))  # External message tracking ID
    
    # User feedback
    feedback = db.Column(db.String(50))  # interested, not_interested, too_expensive, etc.
    feedback_note = db.Column(db.Text)
    
    def __repr__(self):
        return f'<Match Lead:{self.lead_id} Listing:{self.listing_id} Score:{self.match_score}>'
    
    def mark_sent(self, message_id=None):
        """Mark match as sent"""
        self.sent_at = datetime.utcnow()
        self.status = 'sent'
        if message_id:
            self.message_id = message_id
        db.session.commit()
    
    def mark_opened(self):
        """Mark match email as opened"""
        if not self.opened_at:
            self.opened_at = datetime.utcnow()
            self.status = 'opened'
            # Update lead engagement
            self.lead.update_engagement_score('email_open')
            db.session.commit()
    
    def mark_clicked(self):
        """Mark match link as clicked"""
        if not self.clicked_at:
            self.clicked_at = datetime.utcnow()
            self.status = 'clicked'
            # Update lead engagement
            self.lead.update_engagement_score('email_click')
            db.session.commit()


class NurtureTouch(BaseModel):
    """Track all nurture communications"""
    __tablename__ = 'nurture_touches'
    
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False, index=True)
    
    # Touch details
    touch_type = db.Column(db.String(50), nullable=False)
    # Types: listing_alert, market_update, check_in, price_drop, dormant_reengagement
    
    subject = db.Column(db.String(255))
    message_content = db.Column(db.Text)
    
    # Delivery
    channel = db.Column(db.String(20), default='email')  # email, sms, both
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Engagement
    opened_at = db.Column(db.DateTime)
    clicked_at = db.Column(db.DateTime)
    response_received = db.Column(db.Boolean, default=False)
    response_text = db.Column(db.Text)
    
    # External tracking
    message_id = db.Column(db.String(255))
    
    # Related match (if this is a listing alert)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'))
    
    def __repr__(self):
        return f'<NurtureTouch {self.touch_type} for Lead {self.lead_id}>'
    
    def mark_opened(self):
        """Mark touch as opened"""
        if not self.opened_at:
            self.opened_at = datetime.utcnow()
            self.lead.update_engagement_score('email_open')
            db.session.commit()
    
    def mark_clicked(self):
        """Mark touch as clicked"""
        if not self.clicked_at:
            self.clicked_at = datetime.utcnow()
            self.lead.update_engagement_score('email_click')
            db.session.commit()
