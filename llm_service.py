import anthropic
import logging
from typing import Optional, Dict
from datetime import datetime

from app.models import Lead, Listing, Match, NurtureTouch
from config.config import Config

logger = logging.getLogger(__name__)


class LLMService:
    """
    AI-powered personalization using Claude
    """
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-20250514"
    
    def generate_listing_alert(self, lead: Lead, listing: Listing, 
                              match_reasons: str) -> Dict[str, str]:
        """
        Generate personalized listing alert email
        
        Returns:
            Dict with 'subject' and 'body' keys
        """
        try:
            # Get recent engagement history
            recent_touches = NurtureTouch.query.filter_by(
                lead_id=lead.id
            ).order_by(NurtureTouch.sent_at.desc()).limit(5).all()
            
            engagement_summary = self._format_engagement_history(recent_touches)
            
            # Check for special features
            is_price_reduced, reduction_amount, reduction_pct = listing.is_price_reduced()
            
            prompt = f"""Generate a personalized email alerting {lead.first_name} about a new listing match.

LEAD PROFILE:
- Name: {lead.first_name} {lead.last_name}
- Search criteria: {lead.criteria.must_haves if lead.criteria.must_haves else 'Standard home search'}
- Budget: ${lead.criteria.min_price:,.0f} - ${lead.criteria.max_price:,.0f}
- Timeline: {lead.criteria.timeline or 'Not specified'}
- Engagement level: {self._get_engagement_level(lead)}

NEW LISTING:
- Address: {listing.address}, {listing.city}
- Price: ${listing.price:,.0f}
- Beds/Baths: {listing.bedrooms}/{listing.bathrooms}
- Square feet: {listing.sqft:,} sqft
- Property type: {listing.property_type}
- Days on market: {listing.days_on_market or 'Just listed'}
{f'- PRICE REDUCED: ${reduction_amount:,.0f} ({reduction_pct:.1f}% reduction)' if is_price_reduced else ''}

WHY IT MATCHES:
{match_reasons}

LISTING DESCRIPTION (first 300 chars):
{listing.description[:300] if listing.description else 'No description available'}...

RECENT ENGAGEMENT:
{engagement_summary}

INSTRUCTIONS:
Write a warm, conversational email (200-250 words) that:
1. Opens with a friendly greeting using their first name
2. Immediately highlights why this property is exciting for them specifically
3. References their search criteria naturally
4. Creates appropriate urgency (new listing, price drop, hot market) WITHOUT being pushy
5. Includes 1-2 specific details that would appeal to them
6. Ends with a clear call-to-action to schedule a showing or get more info
7. Keep tone helpful and knowledgeable, like a trusted advisor

Respond with JSON in this exact format:
{{"subject": "subject line here", "body": "email body here"}}

The subject should be compelling and personalized (40-60 chars).
Do not include any markdown formatting or preamble, ONLY the JSON."""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse response
            import json
            response_text = message.content[0].text.strip()
            
            # Remove any markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            result = json.loads(response_text)
            
            logger.info(f"Generated listing alert for lead {lead.id}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating listing alert: {e}")
            # Fallback to template
            return self._fallback_listing_alert(lead, listing)
    
    def generate_nurture_message(self, lead: Lead, nurture_type: str) -> Dict[str, str]:
        """
        Generate personalized nurture message
        
        Args:
            lead: Lead object
            nurture_type: Type of nurture (market_update, check_in, dormant_reengagement)
            
        Returns:
            Dict with 'subject' and 'body' keys
        """
        try:
            criteria = lead.criteria
            days_since_contact = (datetime.utcnow() - lead.last_contact).days if lead.last_contact else 999
            
            if nurture_type == "market_update":
                prompt = f"""Generate a market update email for {lead.first_name}.

BUYER PROFILE:
- Looking in: {', '.join(criteria.location_preferences) if criteria.location_preferences else 'their target area'}
- Budget: ${criteria.max_price:,.0f}
- Looking for: {criteria.bedrooms} bed, {criteria.bathrooms} bath
- Special needs: {criteria.must_haves or 'None specified'}

Create a brief, valuable market update (150-180 words) that:
1. Provides relevant market insights for their target area and price range
2. Mentions current trends (inventory levels, average days on market, price trends)
3. Subtly reminds them you're here to help when ready
4. Feels informative, not salesy

Note: You can mention general trends without specific data. Be helpful and conversational.

Respond with JSON: {{"subject": "subject here", "body": "body here"}}"""
            
            elif nurture_type == "check_in":
                prompt = f"""Generate a friendly check-in email for {lead.first_name}.

CONTEXT:
- Last contact: {days_since_contact} days ago
- Looking for: {criteria.bedrooms} bed / {criteria.bathrooms} bath in {', '.join(criteria.location_preferences) if criteria.location_preferences else 'their area'}
- Budget: ${criteria.max_price:,.0f}
- Timeline: {criteria.timeline or 'Flexible'}

Write a brief, warm check-in (100-120 words) that:
1. Acknowledges time has passed naturally
2. Asks if their needs or timeline have changed
3. Offers to help or provide updated listings
4. Feels genuine and respectful of their time
5. Easy to reply to or ignore

Respond with JSON: {{"subject": "subject here", "body": "body here"}}"""
            
            elif nurture_type == "dormant_reengagement":
                prompt = f"""Generate a re-engagement email for {lead.first_name} who hasn't engaged in {days_since_contact} days.

ORIGINAL SEARCH:
- {criteria.bedrooms} bed / {criteria.bathrooms} bath
- Budget: ${criteria.max_price:,.0f}
- Looking in: {', '.join(criteria.location_preferences) if criteria.location_preferences else 'various areas'}

Write a respectful re-engagement email (120-150 words) that:
1. Acknowledges they may have found a home or changed plans
2. Offers updated market insights or new inventory
3. Makes it easy to opt out if not interested
4. Feels helpful, not desperate
5. Gives them a reason to respond (market changes, new listings, rate changes, etc.)

Respond with JSON: {{"subject": "subject here", "body": "body here"}}"""
            
            else:
                raise ValueError(f"Unknown nurture type: {nurture_type}")
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse response
            import json
            response_text = message.content[0].text.strip()
            
            # Remove markdown if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            result = json.loads(response_text)
            
            logger.info(f"Generated {nurture_type} message for lead {lead.id}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating nurture message: {e}")
            return self._fallback_nurture_message(lead, nurture_type)
    
    def score_listing_match(self, listing_description: str, must_haves: str, 
                           nice_to_haves: Optional[str] = None) -> int:
        """
        Use LLM to score how well a listing matches buyer requirements
        
        Returns:
            Score from 0-20
        """
        try:
            prompt = f"""Score how well this listing matches the buyer's requirements on a scale of 0-20.

LISTING DESCRIPTION:
{listing_description[:500]}

BUYER MUST-HAVES:
{must_haves}

BUYER NICE-TO-HAVES:
{nice_to_haves or 'None specified'}

SCORING:
- 0-5: Poor match, missing critical requirements
- 6-10: Partial match, has some features
- 11-15: Good match, meets most requirements
- 16-20: Excellent match, exceeds requirements

Consider:
- Does it explicitly mention the must-haves?
- Are there features that align with nice-to-haves?
- Are there deal-breakers mentioned?

Respond with ONLY a single number between 0 and 20. No explanation."""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=10,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            
            score_text = message.content[0].text.strip()
            score = int(score_text)
            
            # Clamp to 0-20 range
            return max(0, min(20, score))
            
        except Exception as e:
            logger.error(f"Error scoring match: {e}")
            return 10  # Default moderate score
    
    def _format_engagement_history(self, touches: list) -> str:
        """Format recent engagement for context"""
        if not touches:
            return "No recent engagement"
        
        history = []
        for touch in touches[:3]:  # Last 3 touches
            days_ago = (datetime.utcnow() - touch.sent_at).days
            opened = "Opened" if touch.opened_at else "Not opened"
            history.append(f"- {touch.touch_type} {days_ago} days ago ({opened})")
        
        return "\n".join(history)
    
    def _get_engagement_level(self, lead: Lead) -> str:
        """Determine engagement level"""
        if lead.engagement_score >= 100:
            return "Highly engaged"
        elif lead.engagement_score >= 50:
            return "Moderately engaged"
        elif lead.engagement_score >= 20:
            return "Low engagement"
        else:
            return "Minimal engagement"
    
    def _fallback_listing_alert(self, lead: Lead, listing: Listing) -> Dict[str, str]:
        """Fallback template if LLM fails"""
        subject = f"New Match: {listing.address}"
        
        body = f"""Hi {lead.first_name},

I found a property that matches your search criteria:

{listing.address}, {listing.city}
${listing.price:,.0f} | {listing.bedrooms} bed, {listing.bathrooms} bath | {listing.sqft:,} sqft

This property is in your preferred area and price range. Would you like to schedule a showing?

Let me know if you'd like more details!

Best regards"""
        
        return {"subject": subject, "body": body}
    
    def _fallback_nurture_message(self, lead: Lead, nurture_type: str) -> Dict[str, str]:
        """Fallback template for nurture messages"""
        subject = f"Checking in on your home search"
        
        body = f"""Hi {lead.first_name},

I wanted to check in and see how your home search is going. Have your needs or timeline changed at all?

I'm here to help when you're ready. Let me know if you'd like to see some updated listings!

Best regards"""
        
        return {"subject": subject, "body": body}
