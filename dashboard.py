import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import timedelta
from aiohttp import web
import discord

GUILD_ID = 1544006188927156244
PERMISSIONS = {'members','timeout','untimeout','ban','unban','balance','coins','send_channel','send_dm','audit','accounts'}
DEFAULTS = {
    'tech': PERMISSIONS,
    'owner': PERMISSIONS,
    'moderator': {'members','timeout','untimeout','ban','unban','balance'},
    'support': {'members','timeout','untimeout'},
}


def password_hash(password, salt=None):
    if not isinstance(password,str) or not 12 <= len(password) <= 256:
        raise ValueError('Пароль: от 12 до 256 символов.')
    salt = salt or secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return f'scrypt${salt}${value}'


def password_matches(password, encoded):
    try:
        algorithm,salt,value = encoded.split('$')
        return algorithm == 'scrypt' and hmac.compare_digest(password_hash(password,salt),encoded)
    except (ValueError,TypeError):
        return False


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Dashboard:
    def __init__(self, activity):
        self.activity = activity
        self.bot = activity.bot
        self.db = activity.economy.db
        self.lock = asyncio.Lock()
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS dash_users (login TEXT PRIMARY KEY, password TEXT NOT NULL, role TEXT NOT NULL, discord_id TEXT NOT NULL, permissions TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS dash_sessions (token TEXT PRIMARY KEY, login TEXT NOT NULL, csrf TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS dash_audit (id INTEGER PRIMARY KEY, created REAL, actor TEXT, action TEXT, target TEXT, reason TEXT, status TEXT, detail TEXT, request_key TEXT, UNIQUE(actor,request_key));
        CREATE TABLE IF NOT EXISTS dash_limits (key TEXT PRIMARY KEY, started REAL, count INTEGER);
        CREATE TABLE IF NOT EXISTS dash_cooldowns (actor TEXT, action TEXT, used REAL, PRIMARY KEY(actor,action));
        ''')
        initial = os.getenv('DASHBOARD_USERS_JSON','')
        if initial and self.db.execute('SELECT count(*) FROM dash_users').fetchone()[0] == 0:
            users = json.loads(initial)
            if {u['role'] for u in users} != {'tech','owner'} or len(users)!=2:
                raise ValueError('DASHBOARD_USERS_JSON должен содержать tech и owner.')
            for u in users:
                self.validate_login(u['login'])
                if not re.fullmatch(r'scrypt\$[a-f0-9]{32}\$[a-f0-9]{128}',u['password_hash']):
                    raise ValueError('В начальной настройке требуется хеш пароля.')
            with activity.economy.transaction():
                for u in users:
                    self.db.execute('INSERT INTO dash_users VALUES (?,?,?,?,?,1)',(u['login'],u['password_hash'],u['role'],u['discord_id'],json.dumps(sorted(DEFAULTS[u['role']]))))
        self.dummy = password_hash(secrets.token_urlsafe(24))

    def validate_login(self, login):
        if not isinstance(login,str) or not re.fullmatch(r'[a-z0-9_.-]{3,32}',login):
            raise ValueError('Логин: 3–32 латинских строчных буквы, цифры, . _ -')

    def routes(self, app):
        app.router.add_route('*','/dashboard-api/{path:.*}',self.handle)

    def audit(self, actor, action, target='', reason='', status='success', detail='', key=None):
        cursor=self.db.execute('INSERT INTO dash_audit(created,actor,action,target,reason,status,detail,request_key) VALUES (?,?,?,?,?,?,?,?)',
            (time.time(),actor,action,str(target),reason,status,detail,key))
        return cursor.lastrowid

    def limited(self,key,maximum,period):
        now=time.time()
        row=self.db.execute('SELECT * FROM dash_limits WHERE key=?',(key,)).fetchone()
        if not row or now-row['started']>=period:
            self.db.execute('INSERT OR REPLACE INTO dash_limits VALUES (?,?,1)',(key,now))
        else:
            if row['count']>=maximum:
                raise web.HTTPTooManyRequests(text='Слишком много попыток. Повторите позже.')
            self.db.execute('UPDATE dash_limits SET count=count+1 WHERE key=?',(key,))
        self.db.execute('DELETE FROM dash_limits WHERE started<?',(now-86400,))

    def identity(self, request):
        cookie=request.cookies.get('__Host-dashboard','')
        row=self.db.execute('SELECT u.*,s.csrf FROM dash_sessions s JOIN dash_users u ON u.login=s.login WHERE s.token=? AND s.expires>? AND u.enabled=1',(digest(cookie),time.time())).fetchone()
        if not row:
            raise web.HTTPUnauthorized(text='Войдите в панель.')
        if request.method!='GET' and not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),row['csrf']):
            raise web.HTTPForbidden(text='Обновите страницу и повторите действие.')
        return dict(row)

    def public_user(self,u):
        return {k:u[k] for k in ('login','role','discord_id','enabled')} | {'permissions':json.loads(u['permissions'])}

    def need(self,user,permission):
        if permission not in json.loads(user['permissions']):
            raise web.HTTPForbidden(text='Для этого действия нет прав.')

    def guild(self):
        guild=self.bot.get_guild(int(os.getenv('DASHBOARD_GUILD_ID',str(GUILD_ID))))
        if not guild or not self.bot.is_ready():
            raise web.HTTPServiceUnavailable(text='Бот ещё не подключён к серверу.')
        return guild

    async def handle(self, request):
        try:
            key=os.getenv('DASHBOARD_BRIDGE_KEY','')
            if len(key)<32:
                raise web.HTTPServiceUnavailable(text='Связь панели с ботом ещё не настроена.')
            if not hmac.compare_digest(request.headers.get('X-Dashboard-Key',''),key):
                raise web.HTTPForbidden(text='Нет доступа.')
            path=request.match_info['path']
            if request.method not in ('GET','POST'):
                raise web.HTTPMethodNotAllowed(request.method,['GET','POST'])
            body=await request.json() if request.method=='POST' else {}
            if not isinstance(body,dict):
                raise ValueError('Ожидается объект запроса.')
            if path=='login' and request.method=='POST':
                response=await self.login(request,body)
            else:
                user=self.identity(request)
                self.limited('user:'+user['login'],180,60)
                if path=='me' and request.method=='GET':
                    response=web.json_response({'user':self.public_user(user),'csrf':user['csrf']})
                elif path=='logout' and request.method=='POST':
                    self.db.execute('DELETE FROM dash_sessions WHERE token=?',(digest(request.cookies.get('__Host-dashboard','')),))
                    response=web.json_response({'ok':True})
                    response.del_cookie('__Host-dashboard',path='/',secure=True,httponly=True,samesite='Strict')
                elif path=='action' and request.method=='POST':
                    response=web.json_response(await self.action(user,body))
                elif request.method=='GET':
                    response=web.json_response(await self.read(user,path,request.query))
                else:
                    raise web.HTTPNotFound()
        except web.HTTPException as exc:
            response=web.json_response({'error':exc.text if exc.text and not exc.text.startswith('404:') else 'Раздел не найден.'},status=exc.status)
        except (ValueError,KeyError,TypeError) as exc:
            response=web.json_response({'error':str(exc) or 'Проверьте параметры.'},status=400)
        except discord.HTTPException:
            response=web.json_response({'error':'Discord отклонил запрос. Проверьте права бота и доступность участника.'},status=502)
        except Exception:
            import logging
            logging.exception('Dashboard request failed')
            response=web.json_response({'error':'Ошибка сервера. Действие могло сохраниться; проверьте аудит перед повтором.'},status=500)
        response.headers['Cache-Control']='no-store'
        return response

    async def login(self,request,body):
        login=str(body.get('login','')).strip().lower()
        ip=request.headers.get('X-Dashboard-IP','unknown')
        self.limited('ip:'+ip,20,900)
        self.limited('login:'+login,10,900)
        u=self.db.execute('SELECT * FROM dash_users WHERE login=?',(login,)).fetchone()
        valid=await asyncio.to_thread(password_matches,body.get('password',''),u['password'] if u else self.dummy)
        if not u or not valid or not u['enabled']:
            self.audit(login[:32],'login',status='denied',detail='Неверные данные входа')
            raise web.HTTPUnauthorized(text='Неверный логин или пароль.')
        token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        self.db.execute('DELETE FROM dash_sessions WHERE expires<?',(time.time(),))
        self.db.execute('INSERT INTO dash_sessions VALUES (?,?,?,?)',(digest(token),login,csrf,time.time()+8*3600))
        self.audit(login,'login')
        response=web.json_response({'user':self.public_user(u),'csrf':csrf})
        response.set_cookie('__Host-dashboard',token,max_age=28800,path='/',secure=True,httponly=True,samesite='Strict')
        return response

    def member_json(self,m):
        return {'id':str(m.id),'name':m.display_name,'username':m.name,'avatar':str(m.display_avatar.url),'bot':m.bot,
                'timeout_until':m.timed_out_until.isoformat() if m.is_timed_out() else None,
                'banned':any(r.id==1563149246964834324 for r in m.roles),
                'roles':[{'id':str(r.id),'name':r.name} for r in m.roles if not r.is_default()]}

    async def read(self,user,path,q):
        guild=self.guild()
        if path=='overview':
            recent=[]
            if 'audit' in json.loads(user['permissions']):
                recent=[dict(r) for r in self.db.execute('SELECT * FROM dash_audit ORDER BY id DESC LIMIT 6')]
            coins=None
            if 'balance' in json.loads(user['permissions']):
                coins=self.db.execute('SELECT coalesce(sum(coins),0) FROM wallets WHERE guild=?',(str(guild.id),)).fetchone()[0]
            return {'guild':{'id':str(guild.id),'name':guild.name},'online':self.bot.is_ready(),'latency':round(self.bot.latency*1000),
                    'members':guild.member_count,'cached_members':len(guild.members),'coins':coins,
                    'actions_today':self.db.execute('SELECT count(*) FROM dash_audit WHERE created>? AND action!=?',(time.time()-86400,'login')).fetchone()[0],
                    'recent':recent,'voice':sum(len(c.members) for c in guild.voice_channels)}
        if path=='members':
            self.need(user,'members')
            needle=str(q.get('q','')).casefold()[:100]
            offset=max(0,int(q.get('offset','0')))
            members=[m for m in guild.members if needle in (m.name+' '+m.display_name+' '+str(m.id)).casefold()]
            members.sort(key=lambda m:(m.bot,m.display_name.casefold()))
            if needle.isdigit() and not members:
                try:members=[await guild.fetch_member(int(needle))]
                except discord.NotFound:pass
            return {'items':[self.member_json(m) for m in members[offset:offset+30]],'total':len(members),'partial':len(guild.members)<(guild.member_count or 0)}
        if path=='member':
            self.need(user,'members')
            member=await guild.fetch_member(int(q['id']))
            result={'member':self.member_json(member)}
            if 'balance' in json.loads(user['permissions']):
                result['balance']=self.activity.economy.wallet(guild.id,member.id)['coins']
                result['ledger']=[dict(r) for r in self.db.execute('SELECT delta,reason,created FROM ledger WHERE guild=? AND user=? ORDER BY id DESC LIMIT 30',(str(guild.id),str(member.id)))]
                result['daily']=dict(r) if (r:=self.db.execute('SELECT day,streak FROM daily WHERE guild=? AND user=?',(str(guild.id),str(member.id))).fetchone()) else None
            return result
        if path=='channels':
            self.need(user,'send_channel')
            return {'items':[{'id':str(c.id),'name':c.name} for c in guild.text_channels if c.permissions_for(guild.me).send_messages]}
        if path=='audit':
            self.need(user,'audit')
            clauses,params=[],[]
            for field in ('actor','action','status','target'):
                if q.get(field):clauses.append(field+'=?');params.append(q[field])
            if q.get('from'):clauses.append('created>=?');params.append(float(q['from']))
            if q.get('to'):clauses.append('created<=?');params.append(float(q['to']))
            if q.get('q'):clauses.append('(reason LIKE ? OR detail LIKE ?)');params.extend(['%'+q['q'][:100]+'%']*2)
            where=' WHERE '+' AND '.join(clauses) if clauses else ''
            offset=max(0,int(q.get('offset','0')))
            return {'items':[dict(r) for r in self.db.execute('SELECT * FROM dash_audit'+where+' ORDER BY id DESC LIMIT 50 OFFSET ?',(*params,offset))],
                    'total':self.db.execute('SELECT count(*) FROM dash_audit'+where,params).fetchone()[0]}
        if path=='accounts':
            self.need(user,'accounts')
            return {'items':[self.public_user(r) for r in self.db.execute('SELECT * FROM dash_users ORDER BY login')],'permissions':sorted(PERMISSIONS),'defaults':{k:sorted(v) for k,v in DEFAULTS.items()}}
        raise web.HTTPNotFound()

    async def action(self,user,body):
        kind=str(body.get('action',''))
        permission={'coins':'coins','account':'accounts','password':'members'}.get(kind,kind)
        if kind!='password':self.need(user,permission)
        key=body.get('key')
        if not isinstance(key,str) or not re.fullmatch(r'[\w-]{8,80}',key):
            raise ValueError('Некорректный идентификатор операции.')
        reason=str(body.get('reason','')).strip()
        if kind!='password' and not 1<=len(reason)<=300:
            raise ValueError('Укажите причину (до 300 символов).')
        async with self.lock:
            current=self.db.execute('SELECT * FROM dash_users WHERE login=? AND enabled=1',(user['login'],)).fetchone()
            if not current:
                raise web.HTTPForbidden(text='Доступ отключён.')
            user=dict(current)
            if kind!='password':self.need(user,permission)
            old=self.db.execute('SELECT status,detail FROM dash_audit WHERE actor=? AND request_key=?',(user['login'],key)).fetchone()
            if old:
                if old['status']=='success':return json.loads(old['detail'])
                raise ValueError('Запрос уже обработан или его результат не подтверждён. Проверьте журнал; повторная отправка заблокирована.')
            audit_id=self.audit(user['login'],kind,body.get('target',''),reason,'pending','Ожидание подтверждения',key)
            try:
                result=await self.execute(user,body,reason)
            except Exception as exc:
                self.db.execute('UPDATE dash_audit SET status=?,detail=? WHERE id=?',('error',str(exc)[:700],audit_id))
                raise
            self.db.execute('UPDATE dash_audit SET status=?,detail=? WHERE id=?',('success',json.dumps(result,ensure_ascii=False),audit_id))
            return result

    async def execute(self,user,body,reason):
        kind=body['action']
        if kind=='account':return await self.account(user,body)
        if kind=='password':
            if not await asyncio.to_thread(password_matches,body.get('old_password',''),user['password']):raise ValueError('Текущий пароль неверен.')
            hashed=await asyncio.to_thread(password_hash,body.get('password',''))
            self.db.execute('UPDATE dash_users SET password=? WHERE login=?',(hashed,user['login']))
            self.db.execute('DELETE FROM dash_sessions WHERE login=?',(user['login'],))
            return {'message':'Пароль изменён. Войдите заново.'}
        guild=self.guild()
        if kind in ('send_channel','send_dm'):
            text=body.get('text','')
            if not isinstance(text,str) or not 1<=len(text)<=2000:raise ValueError('Сообщение: 1–2000 символов.')
            self.limited('send:'+user['login'],10,60)
            if kind=='send_channel':
                target=guild.get_channel(int(body['target']))
                if not isinstance(target,discord.TextChannel):raise ValueError('Выберите текстовый канал этого сервера.')
            else:target=await guild.fetch_member(int(body['target']))
            message=await target.send(text,allowed_mentions=discord.AllowedMentions.none())
            return {'message':'Сообщение отправлено.','message_id':str(message.id),'text':text}
        member=await guild.fetch_member(int(body['target']))
        if kind=='coins':
            if member.bot:raise ValueError('Баланс бота недоступен.')
            async with self.activity.locks[(guild.id,member.id)]:
                result=self.activity.economy.admin_adjust(guild.id,user['discord_id'],member.id,body.get('operation'),body.get('amount'),reason,'web:'+body['key'])
            return {'message':f"Баланс: {result['balance']} монет.",**result}
        if member.id in (guild.owner_id,1542513699539918979,933727248039698443) or member.bot:
            raise ValueError('Этого участника нельзя наказать через панель.')
        if user['role'] in ('support','moderator') and (member.guild_permissions.administrator or any(r.id in (1564579894422282310,1564980856081227846) for r in member.roles)):
            raise ValueError('Наказания сотрудников доступны овнеру и техническому администратору.')
        cooldown=1800 if kind=='timeout' and user['role']=='support' else 300 if kind=='ban' and user['role']=='moderator' else 0
        if cooldown:
            row=self.db.execute('SELECT used FROM dash_cooldowns WHERE actor=? AND action=?',(user['discord_id'],kind)).fetchone()
            if row and time.time()-row['used']<cooldown:raise ValueError(f"Повторное действие через {int(cooldown-time.time()+row['used'])} сек.")
        label=f"Панель: {user['login']} | {reason}"
        if kind in ('timeout','untimeout'):
            if member.top_role>=guild.me.top_role:raise ValueError('Роль участника не ниже роли бота.')
            seconds=body.get('seconds',0)
            if kind=='timeout' and (type(seconds)is not int or not 60<=seconds<=2419200):raise ValueError('Таймаут: от минуты до 28 дней.')
            await member.timeout(discord.utils.utcnow()+timedelta(seconds=seconds) if kind=='timeout' else None,reason=label)
            result={'message':'Таймаут выдан.' if kind=='timeout' else 'Таймаут снят.'}
        elif kind=='ban':result=await self.activity.moderation.ban(guild,member,label)
        elif kind=='unban':result=await self.activity.moderation.unban(guild,member,label)
        else:raise ValueError('Неизвестное действие.')
        if cooldown:self.db.execute('INSERT OR REPLACE INTO dash_cooldowns VALUES (?,?,?)',(user['discord_id'],kind,time.time()))
        return result

    async def account(self,user,body):
        login=str(body.get('login','')).strip().lower()
        self.validate_login(login)
        old=self.db.execute('SELECT * FROM dash_users WHERE login=?',(login,)).fetchone()
        if old and old['role']=='tech':raise ValueError('Технический аккаунт изменяется только его владельцем через смену пароля.')
        if old and old['role']=='owner' and user['role']!='tech':raise ValueError('Аккаунт овнера изменяет только технический администратор.')
        role=body.get('role')
        if role not in ('owner','moderator','support') or (role=='owner' and user['role']!='tech'):raise ValueError('Эту роль нельзя назначить.')
        permissions=body.get('permissions',[])
        if not isinstance(permissions,list) or not set(permissions)<=PERMISSIONS:raise ValueError('Некорректные права.')
        if role in ('support','moderator') and 'accounts' in permissions:raise ValueError('Управление аккаунтами доступно только овнеру и техническому администратору.')
        if user['role'] not in ('owner','tech') or not set(permissions)<=set(json.loads(user['permissions'])):raise ValueError('Нельзя передать эти права.')
        discord_id=str(body.get('discord_id',''))
        if not re.fullmatch(r'\d{15,20}',discord_id):raise ValueError('Укажите Discord ID сотрудника.')
        await self.guild().fetch_member(int(discord_id))
        enabled=body.get('enabled',True)
        if type(enabled)is not bool:raise ValueError('Некорректное состояние аккаунта.')
        password=body.get('password','')
        hashed=await asyncio.to_thread(password_hash,password) if password else old['password'] if old else None
        if not hashed:raise ValueError('Новому аккаунту требуется пароль.')
        self.db.execute('INSERT OR REPLACE INTO dash_users VALUES (?,?,?,?,?,?)',(login,hashed,role,discord_id,json.dumps(sorted(set(permissions))),int(enabled)))
        self.db.execute('DELETE FROM dash_sessions WHERE login=?',(login,))
        return {'message':'Аккаунт сохранён. Предыдущие сеансы завершены.','login':login,'role':role,'permissions':permissions,'enabled':enabled}
