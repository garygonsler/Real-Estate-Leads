from flask import Blueprint, jsonify
import logging
from datetime import datetime, timedelta
from sqlalchemy import func

from app.database import db
from app.models import Lead, Listing, Match, NurtureTouch

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')


@dashboard_bp.route('/stats')
def get_stats():
    """Get overall system statistics"""
    try:
        # Lead stats
        total_leads = Lead.query.count()
        active_leads = Lead.query.filter_by(status='active').count()
        nurture_leads = Lead.query.filter_by(status='nurture').count()
        converted_leads = Lead.query.filter_by(status='converted').count()
        
        # Listing stats
        active_listings = Listing.query.filter_by(status='Active').count()
        
        # Match stats - today
        today = datetime.utcnow().date()
        matches_today = Match.query.filter(
            func.date(Match.created_at) == today
        ).count()
        
        matches_sent_today = Match.query.filter(
            func.date(Match.sent_at) == today
        ).count()
        
        # Engagement stats - last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        emails_sent_7d = NurtureTouch.query.filter(
            NurtureTouch.sent_at >= week_ago
        ).count()
        
        emails_opened_7d = NurtureTouch.query.filter(
            NurtureTouch.sent_at >= week_ago,
            NurtureTouch.opened_at.isnot(None)
        ).count()
        
        emails_clicked_7d = NurtureTouch.query.filter(
            NurtureTouch.sent_at >= week_ago,
            NurtureTouch.clicked_at.isnot(None)
        ).count()
        
        open_rate = (emails_opened_7d / emails_sent_7d * 100) if emails_sent_7d > 0 else 0
        click_rate = (emails_clicked_7d / emails_sent_7d * 100) if emails_sent_7d > 0 else 0
        
        return jsonify({
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
                'created_today': matches_today,
                'sent_today': matches_sent_today
            },
            'engagement': {
                'emails_sent_7d': emails_sent_7d,
                'emails_opened_7d': emails_opened_7d,
                'emails_clicked_7d': emails_clicked_7d,
                'open_rate': round(open_rate, 2),
                'click_rate': round(click_rate, 2)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/recent-matches')
def get_recent_matches():
    """Get recent matches"""
    try:
        limit = request.args.get('limit', 20, type=int)
        
        matches = Match.query.order_by(
            Match.created_at.desc()
        ).limit(limit).all()
        
        result = [{
            'id': m.id,
            'lead': {
                'id': m.lead.id,
                'name': m.lead.full_name,
                'email': m.lead.email
            },
            'listing': {
                'id': m.listing.id,
                'address': m.listing.address,
                'city': m.listing.city,
                'price': float(m.listing.price),
                'bedrooms': m.listing.bedrooms,
                'bathrooms': float(m.listing.bathrooms) if m.listing.bathrooms else None
            },
            'match_score': m.match_score,
            'status': m.status,
            'created_at': m.created_at.isoformat(),
            'sent_at': m.sent_at.isoformat() if m.sent_at else None,
            'opened_at': m.opened_at.isoformat() if m.opened_at else None
        } for m in matches]
        
        return jsonify({'matches': result})
        
    except Exception as e:
        logger.error(f"Error getting recent matches: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/engagement-timeline')
def get_engagement_timeline():
    """Get engagement metrics over time"""
    try:
        days = request.args.get('days', 30, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Group by date
        daily_stats = db.session.query(
            func.date(NurtureTouch.sent_at).label('date'),
            func.count(NurtureTouch.id).label('sent'),
            func.sum(func.cast(NurtureTouch.opened_at.isnot(None), db.Integer)).label('opened'),
            func.sum(func.cast(NurtureTouch.clicked_at.isnot(None), db.Integer)).label('clicked')
        ).filter(
            NurtureTouch.sent_at >= start_date
        ).group_by(
            func.date(NurtureTouch.sent_at)
        ).order_by(
            func.date(NurtureTouch.sent_at)
        ).all()
        
        timeline = [{
            'date': stat.date.isoformat(),
            'sent': stat.sent,
            'opened': stat.opened or 0,
            'clicked': stat.clicked or 0,
            'open_rate': round((stat.opened or 0) / stat.sent * 100, 2) if stat.sent > 0 else 0
        } for stat in daily_stats]
        
        return jsonify({'timeline': timeline})
        
    except Exception as e:
        logger.error(f"Error getting engagement timeline: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/top-performing-leads')
def get_top_performing_leads():
    """Get leads with highest engagement scores"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        leads = Lead.query.filter(
            Lead.status.in_(['active', 'nurture'])
        ).order_by(
            Lead.engagement_score.desc()
        ).limit(limit).all()
        
        result = [{
            'id': lead.id,
            'name': lead.full_name,
            'email': lead.email,
            'engagement_score': lead.engagement_score,
            'status': lead.status,
            'last_contact': lead.last_contact.isoformat() if lead.last_contact else None,
            'matches_count': lead.matches.count()
        } for lead in leads]
        
        return jsonify({'leads': result})
        
    except Exception as e:
        logger.error(f"Error getting top leads: {e}")
        return jsonify({'error': str(e)}), 500


# Import at bottom
from flask import request
