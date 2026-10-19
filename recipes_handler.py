import asyncio

import aiohttp
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

CATEGORIES_URL = "https://www.themealdb.com/api/json/v1/1/categories.php"


class RecipeStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_recipes = State()


@router.message(Command("category_search_random"))
async def cmd_category_search_random(message: Message, state: FSMContext):
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("Напиши так: /category_search_random 3")
        return

    count = int(args[1])
    await state.set_data({"count": count})

    async with aiohttp.ClientSession() as session:
        async with session.get(CATEGORIES_URL) as resp:
            data = await resp.json()

    categories = [c["strCategory"] for c in data["categories"]]

    buttons = []
    row = []
    for cat in categories:
        row.append(InlineKeyboardButton(text=cat, callback_data=f"cat:{cat}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери категорию:", reply_markup=keyboard)

    await state.set_state(RecipeStates.waiting_for_category)

@router.callback_query(F.data.startswith("cat:"))
async def process_category(callback: CallbackQuery, state: FSMContext):
    # Достаём категорию из кнопки
    category = callback.data.split(":", 1)[1]

    data = await state.get_data()
    count = data.get("count", 1)

    url = f"https://www.themealdb.com/api/json/v1/1/filter.php?c={category}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()

    meals = data.get("meals") or []
    if not meals:
        await callback.message.answer("В этой категории нет рецептов 😔")
        await callback.answer()
        await state.clear()
        return

    from random import choices
    chosen = choices(meals, k=min(count, len(meals)))

    from googletrans import Translator
    translator = Translator()
    names_ru = []
    for meal in chosen:
        try:
            translated = translator.translate(meal["strMeal"], dest="ru").text
        except Exception:
            translated = meal["strMeal"]
        names_ru.append(translated)

    ids = [meal["idMeal"] for meal in chosen]
    await state.update_data(recipe_ids=ids)

    text = "Случайные рецепты:\n\n" + "\n".join(f"• {n}" for n in names_ru)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Показать рецепты", callback_data="show_recipes")]
    ])
    await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()

    await state.set_state(RecipeStates.waiting_for_recipes)

async def fetch_recipe(session, meal_id):
    url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={meal_id}"
    async with session.get(url) as resp:
        data = await resp.json()
    return data["meals"][0]

def translate_safe(translator, text):
    try:
        return translator.translate(text, dest="ru").text
    except Exception:
        return text


@router.callback_query(F.data == "show_recipes")
async def process_show_recipes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ids = data.get("recipe_ids", [])

    if not ids:
        await callback.message.answer("Сначала выбери категорию через /category_search_random")
        await callback.answer()
        await state.clear()
        return

    await callback.message.answer("Готовлю рецепты... ⏳")
    await callback.answer()

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_recipe(session, meal_id) for meal_id in ids]
        meals = await asyncio.gather(*tasks)

    from googletrans import Translator
    translator = Translator()

    for meal in meals:
        # Название
        name_ru = translate_safe(translator, meal["strMeal"])
        # Рецепт
        instructions_ru = translate_safe(translator, meal["strInstructions"] or "")

        ingredients = []
        for i in range(1, 21):
            ing = meal.get(f"strIngredient{i}")
            measure = meal.get(f"strMeasure{i}")
            if ing and ing.strip():
                ing_ru = translate_safe(translator, ing.strip())
                if measure and measure.strip():
                    ingredients.append(f"{ing_ru} — {measure.strip()}")
                else:
                    ingredients.append(ing_ru)

        text = (
            f"<b>{name_ru}</b>\n\n"
            f"<b>Рецепт:</b>\n{instructions_ru}\n\n"
            f"<b>Ингредиенты:</b> {', '.join(ingredients)}"
        )
        await callback.message.answer(text)

    await state.clear()