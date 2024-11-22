from datetime import datetime
from typing import List, Dict
from .pastel_integration import PastelAPI
from django.conf import settings
from .models import Document, CylinderMovement, Customer

class PastelService:
    def __init__(self):
        self.api = PastelAPI(
            settings.PASTEL_API_URL,
            settings.PASTEL_API_KEY
        )

    def sync_customer(self, account_number: str) -> bool:
        """Sync customer data from Pastel"""
        pastel_customer = self.api.get_customer(account_number)
        if not pastel_customer:
            return False

        Customer.objects.update_or_create(
            account_number=account_number,
            defaults={
                'name': pastel_customer['name'],
                'contact_person': pastel_customer.get('contact_person', ''),
                'phone_number': pastel_customer.get('telephone', ''),
                'email': pastel_customer.get('email', ''),
                'address': pastel_customer.get('physical_address', '')
            }
        )
        return True

    def check_cylinder_movements(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Check Pastel invoices for cylinder movements that might need to be recorded
        Returns list of potential movements that aren't in our system
        """
        # Get all cylinder-related items from Pastel
        cylinder_items = {
            item['code']: item['description'] 
            for item in self.api.get_cylinder_items()
        }

        # Get invoices from the date range
        invoices = self.api.get_invoices_by_date_range(start_date, end_date)
        
        potential_movements = []
        for invoice in invoices:
            # Skip if we already have this document
            if Document.objects.filter(document_number=invoice['number']).exists():
                continue

            # Check each line item for cylinder movements
            for line in invoice['lines']:
                if line['item_code'] in cylinder_items:
                    potential_movements.append({
                        'invoice_number': invoice['number'],
                        'date': invoice['date'],
                        'customer': invoice['account_code'],
                        'item_code': line['item_code'],
                        'description': cylinder_items[line['item_code']],
                        'quantity': line['quantity']
                    })

        return potential_movements 