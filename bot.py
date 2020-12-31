import asyncio
import logging

from aiogram.utils import exceptions

from aiogram import Bot
from aiogram import types
from aiogram.dispatcher import Dispatcher
from aiogram.types.message import ContentTypes
from aiogram.utils import executor

from db import DB
from bot_db import BotDB

from pymysql.err import *

import json

from random import choice

from config import token


logging.basicConfig(level=logging.INFO)
log = logging.getLogger('broadcast')

bot = Bot(token=token, parse_mode=types.ParseMode.MARKDOWN)
dp = Dispatcher(bot)

link_to_task_id = "https://ege.sdamgia.ru/problem?id="


async def send_message(user_id: int, text: str, disable_notification: bool = False) -> bool:
    """
    Safe messages sender
    :param user_id:
    :param text:
    :param disable_notification:
    :return:
    """
    try:
        await bot.send_message(user_id, text, disable_notification=disable_notification)
    except exceptions.BotBlocked:
        log.error(f"Target [ID:{user_id}]: blocked by user")
    except exceptions.ChatNotFound:
        log.error(f"Target [ID:{user_id}]: invalid user ID")
    except exceptions.RetryAfter as e:
        log.error(f"Target [ID:{user_id}]: Flood limit is exceeded. Sleep {e.timeout} seconds.")
        await asyncio.sleep(e.timeout)
        return await send_message(user_id, text)  # Recursive call
    except exceptions.UserDeactivated:
        log.error(f"Target [ID:{user_id}]: user is deactivated")
    except exceptions.TelegramAPIError:
        log.exception(f"Target [ID:{user_id}]: failed")
    else:
        log.info(f"Target [ID:{user_id}]: success")
        return True
    return False


@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    try:
        bot_db.add_user(user_id=user_id)
        await send_message(user_id=user_id,
                           text="Тренировка по задачам ЕГЭ. Отправь свой ник что бы зарегестрироваться")
    except IntegrityError:
        log.error(f"Target [ID: {user_id}]: Duplicate entry user_id. User wants to register twice.")
        await send_message(user_id=user_id,
                           text="Вы уже зарегестрированы. Напишите /task что бы получить задачу.")


@dp.message_handler(commands=["task"])
async def task_handler(message: types.Message):
    user_data = bot_db.get_user_data(user_id=message.from_user.id)
    if user_data["status"] == 1:
        user_id = message.from_user.id
        await send_task(user_id)


@dp.message_handler(commands=['top'])
async def get_top_users(message: types.Message):
    user_data = bot_db.get_user_data(user_id=message.from_user.id)
    if user_data["status"] == 1:
        user_id = message.from_user.id
        tops = bot_db.get_top_users()
        m_text = "Топ пользователей"
        for i, top in enumerate(tops):
            m_text += f"\n {i+1}. {top['name']}: {top['score']}"
        await send_message(user_id=user_id, text=m_text)


@dp.message_handler(commands=['delme'])
async def del_user(message: types.Message):
    """Удалить информацию о пользователе по закону о ПД."""
    user_data = bot_db.get_user_data(user_id=message.from_user.id)
    if user_data["status"] == 1:
        user_id = message.from_user.id
        log.info(f"Target [ID:{user_id}]: try to delete his personal info")
        bot_db.delete_user(user_id=user_id)


@dp.message_handler(commands=['setname'])
async def cmd_start(message: types.Message):
    user_data = bot_db.get_user_data(user_id=message.from_user.id)
    if user_data["status"] == 1:
        user_id = message.from_user.id
        m_text = "Теперь отправьте боту ваше новое имя."
        bot_db.change_user_status(user_id=user_id, new_status=0)
        await send_message(user_id=user_id, text=m_text)


@dp.message_handler(content_types=ContentTypes.TEXT)
async def user_get_text_handler(message: types.Message):
    user_id = message.from_user.id
    user_data = bot_db.get_user_data(user_id=user_id)
    if user_data["status"] == 0:
        bot_db.set_user_name(user_id=user_id, name=message.text[:63])
        await send_message(user_id=user_id,
                           text="Поздравляем! Вы успешно зарегестрировались! Вы можете получить вашу "
                                "задачу комндой /task. Этой же команжой вы можете запросить новую, "
                                "если предидущая вам надоест. После того как решите задачу отправьте ответ "
                                "сообщением. Символом разделения дробной и целой части является запятая."
                                "Что бы узнать топ пользователей напиши /top")
    elif user_data["status"] == 1:
        # В случае если этот текст нужно воспринимать как ответ на задачу
        task_data = db.get_task_data(task_id=user_data["current_problem_id"])
        right_ans = str(task_data["answer"]).strip().replace(" ", "").replace("Примечание", "").replace("Приведем", "").replace("Напомним,", "").replace("Аналоги", "").replace("Иногда", "").replace("Классификатор", "").replace("Источник:", "")
        link = link_to_task_id + str(task_data["task_id"])
        if message.text == right_ans:
            # В случае если пользователь ответил правильно
            score = bot_db.add_new_solved_problem(user_id=user_id, task_id=task_data["task_id"])

            await send_message(user_id=user_id,
                               text=f"""Вы ответили правильно. Ваш счёт {score}. Ссылка на эту задачу: {link}.
                                        \n {task_data['solution']}.""")
        else:
            # В случае если пользователь ответил не правильно
            score = bot_db.add_new_wrong_solved_problem(user_id=user_id, task_id=task_data["task_id"])
            await send_message(user_id=user_id,
                               text=f"""Вы ответили неправильно. Ваш счёт {score}. Ссылка на эту задачу: {link}.
                                        \n {task_data['solution']}.""")

    # Теперь нужно сгенерировать и отправить ползователю новую задачу
    await send_task(user_id)


async def send_task(user_id):
    solved_problems = bot_db.get_user_data(user_id)["solved_problems"]
    if solved_problems != "":
        not_valid_tasks = json.loads(solved_problems)
    else:
        not_valid_tasks = []

    task = db.get_task(not_valid_task=not_valid_tasks, num = choice([1, 4]))
    bot_db.set_current_problem(user_id=user_id, current_task_id=task["task_id"]) # TODO Send photos
    log.info(f"User [ID:{user_id}]: get task {task}")
    await send_message(user_id=user_id, text=task["text"])


if __name__ == '__main__':
    bot_db = BotDB()
    db = DB()
    executor.start_polling(dp, skip_updates=True)
