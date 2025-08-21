from flask import Flask, request
import os
import base64
import asyncio
import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding

# --- Secrets & Config ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
PRIVATE_KEY_PEM = os.environ.get("PRIVATE_KEY_PEM")
PAYMENT_INSTRUCTIONS = """Please send **$19.99** to:\n\n**GPay / UPI:** `your-upi-id@okhdfcbank`\n\nAfter paying, send the confirmation screenshot to this chat."""

# --- Initialize Cryptography ---
private_key = None
if PRIVATE_KEY_PEM:
    try:
        private_key = serialization.load_pem_private_key(PRIVATE_KEY_PEM.encode(), password=None)
    except Exception as e:
        print(f"FATAL: Could not load private key: {e}")

def create_license(data_to_sign):
    if not private_key: raise ValueError("Private key not loaded")
    message = data_to_sign.encode('utf-8')
    signature = private_key.sign(
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256()
    )
    return f"{data_to_sign}::{base64.b64encode(signature).decode('utf-8')}"

# --- Bot Handlers (async) ---
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Welcome! To get your Ankard PRO license, please follow these steps:")
    await update.message.reply_text(PAYMENT_INSTRUCTIONS, parse_mode=telegram.ParseMode.MARKDOWN)

async def handle_screenshot(update: Update, context: CallbackContext):
    if not ADMIN_CHAT_ID: return
    user = update.message.from_user
    user_info = f"Screenshot from:\nUser: {user.full_name}\nID: `{user.id}`"
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=user_info, parse_mode=telegram.ParseMode.MARKDOWN)
    await context.bot.forward_message(chat_id=ADMIN_CHAT_ID, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
    await update.message.reply_text("Thanks! Your screenshot is being verified. You will receive your key shortly.")

async def approve(update: Update, context: CallbackContext):
    if str(update.message.from_user.id) != ADMIN_CHAT_ID: return
    try:
        target_user_id = context.args[0]
        license_key = create_license(target_user_id)
        await context.bot.send_message(chat_id=target_user_id, text="✅ Your payment is confirmed! Here is your Ankard PRO license key:")
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"`{license_key}`",
            parse_mode=telegram.ParseMode.MARKDOWN_V2
        )
        await update.message.reply_text(f"License sent to user {target_user_id}.")
    except IndexError:
        await update.message.reply_text("Usage: /approve <user_id>")
    except Exception as e:
        await update.message.reply_text(f"Error approving license: {e}")

# --- Vercel Entry Point with Flask ---
app = Flask(__name__)

# Initialize the Telegram bot application
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("approve", approve))
application.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))

@app.route('/', methods=['POST', 'GET'])
def webhook():
    # This function now handles both the webhook and a simple "Hello World" test
    if request.method == 'POST':
        try:
            # The asyncio.run() call is the key to making this work in Flask on Vercel
            asyncio.run(application.process_update(
                Update.de_json(request.get_json(force=True), application.bot)
            ))
        except Exception as e:
            print(f"Error processing update: {e}")
            return "Error", 500
        return "Ok", 200
    else:
        # This is for the browser test
        return "<h1>Success! Your Vercel server is running the bot code.</h1>"
    