import json
import logging
import os
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.error import BadRequest, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# ============ CONFIG ============
BOT_TOKEN = "8940470600:AAFARfi2d9hUuRKc10gI6hqBaG8ZGm6u9QA"  # Revoke old token and paste new token here
ADMIN_ID = 2063515136
DATA_FILE = "fund.txt"
# ================================

# --- Silence noisy httpx & network logs ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# Silence httpx and internal telegram requests from console
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# Conversation States
(
    ADD_FUND_DATE,
    ADD_FUND_AMOUNT,
    ADD_EXPENSE_PURPOSE,
    ADD_EXPENSE_AMOUNT,
    EDIT_RECORD_SELECT,
    EDIT_COLL_DAY,
    EDIT_COLL_AMOUNT,
    EDIT_EXP_PURPOSE,
    EDIT_EXP_AMOUNT,
) = range(9)

# ---------- Data Store (fund.txt) ----------

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except Exception as e:
            logging.error(f"Error reading {DATA_FILE}: {e}")
    return {"collections": {}, "expenses": []}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error saving {DATA_FILE}: {e}")

# ---------- Menus ----------

async def show_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Add Fund", callback_data="add_fund")],
        [InlineKeyboardButton("➖ Add Expense", callback_data="add_expense")],
        [InlineKeyboardButton("✏️ Edit Data", callback_data="edit_data")],
        [InlineKeyboardButton("📊 View Fund Status", callback_data="fund_data")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "👑 *Admin Control Panel* 👑"

    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_user_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 View Fund Data", callback_data="fund_data")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👥 *User Panel*", reply_markup=reply_markup, parse_mode="Markdown")

# ---------- Add Fund Flow ----------

async def handle_add_fund(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📅 *Enter the Day/Date* (e.g., 1, 2, 3 or 25-Aug):", parse_mode="Markdown")
    return ADD_FUND_DATE

async def handle_add_fund_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = update.message.text.strip()
    context.user_data["fund_date"] = date
    await update.message.reply_text("💰 *Enter the amount to add:*", parse_mode="Markdown")
    return ADD_FUND_AMOUNT

async def handle_add_fund_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_str = update.message.text.strip()
    if not amount_str.isdigit():
        await update.message.reply_text("⚠️ Invalid amount! Please enter digits only (e.g., 500):")
        return ADD_FUND_AMOUNT

    date = context.user_data["fund_date"]
    amount = int(amount_str)

    data = load_data()
    data["collections"][date] = data["collections"].get(date, 0) + amount
    save_data(data)

    total = sum(data["collections"].values())
    await update.message.reply_text(
        f"✅ *Fund Added Successfully!*\n\n"
        f"📅 Day {date}: ₹{amount}\n"
        f"💰 Total Collections: ₹{total}",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    await show_admin_buttons(update, context)
    return ConversationHandler.END

# ---------- Add Expense Flow ----------

async def handle_add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📌 *Enter the purpose of the expense:*", parse_mode="Markdown")
    return ADD_EXPENSE_PURPOSE

async def handle_add_expense_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    purpose = update.message.text.strip()
    context.user_data["expense_purpose"] = purpose
    await update.message.reply_text("💸 *Enter the expense amount:*", parse_mode="Markdown")
    return ADD_EXPENSE_AMOUNT

async def handle_add_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_str = update.message.text.strip()
    if not amount_str.isdigit():
        await update.message.reply_text("⚠️ Invalid amount! Please enter digits only (e.g., 250):")
        return ADD_EXPENSE_AMOUNT

    purpose = context.user_data["expense_purpose"]
    amount = int(amount_str)

    data = load_data()
    data["expenses"].append({"purpose": purpose, "amount": amount})
    save_data(data)

    total_spent = sum(e["amount"] for e in data["expenses"])
    total_coll = sum(data["collections"].values())
    balance = total_coll - total_spent

    await update.message.reply_text(
        f"✅ *Expense Recorded Successfully!*\n\n"
        f"🔸 Purpose: {purpose}\n"
        f"💸 Amount: ₹{amount}\n"
        f"📉 Total Spent: ₹{total_spent}\n"
        f"🟢 Remaining Balance: ₹{balance}",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    await show_admin_buttons(update, context)
    return ConversationHandler.END

# ---------- Edit Records Flow ----------

async def handle_edit_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = load_data()
    collections = data.get("collections", {})
    expenses = data.get("expenses", [])

    if not collections and not expenses:
        await query.edit_message_text("❌ No records available to edit.")
        return ConversationHandler.END

    keyboard = []
    if collections:
        for day in sorted(collections.keys()):
            keyboard.append([
                InlineKeyboardButton(
                    f"📅 Day {day}: ₹{collections[day]}",
                    callback_data=f"editcol_{day}"
                )
            ])

    if expenses:
        for idx, exp in enumerate(expenses):
            keyboard.append([
                InlineKeyboardButton(
                    f"💸 {exp['purpose']}: ₹{exp['amount']}",
                    callback_data=f"editexp_{idx}"
                )
            ])

    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")])

    await query.edit_message_text(
        "🔧 *Select any record below to edit:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return EDIT_RECORD_SELECT

async def select_collection_to_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    day = query.data.replace("editcol_", "")
    data = load_data()
    current_amount = data["collections"].get(day, 0)

    context.user_data["edit_old_day"] = day
    context.user_data["edit_old_amount"] = current_amount

    await query.edit_message_text(
        f"📅 Editing Collection: *Day {day}* (₹{current_amount})\n\n"
        f"Enter the *New Day/Date* (or send `{day}` to keep it unchanged):",
        parse_mode="Markdown",
    )
    return EDIT_COLL_DAY

async def edit_collection_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_day = update.message.text.strip()
    context.user_data["edit_new_day"] = new_day
    old_amount = context.user_data.get("edit_old_amount", 0)

    await update.message.reply_text(
        f"💰 Enter the *New Amount* (Current is ₹{old_amount}):",
        parse_mode="Markdown",
    )
    return EDIT_COLL_AMOUNT

async def edit_collection_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_str = update.message.text.strip()
    if not amount_str.isdigit():
        await update.message.reply_text("⚠️ Please enter a valid numerical amount:")
        return EDIT_COLL_AMOUNT

    new_day = context.user_data["edit_new_day"]
    old_day = context.user_data["edit_old_day"]
    new_amount = int(amount_str)

    data = load_data()
    if old_day in data["collections"] and old_day != new_day:
        del data["collections"][old_day]

    data["collections"][new_day] = new_amount
    save_data(data)

    await update.message.reply_text(
        f"✅ *Collection Updated!*\n\n"
        f"📅 Day: {new_day}\n"
        f"💰 Amount: ₹{new_amount}",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    await show_admin_buttons(update, context)
    return ConversationHandler.END

async def select_expense_to_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    idx = int(query.data.replace("editexp_", ""))
    data = load_data()
    exp = data["expenses"][idx]

    context.user_data["edit_exp_idx"] = idx
    context.user_data["edit_exp_old_purpose"] = exp["purpose"]
    context.user_data["edit_exp_old_amount"] = exp["amount"]

    await query.edit_message_text(
        f"💸 Editing Expense: *{exp['purpose']}* (₹{exp['amount']})\n\n"
        f"Enter the *New Purpose* (or send `{exp['purpose']}` to keep it unchanged):",
        parse_mode="Markdown",
    )
    return EDIT_EXP_PURPOSE

async def edit_expense_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_purpose = update.message.text.strip()
    context.user_data["edit_new_purpose"] = new_purpose
    old_amount = context.user_data.get("edit_exp_old_amount", 0)

    await update.message.reply_text(
        f"💸 Enter the *New Amount* (Current is ₹{old_amount}):",
        parse_mode="Markdown",
    )
    return EDIT_EXP_AMOUNT

async def edit_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_str = update.message.text.strip()
    if not amount_str.isdigit():
        await update.message.reply_text("⚠️ Please enter a valid numerical amount:")
        return EDIT_EXP_AMOUNT

    idx = context.user_data["edit_exp_idx"]
    new_purpose = context.user_data["edit_new_purpose"]
    new_amount = int(amount_str)

    data = load_data()
    if 0 <= idx < len(data["expenses"]):
        data["expenses"][idx] = {"purpose": new_purpose, "amount": new_amount}
        save_data(data)

    await update.message.reply_text(
        f"✅ *Expense Updated!*\n\n"
        f"🔸 Purpose: {new_purpose}\n"
        f"💸 Amount: ₹{new_amount}",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    await show_admin_buttons(update, context)
    return ConversationHandler.END

# ---------- Show Fund Data ----------

async def send_fund_summary(chat_id, context: ContextTypes.DEFAULT_TYPE, query=None):
    data = load_data()
    collections = data.get("collections", {})
    expenses = data.get("expenses", [])

    total_collected = sum(collections.values())
    total_spent = sum(e["amount"] for e in expenses)
    balance = total_collected - total_spent

    text = "📊 *Vinayaka Chavithi Fund Status* 📊\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"

    text += "💰 *Collections (Day wise):*\n"
    if collections:
        try:
            sorted_days = sorted(collections.keys(), key=lambda x: int(x) if x.isdigit() else str(x))
        except Exception:
            sorted_days = sorted(collections.keys())

        for day in sorted_days:
            text += f"   📅 Day {day}: ₹{collections[day]}\n"
    else:
        text += "   Ippudu varaku emi collect avvaledu\n"

    text += f"\n   ✅ *Total Collected: ₹{total_collected}*\n"

    text += "\n💸 *Expenses:*\n"
    if expenses:
        for e in expenses:
            text += f"   🔸 {e['purpose']}: ₹{e['amount']}\n"
    else:
        text += "   Ippudu varaku expenses ledu\n"

    text += f"\n   ❌ *Total Spent: ₹{total_spent}*\n"
    text += "\n━━━━━━━━━━━━━━━━━━\n"

    if balance >= 0:
        text += f"🟢 *Balance: ₹{balance}*"
    else:
        text += f"🔴 *Overspent by: ₹{abs(balance)}*"

    if query:
        try:
            await query.edit_message_text(text, parse_mode="Markdown")
        except BadRequest:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

async def show_fund_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await send_fund_summary(update.effective_chat.id, context, query=query)

async def fund_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_fund_summary(update.effective_chat.id, context)

async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Action cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

# ---------- Start Command ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.effective_user.id == ADMIN_ID:
        await show_admin_buttons(update, context)
    else:
        await show_user_button(update, context)

async def set_menu_commands(application: Application):
    """Sets the Telegram blue Menu button beside the input bar."""
    commands = [
        BotCommand("start", "Open Main Menu"),
        BotCommand("fund", "Check Fund Status"),
    ]
    await application.bot.set_my_commands(commands)

async def error_handler(update, context):
    if isinstance(context.error, TimedOut):
        pass
    else:
        logging.error(f"Error: {context.error}")

# ---------- Main Application ----------

def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(set_menu_commands)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_add_fund, pattern="^add_fund$"),
            CallbackQueryHandler(handle_add_expense, pattern="^add_expense$"),
            CallbackQueryHandler(handle_edit_data, pattern="^edit_data$"),
        ],
        states={
            ADD_FUND_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_fund_date)],
            ADD_FUND_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_fund_amount)],
            ADD_EXPENSE_PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_expense_purpose)],
            ADD_EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_expense_amount)],
            EDIT_RECORD_SELECT: [
                CallbackQueryHandler(select_collection_to_edit, pattern="^editcol_"),
                CallbackQueryHandler(select_expense_to_edit, pattern="^editexp_"),
            ],
            EDIT_COLL_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_collection_day)],
            EDIT_COLL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_collection_amount)],
            EDIT_EXP_PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_expense_purpose)],
            EDIT_EXP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_expense_amount)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_action, pattern="^cancel_action$"),
            CommandHandler("start", start),
        ],
        per_chat=True,
        per_user=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fund", fund_command))
    app.add_handler(admin_conv)
    app.add_handler(CallbackQueryHandler(show_fund_data, pattern="^fund_data$"))
    app.add_handler(CallbackQueryHandler(cancel_action, pattern="^cancel_action$"))

    app.add_error_handler(error_handler)

    print("🤖 Bot running cleanly in Termux... Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
