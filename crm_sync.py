import requests
import logging
from datetime import datetime
from typing import List, Dict, Optional

from app.models import Lead, BuyerCriteria
from app.database import db
from config.config import Config

logger = logging.getLogger(__name__)


class CRMSync:
    """
    CRM Integration Service
    
    This example uses Follow Up Boss API format
    Adapt for other CRMs (Salesforce, HubSpot, etc.)
    """
    
    def __init__(self, api_key: str = None, api_url: str = None):
        self.api_key = api_key or Config.CRM_API_KEY
        self.api_url = api_url or Config.CRM_API_URL
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def sync_leads(self, limit: int = 100) -> List[Lead]:
        """
        Pull leads from CRM and sync to our database
        
        Args:
            limit: Maximum number of leads to sync
            
        Returns:
            List of synced Lead objects
        """
        try:
            logger.info(f"Syncing leads from CRM (limit: {limit})")
            
            # Fetch leads from CRM
            response = requests.get(
                f"{self.api_url}/people",
                headers=self.headers,
                params={
                    'type': 'lead',
                    'limit': limit,
                    'offset': 0
                },
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            leads_data = data.get('people', [])
            
            synced_leads = []
            for lead_data in leads_data:
                lead = self.upsert_lead(lead_data)
                if lead:
                    synced_leads.append(lead)
            
            logger.info(f"Synced {len(synced_leads)} leads from CRM")
            return synced_leads
            
        except requests.RequestException as e:
            logger.error(f"Error syncing leads from CRM: {e}")
            return []
    
    def upsert_lead(self, data: Dict) -> Optional[Lead]:
        """
        Create or update lead from CRM data
        
        Args:
            data: Raw CRM lead data
            
        Returns:
            Lead object or None
        """
        try:
            email = data.get('email')
            if not email:
                logger.warning("Lead data missing email, skipping")
                return None
            
            # Check if lead exists
            lead = Lead.query.filter_by(email=email).first()
            
            if lead:
                # Update existing lead
                lead.first_name = data.get('firstName', lead.first_name)
                lead.last_name = data.get('lastName', lead.last_name)
                lead.phone = data.get('phone') or lead.phone
                lead.source = data.get('source') or lead.source
                lead.crm_id = data.get('id')
                lead.crm_last_sync = datetime.utcnow()
                
                logger.debug(f"Updated lead {lead.id} from CRM")
            else:
                # Create new lead
                lead = Lead(
                    first_name=data.get('firstName', ''),
                    last_name=data.get('lastName', ''),
                    email=email,
                    phone=data.get('phone'),
                    source=data.get('source', 'CRM Import'),
                    status='active',
                    crm_id=data.get('id'),
                    crm_last_sync=datetime.utcnow()
                )
                db.session.add(lead)
                db.session.flush()  # Get lead ID
                
                # Extract and create buyer criteria from CRM notes/tags
                criteria = self._extract_criteria_from_crm(data, lead.id)
                if criteria:
                    db.session.add(criteria)
                
                logger.info(f"Created new lead {lead.id} from CRM: {email}")
            
            db.session.commit()
            return lead
            
        except Exception as e:
            logger.error(f"Error upserting lead from CRM: {e}")
            db.session.rollback()
            return None
    
    def _extract_criteria_from_crm(self, crm_data: Dict, lead_id: int) -> Optional[BuyerCriteria]:
        """
        Extract buyer criteria from CRM data
        
        Different CRMs store criteria differently - customize as needed
        """
        try:
            # Example: criteria might be in custom fields or notes
            custom_fields = crm_data.get('customFields', {})
            tags = crm_data.get('tags', [])
            
            # Extract price range
            min_price = custom_fields.get('minPrice')
            max_price = custom_fields.get('maxPrice')
            
            # Extract bedrooms/bathrooms
            bedrooms = custom_fields.get('bedrooms')
            bathrooms = custom_fields.get('bathrooms')
            
            # Extract locations from tags
            locations = [tag for tag in tags if tag.startswith('location:')]
            locations = [loc.replace('location:', '') for loc in locations]
            
            # Create criteria if we have any data
            if any([min_price, max_price, bedrooms, bathrooms, locations]):
                criteria = BuyerCriteria(
                    lead_id=lead_id,
                    min_price=min_price,
                    max_price=max_price,
                    bedrooms=bedrooms,
                    bathrooms=bathrooms,
                    location_preferences=locations if locations else None
                )
                return criteria
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting criteria from CRM data: {e}")
            return None
    
    def push_activity(self, lead_id: int, activity_type: str, details: str) -> bool:
        """
        Push activity back to CRM
        
        Args:
            lead_id: Our lead ID
            activity_type: Type of activity
            details: Activity details
            
        Returns:
            True if successful
        """
        try:
            lead = Lead.query.get(lead_id)
            if not lead or not lead.crm_id:
                logger.warning(f"Lead {lead_id} not found or has no CRM ID")
                return False
            
            # Create activity/event in CRM
            activity_data = {
                'personId': lead.crm_id,
                'type': activity_type,
                'note': details,
                'source': 'Real Estate AI System',
                'created': datetime.utcnow().isoformat()
            }
            
            response = requests.post(
                f"{self.api_url}/events",
                headers=self.headers,
                json=activity_data,
                timeout=30
            )
            response.raise_for_status()
            
            logger.info(f"Pushed activity to CRM for lead {lead_id}: {activity_type}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Error pushing activity to CRM: {e}")
            return False
    
    def update_lead_status(self, lead_id: int, status: str) -> bool:
        """
        Update lead status in CRM
        
        Args:
            lead_id: Our lead ID
            status: New status
            
        Returns:
            True if successful
        """
        try:
            lead = Lead.query.get(lead_id)
            if not lead or not lead.crm_id:
                return False
            
            # Map our status to CRM status
            crm_status_map = {
                'active': 'Active',
                'nurture': 'Nurture',
                'converted': 'Converted',
                'unsubscribed': 'Unsubscribed'
            }
            
            crm_status = crm_status_map.get(status, 'Active')
            
            response = requests.put(
                f"{self.api_url}/people/{lead.crm_id}",
                headers=self.headers,
                json={'status': crm_status},
                timeout=30
            )
            response.raise_for_status()
            
            logger.info(f"Updated lead {lead_id} status in CRM to {crm_status}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Error updating lead status in CRM: {e}")
            return False
    
    def sync_agent_assignment(self, lead_id: int, agent_id: int) -> bool:
        """
        Sync agent assignment to CRM
        
        Args:
            lead_id: Our lead ID
            agent_id: Our agent ID
            
        Returns:
            True if successful
        """
        try:
            from app.models import Agent
            
            lead = Lead.query.get(lead_id)
            agent = Agent.query.get(agent_id)
            
            if not lead or not agent or not lead.crm_id:
                return False
            
            # Assign in CRM
            response = requests.put(
                f"{self.api_url}/people/{lead.crm_id}",
                headers=self.headers,
                json={'assignedTo': agent.crm_id or agent.email},
                timeout=30
            )
            response.raise_for_status()
            
            logger.info(f"Synced agent assignment to CRM: Lead {lead_id} -> Agent {agent_id}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Error syncing agent assignment: {e}")
            return False
