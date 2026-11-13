
import asyncio
import logging
import os
import random
import secrets

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    ChatPermissions,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# =========================
# CẤU HÌNH
# =========================

TOKEN = os.getenv("BOT_TOKEN")
VERIFY_TIME = 120

dp = Dispatcher()

pending = {}
timers = {}

logging.basicConfig(level=logging.INFO)


# =========================
# KHÓA THÀNH VIÊN
# =========================

async def mute_member(bot, chat_id, user_id):
    permissions = ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False
    )

    await bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=user_id,
        permissions=permissions
    )


# =========================
# MỞ KHÓA THÀNH VIÊN
# =========================

async def unmute_member(bot, chat_id, user_id):
    chat = await bot.get_chat(chat_id)

    permissions = chat.permissions or ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True
    )

    await bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=user_id,
        permissions=permissions
    )


# =========================
# KICK THÀNH VIÊN
# =========================

async def kick_member(bot, chat_id, user_id):
    await bot.ban_chat_member(
        chat_id=chat_id,
        user_id=user_id,
        revoke_messages=False
    )

    await bot.unban_chat_member(
        chat_id=chat_id,
        user_id=user_id,
        only_if_banned=True
    )


# =========================
# TẠO CÂU HỎI
# =========================

def create_question():

    question_type = random.randint(1, 3)

    # CÂU 1: PHÉP CỘNG
    if question_type == 1:
        a = random.randint(1, 30)
        b = random.randint(1, 30)
        answer = a + b

        choices = {answer}

        while len(choices) < 4:
            value = answer + random.randint(-15, 15)
            if value != answer:
                choices.add(value)

        choices = list(choices)
        random.shuffle(choices)

        return f"🔢 {a} + {b} = ?", choices, [str(answer)]

    # CÂU 2: PHÉP TRỪ
    elif question_type == 2:
        a = random.randint(20, 60)
        b = random.randint(1, a - 1)
        answer = a - b

        choices = {answer}

        while len(choices) < 4:
            value = answer + random.randint(-15, 15)
            if value >= 0 and value != answer:
                choices.add(value)

        choices = list(choices)
        random.shuffle(choices)

        return f"🔢 {a} - {b} = ?", choices, [str(answer)]

    # CÂU 3: TiOS
    else:
        question = "📢 Bạn biết tới TiOS bằng gì?"

        choices = [
            "Facebook",
            "TikTok",
            "Bạn bè giới thiệu",
            "Telegram"
        ]

        random.shuffle(choices)

        # Cả 4 đáp án đều đúng
        return question, choices, choices.copy()


# =========================
# TẠO BÀN PHÍM
# =========================

def create_keyboard(captcha_id, choices):
    buttons = []

    for index, choice in enumerate(choices):
        buttons.append(
            InlineKeyboardButton(
                text=choice,
                callback_data=f"captcha:{captcha_id}:{index}"
            )
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons[:2],
            buttons[2:]
        ]
    )


# =========================
# HẾT THỜI GIAN
# =========================

async def verification_timeout(bot, captcha_id):
    try:
        await asyncio.sleep(VERIFY_TIME)

        data = pending.pop(captcha_id, None)

        if not data:
            return

        timers.pop(captcha_id, None)

        await kick_member(
            bot,
            data["chat_id"],
            data["user_id"]
        )

        await bot.send_message(
            data["chat_id"],
            f"⏰ {data['name']} đã hết 120 giây xác minh.\n\n"
            "🚫 Đã bị đuổi khỏi TiOS Chat."
        )

    except asyncio.CancelledError:
        pass

    except Exception:
        logging.exception("Lỗi xử lý hết thời gian")


# =========================
# THÀNH VIÊN MỚI
# =========================

@dp.message(F.new_chat_members)
async def new_member(message: Message, bot: Bot):

    for user in message.new_chat_members:

        if user.is_bot:
            continue

        chat_id = message.chat.id
        user_id = user.id

        try:
            await mute_member(bot, chat_id, user_id)

            question, choices, correct = create_question()

            captcha_id = secrets.token_urlsafe(8)

            pending[captcha_id] = {
                "chat_id": chat_id,
                "user_id": user_id,
                "name": user.full_name,
                "correct": correct
            }

            keyboard = create_keyboard(
                captcha_id,
                choices
            )

            await message.answer(
                f"👋 Chào mừng {user.full_name} đến với TiOS Chat!\n\n"
                "🛡 XÁC MINH THAM GIA NHÓM\n\n"
                f"{question}\n\n"
                "👇 Hãy chọn đáp án đúng bên dưới.\n\n"
                "⏰ Thời gian: 120 giây\n"
                "❌ Trả lời sai hoặc hết giờ sẽ bị đuổi khỏi nhóm.",
                reply_markup=keyboard
            )

            timers[captcha_id] = asyncio.create_task(
                verification_timeout(bot, captcha_id)
            )

        except Exception:
            logging.exception(
                f"Lỗi xác minh thành viên {user_id}"
            )


# =========================
# KIỂM TRA ĐÁP ÁN
# =========================

@dp.callback_query(F.data.startswith("captcha:"))
async def check_captcha(callback: CallbackQuery, bot: Bot):

    try:
        _, captcha_id, index = callback.data.split(":")
        index = int(index)

    except (ValueError, AttributeError):
        await callback.answer("Dữ liệu không hợp lệ!")
        return

    data = pending.get(captcha_id)

    if not data:
        await callback.answer(
            "Câu hỏi đã hết hạn!",
            show_alert=True
        )
        return

    if callback.from_user.id != data["user_id"]:
        await callback.answer(
            "Đây không phải câu hỏi của bạn!",
            show_alert=True
        )
        return

    if callback.message is None:
        await callback.answer("Không tìm thấy câu hỏi!")
        return

    markup = callback.message.reply_markup

    if markup is None:
        await callback.answer("Câu hỏi không còn hiệu lực!")
        return

    buttons = [
        button
        for row in markup.inline_keyboard
        for button in row
    ]

    if index < 0 or index >= len(buttons):
        await callback.answer("Đáp án không hợp lệ!")
        return

    selected = buttons[index].text

    # TRẢ LỜI SAI
    if selected not in data["correct"]:

        pending.pop(captcha_id, None)

        task = timers.pop(captcha_id, None)

        if task:
            task.cancel()

        await callback.answer(
            "❌ Sai đáp án! Bạn bị đuổi khỏi nhóm.",
            show_alert=True
        )

        try:
            await kick_member(
                bot,
                data["chat_id"],
                data["user_id"]
            )

            await callback.message.edit_text(
                f"❌ {data['name']} đã trả lời sai.\n\n"
                "🚫 Đã bị đuổi khỏi TiOS Chat."
            )

        except Exception:
            logging.exception("Không thể kick thành viên")

        return

    # TRẢ LỜI ĐÚNG
    pending.pop(captcha_id, None)

    task = timers.pop(captcha_id, None)

    if task:
        task.cancel()

    try:
        await unmute_member(
            bot,
            data["chat_id"],
            data["user_id"]
        )

        await callback.answer(
            "✅ Xác minh thành công!"
        )

        await callback.message.edit_text(
            f"✅ Chúc mừng {data['name']}!\n\n"
            "🎉 Bạn đã xác minh thành công.\n"
            "🔓 Bạn đã được phép nhắn tin trong TiOS Chat."
        )

    except Exception:
        logging.exception("Không thể mở khóa thành viên")

        await callback.answer(
            "Có lỗi khi mở khóa! Hãy báo Admin.",
            show_alert=True
        )


# =========================
# LỆNH START
# =========================

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🤖 TiOS Chat CAPTCHA BOT\n\n"
        "Bot xác minh thành viên tự động đang hoạt động!"
    )


# =========================
# KHỞI ĐỘNG BOT
# =========================

async def main():

    if not TOKEN:
        raise RuntimeError(
            "Chưa cấu hình BOT_TOKEN trên Hosting!"
        )

    bot = Bot(token=TOKEN)

    logging.info("TiOS Chat CAPTCHA BOT STARTED")

    try:
        await dp.start_polling(bot)

    finally:
        for task in timers.values():
            task.cancel()

        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
