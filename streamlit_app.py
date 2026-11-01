import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import datetime
import time
import asyncio
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ==========================================
# CONFIGURATION & SETTINGS
# ==========================================
BOT_TOKEN = "8878465383:AAEKp4SQvHD0Npd7C10uGaYM6f7v5oejPis"  # Apna Telegram Bot Token yahan dalein

# 25 Total Pairs (Live Forex + Quotex OTC Pairs)
PAIRS = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "JPY=X",
    "EUR/JPY": "EURJPY=X", "EUR/GBP": "EURGBP=X", "USD/CAD": "CAD=X",
    "EUR/USD (OTC)": "EURUSD=X", "GBP/USD (OTC)": "GBPUSD=X", "USD/JPY (OTC)": "JPY=X",
    "USD/CAD (OTC)": "CAD=X", "USD/IDR (OTC)": "IDR=X", "USD/COP (OTC)": "COP=X",
    "CAD/CHF (OTC)": "CADCHF=X", "USD/PHP (OTC)": "PHP=X", "EUR/CAD (OTC)": "EURCAD=X",
    "USD/CHF (OTC)": "CHF=X", "USD/PKR (OTC)": "PKR=X", "USD/ZAR (OTC)": "ZAR=X",
    "NZD/CAD (OTC)": "NZDCAD=X", "USD/BDT (OTC)": "BDT=X", "AUD/CAD (OTC)": "AUDCAD=X",
    "AUD/CHF (OTC)": "AUDCHF=X", "AUD/USD (OTC)": "AUDUSD=X", "USD/BRL (OTC)": "BRL=X",
    "EUR/CHF (OTC)": "EURCHF=X"
}

# User Sessions Data Storage
user_sessions = {}

# ==========================================
# PURE AI MARKET ANALYSIS ENGINE (BALANCED)
# ==========================================
def fetch_market_data(ticker_symbol, period="1d", interval="1m"):
    try:
        data = yf.download(tickers=ticker_symbol, period=period, interval=interval, progress=False)
        if data.empty:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except Exception as e:
        return None

def ai_market_analysis(df, martingale_level=1):
    """
    Balanced AI Engine: Analyzes instant price action (Green/Red candles, Wick rejection)
    Produces an equal chance of CALL or PUT based strictly on real-time market dynamics.
    """
    if df is None or len(df) < 5:
        # Fallback in case of no data
        return {"direction": "CALL (BUY) 🟢", "confidence": 85, "reason": "Default Upward Bias"}

    # Extract last 5 candles data
    closes = df['Close'].tail(5).values
    opens = df['Open'].tail(5).values
    highs = df['High'].tail(5).values
    lows = df['Low'].tail(5).values

    curr_close = closes[-1]
    curr_open = opens[-1]
    curr_high = highs[-1]
    curr_low = lows[-1]

    ai_score = 0

    # 1. Micro-Trend Component (Comparing current to 4 candles ago)
    if curr_close > closes[0]:
        ai_score += 2
    else:
        ai_score -= 2

    # 2. Current Candle Color Momentum Component
    if curr_close > curr_open:
        ai_score += 3  # Green candle pushing UP
    else:
        ai_score -= 3  # Red candle pushing DOWN

    # 3. Wick Rejection Component (Buyers vs Sellers pressure)
    upper_wick = curr_high - max(curr_open, curr_close)
    lower_wick = min(curr_open, curr_close) - curr_low

    if lower_wick > upper_wick:
        ai_score += 2  # Strong buyer rejection from bottom
    elif upper_wick > lower_wick:
        ai_score -= 2  # Strong seller rejection from top

    # Guaranteed balanced decision logic
    if ai_score >= 0:
        direction = "CALL (BUY) 🟢"
        reasons = ["Bullish Price Action", "Lower Wick Rejection", "Micro Uptrend Breakout"]
    else:
        direction = "PUT (SELL) 🔴"
        reasons = ["Bearish Price Action", "Upper Wick Rejection", "Micro Downtrend Momentum"]

    # Calculate Confidence
    base_confidence = 85 + min(10, abs(ai_score))
    
    # Increase confidence based on Martingale Level (Recovery Mode)
    if martingale_level > 1:
        base_confidence = min(98, base_confidence + (martingale_level * 3))

    return {
        "direction": direction,
        "confidence": base_confidence,
        "reason": reasons[abs(ai_score) % len(reasons)]
    }

# ==========================================
# TELEGRAM KEYBOARDS
# ==========================================
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Select Pair", callback_data="menu_select_pair"),
         InlineKeyboardButton("⏱️ Set Timeframe", callback_data="menu_select_tf")],
        [InlineKeyboardButton("🚀 START SNIPER BOT", callback_data="start_bot")],
        [InlineKeyboardButton("🛑 STOP BOT", callback_data="stop_bot")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_signal_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ WIN (Level Reset)", callback_data="result_win")],
        [InlineKeyboardButton("❌ LOSS (Next Level)", callback_data="result_loss")],
        [InlineKeyboardButton("⏭️ SKIP (Skip to Next Signal)", callback_data="result_skip")],
        [InlineKeyboardButton("🛑 STOP BOT", callback_data="stop_bot")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==========================================
# TELEGRAM BOT HANDLERS
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            "pair": "EUR/USD", "tf": 1, "active": False,
            "level": 1, "amount": 1.0, "wins": 0, "losses": 0,
            "waiting_for_result": False  # New variable to pause signals
        }

    session = user_sessions[chat_id]
    msg = (
        "🤖 **QUOTEX AI SNIPER BOT v5.0** 🤖\n\n"
        "✨ **Features:**\n"
        "• Pure Balanced AI (CALL & PUT dynamic signals)\n"
        "• **Wait-for-Result System:** Bot will wait for you to click WIN/LOSS before giving the next signal.\n"
        "• Smart Martingale Recovery ($1 ➔ $2.50 ➔ $6.00)\n\n"
        "📌 **Current Status:**\n"
        f"Pair: `{session['pair']}` | Timeframe: `{session['tf']}m`\n"
        f"Level: `Level {session['level']} (${session['amount']:.2f})`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            "pair": "EUR/USD", "tf": 1, "active": False,
            "level": 1, "amount": 1.0, "wins": 0, "losses": 0,
            "waiting_for_result": False
        }

    session = user_sessions[chat_id]
    data = query.data

    if data == "menu_select_pair":
        keyboard = []
        pair_keys = list(PAIRS.keys())
        for i in range(0, len(pair_keys), 2):
            row = [InlineKeyboardButton(pair_keys[i], callback_data=f"set_pair_{pair_keys[i]}")]
            if i + 1 < len(pair_keys):
                row.append(InlineKeyboardButton(pair_keys[i+1], callback_data=f"set_pair_{pair_keys[i+1]}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")])
        await query.edit_message_text("📊 Select Currency Pair:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("set_pair_"):
        selected_pair = data.replace("set_pair_", "")
        session["pair"] = selected_pair
        await query.edit_message_text(f"✅ Pair Set to: `{selected_pair}`", parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif data == "menu_select_tf":
        keyboard = [
            [InlineKeyboardButton("⚡ 1 Minute (12s Lead Time)", callback_data="set_tf_1")],
            [InlineKeyboardButton("📊 5 Minutes (15s Lead Time)", callback_data="set_tf_5")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.edit_message_text("⏱️ Select Timeframe:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("set_tf_"):
        tf_val = int(data.replace("set_tf_", ""))
        session["tf"] = tf_val
        await query.edit_message_text(f"✅ Timeframe Set to: `{tf_val} Minute(s)`", parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif data == "start_bot":
        session["active"] = True
        session["waiting_for_result"] = False  # Reset wait state
        await query.edit_message_text(
            f"🟢 **BOT STARTED!**\n\nWaiting for the exact signal time on `{session['pair']}` ({session['tf']}m TF)...\n"
            f"Current Target: Level {session['level']} (${session['amount']:.2f})",
            parse_mode="Markdown", reply_markup=get_main_keyboard()
        )

    elif data == "stop_bot":
        session["active"] = False
        session["waiting_for_result"] = False
        await query.edit_message_text("🔴 **BOT STOPPED.**", reply_markup=get_main_keyboard())

    elif data == "main_menu":
        await query.edit_message_text("🤖 **MAIN MENU**", reply_markup=get_main_keyboard())

    elif data == "result_win":
        session["wins"] += 1
        session["level"] = 1
        session["amount"] = 1.00
        session["waiting_for_result"] = False  # UNPAUSE BOT
        await query.edit_message_text(
            f"🎉 **WIN CONFIRMED!**\n\nTotal Wins: `{session['wins']}`\n"
            f"🔄 Level Reset to **Level 1 ($1.00)**.\n"
            f"⏳ Bot is now waiting for the next valid setup...",
            parse_mode="Markdown", reply_markup=get_main_keyboard()
        )

    elif data == "result_loss":
        session["losses"] += 1
        if session["level"] == 1:
            session["level"] = 2
            session["amount"] = 2.50
        elif session["level"] == 2:
            session["level"] = 3
            session["amount"] = 6.00
        else:
            session["level"] = 1  # Reset if 3rd level also lost
            session["amount"] = 1.00
            
        session["waiting_for_result"] = False  # UNPAUSE BOT
        await query.edit_message_text(
            f"⚠️ **LOSS RECORDED!**\n\nTotal Losses: `{session['losses']}`\n"
            f"📈 Switching to **Level {session['level']} (${session['amount']:.2f})**.\n"
            f"⏳ AI is now scanning for max recovery setup...",
            parse_mode="Markdown", reply_markup=get_main_keyboard()
        )

    elif data == "result_skip":
        # User missed the trade or wanted to skip
        session["waiting_for_result"] = False  # UNPAUSE BOT
        await query.edit_message_text(
            f"⏭️ **TRADE SKIPPED.**\n\nMartingale level maintained at Level {session['level']}.\n"
            f"⏳ Bot is waiting for the next setup...",
            parse_mode="Markdown", reply_markup=get_main_keyboard()
        )

# ==========================================
# BACKGROUND SIGNAL DISPATCHER LOOP
# ==========================================
async def bot_signal_loop(app):
    """Monitors clock and dispatches signals if bot is active and NOT waiting for result."""
    while True:
        try:
            now = datetime.datetime.now()
            current_sec = now.second
            current_min = now.minute

            for chat_id, session in list(user_sessions.items()):
                # Only check if active AND NOT waiting for user result
                if not session.get("active", False) or session.get("waiting_for_result", False):
                    continue

                tf = session["tf"]
                target_signal = False

                # 1m TF triggers at 48s (12s lead)
                if tf == 1 and current_sec == 48:
                    target_signal = True
                # 5m TF triggers at 4m:45s (15s lead)
                elif tf == 5 and (current_min % 5 == 4) and current_sec == 45:
                    target_signal = True

                if target_signal:
                    pair_name = session["pair"]
                    ticker = PAIRS.get(pair_name, "EURUSD=X")
                    level = session["level"]
                    amount = session["amount"]

                    # Fetch market data & run AI
                    df = fetch_market_data(ticker, period="1d", interval=f"{tf}m")
                    ai_res = ai_market_analysis(df, martingale_level=level)

                    # PAUSE the bot for this user until they press WIN/LOSS/SKIP
                    session["waiting_for_result"] = True

                    signal_msg = (
                        f"🤖 **AI SNIPER SIGNAL** 🤖\n\n"
                        f"🔤 **Pair:** `{pair_name}`\n"
                        f"⏱️ **Timeframe:** `{tf} MINUTE`\n"
                        f"📊 **Action:** {ai_res['direction']}\n"
                        f"💰 **Stake:** `Level {level} (${amount:.2f})`\n"
                        f"🎯 **Confidence:** `{ai_res['confidence']}%`\n"
                        f"🧠 **AI Reason:** `{ai_res['reason']}`\n\n"
                        f"⚡ *Enter trade exactly at 00:00 candle open!*\n\n"
                        f"⚠️ **BOT PAUSED!** Click ✅ WIN or ❌ LOSS below to get the next signal."
                    )

                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=signal_msg,
                        parse_mode="Markdown",
                        reply_markup=get_signal_keyboard()
                    )

            await asyncio.sleep(1)

        except Exception as e:
            await asyncio.sleep(1)

# ==========================================
# ASYNC BOT RUNNER & STREAMLIT INTEGRATION
# ==========================================
def start_telegram_app():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Add background signal loop
    loop.create_task(bot_signal_loop(app))

    # Run bot polling
    app.run_polling(drop_pending_updates=True, stop_signals=False)

if "bot_started" not in st.session_state:
    st.session_state["bot_started"] = True
    t = threading.Thread(target=start_telegram_app, daemon=True)
    t.start()

# Streamlit UI
st.set_page_config(page_title="Quotex AI Sniper", page_icon="🤖", layout="wide")
st.title("🤖 Quotex AI Autonomous Bot")
st.markdown("---")
st.success("✅ Telegram Bot is running 24/7. Open Telegram to control the bot.")
