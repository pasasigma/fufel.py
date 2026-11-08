import asyncio
import logging
import os
import secrets
import time
from collections import defaultdict
from pathlib import Path

import aiohttp
from aiohttp import web
import discord
from discord.ext import tasks
from discord.http import Route
from economy import Economy, ROLES, PRIZES

CLIENT_ID = os.getenv('DISCORD_CLIENT_ID', '1564664931343794366')
ADMIN_IDS = {1542513699539918979, 933727248039698443}
ROOT = Path(__file__).parent
logger = logging.getLogger(__name__)


class Activity:
    def __init__(self, bot):
        self.bot = bot
        self.economy = Economy(os.getenv('ECONOMY_DB', str(ROOT / 'economy.sqlite3')))
        self.sessions = {}
        self.locks = defaultdict(asyncio.Lock)
        self.voice = {}
        self.runner = None
        self.start_lock = asyncio.Lock()
        self.http = None
        self.login_limits = {}
        self.commands_registered = False

    async def reward_message(self, message):
        if (message.guild and not message.author.bot and not message.webhook_id
                and message.content.strip() and not message.content.startswith('!')
                and not message.author.is_timed_out()):
            self.economy.message_reward(message.guild.id, message.author.id)

    def eligible_voice(self):
        eligible = set()
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                if channel == guild.afk_channel:
                    continue
                humans = [m for m in channel.members if not m.bot and m.voice
                          and not m.voice.self_deaf and not m.voice.deaf
                          and not m.is_timed_out()]
                if len(humans) >= 2:
                    eligible.update((str(guild.id), str(m.id)) for m in humans)
        return eligible

    def update_voice(self):
        now = time.monotonic()
        eligible = self.eligible_voice()
        for key in list(self.voice):
            if key not in eligible:
                del self.voice[key]
        for key in eligible:
            last, remainder = self.voice.get(key, (now, 0))
            elapsed = now - last
            total = remainder + (elapsed if elapsed <= 15 else 0)
            minutes = int(total // 60)
            if minutes:
                self.economy.voice_reward(*key, minutes)
            self.voice[key] = (now, total % 60)

    async def voice_changed(self, member, before, after):
        self.update_voice()

    @tasks.loop(seconds=5)
    async def voice_tick(self):
        if not self.bot.is_ready():
            self.voice.clear()
            return
        self.update_voice()

    async def start(self):
        async with self.start_lock:
            if self.runner is not None:
                return
            self.http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))
            app = web.Application(client_max_size=8192, middlewares=[self.errors])
            app.router.add_get('/api/config', self.config)
            app.router.add_post('/api/login', self.login)
            app.router.add_get('/api/state', self.state)
            app.router.add_post('/api/action', self.action)
            app.router.add_post('/api/admin', self.admin)
            app.router.add_get('/', self.index)
            app.router.add_static('/assets', ROOT / 'static' / 'assets')
            runner = web.AppRunner(app, access_log=None)
            try:
                await runner.setup()
                await web.TCPSite(runner, '0.0.0.0', int(os.getenv('PORT', '8080'))).start()
            except BaseException:
                await runner.cleanup()
                await self.http.close()
                raise
            self.runner = runner
            if not self.voice_tick.is_running():
                self.voice_tick.start()
            if not self.entry_point_tick.is_running():
                self.entry_point_tick.start()

    async def register_entry_point(self):
        application_id = self.bot.application_id
        if not application_id or str(application_id) != CLIENT_ID:
            logger.error('Activity: DISCORD_CLIENT_ID не совпадает с приложением запущенного бота.')
            return False
        commands = await self.bot.http.request(Route(
            'GET', '/applications/{application_id}/commands', application_id=application_id))
        if not self.commands_registered:
            for command in self.bot.tree.get_commands():
                payload = command.to_dict(self.bot.tree)
                await self.bot.http.request(Route('POST', '/applications/{application_id}/commands', application_id=application_id), json=payload)
            self.commands_registered = True
        entry = next((command for command in commands if command.get('type') == 4), None)
        if entry is None:
            await self.bot.http.request(Route(
                'POST', '/applications/{application_id}/commands', application_id=application_id), json={
                    'name': 'launch', 'name_localizations': {'ru': 'Играть'},
                    'description': 'Открыть игру, баланс и магазин ролей',
                    'type': 4, 'handler': 2, 'contexts': [0], 'integration_types': [0],
                })
        elif entry.get('handler') != 2 or (entry.get('contexts') is not None and 0 not in entry['contexts']):
            await self.bot.http.request(Route(
                'PATCH', '/applications/{application_id}/commands/{command_id}',
                application_id=application_id, command_id=entry['id']), json={
                    'handler': 2, 'contexts': sorted(set(entry.get('contexts') or []) | {0}),
                })
        logger.info('Activity: команда запуска готова. Откройте приложение в Discord и нажмите «Играть».')
        return True

    @tasks.loop(seconds=60)
    async def entry_point_tick(self):
        if not self.bot.is_ready():
            return
        try:
            if await self.register_entry_point():
                self.entry_point_tick.stop()
        except discord.HTTPException as exc:
            logger.warning('Activity: не удалось зарегистрировать запуск (HTTP %s, код %s). Проверьте Enable Activities. Повтор через минуту.', exc.status, exc.code)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            logger.warning('Activity: нет связи с Discord при регистрации запуска. Повтор через минуту.')

    @web.middleware
    async def errors(self, request, handler):
        try:
            response = await handler(request)
        except web.HTTPException:
            raise
        except (ValueError, KeyError, TypeError):
            response = web.json_response({'error': 'Операция недоступна. Проверьте баланс, роль и текущую игру.'}, status=400)
        except (discord.HTTPException, aiohttp.ClientError, asyncio.TimeoutError):
            response = web.json_response({'error': 'Ошибка связи с Discord. Повторите запрос.'}, status=503)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    async def index(self, request):
        return web.FileResponse(ROOT / 'static' / 'index.html')

    async def config(self, request):
        return web.json_response({'client_id': CLIENT_ID})

    async def login(self, request):
        secret = os.getenv('DISCORD_CLIENT_SECRET')
        if not secret:
            return web.json_response({'error': 'Администратор ещё не настроил вход в Activity.'}, status=503)
        now = time.time()
        self.sessions = {k:v for k,v in self.sessions.items() if v['expires'] > now}
        self.login_limits = {k:v for k,v in self.login_limits.items() if now-v[0] < 60}
        remote = request.remote or 'proxy'
        start, count = self.login_limits.get(remote, (now, 0))
        if count >= 60:
            raise web.HTTPTooManyRequests()
        self.login_limits[remote] = (start, count+1)
        body = await request.json()
        code = body.get('code')
        guild_id = str(body.get('guild_id', ''))
        if not isinstance(code, str) or not 1 <= len(code) <= 2048 or not guild_id.isdigit():
            raise web.HTTPBadRequest()
        async with self.http.post('https://discord.com/api/v10/oauth2/token', data={
            'client_id': CLIENT_ID, 'client_secret': secret,
            'grant_type': 'authorization_code', 'code': code,
        }) as resp:
            if resp.status != 200:
                raise web.HTTPUnauthorized()
            token = await resp.json()
        async with self.http.get('https://discord.com/api/v10/users/@me', headers={
            'Authorization': 'Bearer ' + token['access_token'],
        }) as resp:
            if resp.status != 200:
                raise web.HTTPUnauthorized()
            user = await resp.json()
        guild = self.bot.get_guild(int(guild_id))
        if guild is None:
            raise web.HTTPForbidden()
        member = await guild.fetch_member(int(user['id']))
        if member.bot:
            raise web.HTTPForbidden()
        session = secrets.token_urlsafe(32)
        self.sessions[session] = {'user': member.id, 'guild': guild.id, 'expires': now+3600}
        return web.json_response({'session': session, 'access_token': token['access_token']})

    async def identity(self, request):
        token = request.headers.get('Authorization', '').removeprefix('Bearer ')
        session = self.sessions.get(token)
        if not session or session['expires'] <= time.time():
            raise web.HTTPUnauthorized()
        guild = self.bot.get_guild(session['guild'])
        if not guild:
            raise web.HTTPForbidden()
        member = await guild.fetch_member(session['user'])
        return guild, member

    def check_role(self, guild, role_id):
        role = guild.get_role(int(role_id))
        me = guild.me
        if (not role or role.managed or role.is_default() or not me
                or not me.guild_permissions.manage_roles or role >= me.top_role):
            raise ValueError('Роль недоступна')
        if role.permissions.administrator or role.permissions.manage_roles:
            raise ValueError('Нельзя продавать административную роль')
        return role

    async def deliver(self, guild, member):
        if any(r.id == 1563149246964834324 for r in member.roles):
            return True
        for held in member.roles:
            role_id = str(held.id)
            if role_id in ROLES and not self.economy.own_role(guild.id,member.id,role_id):
                self.economy.grant_role(guild.id,member.id,role_id)
                self.economy.db.execute('UPDATE entitlements SET delivered=1 WHERE guild=? AND user=? AND role=?', (str(guild.id),str(member.id),role_id))
        rows = self.economy.db.execute('SELECT role FROM entitlements WHERE guild=? AND user=? AND delivered=0',
                                      (str(guild.id),str(member.id))).fetchall()
        highest = self.economy.highest_role(guild.id,member.id)
        previous = [r for r in member.roles if str(r.id) in ROLES and ROLES[str(r.id)] < ROLES.get(highest,0)]
        if not rows and not previous:
            return False
        try:
            role = self.check_role(guild,highest)
            if role not in member.roles:
                if not rows:
                    return False
                await member.add_roles(role, reason='Фуфлыжник: новая ступень роли')
            if previous:
                await member.remove_roles(*previous, reason='Фуфлыжник: замена предыдущей ступени')
            self.economy.db.execute('UPDATE entitlements SET delivered=1 WHERE guild=? AND user=?', (str(guild.id),str(member.id)))
            return False
        except (discord.HTTPException, ValueError):
            return True

    async def state(self, request):
        guild, member = await self.identity(request)
        async with self.locks[(guild.id,member.id)]:
            pending = await self.deliver(guild,member)
            roles = []
            for role_id,price in sorted(ROLES.items(), key=lambda item:item[1]):
                role = guild.get_role(int(role_id))
                try:
                    self.check_role(guild,role_id)
                    available = True
                except ValueError:
                    available = False
                roles.append({'id':role_id, 'name':role.name if role else 'Роль недоступна',
                              'price':price, 'available':available, 'next':role_id == self.economy.next_role(guild.id,member.id),
                              'owned':bool(role and role in member.roles) or self.economy.own_role(guild.id,member.id,role_id)})
            history = self.economy.db.execute('SELECT delta,reason,created FROM ledger WHERE guild=? AND user=? ORDER BY id DESC LIMIT 12',
                                              (str(guild.id),str(member.id))).fetchall()
            return web.json_response({'balance':self.economy.wallet(guild.id,member.id)['coins'],
                'is_admin':member.id in ADMIN_IDS, 'name':member.display_name, 'roles':roles, 'prizes':PRIZES,
                'crash':self.economy.crash_status(guild.id,member.id),
                'history':[dict(r) for r in history], 'pending_roles':pending})

    async def admin(self, request):
        guild, actor = await self.identity(request)
        if actor.id not in ADMIN_IDS:
            raise web.HTTPForbidden()
        body = await request.json()
        target_id = str(body.get('target', ''))
        if not target_id.isascii() or not target_id.isdigit() or not 15 <= len(target_id) <= 20:
            return web.json_response({'error':'Введите Discord ID участника.'}, status=400)
        try:
            target = await guild.fetch_member(int(target_id))
        except discord.NotFound:
            return web.json_response({'error':'Участник не найден на этом сервере.'}, status=404)
        if target.bot:
            return web.json_response({'error':'Выберите участника, а не бота.'}, status=400)
        async with self.locks[(guild.id,target.id)]:
            operation = body.get('operation', 'view')
            result = {}
            if operation != 'view':
                key = body.get('key')
                if not isinstance(key,str) or not 8 <= len(key) <= 80:
                    raise ValueError('Некорректный ключ')
                try:
                    result = self.economy.admin_adjust(guild.id,actor.id,target.id,operation,
                        body.get('amount'),body.get('reason'),key)
                except ValueError as exc:
                    return web.json_response({'error':str(exc)}, status=400)
            history = self.economy.db.execute('SELECT actor,target,operation,amount,before_balance,after_balance,reason,created FROM admin_audit WHERE guild=? AND target=? ORDER BY id DESC LIMIT 20',
                (str(guild.id),str(target.id))).fetchall()
            return web.json_response({**result,'target':str(target.id),'name':target.display_name,
                'balance':self.economy.wallet(guild.id,target.id)['coins'],'history':[dict(row) for row in history]})

    async def action(self, request):
        guild, member = await self.identity(request)
        if member.is_timed_out() or any(r.id == 1563149246964834324 for r in member.roles):
            raise web.HTTPForbidden()
        body = await request.json()
        kind, key = body.get('action'), body.get('key')
        if not isinstance(key,str) or not 8<=len(key)<=80:
            raise ValueError('Некорректный запрос')
        async with self.locks[(guild.id,member.id)]:
            args = (guild.id,member.id)
            await self.deliver(guild,member)
            if kind == 'buy':
                role_id = str(body.get('role',''))
                if role_id not in ROLES:
                    raise ValueError('Нет такой роли')
                role = self.check_role(guild,role_id)
                if role in member.roles and not self.economy.own_role(*args,role_id):
                    raise ValueError('Роль уже есть')
                result = self.economy.purchase(*args,role_id,'buy:'+key)
            elif kind == 'roulette':
                for role_id in ROLES:
                    self.check_role(guild,role_id)
                    role = guild.get_role(int(role_id))
                    if role in member.roles and not self.economy.own_role(*args,role_id):
                        self.economy.grant_role(*args,role_id)
                        self.economy.db.execute('UPDATE entitlements SET delivered=1 WHERE guild=? AND user=? AND role=?',(*map(str,args),role_id))
                result = self.economy.roulette(*args,'roulette:'+key)
            elif kind == 'start':
                result = self.economy.crash_start(*args,body.get('stake'),'start:'+key)
            elif kind == 'cashout':
                result = self.economy.crash_cashout(*args,'cashout:'+key)
            else:
                raise ValueError('Нет такой операции')
            result = {**result,'pending_roles':await self.deliver(guild,member)}
            return web.json_response(result)


def install(bot):
    activity = Activity(bot)
    bot.add_listener(activity.start, 'on_ready')
    bot.add_listener(activity.voice_changed, 'on_voice_state_update')
    return activity
