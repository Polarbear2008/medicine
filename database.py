import os
import asyncio
from typing import Dict, List, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Supabase connection
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(supabase_url, supabase_key)

class DatabaseManager:
    def __init__(self):
        self.supabase = supabase
    
    async def create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            # Create medicines table
            medicines_sql = """
            CREATE TABLE IF NOT EXISTS medicines (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                benefits TEXT,
                contraindications TEXT,
                description TEXT,
                price TEXT,
                photo TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            """
            
            # Create orders table
            orders_sql = """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT,
                full_name TEXT,
                medicine TEXT NOT NULL,
                months INTEGER DEFAULT 1,
                price TEXT,
                status TEXT DEFAULT 'new',
                delivery_region TEXT,
                delivery_district TEXT,
                delivery_address TEXT,
                phone_number TEXT,
                receipt_photo_id TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            """
            
            # Execute SQL commands (Note: Supabase handles table creation via dashboard)
            print("Tables should be created via Supabase dashboard")
            return True
            
        except Exception as e:
            print(f"Error creating tables: {e}")
            return False
    
    # Medicine operations
    async def get_all_medicines(self) -> Dict[str, Dict]:
        """Get all medicines from database"""
        try:
            response = self.supabase.table('medicines').select('*').execute()
            medicines = {}
            for med in response.data:
                medicines[med['id']] = {
                    'name': med['name'],
                    'benefits': med.get('benefits'),
                    'contraindications': med.get('contraindications'),
                    'description': med.get('description'),
                    'price': med.get('price'),
                    'photo': med.get('photo')
                }
            return medicines
        except Exception as e:
            print(f"Error getting medicines: {e}")
            return {}
    
    async def add_medicine(self, med_id: str, medicine_data: Dict) -> bool:
        """Add a new medicine to database"""
        try:
            data = {
                'id': med_id,
                'name': medicine_data['name'],
                'benefits': medicine_data.get('benefits'),
                'contraindications': medicine_data.get('contraindications'),
                'description': medicine_data.get('description'),
                'price': medicine_data.get('price'),
                'photo': medicine_data.get('photo')
            }
            response = self.supabase.table('medicines').insert(data).execute()
            return True
        except Exception as e:
            print(f"Error adding medicine: {e}")
            return False
    
    async def update_medicine(self, med_id: str, medicine_data: Dict) -> bool:
        """Update medicine in database"""
        try:
            response = self.supabase.table('medicines').update(medicine_data).eq('id', med_id).execute()
            return True
        except Exception as e:
            print(f"Error updating medicine: {e}")
            return False
    
    async def delete_medicine(self, med_id: str) -> bool:
        """Delete medicine from database"""
        try:
            response = self.supabase.table('medicines').delete().eq('id', med_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting medicine: {e}")
            return False
    
    # Order operations
    async def get_all_orders(self) -> Dict[str, Dict]:
        """Get all orders from database"""
        try:
            response = self.supabase.table('orders').select('*').order('created_at', desc=True).execute()
            orders = {}
            for order in response.data:
                orders[order['id']] = {
                    'order_id': order['id'],
                    'user_id': order['user_id'],
                    'username': order.get('username'),
                    'full_name': order.get('full_name'),
                    'medicine': order['medicine'],
                    'months': order.get('months', 1),
                    'price': order.get('price'),
                    'status': order.get('status', 'new'),
                    'timestamp': order['created_at'],
                    'delivery_info': {
                        'region': order.get('delivery_region'),
                        'district': order.get('delivery_district'),
                        'address': order.get('delivery_address'),
                        'phone': order.get('phone_number')
                    },
                    'receipt_photo_id': order.get('receipt_photo_id')
                }
            return orders
        except Exception as e:
            print(f"Error getting orders: {e}")
            return {}
    
    async def add_order(self, order_data: Dict) -> bool:
        """Add a new order to database"""
        try:
            data = {
                'id': order_data['order_id'],
                'user_id': order_data['user_id'],
                'username': order_data.get('username'),
                'full_name': order_data.get('full_name'),
                'medicine': order_data['medicine'],
                'months': order_data.get('months', 1),
                'price': order_data.get('price'),
                'status': order_data.get('status', 'new'),
                'delivery_region': order_data['delivery_info'].get('region'),
                'delivery_district': order_data['delivery_info'].get('district'),
                'delivery_address': order_data['delivery_info'].get('address'),
                'phone_number': order_data['delivery_info'].get('phone'),
                'receipt_photo_id': order_data.get('receipt_photo_id')
            }
            response = self.supabase.table('orders').insert(data).execute()
            return True
        except Exception as e:
            print(f"Error adding order: {e}")
            return False
    
    async def update_order_status(self, order_id: str, status: str) -> bool:
        """Update order status in database"""
        try:
            response = self.supabase.table('orders').update({
                'status': status,
                'updated_at': 'NOW()'
            }).eq('id', order_id).execute()
            return True
        except Exception as e:
            print(f"Error updating order status: {e}")
            return False

# Global database manager instance
db = DatabaseManager()
