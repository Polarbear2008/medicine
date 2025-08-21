# MedBot - Telegram Medicine Store Bot

A Telegram bot for an online medicine store built with Python and aiogram.

## Features

- 🏬 Browse available medicines
- 🛒 Add items to basket
- 💳 Simple checkout process
- 📞 Contact information
- ❓ Help section

## Setup

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your bot token:
   ```
   BOT_TOKEN=your_bot_token_here
   ```
4. Run the bot:
   ```
   python bot.py
   ```

## Usage

1. Start the bot with `/start`
2. Use the menu to navigate:
   - 🏬 Store - Browse medicines
   - 📦 Basket - View your cart
   - 📞 Contact - Get in touch
   - ❓ Help - How to use the bot

## Extending the Bot

- Add more medicines to the `MEDICINES` dictionary in `bot.py`
- Implement a database instead of in-memory storage for persistence
- Add payment gateway integration
- Create an admin panel for inventory management
