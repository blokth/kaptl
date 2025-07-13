import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PLAN_FILE = "plan.csv"
REGISTER_FILE = "register.csv"

def load_plan():
    if not os.path.exists(PLAN_FILE):
        df = pd.DataFrame(columns=["Month", "Category Group/Category", "Category Group", "Category", "Assigned", "Activity", "Available"])
        save_plan(df)
    return pd.read_csv(PLAN_FILE)

def save_plan(df):
    df.to_csv(PLAN_FILE, index=False)

def load_register():
    if not os.path.exists(REGISTER_FILE):
        df = pd.DataFrame(columns=["Account", "Flag", "Date", "Payee", "Category Group/Category", "Category Group", "Category", "Memo", "Outflow", "Inflow"])
        save_register(df)
    return pd.read_csv(REGISTER_FILE)

def save_register(df):
    df.to_csv(REGISTER_FILE, index=False)

def get_current_month_str():
    return datetime.now().strftime("%b %Y")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to the Expense Tracker Bot!\n\n"
        "Use /add <amount> <category> to add an expense.\n"
        "Use /income <amount> to add income to 'Ready to Assign'.\n"
        "Use /move <amount> <from_category> <to_category> to move money between categories.\n"
        "Use /overview to see a monthly summary.\n"
        "Use /categories to see all available categories."
    )

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(context.args[0])
        category = " ".join(context.args[1:])

        plan_df = load_plan()
        register_df = load_register()

        month_str = get_current_month_str()
        category_row = plan_df[(plan_df["Category"] == category) & (plan_df["Month"] == month_str)]

        if category_row.empty:
            await update.message.reply_text(f"Category '{category}' not found for the current month.")
            return

        # Update plan
        plan_df.loc[category_row.index, "Activity"] -= amount
        plan_df.loc[category_row.index, "Available"] -= amount
        save_plan(plan_df)

        # Add to register
        new_transaction = {
            "Account": "Cash",  # Assuming cash for simplicity
            "Date": datetime.now().strftime("%d/%m/%Y"),
            "Category Group": category_row.iloc[0]["Category Group"],
            "Category": category,
            "Outflow": f"{amount:.2f}€",
            "Inflow": "0.00€"
        }
        register_df = pd.concat([register_df, pd.DataFrame([new_transaction])], ignore_index=True)
        save_register(register_df)

        await update.message.reply_text(f"Expense of {amount} added to {category}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /add <amount> <category>")

async def add_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(context.args[0])
        plan_df = load_plan()
        register_df = load_register()
        month_str = get_current_month_str()

        # Update plan
        plan_df.loc[(plan_df["Category"] == "Ready to Assign") & (plan_df["Month"] == month_str), "Available"] += amount
        save_plan(plan_df)

        # Add to register
        new_transaction = {
            "Account": "Cash",
            "Date": datetime.now().strftime("%d/%m/%Y"),
            "Category Group": "Inflow",
            "Category": "Ready to Assign",
            "Outflow": "0.00€",
            "Inflow": f"{amount:.2f}€"
        }
        register_df = pd.concat([register_df, pd.DataFrame([new_transaction])], ignore_index=True)
        save_register(register_df)

        await update.message.reply_text(f"Income of {amount} added to 'Ready to Assign'.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /income <amount>")

async def move_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(context.args[0])
        from_category = context.args[1]
        to_category = context.args[2]

        plan_df = load_plan()
        month_str = get_current_month_str()

        from_row = plan_df[(plan_df["Category"] == from_category) & (plan_df["Month"] == month_str)]
        to_row = plan_df[(plan_df["Category"] == to_category) & (plan_df["Month"] == month_str)]

        if from_row.empty or to_row.empty:
            await update.message.reply_text("Invalid category for the current month.")
            return

        plan_df.loc[from_row.index, "Available"] -= amount
        plan_df.loc[to_row.index, "Available"] += amount
        save_plan(plan_df)

        await update.message.reply_text(f"Moved {amount} from {from_category} to {to_category}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /move <amount> <from> <to>")

async def overview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_df = load_plan()
    month_str = get_current_month_str()
    month_plan = plan_df[plan_df["Month"] == month_str]

    if month_plan.empty:
        await update.message.reply_text("No data for the current month.")
        return

    message = f"**Overview for {month_str}**\n\n"
    for index, row in month_plan.iterrows():
        message += f"**{row["Category Group"]}: {row["Category"]}**\n"
        message += f"  - Assigned: {row["Assigned"]}\n"
        message += f"  - Activity: {row["Activity"]}\n"
        message += f"  - Available: {row["Available"]}\n\n"

    await update.message.reply_text(message, parse_mode="Markdown")

async def categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_df = load_plan()
    month_str = get_current_month_str()
    month_plan = plan_df[plan_df["Month"] == month_str]

    if month_plan.empty:
        await update.message.reply_text("No categories found for the current month.")
        return

    message = "**Available Categories:**\n\n"
    for group in month_plan["Category Group"].unique():
        message += f"**{group}**\n"
        for cat in month_plan[month_plan["Category Group"] == group]["Category"]:
            message += f"  - {cat}\n"

    await update.message.reply_text(message, parse_mode="Markdown")

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "See the welcome message"),
        BotCommand("add", "Add a new expense"),
        BotCommand("income", "Add a new income"),
        BotCommand("move", "Move money between categories"),
        BotCommand("overview", "Get a monthly overview"),
        BotCommand("categories", "See all available categories"),
    ])

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_expense))
    app.add_handler(CommandHandler("income", add_income))
    app.add_handler(CommandHandler("move", move_money))
    app.add_handler(CommandHandler("overview", overview))
    app.add_handler(CommandHandler("categories", categories))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
