"""
Web Dashboard for The People's Scorecard
Simple Flask application to display big money percentages for candidates
"""

from flask import Flask, render_template, request, jsonify
from fec_data_fetcher import FECDataFetcher, calculate_big_money_percentage
import os

app = Flask(__name__)

# Initialize FEC fetcher (you should set FEC_API_KEY environment variable)
fetcher = FECDataFetcher(api_key=os.environ.get('FEC_API_KEY', 'DEMO_KEY'))

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/search_candidates')
def search_candidates():
    """API endpoint to search for candidates"""
    name = request.args.get('name', '')
    office = request.args.get('office', '')
    cycle = int(request.args.get('cycle', 2026))
    
    if not name:
        return jsonify({'error': 'Name parameter required'}), 400
    
    try:
        candidates = fetcher.search_candidates(
            name=name,
            cycle=cycle,
            office=office if office else None
        )
        
        # Format results
        results = []
        for candidate in candidates[:10]:  # Limit to 10 results
            results.append({
                'candidate_id': candidate['candidate_id'],
                'name': candidate['name'],
                'party': candidate.get('party', 'Unknown'),
                'state': candidate.get('state', ''),
                'district': candidate.get('district', ''),
                'office': candidate.get('office', ''),
                'office_full': candidate.get('office_full', '')
            })
        
        return jsonify({'results': results})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze_candidate')
def analyze_candidate():
    """API endpoint to analyze a specific candidate"""
    candidate_id = request.args.get('candidate_id', '')
    candidate_name = request.args.get('name', '')
    candidate_party = request.args.get('party', '')
    candidate_state = request.args.get('state', '')
    cycle = int(request.args.get('cycle', 2026))
    max_pages = int(request.args.get('max_pages', 10))
    
    if not candidate_id:
        return jsonify({'error': 'candidate_id parameter required'}), 400
    
    try:
        # Get committees directly - we don't need to search again since we have the ID
        committees = fetcher.get_candidate_committees(candidate_id, cycle=cycle)
        
        if not committees:
            return jsonify({
                'error': 'No committees found for this candidate',
                'candidate_id': candidate_id
            }), 404
        
        # Get receipts from principal committee
        principal_committee = committees[0]
        receipts = fetcher.get_committee_receipts(
            principal_committee['committee_id'],
            cycle=cycle,
            max_pages=max_pages
        )
        
        if not receipts:
            return jsonify({
                'warning': 'No contribution data available yet for this candidate',
                'committee': {
                    'name': principal_committee['name'],
                    'id': principal_committee['committee_id']
                }
            })
        
        # Calculate analysis - use the name passed from frontend
        analysis = calculate_big_money_percentage(receipts, candidate_name)
        
        # Format response
        return jsonify({
            'candidate': {
                'id': candidate_id,
                'name': candidate_name,
                'party': candidate_party,
                'state': candidate_state
            },
            'committee': {
                'name': principal_committee['name'],
                'id': principal_committee['committee_id']
            },
            'analysis': analysis,
            'note': f'Analysis based on {len(receipts)} contribution records'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
