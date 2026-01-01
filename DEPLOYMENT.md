# Deployment Guide

## Local Development

### Quick Start with Docker Compose

The easiest way to run everything locally:

```bash
# 1. Set environment variables
cp .env.example .env
# Edit .env with your API keys

# 2. Start all services
docker-compose up

# 3. Initialize database (in another terminal)
docker-compose exec api python scripts/init_db.py
```

Services will be available at:
- API: http://localhost:5000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Manual Setup (without Docker)

See quickstart.sh or follow README.md instructions.

---

## Production Deployment

### Option 1: Heroku

**Pros**: Easiest, managed services
**Cons**: More expensive at scale

```bash
# 1. Install Heroku CLI
# 2. Create app
heroku create your-app-name

# 3. Add PostgreSQL
heroku addons:create heroku-postgresql:standard-0

# 4. Add Redis
heroku addons:create heroku-redis:premium-0

# 5. Set environment variables
heroku config:set ANTHROPIC_API_KEY=your-key
heroku config:set SENDGRID_API_KEY=your-key
heroku config:set MLS_API_KEY=your-key
# ... set all required vars from .env

# 6. Add Procfile
echo "web: gunicorn app.main:app" > Procfile
echo "worker: celery -A app.celery_app worker --loglevel=info" >> Procfile
echo "beat: celery -A app.celery_app beat --loglevel=info" >> Procfile

# 7. Deploy
git push heroku main

# 8. Initialize database
heroku run python scripts/init_db.py

# 9. Scale workers
heroku ps:scale web=1 worker=1 beat=1
```

**Cost estimate**: $50-150/month
- Dyno: $25/month (standard)
- Postgres: $50/month (standard-0)
- Redis: $30/month (premium-0)

---

### Option 2: DigitalOcean

**Pros**: Good balance of cost and control
**Cons**: More setup required

#### Setup Steps

**1. Create Droplet**
- Ubuntu 22.04
- At least 2GB RAM
- $12/month tier

**2. Create Managed Database**
- PostgreSQL 15
- Basic plan: $15/month

**3. Create Managed Redis**
- Basic plan: $15/month

**4. SSH into droplet**

```bash
ssh root@your-droplet-ip
```

**5. Install dependencies**

```bash
# Update system
apt update && apt upgrade -y

# Install Python
apt install python3.11 python3.11-venv python3-pip -y

# Install Nginx
apt install nginx -y

# Install Supervisor
apt install supervisor -y
```

**6. Deploy application**

```bash
# Create app user
adduser appuser
usermod -aG sudo appuser
su - appuser

# Clone repository
git clone https://github.com/yourusername/real-estate-ai.git
cd real-estate-ai

# Setup virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn
```

**7. Configure environment**

```bash
# Create .env file
nano .env
# Add all required environment variables
# Use DigitalOcean managed database URLs
```

**8. Initialize database**

```bash
python scripts/init_db.py
```

**9. Setup Supervisor for process management**

```bash
sudo nano /etc/supervisor/conf.d/real-estate-ai.conf
```

Add:

```ini
[program:real_estate_api]
command=/home/appuser/real-estate-ai/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app.main:app
directory=/home/appuser/real-estate-ai
user=appuser
autostart=true
autorestart=true
stderr_logfile=/var/log/real-estate-ai/api.err.log
stdout_logfile=/var/log/real-estate-ai/api.out.log

[program:celery_worker]
command=/home/appuser/real-estate-ai/venv/bin/celery -A app.celery_app worker --loglevel=info
directory=/home/appuser/real-estate-ai
user=appuser
autostart=true
autorestart=true
stderr_logfile=/var/log/real-estate-ai/worker.err.log
stdout_logfile=/var/log/real-estate-ai/worker.out.log

[program:celery_beat]
command=/home/appuser/real-estate-ai/venv/bin/celery -A app.celery_app beat --loglevel=info
directory=/home/appuser/real-estate-ai
user=appuser
autostart=true
autorestart=true
stderr_logfile=/var/log/real-estate-ai/beat.err.log
stdout_logfile=/var/log/real-estate-ai/beat.out.log
```

**10. Create log directory**

```bash
sudo mkdir -p /var/log/real-estate-ai
sudo chown appuser:appuser /var/log/real-estate-ai
```

**11. Start services**

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all
```

**12. Configure Nginx**

```bash
sudo nano /etc/nginx/sites-available/real-estate-ai
```

Add:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**13. Enable site**

```bash
sudo ln -s /etc/nginx/sites-available/real-estate-ai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**14. Setup SSL with Let's Encrypt**

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

**Cost estimate**: $42/month
- Droplet: $12/month
- PostgreSQL: $15/month
- Redis: $15/month

---

### Option 3: AWS

**Pros**: Most scalable, full control
**Cons**: Most complex setup

#### Architecture

- **EC2**: Application servers
- **RDS**: PostgreSQL database
- **ElastiCache**: Redis
- **ALB**: Load balancer
- **S3**: Static files (optional)
- **CloudWatch**: Monitoring

#### Estimated Cost

- EC2 (t3.medium): $30/month
- RDS (db.t3.micro): $15/month
- ElastiCache (cache.t3.micro): $12/month
- ALB: $20/month
- **Total**: ~$77/month

#### Quick Setup with Elastic Beanstalk

```bash
# Install EB CLI
pip install awsebcli

# Initialize EB application
eb init -p python-3.11 real-estate-ai

# Create environment
eb create real-estate-env

# Set environment variables
eb setenv ANTHROPIC_API_KEY=your-key SENDGRID_API_KEY=your-key ...

# Deploy
eb deploy

# Open in browser
eb open
```

For Celery workers, use **AWS ECS** or separate EC2 instances.

---

## Post-Deployment Checklist

### Security

- [ ] Change default database passwords
- [ ] Enable SSL/HTTPS
- [ ] Set up firewall rules
- [ ] Configure CORS properly
- [ ] Use secrets manager for API keys
- [ ] Enable database backups
- [ ] Set up security monitoring

### Monitoring

- [ ] Configure application logging
- [ ] Set up error tracking (Sentry)
- [ ] Monitor database performance
- [ ] Track Celery queue length
- [ ] Set up uptime monitoring
- [ ] Configure alerts for failures

### Optimization

- [ ] Enable database connection pooling
- [ ] Configure Redis persistence
- [ ] Set up CDN for static assets (if any)
- [ ] Enable gzip compression in Nginx
- [ ] Optimize database indexes
- [ ] Configure Celery autoscaling

### Backup Strategy

```bash
# Database backup (daily cron job)
0 2 * * * pg_dump $DATABASE_URL > /backups/db_$(date +\%Y\%m\%d).sql

# Keep last 7 days
find /backups -name "db_*.sql" -mtime +7 -delete
```

### Updates & Maintenance

```bash
# Update code
git pull origin main
source venv/bin/activate
pip install -r requirements.txt

# Run migrations (if any)
flask db upgrade

# Restart services
sudo supervisorctl restart all

# Or with Docker
docker-compose pull
docker-compose up -d --build
```

---

## Scaling Considerations

### When to scale:

- **API response time > 500ms**: Add more web workers
- **Celery queue backing up**: Add more workers
- **Database CPU > 80%**: Upgrade database tier
- **Redis memory > 80%**: Upgrade Redis tier

### Horizontal Scaling

**Multi-server setup**:
1. Move database to managed service
2. Move Redis to managed service
3. Deploy multiple API servers behind load balancer
4. Run Celery workers on separate servers
5. Use shared file storage (S3) if needed

### Vertical Scaling

**Upgrade server resources**:
- Start: 2GB RAM, 1 CPU
- Growing: 4GB RAM, 2 CPU
- Mature: 8GB RAM, 4 CPU

---

## Troubleshooting Production Issues

### App won't start

```bash
# Check logs
sudo tail -f /var/log/real-estate-ai/api.err.log

# Check Supervisor status
sudo supervisorctl status

# Restart manually
sudo supervisorctl restart all
```

### Database connection issues

```bash
# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Check connection pool
# Add to config.py:
SQLALCHEMY_POOL_SIZE = 10
SQLALCHEMY_POOL_RECYCLE = 3600
```

### Celery tasks not running

```bash
# Check worker status
sudo supervisorctl status celery_worker

# Check Redis
redis-cli ping

# Purge queue if stuck
celery -A app.celery_app purge
```

### High memory usage

```bash
# Check process memory
ps aux --sort=-%mem | head

# Reduce Celery workers
# In supervisor config: --concurrency=2

# Enable memory limits
# In celery config: worker_max_memory_per_child = 200000  # 200MB
```

---

## Monitoring Dashboard

### Recommended Tools

- **Uptime**: UptimeRobot (free)
- **Errors**: Sentry (free tier)
- **Logs**: Papertrail or Loggly
- **Metrics**: Grafana + Prometheus

### Key Metrics to Track

1. **API Performance**
   - Response time (p50, p95, p99)
   - Error rate
   - Request volume

2. **Celery**
   - Queue length
   - Task success/failure rate
   - Average task duration

3. **Database**
   - Connection count
   - Query performance
   - Lock waits

4. **Business Metrics**
   - Email open rate
   - Match creation rate
   - Lead conversion rate

---

## Support

For deployment assistance:
- Documentation: See README.md
- Issues: GitHub Issues
- Email: support@yourdomain.com
