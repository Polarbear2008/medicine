import asyncio
import datetime
import json
import logging
import os
import uuid
from typing import Dict, List, Optional, Tuple, Union

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
    Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, LinkPreviewOptions
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot, dispatcher and storage
storage = MemoryStorage()
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher(storage=storage)

# --- Data --- #

# --- Data Loading --- #

MEDICINES_FILE = 'medicines.json'
ORDERS_FILE = 'orders.json'

def load_medicines():
    default_medicines = {
        'paracetamol': {
            'name': 'Paratsetamol 500mg',
            'price': 5000,
            'description': 'Isitma va og\'riqni qoldirish uchun. Kerak bo\'lganda har 4-6 soatda 1-2 tabletkadan iching.',
            'photo': None
        },
        'ibuprofen': {
            'name': 'Ibuprofen 400mg',
            'price': 8000,
            'description': 'Og\'riq, isitma va yallig\'lanish uchun. Har 6-8 soatda ovqat bilan birga 1 tabletkadan iching.',
            'photo': None
        },
        'vitamin_c': {
            'name': 'Vitamin C 1000mg',
            'price': 12000,
            'description': 'Immun tizimini qo\'llab-quvvatlash. Har kuni ovqat bilan birga 1 tabletkadan iching.',
            'photo': None
        },
        'omeprazole': {
            'name': 'Omeprazol 20mg',
            'price': 9500,
            'description': 'Jig\'ildon qaynashi va kislota reflyuksi uchun. Har kuni nonushtadan oldin 1 kapsuladan iching.',
            'photo': None
        },
        'cetirizine': {
            'name': 'Setirizin 10mg',
            'price': 7500,
            'description': 'Allergiya va burun to\'silishi uchun. Har kuni kechqurun 1 tabletkadan iching.',
            'photo': None
        }
    }
    
    if not os.path.exists(MEDICINES_FILE):
        # Create the file with default data if it doesn't exist
        with open(MEDICINES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_medicines, f, ensure_ascii=False, indent=2)
        return default_medicines
        
    try:
        with open(MEDICINES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading {MEDICINES_FILE}: {e}")
        # Return default medicines if there's an error loading the file
        return default_medicines

def save_medicines(medicines: Dict[str, Dict]) -> None:
    """Save medicines to JSON file"""
    try:
        # Only create directory if there is a directory path in MEDICINES_FILE
        dir_path = os.path.dirname(MEDICINES_FILE)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        with open(MEDICINES_FILE, 'w', encoding='utf-8') as f:
            json.dump(medicines, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error saving medicines: {e}")
        raise

def load_orders() -> Dict[str, Dict]:
    """Load orders from JSON file"""
    try:
        with open(ORDERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_orders(orders: Dict[str, Dict]) -> None:
    """Save orders to JSON file"""
    with open(ORDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2, default=str)

def update_order_status(order_id: str, new_status: str, admin_username: str = None) -> Optional[Dict]:
    """Update order status and return the updated order"""
    orders = load_orders()
    if order_id not in orders:
        return None
    
    order = orders[order_id]
    old_status = order.get('status', 'yangi')
    order['status'] = new_status
    
    # Add status history
    if 'status_history' not in order:
        order['status_history'] = []
    
    status_update = {
        'status': new_status,
        'timestamp': datetime.now().isoformat(),
        'changed_by': admin_username or 'system'
    }
    order['status_history'].append(status_update)
    
    # Update timestamps
    if new_status == 'processing':
        order['processing_at'] = datetime.now().isoformat()
    elif new_status == 'completed':
        order['completed_at'] = datetime.now().isoformat()
    elif new_status == 'cancelled':
        order['cancelled_at'] = datetime.now().isoformat()
    
    orders[order_id] = order
    save_orders(orders)
    
    # Log the status change
    logging.info(f"Order {order_id} status changed from {old_status} to {new_status} by {admin_username or 'system'}")
    
    return order

# Load medicines at startup
MEDICINES = load_medicines()

# User baskets storage (using FSM storage for simplicity)
user_baskets = {}

# --- Keyboards --- #

def get_admin_panel_keyboard():
    # Load orders to check for new ones
    orders = load_orders()
    new_orders = sum(1 for o in orders.values() if o.get('status') == 'yangi')
    
    orders_btn = f"📥 Buyurtmalar"
    if new_orders > 0:
        orders_btn += f" ({new_orders} new)"
    
    buttons = [
        [InlineKeyboardButton(text=orders_btn, callback_data='admin_list_orders')],
        [
            InlineKeyboardButton(text="➕ Dori qo'shish", callback_data='admin_add_medicine'),
            InlineKeyboardButton(text="📋 Dorilar", callback_data='admin_list_medicines')
        ],
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data='admin_stats'),
            InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data='admin_settings')
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Main menu keyboard
def get_main_menu():
    buttons = [
        [KeyboardButton(text='🏬 Do\'kon'), KeyboardButton(text='📦 Savat')],
        [KeyboardButton(text='📞 Aloqa'), KeyboardButton(text='❓ Yordam')]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard

# Store menu keyboard
def get_store_menu():
    buttons = []
    for med_id, med in MEDICINES.items():
        buttons.append([InlineKeyboardButton(text=med['name'], callback_data=f'med_{med_id}')])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

# Medicine detail keyboard
def get_medicine_detail_keyboard(med_id):
    buttons = [
        [InlineKeyboardButton(text='➕ Savatga qo\'shish', callback_data=f'add_{med_id}'),
         InlineKeyboardButton(text='🛒 Hozir sotib olish', callback_data=f'buy_{med_id}')],
        [InlineKeyboardButton(text='🔙 Do\'konga qaytish', callback_data='back_to_store')]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

# Basket keyboard
def get_basket_keyboard(user_id):
    buttons = []
    if user_id in user_baskets and user_baskets[user_id]:
        buttons.append([InlineKeyboardButton(text='💳 To\'lov', callback_data='checkout')])
    buttons.append([InlineKeyboardButton(text='🏠 Bosh menyu', callback_data='main_menu')])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_checkout_options_keyboard():
    buttons = [
        [InlineKeyboardButton(text="👨‍💼 Administrator bilan bog'lanish", callback_data='contact_admin')],
        [InlineKeyboardButton(text="✅ Buyurtmani tasdiqlash", callback_data='send_order')],
        [InlineKeyboardButton(text='⬅️ Ortga', callback_data='back_to_basket')]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

# --- FSM for Adding Medicine ---

class AddMedicine(StatesGroup):
    name = State()
    price = State()
    description = State()
    photo = State()

class EditMedicine(StatesGroup):
    choosing_field = State()
    editing_field = State()

class Checkout(StatesGroup):
    waiting_for_address = State()
    waiting_for_payment = State()
    waiting_for_confirmation = State()
    waiting_for_receipt = State()


# --- Admin Handlers ---

# Custom filter to check for admin
class IsAdmin(Filter):
    def __init__(self):
        self.admin_id = os.getenv('ADMIN_ID')

    async def __call__(self, message: Message) -> bool:
        return str(message.from_user.id) == self.admin_id

@dp.message(Command("admin"), IsAdmin())
async def admin_panel(message: Message):
    await message.answer("Salom, admin! Admin panelga xush kelibsiz.", reply_markup=get_admin_panel_keyboard())

@dp.callback_query(F.data == 'admin_panel', IsAdmin())
async def admin_panel_callback(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text("Salom, admin! Admin panelga xush kelibsiz.", reply_markup=get_admin_panel_keyboard())
    await callback_query.answer()


@dp.callback_query(F.data == 'admin_list_medicines', IsAdmin())
async def list_medicines(callback_query: types.CallbackQuery):
    medicines = load_medicines()
    if not medicines:
        await callback_query.message.edit_text(
            "Hozirda dorilar mavjud emas.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Ortga", callback_data='admin_panel')]
            ])
        )
        await callback_query.answer()
        return

    buttons = []
    for med_id, med in medicines.items():
        buttons.append([InlineKeyboardButton(text=med['name'], callback_data=f'admin_view_med_{med_id}')])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data='admin_panel')])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback_query.message.edit_text("Barcha dorilar ro'yxati:", reply_markup=keyboard)
    await callback_query.answer()


@dp.callback_query(F.data.startswith('admin_view_med_'), IsAdmin())
async def view_medicine(callback_query: types.CallbackQuery):
    med_id = callback_query.data.removeprefix('admin_view_med_')
    med = load_medicines().get(med_id)

    if not med:
        await callback_query.answer("Dori topilmadi.", show_alert=True)
        return

    message_text = (
        f"*{med['name']}*\n\n"
        f"*ID:* `{med_id}`\n"
        f"*Narx:* {med['price']} so'm\n"
        f"*Tavsif:* {med['description']}"
    )
    
    buttons = [
        [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f'admin_edit_med_{med_id}')],
        [InlineKeyboardButton(text="❌ O'chirish", callback_data=f'admin_delete_med_{med_id}')],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data='admin_list_medicines')]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback_query.message.edit_text(message_text, parse_mode='Markdown', reply_markup=keyboard)
    await callback_query.answer()


@dp.callback_query(F.data.startswith('admin_delete_med_'), IsAdmin())
async def delete_medicine_confirm(callback_query: types.CallbackQuery):
    med_id = callback_query.data.removeprefix('admin_delete_med_')
    med = load_medicines().get(med_id)

    if not med:
        await callback_query.answer("Dori topilmadi.", show_alert=True)
        return

    buttons = [
        [InlineKeyboardButton(text=f"✅ Ha, o'chirish", callback_data=f'admin_confirm_delete_{med_id}')],
        [InlineKeyboardButton(text="❌ Yo'q, bekor qilish", callback_data=f'admin_view_med_{med_id}')]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback_query.message.edit_text(f"Haqiqatan ham '{med['name']}' dorisini o'chirmoqchimisiz?", reply_markup=keyboard)
    await callback_query.answer()


@dp.callback_query(F.data.startswith('admin_edit_med_'), IsAdmin())
async def edit_medicine_start(callback_query: types.CallbackQuery, state: FSMContext):
    med_id = callback_query.data.removeprefix('admin_edit_med_')
    await state.update_data(med_id=med_id)
    await state.set_state(EditMedicine.choosing_field)

    buttons = [
        [InlineKeyboardButton(text="Nomi", callback_data='edit_name')],
        [InlineKeyboardButton(text="Narxi", callback_data='edit_price')],
        [InlineKeyboardButton(text="Tavsifi", callback_data='edit_description')],
        [InlineKeyboardButton(text="Rasmi", callback_data='edit_photo')],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data=f'admin_view_med_{med_id}')]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback_query.message.edit_text("Qaysi maydonni tahrirlamoqchisiz?", reply_markup=keyboard)
    await callback_query.answer()


@dp.callback_query(F.data.startswith('edit_'), IsAdmin(), EditMedicine.choosing_field)
async def edit_medicine_field_selected(callback_query: types.CallbackQuery, state: FSMContext):
    field_to_edit = callback_query.data.split('_')[1]
    await state.update_data(field_to_edit=field_to_edit)
    await state.set_state(EditMedicine.editing_field)

    if field_to_edit == 'photo':
        await callback_query.message.edit_text("Yangi rasmni yuboring yoki 'ochirish' deb yozing.")
    else:
        await callback_query.message.edit_text(f"Yangi qiymatni kiriting:")
    await callback_query.answer()


@dp.message(EditMedicine.editing_field, IsAdmin())
async def edit_medicine_field_value_provided(message: Message, state: FSMContext):
    data = await state.get_data()
    med_id = data['med_id']
    field_to_edit = data['field_to_edit']
    medicines = load_medicines()

    if field_to_edit == 'photo':
        if message.photo:
            medicines[med_id][field_to_edit] = message.photo[-1].file_id
        elif message.text.lower() == 'ochirish':
            medicines[med_id][field_to_edit] = None
        else:
            await message.answer("Iltimos, rasm yuboring yoki 'ochirish' deb yozing.")
            return
    else:
        medicines[med_id][field_to_edit] = message.text

    save_medicines(medicines)
    global MEDICINES
    MEDICINES = medicines

    await message.answer("✅ Muvaffaqiyatli o'zgartirildi!")
    await state.clear()

    # Create a dummy callback query to refresh the view
    from aiogram.types import User, Chat
    dummy_callback_query = types.CallbackQuery(
        id='dummy', 
        from_user=message.from_user, 
        chat_instance='', 
        message=message, 
        data=f'admin_view_med_{med_id}'
    )
    await view_medicine(dummy_callback_query)


@dp.callback_query(F.data.startswith('admin_confirm_delete_'), IsAdmin())
async def delete_medicine_execute(callback_query: types.CallbackQuery):
    med_id = callback_query.data.removeprefix('admin_confirm_delete_')
    medicines = load_medicines()
    
    if med_id in medicines:
        deleted_med_name = medicines[med_id]['name']
        del medicines[med_id]
        save_medicines(medicines)
        global MEDICINES
        MEDICINES = medicines
        await callback_query.answer(f"'{deleted_med_name}' dorisi o'chirildi.", show_alert=True)
        await list_medicines(callback_query) # Refresh the list
    else:
        await callback_query.answer("Dori topilmadi.", show_alert=True)

@dp.callback_query(F.data.startswith('call_customer_'))
async def handle_call_customer(callback_query: types.CallbackQuery):
    """Handle call customer button click"""
    try:
        phone_number = callback_query.data.split('_', 2)[2]
        if not phone_number:
            await callback_query.answer("Telefon raqami topilmadi.", show_alert=True)
            return
            
        # Create a clickable phone link
        phone_link = f"tel:{phone_number}"
        await callback_query.answer("Telefon raqami nusxalandi!")
        
        # Send the phone number as a clickable link
        await callback_query.message.answer(
            f"📞 Mijozga qo'ng'iroq qilish uchun: <a href='{phone_link}'>{phone_number}</a>",
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
        # Extract order ID from message text
        message_text = callback_query.message.text or ""
        if 'Buyurtma #' in message_text:
            order_id = message_text.split('Buyurtma #')[1].split('\n')[0].strip()
            await admin_view_order_details(callback_query, order_id)
            
    except Exception as e:
        logging.error(f"Error handling call customer: {e}")
        await callback_query.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.", show_alert=True)


@dp.callback_query(F.data.startswith('admin_list_orders') | F.data.startswith('filter_'), IsAdmin())
async def admin_list_orders(callback_query: types.CallbackQuery):
    orders = load_orders()
    if not orders:
        await callback_query.message.edit_text(
            "Hozirda buyurtmalar mavjud emas.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Ortga", callback_data='admin_panel')]
            ])
        )
        await callback_query.answer()
        return

    # Get filter type from callback data
    filter_type = 'all'
    if callback_query.data.startswith('filter_'):
        filter_type = callback_query.data.split('_', 1)[1]

    # Filter buttons
    filter_buttons = [
        [
            InlineKeyboardButton(text="🆕 Yangi" + (" ✓" if filter_type == 'new' else ""), 
                              callback_data='filter_new'),
            InlineKeyboardButton(text="🔄 Jarayonda" + (" ✓" if filter_type == 'processing' else ""), 
                              callback_data='filter_processing'),
            InlineKeyboardButton(text="✅ Bajarildi" + (" ✓" if filter_type == 'completed' else ""), 
                              callback_data='filter_completed')
        ],
        [
            InlineKeyboardButton(text="❌ Bekor qilingan" + (" ✓" if filter_type == 'cancelled' else ""), 
                              callback_data='filter_cancelled'),
            InlineKeyboardButton(text="🔍 Barchasi" + (" ✓" if filter_type == 'all' else ""), 
                              callback_data='filter_all')
        ]
    ]

    # Filter orders
    filtered_orders = []
    for order_id, order in orders.items():
        if filter_type == 'all' or order.get('status') == filter_type:
            filtered_orders.append((order_id, order))
    
    # Sort by timestamp (newest first)
    filtered_orders.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)

    # Create order buttons
    order_buttons = []
    for order_id, order in filtered_orders[:10]:  # Show first 10 orders
        status_emoji = {
            'yangi': '🆕',
            'processing': '🔄',
            'completed': '✅',
            'cancelled': '❌'
        }.get(order.get('status', 'yangi'), '❓')
        
        user_name = order.get('first_name', 'Mijoz')
        order_time = datetime.datetime.fromisoformat(order.get('timestamp', '')).strftime('%d.%m %H:%M')
        total = sum(item.get('price', 0) * item.get('quantity', 1) for item in order.get('items', []))
        
        order_buttons.append([
            InlineKeyboardButton(
                text=f"{status_emoji} #{order_id[:6]} | {user_name} | {total:,} so'm | {order_time}",
                callback_data=f'admin_view_order_{order_id}'
            )
        ])

    # Navigation buttons
    nav_buttons = [
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data='admin_list_orders')],
        [InlineKeyboardButton(text="📊 Statistika", callback_data='admin_stats')],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data='admin_panel')]
    ]

    # Combine all buttons
    all_buttons = filter_buttons + order_buttons + nav_buttons
    
    # Add stats
    stats = {
        'total': len(orders),
        'new': sum(1 for o in orders.values() if o.get('status') == 'yangi'),
        'processing': sum(1 for o in orders.values() if o.get('status') == 'processing'),
        'completed': sum(1 for o in orders.values() if o.get('status') == 'completed'),
        'cancelled': sum(1 for o in orders.values() if o.get('status') == 'cancelled')
    }
    
    stats_text = (
        "📊 *Buyurtmalar statistikasi*\n\n"
        f"🆕 Yangi: {stats['new']} | "
        f"🔄 Jarayonda: {stats['processing']}\n"
        f"✅ Bajarildi: {stats['completed']} | "
        f"❌ Bekor: {stats['cancelled']}\n\n"
        f"📌 Jami: {stats['total']} ta"
    )
    
    await callback_query.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=all_buttons),
        parse_mode='Markdown'
    )
    await callback_query.answer()


@dp.callback_query(F.data.startswith('admin_approve_order_'), IsAdmin())
async def admin_approve_order(callback_query: types.CallbackQuery):
    order_id = callback_query.data.split('_')[-1]
    orders = load_orders()
    order = orders.get(order_id)

    if not order:
        await callback_query.answer("Buyurtma topilmadi.", show_alert=True)
        return

    orders[order_id]['status'] = 'tasdiqlandi' # approved
    save_orders(orders)

    await callback_query.answer("Buyurtma tasdiqlandi.", show_alert=True)

    try:
        await bot.send_message(order['user_id'], f"Sizning #{order_id[:8]} raqamli buyurtmangiz tasdiqlandi!")
    except Exception as e:
        logging.error(f"Failed to send approval message to user {order['user_id']}: {e}")

    await admin_view_order_details(callback_query, order_id=order_id) # Refresh view


@dp.callback_query(F.data.startswith('admin_reject_order_'), IsAdmin())
async def admin_reject_order(callback_query: types.CallbackQuery):
    order_id = callback_query.data.split('_')[-1]
    orders = load_orders()
    order = orders.get(order_id)

    if not order:
        await callback_query.answer("Buyurtma topilmadi.", show_alert=True)
        return

    orders[order_id]['status'] = 'rad etildi' # rejected
    save_orders(orders)

    await callback_query.answer("Buyurtma rad etildi.", show_alert=True)

    try:
        await bot.send_message(order['user_id'], f"Afsuski, sizning #{order_id[:8]} raqamli buyurtmangiz rad etildi.")
    except Exception as e:
        logging.error(f"Failed to send rejection message to user {order['user_id']}: {e}")

    await admin_view_order_details(callback_query, order_id=order_id) # Refresh view


@dp.callback_query(F.data.startswith('order_status_'), IsAdmin())
async def handle_order_status_update(callback_query: types.CallbackQuery):
    """Handle order status updates from admin"""
    try:
        # Extract order_id and new_status from callback data (format: order_status_<order_id>_<new_status>)
        _, order_id, new_status = callback_query.data.split('_')
    except ValueError:
        await callback_query.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.", show_alert=True)
        return
    
    # Get admin username for logging
    admin_username = callback_query.from_user.username or "admin"
    
    # Update order status
    order = update_order_status(order_id, new_status, admin_username)
    if not order:
        await callback_query.answer("Buyurtma topilmadi yoki yangilanishda xatolik yuz berdi.", show_alert=True)
        return
    
    # Status display names
    status_names = {
        'yangi': '🆕 Yangi',
        'processing': '🔄 Jarayonda',
        'completed': '✅ Bajarildi',
        'cancelled': '❌ Bekor qilingan'
    }
    
    # Notify admin
    status_display = status_names.get(new_status, new_status.capitalize())
    await callback_query.answer(f"Buyurtma holati " + status_display + " ga o'zgartirildi.")
    
    # Update the message to show new status
    await admin_view_order_details(callback_query, order_id)
    
    # Notify user if their order status was changed
    if 'user_id' in order:
        try:
            user_id = order['user_id']
            user_message = (
                f"📢 Sizning #{order_id[:6]} raqamli buyurtmangizning holati o'zgartirildi.\n"
                f"🔄 Yangi holat: {status_display}"
            )
            
            # Add cancellation reason if available
            if new_status == 'cancelled' and order.get('cancellation_reason'):
                user_message += f"\n\n❌ Sabab: {order['cancellation_reason']}"
            
            await bot.send_message(
                chat_id=user_id,
                text=user_message
            )
        except Exception as e:
            logging.error(f"Error notifying user about order status update: {e}")

@dp.callback_query(F.data.startswith('admin_view_order_'), IsAdmin())
async def admin_view_order_details(callback_query: types.CallbackQuery, order_id: str = None):
    if not order_id:
        order_id = callback_query.data.split('_')[-1]
    
    orders = load_orders()
    order = orders.get(order_id)

    if not order:
        await callback_query.answer("Buyurtma topilmadi.", show_alert=True)
        return
        
    # Format order details
    status_emoji = {
        'yangi': '🆕',
        'processing': '🔄',
        'completed': '✅',
        'cancelled': '❌'
    }.get(order.get('status', 'yangi'), '❓')
    
    # Format order time
    try:
        order_time = datetime.datetime.fromisoformat(order.get('timestamp', '')).strftime('%d.%m.%Y %H:%M')
    except:
        order_time = "Noma'lum vaqt"
    
    # Format user info
    user_info = []
    if order.get('first_name'):
        user_info.append(order['first_name'])
    if order.get('username'):
        user_info.append(f"@{order['username']}")
    if not user_info:
        user_info = ["Mijoz"]
    
    # Format order items
    order_items = []
    total_amount = 0
    for item in order.get('items', []):
        med = MEDICINES.get(item.get('id', ''), {})
        name = med.get('name', 'Noma\'lum dori')
        price = int(item.get('price', 0))
        quantity = int(item.get('quantity', 1))
        item_total = price * quantity
        total_amount += item_total
        order_items.append(f"• {name} x{quantity} = {item_total:,} so'm")
    
    # Build order details message
    message_text = (
        f"📦 *Buyurtma #{order_id[:6]}*\n"
        f"📅 *Sana:* {order_time}\n"
        f"👤 *Mijoz:* {' '.join(user_info)}\n"
        f"📱 *Telefon:* {order.get('phone_number', 'N/A')}\n"
        f"📍 *Manzil:* {order.get('address', 'N/A')}\n"
        f"📊 *Holat:* {status_emoji} {order.get('status', 'yangi').capitalize()}\n\n"
        f"📋 *Buyurtma tarkibi:*\n" + '\n'.join(order_items) + '\n\n'
        f"💵 *Jami:* {total_amount:,} so'm"
    )
    
    # Build action buttons
    action_buttons = []
    
    # Status update buttons
    current_status = order.get('status', 'yangi')
    status_buttons = []
    
    if current_status != 'processing':
        status_buttons.append(InlineKeyboardButton(
            text="🔄 Jarayonga qo'shish",
            callback_data=f'order_status_{order_id}_processing'
        ))
    
    if current_status != 'completed':
        status_buttons.append(InlineKeyboardButton(
            text="✅ Bajarildi",
            callback_data=f'order_status_{order_id}_completed'
        ))
    
    if current_status != 'cancelled':
        status_buttons.append(InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data=f'order_status_{order_id}_cancelled'
        ))
    
    if status_buttons:
        action_buttons.append(status_buttons)
    
    # Additional actions
    action_buttons.extend([
        [
            InlineKeyboardButton(
                text="📞 Qo'ng'iroq qilish",
                callback_data=f'call_customer_{order.get("phone_number", "")}'
            ) if order.get('phone_number') else None,
            InlineKeyboardButton(
                text="📝 Izoh qo'shish",
                callback_data=f'add_note_{order_id}'
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Orqaga",
                callback_data='admin_list_orders'
            ),
            InlineKeyboardButton(
                text="🔄 Yangilash",
                callback_data=f'admin_view_order_{order_id}'
            )
        ]
    ])
    
    # Remove any None values from buttons
    action_buttons = [[btn for btn in row if btn is not None] for row in action_buttons if any(btn is not None for btn in row)]
    
    # Create keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=action_buttons)
    
    # Edit the message with new content
    try:
        await callback_query.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"Error updating order details: {e}")
        await callback_query.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.", show_alert=True)
        return
    
    await callback_query.answer()

    # Mark as viewed if it was new
    if order.get('status') == 'yangi':
        order['status'] = 'processing'
        orders[order_id] = order
        save_orders(orders)

    # Format user info
    user_info = []
    if order.get('first_name'):
        user_info.append(order['first_name'])
    if order.get('username'):
        user_info.append(f"@{order['username']}")
    if not user_info:
        user_info = ["Mijoz"]
    
    # Format order time
    try:
        order_time = datetime.datetime.fromisoformat(order.get('timestamp', '')).strftime('%d.%m.%Y %H:%M')
    except:
        order_time = "Noma'lum vaqt"

    # Format order items
    order_items = []
    total_amount = 0
    for item in order.get('items', []):
        med = MEDICINES.get(item.get('id', ''), {})
        name = med.get('name', 'Noma\'lum dori')
        price = int(item.get('price', 0))
        quantity = int(item.get('quantity', 1))
        item_total = price * quantity
        total_amount += item_total
        order_items.append(f"• {name} x{quantity} = {item_total:,} so'm")

    # Format status
    status_emoji = {
        'yangi': '🆕 Yangi',
        'processing': '🔄 Jarayonda',
        'completed': '✅ Bajarildi',
        'cancelled': '❌ Bekor qilingan'
    }.get(order.get('status', 'yangi'), '❓ Noma\'lum')

    # Build order details message
    message_text = (
        f"📦 *Buyurtma #{order_id[:6]}*\n"
        f"📅 *Sana:* {order_time}\n"
        f"👤 *Mijoz:* {' '.join(user_info)}\n"
        f"📱 *Telefon:* {order.get('phone_number', 'N/A')}\n"
        f"📍 *Manzil:* {order.get('address', 'N/A')}\n"
        f"📊 *Holat:* {status_emoji}\n\n"
        f"📋 *Buyurtma tarkibi:*\n" + '\n'.join(order_items) + '\n\n'
        f"💵 *Jami:* {total_amount:,} so'm"
    )

    # Build action buttons
    action_buttons = []
    
    # Status update buttons
    status_buttons = []
    if order.get('status') != 'processing':
        status_buttons.append(InlineKeyboardButton(text="🔄 Jarayonga qo'shish", 
                                                callback_data=f'order_status_{order_id}_processing'))
    if order.get('status') != 'completed':
        status_buttons.append(InlineKeyboardButton(text="✅ Bajarildi", 
                                                callback_data=f'order_status_{order_id}_completed'))
    if order.get('status') != 'cancelled':
        status_buttons.append(InlineKeyboardButton(text="❌ Bekor qilish", 
                                                callback_data=f'order_status_{order_id}_cancelled'))
    
    if status_buttons:
        action_buttons.append(status_buttons)

    # Additional actions
    action_buttons.extend([
        [
            InlineKeyboardButton(text="📞 Qo'ng'iroq qilish", 
                              callback_data=f'call_customer_{order.get("phone_number", "")}'),
            InlineKeyboardButton(text="📝 Izoh qo'shish", 
                              callback_data=f'add_note_{order_id}')
        ],
        [
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data='admin_list_orders'),
            InlineKeyboardButton(text="🔄 Yangilash", callback_data=f'admin_view_order_{order_id}')
        ]
    ])

    # Add receipt if exists
    if order.get('receipt_file_id'):
        try:
            await callback_query.message.answer_photo(
                photo=order['receipt_file_id'],
                caption=f"📎 To'lov cheki (Buyurtma #{order_id[:6]})"
            )
        except Exception as e:
            logging.error(f"Failed to send receipt: {e}")
            action_buttons.insert(0, [
                InlineKeyboardButton(text="❌ Chek yuklashda xatolik", 
                                  callback_data='error_receipt')
            ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=action_buttons)
    
    await callback_query.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback_query.answer()
    
    basket_items = []
    total_price = 0
    medicines = load_medicines()
    for med_id, quantity in order['basket'].items():
        med = medicines.get(med_id)
        if med:
            price = int(med['price']) * quantity
            total_price += price
            basket_items.append(f"- {med['name']} x {quantity} = {price} so'm")
    
    basket_text = "\n".join(basket_items)
    
    message_text = (
        f"*Buyurtma Tafsilotlari*\n\n"
        f"*ID:* `{order_id}`\n"
        f"*Vaqt:* {order_time}\n"
        f"*Mijoz:* {user_info}\n"
        f"*Status:* {order['status']}\n\n"
        f"*Savatcha:*\n{basket_text}\n\n"
        f"*Jami:* {total_price} so'm"
    )

    buttons = [
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f'admin_approve_order_{order_id}')],
        [InlineKeyboardButton(text="❌ Rad etish", callback_data=f'admin_reject_order_{order_id}')],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data='admin_list_orders')]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback_query.message.edit_text(message_text, parse_mode='Markdown', reply_markup=keyboard)
    await callback_query.answer()


@dp.callback_query(F.data == 'admin_add_medicine', IsAdmin())
async def add_medicine_start(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddMedicine.name)
    await callback_query.message.answer("Yangi dori nomini kiriting:")
    await callback_query.answer()


@dp.message(AddMedicine.name, IsAdmin())
async def add_medicine_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddMedicine.price)
    await message.answer("Endi dori narxini kiriting (faqat raqamlarda):")


@dp.message(AddMedicine.price, IsAdmin())
async def add_medicine_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Narxni raqamlarda kiriting.")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AddMedicine.description)
    await message.answer("Dori haqida ma'lumot kiriting:")


@dp.message(AddMedicine.description, IsAdmin())
async def add_medicine_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddMedicine.photo)
    await message.answer("Dori rasmini yuboring yoki 'tashlab ketish' deb yozing:")


@dp.message(AddMedicine.photo, F.photo, IsAdmin())
async def add_medicine_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await finalize_add_medicine(message, state)


@dp.message(AddMedicine.photo, F.text == 'tashlab ketish', IsAdmin())
async def skip_medicine_photo(message: Message, state: FSMContext):
    await state.update_data(photo=None)
    await finalize_add_medicine(message, state)


async def finalize_add_medicine(message: Message, state: FSMContext):
    data = await state.get_data()
    medicines = load_medicines()
    
    # Create a simple ID from the name
    med_id = data['name'].lower().replace(' ', '_')
    
    medicines[med_id] = {
        'name': data['name'],
        'price': data['price'],
        'description': data['description'],
        'photo': data['photo']
    }
    
    save_medicines(medicines)
    global MEDICINES
    MEDICINES = medicines
    
    await message.answer(f"✅ Dori '{data['name']}' muvaffaqiyatli qo'shildi!", reply_markup=get_admin_panel_keyboard())
    await state.clear()


# --- Command Handlers --- #

@dp.message(CommandStart())
async def send_welcome(message: Message):
    await message.answer(
        "MedBot ga xush kelibsiz! 🏥\n"
        "Do\'konimizni ko\'zdan kechirish uchun quyidagi menyudan foydalaning.",
        reply_markup=get_main_menu()
    )

# --- Message Handlers for Main Menu --- #

@dp.message(F.text == '🏬 Do\'kon')
async def show_store(message: Message):
    await message.answer("Iltimos, dorini tanlang:", reply_markup=get_store_menu())

async def get_basket_text_and_keyboard(user_id):
    if user_id not in user_baskets or not user_baskets[user_id]:
        return "Sizning savatingiz bo'sh.", get_basket_keyboard(user_id)
    
    basket = user_baskets[user_id]
    total = 0
    medicines = load_medicines() # Ensure we have the latest data
    basket_text = "🛒 *Sizning savatingiz*\n\n"
    
    for med_id, quantity in basket.items():
        med = medicines.get(med_id)
        if med:
            price = int(med['price']) * quantity
            total += price
            basket_text += f"{med['name']} x{quantity} = {price} so'm\n"
    
    basket_text += f"\n*Jami: {total} so'm*"
    return basket_text, get_basket_keyboard(user_id)

@dp.message(F.text == '📦 Savat')
async def show_basket_handler(message: Message):
    user_id = message.from_user.id
    basket_text, keyboard = await get_basket_text_and_keyboard(user_id)
    await message.answer(basket_text, parse_mode='Markdown', reply_markup=keyboard)

@dp.message(F.text == '📞 Aloqa')
async def show_contact(message: Message):
    contact_text = (
        "📞 *Biz bilan bog\'laning*\n\n"
        "Telefon: +998 (XX) XXX-XX-XX\n"
        "Manzil: [Google Xaritalar](https://goo.gl/maps/example)\n"
        "Ish vaqti: 9:00 - 21:00"
    )
    await message.answer(contact_text, parse_mode='Markdown', disable_web_page_preview=True)

@dp.message(F.text == '❓ Yordam')
async def show_help(message: Message):
    help_text = (
        "*MedBot dan qanday foydalanish*\n\n"
        "🏬 *Do\'kon* - Dori-darmonlar ro\'yxatini ko\'rish\n"
        "📦 *Savat* - Tanlangan mahsulotlarni ko\'rish va to\'lovga o\'tish\n"
        "📞 *Aloqa* - Bizning aloqa ma\'lumotlarimiz\n\n"
        "Savatga mahsulot qo\'shish uchun:\n"
        "1. *Do\'kon* bo\'limiga o\'ting\n"
        "2. Kerakli dorini tanlang\n"
        "3. *Savatga qo\'shish* tugmasini bosing\n\n"
        "Barcha savollar bo\'yicha biz bilan bog\'laning."
    )
    await message.answer(help_text, parse_mode='Markdown')

# --- Callback Query Handlers --- #

@dp.callback_query(F.data == 'back_to_store')
async def process_callback_back_to_store(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text(
        "Iltimos, dorini tanlang:",
        reply_markup=get_store_menu()
    )
    await callback_query.answer()

@dp.callback_query(F.data.startswith('med_'))
async def process_callback_medicine(callback_query: types.CallbackQuery):
    med_id = callback_query.data.removeprefix('med_')
    med = MEDICINES[med_id]
    
    message_text = (
        f"*{med['name']}*\n\n"
        f"💊 *Tavsif*: {med['description']}\n"
        f"💰 *Narx*: {med['price']} so'm"
    )

    if med.get('photo'):
        await callback_query.message.answer_photo(
            photo=med['photo'],
            caption=message_text,
            parse_mode='Markdown',
            reply_markup=get_medicine_detail_keyboard(med_id)
        )
        await callback_query.message.delete() # delete the old text-only message
    else:
        await callback_query.message.edit_text(
            message_text,
            parse_mode='Markdown',
            reply_markup=get_medicine_detail_keyboard(med_id)
        )

    await callback_query.answer()

@dp.callback_query(F.data.startswith('add_'))
async def process_callback_add_to_basket(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    med_id = callback_query.data.removeprefix('add_')
    
    if user_id not in user_baskets:
        user_baskets[user_id] = {}
    
    user_baskets[user_id][med_id] = user_baskets[user_id].get(med_id, 0) + 1
    
    await callback_query.answer(f"✅ {MEDICINES[med_id]['name']} savatingizga qo\'shildi.")


@dp.callback_query(F.data.startswith('buy_'))
async def process_callback_buy_now(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    med_id = callback_query.data.removeprefix('buy_')
    
    # Add to basket first
    if user_id not in user_baskets:
        user_baskets[user_id] = {}
    user_baskets[user_id][med_id] = user_baskets[user_id].get(med_id, 0) + 1
    
    # Then start checkout
    await state.set_state(Checkout.waiting_for_address)
    await callback_query.message.edit_text(
        "Iltimos, yetkazib berish uchun to'liq manzilingizni kiriting (shahar, tuman, ko'cha, uy raqami):"
    )
    await callback_query.answer()

@dp.callback_query(F.data == 'checkout')
async def process_callback_checkout(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if user_id not in user_baskets or not user_baskets[user_id]:
        await callback_query.answer("Sizning savatingiz bo'sh.", show_alert=True)
        return

    await state.set_state(Checkout.waiting_for_address)
    await callback_query.message.edit_text(
        "Iltimos, yetkazib berish uchun to'liq manzilingizni kiriting (shahar, tuman, ko'cha, uy raqami):"
    )
    await callback_query.answer()


@dp.message(Checkout.waiting_for_address, F.text)
async def process_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    
    user_id = message.from_user.id
    basket = user_baskets.get(user_id, {})
    medicines = load_medicines()
    total = 0
    for med_id, quantity in basket.items():
        med = medicines.get(med_id, {})
        total += med.get('price', 0) * quantity
        
    await state.update_data(total=total)
    await state.set_state(Checkout.waiting_for_payment)

    buttons = [
        [InlineKeyboardButton(text=f"💳 To'lash ({total} so'm)", callback_data='pay_order')],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data='cancel_order')]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(f"Buyurtmangiz uchun jami to'lov: {total} so'm. Iltimos, to'lovni amalga oshiring.", reply_markup=keyboard)


@dp.callback_query(F.data == 'pay_order')
async def process_payment(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        current_state = await state.get_state()
        if current_state != Checkout.waiting_for_payment.state:
            await callback_query.answer("Iltimos, avval to'lov ma'lumotlarini kiriting.", show_alert=True)
            return
            
        user_data = await state.get_data()
        address = user_data.get('address')
        total = user_data.get('total')
        
        if not address or total is None:
            await callback_query.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.", show_alert=True)
            return

        user_id = callback_query.from_user.id
        basket = user_baskets.get(user_id, {})
        medicines = load_medicines()
        
        order_summary = "--- Buyurtma tasdiqlash ---\n\n"
        for med_id, quantity in basket.items():
            med = medicines.get(med_id, {})
            item_total = med.get('price', 0) * quantity
            order_summary += f"• {med.get('name', 'Noma\'lum dori')} x{quantity} = {item_total} so'm\n"
        
        order_summary += f"\n*Manzil:* {address}"
        order_summary += f"\n\n*Jami to'lov:* {total} so'm"

        buttons = [
            [InlineKeyboardButton(text="✅ Tasdiqlash va Yuborish", callback_data='confirm_order')],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data='cancel_order')]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await state.set_state(Checkout.waiting_for_confirmation)
        await callback_query.message.edit_text(order_summary, reply_markup=keyboard, parse_mode='Markdown')
        await callback_query.answer()
    except Exception as e:
        logging.error(f"Error in process_payment: {e}")
        await callback_query.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.", show_alert=True)


@dp.callback_query(F.data == 'confirm_order')
async def process_order_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        current_state = await state.get_state()
        if current_state != Checkout.waiting_for_confirmation.state:
            await callback_query.answer("Iltimos, avval buyurtmani tasdiqlang.", show_alert=True)
            return
            
        await state.set_state(Checkout.waiting_for_receipt)
        await callback_query.message.edit_text(
            "🔄 Iltimos, to'lov chekini yuboring. "
            "Chekni rasm yoki fayl shaklida yuborishingiz mumkin."
        )
        await callback_query.answer()
    except Exception as e:
        logging.error(f"Error in process_order_confirmation: {e}")
        await callback_query.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.", show_alert=True)

async def submit_order(user_id: int, user_info: types.User, address: str, receipt_file_id: str = None):
    """Helper function to submit order to admin"""
    admin_id = os.getenv('ADMIN_ID')
    if not admin_id:
        logging.error("ADMIN_ID not found in .env file")
        return False, "Kechirasiz, buyurtmani qayta ishlashda xatolik yuz berdi."

    if user_id not in user_baskets or not user_baskets[user_id]:
        return False, "Sizning savatingiz bo'sh."

    basket = user_baskets[user_id]
    total = 0
    order_details = "📝 *Yangi buyurtma!*\n\n"
    order_details += f"*Foydalanuvchi:* {user_info.full_name}\n"
    if user_info.username:
        order_details += f"*Telegram:* @{user_info.username}\n"
    order_details += f"*User ID:* `{user_id}`\n"
    if address:
        order_details += f"*Manzil:* {address}\n"
    order_details += "\n"

    medicines = load_medicines()
    for med_id, quantity in basket.items():
        med = medicines.get(med_id)
        if not med:
            order_details += f"• Noma'lum dori (ID: {med_id}) x{quantity} - topilmadi\n"
            continue
        item_total = med['price'] * quantity
        total += item_total
        order_details += f"• {med['name']} x{quantity} = {item_total} so'm\n"
        
    order_details += f"\n*Jami to'lov:* {total} so'm"

    try:
        # Send order details
        await bot.send_message(admin_id, order_details, parse_mode='Markdown')
        
        # Send receipt if available
        if receipt_file_id:
            receipt_caption = (
                f"💳 *To'lov cheki*\n"
                f"Foydalanuvchi: {user_info.full_name} (ID: {user_id})\n"
                f"Buyurtma sanasi: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            try:
                await bot.send_document(admin_id, receipt_file_id, caption=receipt_caption, parse_mode='Markdown')
            except Exception as e:
                logging.error(f"Failed to send receipt: {e}")
                await bot.send_message(admin_id, "❌ To'lov chekini yuklashda xatolik yuz berdi.")
        
        # Clear user's basket
        if user_id in user_baskets:
            del user_baskets[user_id]
            
        return True, "✅ Buyurtmangiz muvaffaqiyatli yuborildi! Tez orada siz bilan bog'lanamiz."
        
    except Exception as e:
        logging.error(f"Failed to send order to admin: {e}")
        return False, "❌ Buyurtmani yuborishda xatolik yuz berdi. Iltimos, administrator bilan bog'laning."

@dp.callback_query(F.data == 'send_order')
async def handle_send_order(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        user_data = await state.get_data()
        success, response = await submit_order(
            user_id=callback_query.from_user.id,
            user_info=callback_query.from_user,
            address=user_data.get('address')
        )
        
        if success:
            await state.clear()
            await callback_query.message.edit_text(response)
        else:
            await callback_query.answer(response, show_alert=True)
            
    except Exception as e:
        logging.error(f"Error in handle_send_order: {e}")
        await callback_query.answer(
            "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.",
            show_alert=True
        )

@dp.callback_query(F.data == 'main_menu')
async def process_callback_main_menu(callback_query: types.CallbackQuery):
    await callback_query.message.answer(
        "Bosh menyu:",
        reply_markup=get_main_menu()
    )
    await callback_query.answer()

# --- Main Function --- #

async def main():
    logging.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
