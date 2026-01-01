from flask import Blueprint, request, redirect, jsonify
import logging
from datetime import datetime

from app.database import db
from app.models import Match, NurtureTouch

logger = logging.getLogger(__name__)

tracking_bp = Blueprint('tracking', __name__, url_prefix='/track')


@tracking_bp.route('/<int:match_id>/listing_view')
def track_listing_view(match_id):
    """
    Track when a user clicks to view a listing
    Redirects to the actual listing page
    """
    try:
        match = Match.query.get(match_id)
        
        if match:
            # Mark as clicked
            match.mark_clicked()
            
            logger.info(f"Tracked listing view for match {match_id}")
            
            # Redirect to listing (you'd integrate with your listing detail page)
            listing_url = f"/listings/{match.listing.mls_id}"
            return redirect(listing_url)
        else:
            logger.warning(f"Match {match_id} not found for tracking")
            return redirect('/')
            
    except Exception as e:
        logger.error(f"Error tracking listing view: {e}")
        return redirect('/')


@tracking_bp.route('/<int:match_id>/schedule_showing')
def track_schedule_showing(match_id):
    """
    Track when a user wants to schedule a showing
    """
    try:
        match = Match.query.get(match_id)
        
        if match:
            match.mark_clicked()
            match.status = 'showing_requested'
            match.responded_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Showing requested for match {match_id}")
            
            # Redirect to scheduling page
            return redirect(f"/schedule/{match_id}")
        else:
            return redirect('/')
            
    except Exception as e:
        logger.error(f"Error tracking showing request: {e}")
        return redirect('/')


@tracking_bp.route('/open/<message_id>')
def track_email_open(message_id):
    """
    Track email opens via tracking pixel
    
    Returns a 1x1 transparent GIF
    """
    try:
        # Find the nurture touch by message ID
        touch = NurtureTouch.query.filter_by(message_id=message_id).first()
        
        if touch:
            touch.mark_opened()
            logger.debug(f"Email opened: message {message_id}")
        
        # Also check for matches
        match = Match.query.filter_by(message_id=message_id).first()
        if match:
            match.mark_opened()
        
        # Return 1x1 transparent GIF
        from flask import Response
        import base64
        
        # 1x1 transparent GIF in base64
        gif_data = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
        
        return Response(gif_data, mimetype='image/gif')
        
    except Exception as e:
        logger.error(f"Error tracking email open: {e}")
        # Still return the pixel
        from flask import Response
        import base64
        gif_data = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
        return Response(gif_data, mimetype='image/gif')


@tracking_bp.route('/unsubscribe/<int:lead_id>')
def unsubscribe(lead_id):
    """
    Unsubscribe a lead from emails
    """
    try:
        from app.models import Lead
        
        lead = Lead.query.get(lead_id)
        
        if lead:
            lead.status = 'unsubscribed'
            db.session.commit()
            
            logger.info(f"Lead {lead_id} unsubscribed")
            
            return """
            <html>
            <head><title>Unsubscribed</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>You've been unsubscribed</h1>
                <p>You will no longer receive emails from us.</p>
                <p>If this was a mistake, please contact us.</p>
            </body>
            </html>
            """
        else:
            return "Lead not found", 404
            
    except Exception as e:
        logger.error(f"Error unsubscribing lead {lead_id}: {e}")
        return "An error occurred", 500
