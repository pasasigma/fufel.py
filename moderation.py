import json
import time
import discord

BANNED_ROLE_ID = 1563149246964834324


class RoleModeration:
    def __init__(self, db, locks):
        self.db, self.locks = db, locks
        db.execute('CREATE TABLE IF NOT EXISTS role_bans (guild TEXT, user TEXT, roles TEXT NOT NULL, state TEXT NOT NULL, created REAL, PRIMARY KEY(guild,user))')

    def validate(self, guild, member):
        if member.id == guild.owner_id or member.bot:
            raise ValueError('Нельзя изменить наказание владельца сервера или бота.')
        if not guild.me or not guild.me.guild_permissions.manage_roles or member.top_role >= guild.me.top_role:
            raise ValueError('Проверьте право «Управлять ролями» и положение роли бота.')
        role = guild.get_role(BANNED_ROLE_ID)
        if not role or role.managed or role >= guild.me.top_role:
            raise ValueError('Роль бана отсутствует или находится выше роли бота.')
        return role

    async def ban(self, guild, member, reason):
        async with self.locks[(guild.id,member.id)]:
            role = self.validate(guild,member)
            if role in member.roles:
                return {'message':'Роль бана уже выдана; сохранённые роли не изменены.'}
            saved = [r.id for r in member.roles if not r.is_default() and not r.managed and r.id != role.id]
            old = self.db.execute('SELECT roles FROM role_bans WHERE guild=? AND user=?',(str(guild.id),str(member.id))).fetchone()
            if old:
                saved = sorted(set(saved) | set(json.loads(old['roles'])))
            self.db.execute('INSERT OR REPLACE INTO role_bans VALUES (?,?,?,?,?)',(str(guild.id),str(member.id),json.dumps(saved),'prepared',time.time()))
            await member.edit(roles=[r for r in member.roles if r.managed]+[role], reason=reason)
            self.db.execute("UPDATE role_bans SET state='banned' WHERE guild=? AND user=?",(str(guild.id),str(member.id)))
            return {'message':'Роль бана выдана. Предыдущие роли сохранены.', 'saved_roles':len(saved)}

    async def unban(self, guild, member, reason):
        async with self.locks[(guild.id,member.id)]:
            ban = self.validate(guild,member)
            row = self.db.execute('SELECT * FROM role_bans WHERE guild=? AND user=?',(str(guild.id),str(member.id))).fetchone()
            if ban not in member.roles and (not row or row['state']=='prepared'):
                return {'message':'Активного бана нет.'}
            restored, blocked, deleted = [], [], []
            for rid in json.loads(row['roles']) if row else []:
                role = guild.get_role(rid)
                if role is None:
                    deleted.append(str(rid))
                elif role.managed or role >= guild.me.top_role:
                    blocked.append(rid)
                elif not role.is_default():
                    restored.append(role)
            roles = {r.id:r for r in member.roles if r.id != ban.id and not r.is_default()}
            roles.update({r.id:r for r in restored})
            await member.edit(roles=list(roles.values()),reason=reason)
            if blocked:
                self.db.execute("UPDATE role_bans SET roles=?,state='restore_pending' WHERE guild=? AND user=?",(json.dumps(blocked),str(guild.id),str(member.id)))
            else:
                self.db.execute('DELETE FROM role_bans WHERE guild=? AND user=?',(str(guild.id),str(member.id)))
            message = f'Бан снят. Восстановлено ролей: {len(restored)}.' if row else 'Бан снят. Старая копия ролей отсутствует — их нужно вернуть вручную.'
            if blocked:
                message += f' Не удалось вернуть {len(blocked)} ролей из-за иерархии. Исправьте права и повторите разбан.'
            if deleted:
                message += f' Ранее удалённых с сервера ролей: {len(deleted)}.'
            return {'message':message,'restored':len(restored),'blocked':blocked,'deleted':deleted}
