from typing import Dict, List, Optional
import requests
from datetime import datetime

class PastelAPI:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    def get_customer(self, account_code: str) -> Optional[Dict]:
        """Fetch customer details from Pastel"""
        try:
            response = requests.get(
                f"{self.base_url}/customers/{account_code}",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching customer: {str(e)}")
            return None

    def get_invoice(self, invoice_number: str) -> Optional[Dict]:
        """Fetch invoice details from Pastel"""
        try:
            response = requests.get(
                f"{self.base_url}/invoices/{invoice_number}",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching invoice: {str(e)}")
            return None

    def get_invoices_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime,
        account_code: Optional[str] = None
    ) -> List[Dict]:
        """Fetch invoices within a date range, optionally filtered by customer"""
        params = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
        }
        if account_code:
            params['account_code'] = account_code

        try:
            response = requests.get(
                f"{self.base_url}/invoices",
                params=params,
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error fetching invoices: {str(e)}")
            return []

    def get_cylinder_items(self) -> List[Dict]:
        """Fetch all cylinder-related items from Pastel"""
        try:
            response = requests.get(
                f"{self.base_url}/items",
                params={'category': 'CYLINDERS'},  # Assuming there's a category filter
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error fetching cylinder items: {str(e)}")
            return [] 