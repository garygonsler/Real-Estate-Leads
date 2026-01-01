from typing import List, Tuple, Optional
import logging
from sqlalchemy import and_, or_

from app.models import Listing, BuyerCriteria, Lead, Match
from app.database import db
from app.services.llm_service import LLMService
from config.config import Config

logger = logging.getLogger(__name__)


class MatchingEngine:
    """
    Intelligent matching engine that connects listings to buyers
    """
    
    def __init__(self):
        self.llm = LLMService()
        self.score_threshold = Config.MATCH_SCORE_THRESHOLD
    
    def find_matches_for_listing(self, listing_id: int) -> List[Match]:
        """
        Find all buyers that match a given listing
        
        Args:
            listing_id: ID of the listing to match
            
        Returns:
            List of Match objects for qualifying buyers
        """
        listing = Listing.query.get(listing_id)
        if not listing:
            logger.warning(f"Listing {listing_id} not found")
            return []
        
        logger.info(f"Finding matches for listing {listing.mls_id}")
        
        # Get potential buyers based on basic criteria
        potential_buyers = self._get_potential_buyers(listing)
        
        matches = []
        for criteria in potential_buyers:
            score, reasons = self.calculate_match_score(listing, criteria)
            
            if score >= self.score_threshold:
                match = self._create_match(listing, criteria, score, reasons)
                matches.append(match)
                logger.debug(f"Match created: Lead {criteria.lead_id}, Score {score}")
        
        logger.info(f"Found {len(matches)} matches for listing {listing.mls_id}")
        return matches
    
    def find_matches_for_buyer(self, lead_id: int, limit: int = 10) -> List[Match]:
        """
        Find listings that match a buyer's criteria
        
        Args:
            lead_id: ID of the lead/buyer
            limit: Maximum number of matches to return
            
        Returns:
            List of Match objects
        """
        lead = Lead.query.get(lead_id)
        if not lead or not lead.criteria:
            logger.warning(f"Lead {lead_id} not found or has no criteria")
            return []
        
        criteria = lead.criteria
        
        # Get potential listings
        potential_listings = self._get_potential_listings(criteria)
        
        matches = []
        for listing in potential_listings:
            score, reasons = self.calculate_match_score(listing, criteria)
            
            if score >= self.score_threshold:
                match = self._create_match(listing, criteria, score, reasons)
                matches.append(match)
        
        # Sort by score, return top matches
        matches.sort(key=lambda m: m.match_score, reverse=True)
        return matches[:limit]
    
    def _get_potential_buyers(self, listing: Listing) -> List[BuyerCriteria]:
        """
        Get buyers whose basic criteria match this listing
        """
        # Build query based on listing attributes
        query = BuyerCriteria.query.join(Lead).filter(
            Lead.status.in_(['active', 'nurture'])
        )
        
        # Price range filter
        if listing.price:
            query = query.filter(
                or_(
                    BuyerCriteria.min_price.is_(None),
                    BuyerCriteria.min_price <= listing.price
                ),
                or_(
                    BuyerCriteria.max_price.is_(None),
                    BuyerCriteria.max_price >= listing.price
                )
            )
        
        # Bedroom filter
        if listing.bedrooms:
            query = query.filter(
                or_(
                    BuyerCriteria.bedrooms.is_(None),
                    BuyerCriteria.bedrooms <= listing.bedrooms
                )
            )
        
        # Bathroom filter
        if listing.bathrooms:
            query = query.filter(
                or_(
                    BuyerCriteria.bathrooms.is_(None),
                    BuyerCriteria.bathrooms <= listing.bathrooms
                )
            )
        
        # Location filter - check if listing city is in buyer's preferences
        if listing.city:
            query = query.filter(
                or_(
                    BuyerCriteria.location_preferences.is_(None),
                    BuyerCriteria.location_preferences.contains([listing.city])
                )
            )
        
        return query.all()
    
    def _get_potential_listings(self, criteria: BuyerCriteria) -> List[Listing]:
        """
        Get active listings that match basic criteria
        """
        query = Listing.query.filter(Listing.status == 'Active')
        
        # Price range
        if criteria.min_price:
            query = query.filter(Listing.price >= criteria.min_price)
        if criteria.max_price:
            query = query.filter(Listing.price <= criteria.max_price)
        
        # Bedrooms/bathrooms
        if criteria.bedrooms:
            query = query.filter(Listing.bedrooms >= criteria.bedrooms)
        if criteria.bathrooms:
            query = query.filter(Listing.bathrooms >= criteria.bathrooms)
        
        # Square footage
        if criteria.min_sqft:
            query = query.filter(Listing.sqft >= criteria.min_sqft)
        if criteria.max_sqft:
            query = query.filter(Listing.sqft <= criteria.max_sqft)
        
        # Location
        if criteria.location_preferences:
            query = query.filter(Listing.city.in_(criteria.location_preferences))
        
        # Property type
        if criteria.property_types:
            query = query.filter(Listing.property_type.in_(criteria.property_types))
        
        return query.all()
    
    def calculate_match_score(self, listing: Listing, criteria: BuyerCriteria) -> Tuple[int, List[str]]:
        """
        Calculate match score (0-100) and reasons
        
        Args:
            listing: Listing object
            criteria: BuyerCriteria object
            
        Returns:
            Tuple of (score, list of match reasons)
        """
        score = 0
        reasons = []
        
        # Price match (30 points max)
        price_score, price_reason = self._score_price(listing, criteria)
        score += price_score
        if price_reason:
            reasons.append(price_reason)
        
        # Bedrooms/bathrooms (20 points max)
        bed_bath_score, bed_bath_reason = self._score_bed_bath(listing, criteria)
        score += bed_bath_score
        if bed_bath_reason:
            reasons.append(bed_bath_reason)
        
        # Location (20 points max)
        location_score, location_reason = self._score_location(listing, criteria)
        score += location_score
        if location_reason:
            reasons.append(location_reason)
        
        # Property type (10 points max)
        type_score, type_reason = self._score_property_type(listing, criteria)
        score += type_score
        if type_reason:
            reasons.append(type_reason)
        
        # Semantic match on must-haves (20 points max)
        if criteria.must_haves and listing.description:
            semantic_score, semantic_reason = self._score_semantic_match(listing, criteria)
            score += semantic_score
            if semantic_reason:
                reasons.append(semantic_reason)
        
        return min(score, 100), reasons
    
    def _score_price(self, listing: Listing, criteria: BuyerCriteria) -> Tuple[int, str]:
        """Score price match"""
        if not listing.price:
            return 0, ""
        
        if criteria.min_price and listing.price < criteria.min_price:
            return 0, "Below minimum price"
        
        if criteria.max_price and listing.price > criteria.max_price:
            return 0, "Above maximum price"
        
        # Perfect match: in range
        if (not criteria.min_price or listing.price >= criteria.min_price) and \
           (not criteria.max_price or listing.price <= criteria.max_price):
            
            # Bonus if it's a good deal (lower third of range)
            if criteria.min_price and criteria.max_price:
                range_size = criteria.max_price - criteria.min_price
                if listing.price <= criteria.min_price + (range_size / 3):
                    return 30, f"Great value at ${listing.price:,.0f} (lower end of budget)"
            
            return 25, f"In budget at ${listing.price:,.0f}"
        
        return 0, ""
    
    def _score_bed_bath(self, listing: Listing, criteria: BuyerCriteria) -> Tuple[int, str]:
        """Score bedroom/bathroom match"""
        score = 0
        reason_parts = []
        
        if criteria.bedrooms and listing.bedrooms:
            if listing.bedrooms >= criteria.bedrooms:
                score += 10
                if listing.bedrooms == criteria.bedrooms:
                    reason_parts.append(f"{listing.bedrooms} bedrooms (exact match)")
                else:
                    reason_parts.append(f"{listing.bedrooms} bedrooms")
        
        if criteria.bathrooms and listing.bathrooms:
            if listing.bathrooms >= criteria.bathrooms:
                score += 10
                if listing.bathrooms == criteria.bathrooms:
                    reason_parts.append(f"{listing.bathrooms} bathrooms (exact match)")
                else:
                    reason_parts.append(f"{listing.bathrooms} bathrooms")
        
        reason = ", ".join(reason_parts) if reason_parts else ""
        return score, reason
    
    def _score_location(self, listing: Listing, criteria: BuyerCriteria) -> Tuple[int, str]:
        """Score location match"""
        if not listing.city:
            return 0, ""
        
        if criteria.location_preferences and listing.city in criteria.location_preferences:
            return 20, f"In preferred area ({listing.city})"
        
        # Check zip code match
        if criteria.zip_codes and listing.zip_code in criteria.zip_codes:
            return 20, f"In preferred zip code ({listing.zip_code})"
        
        return 0, ""
    
    def _score_property_type(self, listing: Listing, criteria: BuyerCriteria) -> Tuple[int, str]:
        """Score property type match"""
        if not listing.property_type:
            return 0, ""
        
        if criteria.property_types and listing.property_type in criteria.property_types:
            return 10, f"Preferred property type ({listing.property_type})"
        
        return 0, ""
    
    def _score_semantic_match(self, listing: Listing, criteria: BuyerCriteria) -> Tuple[int, str]:
        """Use LLM to check if listing meets special requirements"""
        try:
            score = self.llm.score_listing_match(
                listing_description=listing.description,
                must_haves=criteria.must_haves,
                nice_to_haves=criteria.nice_to_haves
            )
            
            if score >= 15:
                return score, "Matches special requirements"
            elif score >= 8:
                return score, "Partially matches special requirements"
            else:
                return 0, ""
                
        except Exception as e:
            logger.error(f"Error in semantic matching: {e}")
            return 0, ""
    
    def _create_match(self, listing: Listing, criteria: BuyerCriteria, 
                      score: int, reasons: List[str]) -> Match:
        """Create and save a match"""
        # Check if match already exists
        existing_match = Match.query.filter_by(
            lead_id=criteria.lead_id,
            listing_id=listing.id
        ).first()
        
        if existing_match:
            # Update existing match
            existing_match.match_score = score
            existing_match.match_reasons = "; ".join(reasons)
            existing_match.updated_at = db.func.now()
            db.session.commit()
            return existing_match
        
        # Create new match
        match = Match(
            lead_id=criteria.lead_id,
            listing_id=listing.id,
            match_score=score,
            match_reasons="; ".join(reasons),
            match_details={
                'price': float(listing.price) if listing.price else None,
                'bedrooms': listing.bedrooms,
                'bathrooms': float(listing.bathrooms) if listing.bathrooms else None,
                'city': listing.city,
                'property_type': listing.property_type
            },
            status='pending'
        )
        
        db.session.add(match)
        db.session.commit()
        
        return match
