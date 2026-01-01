import logging
from datetime import datetime, timedelta

from app.celery_app import celery
from app.database import db
from app.models import Listing, NurtureTouch, Match
from app.services.mls_sync import MLSSync

logger = logging.getLogger(__name__)


@celery.task
def cleanup_old_data():
    """
    Weekly cleanup of old data
    Runs every Sunday at 2 AM
    """
    try:
        logger.info("Starting weekly cleanup task")
        
        results = {
            'old_listings_removed': 0,
            'old_touches_archived': 0,
            'old_matches_removed': 0
        }
        
        # Remove sold/expired listings older than 90 days
        mls = MLSSync()
        mls.cleanup_old_listings(days=90)
        results['old_listings_removed'] = 'completed'
        
        # Archive old nurture touches (keep for 1 year for analytics)
        one_year_ago = datetime.utcnow() - timedelta(days=365)
        
        old_touches = NurtureTouch.query.filter(
            NurtureTouch.sent_at < one_year_ago
        ).delete()
        
        results['old_touches_archived'] = old_touches
        
        # Remove old unresponded matches (6 months)
        six_months_ago = datetime.utcnow() - timedelta(days=180)
        
        old_matches = Match.query.filter(
            Match.created_at < six_months_ago,
            Match.status.in_(['pending', 'sent', 'opened'])  # Not converted
        ).delete()
        
        results['old_matches_removed'] = old_matches
        
        db.session.commit()
        
        logger.info(f"Cleanup complete: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {e}")
        db.session.rollback()
        return {'status': 'error', 'error': str(e)}


@celery.task
def generate_analytics_report():
    """
    Generate weekly analytics report
    Track key metrics for the system
    """
    try:
        from app.models import Lead
        
        logger.info("Generating analytics report")
        
        # Calculate metrics
        total_leads = Lead.query.count()
        active_leads = Lead.query.filter_by(status='active').count()
        nurture_leads = Lead.query.filter_by(status='nurture').count()
        converted_leads = Lead.query.filter_by(status='converted').count()
        
        # Listings
        active_listings = Listing.query.filter_by(status='Active').count()
        
        # Matches in last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_matches = Match.query.filter(Match.created_at >= week_ago).count()
        
        # Engagement rates
        sent_this_week = NurtureTouch.query.filter(
            NurtureTouch.sent_at >= week_ago
        ).count()
        
        opened_this_week = NurtureTouch.query.filter(
            NurtureTouch.sent_at >= week_ago,
            NurtureTouch.opened_at.isnot(None)
        ).count()
        
        open_rate = (opened_this_week / sent_this_week * 100) if sent_this_week > 0 else 0
        
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'leads': {
                'total': total_leads,
                'active': active_leads,
                'nurture': nurture_leads,
                'converted': converted_leads
            },
            'listings': {
                'active': active_listings
            },
            'matches': {
                'last_7_days': recent_matches
            },
            'engagement': {
                'emails_sent_7d': sent_this_week,
                'emails_opened_7d': opened_this_week,
                'open_rate': round(open_rate, 2)
            }
        }
        
        logger.info(f"Analytics report: {report}")
        
        # TODO: Save to analytics table or send to admin
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating analytics: {e}")
        return {'status': 'error', 'error': str(e)}


@celery.task
def sync_crm_data():
    """
    Sync data with CRM system
    Pull new leads from CRM and push activity back
    """
    try:
        from app.services.crm_sync import CRMSync
        
        logger.info("Starting CRM sync")
        
        crm = CRMSync()
        
        # Pull new leads from CRM
        new_leads = crm.sync_leads()
        
        # Push recent activity back to CRM
        recent_matches = Match.query.filter(
            Match.sent_at >= datetime.utcnow() - timedelta(days=1),
            Match.sent_at.isnot(None)
        ).all()
        
        for match in recent_matches:
            crm.push_activity(
                lead_id=match.lead_id,
                activity_type='listing_alert_sent',
                details=f"Sent listing alert for {match.listing.address}"
            )
        
        logger.info(f"CRM sync complete: {len(new_leads)} leads synced")
        return {
            'status': 'success',
            'leads_synced': len(new_leads),
            'activities_pushed': len(recent_matches)
        }
        
    except Exception as e:
        logger.error(f"Error syncing CRM: {e}")
        return {'status': 'error', 'error': str(e)}
