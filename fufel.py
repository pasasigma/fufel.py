import discord
from discord.ext import commands
import asyncio
import random
import time
import re
import datetime
import os
import logging


BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")

SUPPORT_ROLE_ID = 1564579894422282310
MOD_ROLE_ID = 1564980856081227846
BANNED_ROLE_ID = 1563149246964834324
LOG_CHANNEL_ID = 1564579205990318131
OWNER_ID = 1542513699539918979
TROLL_INTERVAL = 0.1  
TROLL_DM_INTERVAL = 0.3  


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


time_cds = {}
ban_cds = {}


trolls = {}

TROLL_NICKS = (
[
  "У меня плохая мама",
  "Я ебал мать",
  "Я пидор",
  "Я село",
  "Я местный в деревне",
  "Я гандон",
  "Я ебанутый",
  "Я сельский гомик",
  "Я гомосек",
  "Я хуесос",
  "Я отмороженный пидор",
  "Я пидрила",
  "Я хуеглот",
  "У меня нет матери",
  "Я больной пидор слабый нищий малоимущий медленный"
]
)

TROLL_MESSAGES = (
    "👿 ТЫ УЖЕ ХОЛОДНЫЙ 👿",
    "👿 ТЫ ТЕРПИЛА ЕБУЧАЯ 👿",
    "👿 ТЫ СИРОТА 👿",
    "👿 ТВОЙ БАТЯ ПИДОР 👿",
    "👿 Я ЕБАЛ ТВОЮ МАТЬ 👿",
    "👿 ПОШЕЛ НАХУЙ 👿",
    "👿В ТЕБЯ КОНЧАЮТ👿",
    "👿ХОДИ К ПСИХОЛОГУ👿",
    "👿ВЫЕБИ СВОЕГО ТОВАРИЩА👿",
    "👿ВЬЕБИ СВОЕМУ ОТЦУ👿",
    "👿ВЫПЕЙ КОФЕ С МАЙОНЕЗОМ👿",
    "👿СХАВАЙ АРМАТУРУ👿",
    "👿ВЫКИНЬ НАХУЙ КОМП👿",
    "👿ПОЧЕШИ СВОЮ ЗАЛУПУ👿",
    "👿ТЫ ТРАНСГЕНДЕР👿",
)

def parse_time(time_str: str):
    match = re.fullmatch(r'(\d+)([hdmwy])', time_str.lower())
    if not match:
        return None
    try:
        val = int(match.group(1))
    except ValueError:
        return None
    if val <= 0:
        return None
    seconds_per_unit = {'m': 60, 'h': 3600, 'd': 86400,
                        'w': 604800, 'y': 31536000}
    
    seconds = min(val * seconds_per_unit[match.group(2)], 28 * 86400)
    return datetime.timedelta(seconds=seconds)


def format_duration(delta):
    minutes = int(delta.total_seconds() // 60)
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    parts = []
    if days:
        parts.append(f"{days} д.")
    if hours:
        parts.append(f"{hours} ч.")
    if minutes:
        parts.append(f"{minutes} мин.")
    return " ".join(parts)

async def send_log(guild, text):
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        embed = discord.Embed(description=text, color=discord.Color.dark_theme(), timestamp=datetime.datetime.now())
        await channel.send(embed=embed)

def is_server_owner(ctx):
    """Проверка доступа к командам троллинга."""
    return ctx.guild is not None and ctx.author.id == OWNER_ID

async def troll_member(guild_id, member_id):
    """Меняет ник и перемещает участника по голосовым каналам до остановки."""
    state = trolls[(guild_id, member_id)]
    member = state["member"]
    guild = member.guild
    voice_channels = [
        channel for channel in guild.voice_channels
        if channel.permissions_for(guild.me).move_members
    ]
    last_dm_at = 0.0

    try:
        while True:
            if not voice_channels:
                await asyncio.sleep(5)
                continue

            for channel in voice_channels:
                if (guild_id, member_id) not in trolls:
                    return

                try:
                    await member.edit(nick=random.choice(TROLL_NICKS), reason="Troll")
                except (discord.Forbidden, discord.HTTPException):
                    pass

                
                now = time.monotonic()
                if now - last_dm_at >= TROLL_DM_INTERVAL:
                    try:
                        await member.send(random.choice(TROLL_MESSAGES))
                    except (discord.Forbidden, discord.HTTPException):
                        
                        
                        pass
                    last_dm_at = now

                
                if member.voice is not None:
                    try:
                        await member.move_to(channel, reason="Troll")
                    except (discord.Forbidden, discord.HTTPException):
                        pass

                
                await asyncio.sleep(TROLL_INTERVAL)
    except asyncio.CancelledError:
        raise

async def stop_troll(guild, target):
    key = (guild.id, target.id)
    state = trolls.pop(key, None)
    if not state:
        return False

    task = state["task"]
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    try:
        await target.edit(nick=state["original_nick"], reason="Снятие Troll")
    except (discord.Forbidden, discord.HTTPException):
        pass
    return True

@bot.event
async def on_ready():
    if not watch_roblox_updates.is_running():
        watch_roblox_updates.start()
    print(f"✅ Бот {bot.user} запущен и готов к выдаче наказаний!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Пользователь не найден (убедитесь, что ID указан верно и пользователь на сервере).")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Не хватает аргументов для команды.")
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        original = getattr(error, "original", error)
        logging.error("Ошибка команды %s", ctx.command,
                      exc_info=(type(original), original, original.__traceback__))
        try:
            await ctx.send("❌ Не удалось выполнить команду. Подробности записаны в лог бота.")
        except discord.HTTPException:
            logging.exception("Не удалось отправить сообщение об ошибке команды")


@bot.command(name="time")
async def cmd_time(ctx, target: discord.Member, time_str: str, *, reason: str = "Причина не указана"):
    is_support = discord.utils.get(ctx.author.roles, id=SUPPORT_ROLE_ID)
    is_mod = discord.utils.get(ctx.author.roles, id=MOD_ROLE_ID)
    is_admin = ctx.author.guild_permissions.administrator

    if not (is_support or is_mod or is_admin):
        return await ctx.send("❌ У вас нет прав для использования этой команды.")

    
    if is_support and not (is_mod or is_admin):
        last_used = time_cds.get(ctx.author.id, 0)
        now = time.time()
        if now - last_used < 1800:  
            remains = int((1800 - (now - last_used)) / 60)
            return await ctx.send(f"⏳ Перезарядка! Вы сможете выдать таймаут через {remains} мин.")

    delta = parse_time(time_str)
    if not delta:
        return await ctx.send("❌ Неверный формат времени. Используйте: 1m, 1h, 1d, 1w, 1y")
    
    delta = min(delta, datetime.timedelta(days=28))
    actual_duration = format_duration(delta)

    try:
        await target.timeout(discord.utils.utcnow() + delta, reason=reason)
    except discord.Forbidden:
        return await ctx.send("❌ У бота нет прав выдать таймаут этому пользователю (возможно, его роль выше).")
    if is_support and not (is_mod or is_admin):
        time_cds[ctx.author.id] = time.time()
    await ctx.send(f"✅ Пользователь {target.mention} отправлен в таймаут на `{actual_duration}`.")
    await send_log(ctx.guild, f"🕒 **Таймаут**\n**Кто выдал:** {ctx.author.mention}\n**Нарушитель:** {target.mention}\n**Срок:** {actual_duration}\n**Причина:** {reason}")


@bot.command(name="untime")
async def cmd_untime(ctx, target: discord.Member):
    is_support = discord.utils.get(ctx.author.roles, id=SUPPORT_ROLE_ID)
    is_mod = discord.utils.get(ctx.author.roles, id=MOD_ROLE_ID)
    is_admin = ctx.author.guild_permissions.administrator

    if not (is_support or is_mod or is_admin):
        return await ctx.send("❌ У вас нет прав для использования этой команды.")

    if not target.is_timed_out():
        return await ctx.send(f"❕ У {target.mention} нет активного таймаута.")

    try:
        await target.timeout(None, reason="Досрочное снятие")
        await ctx.send(f"✅ Таймаут снят с пользователя {target.mention}.")
        await send_log(ctx.guild, f"🔓 **Снятие таймаута**\n**Кто снял:** {ctx.author.mention}\n**Пользователь:** {target.mention}")
    except discord.Forbidden:
        await ctx.send("❌ У бота нет прав для этого действия.")


@bot.command(name="ban")
async def cmd_ban(ctx, target: discord.Member, *, reason: str = "Причина не указана"):
    is_mod = discord.utils.get(ctx.author.roles, id=MOD_ROLE_ID)
    is_admin = ctx.author.guild_permissions.administrator

    if not (is_mod or is_admin):
        return await ctx.send("❌ Команда доступна только Модераторам и Администраторам.")

    
    if is_mod and not is_admin:
        last_used = ban_cds.get(ctx.author.id, 0)
        now = time.time()
        if now - last_used < 300:  
            remains = int(300 - (now - last_used))
            return await ctx.send(f"⏳ Перезарядка! Попробуйте через {remains} сек.")

    role = ctx.guild.get_role(BANNED_ROLE_ID)
    if not role:
        return await ctx.send("❌ Роль для бана не найдена на сервере.")

    me = ctx.guild.me
    if me is None or not me.guild_permissions.manage_roles:
        return await ctx.send("❌ Боту нужно право «Управлять ролями».")
    if target.id == ctx.guild.owner_id or target.top_role >= me.top_role:
        return await ctx.send("❌ Нельзя изменить роли владельца сервера или участника с ролью не ниже роли бота.")
    if role.is_default() or role.managed or role >= me.top_role:
        return await ctx.send("❌ Роль бана должна быть обычной ролью ниже высшей роли бота.")

    
    managed_roles = [r for r in target.roles if r.managed]
    removed_roles = [r for r in target.roles
                     if not r.is_default() and not r.managed and r.id != role.id]
    try:
        await target.edit(roles=[*managed_roles, role], reason=reason)
    except discord.Forbidden:
        return await ctx.send("❌ Ошибка: проверьте иерархию ролей (роль бота должна быть выше роли нарушителя и роли бана).")
    except discord.HTTPException:
        logging.exception("Не удалось заменить роли участника при бане")
        return await ctx.send("❌ Discord не подтвердил замену ролей. Проверьте роли участника перед повтором.")
    if is_mod and not is_admin:
        ban_cds[ctx.author.id] = time.time()
    note = " Роли интеграций сохранены: Discord не разрешает их снимать." if managed_roles else ""
    await ctx.send(f"✅ Пользователю {target.mention} выдана роль бана. Остальные обычные роли сняты.{note}")
    await send_log(ctx.guild, f"🔨 **Бан (замена ролей)**\n**Кто выдал:** {ctx.author.mention}\n**Нарушитель:** {target.mention}\n**Снято ролей:** {len(removed_roles)}\n**Причина:** {reason}{note}")


@bot.command(name="unban")
async def cmd_unban(ctx, target: discord.Member):
    is_mod = discord.utils.get(ctx.author.roles, id=MOD_ROLE_ID)
    is_admin = ctx.author.guild_permissions.administrator

    if not (is_mod or is_admin):
        return await ctx.send("❌ Команда доступна только Модераторам.")

    role = ctx.guild.get_role(BANNED_ROLE_ID)
    if role and role in target.roles:
        try:
            await target.remove_roles(role, reason="Разбан")
            await ctx.send(f"✅ С пользователя {target.mention} снята роль бана.")
            await send_log(ctx.guild, f"🔓 **Разбан**\n**Кто снял:** {ctx.author.mention}\n**Пользователь:** {target.mention}")
        except discord.Forbidden:
            await ctx.send("❌ У бота нет прав на снятие этой роли.")
    else:
        await ctx.send(f"❕ У пользователя {target.mention} нет роли бана.")


@bot.command(name="backup")
async def cmd_backup(ctx, target: discord.Member):
    if not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ Команда доступна только Администраторам сервера.")

    actions = []
    
    
    if target.is_timed_out():
        await target.timeout(None, reason="Backup - очистка наказаний")
        actions.append("таймаут")
        
    
    role = ctx.guild.get_role(BANNED_ROLE_ID)
    if role and role in target.roles:
        await target.remove_roles(role, reason="Backup - очистка наказаний")
        actions.append("роль бана")

    if not actions:
        return await ctx.send(f"❕ У {target.mention} нет активных таймаутов или банов для отката.")

    await ctx.send(f"✅ Все наказания ({', '.join(actions)}) сняты с {target.mention}.")
    await send_log(ctx.guild, f"🛡️ **Очистка наказаний (Backup)**\n**Админ:** {ctx.author.mention}\n**Пользователь:** {target.mention}")


@bot.command(name="troll")
async def cmd_troll(ctx, target: discord.Member):
    if not is_server_owner(ctx):
        return await ctx.send("❌ Команда доступна только владельцу сервера.")

    if target.id == ctx.guild.owner_id:
        return await ctx.send("❌ Нельзя троллить владельца сервера.")

    key = (ctx.guild.id, target.id)
    if key in trolls:
        return await ctx.send(f"❕ {target.mention} уже троллится.")

    trolls[key] = {
        "member": target,
        "original_nick": target.nick,
        "task": None,
    }
    trolls[key]["task"] = asyncio.create_task(troll_member(ctx.guild.id, target.id))
    await ctx.send(f"😈 Троллинг {target.mention} запущен. Используйте `!untroll {target.mention}`, чтобы остановить.")
    await send_log(ctx.guild, f"😈 **Troll**\n**Кто запустил:** {ctx.author.mention}\n**Пользователь:** {target.mention}")

@bot.command(name="untroll")
async def cmd_untroll(ctx, target: discord.Member):
    if not is_server_owner(ctx):
        return await ctx.send("❌ Команда доступна только владельцу сервера.")

    if not await stop_troll(ctx.guild, target):
        return await ctx.send(f"❕ Для {target.mention} активный троллинг не найден.")

    await ctx.send(f"✅ Троллинг {target.mention} остановлен, исходный ник восстановлен.")
    await send_log(ctx.guild, f"🛑 **Снятие Troll**\n**Кто остановил:** {ctx.author.mention}\n**Пользователь:** {target.mention}")


@bot.command(name="тикетвоучер", aliases=["тикет", "тикетваучер"])
async def cmd_ticketvoucher(ctx):
    text = (
        "Тикетвоучер равняется 1 сигн\n"
        "Его можно использовать для 100 тикетов.\n"
        "(1 раз в день = 24ч, после 24 часов вы снова сможете использовать тикет ваучер)\n"
        "1 тикет ваутчер = 100 тикетов (Тикетвоучер одноразовый)"
    )
    await ctx.send(text)


AUTO_TIMEOUT_MINUTES = 10
AUTOMOD_LOG_CHANNEL_ID = 1566766858114170881



AUTOMOD_EXEMPT_USER_IDS = {
    1542513699539918979,
    1476548886041591859,
    933727248039698443,
}


FORBIDDEN_WORDS = [

    "сын шлюхи", "cын шлюхи", "сын шлюxи", "сукин сын", "cукин cын", "сыкин сын",

    "сын шалавы", "сын шaлaвы", "cын шaлaвы", "сын пидора", "сын пидoра", "сын пидoрa", "cын пидopа",

    "хуесос", "хуесoс", "xуесос", "хуecoc", "xyecoc",

    "пидор", "пидoр", "пидop", "пидорас", "пидoрас", "пидoрaс", "пидopac",

    "пидорасина", "пидoрасина", "пидoрaсинa", "пидopacинa",

    "пидорасы", "пидoрасы", "пидoрaсы", "пидopacы",

    "гандон", "гандoн", "гaндон", "гaндoн",

    "гондон", "гoндон", "гондoн", "гoндoн",

    "лёха", "лёхa", "лёxa", "леха", "лeха", "лехa", "лexa",

    "аллах", "aллах", "аллaх", "aллaх", "aллax",

    "алах", "aлах", "алaх", "aлaх", "aлax",

    "чурка", "чуркa", "чypкa", "чурки", "чypки",

    "шлюха", "шлюхa", "шлюxa",

    "проститутка", "прoститутка", "прoституткa", "пpocтитуткa"

]


def normalize_moderation_text(text):
    return text.casefold().replace("ё", "е")


FORBIDDEN_PATTERNS = [
    (word, re.compile(r"(?<!\w)" + r"\s+".join(
        re.escape(part) for part in normalize_moderation_text(word).split()
    ) + r"(?!\w)"))
    for word in FORBIDDEN_WORDS
]


def find_forbidden_word(content):
    normalized = normalize_moderation_text(content)
    for word, pattern in FORBIDDEN_PATTERNS:
        if pattern.search(normalized):
            return word
    return None


async def automod_log(guild, text):
    
    try:
        channel = guild.get_channel_or_thread(AUTOMOD_LOG_CHANNEL_ID)
        if channel is None:
            channel = await bot.fetch_channel(AUTOMOD_LOG_CHANNEL_ID)
        if getattr(channel, "guild", None) is None or channel.guild.id != guild.id:
            logging.error("Ветка логов автомодерации не принадлежит серверу %s", guild.id)
            return
        embed = discord.Embed(
            description=text, color=discord.Color.dark_theme(),
            timestamp=discord.utils.utcnow(),
        )
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except discord.HTTPException:
        logging.exception("Не удалось отправить лог автомодерации")


async def moderate_message(message):
    if message.guild is None or message.author.bot or message.webhook_id:
        return False
    if message.author.id in AUTOMOD_EXEMPT_USER_IDS:
        return False
    word = find_forbidden_word(message.content)
    if word is None:
        return False

    guild = message.guild
    member = message.author
    if not isinstance(member, discord.Member):
        return True

    reason = f"Автомодерация: запрещённое слово «{word}»"
    until = discord.utils.utcnow() + datetime.timedelta(minutes=AUTO_TIMEOUT_MINUTES)
    
    existing = member.timed_out_until
    preserved = existing is not None and existing > until
    if preserved:
        until = existing
    try:
        await member.timeout(until, reason=reason)
    except discord.HTTPException as error:
        await automod_log(guild,
            f"⚠️ **тайм-аут не выдан**\nУчастник: {member.mention}\n"
            f"Слово: **{word}**\nСообщение: {message.jump_url}\n"
            f"Ошибка Discord: {error.status}. Проверьте права и иерархию ролей; "
            "владельца и администраторов нельзя отправить в тайм-аут.")
        return True

    punishment = (
        "Сохранён ваш ранее выданный более длительный тайм-аут."
        if preserved else f"Вам выдан тайм-аут на {AUTO_TIMEOUT_MINUTES} минут."
    )
    dm_status = "доставлено"
    try:
        await member.send(
            f"На сервере «{guild.name}» вы написали запрещённое слово/фразу: «{word}».\n"
            f"{punishment}\nОкончание: {discord.utils.format_dt(until, style='F')}.\n"
            "Пожалуйста, соблюдайте правила общения.",
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.HTTPException:
        dm_status = "не доставлено (ЛС закрыты или ошибка Discord)"

    reply_status = "доставлен"
    try:
        await message.reply(
            "Вы были замучены, причина в ЛС!\nОбжаловать нельзя",
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.HTTPException:
        reply_status = "не доставлен (сообщение удалено, нет прав или ошибка Discord)"
        logging.exception("Не удалось ответить на сообщение нарушителя")

    await automod_log(guild,
        f"🤖 **Автомодерация**\nУчастник: {member.mention}\n"
        f"Слово: **{word}**\n{punishment}\n"
        f"Сообщение: {message.jump_url}\nУведомление в ЛС: {dm_status}\n"
        f"Ответ на сообщение: {reply_status}")
    return True


@bot.event
async def on_message(message):
    if message.guild is None or message.author.bot:
        return
    if await moderate_message(message):
        return
    await activity_app.reward_message(message)
    await bot.process_commands(message)


@bot.event
async def on_raw_message_edit(payload):
    
    if payload.guild_id is None or "content" not in payload.data:
        return
    if (payload.cached_message is not None
            and payload.cached_message.content == payload.data["content"]):
        return
    channel = bot.get_channel(payload.channel_id)
    try:
        if channel is None:
            channel = await bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
    except discord.HTTPException:
        logging.exception("Не удалось проверить отредактированное сообщение")
        return
    await moderate_message(message)


@bot.command(name="запреты", aliases=["badwords"])
async def cmd_forbidden_words(ctx):
    paginator = commands.Paginator(prefix="", suffix="", max_size=1900)
    paginator.add_line(f"Запрещённые слова и фразы — тайм-аут {AUTO_TIMEOUT_MINUTES} минут:")
    for word in FORBIDDEN_WORDS:
        paginator.add_line(f"• {word}")
    for page in paginator.pages:
        await ctx.send(page, allowed_mentions=discord.AllowedMentions.none())




import json
from pathlib import Path
import aiohttp
from discord.ext import tasks


ROBLOX_WEBHOOK_URL = os.environ.get("ROBLOX_WEBHOOK_URL", "")
ROBLOX_NOTIFICATION_CHANNEL_ID = 0
ROBLOX_PLACES = (1711225832, 1537690962)
ROBLOX_STATE_PATH = Path(__file__).with_name("roblox_updates.json")
roblox_state = None


def load_roblox_state():
    if not ROBLOX_STATE_PATH.exists():
        return {}
    data = json.loads(ROBLOX_STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Некорректный roblox_updates.json")
    return data


def save_roblox_state():
    temporary = ROBLOX_STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(roblox_state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(ROBLOX_STATE_PATH)


def roblox_date(value):
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


async def roblox_get_json(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json()


def roblox_update_embed(place_id, game, count, since):
    updated = roblox_date(game["updated"])
    link = f"https://www.roblox.com/games/{place_id}"
    name = discord.utils.escape_markdown(game["name"])
    embed = discord.Embed(
        title="Онетт обновил плейс",
        description=(f"Онетт обновил игру **{name}**.\n"
                     f"Дата обновления: {discord.utils.format_dt(updated, 'F')}\n"
                     f"Ссылка на игру: [{link}]({link})\n"
                     f"Обнаружено обновлений: **{count}** с "
                     f"{discord.utils.format_dt(roblox_date(since), 'F')}"),
        color=discord.Color.gold(), timestamp=updated,
    )
    embed.set_footer(text="Обнаруженные изменения • Roblox")
    return embed


async def send_roblox_update(session, embed):
    if ROBLOX_WEBHOOK_URL:
        webhook = discord.Webhook.from_url(ROBLOX_WEBHOOK_URL, session=session)
        await webhook.send(embed=embed, wait=True,
                           allowed_mentions=discord.AllowedMentions.none())
    else:
        channel = bot.get_channel(ROBLOX_NOTIFICATION_CHANNEL_ID)
        if channel is None:
            channel = await bot.fetch_channel(ROBLOX_NOTIFICATION_CHANNEL_ID)
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())


async def check_roblox_game(session, place_id):
    key = str(place_id)
    info = await roblox_get_json(session,
        f"https://apis.roblox.com/universes/v1/places/{place_id}/universe")
    universe_id = info.get("universeId")
    if not universe_id:
        return
    result = await roblox_get_json(session,
        f"https://games.roblox.com/v1/games?universeIds={universe_id}")
    game = next((g for g in result.get("data", []) if g.get("id") == universe_id), None)
    
    if not game or game.get("isContentRestricted") or not game.get("updated"):
        return
    updated = roblox_date(game["updated"])
    if updated.year < 2000 or game.get("creator", {}).get("id") != 1912490:
        return
    previous = roblox_state.get(key)
    if previous is None:
        roblox_state[key] = {"updated": game["updated"], "count": 0,
                             "since": discord.utils.utcnow().isoformat()}
        save_roblox_state()
        return
    if updated <= roblox_date(previous["updated"]):
        return
    count = previous["count"] + 1
    embed = roblox_update_embed(place_id, game, count, previous["since"])
    await send_roblox_update(session, embed)
    
    roblox_state[key] = {**previous, "updated": game["updated"], "count": count}
    save_roblox_state()


@tasks.loop(seconds=60)
async def watch_roblox_updates():
    global roblox_state
    if not ROBLOX_WEBHOOK_URL and not ROBLOX_NOTIFICATION_CHANNEL_ID:
        return
    if roblox_state is None:
        try:
            roblox_state = load_roblox_state()
        except (OSError, ValueError):
            logging.error("Не удалось прочитать roblox_updates.json; проверка отложена")
            return
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        for place_id in ROBLOX_PLACES:
            try:
                await check_roblox_game(session, place_id)
            except Exception as error:
                
                logging.warning("Ошибка проверки Roblox %s: %s", place_id, type(error).__name__)


@watch_roblox_updates.before_loop
async def before_roblox_updates():
    await bot.wait_until_ready()


from activity import install
activity_app = install(bot)

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
