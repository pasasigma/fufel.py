import getpass
import json
import secrets
from pathlib import Path
from dashboard import password_hash


def main():
    destination = Path.home() / '.fufel-dashboard-secrets'
    destination.mkdir(exist_ok=True)
    output = destination / 'bothost.json'
    if output.exists():
        raise SystemExit('Настройки уже созданы: ' + str(output))
    users = []
    for login, discord_id in [('tech','1542513699539918979'),('owner','933727248039698443')]:
        while True:
            password = getpass.getpass(f'Новый пароль {login} (минимум 12 символов): ')
            if password != getpass.getpass('Повторите пароль: '):
                print('Пароли не совпадают.')
                continue
            try:
                hashed = password_hash(password)
            except ValueError as error:
                print(error)
                continue
            users.append(dict(login=login,role=login,discord_id=discord_id,password_hash=hashed))
            break
    bridge = secrets.token_urlsafe(48)
    settings = dict(DASHBOARD_GUILD_ID='1544006188927156244',DASHBOARD_BRIDGE_KEY=bridge,DASHBOARD_USERS_JSON=json.dumps(users,separators=(',',':')))
    with output.open('x',encoding='utf-8') as handle:
        json.dump(settings,handle,ensure_ascii=False,indent=2)
    with (destination/'bridge-key.txt').open('x',encoding='utf-8') as handle:
        handle.write(bridge)
    print('Созданы настройки вне проекта: ' + str(output))
    print('Пароли сохранены только в виде хешей. Эти файлы не загружайте на GitHub.')


if __name__ == '__main__':
    main()
