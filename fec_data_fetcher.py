"""
FEC Data Fetcher for The People's Scorecard
Fetches and processes campaign contribution data from the FEC API
"""

import requests
import time
from typing import Dict, List, Optional
from datetime import datetime

class FECDataFetcher:
    """Handles all interactions with the FEC API"""
    
    BASE_URL = "https://api.open.fec.gov/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the FEC data fetcher
        
        Args:
            api_key: FEC API key (get one at https://api.open.fec.gov/developers/)
                    Without a key, you're limited to 120 requests/hour
                    With a key, you get 1,000 requests/hour
        """
        self.api_key = api_key or "DEMO_KEY"
        self.session = requests.Session()
        self.rate_limit_delay = 0.1  # Small delay between requests to be respectful
        
    def _make_request(self, endpoint: str, params: Dict, max_retries: int = 3) -> Dict:
        """Make a request to the FEC API with rate limiting, timeout, and retries"""
        params['api_key'] = self.api_key
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        for attempt in range(max_retries):
            try:
                time.sleep(self.rate_limit_delay)
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"Request timeout, retrying... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(2)  # Wait 2 seconds before retry
                    continue
                else:
                    raise
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    print(f"Request error: {e}, retrying... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(2)
                    continue
                else:
                    raise
        
        raise Exception("Max retries exceeded")
    
    def search_candidates(self, name: str, cycle: int = 2026, office: str = None) -> List[Dict]:
        """
        Search for candidates by name
        
        Args:
            name: Candidate name (partial match works)
            cycle: Election cycle (e.g., 2026)
            office: 'H' for House, 'S' for Senate, 'P' for President
            
        Returns:
            List of candidate dictionaries with basic info
        """
        params = {
            'name': name,
            'cycle': cycle,
            'per_page': 100
        }
        
        if office:
            params['office'] = office
            
        data = self._make_request('candidates/search', params)
        return data.get('results', [])
    
    def get_candidate_committees(self, candidate_id: str, cycle: int = 2026) -> List[Dict]:
        """Get all committees associated with a candidate"""
        params = {
            'candidate_id': candidate_id,
            'cycle': cycle,
            'per_page': 100
        }
        
        data = self._make_request('candidate/' + candidate_id + '/committees', params)
        return data.get('results', [])
    
    def get_committee_receipts(self, committee_id: str, cycle: int = 2026, 
                              max_pages: int = None) -> List[Dict]:
        """
        Get itemized receipts (contributions) for a committee
        
        Args:
            committee_id: FEC committee ID
            cycle: Election cycle
            max_pages: Maximum number of pages to fetch (None = all pages)
            
        Returns:
            List of contribution records
        """
        all_receipts = []
        page = 1
        
        while True:
            if max_pages and page > max_pages:
                break
                
            params = {
                'committee_id': committee_id,
                'two_year_transaction_period': cycle,
                'per_page': 100,
                'page': page,
                'sort': '-contribution_receipt_date'
            }
            
            try:
                data = self._make_request('schedules/schedule_a', params)
            except requests.exceptions.Timeout:
                print(f"Timeout on page {page}, using data from {page-1} pages")
                break
            except requests.exceptions.RequestException as e:
                print(f"Error fetching page {page}: {e}")
                break
                
            results = data.get('results', [])
            if not results:
                break
                
            all_receipts.extend(results)
            
            # Check if there are more pages
            pagination = data.get('pagination', {})
            if page >= pagination.get('pages', 1):
                break
                
            page += 1
            if page % 2 == 0:  # Log every 2 pages
                print(f"Fetched {page-1} pages, {len(all_receipts)} receipts so far...")
            
        print(f"Completed: Fetched {len(all_receipts)} total receipts from {page-1} pages")
        return all_receipts
    
    def get_candidate_summary(self, candidate_id: str, cycle: int = 2026) -> Dict:
        """Get financial summary for a candidate"""
        params = {
            'candidate_id': candidate_id,
            'cycle': cycle
        }
        
        data = self._make_request(f'candidate/{candidate_id}/totals', params)
        results = data.get('results', [])
        return results[0] if results else {}


def calculate_big_money_percentage(receipts: List[Dict], candidate_name: str = "") -> Dict:
    """
    Calculate comprehensive breakdown of contributions by entity type
    
    Returns both:
    1. Big money percentage (excludes grassroots <$200, self-funding, conduits)
    2. Detailed breakdown of ALL contributions by entity type with no exclusions
    
    Args:
        receipts: List of contribution records from FEC
        candidate_name: Name of candidate to identify self-funding
        
    Returns:
        Dictionary with big money percentage and detailed breakdown
    """
    # Initialize counters for detailed breakdown
    breakdown = {
        'pacs': 0,
        'party_committees': 0,
        'other_candidates': 0,
        'organizations': 0,
        'large_individual_donors': 0,
        'small_individual_donors': 0,
        'self_funding': 0,
        'conduits': 0,
        'unknown': 0
    }
    
    # Common conduit organizations
    conduits = ['ACTBLUE', 'WINRED', 'ACT BLUE', 'WIN RED']
    
    # Process each receipt
    for receipt in receipts:
        amount = float(receipt.get('contribution_receipt_amount', 0))
        entity_type = receipt.get('entity_type', '').upper()
        contributor_name = receipt.get('contributor_name', '').upper()
        
        # Skip if no amount or negative (refunds)
        if amount <= 0:
            continue
        
        # Check for conduits (ActBlue/WinRed)
        is_conduit = any(conduit in contributor_name for conduit in conduits)
        if is_conduit:
            breakdown['conduits'] += amount
            continue
        
        # Check for self-funding (candidate's own money)
        is_self_funded = False
        if candidate_name:
            candidate_last_name = candidate_name.split()[-1].upper()
            if candidate_last_name in contributor_name or entity_type == 'CAN':
                is_self_funded = True
                breakdown['self_funding'] += amount
                continue
        
        # Categorize by entity type
        if entity_type == 'PAC':
            breakdown['pacs'] += amount
        elif entity_type == 'PTY':
            breakdown['party_committees'] += amount
        elif entity_type == 'CCM':
            breakdown['other_candidates'] += amount
        elif entity_type == 'ORG':
            breakdown['organizations'] += amount
        elif entity_type == 'IND':
            # Split individuals by amount
            if amount >= 200:
                breakdown['large_individual_donors'] += amount
            else:
                breakdown['small_individual_donors'] += amount
        else:
            # Unknown entity type
            breakdown['unknown'] += amount
    
    # Calculate totals
    total_raised = sum(breakdown.values())
    
    # Calculate "Big Money" (PACs + Party + Other Candidates + Orgs + Large Donors)
    big_money = (
        breakdown['pacs'] +
        breakdown['party_committees'] +
        breakdown['other_candidates'] +
        breakdown['organizations'] +
        breakdown['large_individual_donors']
    )
    
    # Combine conduits with small donors (both are grassroots)
    grassroots_total = breakdown['small_individual_donors'] + breakdown['conduits']
    
    # Calculate big money percentage (out of total raised - no exclusions except self-funding)
    countable_total = total_raised - breakdown['self_funding']
    
    if countable_total > 0:
        big_money_percentage = round((big_money / countable_total) * 100, 1)
    else:
        big_money_percentage = 0
    
    # Calculate percentages for each category (out of total raised - no exclusions)
    breakdown_percentages = {}
    if total_raised > 0:
        for key, value in breakdown.items():
            breakdown_percentages[key] = round((value / total_raised) * 100, 1)
    else:
        breakdown_percentages = {key: 0 for key in breakdown.keys()}
    
    return {
        'big_money_percentage': big_money_percentage,
        'total_raised': round(total_raised, 2),
        'big_money_amount': round(big_money, 2),
        'grassroots_amount': round(grassroots_total, 2),
        'self_funding_amount': round(breakdown['self_funding'], 2),
        'total_receipts': len(receipts),
        'breakdown': {
            'pacs': {
                'amount': round(breakdown['pacs'], 2),
                'percentage': breakdown_percentages['pacs']
            },
            'party_committees': {
                'amount': round(breakdown['party_committees'], 2),
                'percentage': breakdown_percentages['party_committees']
            },
            'other_candidates': {
                'amount': round(breakdown['other_candidates'], 2),
                'percentage': breakdown_percentages['other_candidates']
            },
            'organizations': {
                'amount': round(breakdown['organizations'], 2),
                'percentage': breakdown_percentages['organizations']
            },
            'large_individual_donors': {
                'amount': round(breakdown['large_individual_donors'], 2),
                'percentage': breakdown_percentages['large_individual_donors']
            },
            'small_individual_donors': {
                'amount': round(breakdown['small_individual_donors'], 2),
                'percentage': breakdown_percentages['small_individual_donors']
            },
            'self_funding': {
                'amount': round(breakdown['self_funding'], 2),
                'percentage': breakdown_percentages['self_funding']
            },
            'conduits': {
                'amount': round(breakdown['conduits'], 2),
                'percentage': breakdown_percentages['conduits']
            },
            'grassroots_combined': {
                'amount': round(grassroots_total, 2),
                'percentage': round((grassroots_total / total_raised * 100) if total_raised > 0 else 0, 1)
            }
        }
    }


if __name__ == "__main__":
    # Example usage
    fetcher = FECDataFetcher()
    
    # Search for a candidate (example: searching for "Warren")
    print("Searching for candidates named Warren in 2026 cycle...")
    candidates = fetcher.search_candidates("Warren", cycle=2026, office='S')
    
    if candidates:
        candidate = candidates[0]
        print(f"\nFound: {candidate['name']} ({candidate['party']})")
        print(f"Candidate ID: {candidate['candidate_id']}")
        print(f"State: {candidate['state']}")
        
        # Get their committees
        committees = fetcher.get_candidate_committees(candidate['candidate_id'], cycle=2026)
        
        if committees:
            committee = committees[0]
            print(f"\nPrincipal Committee: {committee['name']}")
            print(f"Committee ID: {committee['committee_id']}")
            
            # Get receipts (limiting to first 5 pages for demo)
            print("\nFetching contribution data (limited to 5 pages for demo)...")
            receipts = fetcher.get_committee_receipts(
                committee['committee_id'], 
                cycle=2026,
                max_pages=5
            )
            
            # Calculate big money percentage
            if receipts:
                analysis = calculate_big_money_percentage(receipts, candidate['name'])
                
                print("\n" + "="*60)
                print(f"ANALYSIS FOR {candidate['name']}")
                print("="*60)
                print(f"Total Raised: ${analysis['total_raised']:,.2f}")
                print(f"Total Receipt Records: {analysis['total_receipts']}")
                
                print(f"\n{'='*60}")
                print(f"BIG MONEY PERCENTAGE: {analysis['big_money_percentage']}%")
                print(f"(excludes small donors, self-funding, conduits)")
                print(f"{'='*60}")
                
                print(f"\nDetailed Breakdown:")
                breakdown = analysis['breakdown']
                print(f"  PACs: ${breakdown['pacs']['amount']:,.2f} ({breakdown['pacs']['percentage']}%)")
                print(f"  Party Committees: ${breakdown['party_committees']['amount']:,.2f} ({breakdown['party_committees']['percentage']}%)")
                print(f"  Other Candidates: ${breakdown['other_candidates']['amount']:,.2f} ({breakdown['other_candidates']['percentage']}%)")
                print(f"  Organizations: ${breakdown['organizations']['amount']:,.2f} ({breakdown['organizations']['percentage']}%)")
                print(f"  Large Individual Donors (≥$200): ${breakdown['large_individual_donors']['amount']:,.2f} ({breakdown['large_individual_donors']['percentage']}%)")
                print(f"  Small Individual Donors (<$200): ${breakdown['small_individual_donors']['amount']:,.2f} ({breakdown['small_individual_donors']['percentage']}%)")
                print(f"  Self-Funding: ${breakdown['self_funding']['amount']:,.2f} ({breakdown['self_funding']['percentage']}%)")
                print(f"  ActBlue/WinRed Conduits: ${breakdown['conduits']['amount']:,.2f} ({breakdown['conduits']['percentage']}%)")
                print(f"\n(All percentages are of total raised)")
            else:
                print("No receipts found for this candidate yet (may be too early in cycle)")
        else:
            print("No committees found for this candidate")
    else:
        print("No candidates found")
