from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackContext, ConversationHandler, filters
)
import matplotlib.pyplot as plt
from io import BytesIO
from database import db

AMOUNT, CATEGORY = range(2)

# Общая клавиатура для отмены
cancel_markup = ReplyKeyboardMarkup([['/cancel']], resize_keyboard=True, one_time_keyboard=True)


async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    db.add_user(user.id, user.first_name, user.username)

    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот для учета финансов. Вот что я умею:\n\n"
        "➕ Добавить расход: /expense\n"
        "➕ Добавить доход: /income\n"
        "📊 Статистика: /stats\n"
        "📁 Экспорт данных: /export\n\n"
        "💡 Просто введите команду и следуйте инструкциям",
        parse_mode="HTML"
    )


async def expense_command(update: Update, context: CallbackContext) -> int:
    context.user_data['is_income'] = False
    await update.message.reply_text(
        "💰 Введите сумму расхода:",
        reply_markup=cancel_markup
    )
    return AMOUNT


async def income_command(update: Update, context: CallbackContext) -> int:
    context.user_data['is_income'] = True
    await update.message.reply_text(
        "💰 Введите сумму дохода:",
        reply_markup=cancel_markup
    )
    return AMOUNT


async def amount_received(update: Update, context: CallbackContext) -> int:
    try:
        amount = float(update.message.text)
        context.user_data['amount'] = amount

        if context.user_data.get('is_income', False):
            db.add_transaction(update.effective_user.id, amount, None, True)
            await update.message.reply_text(
                f"✅ Доход {amount:.2f}₽ сохранен!",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

        await update.message.reply_text(
            "📝 Введите категорию расхода (например: еда, транспорт):",
            reply_markup=cancel_markup
        )
        return CATEGORY
    except ValueError:
        await update.message.reply_text(
            "🚫 Пожалуйста, введите корректную сумму (число)",
            reply_markup=cancel_markup
        )
        return AMOUNT


async def category_received(update: Update, context: CallbackContext) -> int:
    category = update.message.text.lower()
    amount = context.user_data['amount']

    db.add_transaction(update.effective_user.id, amount, category, False)

    await update.message.reply_text(
        f"✅ Расход {amount:.2f}₽ на '{category}' сохранен!",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "❌ Операция отменена",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def show_stats(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    periods = {
        'current_month': 'Текущий месяц',
        'last_month': 'Прошлый месяц',
        'last_30_days': '30 дней',
        'last_12_months': '12 месяцев',
        'all': 'Все время'
    }

    stats_messages = []
    for period, name in periods.items():
        stats = db.get_stats(user_id, period)

        if not stats['total_income'] and not stats['total_expense']:
            continue

        message = (
            f"📊 <b>{name}</b>\n"
            f"Доходы: {stats['total_income']:.2f}₽\n"
            f"Расходы: {stats['total_expense']:.2f}₽\n"
            f"Баланс: {stats['total_income'] - stats['total_expense']:.2f}₽\n"
        )
        stats_messages.append(message)

    if not stats_messages:
        await update.message.reply_text("📭 Нет данных для отображения")
        return

    stats = db.get_stats(user_id, 'last_30_days')
    if stats['categories_expense']:
        plt.figure(figsize=(8, 6))
        plt.pie(
            stats['categories_expense'].values(),
            labels=stats['categories_expense'].keys(),
            autopct='%1.1f%%'
        )
        plt.title('Расходы по категориям (30 дней)')

        buf = BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)

        await update.message.reply_photo(
            photo=buf,
            caption='\n'.join(stats_messages),
            parse_mode="HTML"
        )
        plt.close()
    else:
        await update.message.reply_text('\n'.join(stats_messages), parse_mode="HTML")


async def export_data(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    csv_data = db.export_to_csv(user_id)

    if not csv_data:
        await update.message.reply_text("📭 Нет данных для экспорта")
        return

    await update.message.reply_document(
        document=InputFile(BytesIO(csv_data.encode()), filename='transactions.csv'),
        caption="📁 Ваши транзакции в CSV"
    )


def main() -> None:
    token = "7759417622:AAGX-4NM1fWN1qEcFFo605Q7f9435BlQ-00"
    application = Application.builder().token(token).build()

    expense_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('expense', expense_command)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_received)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_received)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True
    )

    income_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('income', income_command)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_received)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(expense_conv_handler)
    application.add_handler(income_conv_handler)
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("export", export_data))

    application.run_polling()
    print("Бот запущен! 🚀")


if __name__ == '__main__':
    main()
