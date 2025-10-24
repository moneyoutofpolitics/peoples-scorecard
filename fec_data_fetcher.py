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
        
    def _make_request(self, endpoint: str, params: Dict) -> Dict:
        """Make a request to the FEC API with rate limiting"""
        params['api_key'] = self.api_key
        
        time.sleep(self.rate_limit_delay)
        
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
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
            except requests.exceptions.HTTPError as e:
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
            print(f"Fetched page {page-1}, total receipts so far: {len(all_receipts)}")
            
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
    Calculate what percentage of contributions come from "big money"
    
    Excludes:
    - Self-funding (contributions from the candidate)
    - Small donors (under $200)
    - ActBlue and WinRed conduit contributions
    
    Args:
        receipts: List of contribution records from FEC
        candidate_name: Name of candidate to identify self-funding
        
    Returns:
        Dictionary with breakdown of contribution sources
    """
    total_amount = 0
    small_donor_amount = 0
    self_funding_amount = 0
    conduit_amount = 0
    big_money_amount = 0
    
    # Common conduit organizations
    conduits = ['ACTBLUE', 'WINRED', 'ACT BLUE', 'WIN RED']
    
    for receipt in receipts:
        amount = receipt.get('contribution_receipt_amount', 0)
        if amount <= 0:  # Skip refunds and zero amounts
            continue
            
        contributor_name = (receipt.get('contributor_name') or '').upper()
        
        # Check if it's self-funding
        is_self_funded = False
        if candidate_name:
            candidate_last_name = candidate_name.split()[-1].upper()
            if candidate_last_name in contributor_name:
                is_self_funded = True
                self_funding_amount += amount
        
        # Check if it's a conduit (ActBlue/WinRed)
        is_conduit = any(conduit in contributor_name for conduit in conduits)
        if is_conduit:
            conduit_amount += amount
        
        # Check if it's a small donor (under $200)
        elif amount < 200:
            small_donor_amount += amount
        
        # Everything else is "big money" (PACs, large donors, etc.)
        elif not is_self_funded:
            big_money_amount += amount
            
        total_amount += amount
    
    # Calculate percentages
    grassroots_total = small_donor_amount
    excluded_total = self_funding_amount + conduit_amount + small_donor_amount
    countable_total = total_amount - excluded_total
    
    big_money_percentage = 0
    if countable_total > 0:
        big_money_percentage = (big_money_amount / countable_total) * 100
    
    return {
        'total_contributions': total_amount,
        'total_receipts': len(receipts),
        'small_donor_amount': small_donor_amount,
        'self_funding_amount': self_funding_amount,
        'conduit_amount': conduit_amount,
        'big_money_amount': big_money_amount,
        'excluded_amount': excluded_total,
        'countable_total': countable_total,
        'big_money_percentage': round(big_money_percentage, 2),
        'grassroots_percentage': round((grassroots_total / total_amount * 100) if total_amount > 0 else 0, 2)
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
                print(f"Total Contributions: ${analysis['total_contributions']:,.2f}")
                print(f"Total Receipt Records: {analysis['total_receipts']}")
                print(f"\nBreakdown:")
                print(f"  Small Donors (<$200): ${analysis['small_donor_amount']:,.2f} ({analysis['grassroots_percentage']}%)")
                print(f"  Self-Funding: ${analysis['self_funding_amount']:,.2f}")
                print(f"  Conduit (ActBlue/WinRed): ${analysis['conduit_amount']:,.2f}")
                print(f"  Big Money (PACs + Large Donors): ${analysis['big_money_amount']:,.2f}")
                print(f"\n{'='*60}")
                print(f"BIG MONEY PERCENTAGE: {analysis['big_money_percentage']}%")
                print(f"{'='*60}")
            else:
                print("No receipts found for this candidate yet (may be too early in cycle)")
        else:
            print("No committees found for this candidate")
    else:
        print("No candidates found")
