from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import uuid
import logging
import settings
import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_db_connection():
    return psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD
    )


def is_authorized(user_id: int) -> bool:
    return user_id in settings.AUTHORIZED_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        logger.warning(f"Unauthorized access attempt by user {user_id}")
        await update.message.reply_text(f"You don't have permission for this bot. Your Telegram ID: {user_id}")
        return

    logger.info(f"User {user_id} successfully authorized.")
    await update.message.reply_text(
        "Successful authorization. You can send an: Payment ID, Merchant ID, User (client) ID in merchant's system, Payment (order) ID in merchant's system or Payment ID in provider's system to retrieve payment information."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        logger.warning(f"Unauthorized message from user {user_id}")
        await update.message.reply_text(
            f"You don't have permission to use this bot. Please provide your Telegram ID: {user_id}")
        return

    user_message = update.message.text.strip()
    logger.info(f"Received message from {user_id}: {user_message}")

    is_uuid = False

    try:
        uuid.UUID(user_message)
        is_uuid = True
    except ValueError:
        is_uuid = False

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if is_uuid:
            query = """
            SELECT p.id AS transaction_id, 
                   p.merchants_user_id AS customer_id, 
                   p.amount, 
                   p.amount_account, 
                   p.status, 
                   p.merchant_id, 
                   m.name AS merchant_name, 
                   p.merchants_payment_id, 
                   p.integrations_payment_id, 
                   p.created_at, 
                   p.updated_at
            FROM payments p
            LEFT JOIN merchants m ON p.merchant_id = m.id
            WHERE p.id = %s OR p.merchant_id = %s OR p.merchants_user_id = %s OR p.merchants_payment_id = %s OR p.integrations_payment_id = %s
            ORDER BY p.created_at DESC
            LIMIT 5
            """
            cursor.execute(query, (
                str(user_message), str(user_message), str(user_message), str(user_message), str(user_message)))
        else:
            query = """
            SELECT p.id AS transaction_id, 
                   p.merchants_user_id AS customer_id, 
                   p.amount, 
                   p.amount_account, 
                   p.status, 
                   p.merchant_id, 
                   m.name AS merchant_name, 
                   p.merchants_payment_id, 
                   p.integrations_payment_id, 
                   p.created_at, 
                   p.updated_at
            FROM payments p
            LEFT JOIN merchants m ON p.merchant_id = m.id
            WHERE p.merchants_user_id = %s OR p.merchants_payment_id = %s OR p.integrations_payment_id = %s
            ORDER BY p.created_at DESC
            LIMIT 5
            """
            cursor.execute(query, (user_message, user_message, user_message))

        results = cursor.fetchall()

        if results:
            response = "Last 5 records:\n"
            for idx, result in enumerate(results, start=1):
                merchant_name = result[6] or "no data"
                merchants_payment_id = result[7] or "no data"
                integrations_payment_id = result[8] or "no data"
                transaction_id = result[0] or "no data"
                customer_id = result[1] or "no data"
                amount = result[2] or "no data"
                final_amount = result[3] or "no data"
                status = result[4] or "no data"
                created_at = result[9].strftime('%Y-%m-%d %H:%M:%S') if result[9] else "no data"
                updated_at = result[10].strftime('%Y-%m-%d %H:%M:%S') if result[10] else "no data"

                response += (
                    f"\nRecord {idx}:\n"
                    f"Merchant Name: {merchant_name}\n"
                    f"Merchants Payment ID: {merchants_payment_id}\n"
                    f"Integrations Payment ID: {integrations_payment_id}\n"
                    f"Transaction ID: {transaction_id}\n"
                    f"Customer ID: {customer_id}\n"
                    f"Sum: {amount}\n"
                    f"Final Sum: {final_amount}\n"
                    f"Status: {status}\n"
                    f"Created At: {created_at}\n"
                    f"Updated At: {updated_at}\n"
                )
        else:
            response = "No matching records found for the provided ID."

        await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Database error: {e}")
        await update.message.reply_text("An error occurred while processing your request. Please try again later.")
    finally:
        try:
            if conn:
                conn.close()
        except NameError:
            logger.warning("Connection was not established, nothing to close.")


def main():
    application = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is starting...")
    application.run_polling()


if __name__ == "__main__":
    load_dotenv()
    main()
