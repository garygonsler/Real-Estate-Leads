import requests
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import logging
from requests.auth import HTTPBasicAuth

from app.models import Listing, ListingHistory
from app.database import db
from config.config import Config

logger = logging.getLogger(__name__)


class MLSSync:
    """
    MLS Data Synchronization Service
    
    This example uses SimplyRETS API format, but can be adapted
    for other MLS providers (RETS, RESO Web API, etc.)
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None, api_url: str = None):
        self.api_key = api_key or Config.MLS_API_KEY
        self.api_secret = api_secret or Config.MLS_API_SECRET
        self.api_url = api_url or Config.MLS_API_URL
        self.auth = HTTPBasicAuth(self.api_key, self.api_secret)
    
    def fetch_new_listings(self, hours_back: int = 24) -> List[Listing]:
        """
        Fetch listings added/updated in the last X hours
        
        Args:
            hours_back: How many hours back to search
            
        Returns:
            List of new/updated Listing objects
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
            
            # SimplyRETS API endpoint
            url = f"{self.api_url}/properties"
            
            params = {
                'status': 'Active',
                'minlistdate': cutoff_time.strftime('%Y-%m-%d'),
                'limit': 500,
                'lastId': 0  # For pagination
            }
            
            logger.info(f"Fetching listings from MLS since {cutoff_time}")
            
            response = requests.get(url, auth=self.auth, params=params, timeout=30)
            response.raise_for_status()
            
            listings_data = response.json()
            logger.info(f"Received {len(listings_data)} listings from MLS")
            
            new_listings = []
            for listing_data in listings_data:
                listing = self.upsert_listing(listing_data)
                if listing:
                    new_listings.append(listing)
            
            return new_listings
            
        except requests.RequestException as e:
            logger.error(f"Error fetching MLS listings: {e}")
            return []
    
    def fetch_listing_by_mls_id(self, mls_id: str) -> Optional[Listing]:
        """Fetch a specific listing by MLS ID"""
        try:
            url = f"{self.api_url}/properties/{mls_id}"
            response = requests.get(url, auth=self.auth, timeout=30)
            response.raise_for_status()
            
            listing_data = response.json()
            return self.upsert_listing(listing_data)
            
        except requests.RequestException as e:
            logger.error(f"Error fetching listing {mls_id}: {e}")
            return None
    
    def upsert_listing(self, data: Dict) -> Optional[Listing]:
        """
        Insert or update listing in database
        
        Args:
            data: Raw MLS listing data
            
        Returns:
            Listing object or None
        """
        try:
            mls_id = data.get('mlsId') or data.get('listingId')
            if not mls_id:
                logger.warning("Listing data missing MLS ID, skipping")
                return None
            
            # Check if listing exists
            listing = Listing.query.filter_by(mls_id=mls_id).first()
            
            # Parse listing data
            parsed_data = self._parse_listing_data(data)
            
            if listing:
                # Track price changes
                if listing.price != parsed_data['price']:
                    self._record_price_change(listing, parsed_data['price'])
                
                # Track status changes
                if listing.status != parsed_data['status']:
                    self._record_status_change(listing, parsed_data['status'])
                
                # Update existing listing
                for key, value in parsed_data.items():
                    setattr(listing, key, value)
                
                listing.last_synced = datetime.utcnow()
                listing.updated_at = datetime.utcnow()
                
                logger.debug(f"Updated listing {mls_id}")
            else:
                # Create new listing
                listing = Listing(**parsed_data)
                listing.last_synced = datetime.utcnow()
                db.session.add(listing)
                
                logger.info(f"Created new listing {mls_id}")
            
            db.session.commit()
            
            # Calculate derived fields
            listing.calculate_price_per_sqft()
            
            return listing
            
        except Exception as e:
            logger.error(f"Error upserting listing: {e}")
            db.session.rollback()
            return None
    
    def _parse_listing_data(self, data: Dict) -> Dict:
        """
        Parse raw MLS data into our schema
        
        Note: Field names vary by MLS provider. Adjust as needed.
        """
        # Address info
        address_data = data.get('address', {})
        geo_data = data.get('geo', {})
        property_data = data.get('property', {})
        
        parsed = {
            'mls_id': data.get('mlsId') or data.get('listingId'),
            'mls_source': data.get('mls', 'SimplyRETS'),
            
            # Address
            'address': address_data.get('full') or address_data.get('streetName'),
            'city': address_data.get('city'),
            'state': address_data.get('state'),
            'zip_code': address_data.get('postalCode'),
            'latitude': geo_data.get('lat'),
            'longitude': geo_data.get('lng'),
            
            # Price
            'price': data.get('listPrice'),
            'original_price': data.get('originalListPrice') or data.get('listPrice'),
            
            # Property details
            'bedrooms': property_data.get('bedrooms') or data.get('bedrooms'),
            'bathrooms': property_data.get('bathsFull') or data.get('bathrooms'),
            'sqft': property_data.get('area') or data.get('sqft'),
            'lot_size': property_data.get('lotSize'),
            'year_built': property_data.get('yearBuilt'),
            
            # Type
            'property_type': property_data.get('type') or data.get('propertyType'),
            'property_subtype': property_data.get('subType') or data.get('propertySubType'),
            
            # Features
            'garage_spaces': property_data.get('garageSpaces'),
            'stories': property_data.get('stories'),
            'pool': property_data.get('pool', False),
            
            # Listing details
            'listing_date': self._parse_date(data.get('listDate')),
            'status': data.get('mls', {}).get('status') or data.get('status', 'Active'),
            'status_date': self._parse_date(data.get('mls', {}).get('statusDate')),
            'days_on_market': data.get('mls', {}).get('daysOnMarket'),
            
            # Description & media
            'description': data.get('remarks') or data.get('description'),
            'photos': data.get('photos', []),
            'virtual_tour_url': data.get('virtualTourUrl'),
            
            # HOA
            'hoa_fee': data.get('association', {}).get('fee'),
            'hoa_frequency': data.get('association', {}).get('feeFrequency'),
            
            # Schools
            'elementary_school': data.get('school', {}).get('elementarySchool'),
            'middle_school': data.get('school', {}).get('middleSchool'),
            'high_school': data.get('school', {}).get('highSchool'),
            'school_district': data.get('school', {}).get('district'),
            
            # Agent
            'listing_agent_name': data.get('agent', {}).get('name') or 
                                 f"{data.get('agent', {}).get('firstName', '')} {data.get('agent', {}).get('lastName', '')}".strip(),
            'listing_agent_phone': data.get('agent', {}).get('contact'),
            'listing_office': data.get('office', {}).get('name'),
            
            # Raw data for reference
            'raw_data': data
        }
        
        # Remove None values
        return {k: v for k, v in parsed.items() if v is not None}
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime"""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None
    
    def _record_price_change(self, listing: Listing, new_price: float):
        """Record price change in history"""
        history = ListingHistory(
            listing_id=listing.id,
            change_type='price_change',
            old_value=str(listing.price),
            new_value=str(new_price),
            changed_at=datetime.utcnow()
        )
        db.session.add(history)
        logger.info(f"Price change for {listing.mls_id}: ${listing.price} -> ${new_price}")
    
    def _record_status_change(self, listing: Listing, new_status: str):
        """Record status change in history"""
        history = ListingHistory(
            listing_id=listing.id,
            change_type='status_change',
            old_value=listing.status,
            new_value=new_status,
            changed_at=datetime.utcnow()
        )
        db.session.add(history)
        logger.info(f"Status change for {listing.mls_id}: {listing.status} -> {new_status}")
    
    def cleanup_old_listings(self, days: int = 90):
        """Remove sold/expired listings older than X days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        old_listings = Listing.query.filter(
            Listing.status.in_(['Sold', 'Expired', 'Withdrawn']),
            Listing.status_date < cutoff_date
        ).all()
        
        for listing in old_listings:
            db.session.delete(listing)
        
        db.session.commit()
        logger.info(f"Cleaned up {len(old_listings)} old listings")
