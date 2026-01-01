#!/bin/bash

# Quick Start Script for Real Estate AI
# This script sets up the development environment

echo "🏠 Real Estate AI - Quick Start Setup"
echo "======================================"
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $python_version found"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
echo "✓ Virtual environment created"
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  IMPORTANT: Edit .env file with your API keys before continuing"
    echo ""
    echo "Required credentials:"
    echo "  - DATABASE_URL (PostgreSQL)"
    echo "  - ANTHROPIC_API_KEY"
    echo "  - SENDGRID_API_KEY"
    echo "  - MLS_API_KEY"
    echo ""
    read -p "Press Enter after you've configured .env..."
else
    echo "✓ .env file already exists"
fi
echo ""

# Check if PostgreSQL is running
echo "Checking PostgreSQL connection..."
if command -v psql &> /dev/null; then
    echo "✓ PostgreSQL client found"
else
    echo "⚠️  PostgreSQL client not found. Make sure PostgreSQL is installed."
fi
echo ""

# Check if Redis is running
echo "Checking Redis connection..."
if command -v redis-cli &> /dev/null; then
    redis-cli ping &> /dev/null
    if [ $? -eq 0 ]; then
        echo "✓ Redis is running"
    else
        echo "⚠️  Redis is not running. Please start Redis: redis-server"
    fi
else
    echo "⚠️  Redis client not found. Make sure Redis is installed."
fi
echo ""

# Initialize database
echo "Do you want to initialize the database now? (y/n)"
read -p "> " init_db

if [ "$init_db" = "y" ]; then
    echo "Initializing database..."
    python scripts/init_db.py
    echo "✓ Database initialized"
else
    echo "⚠️  Skipping database initialization"
    echo "   Run 'python scripts/init_db.py' when ready"
fi
echo ""

# Done
echo "======================================"
echo "✓ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Make sure .env is configured with your API keys"
echo "2. Start the Flask API:"
echo "   python app/main.py"
echo ""
echo "3. In a new terminal, start Celery worker:"
echo "   celery -A app.celery_app worker --loglevel=info"
echo ""
echo "4. In another terminal, start Celery beat:"
echo "   celery -A app.celery_app beat --loglevel=info"
echo ""
echo "5. Access the API at http://localhost:5000"
echo ""
echo "📚 See README.md for full documentation"
echo "======================================"
