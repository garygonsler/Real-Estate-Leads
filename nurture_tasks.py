import logging
from datetime import datetime, timedelta
from sqlalchemy import and_

from app.celery_app import celery
from app.database import db
from app.models import Lead, NurtureTouch
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


@celery.task
def run_daily_nurture():
    """
    Daily task to send nurture emails to appropriate leads
    Runs at 9 AM every day
    """
    try:
        logger.info("Starting daily nurture task")
        
        results = {
            'check_ins_sent': 0,
            'market_updates_sent': 0,
            'reengagements_sent': 0
        }
        
        # Active leads who haven't been contacted in 7 days
        active_leads = Lead.query.filter(
            Lead.status == 'active',
            Lead.last_contact < datetime.utcnow() - timedelta(days=7)
        ).all()
        
        for lead in active_leads:
            send_nurture_touch.delay(lead.id, 'check_in')
            results['check_ins_sent'] += 1
        
        # Nurture status leads who haven't been contacted in 14 days
        # Send market updates
        nurture_leads = Lead.query.filter(
            Lead.status == 'nurture',
            Lead.last_contact < datetime.utcnow() - timedelta(days=14),
            Lead.last_contact >= datetime.utcnow() - timedelta(days=60)
        ).all()
        
        for lead in nurture_leads:
            send_nurture_touch.delay(lead.id, 'market_update')
            results['market_updates_sent'] += 1
        
        # Dormant leads (60+ days no contact)
        # Try to re-engage
        dormant_leads = Lead.query.filter(
            Lead.status.in_(['active', 'nurture']),
            Lead.last_contact < datetime.utcnow() - timedelta(days=60)
        ).all()
        
        for lead in dormant_leads:
            # Don't spam - only send reengagement once every 30 days
            last_reengagement = NurtureTouch.query.filter(
                NurtureTouch.lead_id == lead.id,
                NurtureTouch.touch_type == 'dormant_reengagement'
            ).order_by(NurtureTouch.sent_at.desc()).first()
            
            if not last_reengagement or \
               last_reengagement.sent_at < datetime.utcnow() - timedelta(days=30):
                send_nurture_touch.delay(lead.id, 'dormant_reengagement')
                results['reengagements_sent'] += 1
        
        logger.info(f"Daily nurture complete: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Error in daily nurture task: {e}")
        return {'status': 'error', 'error': str(e)}


@celery.task(bind=True, max_retries=2)
def send_nurture_touch(self, lead_id, touch_type):
    """
    Send a specific nurture message to a lead
    
    Args:
        lead_id: ID of the lead
        touch_type: Type of nurture message (check_in, market_update, dormant_reengagement)
    """
    try:
        logger.info(f"Sending {touch_type} to lead {lead_id}")
        
        email_service = EmailService()
        success = email_service.send_nurture_email(lead_id, touch_type)
        
        if not success:
            raise Exception(f"Failed to send {touch_type} to lead {lead_id}")
        
        return {
            'status': 'success',
            'lead_id': lead_id,
            'touch_type': touch_type
        }
        
    except Exception as e:
        logger.error(f"Error sending {touch_type} to lead {lead_id}: {e}")
        raise self.retry(exc=e, countdown=300)


@celery.task
def update_engagement_scores():
    """
    Periodic task to decay engagement scores over time
    Leads who don't engage gradually get lower scores
    """
    try:
        logger.info("Updating engagement scores")
        
        # Decay scores for leads with no activity in 30 days
        inactive_threshold = datetime.utcnow() - timedelta(days=30)
        
        inactive_leads = Lead.query.filter(
            Lead.last_contact < inactive_threshold,
            Lead.engagement_score > 0
        ).all()
        
        for lead in inactive_leads:
            # Decay by 10% per month of inactivity
            months_inactive = (datetime.utcnow() - lead.last_contact).days / 30
            decay_factor = 0.9 ** months_inactive
            
            lead.engagement_score = int(lead.engagement_score * decay_factor)
            
            # Move to dormant if score drops too low
            if lead.engagement_score < 10 and lead.status == 'active':
                lead.status = 'nurture'
        
        db.session.commit()
        
        logger.info(f"Updated engagement scores for {len(inactive_leads)} leads")
        return {'updated': len(inactive_leads)}
        
    except Exception as e:
        logger.error(f"Error updating engagement scores: {e}")
        db.session.rollback()
        return {'status': 'error', 'error': str(e)}


@celery.task
def send_weekly_digest(lead_id):
    """
    Send a weekly digest of new matches to a lead
    For leads who prefer batched updates over immediate alerts
    
    Args:
        lead_id: ID of the lead
    """
    try:
        from app.models import Match
        
        logger.info(f"Sending weekly digest to lead {lead_id}")
        
        # Get matches from the past week that weren't sent immediately
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        matches = Match.query.filter(
            Match.lead_id == lead_id,
            Match.created_at >= week_ago,
            Match.status == 'pending',
            Match.match_score < 70  # Only include medium matches (high ones were sent immediately)
        ).order_by(Match.match_score.desc()).limit(5).all()
        
        if not matches:
            logger.info(f"No matches to include in weekly digest for lead {lead_id}")
            return {'status': 'no_matches'}
        
        # TODO: Implement digest email template
        # For now, just send individual alerts
        for match in matches:
            send_listing_alert.delay(match.id)
        
        return {
            'status': 'success',
            'lead_id': lead_id,
            'matches_sent': len(matches)
        }
        
    except Exception as e:
        logger.error(f"Error sending weekly digest to lead {lead_id}: {e}")
        return {'status': 'error', 'error': str(e)}


# Import to avoid circular dependency
from app.tasks.mls_tasks import send_listing_alert
