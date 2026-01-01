from flask import Blueprint, request, jsonify
import logging
from datetime import datetime

from app.database import db
from app.models import Lead, BuyerCriteria, Agent
from app.tasks.mls_tasks import bulk_match_buyer

logger = logging.getLogger(__name__)

leads_bp = Blueprint('leads', __name__, url_prefix='/api/leads')


@leads_bp.route('/', methods=['GET'])
def get_leads():
    """Get all leads with optional filtering"""
    try:
        # Query parameters
        status = request.args.get('status')
        agent_id = request.args.get('agent_id', type=int)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Build query
        query = Lead.query
        
        if status:
            query = query.filter_by(status=status)
        
        if agent_id:
            query = query.filter_by(assigned_agent_id=agent_id)
        
        # Paginate
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        leads = [{
            'id': lead.id,
            'name': lead.full_name,
            'email': lead.email,
            'phone': lead.phone,
            'status': lead.status,
            'engagement_score': lead.engagement_score,
            'last_contact': lead.last_contact.isoformat() if lead.last_contact else None,
            'created_at': lead.created_at.isoformat()
        } for lead in pagination.items]
        
        return jsonify({
            'leads': leads,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        })
        
    except Exception as e:
        logger.error(f"Error getting leads: {e}")
        return jsonify({'error': str(e)}), 500


@leads_bp.route('/<int:lead_id>', methods=['GET'])
def get_lead(lead_id):
    """Get detailed information for a specific lead"""
    try:
        lead = Lead.query.get_or_404(lead_id)
        
        # Get recent matches
        recent_matches = [{
            'id': m.id,
            'listing_address': m.listing.address,
            'listing_price': float(m.listing.price),
            'match_score': m.match_score,
            'status': m.status,
            'sent_at': m.sent_at.isoformat() if m.sent_at else None,
            'opened_at': m.opened_at.isoformat() if m.opened_at else None
        } for m in lead.matches.order_by(Match.created_at.desc()).limit(10)]
        
        # Get recent touches
        recent_touches = [{
            'id': t.id,
            'touch_type': t.touch_type,
            'sent_at': t.sent_at.isoformat(),
            'opened_at': t.opened_at.isoformat() if t.opened_at else None,
            'clicked': t.clicked_at is not None
        } for t in lead.nurture_touches.order_by(NurtureTouch.sent_at.desc()).limit(10)]
        
        criteria_data = None
        if lead.criteria:
            criteria_data = {
                'price_range': {
                    'min': float(lead.criteria.min_price) if lead.criteria.min_price else None,
                    'max': float(lead.criteria.max_price) if lead.criteria.max_price else None
                },
                'bedrooms': lead.criteria.bedrooms,
                'bathrooms': float(lead.criteria.bathrooms) if lead.criteria.bathrooms else None,
                'locations': lead.criteria.location_preferences,
                'property_types': lead.criteria.property_types,
                'must_haves': lead.criteria.must_haves,
                'timeline': lead.criteria.timeline
            }
        
        return jsonify({
            'id': lead.id,
            'name': lead.full_name,
            'email': lead.email,
            'phone': lead.phone,
            'status': lead.status,
            'engagement_score': lead.engagement_score,
            'last_contact': lead.last_contact.isoformat() if lead.last_contact else None,
            'source': lead.source,
            'created_at': lead.created_at.isoformat(),
            'criteria': criteria_data,
            'recent_matches': recent_matches,
            'recent_touches': recent_touches,
            'assigned_agent': {
                'id': lead.agent.id,
                'name': lead.agent.full_name
            } if lead.agent else None
        })
        
    except Exception as e:
        logger.error(f"Error getting lead {lead_id}: {e}")
        return jsonify({'error': str(e)}), 500


@leads_bp.route('/', methods=['POST'])
def create_lead():
    """Create a new lead"""
    try:
        data = request.get_json()
        
        # Check if lead with email already exists
        existing_lead = Lead.query.filter_by(email=data['email']).first()
        if existing_lead:
            return jsonify({'error': 'Lead with this email already exists'}), 400
        
        # Create lead
        lead = Lead(
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data['email'],
            phone=data.get('phone'),
            source=data.get('source', 'manual'),
            status='active'
        )
        
        db.session.add(lead)
        db.session.flush()  # Get the lead ID
        
        # Create buyer criteria if provided
        if 'criteria' in data:
            criteria_data = data['criteria']
            criteria = BuyerCriteria(
                lead_id=lead.id,
                min_price=criteria_data.get('min_price'),
                max_price=criteria_data.get('max_price'),
                bedrooms=criteria_data.get('bedrooms'),
                bathrooms=criteria_data.get('bathrooms'),
                location_preferences=criteria_data.get('locations', []),
                property_types=criteria_data.get('property_types', []),
                must_haves=criteria_data.get('must_haves'),
                timeline=criteria_data.get('timeline')
            )
            db.session.add(criteria)
        
        db.session.commit()
        
        # Trigger initial matching
        if lead.criteria:
            bulk_match_buyer.delay(lead.id, send_top_matches=True)
        
        logger.info(f"Created new lead {lead.id}: {lead.email}")
        
        return jsonify({
            'id': lead.id,
            'email': lead.email,
            'message': 'Lead created successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating lead: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@leads_bp.route('/<int:lead_id>', methods=['PUT'])
def update_lead(lead_id):
    """Update an existing lead"""
    try:
        lead = Lead.query.get_or_404(lead_id)
        data = request.get_json()
        
        # Update basic fields
        if 'first_name' in data:
            lead.first_name = data['first_name']
        if 'last_name' in data:
            lead.last_name = data['last_name']
        if 'phone' in data:
            lead.phone = data['phone']
        if 'status' in data:
            lead.status = data['status']
        
        # Update criteria if provided
        if 'criteria' in data:
            criteria_data = data['criteria']
            
            if lead.criteria:
                # Update existing criteria
                criteria = lead.criteria
            else:
                # Create new criteria
                criteria = BuyerCriteria(lead_id=lead.id)
                db.session.add(criteria)
            
            if 'min_price' in criteria_data:
                criteria.min_price = criteria_data['min_price']
            if 'max_price' in criteria_data:
                criteria.max_price = criteria_data['max_price']
            if 'bedrooms' in criteria_data:
                criteria.bedrooms = criteria_data['bedrooms']
            if 'bathrooms' in criteria_data:
                criteria.bathrooms = criteria_data['bathrooms']
            if 'locations' in criteria_data:
                criteria.location_preferences = criteria_data['locations']
            if 'property_types' in criteria_data:
                criteria.property_types = criteria_data['property_types']
            if 'must_haves' in criteria_data:
                criteria.must_haves = criteria_data['must_haves']
            if 'timeline' in criteria_data:
                criteria.timeline = criteria_data['timeline']
        
        db.session.commit()
        
        # Re-run matching if criteria changed
        if 'criteria' in data:
            bulk_match_buyer.delay(lead.id, send_top_matches=False)
        
        logger.info(f"Updated lead {lead_id}")
        
        return jsonify({
            'id': lead.id,
            'message': 'Lead updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating lead {lead_id}: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@leads_bp.route('/<int:lead_id>', methods=['DELETE'])
def delete_lead(lead_id):
    """Delete a lead"""
    try:
        lead = Lead.query.get_or_404(lead_id)
        
        db.session.delete(lead)
        db.session.commit()
        
        logger.info(f"Deleted lead {lead_id}")
        
        return jsonify({'message': 'Lead deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting lead {lead_id}: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# Import at bottom to avoid circular dependency
from app.models import Match, NurtureTouch
