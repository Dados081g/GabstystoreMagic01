import asyncio
import sqlite3

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    MessageEntity,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ======================= НАСТРОЙКИ =======================

BOT_TOKEN = "ВАШ_ТОКЕН_ЗДЕСЬ"          # токен от @BotFather
ADMIN_ID = 123456789                   # ваш Telegram ID (узнать можно у @userinfobot)
ADMIN_PASSWORD = "maksumtop1"          # пароль для входа в /admin
CARD_NUMBER = "2202 2083 0536 9622"
CHANNEL_LINK = "https://t.me/+0D3hMBZtdcc3Y2Uy"
REVIEWS_CHANNEL = "@gabstystoreotzivi"  # бот должен быть админом этого канала с правом постить

PRIVACY_POLICY = (
    "📄 Политика конфиденциальности\n\n"
    "1. Какие данные мы собираем\n"
    "Мы сохраняем ваш Telegram ID, историю заказов (категория, сумма, статус) "
    "и файл присланного вами чека об оплате.\n\n"
    "2. Зачем это нужно\n"
    "Эти данные используются только для обработки заказа: проверки оплаты, "
    "выдачи ключа и связи с вами по вопросам покупки.\n\n"
    "3. Хранение и передача данных\n"
    "Данные хранятся на сервере бота и не передаются третьим лицам, кроме случаев, "
    "предусмотренных законодательством.\n\n"
    "4. Рассылки\n"
    "Мы можем присылать вам сообщения о статусе заказа и редкие объявления, "
    "связанные с работой магазина.\n\n"
    "5. Удаление данных\n"
    "Чтобы удалить свои данные, напишите в поддержку — запрос будет обработан "
    "в разумный срок.\n\n"
    "Используя бота, вы соглашаетесь с этой политикой."
)

USER_AGREEMENT = (
    "📜 Пользовательское соглашение\n\n"
    "1. Общие положения\n"
    "Используя этого бота, вы подтверждаете, что ознакомились и согласны "
    "с условиями данного соглашения.\n\n"
    "2. Предмет соглашения\n"
    "Бот предоставляет доступ к покупке цифровых товаров (ключей) за указанную "
    "в карточке товара стоимость.\n\n"
    "3. Порядок оплаты\n"
    "Оплата производится переводом на указанные реквизиты. После оплаты необходимо "
    "прислать чек в этот чат для подтверждения администратором.\n\n"
    "4. Выдача товара\n"
    "После подтверждения оплаты администратором ключ выдаётся автоматически в этом чате.\n\n"
    "5. Возврат средств\n"
    "Поскольку товар является цифровым и выдаётся сразу после подтверждения оплаты, "
    "возврат средств возможен только в случае, если ключ оказался нерабочим — "
    "в этом случае обратитесь в поддержку.\n\n"
    "6. Ответственность\n"
    "Администрация не несёт ответственности за ошибки, допущенные пользователем "
    "при переводе средств (неверные реквизиты, недостаточная сумма и т.д.).\n\n"
    "7. Изменения соглашения\n"
    "Администрация вправе изменять условия соглашения; актуальная версия всегда "
    "доступна по команде /agreement."
)

# ID премиум-эмодзи
EMOJI_GIFT = "5983580310292402968"     # 🎁 в приветствии
EMOJI_BELL = "5773677501825945508"     # 🔔 в приветствии
EMOJI_CATEGORY = "5890883384057533697" # 🛍 "Выберите категорию"
EMOJI_CRY4ME = "5294524383279198295"   # 😢 рядом с cry4me в списке категорий
EMOJI_PRODUCT = "5413477410962174963"  # 😭 в карточке товара
EMOJI_OXIDE = "6037083366438737901"    # 🧊 рядом с oxide в списке категорий

DB_PATH = "shop.db"

# ======================= БАЗА ДАННЫХ =======================


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            key_value TEXT NOT NULL,
            is_used INTEGER DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            price TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            receipt_file_id TEXT,
            receipt_type TEXT,
            key_value TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.commit()
    conn.close()


# ======================= ПОМОЩНИК ДЛЯ ПРЕМИУМ-ЭМОДЗИ =======================


def utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def emoji_entity(text: str, placeholder: str, emoji_id: str) -> MessageEntity:
    idx = text.index(placeholder)
    offset = utf16_len(text[:idx])
    length = utf16_len(placeholder)
    return MessageEntity(
        type="custom_emoji", offset=offset, length=length, custom_emoji_id=emoji_id
    )


# ======================= FSM СОСТОЯНИЯ =======================


class AdminStates(StatesGroup):
    waiting_password = State()
    waiting_add_key = State()
    waiting_broadcast = State()


class ReviewStates(StatesGroup):
    waiting_text = State()


# ======================= КЛАВИАТУРЫ =======================

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Категория")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="📢 Наш канал")],
    ],
    resize_keyboard=True,
)


def rating_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐" * n, callback_data=f"rate_{order_id}_{n}")
                for n in range(1, 6)
            ]
        ]
    )

# Товары/категории. Порядок в словаре = порядок в списке "Выберите категорию".
PRODUCTS = {
    "cry4me": {
        "list_char": "😢",
        "list_emoji": EMOJI_CRY4ME,
        "name": "cry4me 1D",
        "price": "160 руб",
        "product_char": "😭",
        "product_emoji": EMOJI_PRODUCT,
    },
}

ADMIN_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🧾 Чеки", callback_data="admin_receipts")],
        [InlineKeyboardButton(text="➕ Добавить ключи", callback_data="admin_add_keys")],
        [InlineKeyboardButton(text="📦 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="📢 Сделать объявление", callback_data="admin_broadcast")],
    ]
)

# ======================= ПОЛЬЗОВАТЕЛЬСКИЙ РОУТЕР =======================

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    conn = db()
    conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()

    text = (
        "🎁 Привет!\n\n"
        "Спасибо, что решили воспользоваться нашим магазином.\n\n"
        "🔔 Если у вас есть вопросы или проблемы с товаром — напишите в поддержку.\n\n"
        "Перед началом использования бота ознакомьтесь с политикой конфиденциальности "
        "и пользовательским соглашением."
    )
    entities = [
        emoji_entity(text, "🎁", EMOJI_GIFT),
        emoji_entity(text, "🔔", EMOJI_BELL),
    ]
    await message.answer(text, entities=entities, reply_markup=MAIN_KB)


@router.message(F.text == "Категория")
async def show_categories(message: Message):
    lines = ["🛍 Выберите категорию:", ""]
    for key, p in PRODUCTS.items():
        lines.append(f"{p['list_char']} {key}")
    text = "\n".join(lines)

    entities = [emoji_entity(text, "🛍", EMOJI_CATEGORY)]
    for key, p in PRODUCTS.items():
        entities.append(emoji_entity(text, p["list_char"], p["list_emoji"]))

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=key, callback_data=f"cat_{key}")] for key in PRODUCTS
        ]
    )
    await message.answer(text, entities=entities, reply_markup=kb)


@router.message(F.text == "👤 Профиль")
async def profile(message: Message):
    conn = db()
    count = conn.execute(
        "SELECT COUNT(*) as c FROM orders WHERE user_id = ? AND status = 'completed'",
        (message.from_user.id,),
    ).fetchone()["c"]
    conn.close()
    await message.answer(f"👤 Ваш профиль\n\nКуплено ключей: {count}")


@router.message(F.text == "📢 Наш канал")
async def our_channel(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Открыть канал", url=CHANNEL_LINK)]]
    )
    await message.answer("Наш канал:", reply_markup=kb)


@router.callback_query(F.data.startswith("cat_"))
async def show_product(callback: CallbackQuery):
    key = callback.data.split("_", 1)[1]
    p = PRODUCTS.get(key)
    if not p:
        await callback.answer("Товар недоступен", show_alert=True)
        return

    text = f"{p['product_char']} {p['name']} — {p['price']}"
    entities = [emoji_entity(text, p["product_char"], p["product_emoji"])]
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🛒 Купить", callback_data=f"buy_{key}")]]
    )
    await callback.message.edit_text(text, entities=entities, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    key = callback.data.split("_", 1)[1]
    p = PRODUCTS.get(key)
    if not p:
        await callback.answer("Товар недоступен", show_alert=True)
        return

    user_id = callback.from_user.id
    conn = db()
    conn.execute(
        "INSERT INTO orders (user_id, category, price, status) VALUES (?, ?, ?, 'pending')",
        (user_id, key, p["price"]),
    )
    conn.commit()
    conn.close()

    text = (
        f"Переведите на данные реквизиты:\n\n"
        f"💳 {CARD_NUMBER}\n\n"
        f"После оплаты пришлите сюда чек (фото или файл)."
    )
    await callback.message.answer(text)
    await callback.answer()


@router.message(F.photo | F.document)
async def receive_receipt(message: Message):
    user_id = message.from_user.id
    conn = db()
    order = conn.execute(
        "SELECT * FROM orders WHERE user_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if not order:
        conn.close()
        return  # нет ожидающего заказа — игнорируем

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    receipt_type = "photo" if message.photo else "document"
    conn.execute(
        "UPDATE orders SET receipt_file_id = ?, receipt_type = ?, status = 'awaiting_confirmation' WHERE id = ?",
        (file_id, receipt_type, order["id"]),
    )
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{order['id']}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order['id']}"),
            ]
        ]
    )
    caption = (
        f"🧾 Новый чек по заказу #{order['id']}\n"
        f"Пользователь: {user_id}\n"
        f"Категория: {order['category']}\n"
        f"Сумма: {order['price']}"
    )
    if message.photo:
        await message.bot.send_photo(ADMIN_ID, file_id, caption=caption, reply_markup=kb)
    else:
        await message.bot.send_document(ADMIN_ID, file_id, caption=caption, reply_markup=kb)

    await message.answer("⏳ Подождите, пока подтвердится оплата")


@router.callback_query(F.data.startswith("approve_"))
async def approve_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Недоступно", show_alert=True)
        return

    order_id = int(callback.data.split("_", 1)[1])
    conn = db()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order or order["status"] != "awaiting_confirmation":
        conn.close()
        await callback.answer("Заказ уже обработан", show_alert=True)
        return

    key_row = conn.execute(
        "SELECT * FROM keys WHERE category = ? AND is_used = 0 LIMIT 1", (order["category"],)
    ).fetchone()
    if not key_row:
        conn.close()
        await callback.answer("Нет свободных ключей! Добавьте через /admin", show_alert=True)
        return

    conn.execute("UPDATE keys SET is_used = 1 WHERE id = ?", (key_row["id"],))
    conn.execute(
        "UPDATE orders SET status = 'completed', key_value = ? WHERE id = ?",
        (key_row["key_value"], order_id),
    )
    conn.commit()
    conn.close()

    await callback.bot.send_message(
        order["user_id"],
        f"✅ Оплата подтверждена!\nВаш ключ: <code>{key_row['key_value']}</code>",
        parse_mode="HTML",
    )
    await callback.bot.send_message(
        order["user_id"],
        "🙏 Спасибо за покупку! Оцените нас от 1 до 5 звёзд:",
        reply_markup=rating_kb(order_id),
    )
    if callback.message.caption:
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ Подтверждено")
    await callback.answer("Ключ выдан")


@router.callback_query(F.data.startswith("rate_"))
async def rate_order(callback: CallbackQuery, state: FSMContext):
    _, order_id, rating = callback.data.split("_")
    await state.update_data(review_order_id=int(order_id), review_rating=int(rating))
    await state.set_state(ReviewStates.waiting_text)
    await callback.message.edit_text(
        f"Ваша оценка: {'⭐' * int(rating)}\n\nНапишите текст отзыва:"
    )
    await callback.answer()


@router.message(ReviewStates.waiting_text)
async def save_review(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("review_order_id")
    rating = data.get("review_rating", 5)
    await state.clear()

    stars = "⭐" * rating + "☆" * (5 - rating)
    username = (
        f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    )
    text = f"📝 Новый отзыв (заказ #{order_id})\n\n{stars}\n\n{message.text}\n\n— {username}"

    try:
        await message.bot.send_message(REVIEWS_CHANNEL, text)
        await message.answer("Спасибо за отзыв! ❤️")
    except Exception:
        await message.answer("Не получилось отправить отзыв в канал. Попробуйте позже.")


@router.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Недоступно", show_alert=True)
        return

    order_id = int(callback.data.split("_", 1)[1])
    conn = db()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order and order["status"] == "awaiting_confirmation":
        conn.execute("UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))
        conn.commit()
    conn.close()

    if order:
        await callback.bot.send_message(order["user_id"], "❌ Чек не подтверждён. Свяжитесь с поддержкой.")
    if callback.message.caption:
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ Отклонено")
    await callback.answer("Заказ отклонён")


# ======================= АДМИН-РОУТЕР =======================

admin_router = Router()


@admin_router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await message.answer("Введите пароль:")
    await state.set_state(AdminStates.waiting_password)


@admin_router.message(AdminStates.waiting_password)
async def check_password(message: Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        await state.clear()
        await message.answer("Добро пожаловать в админ-панель:", reply_markup=ADMIN_MENU)
    else:
        await message.answer("Неверный пароль.")
        await state.clear()


@admin_router.callback_query(F.data == "admin_receipts")
async def admin_receipts(callback: CallbackQuery):
    conn = db()
    orders = conn.execute(
        "SELECT * FROM orders WHERE status = 'awaiting_confirmation' ORDER BY id"
    ).fetchall()
    conn.close()

    if not orders:
        await callback.message.answer("Нет чеков на проверке.")
        await callback.answer()
        return

    for order in orders:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{order['id']}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order['id']}"),
                ]
            ]
        )
        caption = (
            f"🧾 Заказ #{order['id']}\n"
            f"Пользователь: {order['user_id']}\n"
            f"Категория: {order['category']}\n"
            f"Сумма: {order['price']}"
        )
        if order["receipt_type"] == "photo":
            await callback.message.answer_photo(order["receipt_file_id"], caption=caption, reply_markup=kb)
        elif order["receipt_type"] == "document":
            await callback.message.answer_document(order["receipt_file_id"], caption=caption, reply_markup=kb)
        else:
            await callback.message.answer(caption, reply_markup=kb)

    await callback.answer()


@admin_router.callback_query(F.data == "admin_add_keys")
async def admin_add_keys_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Пришлите ключи в формате:\nкатегория|ключ\n(каждый ключ с новой строки)\n\n"
        "Например:\ncry4me|AAAA-BBBB-CCCC\ncry4me|DDDD-EEEE-FFFF"
    )
    await state.set_state(AdminStates.waiting_add_key)
    await callback.answer()


@admin_router.message(AdminStates.waiting_add_key)
async def admin_add_keys_save(message: Message, state: FSMContext):
    lines = [line.strip() for line in message.text.splitlines() if line.strip()]
    conn = db()
    added = 0
    for line in lines:
        if "|" not in line:
            continue
        category, key_value = line.split("|", 1)
        conn.execute(
            "INSERT INTO keys (category, key_value) VALUES (?, ?)",
            (category.strip(), key_value.strip()),
        )
        added += 1
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer(f"Добавлено ключей: {added}")


@admin_router.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    conn = db()
    orders = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()

    if not orders:
        await callback.message.answer("Заказов пока нет.")
    else:
        lines = [
            f"#{o['id']} | user {o['user_id']} | {o['category']} | {o['price']} | {o['status']}"
            for o in orders
        ]
        await callback.message.answer("📦 Последние заказы:\n\n" + "\n".join(lines))
    await callback.answer()


@admin_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Пришлите текст объявления для рассылки всем пользователям:")
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.answer()


@admin_router.message(AdminStates.waiting_broadcast)
async def admin_broadcast_send(message: Message, state: FSMContext):
    conn = db()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    await state.clear()

    sent, failed = 0, 0
    for u in users:
        try:
            await message.bot.send_message(u["user_id"], message.text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # чтобы не упереться в лимиты Telegram

    await message.answer(f"Рассылка завершена.\nОтправлено: {sent}\nОшибок: {failed}")


# ======================= ЗАПУСК =======================


async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)  # админ-роутер первым — важно для приоритета FSM
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
