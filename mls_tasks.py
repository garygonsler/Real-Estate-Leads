import logging
from datetime import datetime

from app.celery_app import celery
from app.database import db
from app.models import Listing
from app.services.mls_sync import MLSSync
from app.services.matching import MatchingEngine
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3)
def sync_mls_listings(self):
    """
    Periodic task to sync MLS listings
    Runs every hour to fetch new/updated listings
    """
    try:
        logger.info("Starting MLS sync task")
        
        mls = MLSSync()
        new_listings = mls.fetch_new_listings(hours_back=2)  # Extra hour for overlap
        
        logger.info(f"Synced {len(new_listings)} listings from MLS")
        
        # Trigger matching for each new listing
        for listing in new_listings:
            match_listing_to_buyers.delay(listing.id)
        
        return {
            'status': 'success',
            'listings_synced': len(new_listings),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in MLS sync task: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@celery.task(bind=True, max_retries=2)
def match_listing_to_buyers(self, listing_id):
    """
    Find buyers that match a specific listing
    
    Args:
        listing_id: ID of the listing to match
    """
    try:
        logger.info(f"Finding matches for listing {listing_id}")
        
        matcher = MatchingEngine()
        matches = matcher.find_matches_for_listing(listing_id)
        
        logger.info(f"Found {len(matches)} matches for listing {listing_id}")
        
        # Send alerts for high-quality matches
        for match in matches:
            if match.match_score >= 70:  # High-quality matches get immediate alerts
                send_listing_alert.delay(match.id)
            # Medium matches (60-69) might be batched in daily digest
        
        return {
            'status': 'success',
            'listing_id': listing_id,
            'matches_found': len(matches)
        }
        
    except Exception as e:
        logger.error(f"Error matching listing {listing_id}: {e}")
        raise self.retry(exc=e, countdown=120)


@celery.task(bind=True, max_retries=3)
def send_listing_alert(self, match_id):
    """
    Send email alert for a specific match
    
    Args:
        match_id: ID of the match
    """
    try:
        logger.info(f"Sending listing alert for match {match_id}")
        
        email_service = EmailService()
        success = email_service.send_listing_alert(match_id)
        
        if not success:
            raise Exception(f"Failed to send alert for match {match_id}")
        
        return {
            'status': 'success',
            'match_id': match_id,
            'sent_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error sending listing alert for match {match_id}: {e}")
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes


@celery.task
def bulk_match_buyer(lead_id, send_top_matches=True):
    """
    Find matches for a specific buyer
    Useful when a new buyer is added or updates their criteria
    
    Args:
        lead_id: ID of the lead/buyer
        send_top_matches: Whether to send alerts for top matches
    """
    try:
        logger.info(f"Finding matches for buyer {lead_id}")
        
        matcher = MatchingEngine()
        matches = matcher.find_matches_for_buyer(lead_id, limit=20)
        
        logger.info(f"Found {len(matches)} matches for buyer {lead_id}")
        
        if send_top_matches:
            # Send alerts for top 3 matches
            top_matches = sorted(matches, key=lambda m: m.match_score, reverse=True)[:3]
            for match in top_matches:
                send_listing_alert.delay(match.id)
        
        return {
            'status': 'success',
            'lead_id': lead_id,
            'matches_found': len(matches)
        }
        
    except Exception as e:
        logger.error(f"Error in bulk match for buyer {lead_id}: {e}")
        return {'status': 'error', 'error': str(e)}


@celery.task
def refresh_listing(mls_id):
    """
    Refresh a specific listing from MLS
    
    Args:
        mls_id: MLS ID of the listing
    """
    try:
        logger.info(f"Refreshing listing {mls_id}")
        
        mls = MLSSync()
        listing = mls.fetch_listing_by_mls_id(mls_id)
        
        if listing:
            logger.info(f"Successfully refreshed listing {mls_id}")
            return {'status': 'success', 'listing_id': listing.id}
        else:
            logger.warning(f"Could not refresh listing {mls_id}")
            return {'status': 'not_found'}
            
    except Exception as e:
        logger.error(f"Error refreshing listing {mls_id}: {e}")
        return {'status': 'error', 'error': str(e)}
