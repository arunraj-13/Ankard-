# api/index.py
from flask import Flask, request, jsonify
import os
import base64
import telegram
from telegram import Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding

# --- Load Secrets from Environment Variables ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID") # Your personal Telegram Chat ID
PRIVATE_KEY_PEM = os.environ.get("PRIVATE_KEY_PEM")
WEBHOOK_URL = os.environ.get("VERCEL_URL")

# --- Payment Information (Customize This) ---
PAYMENT_INSTRUCTIONS = """
Please send **$19.99** to one of the following:

**GPay / UPI:** `your-upi-id@okhdfcbank`

After payment, please send a screenshot of the confirmation message to this chat. I will verify it and send your license key.
"""

# Initialize bot and dispatcher
bot = telegram.Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)
app = Flask(__name__)

# Load private key for license generation
if PRIVATE_KEY_PEM:
    private_key = serialization.load_pem_private_key(PRIVATE_KEY_PEM.encode(), password=None)
else:
    private_key = None

def create_license(data_to_sign):
    if not private_key: raise ValueError("Private key is not loaded.")
    message = data_to_sign.encode('utf-8')
    signature = private_key.sign(
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256()
    )
    return f"{data_to_sign}::{base64.b64encode(signature).decode('utf-8')}"

# --- Bot Command Handlers ---

# For regular users
def start(update: Update, context):
    """Handler for the /start command. Sends payment info."""
    update.message.reply_text(
        "Welcome to the Ankard PRO Bot! Here is how to get your license key:"
    )
    update.message.reply_text(
        PAYMENT_INSTRUCTIONS,
        parse_mode=telegram.ParseMode.MARKDOWN
    )

def handle_screenshot(update: Update, context):
    """Forwards a user's screenshot to the admin for verification."""
    if not ADMIN_CHAT_ID:
        print("ERROR: ADMIN_CHAT_ID not set. Cannot forward screenshot.")
        return
    
    user = update.message.from_user
    user_info = f"Payment screenshot from:\nUser: {user.full_name}\nUsername: @{user.username}\nUser ID: `{user.id}`"
    
    context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=user_info,
        parse_mode=telegram.ParseMode.MARKDOWN
    )
    
    # Forward the actual photo
    context.bot.forward_message(
        chat_id=ADMIN_CHAT_ID,
        from_chat_id=update.message.chat_id,
        message_id=update.message.message_id
    )
    
    update.message.reply_text("Thank you! Your screenshot has been sent for verification. Please allow some time for approval.")

# For the admin
def approve(update: Update, context):
    """Admin command to approve a payment and send a license key."""
    admin_id = str(update.message.from_user.id)
    
    if admin_id != ADMIN_CHAT_ID:
        update.message.reply_text("You are not authorized to use this command.")
        return

    # The command should be in the format: /approve USER_ID
    try:
        target_user_id = context.args[0]
    except (IndexError, ValueError):
        update.message.reply_text("Usage: `/approve [user_id]`\nPlease provide the User ID to approve.", parse_mode=telegram.ParseMode.MARKDOWN)
        return
        
    try:
        # 1. Generate the license key for the approved user
        license_key = create_license(target_user_id)
        
        # 2. Send the key to the user
        context.bot.send_message(
            chat_id=target_user_id,
            text="Your payment has been approved! Thank you for purchasing Ankard PRO."
        )
        context.bot.send_message(
            chat_id=target_user_id,
            text=f"Here is your license key:\n`{license_key}`",
            parse_mode=telegram.ParseMode.MARKDOWN_V2
        )
        
        # 3. Confirm to the admin that it was sent
        update.message.reply_text(f"✅ Success! License key sent to user {target_user_id}.")
        
    except Exception as e:
        print(f"ERROR during approval: {e}")
        update.message.reply_text(f"❌ Error: Could not process approval for user {target_user_id}. Check logs.")

# --- Flask Webhook Route ---
@app.route('/', methods=['POST'])
def webhook_handler():
    update = Update.deconstruct(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return jsonify({"status": "ok"})

# Set up the dispatcher
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("approve", approve))
dispatcher.add_handler(MessageHandler(Filters.photo, handle_screenshot))

# Set webhook on server startup
try:
    if WEBHOOK_URL and BOT_TOKEN:
        bot.set_webhook(f"https://{WEBHOOK_URL}/")
        print(f"Webhook set to https://{WEBHOOK_URL}/")
except Exception as e:
    print(f"Could not set webhook: {e}")