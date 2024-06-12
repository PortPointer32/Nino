import os
import sys
from aiogram import Bot, Dispatcher, executor, types, filters
import database
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters import Regexp
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery, MenuButtonWebApp, WebAppInfo
from aiogram.utils.callback_data import CallbackData
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler
import aiohttp
import random
import logging
import time
import json
from sys import path
import asyncio
from start import restart_main
import re
import string
from datetime import datetime, timedelta

path.append('')

logging.basicConfig(level=logging.INFO)


def split_districts(districts):
    return districts.split(':')


class OrderState(StatesGroup):
    waiting_for_payment = State()
    waiting_for_payment_balance = State()
    waiting_for_payment_manualpay = State()
    waiting_for_payment_card = State()


class OrderBalanceState(StatesGroup):
    waiting_for_balance_payment = State()


class OrderManualPaymentState(StatesGroup):
    waiting_for_manual_payment_confirmation = State()


class OrderCardPaymentState(StatesGroup):
    waiting_for_card_payment_confirmation = State()


class BalanceStates(StatesGroup):
    replenishment_amount = State()


class CaptchaState(StatesGroup):
    input = State()


async def update_crypto_rates():
    global btc_price, ltc_price
    url = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,litecoin&vs_currencies=rub'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            btc_price = data['bitcoin']['rub']
            ltc_price = data['litecoin']['rub']


async def periodic_crypto_update():
    while True:
        await update_crypto_rates()
        await asyncio.sleep(900)


btc_price = 0
ltc_price = 0


def extract_third_district(districts_string):
    districts = districts_string.split(':')
    if len(districts) >= 3:
        return districts[2]
    else:
        return "Третий район не указан"


def generate_random_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))


async def send_random_captcha(message: types.Message, state: FSMContext):
    captcha_dir = os.path.join(os.path.dirname(__file__), '..', 'captcha')
    if not os.path.exists(captcha_dir) or not os.listdir(captcha_dir):
        return False

    captcha_files = [f for f in os.listdir(captcha_dir) if f.endswith('.jpg')]
    if not captcha_files:
        return False

    captcha_file = random.choice(captcha_files)
    captcha_path = os.path.join(captcha_dir, captcha_file)
    with open(captcha_path, 'rb') as photo:
        await message.answer_photo(photo=photo)

        await message.answer(
            f"Для доступа введите капчу."
        )

        async with state.proxy() as data:
            data['captcha_answer'] = captcha_file.rstrip('.jpg')

    return True


async def register_handlers(dp: Dispatcher, bot_token):
    @dp.message_handler(lambda message: message.text in ["/start", "🏠 Меню", "/menu"], state=None)
    async def cmd_start(message: types.Message, state: FSMContext):
        await state.finish()
        user_id = message.from_user.id
        if not database.check_user_exists(user_id, bot_token):
            if await send_random_captcha(message, state):
                await CaptchaState.input.set()
                return

            database.add_user(user_id, bot_token)

        welcome_message = ("<b>✳️.✳️.✳️..Добро пожаловать..✳️.✳️.✳️</b>\n"
                           "🔷🔶🔹...HaVaNa MaMa...🔹🔶🔷\n"
                           "🚩🚩🚩🚩🚩🚩🚩\n"
                           "♻️.♻️.♻️.♻️.♻️.♻️.♻️.♻️.♻️.♻️♻️.♻️.♻️\n"
                           "⚛️ Нижегородская область, открываем новые города\n"
                           "♻️.♻️.♻️.♻️.♻️.♻️.♻️.♻️.♻️.♻️♻️.♻️.♻️\n\n"
                           "💰 Оплата:BTC, EXMO-USDT, КАРТА 💳\n"
                           "💷💶💵💵💷💴💵💷💴💵💷💴💵💴💶\n\n"
                           " 😱... ИГРЫ, АКЦИИ, СКИДКИ\n"
                           " 😱....🔫🔫🔫💣💣💣🧨🧨\n"
                           " 😱.....(Проводятся ежедневно)\n\n"
                           "◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️\n"
                           "<b>Всегда актуальные контакты</b> http://hvmamm.top\n"
                           "◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️\n\n"
                           "<b>По вопросам покупки опта выше 5г обращаться к оператору👉@hvnmm247</b> \n\n"
                           "Выберите раздел\n\n"
                           "📦 Товары и цены<i>Жми</i> 👉 /products\n\n"
                           "🌆 Выбрать район<i>Жми</i> 👉 /locations\n\n"
                           "💰 Мой последний заказ<i>Жми</i> 👉 /last_order\n"
                           "- - - - - - - - - - - - - - - -\n"
                           "📦 Типы клада\n"
                           "<i>Жми</i> 👉 /storage_types")

        new_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        new_keyboard.add(KeyboardButton('🏠 Меню'))
        new_keyboard.add(KeyboardButton('📦 Все продукты'), KeyboardButton('👉 Локации'))
        new_keyboard.add(KeyboardButton('📦 Типы клада'))
        new_keyboard.add(KeyboardButton('💰 Мой последний заказ'), KeyboardButton('❓ Помощь'))
        new_keyboard.add(KeyboardButton('💰 Баланс'), KeyboardButton('💰 Пополнить баланс'))
        await message.answer(welcome_message, reply_markup=new_keyboard, parse_mode="HTML")

    @dp.message_handler(state=CaptchaState.input)
    async def handle_captcha_input(message: types.Message, state: FSMContext):
        async with state.proxy() as data:
            correct_answer = data.get('captcha_answer')

        if message.text == correct_answer:
            user_id = message.from_user.id
            database.add_user(user_id, bot_token)
            await state.finish()

            welcome_message = ("<b>✳️.✳️.✳️..Добро пожаловать..✳️.✳️.✳️</b>\n"
                               "🔷🔶🔹...HaVaNa MaMa...🔹🔶🔷\n"
                               "🚩🚩🚩🚩🚩🚩🚩\n"
                               "♻️.♻️.♻️.♻️.♻️.♻️.♻️.♻️.♻️.♻️♻️.♻️.♻️\n"
                               "⚛️ Нижегородская область, открываем новые города\n"
                               "♻️.♻️.♻️.♻️.♻️.♻️.♻️.♻️.♻️.♻️♻️.♻️.♻️\n\n"
                               "💰 Оплата:BTC, EXMO-USDT, КАРТА 💳\n"
                               "💷💶💵💵💷💴💵💷💴💵💷💴💵💴💶\n\n"
                               " 😱... ИГРЫ, АКЦИИ, СКИДКИ\n"
                               " 😱....🔫🔫🔫💣💣💣🧨🧨\n"
                               " 😱.....(Проводятся ежедневно)\n\n"
                               "◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️\n"
                               "<b>Всегда актуальные контакты</b> http://hvmamm.top\n"
                               "◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️◼️\n\n"
                               "<b>По вопросам покупки опта выше 5г обращаться к оператору👉@hvnmm247</b> \n\n"
                               "Выберите раздел\n\n"
                               "📦 Товары и цены<i>Жми</i> 👉 /products\n\n"
                               "🌆 Выбрать район<i>Жми</i> 👉 /locations\n\n"
                               "💰 Мой последний заказ<i>Жми</i> 👉 /last_order\n"
                               "- - - - - - - - - - - - - - - -\n"
                               "📦 Типы клада\n"
                               "<i>Жми</i> 👉 /storage_types")

            new_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            new_keyboard.add(KeyboardButton('🏠 Меню'))
            new_keyboard.add(KeyboardButton('📦 Все продукты'), KeyboardButton('👉 Локации'))
            new_keyboard.add(KeyboardButton('📦 Типы клада'))
            new_keyboard.add(KeyboardButton('💰 Мой последний заказ'), KeyboardButton('❓ Помощь'))
            new_keyboard.add(KeyboardButton('💰 Баланс'), KeyboardButton('💰 Пополнить баланс'))

            await message.answer(welcome_message, reply_markup=new_keyboard, parse_mode="HTML")
        else:
            await send_random_captcha(message, state)

    def create_product_keyboard(products):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for product in products:
            button_text = f"{product[1]} product_{product[0]}"
            keyboard.add(types.KeyboardButton(button_text))
        return keyboard

    @dp.message_handler(lambda message: message.text in ["/products", "📦 Все продукты"], state=None)
    async def show_products(message: types.Message, state: FSMContext):
        products = database.get_all_products_with_details()
        if not products:
            await message.reply("Извините, товары на данный момент отсутствуют.")
            return

        product_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)

        product_message = "<b>Выберите товар</b>\n\n"
        for index, (product_name_id, product_name, product_price_id, price) in enumerate(products):
            discount = database.get_discount_by_product_name_id(product_name_id)
            discount_text = f"\n + скидка до {discount}%" if discount > 0 else ""

            match = re.search(r'\s(\d+(\.\d+)?\s?г)$', product_name)
            if match:
                clean_name = product_name[:match.start()]
                weight = match.group(1).strip()
                display_name = f"📦 {clean_name} ({weight})"
            else:
                clean_name = product_name
                display_name = clean_name

            button_text = f"{clean_name} product_{product_price_id}_{product_name_id}"
            product_keyboard.add(types.KeyboardButton(button_text))

            product_message += f"📦 {display_name}<b>{discount_text}</b>\n{int(price)} руб 👉 /product_{product_price_id}_{product_name_id}\n"
            if index < len(products) - 1:
                product_message += "- - - - - - - - - - - - - - - -\n"

        product_keyboard.add(types.KeyboardButton('🏠 Меню'))
        product_keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        product_keyboard.add(types.KeyboardButton('📦 Типы клада'))
        product_keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        product_keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

        product_message += "\n➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"

        await message.answer(product_message, reply_markup=product_keyboard, parse_mode=types.ParseMode.HTML)

    @dp.message_handler(lambda message: re.search(r'product_(\d+)_(\d+)', message.text))
    async def product_selected(message: types.Message, state: FSMContext):
        match = re.search(r'product_(\d+)_(\d+)', message.text)
        if match:
            product_price_id = int(match.group(1))
            product_name_id = int(match.group(2))
            klad_types = database.get_available_klad_types_by_product_and_price(product_name_id, product_price_id)
            if klad_types:
                product_name = database.get_product_name(product_name_id)
                response_message = f"<b>{product_name}</b>\n<b>Выберите тип клада</b>\n\n"
                for index, (klad_type, forkey) in enumerate(klad_types):
                    response_message += f"📦 {klad_type}\n👉 /product_st_{forkey}_{product_price_id}_{product_name_id}"
                    if index < len(klad_types) - 1:
                        response_message += "\n- - - - - - - - - - - - - - - -\n"
                response_message += "\n\n➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"
                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                for klad_type, forkey in klad_types:
                    button_text = f"{klad_type} product_st_{forkey}_{product_price_id}_{product_name_id}"
                    keyboard.add(types.KeyboardButton(button_text))
                keyboard.add(types.KeyboardButton('🏠 Меню'))
                keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
                keyboard.add(types.KeyboardButton('📦 Типы клада'))
                keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
                keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))
                await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
            else:
                await message.reply("Извините, доступные типы клада для данного товара отсутствуют.")

    @dp.message_handler(lambda message: re.search(r'product_(\d+)_(\d+)', message.text))
    async def product_selected(message: types.Message, state: FSMContext):
        match = re.search(r'product_(\d+)_(\d+)', message.text)
        if match:
            product_price_id = int(match.group(1))
            product_name_id = int(match.group(2))
            klad_types = database.get_available_klad_types_by_product_and_price(product_name_id, product_price_id)
            if klad_types:
                product_name = database.get_product_name(product_name_id)
                response_message = f"<b>{product_name}</b>\n<b>Выберите тип клада</b>\n\n"
                for index, (klad_type, forkey) in enumerate(klad_types):
                    response_message += f"📦 {klad_type}\n👉 /product_st_{forkey}_{product_price_id}_{product_name_id}"
                    if index < len(klad_types) - 1:
                        response_message += "\n- - - - - - - - - - - - - - - -\n"
                response_message += "\n➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"
                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                for klad_type, forkey in klad_types:
                    button_text = f"{klad_type} product_st_{forkey}_{product_price_id}_{product_name_id}"
                    keyboard.add(types.KeyboardButton(button_text))
                keyboard.add(types.KeyboardButton('🏠 Меню'))
                keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
                keyboard.add(types.KeyboardButton('📦 Типы клада'))
                keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
                keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))
                await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
            else:
                await message.reply("Извините, доступные типы клада для данного товара отсутствуют.")

    @dp.message_handler(lambda message: re.match('.*product_st_([a-z0-9]+)_(\\d+)_(\\d+)', message.text))
    async def product_st_selected(message: types.Message, state: FSMContext):
        match = re.search('product_st_([a-z0-9]+)_(\\d+)_(\\d+)', message.text)
        if match:
            klad_type_forkey = match.group(1)
            product_price_id = int(match.group(2))
            product_name_id = int(match.group(3))

            product_name = database.get_product_name(product_name_id)
            price = database.get_product_price(product_price_id)
            klad_type_name = database.get_klad_type_name_by_forkey(klad_type_forkey)
            discount = database.get_discount_by_product_name_id(product_name_id)
            discount_text = f" + скидка до {discount}%" if discount > 0 else ""

            if klad_type_name:
                cities = database.get_available_cities_by_product_price_and_klad_type(product_name_id, product_price_id,
                                                                                      klad_type_forkey)
                if cities:
                    response_message = (f"<b>Выбран тип клада:</b>\n"
                                        f"📦 {klad_type_name}\n"
                                        f"➖➖➖➖➖➖➖➖➖➖➖\n"
                                        f"<b>Вы заказываете:</b>\n"
                                        f"<b>{product_name} за {price} руб</b>\n"
                                        f"Уточните район:\n\n")
                    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)

                    for index, (city_name, city_forkey) in enumerate(cities):
                        response_message += f"🚩 <i>{city_name}</i>\n<b>{discount_text}</b>\n👉<i>Выбрать</i> /order_st_{city_forkey}_{klad_type_forkey}_{product_price_id}_{product_name_id}\n"
                        button_text = f"{city_name} order_st_{city_forkey}_{klad_type_forkey}_{product_price_id}_{product_name_id}"
                        keyboard.add(types.KeyboardButton(button_text))

                        if index != len(cities) - 1:
                            response_message += "- - - - - - - - - - - - - - - -\n"

                    response_message += ("\n➖➖➖➖➖➖➖➖➖➖➖\n"
                                         "Ⓜ️ Вернуться в меню\n"
                                         "<i>Жми</i> 👉 /menu")

                    keyboard.add(types.KeyboardButton('🏠 Меню'))
                    keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
                    keyboard.add(types.KeyboardButton('📦 Типы клада'))
                    keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
                    keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

                    await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
                else:
                    await message.reply("К сожалению, для данного товара нет доступных городов.")
            else:
                await message.reply("Извините, информация о данном типе клада отсутствует.")

    @dp.message_handler(lambda message: re.match(
        '.*order_st_(?=.*[a-z])(?=.*[0-9])[a-z0-9]+_(?=.*[a-z])(?=.*[0-9])[a-z0-9]+_([0-9]+)_([0-9]+)$', message.text))
    async def order_first_district_selection(message: types.Message, state: FSMContext):
        match = re.search('order_st_([a-z0-9]+)_([a-z0-9]+)_([0-9]+)_([0-9]+)', message.text)
        if match:
            city_forkey, klad_type_forkey, product_price_id, product_name_id = match.groups()
            districts_raw = database.get_districts_by_city_klad_price_name(city_forkey, klad_type_forkey,
                                                                           int(product_price_id), int(product_name_id))
            district_set = set()
            district_details = {}
            for district_string, district_id in districts_raw:
                districts = district_string.split(':')
                first_district = districts[0] if districts[0].lower() != 'none' else None
                if first_district:
                    district_set.add(first_district)
                    next_step = "4" if len(districts) == 3 and districts[2].lower() == 'none' else "2"
                    district_details[first_district] = {'id': district_id, 'next_step': next_step}

            product_name = database.get_product_name(int(product_name_id))
            price = database.get_product_price(int(product_price_id))
            klad_type_name = database.get_klad_type_name_by_forkey(klad_type_forkey)
            discount = database.get_discount_by_product_name_id(product_name_id)
            discount_text = f" + скидка до {discount}%" if discount > 0 else ""

            district_texts = []
            for district in district_set:
                district_text = (f"🚩 <i>{district}</i>\n<b>{discount_text}</b>\n<i>Выбрать</i> 👉 " +
                                 (
                                     f"/order_st_{city_forkey}_4_{klad_type_forkey}_{product_price_id}_{product_name_id}_{district_details[district]['id']}" if
                                     district_details[district]['next_step'] == '4' else
                                     f"/order_st_{city_forkey}_{district_details[district]['next_step']}_{klad_type_forkey}_{district_details[district]['id']}_{product_price_id}_{product_name_id}"))
                district_texts.append(district_text)

            districts_message = "\n- - - - - - - - - - - - - - - -\n".join(district_texts)

            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            for district in district_set:
                command_text = (
                    f"order_st_{city_forkey}_4_{klad_type_forkey}_{product_price_id}_{product_name_id}_{district_details[district]['id']}" if
                    district_details[district]['next_step'] == '4' else
                    f"order_st_{city_forkey}_{district_details[district]['next_step']}_{klad_type_forkey}_{district_details[district]['id']}_{product_price_id}_{product_name_id}")
                button_text = f"{district} {command_text}"
                keyboard.add(types.KeyboardButton(button_text))

            keyboard.add(types.KeyboardButton('🏠 Меню'))
            keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
            keyboard.add(types.KeyboardButton('📦 Типы клада'))
            keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
            keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

            response_message = (f"<b>Выбран тип клада:</b>\n"
                                f"📦 {klad_type_name}\n"
                                f"➖➖➖➖➖➖➖➖➖➖➖➖\n"
                                f"<b>{product_name}</b>\n\n"
                                f"❗️ Для продолжения заказа\n"
                                f"уточните район:\n\n"
                                f"{districts_message}\n"
                                f"\n➖➖➖➖➖➖➖➖➖➖➖➖\n"
                                "Ⓜ️ Вернуться в меню\n"
                                "<i>Жми</i> 👉 /menu")

            await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

    @dp.message_handler(
        lambda message: re.match('.*order_st_([a-z0-9]+)_2_([a-z0-9]+)_([0-9]+)_([0-9]+)_([0-9]+)$', message.text))
    async def order_second_district_selection(message: types.Message, state: FSMContext):
        match = re.search('order_st_([a-z0-9]+)_2_([a-z0-9]+)_([0-9]+)_([0-9]+)_([0-9]+)', message.text)
        if match:
            city_forkey, klad_type_forkey, district_id, product_price_id, product_name_id = match.groups()

            third_districts = database.get_third_districts_by_filters(city_forkey, klad_type_forkey,
                                                                      int(product_price_id), int(product_name_id),
                                                                      int(district_id))

            product_name = database.get_product_name(int(product_name_id))
            price = database.get_product_price(int(product_price_id))
            klad_type_name = database.get_klad_type_name_by_forkey(klad_type_forkey)
            discount = database.get_discount_by_product_name_id(product_name_id)
            discount_text = f" + скидка до {discount}%" if discount > 0 else ""

            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            for district_id, district_name in third_districts:
                if district_name.lower() != 'none':
                    button_text = f"{district_name} order_st_{city_forkey}_4_{klad_type_forkey}_{product_price_id}_{product_name_id}_{district_id}"
                    keyboard.add(types.KeyboardButton(button_text))

            keyboard.add(types.KeyboardButton('🏠 Меню'))
            keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
            keyboard.add(types.KeyboardButton('📦 Типы клада'))
            keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
            keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

            district_texts = [
                f"🚩 <i>{district_name}</i>\n<b>{discount_text}</b>\n<i>Выбрать</i> 👉 "
                f"/order_st_{city_forkey}_4_{klad_type_forkey}_{product_price_id}_{product_name_id}_{district_id}"
                for district_id, district_name in third_districts if district_name.lower() != 'none'
            ]

            if not district_texts:
                districts_message = "Нет доступных районов для выбора."
            else:
                districts_message = "\n- - - - - - - - - - - - - - - -\n".join(district_texts)

            response_message = (f"<b>Выбран тип клада:</b>\n"
                                f"📦 {klad_type_name}\n"
                                f"➖➖➖➖➖➖➖➖➖➖➖➖\n"
                                f"<b>{product_name}</b>\n\n"
                                f"❗️ Для продолжения заказа\n"
                                f"уточните район:\n\n"
                                f"{districts_message}\n"
                                f"\n➖➖➖➖➖➖➖➖➖➖➖➖\n"
                                "Ⓜ️ Вернуться в меню\n"
                                "<i>Жми</i> 👉 /menu")

            await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

    @dp.message_handler(lambda message: re.match('.*order_st_([0-9]+)_([0-9]+)$', message.text))
    async def order_payment_method_selection123(message: types.Message, state: FSMContext):
        match = re.search('order_st_([0-9]+)_([0-9]+)', message.text)
        if match:
            city_id, product_id = match.groups()
            klad_type_forkey = database.get_klad_type_forkey_by_product_id(product_id)

            discount = database.get_discount_by_product_id(product_id)
            discount_text = f"<b>+ скидка до {discount}%</b>" if discount > 0 else ""

            if klad_type_forkey:
                klad_type_name = database.get_klad_type_name_by_forkey(klad_type_forkey)
                active_payment_types = database.get_active_payment_types()

                response_message = (f"<b>Выбран тип клада</b>\n"
                                    f"📦 {klad_type_name}\n"
                                    f"➖➖➖➖➖➖➖➖➖➖➖\n"
                                    f"❗️ Выберите способ оплаты:\n\n")

                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)

                if 'btc' in active_payment_types:
                    response_message += f"💰 <i>Bitcoin (BTC)</i> 👉 /order_st_{klad_type_forkey}_22_5_{product_id}\n<b>{discount_text}</b>\n\n"
                    keyboard.add(types.KeyboardButton(f"Bitcoin (BTC) order_st_{klad_type_forkey}_22_5_{product_id}"))

                if 'ltc' in active_payment_types:
                    response_message += f"💰 <i>Litecoin (LTC)</i> 👉 /order_st_{klad_type_forkey}_24_5_{product_id}\n<b>{discount_text}</b>\n\n"
                    keyboard.add(types.KeyboardButton(f"Litecoin (LTC) order_st_{klad_type_forkey}_24_5_{product_id}"))

                response_message += f"💰 <i>Оплата с баланса</i> 👉 /order_st_{klad_type_forkey}_35_5_{product_id}\n<b>{discount_text}</b>\n\n"
                keyboard.add(types.KeyboardButton(f"Оплата с баланса order_st_{klad_type_forkey}_35_5_{product_id}"))

                if 'card' in active_payment_types:
                    response_message += f"💰 <i>Оплата на КАРТУ банка через оператора</i> 👉 /order_st_{klad_type_forkey}_10_5_{product_id}\n<b>{discount_text}</b>\n\n"
                    response_message += f"💰 <i>Оплата картой банка</i> 👉 /order_st_{klad_type_forkey}_53_5_{product_id}\n<b>{discount_text}</b>\n\n"
                    keyboard.add(types.KeyboardButton(f"Через оператора order_st_{klad_type_forkey}_10_5_{product_id}"))
                    keyboard.add(
                        types.KeyboardButton(f"Оплата картой банка order_st_{klad_type_forkey}_53_5_{product_id}"))

                response_message += "➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"
                keyboard.add(types.KeyboardButton('🏠 Меню'))
                keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
                keyboard.add(types.KeyboardButton('📦 Типы клада'))
                keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
                keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

                await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
            else:
                await message.reply("Извините, информация о данном товаре отсутствует.")

    @dp.message_handler(
        lambda message: re.match('.*order_st_([a-z0-9]+)_4_([a-z0-9]+)_([0-9]+)_([0-9]+)_([0-9]+)$', message.text))
    async def order_payment_method_selection(message: types.Message, state: FSMContext):
        match = re.search('order_st_([a-z0-9]+)_4_([a-z0-9]+)_([0-9]+)_([0-9]+)_([0-9]+)', message.text)
        if match:
            city_forkey, klad_type_forkey, product_price_id, product_name_id, district_id = match.groups()
            district_forkey = database.get_district_forkey_by_id(district_id)
            product_id = database.get_product_id_by_details(product_name_id, product_price_id, city_forkey,
                                                            klad_type_forkey, district_forkey)
    
            discount = database.get_discount_by_product_name_id(product_name_id)
            discount_text = f"<b>+ скидка до {discount}%</b>" if discount > 0 else ""
    
            if product_id:
                klad_type_name = database.get_klad_type_name_by_forkey(klad_type_forkey)
                active_payment_types = database.get_active_payment_types()
    
                response_message = (f"<b>Выбран тип клада</b>\n"
                                    f"📦 {klad_type_name}\n"
                                    f"➖➖➖➖➖➖➖➖➖➖➖\n"
                                    f"❗️ Выберите способ оплаты:\n\n")
    
                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    
                if 'btc' in active_payment_types:
                    response_message += f"💰 <i>Bitcoin (BTC)</i> 👉 /order_{klad_type_forkey}_22_5_{product_id}\n<b>{discount_text}</b>\n\n"
                    keyboard.add(types.KeyboardButton(f"Bitcoin (BTC) order_{klad_type_forkey}_22_5_{product_id}"))
    
                if 'ltc' in active_payment_types:
                    response_message += f"💰 <i>Litecoin (LTC)</i> 👉 /order_{klad_type_forkey}_24_5_{product_id}\n<b>{discount_text}</b>\n\n"
                    keyboard.add(types.KeyboardButton(f"Litecoin (LTC) order_{klad_type_forkey}_24_5_{product_id}"))
    
                response_message += f"💰 <i>Оплата с баланса</i> 👉 /order_{klad_type_forkey}_35_5_{product_id}\n<b>{discount_text}</b>\n\n"
                keyboard.add(types.KeyboardButton(f"Оплата с баланса order_{klad_type_forkey}_35_5_{product_id}"))
    
                if 'card' in active_payment_types:
                    response_message += f"💰 <i>Оплата на КАРТУ банка через оператора</i> 👉 /order_{klad_type_forkey}_10_5_{product_id}\n<b>{discount_text}</b>\n\n"
                    response_message += f"💰 <i>Оплата картой банка</i> 👉 /order_{klad_type_forkey}_53_5_{product_id}\n<b>{discount_text}</b>\n\n"
                    keyboard.add(types.KeyboardButton(f"Через оператора order_{klad_type_forkey}_10_5_{product_id}"))
                    keyboard.add(
                        types.KeyboardButton(f"Оплата картой банка order_{klad_type_forkey}_53_5_{product_id}"))
    
                response_message += "➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"
                keyboard.add(types.KeyboardButton('🏠 Меню'))
                keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
                keyboard.add(types.KeyboardButton('📦 Типы клада'))
                keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
                keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))
    
                await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
            else:
                await message.reply("Извините, информация о данном товаре отсутствует.")

    @dp.message_handler(lambda message: re.match('.*order_st_([a-z0-9]+)_(22|24)_5_(\\d+)', message.text), state=None)
    async def crypto_payment(message: types.Message, state: FSMContext):
        await OrderState.waiting_for_payment.set()

        match = re.match('.*order_st_([a-z0-9]+)_(22|24)_5_(\\d+)', message.text)
        forkey, payment_method, product_id = match.groups()

        discount = database.get_discount_by_product_id(product_id)

        product_detail = database.get_product_with_details_by_id(
            product_id)  # Используем новую функцию для извлечения деталей по ID
        if product_detail:
            product_name = product_detail['product_name']
            price = product_detail['price']
            price = int(price * (1 - discount / 100))

            klad_type = product_detail['klad_type']
            districts = product_detail['district'].split(':')
            third_district = districts[2] if len(districts) > 2 and districts[2].lower() != 'none' else districts[
                0]  # Используем первый район, если третий равен 'none'
            order_number = database.get_and_increment_purchases_count()

            if payment_method == "22":
                crypto_type = "BTC"
                crypto_price = btc_price  # Пример фиксированной переменной для цены BTC
            elif payment_method == "24":
                crypto_type = "LTC"
                crypto_price = ltc_price  # Пример фиксированной переменной для цены LTC
            else:
                await message.answer("Неподдерживаемый метод оплаты.")
                await state.finish()
                return

            crypto_details = database.get_payment_details(crypto_type.lower())

            cf = database.get_payment_coefficient(crypto_type.lower())

            price = int(price * cf)

            crypto_address = random.choice(
                crypto_details.split('\n')) if crypto_details else f"{crypto_type} адрес не найден"

            price_crypto = round(price / crypto_price, 8)  # Расчёт суммы криптовалюты

            await state.update_data(
                order_number=order_number,
                crypto_type=crypto_type,
                crypto_address=crypto_address,
                price_rub=price,
                price_crypto=price_crypto,
                product_name=product_name,
                third_district=third_district,
                start_time=datetime.now()
            )

            response_message = (f"<b>💰 Вы заказали</b>\n"
                                f"{product_name} на сумму {price} руб\n"
                                f"в районе <b>{third_district}</b>.\n"
                                f"До конца резерва осталось 59 минут.\n"
                                f"Номер заказа: {order_number}.\n"
                                f"➖➖➖➖➖➖➖➖➖➖➖\n\n"
                                f"Переведите на адрес <b>{crypto_type}:</b>\n"
                                f"<b>{crypto_address}</b>\n"
                                f"сумму <b>{price_crypto} {crypto_type}</b>\n\n"
                                f"➖➖➖➖➖➖➖➖➖➖➖\n"
                                f"✔️ Проверить оплату\n"
                                f"<i>Жми</i> 👉 /order_check\n\n"
                                f"🚫 Отменить заказ\n"
                                f"<i>Жми</i> 👉 /order_cancel")

            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            keyboard.add(types.KeyboardButton("🚫 Отменить заказ"))
            keyboard.add(types.KeyboardButton('🏠 Меню'))
            keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
            keyboard.add(types.KeyboardButton('📦 Типы клада'))
            keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
            keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

            await message.answer("Подождите... Ваш запрос обрабатывается...")
            await asyncio.sleep(1)  # Имитация задержки обработки
            await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
            await start_order_timer(message, state, order_number)
        else:
            await message.answer("Информация о товаре не найдена.")
            await state.finish()

    @dp.message_handler(lambda message: message.text not in ["/order_cancel", "🚫 Отменить заказ",
                                                             "✔️ Подтверждаю отмену"] and message.text is not None,
                        state=OrderState.waiting_for_payment)
    async def check_order_payment(message: types.Message, state: FSMContext):
        data = await state.get_data()
        start_time = data['start_time']
        time_passed = datetime.now() - start_time
        time_left = timedelta(minutes=59) - time_passed

        if time_left.total_seconds() <= 0:
            await message.answer("Время на оплату вашего заказа истекло.", reply_markup=types.ReplyKeyboardRemove())
            await state.finish()
            return

        product_name = data['product_name']
        third_district = data['third_district']
        order_number = data['order_number']
        price_rub = data['price_rub']
        crypto_type = data['crypto_type']
        crypto_address = data['crypto_address']
        price_crypto = data['price_crypto']

        response_message = (f"<b>❗️ Ваш заказ не оплачен!</b>\n"
                            f"{product_name} ({third_district}).\n"
                            f"До конца резерва осталось {int(time_left.total_seconds() // 60)} минут.\n"
                            f"Номер заказа: {order_number}.\n"
                            f"➖➖➖➖➖➖➖➖➖➖➖\n"
                            f"Вам необходимо оплатить <b>{price_rub} руб.</b>\n"
                            f"Переведите на адрес {crypto_type}:\n"
                            f"<b>{crypto_address}</b>\n"
                            f"сумму <b>{price_crypto} {crypto_type}</b>\n"
                            f"➖➖➖➖➖➖➖➖➖➖➖\n"
                            f"✔️ Проверить еще раз\n"
                            f"Жми 👉 /order_check\n\n"
                            f"🚫 Отменить заказ\n"
                            f"Жми 👉 /order_cancel")

        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton('✔️ Проверить оплату'), types.KeyboardButton('🚫 Отменить заказ'))
        keyboard.add(types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        keyboard.add(types.KeyboardButton('📦 Типы клада'))
        keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

        await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

    @dp.message_handler(lambda message: message.text in ["/order_cancel", "🚫 Отменить заказ"],
                        state=[OrderState.waiting_for_payment,
                               OrderManualPaymentState.waiting_for_manual_payment_confirmation,
                               OrderCardPaymentState.waiting_for_card_payment_confirmation,
                               OrderState.waiting_for_payment_balance, OrderState.waiting_for_payment_manualpay,
                               OrderState.waiting_for_payment_card])
    async def order_cancel_request(message: types.Message, state: FSMContext):
        data = await state.get_data()
        order_number = data['order_number']

        response_message = f"Вы действительно хотите отменить заказ #{order_number}?"

        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton('✔️ Подтверждаю отмену'), types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        keyboard.add(types.KeyboardButton('📦 Типы клада'))
        keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

        await message.answer(response_message, reply_markup=keyboard)

    @dp.message_handler(lambda message: message.text == "✔️ Подтверждаю отмену", state=[OrderState.waiting_for_payment,
                                                                                        OrderManualPaymentState.waiting_for_manual_payment_confirmation,
                                                                                        OrderCardPaymentState.waiting_for_card_payment_confirmation,
                                                                                        OrderState.waiting_for_payment_balance,
                                                                                        OrderState.waiting_for_payment_manualpay,
                                                                                        OrderState.waiting_for_payment_card])
    async def order_cancel_confirm(message: types.Message, state: FSMContext):
        data = await state.get_data()
        order_number = data['order_number']
        user_id = message.from_user.id

        # Получаем текущее количество попыток пользователя
        user_attempts = database.get_user_attempts(user_id, bot_token)
        user_attempts = int(user_attempts)
        if user_attempts <= 1:  # Если попыток 0 или меньше, сбрасываем до 4
            user_attempts = 4
        user_attempts -= 1  # Уменьшаем на 1

        # Обновляем количество попыток в базе данных
        database.update_user_attempts(user_id, bot_token, user_attempts)

        response_message = f"<b>❗️ Ваш заказ {order_number} отменен!</b>\n\n➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"
        warning_message = f"❗️ Предупреждение!\nЗапрещено резервировать товар без оплаты более 4 раз!\nУ вас осталось {user_attempts} попыток."

        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        keyboard.add(types.KeyboardButton('📦 Типы клада'))
        keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

        await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
        await message.answer(warning_message, reply_markup=keyboard)
        await state.finish()

    @dp.message_handler(lambda message: re.match('.*order_st_([a-z0-9]+)_35_5_(\\d+)', message.text), state=None)
    async def balance_payment(message: types.Message, state: FSMContext):
        product_id = message.text.split('_')[5]
        price = database.get_product_price_by_product_id(product_id)

        if price is not None:
            response_message = (f"Недостаточно средств на балансе.\n"
                                f"Необходимо пополнить баланс.\n\n"
                                f"➖➖➖➖➖➖➖➖➖\n"
                                f"Стоимость товара: {price} руб\n"
                                f"Баланс: 0,0 руб")

            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            keyboard.add(types.KeyboardButton("🚫 Отменить заказ"))
            keyboard.add(types.KeyboardButton('🏠 Меню'))
            keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
            keyboard.add(types.KeyboardButton('📦 Типы клада'))
            keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
            keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

            await message.answer(response_message, reply_markup=keyboard)
        else:
            await message.answer("Информация о товаре не найдена.")
            await state.finish()

    @dp.message_handler(lambda message: message.text == "🚫 Отменить заказ",
                        state=OrderBalanceState.waiting_for_balance_payment)
    async def order_cancel_from_balance(message: types.Message, state: FSMContext):
        await cmd_start(message, state)

    @dp.message_handler(lambda message: re.match('.*order_st_([a-z0-9]+)_10_5_(\\d+)', message.text), state=None)
    async def manual_payment(message: types.Message, state: FSMContext):
        await OrderManualPaymentState.waiting_for_manual_payment_confirmation.set()

        match = re.search('.*order_st_([a-z0-9]+)_10_5_(\\d+)', message.text)

        if match:
            forkey, product_id = match.groups()
            discount = database.get_discount_by_product_id(product_id)
            product_detail = database.get_product_with_details_by_id(product_id)

            if product_detail:
                product_name = product_detail['product_name']
                districts = product_detail['district'].split(':')
                third_district = districts[2] if len(districts) > 2 and districts[2].lower() != 'none' else districts[0]
                order_number = database.get_and_increment_purchases_count()
                price = product_detail['price']
                price = int(price * (1 - discount / 100))

                await state.update_data(
                    order_number=order_number,
                    product_name=product_name,
                    price_rub=price,
                    third_district=third_district,
                    start_time=datetime.now()
                )

                response_message = (f"<b>💰 Вы заказали</b>\n"
                                    f"{product_name} на сумму {price} руб\n"
                                    f"в районе <b>{third_district}</b>.\n"
                                    f"До конца резерва осталось 59 минут.\n"
                                    f"Номер заказа: {order_number}.\n"
                                f"➖➖➖➖➖➖➖➖➖\n\n"
                                    f"Скопируйте и напишите оператору @hvnmm247  текст данного сообщения для уточнения НОМЕРА КАРТЫ!!!).\n"
                                    f"ВНИМАНИЕ! перед каждой оплатой уточняйте  карту у оператора, во избежание потери ваших денег!\n\n"
                                    f"В комментарии к платежу ничего указывать не нужно.\n\n"
                                    f"<b>Внимание!</b> После оплаты сообщите оператору:\n"
                                    f"1. номер заказа <b>{order_number}</b>\n"
                                    f"2. <b>ОПЛАЧЕННУЮ СУММУ</b>\n"
                                    f"3. дату и ВРЕМЯ оплаты\n\n"
                                    f"<b>Внимание!</b> Сообщать об оплате нужно именно оператору, а не боту! Однако адрес выдаст Вам бот.\n\n"
                                f"➖➖➖➖➖➖➖➖➖\n"
                                f"✔️ Проверить оплату\n"
                                f"Жми 👉 /order_check\n\n"
                                f"🚫 Отменить заказ\n"
                                f"Жми 👉 /order_cancel")

                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                keyboard.add(types.KeyboardButton('🚫 Отменить заказ'))
                keyboard.add(types.KeyboardButton('🏠 Меню'))
                keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
                keyboard.add(types.KeyboardButton('📦 Типы клада'))
                keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
                keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

                await message.answer("Подождите... Ваш запрос обрабатывается...")
                await asyncio.sleep(1)  # Имитация задержки обработки
                await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
                await start_order_timer2(message, state, order_number, "hand_payment")
            else:
                await message.answer("Информация о товаре не найдена.")
                await state.finish()

    @dp.message_handler(lambda message: message.text == '❓ Помощь')
    async def help_handler(message: types.Message):
        help_message = "Оператор @hvnmm247"


    @dp.message_handler(lambda message: re.match('.*order_st_([a-z0-9]+)_53_5_(\\d+)', message.text), state=None)
    async def card_payment(message: types.Message, state: FSMContext):
        await OrderCardPaymentState.waiting_for_card_payment_confirmation.set()

        match = re.match('.*order_st_([a-z0-9]+)_53_5_(\\d+)', message.text)
        if match:
            forkey, product_id = match.groups()
            product_detail = database.get_product_with_details_by_id(product_id)

            if product_detail:
                product_name = product_detail['product_name']
                price = product_detail['price']
                price = int(price)
                districts = product_detail['district'].split(':')
                third_district = districts[2] if len(districts) > 2 and districts[2].lower() != 'none' else districts[0]
                order_number = database.get_and_increment_purchases_count()

                card_details = database.get_payment_details('card')
                cf = database.get_payment_coefficient('card')

                discount = database.get_discount_by_product_id(product_id)

                price = int(price * (1 - discount / 100))
    
                price_fee = int(price * cf)

                await state.update_data(
                    order_number=order_number,
                    product_name=product_name,
                    price_rub=price_fee,
                    third_district=third_district,
                    start_time=datetime.now(),
                    payment_details=card_details
                )

                response_message = (f"💰 Вы заказали\n"
                                    f"<b>{product_name}</b> на сумму <b>{price_fee} руб</b>\n"
                                    f"в районе <b>{third_district}</b>.\n"
                                    f"До конца резерва осталось 25 минут.\n"
                                    f"Номер заказа: {order_number}.\n"
                                    f"➖➖➖➖➖➖➖➖➖\n\n"
                                    f"Переведите на карту\n"
                                    f"{card_details}\n"
                                    f"точную сумму одной транзакцией {price_fee} руб.\n\n"
                                    f"➖➖➖➖➖➖➖➖➖\n"
                                    f"✔️ Проверить оплату\n"
                                    f"Жми 👉 /order_check\n\n"
                                    f"🚫 Отменить заказ\n"
                                    f"Жми 👉 /order_cancel")

                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                keyboard.add(types.KeyboardButton("🚫 Отменить заказ"))
                keyboard.add(types.KeyboardButton('🏠 Меню'))
                keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
                keyboard.add(types.KeyboardButton('📦 Типы клада'))
                keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
                keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

                await message.answer("Подождите... Ваш запрос обрабатывается...")
                await asyncio.sleep(1)  # Имитация задержки обработки
                await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
                await start_order_timer2(message, state, order_number, "card")
            else:
                await message.answer("Информация о товаре не найдена.")
                await state.finish()

    @dp.message_handler(lambda message: message.text not in ["/order_cancel", "🚫 Отменить заказ",
                                                             "✔️ Подтверждаю отмену"] and message.text is not None,
                        state=OrderManualPaymentState.waiting_for_manual_payment_confirmation)
    async def check_order_manual_payment(message: types.Message, state: FSMContext):
        data = await state.get_data()
        start_time = data['start_time']
        time_passed = datetime.now() - start_time
        time_left = timedelta(minutes=59) - time_passed

        product_name = data['product_name']
        third_district = data['third_district']
        order_number = data['order_number']
        price_rub = data['price_rub']

        if time_left.total_seconds() <= 0:
            response_message = "Время на оплату вашего заказа истекло."
            await message.answer(response_message, reply_markup=types.ReplyKeyboardRemove())
            await state.finish()
        else:
            response_message = (f"<b>💰 Вы заказали</b>\n"
                                f"{product_name} на сумму {price_rub} руб\n"
                                f"в районе <b>{third_district}.</b>\n"
                                f"До конца резерва осталось {int(time_left.total_seconds() // 60)} минут.\n"
                                f"Номер заказа: {order_number}.\n"
                                f"➖➖➖➖➖➖➖➖➖\n\n"
                                    f"Скопируйте и напишите оператору @hvnmm247  текст данного сообщения для уточнения НОМЕРА КАРТЫ!!!).\n"
                                    f"ВНИМАНИЕ! перед каждой оплатой уточняйте  карту у оператора, во избежание потери ваших денег!\n\n"
                                    f"В комментарии к платежу ничего указывать не нужно.\n\n"
                                    f"<b>Внимание!</b> После оплаты сообщите оператору:\n"
                                    f"1. номер заказа <b>{order_number}</b>\n"
                                    f"2. <b>ОПЛАЧЕННУЮ СУММУ</b>\n"
                                    f"3. дату и ВРЕМЯ оплаты\n\n"
                                    f"<b>Внимание!</b> Сообщать об оплате нужно именно оператору, а не боту! Однако адрес выдаст Вам бот.\n\n"
                                f"➖➖➖➖➖➖➖➖➖\n"
                                f"✔️ Проверить оплату\n"
                                f"Жми 👉 /order_check\n\n"
                                f"🚫 Отменить заказ\n"
                                f"Жми 👉 /order_cancel")

            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            keyboard.add(types.KeyboardButton('✔️ Проверить оплату'), types.KeyboardButton('🚫 Отменить заказ'))
            keyboard.add(types.KeyboardButton('🏠 Меню'))
            keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
            keyboard.add(types.KeyboardButton('📦 Типы клада'))
            keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
            keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

            await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

    @dp.message_handler(lambda message: re.match('.*order_st_([a-z0-9]+)_10_5_(\\d+)', message.text), state=None)
    async def manual_payment(message: types.Message, state: FSMContext):
        await OrderManualPaymentState.waiting_for_manual_payment_confirmation.set()

        match = re.search('.*order_st_([a-z0-9]+)_10_5_(\\d+)', message.text)
        if match:
            forkey, product_id = match.groups()
            discount = database.get_discount_by_product_id(product_id)
            product_detail = database.get_product_with_details_by_id(product_id)

            if product_detail:
                product_name = product_detail['product_name']
                districts = product_detail['district'].split(':')
                third_district = districts[2] if len(districts) > 2 and districts[2].lower() != 'none' else districts[0]
                order_number = database.get_and_increment_purchases_count()
                price = product_detail['price']
                price = int(price * (1 - discount / 100))

                await state.update_data(
                    order_number=order_number,
                    product_name=product_name,
                    price_rub=price,
                    third_district=third_district,
                    start_time=datetime.now()
                )

                response_message = (f"<b>💰 Вы заказали</b>\n"
                                    f"{product_name} на сумму {price} руб\n"
                                    f"в районе <b>{third_district}</b>.\n"
                                    f"До конца резерва осталось 59 минут.\n"
                                    f"Номер заказа: {order_number}.\n"
                                    f"➖➖➖➖➖➖➖➖➖➖➖\n\n"
                                    f"Скопируйте и напишите оператору @hvnmm247  текст данного сообщения для уточнения НОМЕРА КАРТЫ!!!).\n"
                                    f"ВНИМАНИЕ! перед каждой оплатой уточняйте  карту у оператора, во избежание потери ваших денег!\n\n"
                                    f"В комментарии к платежу ничего указывать не нужно.\n\n"
                                    f"<b>Внимание!</b> После оплаты сообщите оператору:\n"
                                    f"1. номер заказа <b>{order_number}</b>\n"
                                    f"2. <b>ОПЛАЧЕННУЮ СУММУ</b>\n"
                                    f"3. дату и ВРЕМЯ оплаты\n\n"
                                    f"<b>Внимание!</b> Сообщать об оплате нужно именно оператору, а не боту! Однако адрес выдаст Вам бот.\n\n"
                                    f"➖➖➖➖➖➖➖➖➖➖➖\n"
                                    f"✔️ Проверить оплату\n"
                                    f"Жми 👉 /order_check\n\n"
                                    f"🚫 Отменить заказ\n"
                                    f"Жми 👉 /order_cancel")

                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                keyboard.add(types.KeyboardButton('🚫 Отменить заказ'))
                keyboard.add(types.KeyboardButton('🏠 Меню'))
                keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
                keyboard.add(types.KeyboardButton('📦 Типы клада'))
                keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
                keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

                await message.answer("Подождите... Ваш запрос обрабатывается...")
                await asyncio.sleep(1)
                await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
            else:
                await message.answer("Информация о товаре не найдена.")
                await state.finish()

    @dp.message_handler(lambda message: message.text not in ["/order_cancel", "🚫 Отменить заказ",
                                                             "✔️ Подтверждаю отмену"] and message.text is not None,
                        state=OrderCardPaymentState.waiting_for_card_payment_confirmation)
    async def check_card_payment(message: types.Message, state: FSMContext):
        data = await state.get_data()
        start_time = data['start_time']
        time_passed = datetime.now() - start_time
        time_left = timedelta(minutes=25) - time_passed  # Обновляем время до 40 минут

        response_message = (f"❗️ Ваш заказ не оплачен!\n"
                            f"{data['product_name']} \n"
                            f"в районе {data['third_district']}.\n"
                            f"До конца резерва осталось {max(int(time_left.total_seconds() // 60), 0)} минут.\n"
                            f"Номер заказа: {data['order_number']}.\n"
                            f"➖➖➖➖➖➖➖➖➖\n\n"
                            f"Переведите на карту\n"
                            f"{data['payment_details']}\n"
                            f"точную сумму одной транзакцией {data['price_rub']} руб.\n\n"
                            f"➖➖➖➖➖➖➖➖➖\n"
                            f"✔️ Проверить оплату\n"
                            f"Жми 👉 /order_check\n\n"
                            f"🚫 Отменить заказ\n"
                            f"Жми 👉 /order_cancel")

        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton('✔️ Проверить оплату'), types.KeyboardButton('🚫 Отменить заказ'))
        keyboard.add(types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        keyboard.add(types.KeyboardButton('📦 Типы клада'))
        keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

        await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

    @dp.message_handler(lambda message: message.text in ["/locations", "👉 Локации"], state=None)
    async def show_locations(message: types.Message, state: FSMContext):
        cities = database.get_cities_with_ids()  # Получаем список городов с ID из базы данных
        if not cities:
            await message.reply("Извините, на данный момент локации отсутствуют.")
            return

        locations_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)

        locations_message = "<b>Выберите район</b>\n\n"
        for index, (city_id, city_name) in enumerate(cities):

            discount = database.get_maximum_discount_by_city_id(city_id)
            discount_text = f"\n + скидка до {discount}%" if discount > 0 else ""

            button_text = f"{city_name} location_{city_id}"
            locations_keyboard.add(types.KeyboardButton(button_text))
            locations_message += f"🚩 <i>{city_name}</i><b>{discount_text}</b>\n<b>Жми</b> 👉 /location_{city_id}\n"
            if index != len(cities) - 1:
                locations_message += "- - - - - - - - - - - - - - - -\n"

        locations_message += "\n➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"

        locations_keyboard.add(types.KeyboardButton('🏠 Меню'))
        locations_keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        locations_keyboard.add(types.KeyboardButton('📦 Типы клада'))
        locations_keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        locations_keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

        await message.answer(locations_message, reply_markup=locations_keyboard, parse_mode=types.ParseMode.HTML)

    @dp.message_handler(lambda message: re.match('.*location_(\\d+)$', message.text))
    async def show_districts(message: types.Message, state: FSMContext):
        city_id_match = re.match('.*location_(\\d+)', message.text)
        if city_id_match:
            city_id = city_id_match.group(1)
            districts = database.get_districts_by_city_id(city_id)
    
            if not districts:
                await message.reply("Извините, на данный момент районы в этом городе отсутствуют.")
                return
    
            city_name = database.get_city_name(city_id)
            response_message = f"<b>{city_name}</b>\nВыберите район:\n\n"
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    
            seen_districts = set()
            district_info = []
            for district_id, district_name in districts:
                first_district = district_name.split(':')[0]
                if first_district not in seen_districts:
                    seen_districts.add(first_district)
                    district_info.append((district_id, first_district))
    
            for index, (district_id, first_district) in enumerate(district_info):
                discount = database.get_maximum_discount_by_district_id(district_id)
                discount_text = f" + скидка до {discount}%" if discount > 0 else ""
                button_text = f"{first_district} location_{district_id}_{city_id}"
                keyboard.add(types.KeyboardButton(button_text))
                response_message += f"🏘 <i>{first_district}</i>\n<b>{discount_text}</b>\n<i>Выбрать</i> 👉 /location_{district_id}_{city_id}\n"
    
                if index < len(district_info) - 1:
                    response_message += "- - - - - - - - - - - - - - - -\n"
    
            keyboard.add(types.KeyboardButton('🏠 Меню'))
            keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
            keyboard.add(types.KeyboardButton('📦 Типы клада'))
            keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
            keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))
    
            response_message += "\n➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"
    
            await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
    
    @dp.message_handler(lambda message: re.match(r'^.*location_(\d+)_(\d+)$', message.text))
    async def show_third_district_selection(message: types.Message, state: FSMContext):
        match = re.match(r'^.*location_(\d+)_(\d+)$', message.text)
        if match:
            first_district_id, city_id = match.groups()
            unique_third_districts = database.get_third_districts_by_first_district_id_and_city_id(first_district_id,
                                                                                                   city_id)
    
            if not unique_third_districts:
                await message.reply("Извините, на данный момент дополнительные районы в этом городе отсутствуют.")
                return
    
            city_name = database.get_city_name(city_id)
            response_message = f"<b>{city_name}</b>\nВыберите район:\n\n"
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    
            sorted_unique_third_districts = sorted(unique_third_districts, key=lambda x: x[1])
            count_districts = len(sorted_unique_third_districts)
    
            for index, (third_district_id, third_district_name) in enumerate(sorted_unique_third_districts):
                discount = database.get_maximum_discount_by_district_id(third_district_id)
                discount_text = f" + скидка до {discount}%" if discount > 0 else ""
    
                if third_district_name.lower() == "none":  # Проверяем, равен ли район "None"
                    klad_types = database.get_available_klad_types_by_city_and_district(city_id, third_district_id)
                    for klad_type_forkey, klad_type_name in klad_types:
                        button_text = f"{klad_type_name} location_st_{klad_type_forkey}_{third_district_id}_{city_id}"
                        keyboard.add(types.KeyboardButton(button_text))
                        response_message += f"📦 {klad_type_name}\n👉 /location_st_{klad_type_forkey}_{third_district_id}_{city_id}\n"
                else:
                    button_text = f"{third_district_name} location_7_{third_district_id}_{city_id}"
                    keyboard.add(types.KeyboardButton(button_text))
                    response_message += f"🏘 <i>{third_district_name}</i>\n<b>{discount_text}</b>\n<i>Выбрать</i> 👉 /location_7_{third_district_id}_{city_id}\n"
    
                if index != count_districts - 1:
                    response_message += "- - - - - - - - - - - - - - - -\n"
    
            keyboard.add(types.KeyboardButton('🏠 Меню'))
            keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
            keyboard.add(types.KeyboardButton('📦 Типы клада'))
            keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
            keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))
    
            response_message += "\n➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"
    
            await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

    @dp.message_handler(lambda message: re.search(r'location_7_(\d+)_(\d+)', message.text.strip()))
    async def show_third_district_selection(message: types.Message, state: FSMContext):
        match = re.search(r'location_7_(\d+)_(\d+)', message.text.strip())
        if match:
            district_id, city_id = match.groups()
            klad_types = database.get_available_klad_types_by_city_and_district(city_id, district_id)
    
            if not klad_types:
                await message.reply("Извините, на данный момент типы клада в этом районе и городе отсутствуют.")
                return
    
            response_message = "<b>Выберите тип клада</b>\n\n"
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    
            for index, (klad_type_forkey, klad_type_name) in enumerate(klad_types):
                button_text = f"{klad_type_name} location_st_{klad_type_forkey}_{district_id}_{city_id}"
                keyboard.add(types.KeyboardButton(button_text))
                response_message += f"📦 {klad_type_name}\n👉 /location_st_{klad_type_forkey}_{district_id}_{city_id}\n"
    
                if index != len(klad_types) - 1:
                    response_message += "- - - - - - - - - - - - - - - -\n"
    
            keyboard.add(types.KeyboardButton('🏠 Меню'))
            keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
            keyboard.add(types.KeyboardButton('📦 Типы клада'))
            keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
            keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))
    
            response_message += "\n➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"
    
            await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

    @dp.message_handler(lambda message: re.search(r'location_st_([a-z0-9]{8})_(\d+)_(\d+)$', message.text.strip()))
    async def show_product_details_for_klad_type(message: types.Message, state: FSMContext):
        match = re.search(r'location_st_([a-z0-9]{8})_(\d+)_(\d+)$', message.text)
        if match:
            klad_type_forkey, district_id, city_id = match.groups()

            klad_type_name = database.get_klad_type_name_by_forkey(klad_type_forkey)
            city_name = database.get_city_name(city_id)
            city_forkey = database.get_city_forkey_by_id(city_id)

            if not klad_type_name or not city_name:
                await message.reply("Не удалось получить данные о типе клада или городе.")
                return

            products = database.get_products_by_klad_type_district_and_city(klad_type_forkey, district_id, city_id)

            if not products:
                await message.reply(
                    "Извините, на данный момент товары этого типа в указанном районе и городе отсутствуют.")
                return

            response_message = f"<b>Выбран тип клада:</b> 📦 {klad_type_name}\n➖➖➖➖➖➖➖➖➖➖➖\n<b>{city_name}</b>\nДоступные товары:\n\n"
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)

            for index, (product_id, product_name, product_price) in enumerate(products):
                discount = database.get_discount_by_product_id(product_id)
                discount_text = f"<b> \n+ скидка до {discount}%</b>" if discount > 0 else ""

                product_price_id = database.get_product_price_id_by_price(product_price)
                product_name_id = database.get_product_name_id_by_name(product_name)
                order_button_text = f"{product_name} {int(product_price)}руб order_st_{city_forkey}_4_{klad_type_forkey}_{product_price_id}_{product_name_id}_{district_id}"
                keyboard.add(types.KeyboardButton(order_button_text))
                response_message += f"📦 {product_name} <b>{int(product_price)} руб</b> {discount_text}\n<i>Заказать</i> 👉 /order_st_{city_forkey}_4_{klad_type_forkey}_{product_price_id}_{product_name_id}_{district_id}\n"

                if index != len(products) - 1:
                    response_message += "- - - - - - - - - - - - - - - -\n"

            keyboard.add(types.KeyboardButton('🏠 Меню'))
            keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
            keyboard.add(types.KeyboardButton('📦 Типы клада'))
            keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
            keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

            response_message += "\n➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"

            await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
        
    @dp.message_handler(lambda message: message.text in ["📦 Типы клада", "/storage_types"])
    async def show_storage_types(message: types.Message):
        klad_types = database.get_av_klad_types()
        if not klad_types:
            await message.reply("Извините, доступные типы клада не найдены.")
            return
    
        response_message = "<b>Выберите тип клада</b>\n\n"
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    
        for index, klad_type in enumerate(klad_types):
            klad_type_name, klad_type_forkey = klad_type
            command_text = f"storage_type_{klad_type_forkey}"
            response_message += f"📦 {klad_type_name}\n👉 /{command_text}\n"
            if index != len(klad_types) - 1:
                response_message += "- - - - - - - - - - - - - - - -\n"
            keyboard.add(types.KeyboardButton(f"{klad_type_name} {command_text}"))
    
        keyboard.add(types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        keyboard.add(types.KeyboardButton('📦 Типы клада'))
        keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))
    
        response_message += "\n➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"
    
        await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

    @dp.message_handler(lambda message: re.match('.*storage_type_([a-z0-9]{8})$', message.text))
    async def show_cities_by_storage_type(message: types.Message):
        storage_type_forkey = message.text.split('_')[-1]
        storage_type_name = database.get_klad_type_name_by_forkey(storage_type_forkey)
    
        cities = database.get_cities_by_klad_type(storage_type_forkey)
    
        if not cities:
            await message.reply("Извините, города для выбранного типа клада отсутствуют.")
            return
    
        response_message = (f"<b>Выбран тип клада:</b>\n"
                            f"📦 {storage_type_name}\n"
                            "➖➖➖➖➖➖➖➖➖➖➖\n"
                            "<b>Выберите город</b>\n\n")
    
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for index, (city_id, city_name) in enumerate(cities):
    
            discount = database.get_maximum_discount_by_city_id(city_id)
            discount_text = f" + скидка до {discount}%" if discount > 0 else ""
    
            button_text = f"{city_name} location_st_1_{storage_type_forkey}_{city_id}"
            keyboard.add(types.KeyboardButton(button_text))
            response_message += (f"🚩 <i>{city_name}</i>\n<b>{discount_text}</b>\n"
                                 f"<i>Далее</i> 👉 /location_st_1_{storage_type_forkey}_{city_id}\n")
            if index < len(cities) - 1:
                response_message += "- - - - - - - - - - - - - - - -\n"
    
        response_message += "\n➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"
    
        keyboard.add(types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        keyboard.add(types.KeyboardButton('📦 Типы клада'))
        keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))
    
        await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

    @dp.message_handler(lambda message: re.match(r'.*location_st_1_([a-z0-9]{8})_(\d+)', message.text))
    async def handle_location_st_1(message: types.Message):
        match = re.match(r'.*location_st_1_([a-z0-9]{8})_(\d+)', message.text)
        if match:
            storage_type_forkey, city_id = match.groups()
            klad_type = database.get_klad_type_name_by_forkey(storage_type_forkey)
            city_name = database.get_city_name(city_id)
            districts = database.get_districts_by_city_and_klad_type(city_id, storage_type_forkey)
    
            if not districts:
                await message.reply("Извините, районы для выбранного типа клада отсутствуют.")
                return
    
            district_dict = {}
            for district_id, district_name in districts:
                district_parts = district_name.split(':')
                first_district = district_parts[0]
                third_district = district_parts[2] if len(district_parts) > 2 else None
    
                if third_district and third_district.lower() == "none":
                    button_text = f"location_st_{storage_type_forkey}_{district_id}_{city_id}"
                    key = (first_district, "none")  # Обработка случаев, когда третий район отсутствует
                else:
                    button_text = f"location_735_{storage_type_forkey}_{district_id}_{city_id}"
                    key = (first_district, "735")  # Случаи с третьим районом и разной командой
    
                current_discount = database.get_maximum_discount_by_district_id(district_id)
                if key not in district_dict or district_dict[key][1] < current_discount:
                    district_dict[key] = (district_id, current_discount, button_text, district_name)
    
            response_message = f"<b>Выбран тип клада:</b>\n📦 {klad_type}\n➖➖➖➖➖➖➖➖➖➖➖\n<b>{city_name}</b>\nВыберите район:\n\n"
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            district_list = list(district_dict.items())
            for index, ((first_district, _), (district_id, discount, button_text, district_name)) in enumerate(district_list):
                discount_text = f" + скидка до {discount}%" if discount > 0 else ""
                keyboard.add(types.KeyboardButton(f"{first_district} {button_text}"))
                response_message += f"🚩 {first_district}\n<b>{discount_text}</b>\n👉 /{button_text}\n"
                if index < len(district_list) - 1:
                    response_message += "- - - - - - - - - - - - - - - -\n"
    
            response_message += "\n➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"
            keyboard.add(types.KeyboardButton('🏠 Меню'))
            keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
            keyboard.add(types.KeyboardButton('📦 Типы клада'))
            keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
            keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))
    
            await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
        
    @dp.message_handler(lambda message: re.match(r'.*location_735_([a-z0-9]{8})_(\d+)_(\d+)$', message.text))
    async def handle_third_district_selection(message: types.Message):
        match = re.search(r'location_735_([a-z0-9]{8})_(\d+)_(\d+)$', message.text)
        if match:
            forkey, district_id, city_id = match.groups()
    
            klad_type_name = database.get_klad_type_name_by_forkey(forkey)
            city_name = database.get_city_name(city_id)
            third_districts = database.get_third_districts_by_first_district_id_and_city_id_and_klad_type(district_id,
                                                                                                          city_id,
                                                                                                          forkey)
    
            if third_districts:
                response_message = (f"<b>Выбран тип клада:</b> 📦 {klad_type_name}\n"
                                    f"➖➖➖➖➖➖➖➖➖➖➖\n"
                                    f"<b>{city_name}</b> \nУточните район:\n\n")
                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    
                for index, (third_district_id, third_district_name) in enumerate(third_districts):
                    if third_district_name.lower() != "none":  # Пропускаем районы с названием "none"
                        discount = database.get_maximum_discount_by_district_id(third_district_id)
                        discount_text = f" + скидка до {discount}%" if discount > 0 else ""
                        button_text = f"{third_district_name} location_st_{forkey}_{third_district_id}_{city_id}"
                        keyboard.add(types.KeyboardButton(button_text))
                        response_message += f"🚩 <i>{third_district_name}</i>\n<b>{discount_text}</b>\n <i>Далее</i> 👉 /location_st_{forkey}_{third_district_id}_{city_id}\n"
                        if index < len(third_districts) - 1:
                            response_message += "- - - - - - - - - - - - - - - -\n"
    
                response_message += "\n➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"
                keyboard.add(types.KeyboardButton('🏠 Меню'))
                keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
                keyboard.add(types.KeyboardButton('📦 Типы клада'))
                keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
                keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))
    
                await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
            else:
                await message.reply("Извините, дополнительные районы в этом городе отсутствуют.")

    @dp.message_handler(lambda message: message.text == "💰 Мой последний заказ" or message.text == "/last_order")
    async def handle_last_order(message: types.Message):
        user_id = message.from_user.id

        last_buy_id = database.get_last_buy_id_by_user(user_id, bot_token)

        if last_buy_id and database.check_last_buy_available(last_buy_id):
            last_buy_text = database.get_last_buy_text(last_buy_id)
            response_message = last_buy_text
        else:
            last_buy_id = database.get_random_last_buy_id()

            if last_buy_id:
                last_buy_text = database.get_last_buy_text(last_buy_id)
                database.update_user_last_buy(user_id, last_buy_id, bot_token)
                response_message = last_buy_text
            else:
                response_message = ("<b>❗️ К сожалению,</b>\n"
                                    "у нас нет информации о Вашем последнем заказе.\n"
                                    "➖➖➖➖➖➖➖➖\n"
                                    "Ⓜ️ Вернуться в меню\n"
                                    "<i>Жми</i> 👉 /menu")

        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        keyboard.add(types.KeyboardButton('📦 Типы клада'))
        keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

        await message.answer(response_message, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

    @dp.message_handler(lambda message: message.text == "/balance" or message.text == "💰 Баланс")
    async def handle_balance(message: types.Message):
        response_message = "Баланс: 0,00 руб"

        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        keyboard.add(types.KeyboardButton('📦 Типы клада'))
        keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

        await message.answer(response_message, reply_markup=keyboard)

    @dp.message_handler(lambda message: message.text == "💰 Пополнить баланс")
    async def handle_balance_replenishment(message: types.Message):
        response_message = ("Введите сумму на какую хотите пополнить баланс.\n\n"
                            "Минимальная сумма пополнения не менее 300 руб и максимальная не более 10000 руб.")
        await message.answer(response_message)
        await BalanceStates.replenishment_amount.set()

    @dp.message_handler(state=BalanceStates.replenishment_amount)
    async def process_replenishment_amount(message: types.Message, state: FSMContext):
        try:
            amount = int(message.text)
            if 300 <= amount <= 10000:
                response_message = f"Вы действительно хотите пополнить баланс на сумму {amount}?"
                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                keyboard.add(types.KeyboardButton(f"☑️ Перейти к оплате up_balance_{amount}"))
                keyboard.add(types.KeyboardButton('🏠 Меню'))
                keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
                keyboard.add(types.KeyboardButton('📦 Типы клада'))
                keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
                keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

                # Добавляем остальные кнопки, если нужно
                await message.answer(response_message, reply_markup=keyboard)
                await state.finish()
                return
        except ValueError:
            pass

        # Если сумма не прошла проверку, повторяем запрос
        response_message = ("Введите сумму на какую хотите пополнить баланс.\n\n"
                            "Минимальная сумма пополнения не менее 300 руб и максимальная не более 10000 руб.")
        await message.answer(response_message)

    @dp.message_handler(lambda message: re.match('.*up_balance_(\\d+)$', message.text))
    async def process_up_balance_command(message: types.Message):
        amount_match = re.match('.*up_balance_(\\d+)', message.text)
        if amount_match:
            amount = int(amount_match.group(1))
            await message.answer("Подождите... Ваш запрос обрабатывается...")
            await asyncio.sleep(1)

            active_payment_types = database.get_active_payment_types()

            payment_options = {
                'btc': f"<i>💰 Bitcoin (BTC)</i> 👉 /up_balance{amount}_22",
                'ltc': f"<i>💰 Litecoin (LTC)</i> 👉 /up_balance{amount}_24",
                'card': [f"<i>💰 Ручная оплата</i> 👉 /up_balance{amount}_10",
                         f"<i>💰 Оплата картой банка</i> 👉 /up_balance{amount}_53"]
            }

            response_message = "❗️ Выберите способ оплаты:\n\n"
            for payment_type, info in payment_options.items():
                if payment_type in active_payment_types:
                    if isinstance(info, list):
                        for item in info:
                            response_message += f"{item}\n\n"
                    else:
                        response_message += f"{info}\n\n"

            response_message += "➖➖➖➖➖➖➖➖➖➖➖\nⓂ️ Вернуться в меню\n<i>Жми</i> 👉 /menu"

            # Создаём клавиатуру
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            keyboard.add(types.KeyboardButton('🏠 Меню'))
            keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
            keyboard.add(types.KeyboardButton('📦 Типы клада'))
            keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
            keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

            await message.answer(response_message, parse_mode="HTML", reply_markup=keyboard)

    @dp.message_handler(lambda message: re.match(r'.*up_balance(\d+)_(22|24)', message.text), state=None)
    async def crypto_payment(message: types.Message, state: FSMContext):
        await OrderState.waiting_for_payment_balance.set()
    
        match = re.match(r'.*up_balance(\d+)_(22|24)', message.text)
        rub_amount, payment_method = match.groups()
    
        crypto_type = None
        crypto_price = 0
    
        if payment_method == "22":
            crypto_type = "BTC"
            crypto_price = btc_price  # Здесь должен быть ваш метод для получения цены BTC
        elif payment_method == "24":
            crypto_type = "LTC"
            crypto_price = ltc_price  # Здесь должен быть ваш метод для получения цены LTC
    
        if not crypto_type:
            await message.answer("Произошла ошибка при определении метода платежа.")
            await state.finish()
            return
    
        cf = database.get_payment_coefficient(crypto_type.lower())  # Получаем коэффициент для крипто-валюты
    
        crypto_details = database.get_payment_details(crypto_type.lower())
        crypto_addresses = crypto_details.split('\n')
        crypto_address = random.choice(crypto_addresses) if crypto_addresses else f"{crypto_type} адрес не найден"
    
        price_crypto = round(int(rub_amount) / crypto_price * cf, 8)  # Умножаем сумму криптовалюты на коэффициент
    
        order_number = database.get_and_increment_purchases_count()
        start_time = datetime.now()
    
        await state.update_data(
            order_number=order_number,
            crypto_type=crypto_type,
            crypto_address=crypto_address,
            rub_amount=rub_amount,
            price_crypto=price_crypto,
            start_time=start_time
        )
    
        response_message = (f"💰 Вы сформировали заявку на пополнение баланса на сумму {rub_amount} руб.\n"
                            f"До конца резерва осталось 59 минут.\n"
                            f"Номер заказа: {order_number}.\n"
                            f"➖➖➖➖➖➖➖➖➖\n\n"
                            f"Переведите на адрес {crypto_type}:\n"
                            f"{crypto_address}\n"
                            f"сумму {price_crypto:.8f} {crypto_type}\n\n"
                            f"➖➖➖➖➖➖➖➖➖\n"
                            f"✔️ Проверить оплату\n"
                            f"Жми 👉 /order_check\n\n"
                            f"🚫 Отменить заказ\n"
                            f"Жми 👉 /order_cancel")
    
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton("🚫 Отменить заказ"))
        keyboard.add(types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        keyboard.add(types.KeyboardButton('📦 Типы клада'))
        keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))
    
        await message.answer("Подождите... Ваш запрос обрабатывается...")
        await asyncio.sleep(1)
        await message.answer(response_message, reply_markup=keyboard, parse_mode="HTML")

    @dp.message_handler(lambda message: message.text not in ["/order_cancel", "🚫 Отменить заказ",
                                                             "✔️ Подтверждаю отмену"] and message.text is not None,
                        state=OrderState.waiting_for_payment_balance)
    async def check_order_payment(message: types.Message, state: FSMContext):
        data = await state.get_data()
        start_time = data['start_time']
        time_passed = datetime.now() - start_time
        time_left = timedelta(minutes=59) - time_passed

        order_number = data['order_number']
        rub_amount = data['rub_amount']
        crypto_type = data['crypto_type']
        crypto_address = data['crypto_address']
        price_crypto = data['price_crypto']

        minutes_left = max(int(time_left.total_seconds() // 60), 0)  # Гарантируем, что значение не отрицательное

        if time_left.total_seconds() <= 0:
            await message.answer("Время на оплату вашего заказа истекло.", reply_markup=types.ReplyKeyboardRemove())
            await state.finish()  # Завершаем состояние
        else:
            response_message = (
                f"❗️ Напоминаем,\n"
                f"что вы сформировали заявку на пополнение баланса на сумму {rub_amount} руб.\n"
                f"До конца резерва осталось {minutes_left} минут.\n"
                f"Номер заказа: {order_number}.\n"
                "➖➖➖➖➖➖➖➖➖\n\n"
                f"Переведите на адрес {crypto_type}:\n"
                f"{crypto_address}\n"
                f"сумму {price_crypto:.8f} {crypto_type} BTC\n\n"  # Предположим, что .8f нужно для BTC и LTC аналогично
                "➖➖➖➖➖➖➖➖➖\n"
                "✔️ Проверить оплату\n"
                "Жми 👉 /order_check\n\n"
                "🚫 Отменить заказ\n"
                "Жми 👉 /order_cancel"
            )

            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            keyboard.add(types.KeyboardButton("✔️ Проверить оплату"), types.KeyboardButton("🚫 Отменить заказ"))
            keyboard.add(types.KeyboardButton('🏠 Меню'))
            keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
            keyboard.add(types.KeyboardButton('📦 Типы клада'))
            keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
            keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

            await message.answer(response_message, reply_markup=keyboard, parse_mode="HTML")

    @dp.message_handler(lambda message: re.match(r'.*up_balance(\d+)_10', message.text), state=None)
    async def manual_payment_initiation(message: types.Message, state: FSMContext):
        await OrderState.waiting_for_payment_manualpay.set()

        match = re.match(r'.*up_balance(\d+)_10', message.text)
        rub_amount = float(match.group(1))
        rub_amount_fee = convert(rub_amount)
        rub_amount_fee = int(rub_amount_fee)

        order_number = database.get_and_increment_purchases_count()
        start_time = datetime.now()

        await state.update_data(
            order_number=order_number,
            rub_amount=rub_amount_fee,
            start_time=start_time
        )

        response_message = (
            f"💰 Вы сформировали заявку на пополнение баланса на сумму {rub_amount_fee} руб.\n"
            "До конца резерва осталось 59 минут.\n"
            f"Номер заказа: {order_number}.\n\n"
            "➖➖➖➖➖➖➖➖➖\n"
                                    f"Скопируйте и напишите оператору @hvnmm247  текст данного сообщения для уточнения НОМЕРА КАРТЫ!!!).\n"
                                    f"ВНИМАНИЕ! перед каждой оплатой уточняйте  карту у оператора, во избежание потери ваших денег!\n\n"
                                    f"В комментарии к платежу ничего указывать не нужно.\n\n"
                                    f"<b>Внимание!</b> После оплаты сообщите оператору:\n"
                                    f"1. номер заказа <b>{order_number}</b>\n"
                                    f"2. <b>ОПЛАЧЕННУЮ СУММУ</b>\n"
                                    f"3. дату и ВРЕМЯ оплаты\n\n"
                                    f"<b>Внимание!</b> Сообщать об оплате нужно именно оператору, а не боту! Однако адрес выдаст Вам бот.\n\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "✔️ Проверить оплату\n"
            "<i>Жми</i> 👉 /order_check\n\n"
            "🚫 Отменить заказ\n"
            "<i>Жми</i> 👉 /order_cancel"
        )

        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton("🚫 Отменить заказ"))
        keyboard.add(types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        keyboard.add(types.KeyboardButton('📦 Типы клада'))
        keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

        await message.answer(response_message, reply_markup=keyboard, parse_mode="HTML")

    @dp.message_handler(lambda message: message.text not in ["/order_cancel", "🚫 Отменить заказ",
                                                             "✔️ Подтверждаю отмену"] and message.text is not None,
                        state=OrderState.waiting_for_payment_manualpay)
    async def check_order_manual_payment(message: types.Message, state: FSMContext):
        data = await state.get_data()
        start_time = data['start_time']
        time_passed = datetime.now() - start_time
        time_left = timedelta(minutes=59) - time_passed
        minutes_left = max(int(time_left.total_seconds() // 60), 0)

        order_number = data['order_number']
        rub_amount = data['rub_amount']
        rub_amount = int(convert(rub_amount))
        rub_amount_fee = convert(rub_amount)

        response_message = (
            "❗️ Напоминаем,\n"
            f"что вы сформировали заявку на пополнение баланса на сумму {rub_amount} руб.\n"
            f"Номер заказа: {order_number}.\n"
            f"До конца резерва осталось {minutes_left} минут.\n\n"
            "➖➖➖➖➖➖➖➖➖\n"
                                    f"Скопируйте и напишите оператору @hvnmm247  текст данного сообщения для уточнения НОМЕРА КАРТЫ!!!).\n"
                                    f"ВНИМАНИЕ! перед каждой оплатой уточняйте  карту у оператора, во избежание потери ваших денег!\n\n"
                                    f"В комментарии к платежу ничего указывать не нужно.\n\n"
                                    f"<b>Внимание!</b> После оплаты сообщите оператору:\n"
                                    f"1. номер заказа <b>{order_number}</b>\n"
                                    f"2. <b>ОПЛАЧЕННУЮ СУММУ</b>\n"
                                    f"3. дату и ВРЕМЯ оплаты\n\n"
                                    f"<b>Внимание!</b> Сообщать об оплате нужно именно оператору, а не боту! Однако адрес выдаст Вам бот.\n\n"
            "➖➖➖➖➖➖➖➖➖\n\n"
            "✔️ Проверить оплату\n"
            "<i>Жми</i> 👉 /order_check\n\n"
            "🚫 Отменить заказ\n"
            "<i>Жми</i> 👉 /order_cancel"
        )

        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton("✔️ Проверить оплату"), types.KeyboardButton("🚫 Отменить заказ"))
        keyboard.add(types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        keyboard.add(types.KeyboardButton('📦 Типы клада'))
        keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

        await message.answer(response_message, reply_markup=keyboard, parse_mode="HTML")

    @dp.message_handler(lambda message: re.match(r'.*up_balance(\d+)_53', message.text), state=None)
    async def card_payment(message: types.Message, state: FSMContext):
        await OrderState.waiting_for_payment_card.set()

        match = re.match(r'.*up_balance(\d+)_53', message.text)
        rub_amount = match.group(1)
        cf = database.get_payment_coefficient("card")
        rub_amount_with_fee = int(rub_amount) * cf
        rub_amount_with_fee = convert(rub_amount_with_fee)

        order_number = database.get_and_increment_purchases_count()
        card_details = database.get_payment_details('card').split('\n')
        random_card = random.choice(card_details) if card_details else "Карта не найдена"

        await state.update_data(
            order_number=order_number,
            rub_amount=rub_amount,
            rub_amount_with_fee=rub_amount,
            card_number=random_card,
            start_time=datetime.now()
        )

        response_message = (
            f"💰 Вы сформировали заявку на пополнение баланса на сумму {rub_amount} руб.\n"
            "До конца резерва осталось 25 минут.\n"
            f"Номер заказа: {order_number}.\n"
            "➖➖➖➖➖➖➖➖➖\n\n"
            "Переведите на карту\n"
            f"{random_card}\n"
            f"точную сумму одной транзакцией {rub_amount_with_fee} руб.\n\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "✔️ Проверить оплату\n"
            "Жми 👉 /order_check\n\n"
            "🚫 Отменить заказ\n"
            "Жми 👉 /order_cancel"
        )

        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton("🚫 Отменить заказ"))
        keyboard.add(types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        keyboard.add(types.KeyboardButton('📦 Типы клада'))
        keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

        await message.answer(response_message, reply_markup=keyboard, parse_mode="HTML")

    @dp.message_handler(lambda message: message.text not in ["/order_cancel", "🚫 Отменить заказ",
                                                             "✔️ Подтверждаю отмену"] and message.text is not None,
                        state=OrderState.waiting_for_payment_card)
    async def check_card_payment(message: types.Message, state: FSMContext):
        data = await state.get_data()
        start_time = data['start_time']
        time_passed = datetime.now() - start_time
        time_left = timedelta(minutes=25) - time_passed
        rub_amount = data['rub_amount']
        rub_amount_with_fee = float(data['rub_amount_with_fee'])
        cf = database.get_payment_coefficient("card")
        rub_amount_with_fee = int(rub_amount_with_fee * cf)

        minutes_left = max(int(time_left.total_seconds() // 60), 0)

        response_message = (
            f"💰 Вы сформировали заявку на пополнение баланса на сумму {rub_amount} руб.\n"
            f"До конца резерва осталось {minutes_left} минут.\n"
            f"Номер заказа: {data['order_number']}.\n"
            "➖➖➖➖➖➖➖➖➖\n\n"
            "Переведите на карту\n"
            f"{data['card_number']}\n"
            f"точную сумму одной транзакцией {rub_amount_with_fee} руб.\n\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "✔️ Проверить оплату\n"
            "Жми 👉 /order_check\n\n"
            "🚫 Отменить заказ\n"
            "Жми 👉 /order_cancel"
        )

        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton("✔️ Проверить оплату"), types.KeyboardButton("🚫 Отменить заказ"))
        keyboard.add(types.KeyboardButton('🏠 Меню'))
        keyboard.add(types.KeyboardButton('📦 Все продукты'), types.KeyboardButton('👉 Локации'))
        keyboard.add(types.KeyboardButton('📦 Типы клада'))
        keyboard.add(types.KeyboardButton('💰 Мой последний заказ'), types.KeyboardButton('❓ Помощь'))
        keyboard.add(types.KeyboardButton('💰 Баланс'), types.KeyboardButton('💰 Пополнить баланс'))

        await message.answer(response_message, reply_markup=keyboard, parse_mode="HTML")

    async def start_order_timer(message: types.Message, state: FSMContext, order_number: str, delay: int = 15 * 60,
                                reminders: int = 4):
        for i in range(reminders):
            await asyncio.sleep(delay)
            data = await state.get_data()
    
            start_time = data['start_time']
            time_passed = datetime.now() - start_time
            time_left = timedelta(minutes=59) - time_passed
    
            if time_left.total_seconds() <= 0:
                break
    
            response_message = (
                f"<b>❗️ Напоминаем,</b>\n"
                f"что за Вами зарезервирован\n"
                f"<b>{data['product_name']}</b> на сумму {data['price_rub']} руб\n"
                f"в районе <b>{data['third_district']}</b>.\n"
                f"Номер заказа: {order_number}.\n"
                f"До конца резерва осталось {int(time_left.total_seconds() // 60)} минут.\n\n"
                f"➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"Вам необходимо оплатить <b>{data['price_rub']} руб</b>.\n"
                f"Переведите на адрес {data['crypto_type']}:\n"
                f"<b>{data['crypto_address']}</b>\n"
                f"сумму <b>{data['price_crypto']} {data['crypto_type']}</b>"
            )
    
            if time_left.total_seconds() > 0:
                await message.answer(response_message, parse_mode=types.ParseMode.HTML)
    
        new_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        new_keyboard.add(KeyboardButton('🏠 Меню'))
        new_keyboard.row(KeyboardButton('📦 Все продукты'), KeyboardButton('👉 Локации'))
        new_keyboard.add(KeyboardButton('📦 Типы клада'))
        new_keyboard.row(KeyboardButton('💰 Мой последний заказ'), KeyboardButton('❓ Помощь'))
        new_keyboard.row(KeyboardButton('💰 Баланс'), KeyboardButton('💰 Пополнить баланс'))
    
        await message.answer(
            f"<b>❗️ Оплата не поступила</b>\n"
            f"Заказ {order_number} отменен!\n\n"
            f"Ⓜ️ Вернуться в меню\n"
            f"Жми 👉 /menu",
            reply_markup=new_keyboard,
            parse_mode=types.ParseMode.HTML
        )
        await state.finish()
    
    async def start_order_timer2(message: types.Message, state: FSMContext, order_number: str, payment_method: str,
                                 delay: int = 10 * 60, reminders: int = 4):
        for i in range(reminders):
            await asyncio.sleep(delay)
            data = await state.get_data()
    
            start_time = data['start_time']
            time_passed = datetime.now() - start_time
            time_left = timedelta(minutes=25) - time_passed
    
            if time_left.total_seconds() <= 0:
                break
    
            if payment_method == "hand_payment":
                response_message = (
                    f"<b>❗️ Напоминаем,</b>\n"
                    f"что за Вами зарезервирован\n"
                    f"<b>{data['product_name']}</b> на сумму {data['price_rub']} руб\n"
                    f"в районе <b>{data['third_district']}</b>.\n"
                    f"Номер заказа: <b>{order_number}</b>.\n"
                    f"До конца резерва осталось {max(int(time_left.total_seconds() // 60), 0)} минут.\n\n"
                    f"➖➖➖➖➖➖➖➖➖➖➖➖\n\n"
                                    f"Скопируйте и напишите оператору @hvnmm247  текст данного сообщения для уточнения НОМЕРА КАРТЫ!!!).\n"
                                    f"ВНИМАНИЕ! перед каждой оплатой уточняйте  карту у оператора, во избежание потери ваших денег!\n\n"
                                    f"В комментарии к платежу ничего указывать не нужно.\n\n"
                                    f"<b>Внимание!</b> После оплаты сообщите оператору:\n"
                                    f"1. номер заказа <b>{order_number}</b>\n"
                                    f"2. <b>ОПЛАЧЕННУЮ СУММУ</b>\n"
                                    f"3. дату и ВРЕМЯ оплаты\n\n"
                                    f"<b>Внимание!</b> Сообщать об оплате нужно именно оператору, а не боту! Однако адрес выдаст Вам бот.\n\n"
                )
            elif payment_method == "card":
                card_details = data['payment_details']
                response_message = (
                    f"<b>❗️ Напоминаем,</b>\n"
                    f"что за Вами зарезервирован\n"
                    f"<b>{data['product_name']}</b> на сумму {data['price_rub']} руб\n"
                    f"в районе <b>{data['third_district']}</b>.\n"
                    f"Номер заказа: {order_number}.\n"
                    f"До конца резерва осталось {max(int(time_left.total_seconds() // 60), 0)} минут.\n\n"
                    f"➖➖➖➖➖➖➖➖➖➖➖➖\n\n"
                    f"Переведите на карту\n"
                    f"{card_details}\n"
                    f"точную сумму одной транзакцией {data['price_rub']} руб.\n\n"
                    f"➖➖➖➖➖➖➖➖➖➖➖➖\n"
                    f"✔️ Проверить оплату\n"
                    f"Жми 👉 /order_check\n\n"
                    f"🚫 Отменить заказ\n"
                    f"Жми 👉 /order_cancel"
                )
    
            if time_left.total_seconds() > 0:
                await message.answer(response_message, parse_mode=types.ParseMode.HTML)
    
        new_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        new_keyboard.add(KeyboardButton('🏠 Меню'))
        new_keyboard.row(KeyboardButton('📦 Все продукты'), KeyboardButton('👉 Локации'))
        new_keyboard.add(KeyboardButton('📦 Типы клада'))
        new_keyboard.row(KeyboardButton('💰 Мой последний заказ'), KeyboardButton('❓ Помощь'))
        new_keyboard.row(KeyboardButton('💰 Баланс'), KeyboardButton('💰 Пополнить баланс'))
    
        await message.answer(
            f"<b>❗️ Оплата не поступила</b>\n"
            f"Заказ {order_number} отменен!\n\n"
            f"Ⓜ️ Вернуться в меню\n"
            f"Жми 👉 /menu",
            reply_markup=new_keyboard,
            parse_mode=types.ParseMode.HTML
        )
        await state.finish()

def convert(value):
    if value is None:
        return None
    try:
        float_value = float(value)
        if float_value == int(float_value):
            return int(float_value)
        else:
            return float_value
    except ValueError:
        return value

