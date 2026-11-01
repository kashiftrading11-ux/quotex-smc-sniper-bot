# ============================================
# 🤖 QUOTEX SMC SMART BRAIN BOT (SNIPER & AUTO-RADAR)
# Strategy: SMC (OB + FVG + BOS + Sweeps)
# Features: 1m (T-12s) | 5m (T-15s) | Level 3 Auto-Radar
# Total Pairs: 25 (6 Live + 19 OTC)
# ============================================

import os
import logging
import asyncio
import threading
from datetime import datetime
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler,
    CallbackQueryHandler, ContextTypes
)

# ================= STREAMLIT UI PAGE =================
st.set_page_config(page_title="Quotex SMC Sniper Bot", page_icon="🤖")
st.title("🤖 Quotex SMC Smart Brain Bot (Sniper Edition)")
st.markdown("---")
st.success("🟢 Status: Bot is Running 24/7 on Cloud!")
st.info("💡 Aapka Telegram Bot active hai. Laptop band kar dein, signals Telegram par aate rahenge.")

# ================= CONFIGURATION =================
# ⚠️ APNA NAYA TELEGRAM BOT TOKEN YAHAN DALEIN (Quotes ke andar)
BOT_TOKEN = "8878465383:AAEKp4SQvHD0Npd7C10uGaYM6f7v5oejPis"

# --- LIVE FOREX PAIRS ---
LIVE_PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "EUR/JPY": "EURJPY=X",
    "EUR/GBP": "EURGBP=X",
    "USD/CAD": "USDCAD=X",
}

# --- OTC PAIRS ---
OTC_PAIRS = {
    "USD/IDR (OTC)": "USDIDR=X",
    "USD/CAD (OTC)": "USDCAD=X",
    "USD/COP (OTC)": "USDCOP=X",
    "CAD/CHF (OTC)": "CADCHF=X",
    "EUR/USD (OTC)": "EURUSD=X",
    "USD/JPY (OTC)": "USDJPY=X",
    "USD/PHP (OTC)": "USDPHP=X",
    "EUR/CAD (OTC)": "EURCAD=X",
    "USD/CHF (OTC)": "USDCHF=X",
    "USD/PKR (OTC)": "USDPKR=X",
    "USD/ZAR (OTC)": "USDZAR=X",
    "NZD/CAD (OTC)": "NZDCAD=X",
    "USD/BDT (OTC)": "USDBDT=X",
    "GBP/USD (OTC)": "GBPUSD=X",
    "AUD/CAD (OTC)": "AUDCAD=X",
    "AUD/CHF (OTC)": "AUDCHF=X",
    "AUD/USD (OTC)": "AUDUSD=X",
    "USD/BRL (OTC)": "USDBRL=X",
    "EUR/CHF (OTC)": "EURCHF=X",
}

ALL_PAIRS = {**LIVE_PAIRS, **OTC_PAIRS}

MARTINGALE_AMOUNTS = [1, 2.5, 6]  # 3 Levels
MAX_LOSSES = 3

# ================= USER STATE =================
user_states = {}

def get_user_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = {
            "selected_pair": None,
            "selected_tf": "5m",
            "loss_count": {p: 0 for p in ALL_PAIRS},
            "last_signal": None,
        }
    return user_states[user_id]

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= DATA FETCH =================
def fetch_market_data(ticker, timeframe="5m"):
    try:
        tf_str = "1m" if timeframe == "1m" else "5m"
        period_str = "1d" if timeframe == "1m" else "5d"
        
        df = yf.download(
            ticker, period=period_str, interval=tf_str,
            progress=False, auto_adjust=True
        )
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        logger.error(f"Data fetch error for {ticker}: {e}")
        return None

# ================= SMC BRAIN ENGINE =================
def analyze_smc(df):
    if len(df) < 30:
        return None

    df = df.tail(30).copy()
    close = df["Close"].values
    high = df["High"].values
    low = df["Low"].values
    open_p = df["Open"].values

    buy_score = 0
    sell_score = 0
    smc_reasons = []

    recent_high = np.max(high[-15:-3])
    recent_low = np.min(low[-15:-3])

    # 1. Structure Break (BOS)
    if close[-1] > recent_high:
        buy_score += 2
        smc_reasons.append("⚡ Bullish BOS (Structure Break UP)")
    elif close[-1] < recent_low:
        sell_score += 2
        smc_reasons.append("⚡ Bearish BOS (Structure Break DOWN)")

    # 2. Fair Value Gap (FVG)
    if low[-1] > high[-3]:
        buy_score += 1.5
        smc_reasons.append("⚖️ Bullish FVG (Imbalance Zone)")
    elif high[-1] < low[-3]:
        sell_score += 1.5
        smc_reasons.append("⚖️ Bearish FVG (Imbalance Zone)")

    # 3. Order Block (OB) Detection
    is_last_red = close[-2] < open_p[-2]
    is_last_green = close[-2] > open_p[-2]
    strong_up = close[-1] > high[-2]
    strong_down = close[-1] < low[-2]

    if is_last_red and strong_up:
        buy_score += 2
        smc_reasons.append("📦 Bullish Order Block Tapped")
    elif is_last_green and strong_down:
        sell_score += 2
        smc_reasons.append("📦 Bearish Order Block Tapped")

    # 4. Liquidity Sweep
    if low[-1] < recent_low and close[-1] > recent_low:
        buy_score += 2
        smc_reasons.append("💧 Liquidity Swept Below (Bull Trap)")
    elif high[-1] > recent_high and close[-1] < recent_high:
        sell_score += 2
        smc_reasons.append("💧 Liquidity Swept Above (Bear Trap)")

    if buy_score >= 3 and buy_score > sell_score:
        direction = "🟢 BUY (UP ⬆️)"
        confidence = min(96, int(60 + (buy_score * 7)))
    elif sell_score >= 3 and sell_score > buy_score:
        direction = "🔴 SELL (DOWN ⬇️)"
        confidence = min(96, int(60 + (sell_score * 7)))
    else:
        trend_up = close[-1] > close[-5]
        direction = "🟢 BUY (UP ⬆️)" if trend_up else "🔴 SELL (DOWN ⬇️)"
        confidence = 68
        smc_reasons.append("📊 Trend Momentum Alignment")

    return {
        "direction": direction,
        "confidence": confidence,
        "price": float(close[-1]),
        "reasons": smc_reasons
    }

# ================= DYNAMIC TIMING ENGINE =================
def calculate_wait_seconds(timeframe="5m"):
    now = datetime.now()
    second = now.second
    microsecond = now.microsecond
    minute = now.minute

    if timeframe == "1m":
        seconds_in_cycle = second + (microsecond / 1_000_000)
        target = 48.0  # 12 seconds before 60s
        cycle_len = 60.0
    else:  # 5m
        seconds_in_cycle = (minute % 5) * 60 + second + (microsecond / 1_000_000)
        target = 285.0  # 15 seconds before 300s
        cycle_len = 300.0

    if seconds_in_cycle < target:
        return target - seconds_in_cycle
    else:
        return (cycle_len - seconds_in_cycle) + target

# ================= TELEGRAM HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user_state(user.id)

    keyboard = [
        [
            InlineKeyboardButton("🌐 Live Forex Pairs", callback_data="cat_live"),
            InlineKeyboardButton("⚡ Quotex OTC Pairs", callback_data="cat_otc")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🤖 *Quotex SMC Smart Brain Bot (Sniper Edition)*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👋 Welcome {user.first_name}!\n\n"
        f"🧠 Strategy: *SMC (OB + FVG + BOS + Sweeps)*\n"
        f"⏱ Timeframes: *1 Min (T-12s) | 5 Min (T-15s)*\n"
        f"🔄 *Level 3 Auto-Radar Sniper Loop Enabled*\n"
        f"💰 Martingale: 3 Levels ($1 → $2.5 → $6)\n\n"
        f"👇 *Category Select Karein:*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    state = get_user_state(user_id)

    # 1. Category Selection
    if data in ["cat_live", "cat_otc"]:
        pair_dict = LIVE_PAIRS if data == "cat_live" else OTC_PAIRS
        category_title = "🌐 Live Forex Pairs" if data == "cat_live" else "⚡ Quotex OTC Pairs"
        
        keyboard = []
        pair_list = list(pair_dict.keys())
        for i in range(0, len(pair_list), 2):
            row = []
            for j in range(2):
                if i + j < len(pair_list):
                    p = pair_list[i + j]
                    row.append(InlineKeyboardButton(p, callback_data=f"pair_{p}"))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="back_categories")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"👇 *{category_title} Select Karein:*",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    # 2. Pair Selected -> Show Timeframe Choice
    elif data.startswith("pair_"):
        pair = data.replace("pair_", "")
        state["selected_pair"] = pair

        keyboard = [
            [
                InlineKeyboardButton("⏱ 1 Minute (T-12s)", callback_data="tf_1m"),
                InlineKeyboardButton("⏱ 5 Minutes (T-15s)", callback_data="tf_5m")
            ],
            [InlineKeyboardButton("📋 Change Pair", callback_data="back_categories")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"✅ Selected Pair: *{pair}*\n\n"
            f"👇 *Timeframe Select Karein:*",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    # 3. Timeframe Selected -> Show RUN Button
    elif data in ["tf_1m", "tf_5m"]:
        tf = "1m" if data == "tf_1m" else "5m"
        state["selected_tf"] = tf
        pair = state["selected_pair"]
        lead_time = "12 sec" if tf == "1m" else "15 sec"

        keyboard = [
            [InlineKeyboardButton("▶️ RUN - SMC Signal", callback_data="run")],
            [InlineKeyboardButton("⚙️ Change Timeframe", callback_data=f"pair_{pair}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"✅ Pair: *{pair}*\n"
            f"⏱ Timeframe: *{tf.upper()}*\n"
            f"⏰ Signal Timing: *Exact {lead_time} Before Close*\n\n"
            f"▶️ Press **RUN** to start market scanning.",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    # 4. RUN Button Action (Level 3 Auto-Radar Engine)
    elif data == "run":
        pair = state["selected_pair"]
        tf = state["selected_tf"]
        if not pair:
            await query.edit_message_text("⚠️ Pehle pair select karein! /start")
            return

        loss_count = state["loss_count"][pair]
        if loss_count >= MAX_LOSSES:
            keyboard = [[InlineKeyboardButton("🔄 Reset & Try Again", callback_data=f"reset_{pair}")]]
            await query.edit_message_text(
                f"🛑 *3 Losses ho gaye {pair} pe!*\n"
                f"Cool down karein aur reset karein.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        lead_sec = 12 if tf == "1m" else 15
        ticker = ALL_PAIRS[pair]
        scan_candle_count = 1

        # ================= AUTO-RADAR LOOP =================
        while True:
            wait_seconds = calculate_wait_seconds(tf)
            
            radar_mode_text = ""
            if loss_count == 2:
                radar_mode_text = f"\n🚨 *LEVEL 3 AUTO-RADAR ACTIVE (Candle #{scan_candle_count})*\nScanning for 88%+ Sniper Signal..."

            await query.edit_message_text(
                f"⏳ *SMC Brain Market Analyze Kar Raha Hai...*\n"
                f"📌 Pair: {pair} ({tf.upper()})\n"
                f"⏰ Signal exact *{lead_sec}s pehle* aayega.\n"
                f"⏱ Wait Time: ~{int(wait_seconds)} sec...{radar_mode_text}",
                parse_mode="Markdown"
            )

            await asyncio.sleep(wait_seconds)

            df = fetch_market_data(ticker, tf)

            if df is None:
                keyboard = [[InlineKeyboardButton("🔄 Try Again", callback_data="run")]]
                await query.edit_message_text(
                    "⚠️ Data fetch error (Weekend/Market closed?). Retry karein.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

            smc_res = analyze_smc(df)
            if smc_res is None:
                await query.edit_message_text("⚠️ Data kam hai SMC analyze karne ke liye.")
                return

            # Level 3 Strict Sniper Filter Logic
            if loss_count == 2:  # Level 3 Trade ($6)
                if smc_res["confidence"] >= 88:
                    break  # Sniper signal found! Exit loop and send signal.
                else:
                    scan_candle_count += 1
                    await query.edit_message_text(
                        f"🔄 *Candle #{scan_candle_count-1} Skipped (Confidence {smc_res['confidence']}% < 88%)*\n"
                        f"🛡 Level 3 Guard: Waiting for PERFECT setup...\n"
                        f"⏳ *Auto-Scanning Candle #{scan_candle_count}...*",
                        parse_mode="Markdown"
                    )
                    await asyncio.sleep(2)
            else:
                break

        # ================= SIGNAL MESSAGE DISPATCH =================
        level = loss_count
        amount = MARTINGALE_AMOUNTS[level]
        mode = "🚨 LEVEL 3 SNIPER RECOVERY" if level == 2 else ("🔥 RECOVERY" if level > 0 else "✅ NORMAL")

        reasons_text = "\n".join([f"  • {r}" for r in smc_res["reasons"]])

        full_msg = (
            f"⚡ *SMC SIGNAL GENERATED* ⚡\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{smc_res['direction']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 Pair: {pair}\n"
            f"⏱ Timeframe: *{tf.upper()}*\n"
            f"⏰ Expiry: *Next {tf.upper()} Candle*\n"
            f"💹 Price: {smc_res['price']:.5f}\n"
            f"🧠 AI Confidence: {smc_res['confidence']}%\n\n"
            f"🔍 *SMC Confluence:*\n{reasons_text}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Trade Amount: ${amount} ({mode})\n"
            f"📈 Level: {level + 1}/3\n"
            f"🚨 *TRADE NOW — {lead_sec} sec remaining!*\n"
            f"━━━━━━━━━━━━━━━━━━"
        )

        state["last_signal"] = pair

        keyboard = [
            [
                InlineKeyboardButton("✅ WIN", callback_data="win"),
                InlineKeyboardButton("❌ LOSS", callback_data="loss"),
            ],
            [
                InlineKeyboardButton("▶️ Next Signal", callback_data="run"),
                InlineKeyboardButton("📋 Change Pair", callback_data="back_categories"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            full_msg, parse_mode="Markdown", reply_markup=reply_markup
        )

    # 5. WIN Button Action
    elif data == "win":
        pair = state["selected_pair"]
        if pair:
            state["loss_count"][pair] = 0

        keyboard = [[InlineKeyboardButton("▶️ Next Signal", callback_data="run")]]
        await query.edit_message_text(
            f"🎉 *WIN! Profit booked!*\n"
            f"📊 Martingale Reset → $1\n\n"
            f"Next signal ke liye RUN press karein.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # 6. LOSS Button Action
    elif data == "loss":
        pair = state["selected_pair"]
        if pair:
            state["loss_count"][pair] = min(state["loss_count"][pair] + 1, MAX_LOSSES)
            level = state["loss_count"][pair]

            if level >= MAX_LOSSES:
                keyboard = [[InlineKeyboardButton("🔄 Reset", callback_data=f"reset_{pair}")]]
                await query.edit_message_text(
                    f"😔 *3rd Loss! Max Recovery Reached.*\n"
                    f"🛑 Cool down karein. Reset karein?",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                next_amount = MARTINGALE_AMOUNTS[level]
                keyboard = [[InlineKeyboardButton("▶️ Run Level 3 Sniper", callback_data="run")]]
                await query.edit_message_text(
                    f"😔 *Loss Noted.*\n"
                    f"📊 Level {level + 1} Recovery Mode ON\n"
                    f"💰 Next Amount: ${next_amount}\n"
                    f"🎯 Level 3 Auto-Radar Mode Ready!\n\n"
                    f"Next signal ke liye RUN press karein.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

    # 7. RESET Button Action
    elif data.startswith("reset_"):
        pair = data.replace("reset_", "")
        state["loss_count"][pair] = 0

        keyboard = [[InlineKeyboardButton("▶️ RUN Signal", callback_data="run")]]
        await query.edit_message_text(
            f"🔄 *Reset Ho Gaya!*\n"
            f"💰 Amount back to $1 (Normal Mode).",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # 8. Back to Categories Action
    elif data == "back_categories":
        keyboard = [
            [
                InlineKeyboardButton("🌐 Live Forex Pairs", callback_data="cat_live"),
                InlineKeyboardButton("⚡ Quotex OTC Pairs", callback_data="cat_otc")
            ]
        ]
        await query.edit_message_text(
            "👇 *Category Select Karein:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ================= BACKGROUND BOT RUNNER =================
def run_telegram_bot_background():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Telegram Bot Thread Active on Streamlit Cloud!")
    app.run_polling(drop_pending_updates=True, stop_signals=False)

if "telegram_bot_thread" not in st.session_state:
    bot_thread = threading.Thread(target=run_telegram_bot_background, daemon=True)
    bot_thread.start()
    st.session_state.telegram_bot_thread = bot_thread
    st.success("✅ Telegram Bot polling loop started successfully!")
