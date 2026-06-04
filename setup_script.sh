#!/bin/bash
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Creating virtual environment..."
python -m venv venv

echo "Setup complete! Activate with: source venv/bin/activate"
