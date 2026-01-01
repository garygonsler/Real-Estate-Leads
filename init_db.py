"""
Database initialization script

Run this to create all database tables
"""

from app.main import app
from app.database import db
from app.models import Lead, BuyerCriteria, Agent, Listing, ListingHistory, Match, NurtureTouch

def init_database():
    """Initialize database with all tables"""
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✓ Database tables created successfully!")
        
        # Print created tables
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"\nCreated {len(tables)} tables:")
        for table in tables:
            print(f"  - {table}")

if __name__ == '__main__':
    init_database()
