"""Provision Ubuntu/Debian or Oracle/RHEL HTTPS hosting without changing broker settings."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CERTBOT = Path('/opt/certbot/bin/certbot')
BACKUPS = Path('/var/lib/sector-heatmap/config-backups')


def domain_name(value):
    value = value.lower().rstrip('.')
    if len(value) > 253 or '.' not in value or any(
        not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', part)
        for part in value.split('.')
    ):
        raise argparse.ArgumentTypeError('Use a DNS hostname, without a scheme, path or port.')
    return value


def run(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def write_managed(path, content, mode=0o644, backups=BACKUPS):
    """Back up changed managed files and replace atomically; identical runs do nothing."""
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError(f'Refusing to replace a symlink: {path}')
    data = content.encode()
    if path.exists() and path.read_bytes() == data:
        return False
    if path.exists():
        backups.mkdir(parents=True, exist_ok=True, mode=0o700)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        target = backups / (path.name + '.' + stamp)
        shutil.copy2(path, target)
        target.chmod(0o600)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.sector-heatmap.tmp')
    # Exclusive creation prevents following an existing temporary symlink.
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def apache_config(domain, tls=True, debian=False):
    domain = domain_name(domain)
    http = f'''<VirtualHost *:80>
    ServerName {domain}
    DocumentRoot /var/www/html
    <Directory /var/www/html/.well-known/acme-challenge>
        Require all granted
    </Directory>
'''
    if tls:
        http += f'''    RewriteEngine On
    RewriteCond %{{REQUEST_URI}} !^/\\.well-known/acme-challenge/
    RewriteRule ^ https://{domain}%{{REQUEST_URI}} [R=301,L]
'''
    http += '</VirtualHost>\n'
    if not tls:
        return http
    result = http + f'''
Listen 443 https
SSLSessionCache shmcb:/run/httpd/sslcache(512000)
<VirtualHost *:443>
    ServerName {domain}
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/{domain}/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/{domain}/privkey.pem
    SSLProtocol -all +TLSv1.2 +TLSv1.3
    ProxyRequests Off
    # Only this exact public origin is translated; foreign/missing origins fail CSRF checks.
    RequestHeader set Origin "http://127.0.0.1:8080" "expr=req('Origin') == 'https://{domain}'"
    ProxyPass / http://127.0.0.1:8080/ connectiontimeout=5 timeout=300
    ProxyPassReverse / http://127.0.0.1:8080/
    ErrorLog logs/trading-ssl-error.log
    CustomLog logs/trading-ssl-access.log combined
</VirtualHost>
'''
    if debian:
        result = result.replace('Listen 443 https\n', '').replace('SSLSessionCache shmcb:/run/httpd/sslcache(512000)\n', '').replace('logs/trading-', '${APACHE_LOG_DIR}/trading-')
    return result


def unit_quote(value):
    value = str(value)
    if any(c in value for c in '\n\r\x00'):
        raise ValueError('Newlines are not allowed in systemd paths.')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def app_service(user, home, root):
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*[$]?', user):
        raise ValueError('Unsupported service username.')
    return f'''[Unit]
Description=Sector Heatmap dashboard
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User={user}
WorkingDirectory={str(root).replace("%", "%%")}
Environment={unit_quote('HOME=' + str(home))}
Environment=HEATMAP_PORT=8080
ExecStart=/bin/sh {unit_quote(Path(root) / 'run_live_heatmap.sh')}
Restart=on-failure
RestartSec=10
TimeoutStopSec=60
UMask=0077

[Install]
WantedBy=multi-user.target
'''


def renewal_service(domain):
    return f'''[Unit]
Description=Renew Let's Encrypt certificate for {domain}
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart={CERTBOT} renew --quiet --no-random-sleep-on-renew --cert-name {domain}
TimeoutStartSec=15min
PrivateTmp=true
'''


TIMER = '''[Unit]
Description=Check Let's Encrypt certificate renewal twice daily

[Timer]
OnCalendar=*-*-* 00,12:00:00 UTC
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
'''
HOOK = '''#!/bin/sh
set -eu
if /usr/bin/systemctl is-active --quiet httpd; then
    /usr/sbin/apachectl configtest
    /usr/bin/systemctl reload httpd
fi
'''


def port_open():
    try:
        with socket.create_connection(('127.0.0.1', 8080), timeout=2):
            return True
    except OSError:
        return False


def native_login(user, domain):
    # Run account initialization as the app owner, never as root. Existing users,
    # passwords, sessions, broker configuration and strategies are not altered.
    code = '''
import os, secrets, json, sys
from pathlib import Path
from sector_heatmap.workspaces import WorkspaceStore
root=Path.cwd()
private=root/'.private'
private.mkdir(exist_ok=True,mode=0o700)
settings=private/'server-settings.json'
expected={'public_origin':'https://'+sys.argv[1]}
if settings.exists():
    if json.loads(settings.read_text()).get('public_origin') != expected['public_origin']:
        raise SystemExit('Existing public origin differs; review server-settings.json before changing domains.')
else:
    settings.write_text(json.dumps(expected)+'\\n');settings.chmod(0o600)
store=WorkspaceStore(private/'dashboard-login/registry.sqlite3')
with store.db() as db:
    first=db.execute('SELECT count(*) FROM users').fetchone()[0]==0
if first:
    password=secrets.token_urlsafe(24)
    credentials=private/'initial-dashboard-login.txt'
    fd=os.open(credentials,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as out:
        out.write('Username: admin\\nPassword: '+password+'\\n')
    store.create_user('admin',password,bootstrap=True)
    print('Initial native dashboard credentials: '+str(credentials))
marker=private/'dashboard-auth-enabled.json'
if not marker.exists():
    marker.write_text('{}\\n');marker.chmod(0o600)
'''
    run('runuser', '-u', user, '--', ROOT / '.venv/bin/python', '-c', code, domain, cwd=ROOT)


def preserve_running_policy(user):
    dropin = Path('/etc/systemd/system/sector-heatmap.service.d/existing-live-order-policy.conf')
    if dropin.exists() or not port_open():
        return
    result = subprocess.run(['ss', '-ltnp', 'sport = :8080'], check=True, capture_output=True, text=True)
    match = re.search(r'pid=(\d+)', result.stdout)
    if not match:
        raise RuntimeError('Cannot identify the process on port 8080; refusing to proxy an unknown service.')
    process = Path('/proc') / match.group(1)
    if process.stat().st_uid != pwd.getpwnam(user).pw_uid or b'heatmap_server.py' not in (process / 'cmdline').read_bytes().split(b'\0'):
        raise RuntimeError('Port 8080 is not owned by this application/user; resolve the conflict before setup.')
    environment = dict(item.split('=', 1) for item in (process / 'environ').read_bytes().decode().split('\0') if '=' in item)
    lines = ['[Service]']
    for key in ('SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS', 'SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS', 'SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS'):
        if key not in environment:
            continue
        value = environment[key]
        if value not in ('0', '1'):
            raise RuntimeError('Invalid existing live-order switch: ' + key)
        lines.append('Environment=' + key + '=' + value)
    write_managed(dropin, '\n'.join(lines) + '\n', mode=0o600)


def allow_debian_web_ports():
    if shutil.which('ufw') and 'Status: active' in subprocess.run(['ufw', 'status'], check=True, capture_output=True, text=True).stdout:
        run('ufw', 'allow', '80/tcp')
        run('ufw', 'allow', '443/tcp')
        return
    # Some Ubuntu cloud images use persistent iptables with a terminal REJECT.
    # Insert only the two web-port rules; preserve SSH and all existing rules.
    persistent = Path('/etc/iptables/rules.v4')
    if not shutil.which('iptables') or not persistent.exists():
        return
    listing = subprocess.run(['iptables', '-L', 'INPUT', '-n', '--line-numbers'], check=True, capture_output=True, text=True).stdout
    if not any('REJECT' in line for line in listing.splitlines()):
        return
    for port in ('80', '443'):
        check = subprocess.run(['iptables', '-C', 'INPUT', '-p', 'tcp', '--dport', port, '-j', 'ACCEPT'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if check.returncode:
            listing = subprocess.run(['iptables', '-L', 'INPUT', '-n', '--line-numbers'], check=True, capture_output=True, text=True).stdout
            before = next(line.split()[0] for line in listing.splitlines() if 'REJECT' in line)
            run('iptables', '-I', 'INPUT', before, '-p', 'tcp', '--dport', port, '-j', 'ACCEPT')
    rules = subprocess.check_output(['iptables-save'], text=True)
    write_managed(persistent, rules)


def restore_labels(*paths):
    if shutil.which('restorecon'):
        run('restorecon', '-RF', *paths)


def install_certbot():
    runtime = Path('/opt/certbot-python')
    if not runtime.exists():
        shutil.copytree(Path(sys.base_prefix), runtime)
        # This runtime is copied, not linked to the user-writable Python install.
        for path in [runtime, *runtime.rglob('*')]:
            os.chown(path, 0, 0, follow_symlinks=False)
        restore_labels(runtime)
    if not CERTBOT.exists():
        run(runtime / 'bin/python3.12', '-m', 'venv', '/opt/certbot')
        run('/opt/certbot/bin/python', '-m', 'pip', 'install', '--disable-pip-version-check', 'certbot==5.8.0')
    restore_labels('/opt/certbot', runtime)


def configure(args):
    if os.geteuid() != 0:
        raise RuntimeError('Server provisioning requires root; invoke it through setup_and_run.sh.')
    release = dict(line.rstrip().split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    os_id = release.get('ID', '').strip('"')
    debian = os_id in {'ubuntu', 'debian'}
    if not debian and os_id not in {'ol', 'rhel', 'rocky', 'almalinux', 'centos'}:
        raise RuntimeError('Public server setup supports Ubuntu/Debian and Oracle/RHEL-family Linux with systemd.')
    apache = 'apache2' if debian else 'httpd'
    apachectl = 'apache2ctl' if debian else 'apachectl'
    owner = pwd.getpwnam(args.user)
    if owner.pw_uid == 0:
        raise RuntimeError('Run the main installer as the non-root application owner, not root.')
    addresses = sorted({row[4][0] for row in socket.getaddrinfo(args.domain, 80, type=socket.SOCK_STREAM)})
    print('Domain addresses:', ', '.join(addresses), flush=True)
    if debian:
        if not shutil.which('apache2ctl'):
            run('apt-get', 'update')
            run('apt-get', '-y', 'install', 'apache2')
        run('a2enmod', 'ssl', 'proxy', 'proxy_http', 'headers', 'rewrite')
    else:
        missing = [p for p in ('httpd', 'mod_ssl') if subprocess.run(['rpm', '-q', p], stdout=subprocess.DEVNULL).returncode]
        if missing:
            run('dnf', '-y', 'install', *missing)
    install_certbot()
    native_login(args.user, args.domain)
    ssl = Path('/etc/httpd/conf.d/ssl.conf')
    if ssl.exists():
        text = ssl.read_text()
        if 'SSLCertificateFile /etc/pki/tls/certs/localhost.crt' not in text:
            raise RuntimeError('Existing custom ssl.conf found; preserve it and review listener conflicts before provisioning.')
        BACKUPS.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination = BACKUPS / ('ssl.conf.' + str(time.time_ns()))
        shutil.copy2(ssl, destination)
        ssl.unlink()
    managed = Path('/etc/apache2/sites-available/trading.conf' if debian else '/etc/httpd/conf.d/trading.conf')
    if managed.exists() and 'ServerName ' + args.domain not in managed.read_text():
        raise RuntimeError('trading.conf serves another domain; refusing to replace it.')
    if debian:
        write_managed(managed, apache_config(args.domain, tls=False, debian=True)) if not managed.exists() else None
        run('a2ensite', 'trading.conf')
        run('a2dissite', '000-default.conf', 'default-ssl.conf')
    cert = Path('/etc/letsencrypt/live') / args.domain / 'fullchain.pem'
    # HTTP validation comes before HTTPS when no certificate exists yet.
    if not cert.exists():
        write_managed(managed, apache_config(args.domain, tls=False, debian=debian))
        run(apachectl, 'configtest')
        run('systemctl', 'enable', '--now', apache)
        run('systemctl', 'reload', apache)
    if shutil.which('firewall-cmd') and subprocess.run(['firewall-cmd', '--state'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        for service in ('http', 'https'):
            run('firewall-cmd', '--permanent', '--add-service=' + service)
            run('firewall-cmd', '--add-service=' + service)
    print('Cloud security lists/NSGs must separately permit inbound TCP 80 and 443.', flush=True)
    if not cert.exists():
        command = [CERTBOT, 'certonly', '--webroot', '--webroot-path', '/var/www/html', '--domain', args.domain,
                   '--non-interactive', '--agree-tos']
        command += ['--email', args.email] if args.email else ['--register-unsafely-without-email']
        try:
            run(*command)
        except subprocess.CalledProcessError:
            raise RuntimeError('Certificate issuance failed. Check domain DNS, every published A/AAAA address, and cloud inbound port 80; rerun setup after fixing them.') from None
    if not debian:
        run('setsebool', '-P', 'httpd_can_network_relay', 'on')
    else:
        allow_debian_web_ports()
    write_managed(managed, apache_config(args.domain, debian=debian))
    restore_labels(managed)
    run(apachectl, 'configtest')
    preserve_running_policy(args.user)
    write_managed('/etc/systemd/system/sector-heatmap.service', app_service(args.user, owner.pw_dir, ROOT))
    write_managed('/etc/systemd/system/certbot-renew.service', renewal_service(args.domain))
    write_managed('/etc/systemd/system/certbot-renew.timer', TIMER)
    hook = Path('/etc/letsencrypt/renewal-hooks/deploy/reload-httpd')
    deploy_hook = HOOK.replace('httpd', 'apache2').replace('/usr/sbin/apachectl', '/usr/sbin/apache2ctl') if debian else HOOK
    write_managed(hook, deploy_hook, mode=0o755)
    restore_labels(hook)
    run('systemd-analyze', 'verify', '/etc/systemd/system/sector-heatmap.service', '/etc/systemd/system/certbot-renew.service', '/etc/systemd/system/certbot-renew.timer')
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', 'sector-heatmap.service')
    if not port_open():
        run('systemctl', 'start', 'sector-heatmap.service')
        for _ in range(30):
            if port_open():
                break
            time.sleep(1)
        else:
            raise RuntimeError('Dashboard did not become ready; inspect journalctl -u sector-heatmap.service.')
    else:
        print('Preserving the process already listening on port 8080; boot service enabled for the next boot.', flush=True)
    run('systemctl', 'enable', '--now', apache, 'certbot-renew.timer')
    run('systemctl', 'reload', apache)
    run('curl', '--fail', '--silent', '--show-error', '--max-time', '15', '--resolve', args.domain + ':443:127.0.0.1',
        '-o', '/dev/null', 'https://' + args.domain + '/')
    if args.test_renewal:
        run(CERTBOT, 'renew', '--cert-name', args.domain, '--dry-run', '--no-random-sleep-on-renew', '--run-deploy-hooks')
    print('Server setup complete: https://' + args.domain + '/', flush=True)
    print('Register this exact FYERS Redirect URL: https://' + args.domain + '/callback', flush=True)
    print('Explicit FYERS_REDIRECT_URI settings are preserved; update any existing loopback override to match.', flush=True)
    try:
        urllib.request.urlopen('https://' + args.domain + '/', timeout=10).close()
    except (OSError, urllib.error.URLError):
        print('Local HTTPS works, but public HTTPS could not be verified. Check cloud TCP 443 access.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', required=True, type=domain_name)
    parser.add_argument('--user', default=os.getenv('SUDO_USER') or os.getenv('USER'))
    parser.add_argument('--email')
    parser.add_argument('--plan', action='store_true', help='Print generated configuration without changing the system.')
    parser.add_argument('--test-renewal', action='store_true')
    args = parser.parse_args()
    if args.email and (any(c.isspace() for c in args.email) or '@' not in args.email):
        parser.error('Use a valid contact email address.')
    if args.plan:
        print(apache_config(args.domain, debian=debian))
        print(app_service(args.user, pwd.getpwnam(args.user).pw_dir, ROOT))
        print(renewal_service(args.domain) + TIMER + HOOK)
        return
    try:
        configure(args)
    except (RuntimeError, subprocess.CalledProcessError, OSError) as error:
        parser.exit(1, 'Server setup failed: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
