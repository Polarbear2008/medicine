import asyncio
import datetime
import json
import logging
import os
import random
import string
from typing import Dict, List, Optional
from typing import Dict, List, Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, 
    KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from supabase import create_client, Client
from database import db

# Atrof-muhit o'zgaruvchilarini yuklash
load_dotenv()

# Loglarni sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot va dispatcherni ishga tushirish
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()
storage = MemoryStorage()

# Bot konfiguratsiyasi
STORE_PHONE = """
+998 99 440 66 64
+998 90 023 06 85"""
STORE_ADDRESS = """🌍 Toshkent shahri, Yashnobod tumani

🗺️ Manzil:https://maps.app.goo.gl/6S5ABPrbg5NGXQwR9"

📍 Aniq manzil: [Manzil tafsilotlari]"""
PAYMENT_CARD = """💳 Karta raqami: 5614 6814 2214 5270
👤 Karta egasi: Karimov Ilyos Atxam ogli"""
# Load admin IDs from environment variable
ADMIN_IDS = [int(admin_id.strip()) for admin_id in os.getenv('ADMIN_ID', '').split(',') if admin_id.strip().isdigit()]
ORDER_CHANNEL = os.getenv('ORDER_CHANNEL', "@zakazlarshifo17")  # Buyurtmalar kanali

# Supabase ulanishi
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(supabase_url, supabase_key)

# Dori-darmonlar ma'lumotlari tuzilmasi
MEDICINES = {
    'bio_tribesteron': {
        'name': '💊 Bio Tribesteron',
        'benefits': 'Tabiiy testosteron va energiya ko\'chiruvchi',
        'contraindications': '18 yoshgacha yoki gormon-sezgir kasalliklarga ega bo\'lgan odamlarga tavsiya qilinmaydi',
        'price': '150,000 UZS'
    },
    'vitiligo_neo': {
        'name': '💊 Vitiligo Neo Aktiv',
        'benefits': 'Teri pigmentatsiya muammolariga yordam beradi',
        'contraindications': 'Homiladorlik yoki emiziklik davrida shifokor bilan maslahatlashing',
        'price': '120,000 UZS'
    },
    'siber_oil': {
        'name': '💊 Siber Firidan Oil',
        'benefits': 'Immunitet tizimini va umumiy sog\'likni qo\'llab-quvvatlaydi',
        'contraindications': 'Ma\'lum emas',
        'price': '85,000 UZS'
    },
    'tarpeda': {
        'name': '💊 TARPEDA (O\'simlik aralashmasi)',
        'benefits': 'Ovqat hazm qilish va tana tozalash uchun',
        'contraindications': 'Past qon bosimi bo\'lgan odamlarga tavsiya qilinmaydi',
        'price': '95,000 UZS'
    },
    'chuvalchan': {
        'name': '💊 Chuvalchan Kapsulalar',
        'benefits': 'Bo\'g\'imlar va suyak sog\'ligini qo\'llab-quvvatlaydi',
        'contraindications': 'Qonni suyultiruvchi dorilar qabul qilayotgan bo\'lsangiz shifokor bilan maslahatlashing',
        'price': '110,000 UZS'
    }
}

# Admin filtri
class IsAdmin(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in ADMIN_IDS

# Buyurtma jarayoni uchun holatlar
class OrderStates(StatesGroup):
    waiting_for_months = State()
    waiting_for_location = State()
    waiting_for_region = State()
    waiting_for_district = State()
    waiting_for_phone = State()
    waiting_for_receipt = State()

# Dori boshqaruvi uchun holatlar
class MedicineStates(StatesGroup):
    waiting_for_medicine_action = State()
    waiting_for_medicine_id = State()
    waiting_for_medicine_name = State()
    waiting_for_medicine_benefits = State()
    waiting_for_medicine_contraindications = State()
    waiting_for_medicine_price = State()
    waiting_for_medicine_photo = State()
    confirming_medicine_deletion = State()

# Dori qo'shish holatlari
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

# Foydalanuvchi buyurtmalari saqlash
ORDERS_FILE = 'orders.json'

async def load_orders() -> dict:
    """Load orders from Supabase database"""
    return await db.get_all_orders()

async def save_orders(orders: dict) -> None:
    """Save orders to Supabase database (legacy function for compatibility)"""
    # This function is kept for compatibility but orders are now saved individually
    pass

async def save_medicines(medicines: Dict[str, Dict]) -> None:
    """Save medicines to Supabase database (legacy function for compatibility)"""
    # This function is kept for compatibility but medicines are now saved individually
    pass

async def load_medicines() -> Dict[str, Dict]:
    """Load medicines from Supabase database"""
    return await db.get_all_medicines()

# Initialize empty containers - will be loaded in main()
orders = {}
# MEDICINES will be loaded from database in main()

# Foydalanuvchi savatlari saqlash
user_baskets = {}

# --- Klaviaturalar --- #

def get_main_menu() -> ReplyKeyboardMarkup:
    """Asosiy menyu klaviaturasini yaratish"""
    buttons = [
        [KeyboardButton(text='📍 Manzil'), KeyboardButton(text='☎️ Telefon raqami')],
        [KeyboardButton(text='🌿 O\'simlik dorilar haqida'), KeyboardButton(text='🛒 Buyurtma berish')]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_main_menu_inline() -> InlineKeyboardMarkup:
    """Inline asosiy menyu klaviaturasini yaratish"""
    buttons = [
        [InlineKeyboardButton(text='📍 Manzil', callback_data='show_address')],
        [InlineKeyboardButton(text='☎️ Telefon raqami', callback_data='show_phone')],
        [InlineKeyboardButton(text='🌿 O\'simlik dorilar', callback_data='show_medicines')],
        [InlineKeyboardButton(text='🛒 Buyurtma berish', callback_data='place_order')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_medicines_menu() -> InlineKeyboardMarkup:
    """Dorilar menyusi klaviaturasini yaratish"""
    buttons = []
    for med_id, med in MEDICINES.items():
        buttons.append([InlineKeyboardButton(
            text=med['name'],
            callback_data=f'med_{med_id}'
        )])
    buttons.append([InlineKeyboardButton(text='🔙 Asosiy menyuga qaytish', callback_data='main_menu')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_months_keyboard() -> InlineKeyboardMarkup:
    """Oy tanlash klaviaturasini yaratish"""
    buttons = [
        [InlineKeyboardButton(text='1 oy', callback_data='months_1')],
        [InlineKeyboardButton(text='2 oy', callback_data='months_2')],
        [InlineKeyboardButton(text='3 oy', callback_data='months_3')],
        [InlineKeyboardButton(text='Boshqa', callback_data='months_other')],
        [InlineKeyboardButton(text='🔙 Bekor qilish', callback_data='cancel_order')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_location_keyboard() -> ReplyKeyboardMarkup:
    """Joylashuv ulashish klaviaturasi"""
    buttons = [
        [KeyboardButton(text='📍 Joylashuv ulashish', request_location=True)],
        [KeyboardButton(text='🔙 Bekor qilish')]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Buyurtma tasdiqlash klaviaturasi"""
    buttons = [
        [
            InlineKeyboardButton(text='✅ Tasdiqlash', callback_data='confirm_order'),
            InlineKeyboardButton(text='❌ Bekor qilish', callback_data='cancel_order')
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_keyboard():
    """Admin klaviaturasini yaratish"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Buyurtmalarni ko'rish", callback_data="admin_orders")],
        [InlineKeyboardButton(text="📦 Mahsulotlarni ko'rish", callback_data="admin_products")],
        [
            InlineKeyboardButton(text="➕ Dori qo'shish", callback_data="add_medicine"),
            InlineKeyboardButton(text="✏️ Dorini tahrirlash", callback_data="edit_medicine")
        ],
        [
            InlineKeyboardButton(text="🗑️ Dorini o'chirish", callback_data="delete_medicine"),
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")
        ]
    ])

# Do'kon menyusi klaviaturasi
def get_store_menu():
    buttons = []
    for med_id, med in MEDICINES.items():
        buttons.append([InlineKeyboardButton(text=med['name'], callback_data=f'med_{med_id}')])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

# Dori tafsilotlari klaviaturasi
def get_medicine_detail_keyboard(med_id):
    buttons = [
        [InlineKeyboardButton(text='➕ Savatga qo\'shish', callback_data=f'add_{med_id}'),
         InlineKeyboardButton(text='🛒 Hoziroq sotib olish', callback_data=f'buy_{med_id}')],
        [InlineKeyboardButton(text='🔙 Do\'konga qaytish', callback_data='back_to_store')]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

# Savat klaviaturasi
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
        [InlineKeyboardButton(text='⬅️ Orqaga', callback_data='back_to_basket')]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

# --- Buyruq ishlovchilari --- #

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """start buyrug'ini qayta ishlash"""
    welcome_text = (
        "🏥 Shifo_17 botiga xush kelibsiz!\n\n"
        "Quyidagi menyudan kerakli bo'limni tanlang:"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu())

@dp.message(F.text == '📍 Manzil')
async def show_address(message: Message):
    """Do'kon manzilini ko'rsatish"""
    await message.answer(f"📍 Bizning manzilimiz:\n{STORE_ADDRESS}")

@dp.message(F.text == '☎️ Telefon raqami')
async def show_phone(message: Message):
    """Do'kon telefon raqamini ko'rsatish"""
    await message.answer(f"☎️ Bizning telefon raqamimiz:\n{STORE_PHONE}")

@dp.message(F.text == '🌿 O\'simlik dorilar haqida')
async def show_medicines(message: Message):
    """Mavjud dorilar ro'yxatini ko'rsatish"""
    await message.answer(
        "🌿 Mavjud o'simlik dorilar:",
        reply_markup=get_medicines_menu()
    )

@dp.callback_query(F.data.startswith('med_'))
async def show_medicine_detail(callback: CallbackQuery):
    """Muayyan dori tafsilotlarini ko'rsatish"""
    global MEDICINES
    med_id = callback.data[4:]  # 'med_' prefixini olib tashlash
    
    logging.info(f"Looking for medicine ID: '{med_id}'")
    logging.info(f"Current MEDICINES keys: {list(MEDICINES.keys())}")
    
    # Reload medicines from database if not found
    if med_id not in MEDICINES:
        logging.warning(f"Medicine {med_id} not found in cache, reloading from database")
        try:
            MEDICINES = await load_medicines()
            logging.info(f"Reloaded {len(MEDICINES)} medicines from database")
            logging.info(f"New MEDICINES keys after reload: {list(MEDICINES.keys())}")
        except Exception as e:
            logging.error(f"Failed to reload medicines: {e}")
    
    if med_id not in MEDICINES:
        logging.error(f"Medicine '{med_id}' still not found after reload.")
        logging.error(f"Available medicines: {list(MEDICINES.keys())}")
        # Try to find similar IDs
        similar = [k for k in MEDICINES.keys() if med_id.lower() in k.lower() or k.lower() in med_id.lower()]
        if similar:
            logging.error(f"Similar medicine IDs found: {similar}")
        await callback.answer("Dori topilmadi. Iltimos, qaytadan urinib ko'ring.")
        return
    
    med = MEDICINES[med_id]
    benefits = med.get('benefits') or med.get('description', "Ma'lumot mavjud emas")
    contraindications = med.get('contraindications', "Ma'lumot mavjud emas")
    price = med.get('price', "Narx ko'rsatilmagan")
    
    text = (
        f"{med['name']}\n\n"
        f"💊 <b>Foydali xususiyatlari:</b>\n{benefits}\n\n"
        f"⚠️ <b>Qarshi ko'rsatmalar:</b>\n{contraindications}\n\n"
        f"💰 <b>Narxi:</b> {price}"
    )
    
    # Buyurtma tugmasini qo'shish
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🛒 Hozir buyurtma berish', callback_data=f'order_{med_id}')],
        [InlineKeyboardButton(text='🔙 Ro\'yxatga qaytish', callback_data='back_to_medicines')]
    ])
    
    # Check if medicine has a photo
    photo_id = med.get('photo')
    if photo_id:
        # Send photo with caption
        try:
            await callback.message.delete()  # Delete the previous message
            await bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=photo_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            # If photo fails, send text message
            logging.error(f"Error sending photo: {e}")
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        # Send text message if no photo
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')

@dp.callback_query(F.data == 'back_to_medicines')
async def back_to_medicines(callback: CallbackQuery):
    """Dorilar ro'yxatiga qaytish"""
    try:
        # Try to edit text first (for text messages)
        await callback.message.edit_text(
            "🌿 Mavjud o'simlik dorilar:",
            reply_markup=get_medicines_menu()
        )
    except Exception:
        # If editing fails (photo message), delete and send new message
        try:
            await callback.message.delete()
            await bot.send_message(
                chat_id=callback.message.chat.id,
                text="🌿 Mavjud o'simlik dorilar:",
                reply_markup=get_medicines_menu()
            )
        except Exception as e:
            logging.error(f"Error in back_to_medicines: {e}")
            # Fallback: just send a new message
            await bot.send_message(
                chat_id=callback.message.chat.id,
                text="🌿 Mavjud o'simlik dorilar:",
                reply_markup=get_medicines_menu()
            )
    
    await callback.answer()

@dp.callback_query(F.data.startswith('order_'))
async def start_order(callback: CallbackQuery, state: FSMContext):
    """Buyurtma jarayonini boshlash"""
    global MEDICINES
    med_id = callback.data[6:]  # 'order_' prefixini olib tashlash
    
    # Reload medicines from database if not found
    if med_id not in MEDICINES:
        logging.warning(f"Medicine {med_id} not found in cache, reloading from database")
        try:
            MEDICINES = await load_medicines()
            logging.info(f"Reloaded {len(MEDICINES)} medicines from database")
        except Exception as e:
            logging.error(f"Failed to reload medicines: {e}")
    
    if med_id not in MEDICINES:
        logging.error(f"Medicine {med_id} still not found after reload. Available: {list(MEDICINES.keys())}")
        await callback.answer("Dori topilmadi. Iltimos, qaytadan urinib ko'ring.")
        return
    
    # Tanlangan dorini holatga saqlash
    await state.update_data(selected_medicine=med_id)
    
    # Davolash muddatini so'rash
    await callback.message.answer(
        "❓ Necha oylik davolanishni xohlaysiz?",
        reply_markup=get_months_keyboard()
    )
    await state.set_state(OrderStates.waiting_for_months)
    await callback.answer()

@dp.callback_query(F.data.startswith('months_'), OrderStates.waiting_for_months)
async def process_months_selection(callback: CallbackQuery, state: FSMContext):
    """Oy tanlovini qayta ishlash"""
    months_data = callback.data.split('_')
    if len(months_data) == 2 and months_data[1].isdigit():
        months = int(months_data[1])
    else:
        months = months_data[1]
    
    await state.update_data(months=months)
    
    # To'lov ma'lumotlarini ko'rsatish
    med_data = await state.get_data()
    med_id = med_data.get('selected_medicine')
    med = MEDICINES.get(med_id, {})
    
    # Umumiy narxni hisoblash (soddalashtirilgan)
    price_str = med.get('price', '0').replace(',', '').split()[0]
    try:
        price = int(price_str) * months
        total_price = f"{price:,} UZS"
    except ValueError:
        total_price = f"{months} x {med.get('price', 'N/A')}"
    
    payment_text = (
        f"💳 <b>To'lov ma'lumotlari</b>\n\n"
        f"🔹 Dori: {med.get('name', 'N/A')}\n"
        f"🔹 Muddat: {months} oy\n"
        f"🔹 Umumiy summa: {total_price}\n\n"
        f"Iltimos, summani bizning kartaga o'tkazing:\n"
        f"<code>{PAYMENT_CARD}</code>\n\n"
        "❗️ To'lovdan keyin, iltimos to'lov chekining suratini yuklang."
    )
    
    await callback.message.answer(
        payment_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='📤 Chek yuklash', callback_data='upload_receipt')],
            [InlineKeyboardButton(text='🔙 Bekor qilish', callback_data='cancel_order')]
        ]),
        parse_mode='HTML'
    )
    
    await state.set_state(OrderStates.waiting_for_receipt)
    await callback.answer()

@dp.message(OrderStates.waiting_for_months, F.text)
async def process_custom_months(message: Message, state: FSMContext):
    """Maxsus oy kiritishini qayta ishlash"""
    try:
        months = int(message.text.strip())
        if months < 1:
            raise ValueError("Oylar kamida 1 bo'lishi kerak")
        
        # Maxsus oy bilan holatni yangilash
        await state.update_data(months=months)
        
        # To'lov ma'lumotlarini ko'rsatish
        med_data = await state.get_data()
        med_id = med_data.get('selected_medicine')
        med = MEDICINES.get(med_id, {})
        
        # Umumiy narxni hisoblash (soddalashtirilgan)
        price_str = med.get('price', '0').replace(',', '').split()[0]
        try:
            price = int(price_str) * months
            total_price = f"{price:,} UZS"
        except ValueError:
            total_price = f"{months} x {med.get('price', 'N/A')}"
        
        payment_text = (
            f"💳 <b>To'lov ma'lumotlari</b>\n\n"
            f"🔹 Dori: {med.get('name', 'N/A')}\n"
            f"🔹 Muddat: {months} oy\n"
            f"🔹 Umumiy summa: {total_price}\n\n"
            f"Iltimos, summani bizning kartaga o'tkazing:\n"
            f"<code>{PAYMENT_CARD}</code>\n\n"
            "❗️ To'lovdan keyin, iltimos to'lov chekining suratini yuklang."
        )
        
        await message.answer(
            payment_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='📤 Chek yuklash', callback_data='upload_receipt')],
                [InlineKeyboardButton(text='🔙 Bekor qilish', callback_data='cancel_order')]
            ]),
            parse_mode='HTML'
        )
        
        await state.set_state(OrderStates.waiting_for_receipt)
        
    except ValueError as e:
        await message.answer("❌ Iltimos, to'g'ri oy sonini kiriting (1 yoki undan ko'p).")
        return

@dp.callback_query(F.data == 'upload_receipt', OrderStates.waiting_for_receipt)
async def request_receipt_upload(callback: CallbackQuery):
    """Chek yuklashni so'rash"""
    await callback.message.answer("📤 Iltimos, to'lov chekingizning suratini yuklang.")
    await callback.answer()

@dp.message(OrderStates.waiting_for_receipt, F.photo)
async def process_receipt_photo(message: Message, state: FSMContext):
    """Chek suratini qayta ishlash"""
    # Surat fayl ID sini holatga saqlash
    photo = message.photo[-1]  # Eng yuqori aniqlikdagi suratni olish
    await state.update_data(receipt_photo_id=photo.file_id)
    
    # Yetkazib berish joylashuvini so'rash
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text='📍 Toshkent shahri', callback_data='location_tashkent'),
            InlineKeyboardButton(text='📍 Boshqa viloyat', callback_data='location_other')
        ],
        [InlineKeyboardButton(text='🔙 Bekor qilish', callback_data='cancel_order')]
    ])
    
    await message.answer(
        "📍 Buyurtmangizni qayerga yetkazib beramiz?\n\n"
        "📝 <b>Eslatma:</b> Toshkent shahridagi buyurtmalarni o'zimiz yetkazib beramiz. "
        "Viloyatlarga esa BTS pochta xizmati orqali yuboramiz. Xaridingiz uchun rahmat!",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await state.set_state(OrderStates.waiting_for_location)

@dp.callback_query(F.data == 'location_tashkent', OrderStates.waiting_for_location)
async def request_tashkent_location(callback: CallbackQuery, state: FSMContext):
    """Toshkent yetkazib berish uchun joylashuvni so'rash"""
    await callback.message.answer(
        "📍 Iltimos, Toshkent shahridagi yetkazib berish uchun joylashuvingizni ulashing:",
        reply_markup=get_location_keyboard()
    )
    await state.update_data(delivery_region="Toshkent")
    await state.set_state(OrderStates.waiting_for_phone)
    await callback.answer()

@dp.callback_query(F.data == 'location_other', OrderStates.waiting_for_location)
async def request_other_region(callback: CallbackQuery, state: FSMContext):
    """Toshkent bo'lmagan yetkazib berish uchun viloyatni so'rash"""
    await callback.message.answer("🌍 Iltimos, viloyatingizni kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(OrderStates.waiting_for_region)
    await callback.answer()

@dp.message(OrderStates.waiting_for_region)
async def process_region(message: Message, state: FSMContext):
    """Viloyatni qayta ishlash va tuman so'rash"""
    await state.update_data(delivery_region=message.text)
    await message.answer("🏘️ Iltimos, tumaningizni kiriting:")
    await state.set_state(OrderStates.waiting_for_district)

@dp.message(OrderStates.waiting_for_district)
async def process_district(message: Message, state: FSMContext):
    """Tumanni qayta ishlash va telefon raqamini so'rash"""
    await state.update_data(delivery_district=message.text)
    await message.answer("📱 Iltimos, telefon raqamingizni ulashing:")
    await state.set_state(OrderStates.waiting_for_phone)

@dp.message(OrderStates.waiting_for_phone, F.text)
async def process_phone(message: Message, state: FSMContext):
    """Telefon raqamini qayta ishlash va buyurtma xulosasini ko'rsatish"""
    await state.update_data(phone_number=message.text)
    await show_order_summary(message, state)

@dp.message(OrderStates.waiting_for_phone, F.location)
async def process_location(message: Message, state: FSMContext):
    """Toshkent yetkazib berish uchun joylashuvni qayta ishlash"""
    location = message.location
    await state.update_data(
        delivery_lat=location.latitude,
        delivery_lon=location.longitude
    )
    await message.answer("📍 Joylashuv qabul qilindi! Endi telefon raqamingizni ulashing:")

async def show_order_summary(message: Message, state: FSMContext):
    """Tasdiqlash uchun buyurtma xulosasini ko'rsatish"""
    data = await state.get_data()
    med_id = data.get('selected_medicine')
    med = MEDICINES.get(med_id, {})
    months = data.get('months', 1)
    
    # Yetkazib berish ma'lumotlarini olish
    if 'delivery_region' in data and data['delivery_region'] == 'Toshkent':
        delivery_info = f"📍 <b>Yetkazib berish:</b> Toshkent shahri (ulashilgan joylashuv)"
    elif 'delivery_region' in data and 'delivery_district' in data:
        delivery_info = f"📍 <b>Yetkazib berish:</b> {data['delivery_region']}, {data['delivery_district']}"
    else:
        delivery_info = "📍 <b>Yetkazib berish:</b> Belgilanmagan"
    
    # Umumiy narxni hisoblash (soddalashtirilgan)
    price_str = med.get('price', '0').replace(',', '').split()[0]
    try:
        price = int(price_str) * months
        total_price = f"{price:,} UZS"
    except ValueError:
        total_price = f"{months} x {med.get('price', 'N/A')}"
    
    summary_text = (
        "📋 <b>Buyurtma xulosasi</b>\n\n"
        f"💊 <b>Dori:</b> {med.get('name', 'N/A')}\n"
        f"⏳ <b>Muddat:</b> {months} oy\n"
        f"💰 <b>Umumiy summa:</b> {total_price}\n\n"
        f"{delivery_info}\n"
        f"📱 <b>Telefon:</b> {data.get('phone_number', 'Berilmagan')}\n\n"
        "Iltimos, buyurtmangizni tasdiqlang:"
    )
    
    await message.answer(
        summary_text,
        reply_markup=get_confirmation_keyboard(),
        parse_mode='HTML'
    )

# Removed order keyboard function - no buttons needed

async def send_order_to_channel(order_data: dict, bot: Bot):
    """Buyurtma tafsilotlarini sozlangan kanalga yuborish"""
    try:
        logging.info(f"Attempting to send order {order_data['order_id']} to channel {ORDER_CHANNEL}")
        
        # Buyurtma tafsilotlarini formatlash
        delivery_info = order_data.get('delivery_info', {})
        region = delivery_info.get('region', 'N/A')
        district = delivery_info.get('district', 'N/A')
        phone = delivery_info.get('phone', 'N/A')
        
        # Build address string
        if region == 'Toshkent':
            address = "Toshkent shahri (GPS joylashuv ulashilgan)"
        elif region != 'N/A' and district != 'N/A':
            address = f"{region}, {district}"
        else:
            address = "Manzil kiritilmagan"
        
        order_text = (
            "🆕 <b>YANGI BUYURTMA QABUL QILINDI</b>\n\n"
            f"🆔 <b>Buyurtma ID:</b> <code>{order_data['order_id']}</code>\n"
            f"👤 <b>Mijoz:</b> {order_data.get('full_name', 'N/A')} (@{order_data.get('username', 'N/A')})\n"
            f"📞 <b>Telefon:</b> {phone}\n\n"
            f"💊 <b>Dori:</b> {order_data.get('medicine', 'N/A')}\n"
            f"⏳ <b>Muddat:</b> {order_data.get('months', 1)} oy\n"
            f"💰 <b>Summa:</b> {order_data.get('price', 'N/A')}\n\n"
            f"📍 <b>Yetkazib berish:</b> {address}\n\n"
            f"📅 <b>Sana:</b> {order_data.get('timestamp', 'Nomalum')}"
        )
        
        # Kanalga yuborish
        try:
            # Check if GPS location exists for Tashkent orders
            if region == 'Toshkent' and delivery_info.get('lat') and delivery_info.get('lon'):
                # Send location first
                await bot.send_location(
                    chat_id=ORDER_CHANNEL,
                    latitude=delivery_info['lat'],
                    longitude=delivery_info['lon']
                )
                logging.info("GPS location sent to channel")
            
            # Then send order details
            if order_data.get('receipt_photo_id'):
                logging.info("Sending order with photo to channel")
                message = await bot.send_photo(
                    chat_id=ORDER_CHANNEL,
                    photo=order_data['receipt_photo_id'],
                    caption=order_text,
                    parse_mode='HTML'
                )
                logging.info(f"Order sent successfully with photo. Message ID: {message.message_id}")
            else:
                logging.info("Sending order without photo to channel")
                message = await bot.send_message(
                    chat_id=ORDER_CHANNEL,
                    text=order_text,
                    parse_mode='HTML'
                )
                logging.info(f"Order sent successfully without photo. Message ID: {message.message_id}")
                
        except Exception as e:
            logging.error(f"Kanalga xabar yuborishda xatolik: {e}")
            # Try to send error message to admin
            try:
                await bot.send_message(
                    chat_id=ADMIN_IDS[0],
                    text=f"❌ Kanalga xabar yuborishda xatolik: {e}\n\nKanal: {ORDER_CHANNEL}\nBuyurtma ID: {order_data['order_id']}"
                )
            except Exception as admin_error:
                logging.error(f"Admin ga xabar yuborishda ham xatolik: {admin_error}")
        
    except Exception as e:
        logging.error(f"Buyurtma kanalga yuborishda umumiy xatolik: {e}")
        # Send error to admin
        try:
            await bot.send_message(
                chat_id=ADMIN_IDS[0],
                text=f"❌ Buyurtma yuborishda umumiy xatolik: {e}"
            )
        except:
            pass

async def update_order_status(order_id: str, status: str, message: Message):
    """Update order status in database"""
    try:
        # Update in database
        success = await db.update_order_status(order_id, status)
        
        if success:
            # Update local orders dict
            if order_id in orders:
                orders[order_id]['status'] = status
                logging.info(f"Updated order {order_id} status to {status}")
            
            # Remove buttons from channel message
            try:
                await message.edit_reply_markup(reply_markup=None)
                status_text = "✅ Yetkazib berildi" if status == "shipped" else "❌ Bekor qilindi"
                await message.edit_text(message.text + f"\n\n{status_text}")
            except Exception as e:
                logging.error(f"Failed to update channel message: {e}")
                
        else:
            logging.error(f"Failed to update order {order_id} in database")
            
    except Exception as e:
        logging.error(f"Error updating order status: {e}")

# Removed order action handlers - no buttons needed

async def show_medicines_for_order(message: Message):
    """Show list of medicines for ordering"""
    if not MEDICINES:
        await message.answer("❌ Hozirda mavjud dori-darmonlar ro'yxati topilmadi.")
        return
    
    # Create a list of medicine buttons
    buttons = []
    for med_id, med in MEDICINES.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"{med.get('name')} - {med.get('price', 'Narx belgilanmagan')}",
                callback_data=f"order_{med_id}"
            )
        ])
    
    # Add back button
    buttons.append([
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data="back_to_main"
        )
    ])
    
    await message.answer(
        "🛒 <b>Buyurtma berish:</b>\n\nQaysi dorini buyurtma qilmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode='HTML'
    )

# Admin command handler
async def cmd_admin(message: Message):
    """Handle /admin command - Show admin panel"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Sizda admin huquqlari yo'q!")
        return
    
    await message.answer(
        "👨‍💼 Admin panelga xush kelibsiz! Quyidagi menyudan kerakli bo'limni tanlang:",
        reply_markup=get_admin_keyboard()
    )

# Test command for admins
@dp.message(Command("test_channel"))
async def test_channel_command(message: Message):
    """Test channel forwarding - Admin only"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Sizda admin huquqlari yo'q!")
        return
    
    # Create test order data
    test_order = {
        'order_id': 'TEST123',
        'user_id': message.from_user.id,
        'username': message.from_user.username,
        'full_name': message.from_user.full_name,
        'medicine': 'Test Medicine',
        'months': 1,
        'price': '100,000 UZS',
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'delivery_info': {
            'region': 'Toshkent',
            'phone': '+998901234567'
        },
        'receipt_photo_id': None
    }
    
    await message.answer("🧪 Test buyurtma kanalga yuborilmoqda...")
    await send_order_to_channel(test_order, bot)

# Command handlers
dp.message.register(cmd_start, CommandStart())
dp.message.register(cmd_admin, Command("admin"))
dp.message.register(test_channel_command, Command("test_channel"))
dp.message.register(show_address, F.text == "📍 Manzil")
dp.message.register(show_phone, F.text == "📞 Bog'lanish")
dp.message.register(show_medicines, F.text == "💊 Dorilar")
dp.message.register(show_medicines_for_order, F.text == "🛒 Buyurtma berish")

# Add medicine handlers
@dp.message(MedicineStates.waiting_for_medicine_name)
async def process_medicine_name(message: Message, state: FSMContext):
    """Process medicine name and ask for benefits"""
    await state.update_data(name=message.text)
    await message.answer("✅ Dori nomi saqlandi.\n\nDorining foydali xususiyatlari haqida ma'lumot bering:")
    await state.set_state(MedicineStates.waiting_for_medicine_benefits)

@dp.message(MedicineStates.waiting_for_medicine_benefits)
async def process_medicine_benefits(message: Message, state: FSMContext):
    """Process medicine benefits and ask for contraindications"""
    await state.update_data(benefits=message.text)
    await message.answer("✅ Foydali xususiyatlar saqlandi.\n\nQo'llanilish cheklovlari (agar mavjud bo'lsa):")
    await state.set_state(MedicineStates.waiting_for_medicine_contraindications)

@dp.message(MedicineStates.waiting_for_medicine_contraindications)
async def process_medicine_contraindications(message: Message, state: FSMContext):
    """Process medicine contraindications and ask for price"""
    await state.update_data(contraindications=message.text)
    await message.answer("✅ Qo'llanilish cheklovlari saqlandi.\n\nDori narxini kiriting (masalan, 15000 so'm):")
    await state.set_state(MedicineStates.waiting_for_medicine_price)

@dp.message(MedicineStates.waiting_for_medicine_price)
async def process_medicine_price(message: Message, state: FSMContext):
    """Process medicine price and ask for photo"""
    if not message.text.replace(' ', '').replace('so\'m', '').replace('sum', '').isdigit():
        await message.answer("❌ Iltimos, faqat raqamlarda kiriting (masalan, 15000 yoki 15000 so'm)")
        return
    
    price = ''.join(c for c in message.text if c.isdigit())
    await state.update_data(price=f"{price} so'm")
    await message.answer("✅ Narx saqlandi.\n\nDori rasmini yuboring (ixtiyoriy):")
    await state.set_state(MedicineStates.waiting_for_medicine_photo)

@dp.message(MedicineStates.waiting_for_medicine_photo, F.photo | F.text)
async def process_medicine_photo(message: Message, state: FSMContext):
    """Process medicine photo and save the medicine"""
    data = await state.get_data()
    
    # Handle photo if provided
    photo_id = None
    if message.photo:
        # Validate photo size (Telegram photos are usually fine, but let's add basic validation)
        photo = message.photo[-1]  # Get highest resolution
        photo_id = photo.file_id
        
        # Optional: Get file info for validation
        try:
            file_info = await bot.get_file(photo_id)
            file_size = file_info.file_size
            
            # Check if file size is reasonable (max 20MB for Telegram)
            if file_size and file_size > 20 * 1024 * 1024:
                await message.answer("❌ Rasm hajmi juda katta. Iltimos, kichikroq rasm yuklang.")
                return
                
        except Exception as e:
            logging.warning(f"Could not get file info: {e}")
            # Continue anyway, as this is not critical
    elif message.text and message.text.lower() in ['yo\'q', 'yoq', 'skip', 'o\'tkazib yuborish']:
        # Allow skipping photo upload
        photo_id = None
    else:
        await message.answer("📷 Iltimos, dori rasmini yuboring yoki 'yo'q' deb yozing:")
        return
    
    # Generate a unique ID for the medicine
    import uuid
    med_id = str(uuid.uuid4())[:8]
    
    # Prepare medicine data
    medicine_data = {
        'id': med_id,
        'name': data.get('name', ''),
        'benefits': data.get('benefits', ''),
        'contraindications': data.get('contraindications', ''),
        'price': data.get('price', 'Narx kiritilmagan'),
        'photo': photo_id if photo_id else None,
        'description': data.get('benefits', '')  # Using benefits as description for now
    }
    
    try:
        # Save to database
        success = await db.add_medicine(med_id, medicine_data)
        
        if success:
            # Update in-memory cache
            MEDICINES[med_id] = medicine_data
            
            # Send confirmation message with medicine details
            photo_status = "📷 Rasm bilan" if photo_id else "📝 Rasmsiz"
            response = (
                f"✅ Dori muvaffaqiyatli qo'shildi! {photo_status}\n\n"
                f"🏷️ Nomi: {medicine_data['name']}\n"
                f"💊 Foydali xususiyatlari: {medicine_data['benefits'][:50]}...\n"
                f"⚠️ Qo'llanilish cheklovlari: {medicine_data['contraindications'][:50]}...\n"
                f"💰 Narxi: {medicine_data['price']}"
            )
            
            # Send photo if available
            if photo_id:
                await message.answer_photo(
                    photo_id,
                    caption=response,
                    reply_markup=get_admin_keyboard()
                )
            else:
                await message.answer(
                    response,
                    reply_markup=get_admin_keyboard()
                )
        else:
            await message.answer(
                "❌ Xatolik yuz berdi. Dori qo'shishda xatolik yuz berdi.",
                reply_markup=get_admin_keyboard()
            )
    except Exception as e:
        logging.error(f"Error adding medicine: {e}")
        await message.answer(
            "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.",
            reply_markup=get_admin_keyboard()
        )
    
    # Reset state
    await state.clear()

@dp.callback_query(F.data == 'back_to_main')
async def back_to_main_menu(callback: CallbackQuery):
    """Handle back to main menu button"""
    await cmd_start(callback.message)
    await callback.answer()

@dp.callback_query(F.data == 'confirm_order')
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    """Handle order confirmation"""
    data = await state.get_data()
    med_id = data.get('selected_medicine')
    med = MEDICINES.get(med_id, {})
    
    # Generate order ID
    order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    # Prepare order data
    order_data = {
        'order_id': order_id,
        'user_id': callback.from_user.id,
        'username': callback.from_user.username,
        'full_name': callback.from_user.full_name,
        'medicine': med.get('name', 'N/A'),
        'months': data.get('months', 1),
        'price': med.get('price', 'N/A'),
        'status': 'new',
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'delivery_info': {
            'region': data.get('delivery_region', 'N/A'),
            'district': data.get('delivery_district', 'N/A'),
            'phone': data.get('phone_number', 'N/A'),
            'address': data.get('delivery_address', 'N/A'),
            'lat': data.get('delivery_lat'),
            'lon': data.get('delivery_lon')
        },
        'receipt_photo_id': data.get('receipt_photo_id')
    }
    
    # Save order to database
    await db.add_order(order_data)
    
    # Send confirmation to user
    await callback.message.edit_text(
        "✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"🆔 Buyurtma raqami: <code>{order_id}</code>\n"
        f"📅 Sana: {order_data['timestamp']}\n"
        "\nTez orada siz bilan bog'lanamiz!",
        parse_mode='HTML'
    )
    
    # Send main menu
    await callback.message.answer(
        "Asosiy menyuga qaytdingiz:",
        reply_markup=get_main_menu()
    )
    
    # Send order to channel
    await send_order_to_channel(order_data, bot)
    
    # Clear state
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data == 'cancel_order')
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    """Handle order cancellation"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Buyurtma bekor qilindi.\n\n"
        "Agar sizda savollar bo'lsa, biz bilan bog'lanishingiz mumkin.",
        parse_mode='HTML'
    )
    
    # Send main menu
    await callback.message.answer(
        "Asosiy menyuga qaytdingiz:",
        reply_markup=get_main_menu()
    )
    await callback.answer()

# Admin callback handlers
@dp.callback_query(F.data == 'admin_orders')
async def admin_orders(callback: CallbackQuery):
    """Show admin orders"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Sizda admin huquqlari yo'q!")
        return
    
    try:
        # Get all orders from the database
        orders = await db.get_all_orders()
        if not orders:
            await callback.message.answer("📭 Hozircha buyurtmalar mavjud emas!")
            return
            
        # Show orders with proper data structure
        response = "📋 So'ngi buyurtmalar:\n\n"
        order_count = 0
        for order_id, order in orders.items():
            if order_count >= 5:  # Limit to 5 orders
                break
            
            customer_name = order.get('full_name', "Noma'lum")
            phone = order.get('delivery_info', {}).get('phone', "Noma'lum")
            date = order.get('timestamp', "Noma'lum")
            status = order.get('status', 'new')
            medicine = order.get('medicine', 'Noma\'lum')
            
            response += (
                f"🆔 Buyurtma: {order_id}\n"
                f"👤 Mijoz: {customer_name}\n"
                f"💊 Dori: {medicine}\n"
                f"📞 Tel: {phone}\n"
                f"📅 Sana: {date}\n"
                f"📦 Holati: {status}\n\n"
            )
            order_count += 1
        
        await callback.message.answer(response)
        await callback.answer()
    except Exception as e:
        logging.error(f"Xatolik yuz berdi: {e}")
        await callback.message.answer("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        await callback.answer()

@dp.callback_query(F.data == 'admin_products')
async def admin_products(callback: CallbackQuery):
    """Show admin products"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Sizda admin huquqlari yo'q!")
        return
    
    try:
        # Get all medicines from the database
        medicines = await db.get_all_medicines()
        if not medicines:
            await callback.message.answer("ℹ️ Hozircha dorilar mavjud emas!")
            return
            
        # Show all medicines with photo status
        response = "💊 Mavjud dorilar ro'yxati:\n\n"
        for med_id, med in medicines.items():
            photo_icon = "📷" if med.get('photo') else "📝"
            response += f"{photo_icon} {med['name']} - {med.get('price', 'Narx kiritilmagan')}\n"
            response += f"   ID: <code>{med_id}</code>\n\n"
        
        await callback.message.answer(response, parse_mode='HTML')
        await callback.answer()
    except Exception as e:
        logging.error(f"Xatolik yuz berdi: {e}")
        await callback.message.answer("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        await callback.answer()

@dp.callback_query(F.data == 'add_medicine')
async def add_medicine_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a new medicine"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Sizda admin huquqlari yo'q!")
        return
    
    await callback.message.answer("💊 Yangi dori qo'shish uchun quyidagi ma'lumotlarni kiriting:\n\nDori nomi:")
    await state.set_state(MedicineStates.waiting_for_medicine_name)
    await callback.answer()

@dp.callback_query(F.data == 'edit_medicine')
async def edit_medicine_start(callback: CallbackQuery, state: FSMContext):
    """Start editing a medicine"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Sizda admin huquqlari yo'q!")
        return
    
    # Show available medicines with IDs
    medicines = await db.get_all_medicines()
    if not medicines:
        await callback.message.answer("❌ Hozircha dorilar mavjud emas!")
        return
    
    response = "✏️ Tahrirlash uchun dori ID sini yuboring:\n\n"
    for med_id, med in medicines.items():
        response += f"ID: <code>{med_id}</code> - {med['name']}\n"
    
    await callback.message.answer(response, parse_mode='HTML')
    await state.set_state(MedicineStates.waiting_for_medicine_id)
    await callback.answer()

@dp.message(MedicineStates.waiting_for_medicine_id)
async def process_medicine_id_for_edit(message: Message, state: FSMContext):
    """Process medicine ID for editing"""
    med_id = message.text.strip()
    
    if med_id not in MEDICINES:
        await message.answer("❌ Bunday ID li dori topilmadi. Iltimos, to'g'ri ID kiriting.")
        return
    
    # Store the medicine ID for editing
    await state.update_data(editing_medicine_id=med_id)
    
    # Show current medicine details and editing options
    med = MEDICINES[med_id]
    current_info = (
        f"📋 Hozirgi ma'lumotlar:\n\n"
        f"🏷️ Nomi: {med.get('name', 'N/A')}\n"
        f"💊 Foydali xususiyatlari: {med.get('benefits', 'N/A')}\n"
        f"⚠️ Qarshi ko'rsatmalar: {med.get('contraindications', 'N/A')}\n"
        f"💰 Narxi: {med.get('price', 'N/A')}\n"
        f"📷 Rasm: {'Mavjud' if med.get('photo') else 'Yoq'}\n\n"
        "Qaysi maydonni tahrirlashni xohlaysiz?\n"
        "1 - Nomi\n"
        "2 - Foydali xususiyatlari\n"
        "3 - Qarshi ko'rsatmalar\n"
        "4 - Narxi\n"
        "5 - Rasm\n\n"
        "Raqamni yuboring:"
    )
    
    await message.answer(current_info)
    await state.set_state(EditMedicine.choosing_field)

@dp.message(EditMedicine.choosing_field)
async def process_field_choice(message: Message, state: FSMContext):
    """Process field choice for editing"""
    choice = message.text.strip()
    
    field_map = {
        '1': ('name', 'Yangi nomi'),
        '2': ('benefits', 'Yangi foydali xususiyatlari'),
        '3': ('contraindications', 'Yangi qarshi ko\'rsatmalar'),
        '4': ('price', 'Yangi narxi'),
        '5': ('photo', 'Yangi rasm')
    }
    
    if choice not in field_map:
        await message.answer("❌ Iltimos, 1-5 orasidagi raqamni tanlang.")
        return
    
    field, prompt = field_map[choice]
    await state.update_data(editing_field=field)
    
    if field == 'photo':
        await message.answer(f"📷 {prompt}ni yuboring yoki 'yo'q' deb yozing:")
    else:
        await message.answer(f"✏️ {prompt}ni kiriting:")
    
    await state.set_state(EditMedicine.editing_field)

@dp.message(EditMedicine.editing_field, F.text | F.photo)
async def process_field_edit(message: Message, state: FSMContext):
    """Process the actual field edit"""
    data = await state.get_data()
    med_id = data.get('editing_medicine_id')
    field = data.get('editing_field')
    
    if not med_id or med_id not in MEDICINES:
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        await state.clear()
        return
    
    try:
        # Prepare update data
        update_data = {}
        
        if field == 'photo':
            if message.photo:
                photo_id = message.photo[-1].file_id
                update_data['photo'] = photo_id
                new_value = "Yangi rasm yuklandi"
            elif message.text and message.text.lower() in ['yo\'q', 'yoq', 'skip']:
                update_data['photo'] = None
                new_value = "Rasm o'chirildi"
            else:
                await message.answer("❌ Iltimos, rasm yuboring yoki 'yo'q' deb yozing.")
                return
        else:
            new_value = message.text.strip()
            update_data[field] = new_value
        
        # Update in database
        success = await db.update_medicine(med_id, update_data)
        
        if success:
            # Update in-memory cache
            MEDICINES[med_id].update(update_data)
            
            await message.answer(
                f"✅ Dori muvaffaqiyatli yangilandi!\n\n"
                f"🆔 ID: {med_id}\n"
                f"📝 Yangilangan maydon: {field}\n"
                f"🔄 Yangi qiymat: {new_value}",
                reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer(
                "❌ Xatolik yuz berdi. Dorini yangilashda muammo bo'ldi.",
                reply_markup=get_admin_keyboard()
            )
    except Exception as e:
        logging.error(f"Error updating medicine: {e}")
        await message.answer(
            "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.",
            reply_markup=get_admin_keyboard()
        )
    
    await state.clear()

@dp.callback_query(F.data == 'delete_medicine')
async def delete_medicine_start(callback: CallbackQuery, state: FSMContext):
    """Start deleting a medicine"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Sizda admin huquqlari yo'q!")
        return
    
    # Show available medicines with IDs
    medicines = await db.get_all_medicines()
    if not medicines:
        await callback.message.answer("❌ Hozircha dorilar mavjud emas!")
        return
    
    response = "🗑️ O'chirish uchun dori ID sini yuboring:\n\n"
    for med_id, med in medicines.items():
        response += f"ID: <code>{med_id}</code> - {med['name']}\n"
    
    await callback.message.answer(response, parse_mode='HTML')
    await state.set_state(MedicineStates.confirming_medicine_deletion)
    await callback.answer()

@dp.message(MedicineStates.confirming_medicine_deletion)
async def process_medicine_deletion(message: Message, state: FSMContext):
    """Process medicine deletion"""
    med_id = message.text.strip()
    
    if med_id not in MEDICINES:
        await message.answer("❌ Bunday ID li dori topilmadi. Iltimos, to'g'ri ID kiriting.")
        return
    
    try:
        # Delete from database
        success = await db.delete_medicine(med_id)
        
        if success:
            # Remove from in-memory cache
            medicine_name = MEDICINES[med_id].get('name', 'Noma\'lum')
            del MEDICINES[med_id]
            
            await message.answer(
                f"✅ Dori muvaffaqiyatli o'chirildi!\n\n"
                f"🏷️ Nomi: {medicine_name}\n"
                f"🆔 ID: {med_id}",
                reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer(
                "❌ Xatolik yuz berdi. Dorini o'chirishda muammo bo'ldi.",
                reply_markup=get_admin_keyboard()
            )
    except Exception as e:
        logging.error(f"Error deleting medicine: {e}")
        await message.answer(
            "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.",
            reply_markup=get_admin_keyboard()
        )
    
    await state.clear()

@dp.callback_query(F.data == 'admin_stats')
async def admin_stats(callback: CallbackQuery):
    """Show admin statistics"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Sizda admin huquqlari yo'q!")
        return
    
    try:
        # Get statistics from the database
        medicines = await db.get_all_medicines()
        orders = await db.get_all_orders()
        
        stats = {
            'total_medicines': len(medicines),
            'total_orders': len(orders),
            'pending_orders': len([o for o in orders.values() if o.get('status') == 'new']),
        }
        
        response = "📊 Statistika:\n\n"
        response += f"💊 Jami dorilar: {stats['total_medicines']}\n"
        response += f"📦 Jami buyurtmalar: {stats['total_orders']}\n"
        response += f"⏳ Kutilayotgan buyurtmalar: {stats['pending_orders']}"
        
        await callback.message.answer(response)
        await callback.answer()
    except Exception as e:
        logging.error(f"Xatolik yuz berdi: {e}")
        await callback.message.answer("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        await callback.answer()

# Inline menu callback handlers

@dp.callback_query(F.data == 'show_address')
async def show_address_callback(callback: CallbackQuery):
    """Show store address"""
    await callback.message.edit_text(
        f"📍 <b>Bizning manzilimiz:</b>\n\n{STORE_ADDRESS}",
        parse_mode='HTML',
        reply_markup=get_main_menu_inline()
    )
    await callback.answer()

@dp.callback_query(F.data == 'show_phone')
async def show_phone_callback(callback: CallbackQuery):
    """Show store phone"""
    await callback.message.edit_text(
        f"☎️ <b>Bizning telefon raqamimiz:</b>\n\n{STORE_PHONE}",
        parse_mode='HTML',
        reply_markup=get_main_menu_inline()
    )
    await callback.answer()

@dp.callback_query(F.data == 'show_medicines')
async def show_medicines_callback(callback: CallbackQuery):
    """Show medicines list"""
    await callback.message.edit_text(
        "🌿 <b>Mavjud o'simlik dorilar:</b>",
        reply_markup=get_medicines_menu(),
        parse_mode='HTML'
    )
    await callback.answer()

@dp.callback_query(F.data == 'place_order')
async def place_order_callback(callback: CallbackQuery):
    """Show order menu"""
    await callback.message.edit_text(
        "🛒 <b>Buyurtma berish:</b>\n\nQaysi dorini buyurtma qilmoqchisiz?",
        reply_markup=get_medicines_menu(),
        parse_mode='HTML'
    )
    await callback.answer()


async def main():
    # Initialize database data
    global MEDICINES, orders
    try:
        MEDICINES = await load_medicines()
        orders = await load_orders()
        logging.info(f"Loaded {len(MEDICINES)} medicines and {len(orders)} orders from database")
        logging.info(f"Medicine IDs loaded: {list(MEDICINES.keys())}")
    except Exception as e:
        logging.error(f"Error loading data from database: {e}")
        # Use hardcoded medicines as fallback
        logging.info("Using hardcoded medicines as fallback")
        orders = {}
    
    # Start the bot
    logging.info("Bot is starting...")
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logging.error(f"Botda xatolik yuz berdi: {e}")
    finally:
        await bot.session.close()
        logging.info("Bot to'xtatildi")

if __name__ == "__main__":
    asyncio.run(main())