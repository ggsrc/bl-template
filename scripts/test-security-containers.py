#!/usr/bin/env python3
"""Opt-in local Docker canaries; no ports published, all networks internal."""
from pathlib import Path
import base64, importlib.util, json, os, secrets, subprocess, sys, time, urllib.request, urllib.error
sys.dont_write_bytecode = True

repo=Path(__file__).resolve().parents[1]
if os.environ.get('BLCLI_SECURITY_CONTAINER_TESTS') != '1':
    raise SystemExit('Set BLCLI_SECURITY_CONTAINER_TESTS=1 to explicitly enable local Docker canaries.')
# Do not create test resources on a remote/shared Docker host.
context=subprocess.run(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True,capture_output=True,check=True).stdout.strip()
if not os.environ.get('DOCKER_HOST',context).startswith('unix://'):
    raise SystemExit('Container canaries require a local Unix-socket Docker endpoint.')
spec=importlib.util.spec_from_file_location('security_tests',repo/'scripts/test-security.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
T=module.SecurityTemplates
T.setUpClass()
work=T.work/'containers'; work.mkdir(mode=0o700)
prefix='blcli-sec-'+secrets.token_hex(6)
containers=[]; network=prefix
all_secrets=[]

def run(args,check=True,timeout=300):
    p=subprocess.run(['docker',*args],text=True,capture_output=True,timeout=timeout)
    if check and p.returncode:
        error=p.stderr+p.stdout
        for s in all_secrets: error=error.replace(s,'[REDACTED]')
        raise RuntimeError(f'docker {args[0]} failed: {error[-2500:]}')
    return p

def start(role,image,args,options=()):
    name=prefix+'-'+role
    containers.append(name)
    run(['run','-d','--name',name,'--network',network,*options,image,*args])
    return name

def wait_for(check,seconds=120):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if check(): return
        time.sleep(1)
    raise RuntimeError('canary readiness timed out')

def secret_values(docs,name):
    d=T.find(docs,'Secret',name)
    result=d.get('stringData') or {k:base64.b64decode(v).decode() for k,v in d['data'].items()}
    all_secrets.extend(result.values())
    return result

try:
    run(['network','create','--internal',network])
    udata=secret_values(T.docs['uptrace'],'uptrace-bootstrap')
    uconfig=secret_values(T.docs['uptrace'],'uptrace')
    ufile=work/'uptrace.yml'; ufile.write_text(uconfig['uptrace.yml'])
    upgpass=secrets.token_hex(24); all_secrets.append(upgpass)
    uenv=work/'uptrace.env'; uenv.write_text('CH_PASSWORD='+udata['clickhouse-password']+'\nPG_HOST=postgres\nPG_USER=uptrace\nPG_DATABASE=uptrace\nPG_PASSWORD='+upgpass+'\n'); uenv.chmod(0o600)
    docs=T.docs['n9e']
    bootstrap=secret_values(docs,'n9e-bootstrap')
    cfg=secret_values(docs,'n9e-config')
    config=work/'n9e'; config.mkdir(mode=0o755)
    for k,v in cfg.items(): (config/k).write_text(v)
    (config/'login-new.json').write_text(json.dumps({'username':'root','password':bootstrap['admin-password']}))
    (config/'login-old.json').write_text(json.dumps({'username':'root','password':'root.2020'}))
    mysql_secret=next(d for d in docs if d['kind']=='Secret' and 'MYSQL_ROOT_PASSWORD' in d.get('stringData',{}))
    mysql_data=mysql_secret['stringData']
    envfile=work/'mysql.env'; envfile.write_text('\n'.join(f'{k}={v}' for k,v in mysql_data.items())); envfile.chmod(0o600)
    init=work/'init'; init.mkdir(mode=0o755)
    for k,v in secret_values(docs,'database-initdb-config').items(): (init/k).write_text(v)
    mysql=start('mysql','mysql:8.4.13',[],['--network-alias',mysql_secret['metadata']['name'],'--user','999:999','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/var/lib/mysql:rw,uid=999,gid=999','--tmpfs','/var/run/mysqld:rw,uid=999,gid=999','--tmpfs','/tmp:rw,mode=1777','--env-file',str(envfile),'--mount',f'type=bind,src={init},dst=/docker-entrypoint-initdb.d,readonly'])
    wait_for(lambda:run(['exec',mysql,'mysqladmin','-h','127.0.0.1','ping','--silent'],check=False).returncode==0,180)
    redisfile=work/'redis.conf'; redisfile.write_text('requirepass '+bootstrap['redis-password']+'\ndir /data\n')
    redis_sts=next(d for d in docs if d['kind']=='StatefulSet' and d['spec']['template']['spec']['containers'][0]['name']=='redis')
    redis=start('redis','redis:7.4.12-alpine',['redis-server','/etc/redis.conf'],['--network-alias',redis_sts['metadata']['name'],'--user','999:999','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/data:rw,uid=999,gid=999','--mount',f'type=bind,src={redisfile},dst=/etc/redis.conf,readonly'])
    # HTTP probes run inside the same isolated network via the image's curl.
    n9e=start('n9e','flashcatcloud/nightingale:9.1.1',['-configs','/app/etc'],['--network-alias','n9e-nightingale-center','--env','CONFIGTYPE_ALERT_HEARTBEAT_IP=127.0.0.1','--entrypoint','/app/n9e','--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/tmp:rw,mode=1777','--mount',f'type=bind,src={config},dst=/app/etc,readonly'])
    probe = "import urllib.request,urllib.error;\ntry: urllib.request.urlopen('http://127.0.0.1:17000/',timeout=2)\nexcept urllib.error.HTTPError: pass"
    wait_for(lambda:run(['exec',n9e,'python3','-c',probe],check=False).returncode==0,60)
    login = "import json,urllib.request,sys; body=open(sys.argv[1],'rb').read(); r=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:17000/api/n9e/auth/login',data=body,headers={'Content-Type':'application/json'})); d=json.load(r); ok=bool(d.get('dat')) and not d.get('err'); sys.exit(0 if ok else 1)"
    assert run(['exec',n9e,'python3','-c',login,'/app/etc/login-new.json'],check=False).returncode==0, 'random admin login failed'
    assert run(['exec',n9e,'python3','-c',login,'/app/etc/login-old.json'],check=False).returncode!=0, 'old admin password accepted'
    n9e_logs=run(['logs',n9e]).stdout
    assert 'auto get outbound ip fail' not in n9e_logs, 'n9e still probes public network for heartbeat'
    assert '127.0.0.1:17000' in n9e_logs, 'heartbeat did not use the supplied Pod IP'
    print('PASS n9e: MySQL initialized, Redis auth, non-root/read-only HTTP, random admin login, old password rejected',flush=True)
    # Exercise the rendered nginx config and both HTTP/TLS paths under the exact
    # Pod restrictions, including /tmp for PID and proxy buffers. No published ports.
    nginx_deployment=next(d for d in docs if d['kind']=='Deployment' and d['spec']['template']['spec']['containers'][0]['name']=='nginx')
    nginx_image=nginx_deployment['spec']['template']['spec']['containers'][0]['image']
    # Docker has no Kubernetes Service NAT: map Service port 80 to container 17000.
    nginx_config=next(d for d in docs if d['kind']=='ConfigMap' and 'nginx.conf' in d.get('data',{}))
    nginx_file=work/'nginx.conf'; nginx_file.write_text(nginx_config['data']['nginx.conf'].replace('n9e-nightingale-center:80', 'n9e-nightingale-center:17000'))
    nginx=start('nginx',nginx_image,[],['--user','10000:10000','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/tmp:rw,uid=10000,gid=10000','--mount',f'type=bind,src={nginx_file},dst=/etc/nginx/nginx.conf,readonly'])
    proxy_login=login.replace('127.0.0.1:17000',nginx+':8080')
    wait_for(lambda:run(['exec',n9e,'python3','-c',proxy_login,'/app/etc/login-new.json'],check=False).returncode==0,30)
    assert run(['exec',nginx,'id','-u']).stdout.strip()=='10000'
    tls_docs=T.render(T.charts['n9e'],'n9e','--set','nightingale.expose.tls.enabled=true','--set','nightingale.expose.tls.auto.commonName=nginx-test')
    tls_config=next(d for d in tls_docs if d['kind']=='ConfigMap' and 'nginx.conf' in d.get('data',{}))
    tls_file=work/'nginx-tls.conf'; tls_file.write_text(tls_config['data']['nginx.conf'].replace('n9e-nightingale-center:80', 'n9e-nightingale-center:17000'))
    certdir=work/'certs'; certdir.mkdir(mode=0o755)
    cert=next(d for d in tls_docs if d['kind']=='Secret' and 'tls.crt' in d.get('data',{}))
    for key,value in cert['data'].items():
        (certdir/key).write_bytes(base64.b64decode(value))
    nginx_tls=start('nginx-tls',nginx_image,[],['--user','10000:10000','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/tmp:rw,uid=10000,gid=10000','--mount',f'type=bind,src={tls_file},dst=/etc/nginx/nginx.conf,readonly','--mount',f'type=bind,src={certdir},dst=/etc/nginx/cert,readonly'])
    tls_login=login.replace('import json,urllib.request,sys;', 'import json,urllib.request,sys,ssl;').replace('http://127.0.0.1:17000','https://'+nginx_tls+':8443').replace("headers={'Content-Type':'application/json'}))", "headers={'Content-Type':'application/json'}),context=ssl._create_unverified_context())")
    wait_for(lambda:run(['exec',n9e,'python3','-c',tls_login,'/app/etc/login-new.json'],check=False).returncode==0,30)
    print('PASS nginx: pinned image, UID 10000, all capabilities dropped, read-only rootfs; HTTP/TLS proxy login',flush=True)
    # Real VM cluster query: vmagent's 8429 writer does not implement PromQL.
    storage=start('vmstorage','victoriametrics/vmstorage:v1.129.1-cluster',['-storageDataPath=/data','-retentionPeriod=1d','-memory.allowedBytes=64MiB'],['--tmpfs','/data:rw'])
    insert=start('vminsert','victoriametrics/vminsert:v1.129.1-cluster',['-storageNode='+storage+':8400','-memory.allowedBytes=64MiB'])
    select=start('vmselect','victoriametrics/vmselect:v1.129.1-cluster',['-storageNode='+storage+':8401','-search.latencyOffset=0s','-memory.allowedBytes=64MiB'],['--network-alias','vmselect-victoriametrics-vmks.monitoring-vm.svc.cluster.local'])
    write_metric="import urllib.request; r=urllib.request.urlopen(urllib.request.Request('http://"+insert+":8480/insert/0/prometheus/api/v1/import/prometheus',data=b'blcli_review_canary 1\\n')); assert r.status==204"
    wait_for(lambda:run(['exec',n9e,'python3','-c',write_metric],check=False).returncode==0,60)
    query_metric="import urllib.request,json; r=json.load(urllib.request.urlopen('http://vmselect-victoriametrics-vmks.monitoring-vm.svc.cluster.local:8481/select/0/prometheus/api/v1/query?query=blcli_review_canary%3D%3D1')); assert r['status']=='success' and r['data']['result'] and r['data']['result'][0]['value'][1]=='1'"
    wait_for(lambda:run(['exec',n9e,'python3','-c',query_metric],check=False).returncode==0,60)
    print('PASS n9e query path: imported synthetic metric and evaluated alert expression via real vmselect:8481',flush=True)
    # Bytebase uses a dedicated non-superuser role in an isolated PostgreSQL DB.
    pgpass=secrets.token_hex(24); apppass=secrets.token_hex(24)
    all_secrets.extend([pgpass,apppass])
    pginit=work/'pginit'; pginit.mkdir(mode=0o755)
    (pginit/'init.sql').write_text("CREATE ROLE bytebase LOGIN PASSWORD '"+apppass+"'; CREATE DATABASE bytebase OWNER bytebase; CREATE ROLE uptrace LOGIN PASSWORD '"+upgpass+"'; CREATE DATABASE uptrace OWNER uptrace;")
    pgenv=work/'pg.env'; pgenv.write_text('POSTGRES_PASSWORD='+pgpass+'\n'); pgenv.chmod(0o600)
    pg=start('pg','postgres:17.10-alpine',[],['--network-alias','postgres','--user','70:70','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/var/lib/postgresql/data:rw,uid=70,gid=70','--tmpfs','/var/run/postgresql:rw,uid=70,gid=70','--tmpfs','/tmp:rw,mode=1777','--env-file',str(pgenv),'--mount',f'type=bind,src={pginit},dst=/docker-entrypoint-initdb.d,readonly'])
    wait_for(lambda:run(['exec',pg,'pg_isready','-h','127.0.0.1'],check=False).returncode==0,120)
    chenv=work/'ch.env'; chenv.write_text('CLICKHOUSE_USER=uptrace\nCLICKHOUSE_PASSWORD='+udata['clickhouse-password']+'\nCLICKHOUSE_DB=uptrace\n'); chenv.chmod(0o600)
    ch_image=T.find(T.docs['uptrace'],'ClickHouseInstallation')['spec']['templates']['podTemplates'][0]['spec']['containers'][0]['image']
    ch=start('clickhouse',ch_image,[],['--network-alias','clickhouse-uptrace1','--tmpfs','/var/lib/clickhouse:rw,size=512m','--tmpfs','/var/log/clickhouse-server:rw,size=128m','--env-file',str(chenv)])
    wait_for(lambda:run(['exec',ch,'bash','-c','true </dev/tcp/127.0.0.1/9000'],check=False).returncode==0,90)
    wait_for(lambda:run(['run','--rm','--network',network,'--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,src={ufile},dst=/etc/uptrace/config.yml,readonly','--env-file',str(uenv),'uptrace/uptrace:2.0.1','config','validate'],check=False).returncode==0,90)
    print('PASS Uptrace: actual binary validates generated config against isolated PostgreSQL/ClickHouse',flush=True)
    uptrace=start('uptrace','uptrace/uptrace:2.0.1',[],['--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,src={ufile},dst=/etc/uptrace/config.yml,readonly','--env-file',str(uenv)])
    uprobe="import urllib.request,urllib.error;\ntry: urllib.request.urlopen('http://"+uptrace+":80/',timeout=2)\nexcept urllib.error.HTTPError: pass"
    wait_for(lambda:run(['exec',n9e,'python3','-c',uprobe],check=False).returncode==0,90)
    ingest="import json,urllib.request,sys; req=urllib.request.Request('http://"+uptrace+":80/v1/traces',data=b'{\"resourceSpans\":[]}',headers={'Content-Type':'application/json','uptrace-dsn':'http://'+sys.argv[1]+'@uptrace:80?grpc=4317'}); assert urllib.request.urlopen(req).status==200"
    # Read the synthetic token from a mounted file rather than a process argument.
    (config/'project-token').write_text(udata['project-token'])
    ingest=ingest.replace("sys.argv[1]", "open('/app/etc/project-token').read()")
    run(['exec',n9e,'python3','-c',ingest])
    print('PASS Uptrace: HTTP server starts with dropped capabilities; authenticated OTLP endpoint accepts request',flush=True)

    bbenv=work/'bb.env'; bbenv.write_text('PG_URL=postgres://bytebase:'+apppass+'@postgres:5432/bytebase?sslmode=disable\nHOME=/tmp\n'); bbenv.chmod(0o600)
    bb=start('bytebase','bytebase/bytebase:3.24.0',['--data','/data','--port','8080','--external-url','http://localhost:8080'],['--user','113:113','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/data:rw,uid=113,gid=113','--tmpfs','/tmp:rw,mode=1777','--env-file',str(bbenv)])
    wait_for(lambda:run(['exec',bb,'curl','-fsS','http://127.0.0.1:8080/healthz'],check=False).returncode==0,120)
    assert run(['exec',bb,'id','-u']).stdout.strip()=='113'
    assert run(['exec',bb,'pgrep','postgres'],check=False).returncode!=0, 'embedded postgres started'
    print('PASS Bytebase: external PostgreSQL non-superuser, UID 113/read-only, HTTP health, no embedded postgres',flush=True)

except Exception:
    for name in containers:
        p=run(['logs','--tail','35',name],check=False)
        output=p.stdout+p.stderr
        for s in all_secrets: output=output.replace(s,'[REDACTED]')
        print(name,output[-2800:])
    raise
finally:
    for name in reversed(containers): run(['rm','-f','-v',name],check=False)
    run(['network','rm',network],check=False)
    T.tearDownClass()
