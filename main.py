"""
The People's Scorecard - Replit Version
This file is configured to run automatically on Replit
"""

from app import app
import os

if __name__ == '__main__':
    # Replit requires binding to 0.0.0.0 and using their PORT
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
