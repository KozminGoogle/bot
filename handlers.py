# handlers.py
from aiogram import Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession
from db import get_session
from models import MasterClass
import asyncio
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from models import MasterClass, Slot, Registration, Team, User
from config import ADMIN_TG_ID
import gspread
from google.oauth2.service_account import Credentials

class TeamReg(StatesGroup):
    waiting_team_name = State()
    waiting_members = State()

class AdminAddMK(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_photo = State()
    waiting_max_people = State()
    waiting_is_team = State()
    waiting_slot = State()
    waiting_slot_max = State()

# --- Google Sheets ---
GSHEET_ID = "1lxjmF-SSLixQN5dBNeRS88_XnWvx5H_BVBgyqgVJLk4"  # замените на свой
GSHEET_RANGE = "spisok"  # например, первый лист
CREDS_PATH = "credentials.json"  # путь к вашему файлу

creds = Credentials.from_service_account_file(CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
gs_client = gspread.authorize(creds)
gs_sheet = gs_client.open_by_key(GSHEET_ID).sheet1

def add_registration_to_gsheet(user_name, user_tg_id, mk_title, slot_time):
    gs_sheet.append_row([user_name, user_tg_id, mk_title, slot_time.strftime("%d.%m %H:%M")])

async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Мастер-классы", callback_data="show_mk:0")]
        ]
    )
    await message.answer("Добро пожаловать! [Заглушка приветствия]", reply_markup=kb, parse_mode="HTML")

async def show_master_class(query: CallbackQuery, session: AsyncSession, page: int = 0):
    mks = await session.execute(MasterClass.__table__.select())
    mks = mks.fetchall()
    if not mks:
        await query.message.answer("Мастер-классы пока не добавлены.")
        return
    mk = mks[page % len(mks)]
    text = f"Мастер-класс: {mk.title}\n{mk.description}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️", callback_data=f"show_mk:{(page-1)%len(mks)}"),
             InlineKeyboardButton(text="➡️", callback_data=f"show_mk:{(page+1)%len(mks)}")],
            [InlineKeyboardButton(text="Записаться", callback_data=f"signup:{mk.id}")]
        ]
    )
    if mk.photo:
        try:
            await query.message.edit_media(
                media=InputMediaPhoto(media=mk.photo, caption=text, parse_mode="HTML"),
                reply_markup=kb
            )
        except Exception:
            await query.message.answer_photo(mk.photo, caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        try:
            await query.message.edit_text(text, reply_markup=kb)
        except Exception:
            await query.message.answer(text, reply_markup=kb, parse_mode="HTML")

async def show_slots(query: CallbackQuery, session: AsyncSession, mk_id: int):
    mk = await session.get(MasterClass, mk_id)
    slots = await session.execute(Slot.__table__.select().where(Slot.master_class_id == mk_id))
    slots = slots.fetchall()
    if not slots:
        await query.message.answer("Нет доступных слотов для этого мастер-класса.")
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{slot.time.strftime('%d.%m %H:%M')} (осталось: {slot.max_people - len((await session.execute(Registration.__table__.select().where(Registration.slot_id == slot.id))).fetchall())})",
                callback_data=f"slot:{slot.id}")]
            for slot in slots
        ] + [
            [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu"), InlineKeyboardButton(text="Мой профиль", callback_data="profile")]
        ]
    )
    if mk.is_team:
        text = "Выберите слот для командной регистрации:"
    else:
        text = "Выберите слот:"
    try:
        await query.message.edit_text(text, reply_markup=kb)
    except Exception:
        await query.message.answer(text, reply_markup=kb)

async def menu_handler(query: CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Мастер-классы", callback_data="show_mk:0")],
            [InlineKeyboardButton(text="Мой профиль", callback_data="profile")]
        ]
    )
    try:
        await query.message.edit_text("Главное меню:", reply_markup=kb)
    except Exception as e:
        if "message is not modified" in str(e):
            pass  # игнорируем ошибку
        else:
            await query.message.answer("Главное меню:", reply_markup=kb)

async def profile_handler(query: CallbackQuery):
    async for session in get_session():
        from models import User, Registration, Slot, MasterClass, Team
        user = await session.execute(User.__table__.select().where(User.tg_id == str(query.from_user.id)))
        user = user.fetchone()
        if not user:
            await query.message.answer("Вы ещё не регистрировались на мастер-классы.")
            return
        regs = await session.execute(Registration.__table__.select().where(Registration.user_id == user.id))
        regs = regs.fetchall()
        if not regs:
            await query.message.answer("У вас нет записей на мастер-классы.")
            return
        text = "Ваши записи:\n"
        for reg in regs:
            slot = await session.get(Slot, reg.slot_id)
            mk = await session.get(MasterClass, slot.master_class_id)
            text += f"{mk.title} — {slot.time.strftime('%d.%m %H:%M')}\n"
            team = await session.execute(Team.__table__.select().where(Team.registration_id == reg.id))
            team = team.fetchone()
            if team:
                text += f"Команда: {team.name} ({', '.join(team.members)})\n"
        await query.message.answer(text)

async def signup_slot(query: CallbackQuery, session: AsyncSession, slot_id: int, user_tg_id: int, state: FSMContext):
    slot = await session.get(Slot, slot_id)
    mk = await session.get(MasterClass, slot.master_class_id)
    registrations = await session.execute(Registration.__table__.select().where(Registration.slot_id == slot_id))
    registrations = registrations.fetchall()
    if len(registrations) >= slot.max_people:
        await query.message.answer("😔 В этом слоте уже нет мест. Попробуйте выбрать другой! 🕓")
        return
    # Проверка и создание пользователя
    user = await session.execute(User.__table__.select().where(User.tg_id == str(query.from_user.id)))
    user = user.fetchone()
    if not user:
        new_user = User(tg_id=str(query.from_user.id), name=query.from_user.full_name)
        session.add(new_user)
        await session.commit()
        user_id = new_user.id
        user_name = new_user.name
    else:
        user_id = user.id
        user_name = user.name
    if mk.is_team:
        await state.set_state(TeamReg.waiting_team_name)
        await state.update_data(slot_id=slot_id)
        await query.message.answer("🤝 Введите название вашей команды:")
    else:
        reg = Registration(user_id=user_id, slot_id=slot_id)
        session.add(reg)
        await session.commit()
        # --- запись в Google Sheets ---
        try:
            add_registration_to_gsheet(user_name, query.from_user.id, mk.title, slot.time)
        except Exception as e:
            print(f"Ошибка Google Sheets: {e}")
        await query.message.answer("✅ Вы успешно записаны! Ждём вас на мастер-классе! 🎉")

async def team_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(team_name=message.text)
    await state.set_state(TeamReg.waiting_members)
    await message.answer("Введите участников команды через запятую (имя или @username):")

async def team_members_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    team_name = data["team_name"]
    slot_id = data["slot_id"]
    members = [m.strip() for m in message.text.split(",") if m.strip()]
    async for session in get_session():
        # Получаем или создаём пользователя
        user = await session.execute(User.__table__.select().where(User.tg_id == str(message.from_user.id)))
        user = user.fetchone()
        if not user:
            new_user = User(tg_id=str(message.from_user.id), name=message.from_user.full_name)
            session.add(new_user)
            await session.commit()
            user_id = new_user.id
        else:
            user_id = user.id
        reg = Registration(user_id=user_id, slot_id=slot_id)
        session.add(reg)
        await session.flush()
        team = Team(name=team_name, members=members, registration_id=reg.id)
        session.add(team)
        await session.commit()
    await message.answer(f"🎊 Команда <b>{team_name}</b> успешно зарегистрирована!\nУчастники: {', '.join(members)}", parse_mode="HTML")
    await state.clear()

async def admin_add_mk(message: types.Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_TG_ID):
        await message.answer("Нет прав.")
        return
    await state.set_state(AdminAddMK.waiting_title)
    await message.answer("Введите название мастер-класса:")

async def admin_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AdminAddMK.waiting_description)
    await message.answer("Введите описание мастер-класса:")

async def admin_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AdminAddMK.waiting_photo)
    await message.answer("Отправьте фото мастер-класса или напишите 'нет':")

async def admin_photo(message: types.Message, state: FSMContext):
    if message.photo:
        file_id = message.photo[-1].file_id
        await state.update_data(photo=file_id)
    else:
        await state.update_data(photo=None)
    await state.set_state(AdminAddMK.waiting_max_people)
    await message.answer("Введите максимальное количество участников:")

async def admin_max_people(message: types.Message, state: FSMContext):
    await state.update_data(max_people=int(message.text))
    await state.set_state(AdminAddMK.waiting_is_team)
    await message.answer("Это командный мастер-класс? (да/нет):")

async def admin_is_team(message: types.Message, state: FSMContext):
    data = await state.get_data()
    is_team = 1 if message.text.lower() in ["да", "yes", "y"] else 0
    async for session in get_session():
        mk = MasterClass(
            title=data["title"],
            description=data["description"],
            photo=data["photo"],
            max_people=data["max_people"],
            is_team=is_team
        )
        session.add(mk)
        await session.commit()
        await state.update_data(mk_id=mk.id)
    await message.answer("🆕 Мастер-класс успешно добавлен! Теперь добавьте слоты (даты и лимиты).\n\nВведите дату и время слота в формате <b>ДД.ММ ЧЧ:ММ</b> или напишите 'стоп' для завершения:", parse_mode="HTML")
    await state.set_state(AdminAddMK.waiting_slot)

async def admin_slot(message: types.Message, state: FSMContext):
    if message.text.lower() == "стоп":
        await message.answer("✅ Добавление мастер-класса завершено!")
        await state.clear()
        return
    try:
        from datetime import datetime
        dt = datetime.strptime(message.text, "%d.%m %H:%M")
    except Exception:
        await message.answer("❌ Неверный формат! Попробуйте ещё раз: <b>ДД.ММ ЧЧ:ММ</b>", parse_mode="HTML")
        return
    await state.set_state(AdminAddMK.waiting_slot_max)
    await state.update_data(slot_time=dt)
    await message.answer("Введите лимит мест для этого слота:")

async def admin_slot_max(message: types.Message, state: FSMContext):
    try:
        max_people = int(message.text)
    except Exception:
        await message.answer("❌ Введите число!")
        return
    data = await state.get_data()
    async for session in get_session():
        slot = Slot(master_class_id=data["mk_id"], time=data["slot_time"], max_people=max_people)
        session.add(slot)
        await session.commit()
    await message.answer("🕓 Слот добавлен! Введите следующий слот или 'стоп' для завершения.", parse_mode="HTML")
    await state.set_state(AdminAddMK.waiting_slot)

async def callback_handler(query: CallbackQuery, state: FSMContext):
    async for session in get_session():
        await query.answer()  # отвечаем на callback сразу
        if query.data.startswith("show_mk:"):
            page = int(query.data.split(":")[1])
            await show_master_class(query, session, page)
        elif query.data.startswith("signup:"):
            mk_id = int(query.data.split(":")[1])
            await show_slots(query, session, mk_id)
        elif query.data.startswith("slot:"):
            slot_id = int(query.data.split(":")[1])
            user_id = query.from_user.id
            await signup_slot(query, session, slot_id, user_id, state)
        elif query.data == "menu":
            await menu_handler(query)
        elif query.data == "profile":
            await profile_handler(query)
        await query.answer()

def register_handlers(dp: Dispatcher):
    dp.message.register(cmd_start, CommandStart())
    dp.callback_query.register(callback_handler, F.data.startswith("show_mk:") | F.data.startswith("signup:") | F.data.startswith("slot:"))
    dp.callback_query.register(callback_handler, F.data == "menu")
    dp.callback_query.register(callback_handler, F.data == "profile")
    dp.message.register(team_name_handler, TeamReg.waiting_team_name)
    dp.message.register(team_members_handler, TeamReg.waiting_members)
    dp.message.register(admin_add_mk, F.text == "/addmk")
    dp.message.register(admin_title, AdminAddMK.waiting_title)
    dp.message.register(admin_description, AdminAddMK.waiting_description)
    dp.message.register(admin_photo, AdminAddMK.waiting_photo)
    dp.message.register(admin_max_people, AdminAddMK.waiting_max_people)
    dp.message.register(admin_is_team, AdminAddMK.waiting_is_team)
    dp.message.register(admin_slot, AdminAddMK.waiting_slot)
    dp.message.register(admin_slot_max, AdminAddMK.waiting_slot_max)
