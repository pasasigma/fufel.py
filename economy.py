import math
import secrets
import sqlite3
import time
from contextlib import contextmanager

ROLES = {
    '1566455609379922101': 35000,
    '1566456856128528425': 25000,
    '1566456770979963191': 15000,
    '1566456515743981678': 10000,
    '1566456609473826907': 5000,
}
PRIZES = [
    ('role', '1566455609379922101', 100),
    ('role', '1566456856128528425', 200),
    ('role', '1566456770979963191', 300),
    ('role', '1566456515743981678', 500),
    ('role', '1566456609473826907', 1000),
    ('coins', 1000, 2000), ('coins', 5000, 500),
    ('coins', 10000, 250), ('coins', 15000, 100),
    ('coins', 30000, 50), ('nothing', 0, 5000),
]


def crash_multiplier(draw):
    u = (draw + 1) / 1000001
    return min(10.0, max(1.0, math.floor((0.95 / u) ** (1 / 2.2) * 10) / 10))


class Economy:
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS wallets (
                guild TEXT, user TEXT, coins INTEGER NOT NULL DEFAULT 0 CHECK(coins>=0),
                last_message REAL NOT NULL DEFAULT 0, PRIMARY KEY(guild,user));
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY, guild TEXT, user TEXT, delta INTEGER,
                reason TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS requests (
                guild TEXT, user TEXT, key TEXT, result TEXT,
                PRIMARY KEY(guild,user,key));
            CREATE TABLE IF NOT EXISTS entitlements (
                guild TEXT, user TEXT, role TEXT, delivered INTEGER DEFAULT 0,
                PRIMARY KEY(guild,user,role));
            CREATE TABLE IF NOT EXISTS admin_audit (
                id INTEGER PRIMARY KEY, guild TEXT, actor TEXT, target TEXT,
                operation TEXT, amount INTEGER, before_balance INTEGER, after_balance INTEGER,
                reason TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS crash (
                guild TEXT, user TEXT, stake INTEGER, started REAL, ends REAL,
                multiplier REAL, status TEXT, payout INTEGER DEFAULT 0,
                PRIMARY KEY(guild,user));
        ''')

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def wallet(self, guild, user):
        self.db.execute('INSERT OR IGNORE INTO wallets(guild,user) VALUES (?,?)', (str(guild),str(user)))
        return self.db.execute('SELECT * FROM wallets WHERE guild=? AND user=?', (str(guild),str(user))).fetchone()

    def change(self, guild, user, amount, reason):
        wallet = self.wallet(guild,user)
        if wallet['coins'] + amount < 0:
            raise ValueError('Недостаточно монет')
        self.db.execute('UPDATE wallets SET coins=coins+? WHERE guild=? AND user=?', (amount,str(guild),str(user)))
        self.db.execute('INSERT INTO ledger(guild,user,delta,reason,created) VALUES (?,?,?,?,?)',
                        (str(guild),str(user),amount,reason,time.time()))

    def message_reward(self, guild, user, now=None):
        now = time.time() if now is None else now
        with self.transaction():
            wallet = self.wallet(guild,user)
            if now-wallet['last_message'] < 30:
                return False
            self.change(guild,user,1,'Сообщение')
            self.db.execute('UPDATE wallets SET last_message=? WHERE guild=? AND user=?', (now,str(guild),str(user)))
        return True

    def voice_reward(self, guild, user, minutes):
        if not isinstance(minutes,int) or minutes <= 0:
            return
        with self.transaction():
            self.change(guild,user,5*minutes,'Время в голосовом канале')

    def once(self, guild, user, key, action):
        import json
        if not isinstance(key,str) or not 8 <= len(key) <= 100:
            raise ValueError('Некорректный идентификатор операции')
        with self.transaction():
            row = self.db.execute('SELECT result FROM requests WHERE guild=? AND user=? AND key=?', (str(guild),str(user),key)).fetchone()
            if row:
                return json.loads(row['result'])
            result = action()
            self.db.execute('INSERT INTO requests VALUES (?,?,?,?)', (str(guild),str(user),key,json.dumps(result)))
            return result

    def own_role(self, guild, user, role):
        return self.db.execute('SELECT 1 FROM entitlements WHERE guild=? AND user=? AND role=?', (str(guild),str(user),role)).fetchone() is not None

    def grant_role(self, guild, user, role):
        self.db.execute('INSERT INTO entitlements(guild,user,role) VALUES (?,?,?)', (str(guild),str(user),role))

    def purchase(self, guild, user, role, key):
        def action():
            if role not in ROLES:
                raise ValueError('Роль не продаётся')
            if self.own_role(guild,user,role):
                raise ValueError('Эта роль уже приобретена')
            self.change(guild,user,-ROLES[role],'Покупка роли')
            self.grant_role(guild,user,role)
            return {'kind':'role','role':role}
        return self.once(guild,user,key,action)

    def roulette(self, guild, user, key):
        def action():
            self.change(guild,user,-1000,'Рулетка: ставка')
            draw=secrets.randbelow(10000)
            for prize_index,(kind,value,weight) in enumerate(PRIZES):
                if draw < weight:
                    break
                draw -= weight
            if kind == 'coins':
                self.change(guild,user,value,'Рулетка: выигрыш')
            elif kind == 'role':
                if self.own_role(guild,user,value):
                    value,kind=ROLES[value],'coins'
                    self.change(guild,user,value,'Рулетка: компенсация повторной роли')
                else:
                    self.grant_role(guild,user,value)
            return {'kind':kind,'value':value,'prize_index':prize_index}
        return self.once(guild,user,key,action)

    def crash_start(self, guild, user, stake, key):
        def action():
            if type(stake) is not int or not 100 <= stake <= 10000:
                raise ValueError('Ставка от 100 до 10 000 монет')
            current=self.crash_status(guild,user)
            if current and current['status']=='flying':
                raise ValueError('Завершите текущий полёт')
            self.change(guild,user,-stake,'Crash: ставка')
            multiplier=crash_multiplier(secrets.randbelow(1000000))
            started=time.time()
            ends=started+math.log(multiplier)/0.12
            self.db.execute('INSERT OR REPLACE INTO crash VALUES (?,?,?,?,?,?,?,?)',
                            (str(guild),str(user),stake,started,ends,multiplier,'flying',0))
            return {'started':started,'stake':stake}
        return self.once(guild,user,key,action)

    def crash_status(self, guild, user):
        row=self.db.execute('SELECT * FROM crash WHERE guild=? AND user=?',(str(guild),str(user))).fetchone()
        if not row:
            return None
        status=row['status']
        if status=='flying' and time.time()>=row['ends']:
            self.db.execute("UPDATE crash SET status='crashed' WHERE guild=? AND user=?",(str(guild),str(user)))
            status='crashed'
        multiplier=row['multiplier'] if status in ('crashed','cashed') else min(row['multiplier'],math.exp(0.12*(time.time()-row['started'])))
        return {'status':status,'multiplier':math.floor((multiplier+1e-9)*10)/10,'stake':row['stake'],'payout':row['payout'],'elapsed':max(0,time.time()-row['started']),'growth_rate':0.12}

    def crash_cashout(self, guild, user, key):
        def action():
            current=self.crash_status(guild,user)
            if not current or current['status']!='flying':
                return {'error':'Полёт уже завершён','round':current}
            payout=math.floor(current['stake']*current['multiplier'])
            self.change(guild,user,payout,'Crash: выигрыш')
            self.db.execute("UPDATE crash SET status='cashed',payout=?,multiplier=? WHERE guild=? AND user=?",(payout,current['multiplier'],str(guild),str(user)))
            return {'payout':payout,'multiplier':current['multiplier']}
        return self.once(guild,user,key,action)

    def admin_adjust(self, guild, actor, target, operation, amount, reason, key):
        if operation not in ('add', 'remove', 'set') or type(amount) is not int or not 0 <= amount <= 1000000000:
            raise ValueError('Некорректная сумма')
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 200:
            raise ValueError('Укажите причину до 200 символов')
        def action():
            before = self.wallet(guild, target)['coins']
            after = amount if operation == 'set' else before + (amount if operation == 'add' else -amount)
            if not 0 <= after <= 1000000000:
                raise ValueError('Баланс вне допустимого диапазона')
            self.change(guild, target, after-before, 'Администратор: ' + reason.strip())
            self.db.execute('INSERT INTO admin_audit(guild,actor,target,operation,amount,before_balance,after_balance,reason,created) VALUES (?,?,?,?,?,?,?,?,?)',
                (str(guild),str(actor),str(target),operation,amount,before,after,reason.strip(),time.time()))
            return {'target':str(target), 'balance':after, 'before':before}
        return self.once(guild, actor, 'admin:'+key, action)
