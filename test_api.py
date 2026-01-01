import pytest
from datetime import datetime

from app.main import create_app
from app.database import db
from app.models import Lead, BuyerCriteria, Listing, Match
from app.services.matching import MatchingEngine


@pytest.fixture
def app():
    """Create application for testing"""
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


class TestLeadAPI:
    """Test Lead API endpoints"""
    
    def test_create_lead(self, client):
        """Test creating a new lead"""
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'phone': '555-1234',
            'criteria': {
                'min_price': 300000,
                'max_price': 500000,
                'bedrooms': 3,
                'bathrooms': 2,
                'locations': ['Austin'],
                'must_haves': 'home office'
            }
        }
        
        response = client.post('/api/leads/', json=data)
        
        assert response.status_code == 201
        assert 'id' in response.json
        assert response.json['email'] == 'john@example.com'
    
    def test_get_leads(self, client, app):
        """Test getting all leads"""
        with app.app_context():
            # Create test lead
            lead = Lead(
                first_name='Jane',
                last_name='Smith',
                email='jane@example.com',
                status='active'
            )
            db.session.add(lead)
            db.session.commit()
        
        response = client.get('/api/leads/')
        
        assert response.status_code == 200
        assert len(response.json['leads']) > 0


class TestMatchingEngine:
    """Test matching engine logic"""
    
    def test_basic_matching(self, app):
        """Test basic listing to buyer matching"""
        with app.app_context():
            # Create lead with criteria
            lead = Lead(
                first_name='Test',
                last_name='Buyer',
                email='buyer@test.com',
                status='active'
            )
            db.session.add(lead)
            db.session.flush()
            
            criteria = BuyerCriteria(
                lead_id=lead.id,
                min_price=300000,
                max_price=500000,
                bedrooms=3,
                bathrooms=2,
                location_preferences=['Austin']
            )
            db.session.add(criteria)
            
            # Create matching listing
            listing = Listing(
                mls_id='TEST123',
                address='123 Main St',
                city='Austin',
                state='TX',
                zip_code='78701',
                price=400000,
                bedrooms=3,
                bathrooms=2,
                sqft=2000,
                property_type='single-family',
                status='Active',
                listing_date=datetime.utcnow()
            )
            db.session.add(listing)
            db.session.commit()
            
            # Run matching
            matcher = MatchingEngine()
            matches = matcher.find_matches_for_listing(listing.id)
            
            assert len(matches) == 1
            assert matches[0].match_score >= 60
    
    def test_price_filtering(self, app):
        """Test that listings outside price range don't match"""
        with app.app_context():
            # Create lead
            lead = Lead(
                first_name='Test',
                last_name='Buyer',
                email='buyer@test.com',
                status='active'
            )
            db.session.add(lead)
            db.session.flush()
            
            # Budget: $300K - $500K
            criteria = BuyerCriteria(
                lead_id=lead.id,
                min_price=300000,
                max_price=500000,
                bedrooms=3
            )
            db.session.add(criteria)
            
            # Listing: $600K (too expensive)
            listing = Listing(
                mls_id='EXPENSIVE',
                address='456 Rich Ave',
                city='Austin',
                state='TX',
                zip_code='78701',
                price=600000,  # Outside budget
                bedrooms=3,
                bathrooms=2,
                sqft=3000,
                property_type='single-family',
                status='Active',
                listing_date=datetime.utcnow()
            )
            db.session.add(listing)
            db.session.commit()
            
            # Run matching
            matcher = MatchingEngine()
            matches = matcher.find_matches_for_listing(listing.id)
            
            # Should not match
            assert len(matches) == 0


class TestDashboardAPI:
    """Test dashboard endpoints"""
    
    def test_get_stats(self, client, app):
        """Test getting dashboard stats"""
        with app.app_context():
            # Create some test data
            lead = Lead(
                first_name='Test',
                last_name='User',
                email='test@example.com',
                status='active'
            )
            db.session.add(lead)
            db.session.commit()
        
        response = client.get('/api/dashboard/stats')
        
        assert response.status_code == 200
        assert 'leads' in response.json
        assert 'matches' in response.json
        assert 'engagement' in response.json


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
