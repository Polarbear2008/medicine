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

# Bot sozlamalari
STORE_PHONE = "+998 9X XXX XX XX"
STORE_ADDRESS = "Toshkent shahri, [aniq manzil]"
PAYMENT_CARD = "8600 xxxx xxxx xxxx"
ADMIN_IDS = [5747916482]  # Admin foydalanuvchi ID larini qo'shing
ORDER_CHANNEL = "@zakazlarshifo17"  # Buyurtmalar kanali

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

def load_orders() -> dict:
    """JSON fayldan buyurtmalarni yuklash"""
    if not os.path.exists(ORDERS_FILE):
        return {}
    try:
        with open(ORDERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Buyurtmalarni yuklashda xatolik: {e}")
        return {}

def save_orders(orders: dict) -> None:
    """Buyurtmalarni JSON faylga saqlash"""
    try:
        with open(ORDERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Buyurtmalarni saqlashda xatolik: {e}")

def save_medicines(medicines: Dict[str, Dict]) -> None:
    """Dorilarni JSON faylga saqlash"""
    try:
        with open('medicines.json', 'w', encoding='utf-8') as f:
            json.dump(medicines, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Dorilarni saqlashda xatolik: {e}")
        raise

def load_medicines() -> Dict[str, Dict]:
    """JSON fayldan dorilarni yuklash"""
    try:
        with open('medicines.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Mavjud ma'lumotlarni yuklash
orders = load_orders()

# Dorilarni yuklash
try:
    with open('medicines.json', 'r', encoding='utf-8') as f:
        MEDICINES.update(json.load(f))
except FileNotFoundError:
    # Agar fayl mavjud bo'lmasa, dastlabki faylni yaratish
    with open('medicines.json', 'w', encoding='utf-8') as f:
        json.dump(MEDICINES, f, ensure_ascii=False, indent=2)

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
    med_id = callback.data[4:]  # 'med_' prefixini olib tashlash
    if med_id not in MEDICINES:
        await callback.answer("Dori topilmadi")
        return
    
    med = MEDICINES[med_id]
    text = (
        f"{med['name']}\n\n"
        f"💊 <b>Foydali xususiyatlari:</b>\n{med['benefits']}\n\n"
        f"⚠️ <b>Qarshi ko'rsatmalar:</b>\n{med['contraindications']}\n\n"
        f"💰 <b>Narxi:</b> {med['price']}"
    )
    
    # Buyurtma tugmasini qo'shish
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🛒 Hozir buyurtma berish', callback_data=f'order_{med_id}')],
        [InlineKeyboardButton(text='🔙 Ro\'yxatga qaytish', callback_data='back_to_medicines')]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')

@dp.callback_query(F.data == 'back_to_medicines')
async def back_to_medicines(callback: CallbackQuery):
    """Dorilar ro'yxatiga qaytish"""
    await callback.message.edit_text(
        "🌿 Mavjud o'simlik dorilar:",
        reply_markup=get_medicines_menu()
    )

@dp.callback_query(F.data.startswith('order_'))
async def start_order(callback: CallbackQuery, state: FSMContext):
    """Buyurtma jarayonini boshlash"""
    med_id = callback.data[6:]  # 'order_' prefixini olib tashlash
    if med_id not in MEDICINES:
        await callback.answer("Dori topilmadi")
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
        "📍 Buyurtmangizni qayerga yetkazib beramiz?",
        reply_markup=keyboard
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

def get_order_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Buyurtma uchun tasdiqlash tugmalari"""
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ Yetkazib berildi",
                callback_data=f"order_shipped_{order_id}"
            ),
            InlineKeyboardButton(
                text="❌ Bekor qilish",
                callback_data=f"order_cancel_{order_id}"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def send_order_to_channel(order_data: dict, bot: Bot):
    """Buyurtma tafsilotlarini sozlangan kanalga yuborish"""
    try:
        # Buyurtma tafsilotlarini formatlash
        order_text = (
            "🆕 <b>YANGI BUYURTMA QABUL QILINDI</b>\n\n"
            f"🆔 <b>Buyurtma ID:</b> <code>{order_data['order_id']}</code>\n"
            f"👤 <b>Mijoz:</b> {order_data['full_name']} (@{order_data['username'] or 'N/A'})\n"
            f"📞 <b>Telefon:</b> {order_data['delivery_info']['phone']}\n\n"
            f"💊 <b>Dori:</b> {order_data['medicine']}\n"
            f"⏳ <b>Muddat:</b> {order_data['months']} oy\n"
            f"💰 <b>Summa:</b> {order_data['price']}\n\n"
            f"📍 <b>Yetkazib berish:</b> {order_data['delivery_info'].get('address', 'Manzil kiritilmagan')}\n\n"
            f"📅 <b>Sana:</b> {order_data.get('timestamp', 'Noma`lum')}"
        )
        
        # Kanalga yuborish
        try:
            # Avval rasmni yuboramiz
            if order_data.get('receipt_photo_id'):
                await bot.send_photo(
                    chat_id=ORDER_CHANNEL,
                    photo=order_data['receipt_photo_id'],
                    caption=order_text,
                    parse_mode='HTML',
                    reply_markup=get_order_keyboard(order_data['order_id'])
                )
            else:
                await bot.send_message(
                    chat_id=ORDER_CHANNEL,
                    text=order_text,
                    parse_mode='HTML',
                    reply_markup=get_order_keyboard(order_data['order_id'])
                )
                
        except Exception as e:
            logging.error(f"Kanalga xabar yuborishda xatolik: {e}")
            # Try to send error message to admin
            try:
                await bot.send_message(
                    chat_id=ADMIN_IDS[0],
                    text=f"❌ Kanalga xabar yuborishda xatolik: {e}"
                )
            except:
                pass
        
    except Exception as e:
        logging.error(f"Buyurtma kanalga yuborishda xatolik: {e}")

async def update_order_status(order_id: str, status: str, message: Message):
    """Update order status and notify user"""
    orders = load_orders()
    if order_id in orders:
        orders[order_id]['status'] = status
        save_orders(orders)
        
        # Update message in channel
        try:
            await message.edit_reply_markup(reply_markup=None)
            status_text = "✅ Yetkazib berildi" if status == "shipped" else "❌ Bekor qilindi"
            await message.answer(f"{status_text} | Buyurtma ID: {order_id}")
            
            # Notify user
            user_id = orders[order_id].get('user_id')
            if user_id:
                status_msg = {
                    'shipped': "✅ Sizning buyurtmangiz yetkazib berildi!",
                    'cancelled': "❌ Sizning buyurtmangiz bekor qilindi."
                }.get(status, "Buyurtma holati yangilandi.")
                
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=f"{status_msg}\n\nBuyurtma ID: {order_id}"
                    )
                except Exception as e:
                    logging.error(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
                    
        except Exception as e:
            logging.error(f"Xabar yangilashda xatolik: {e}")

@dp.callback_query(F.data.startswith('order_'))
async def handle_order_actions(callback: CallbackQuery):
    """Handle order actions from channel"""
    try:
        action, order_id = callback.data.split('_', 1)
        
        if action == 'shipped':
            await update_order_status(order_id, 'shipped', callback.message)
        elif action == 'cancel':
            await update_order_status(order_id, 'cancelled', callback.message)
            
        await callback.answer()
    except Exception as e:
        logging.error(f"Buyurtma amalini bajarishda xatolik: {e}")
        await callback.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.", show_alert=True)

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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        "💊 Iltimos, buyurtma bermoqchi bo'lgan doringizni tanlang:",
        reply_markup=keyboard
    )

# Command handlers
dp.message.register(cmd_start, CommandStart())
dp.message.register(show_address, F.text == "📍 Manzil")
dp.message.register(show_phone, F.text == "📞 Bog'lanish")
dp.message.register(show_medicines, F.text == "💊 Dorilar")
dp.message.register(show_medicines_for_order, F.text == "🛒 Buyurtma berish")

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
            'address': data.get('delivery_address', 'N/A')
        },
        'receipt_photo_id': data.get('receipt_photo_id')
    }
    
    # Save order
    orders = load_orders()
    orders[order_id] = order_data
    save_orders(orders)
    
    # Send confirmation to user
    await callback.message.edit_text(
        "✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"🆔 Buyurtma raqami: <code>{order_id}</code>\n"
        f"📅 Sana: {order_data['timestamp']}\n"
        "\nTez orada siz bilan bog'lanamiz!",
        parse_mode='HTML'
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
    await callback.answer()


async def main():
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