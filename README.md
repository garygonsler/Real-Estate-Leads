# Real Estate AI - Lead Nurture & Matching System

An intelligent real estate CRM that automatically matches listings to buyers and nurtures leads with AI-powered personalization.

## Features

- **Automated MLS Sync**: Hourly sync of new listings from MLS
- **Smart Matching Engine**: AI-powered matching of listings to buyer criteria
- **Personalized Nurture**: Claude AI generates unique emails for each lead
- **Email Tracking**: Open and click tracking for engagement analytics
- **CRM Integration**: Two-way sync with Follow Up Boss and other CRMs
- **Background Jobs**: Celery-powered async task processing
- **RESTful API**: Complete API for lead management and analytics

## Tech Stack

- **Backend**: Flask, SQLAlchemy, PostgreSQL
- **Task Queue**: Celery + Redis
- **AI**: Anthropic Claude API
- **Email**: SendGrid
- **MLS**: SimplyRETS (or custom MLS integration)

## Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 14+
- Redis 6+

### Installation

1. **Clone and setup environment**

```bash
cd real-estate-ai
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment variables**

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required credentials:
- `DATABASE_URL`: PostgreSQL connection string
- `ANTHROPIC_API_KEY`: Get from https://console.anthropic.com
- `SENDGRID_API_KEY`: Get from https://sendgrid.com
- `MLS_API_KEY`: SimplyRETS or your MLS provider

3. **Initialize database**

```bash
python scripts/init_db.py
```

4. **Start services**

In separate terminals:

```bash
# Terminal 1: Flask API
python app/main.py

# Terminal 2: Celery worker
celery -A app.celery_app worker --loglevel=info

# Terminal 3: Celery beat (scheduler)
celery -A app.celery_app beat --loglevel=info
```

## Project Structure

```
real-estate-ai/
├── app/
│   ├── api/                 # API endpoints
│   │   ├── tracking.py      # Email tracking, unsubscribe
│   │   ├── leads.py         # Lead management CRUD
│   │   └── dashboard.py     # Analytics & stats
│   ├── models/              # Database models
│   │   ├── lead.py          # Lead, BuyerCriteria, Agent
│   │   ├── listing.py       # Listing, ListingHistory
│   │   └── match.py         # Match, NurtureTouch
│   ├── services/            # Business logic
│   │   ├── mls_sync.py      # MLS data sync
│   │   ├── matching.py      # Matching engine
│   │   ├── llm_service.py   # AI personalization
│   │   ├── email_service.py # Email delivery
│   │   └── crm_sync.py      # CRM integration
│   ├── tasks/               # Background jobs
│   │   ├── mls_tasks.py     # MLS sync jobs
│   │   ├── nurture_tasks.py # Nurture automation
│   │   └── maintenance_tasks.py # Cleanup jobs
│   ├── database.py          # DB setup
│   ├── celery_app.py        # Celery config
│   └── main.py              # Flask app
├── config/
│   └── config.py            # Configuration
├── scripts/
│   └── init_db.py           # Database initialization
├── requirements.txt
└── README.md
```

## Core Workflows

### 1. New Listing Flow

```
New MLS Listing → sync_mls_listings (hourly)
    ↓
Find matching buyers → match_listing_to_buyers
    ↓
Generate personalized email → LLM Service
    ↓
Send email alert → SendGrid
    ↓
Track engagement → Email opens/clicks
```

### 2. Daily Nurture Flow

```
run_daily_nurture (9 AM daily)
    ↓
Identify leads needing contact
    ↓
Generate contextual message → Claude AI
    ↓
Send via email
    ↓
Update engagement score
```

### 3. New Lead Flow

```
Create lead (API or CRM sync)
    ↓
Create buyer criteria
    ↓
Find existing matches → Matching Engine
    ↓
Send top 3 matches immediately
    ↓
Continue monitoring for new listings
```

## API Endpoints

### Leads

```bash
# Get all leads
GET /api/leads?status=active&page=1&per_page=50

# Get specific lead
GET /api/leads/123

# Create lead
POST /api/leads
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "phone": "555-1234",
  "criteria": {
    "min_price": 300000,
    "max_price": 500000,
    "bedrooms": 3,
    "bathrooms": 2,
    "locations": ["Austin", "Round Rock"],
    "must_haves": "home office, pool"
  }
}

# Update lead
PUT /api/leads/123

# Delete lead
DELETE /api/leads/123
```

### Dashboard

```bash
# Get stats
GET /api/dashboard/stats

# Recent matches
GET /api/dashboard/recent-matches?limit=20

# Engagement timeline
GET /api/dashboard/engagement-timeline?days=30

# Top leads
GET /api/dashboard/top-performing-leads?limit=10
```

### Tracking

```bash
# Track listing view
GET /track/{match_id}/listing_view

# Track email open (1x1 pixel)
GET /track/open/{message_id}

# Unsubscribe
GET /track/unsubscribe/{lead_id}
```

## Configuration

### Matching Score Thresholds

Matches are scored 0-100:
- **70-100**: High priority, send immediately
- **60-69**: Medium priority, include in daily digest
- **<60**: Don't send

Adjust `MATCH_SCORE_THRESHOLD` in config.

### Nurture Cadence

Default cadence:
- **Active leads**: Check-in every 7 days
- **Nurture leads**: Market update every 14 days
- **Dormant leads** (60+ days): Re-engagement attempt every 30 days

Modify in `app/tasks/nurture_tasks.py`.

### Email Tracking

Enable/disable in `.env`:
```
EMAIL_OPEN_TRACKING=true
```

## Celery Schedule

Configured in `app/celery_app.py`:

- **MLS Sync**: Every hour
- **Daily Nurture**: 9 AM daily
- **Weekly Cleanup**: Sunday 2 AM

## MLS Integration

### Using SimplyRETS

1. Sign up at https://simplyrets.com
2. Get API key and secret
3. Add to `.env`:
```
MLS_API_KEY=your-key
MLS_API_SECRET=your-secret
MLS_API_URL=https://api.simplyrets.com
```

### Using Custom MLS

Modify `app/services/mls_sync.py` to adapt to your MLS provider's API format.

## CRM Integration

### Follow Up Boss

1. Get API key from Follow Up Boss settings
2. Add to `.env`:
```
CRM_API_KEY=your-key
CRM_API_URL=https://api.followupboss.com/v1
```

3. Run sync:
```bash
# Manual sync
celery -A app.celery_app call app.tasks.maintenance_tasks.sync_crm_data
```

### Other CRMs

Adapt `app/services/crm_sync.py` for Salesforce, HubSpot, etc.

## Deployment

### Production Setup

1. **Use production config**
```bash
export FLASK_ENV=production
```

2. **Use gunicorn**
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app.main:app
```

3. **Supervisor for Celery**
```ini
[program:celery_worker]
command=/path/to/venv/bin/celery -A app.celery_app worker --loglevel=info
directory=/path/to/real-estate-ai
user=www-data
autostart=true
autorestart=true

[program:celery_beat]
command=/path/to/venv/bin/celery -A app.celery_app beat --loglevel=info
directory=/path/to/real-estate-ai
user=www-data
autostart=true
autorestart=true
```

4. **Nginx reverse proxy**
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Cloud Deployment Options

- **Heroku**: Use Heroku Postgres + Heroku Redis
- **AWS**: EC2 + RDS + ElastiCache
- **DigitalOcean**: Droplet + Managed Database + Managed Redis

## Monitoring

### Logs

```bash
# Flask logs
tail -f logs/app.log

# Celery logs
tail -f logs/celery.log
```

### Metrics to Track

- Email open rate (target: >25%)
- Email click rate (target: >5%)
- Match-to-showing conversion (target: >10%)
- Lead engagement score trends

## Troubleshooting

### MLS Sync Not Working

```bash
# Test MLS connection
python -c "from app.services.mls_sync import MLSSync; mls = MLSSync(); print(mls.fetch_new_listings(hours_back=1))"
```

### Emails Not Sending

```bash
# Test SendGrid
python -c "from app.services.email_service import EmailService; es = EmailService(); print(es.send_nurture_email(lead_id=1, nurture_type='check_in'))"
```

### Celery Not Running

```bash
# Check Redis connection
redis-cli ping
# Should return PONG

# Check Celery status
celery -A app.celery_app inspect active
```

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Add tests
5. Submit pull request

## License

MIT License - see LICENSE file

## Support

For issues or questions:
- GitHub Issues: https://github.com/yourusername/real-estate-ai/issues
- Email: support@yourdomain.com

---

Built with ❤️ using Flask, Celery, and Claude AI
