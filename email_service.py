from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, TrackingSettings, ClickTracking, OpenTracking
import logging
from datetime import datetime
from typing import Optional, Dict

from app.models import Lead, Listing, Match, NurtureTouch
from app.database import db
from app.services.llm_service import LLMService
from config.config import Config

logger = logging.getLogger(__name__)


class EmailService:
    """
    Email delivery service using SendGrid
    """
    
    def __init__(self):
        self.sg = SendGridAPIClient(Config.SENDGRID_API_KEY)
        self.from_email = Config.FROM_EMAIL
        self.from_name = Config.FROM_NAME
        self.app_domain = Config.APP_DOMAIN
        self.llm = LLMService()
    
    def send_listing_alert(self, match_id: int) -> bool:
        """
        Send personalized listing alert email
        
        Args:
            match_id: ID of the match to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            match = Match.query.get(match_id)
            if not match:
                logger.error(f"Match {match_id} not found")
                return False
            
            lead = match.lead
            listing = match.listing
            
            # Generate personalized content
            email_content = self.llm.generate_listing_alert(
                lead, listing, match.match_reasons
            )
            
            # Create tracking links
            listing_url = self._create_tracked_link(match.id, 'listing_view')
            schedule_url = self._create_tracked_link(match.id, 'schedule_showing')
            unsubscribe_url = f"{self.app_domain}/unsubscribe/{lead.id}"
            
            # Build HTML email
            html_content = self._build_listing_email_html(
                lead=lead,
                listing=listing,
                subject=email_content['subject'],
                body=email_content['body'],
                listing_url=listing_url,
                schedule_url=schedule_url,
                unsubscribe_url=unsubscribe_url
            )
            
            # Create and send email
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(lead.email, lead.first_name),
                subject=email_content['subject'],
                html_content=html_content
            )
            
            # Enable click and open tracking
            message.tracking_settings = self._get_tracking_settings()
            
            # Send
            response = self.sg.send(message)
            
            # Record the touch
            touch = NurtureTouch(
                lead_id=lead.id,
                match_id=match.id,
                touch_type='listing_alert',
                subject=email_content['subject'],
                message_content=email_content['body'],
                channel='email',
                sent_at=datetime.utcnow(),
                message_id=response.headers.get('X-Message-Id')
            )
            db.session.add(touch)
            
            # Update match status
            match.mark_sent(response.headers.get('X-Message-Id'))
            
            db.session.commit()
            
            logger.info(f"Sent listing alert for match {match_id} to {lead.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending listing alert: {e}")
            db.session.rollback()
            return False
    
    def send_nurture_email(self, lead_id: int, nurture_type: str) -> bool:
        """
        Send nurture email to lead
        
        Args:
            lead_id: ID of lead
            nurture_type: Type of nurture message
            
        Returns:
            True if successful
        """
        try:
            lead = Lead.query.get(lead_id)
            if not lead:
                logger.error(f"Lead {lead_id} not found")
                return False
            
            # Check if lead is unsubscribed
            if lead.status == 'unsubscribed':
                logger.info(f"Lead {lead_id} is unsubscribed, skipping email")
                return False
            
            # Generate content
            email_content = self.llm.generate_nurture_message(lead, nurture_type)
            
            # Create tracking links
            unsubscribe_url = f"{self.app_domain}/unsubscribe/{lead.id}"
            
            # Build HTML
            html_content = self._build_nurture_email_html(
                lead=lead,
                subject=email_content['subject'],
                body=email_content['body'],
                unsubscribe_url=unsubscribe_url
            )
            
            # Create and send
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(lead.email, lead.first_name),
                subject=email_content['subject'],
                html_content=html_content
            )
            
            message.tracking_settings = self._get_tracking_settings()
            
            response = self.sg.send(message)
            
            # Record touch
            touch = NurtureTouch(
                lead_id=lead.id,
                touch_type=nurture_type,
                subject=email_content['subject'],
                message_content=email_content['body'],
                channel='email',
                sent_at=datetime.utcnow(),
                message_id=response.headers.get('X-Message-Id')
            )
            db.session.add(touch)
            
            # Update lead
            lead.last_contact = datetime.utcnow()
            
            db.session.commit()
            
            logger.info(f"Sent {nurture_type} email to lead {lead_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending nurture email: {e}")
            db.session.rollback()
            return False
    
    def _build_listing_email_html(self, lead: Lead, listing: Listing, 
                                  subject: str, body: str,
                                  listing_url: str, schedule_url: str,
                                  unsubscribe_url: str) -> str:
        """Build HTML for listing alert email"""
        
        # Get first photo or placeholder
        photo_url = listing.photos[0] if listing.photos else "https://via.placeholder.com/600x400?text=No+Image"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #ffffff; }}
        .listing-card {{ margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }}
        .listing-image {{ width: 100%; border-radius: 8px; margin-bottom: 15px; }}
        .listing-details {{ margin: 15px 0; }}
        .price {{ font-size: 24px; font-weight: bold; color: #e74c3c; }}
        .specs {{ color: #666; margin: 10px 0; }}
        .btn {{ display: inline-block; padding: 12px 24px; background: #3498db; color: white; 
                text-decoration: none; border-radius: 4px; margin: 10px 5px; }}
        .btn:hover {{ background: #2980b9; }}
        .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
        .unsubscribe {{ color: #999; text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{self.from_name}</h1>
        </div>
        
        <div class="content">
            <h2>Hi {lead.first_name}! 👋</h2>
            
            <p>{body.replace(chr(10), '<br>')}</p>
            
            <div class="listing-card">
                <img src="{photo_url}" alt="{listing.address}" class="listing-image">
                
                <div class="listing-details">
                    <h3>{listing.address}</h3>
                    <p class="price">${listing.price:,.0f}</p>
                    <p class="specs">
                        🛏️ {listing.bedrooms} bed &nbsp;|&nbsp; 
                        🛁 {listing.bathrooms} bath &nbsp;|&nbsp; 
                        📐 {listing.sqft:,} sqft
                    </p>
                    <p>{listing.city}, {listing.state} {listing.zip_code}</p>
                </div>
                
                <div style="text-align: center; margin-top: 20px;">
                    <a href="{listing_url}" class="btn">View Full Details</a>
                    <a href="{schedule_url}" class="btn" style="background: #2ecc71;">Schedule Showing</a>
                </div>
            </div>
            
            <p style="margin-top: 20px;">
                Questions? Just reply to this email and I'll get back to you right away.
            </p>
        </div>
        
        <div class="footer">
            <p>You're receiving this because you signed up for {self.from_name}.</p>
            <p><a href="{unsubscribe_url}" class="unsubscribe">Unsubscribe</a></p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def _build_nurture_email_html(self, lead: Lead, subject: str, body: str,
                                  unsubscribe_url: str) -> str:
        """Build HTML for nurture email"""
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 30px; background: #ffffff; }}
        .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
        .unsubscribe {{ color: #999; text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>{self.from_name}</h2>
        </div>
        
        <div class="content">
            {body.replace(chr(10), '<br><br>')}
        </div>
        
        <div class="footer">
            <p>You're receiving this because you signed up for {self.from_name}.</p>
            <p><a href="{unsubscribe_url}" class="unsubscribe">Unsubscribe</a></p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def _create_tracked_link(self, match_id: int, action: str) -> str:
        """
        Create tracking link
        
        Args:
            match_id: Match ID
            action: Action type (listing_view, schedule_showing, etc.)
        """
        return f"{self.app_domain}/track/{match_id}/{action}"
    
    def _get_tracking_settings(self) -> TrackingSettings:
        """Get email tracking settings"""
        tracking_settings = TrackingSettings()
        
        if Config.EMAIL_OPEN_TRACKING:
            tracking_settings.open_tracking = OpenTracking(True)
        
        tracking_settings.click_tracking = ClickTracking(True, True)
        
        return tracking_settings
