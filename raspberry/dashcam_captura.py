"""Supervisor: sensores + UNA camara, recorrido persistente, sin borrado local."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import uuid
from dashcam_estado import abrir,encolar,recolectar,cerrar,recuperar
from sincronizar import preparar
from video_espacio import esquema

PARAR=False
def detener(*_):
    global PARAR
    PARAR=True


def reloj():
    r=subprocess.run(['timedatectl','show','-p','NTPSynchronized','--value'],
        capture_output=True,text=True,timeout=5)
    return dict(ntp_sincronizado=r.returncode==0 and r.stdout.strip()=='yes',
                observado_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),
                fecha_host_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                advertencia='Hora host; sin RTC, no asumir hora fiable si NTP no sincronizado')


def salud():
    t=Path('/sys/class/thermal/thermal_zone0/temp')
    wifi=Path('/sys/class/net/wlan0/operstate')
    r=subprocess.run(['vcgencmd','get_throttled'],capture_output=True,text=True,timeout=5)
    disponible=next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))
    return dict(boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),
        temperatura_c=int(t.read_text())/1000 if t.exists() else None,
        wifi=wifi.read_text().strip() if wifi.exists() else 'interfaz_no_encontrada',
        throttled=r.stdout.strip(),carga_1min=os.getloadavg()[0],mem_disponible_kib=int(disponible))


def ejecutar(duracion,limite):
    os.umask(0o077)
    raiz=Path.home()/'dashguard'
    (raiz/'datos').mkdir(parents=True,exist_ok=True)
    for s in (signal.SIGINT,signal.SIGTERM):signal.signal(s,detener)
    with (raiz/'.dashcam.lock').open('a') as bloqueo:
        fcntl.flock(bloqueo,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for unidad in ('dashguard-captura.service','dashguard-sync.timer','dashguard-sync.service'):
            r=subprocess.run(['systemctl','--user','is-active',unidad],capture_output=True,text=True)
            if r.stdout.strip() not in ('inactive','unknown','failed'):
                raise RuntimeError('Detener servicio anterior antes de iniciar: '+unidad)
        if shutil.disk_usage(raiz).free < (limite+512)*1024**2:
            raise RuntimeError('Espacio insuficiente para limite de recorrido mas reserva de sistema')
        db=abrir(raiz/'datos/dashguard.sqlite3')
        db.execute('''CREATE TABLE IF NOT EXISTS muestras(id INTEGER PRIMARY KEY,fecha_hora_pc TEXT NOT NULL,
                     monotonic_s REAL NOT NULL,datos_json TEXT NOT NULL,boot_id TEXT,boottime_ns INTEGER)''')
        db.commit()
        preparar(db); esquema(db); recuperar(db)
        id=str(uuid.uuid4()); boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        inicio=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        carpeta=raiz/'videos/recorridos'/id
        carpeta.mkdir(parents=True)
        db.execute('INSERT INTO dashcam_recorridos VALUES(?,?,?,?,?,?,?,?)',
                   (id,boot,inicio,inicio,None,'activo',str(carpeta),str(uuid.uuid4())))
        encolar(db,id,id,'inicio',dict(boot_id=boot,inicio_boottime_ns=inicio,reloj=reloj(),
                 duracion_solicitada_s=duracion,limite_mib=limite,video='1280x720 15fps nominales 2Mbps',
                 politica='Sin rotacion ni borrado automatico'))
        db.commit()
        print('RECORRIDO:',id,'|',carpeta,flush=True)
        codigo=Path(__file__).resolve().parent
        sensores=video=None
        estado='error'; error=None; mediciones_salud=[]
        try:
            sensores=subprocess.Popen([sys.executable,'-u',str(codigo/'dashguard_local.py')])
            espera=time.monotonic()+30
            while time.monotonic()<espera:
                if PARAR: raise RuntimeError('Apagado durante inicializacion')
                if sensores.poll() is not None:raise RuntimeError('Registrador de sensores termino')
                ultima=db.execute('SELECT max(boottime_ns) FROM muestras WHERE boot_id=?',(boot,)).fetchone()[0]
                if ultima and ultima>=inicio:break
                time.sleep(.2)
            else:raise RuntimeError('Sin muestras nuevas tras 30 s')
            video=subprocess.Popen([sys.executable,'-u',str(codigo/'video_espacio.py'),
                 '--duracion',str(duracion),'--segmento','300','--limite-mib',str(limite),
                 '--conservar','--carpeta',str(carpeta)])
            apagando=False
            proxima_salud=0
            while video.poll() is None:
                ahora=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                db.execute('UPDATE dashcam_recorridos SET ultimo_ns=? WHERE id=?',(ahora,id))
                recolectar(db,id); db.commit()
                if time.monotonic()>=proxima_salud:
                    m=salud();mediciones_salud.append(m)
                    with (carpeta/'salud.jsonl').open('a',encoding='utf-8') as registro:
                        registro.write(json.dumps(m)+'\n')
                    proxima_salud=time.monotonic()+10
                if sensores.poll() is not None:
                    error='Registrador de sensores termino durante video'
                    video.send_signal(signal.SIGTERM); apagando=True
                if PARAR and not apagando:
                    video.send_signal(signal.SIGTERM); apagando=True
                time.sleep(.5)
            if video.returncode: raise RuntimeError('Grabador termino con codigo '+str(video.returncode))
            if error:raise RuntimeError(error)
            estado='detenido' if PARAR else 'completo'
        except BaseException as exc:
            error=str(exc)
            print('ERROR RECORRIDO:',error,flush=True)
        finally:
            if video and video.poll() is None:
                video.send_signal(signal.SIGTERM)
                try:video.wait(timeout=45)
                except subprocess.TimeoutExpired:video.kill();video.wait();error='Grabador no cerro a tiempo; revisar parciales'
            if sensores and sensores.poll() is None:
                sensores.send_signal(signal.SIGINT)
                try:sensores.wait(timeout=10)
                except subprocess.TimeoutExpired:sensores.kill();sensores.wait()
            fin=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
            while recolectar(db,id,fin)==200:db.commit()
            parciales=[str(p.relative_to(carpeta)) for p in carpeta.rglob('*.h264')]
            if parciales:estado='incompleto'
            trip=db.execute('SELECT * FROM dashcam_recorridos WHERE id=?',(id,)).fetchone()
            temperaturas=[m['temperatura_c'] for m in mediciones_salud if m['temperatura_c'] is not None]
            resumen=dict(muestras=len(mediciones_salud),temperatura_max_c=max(temperaturas) if temperaturas else None,
               wifi_estados=sorted(set(m['wifi'] for m in mediciones_salud)),
               throttled_observados=sorted(set(m['throttled'] for m in mediciones_salud)),
               memoria_disponible_min_kib=min((m['mem_disponible_kib'] for m in mediciones_salud),default=None),
               carga_1min_max=max((m['carga_1min'] for m in mediciones_salud),default=None))
            cerrar(db,trip,fin,estado,dict(error=error,parciales=parciales,reloj=reloj(),cierre_estimado=False,salud=resumen,
                                         presentacion_origen='raspberry',segmento_solicitado_s=300))
            db.commit();db.close()
            print('CIERRE:',id,estado,'parciales:',len(parciales),flush=True)
        if error or estado=='incompleto':raise RuntimeError(error or 'Hay brutos pendientes de recuperar')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--duracion',type=int,default=1800)
    p.add_argument('--limite-mib',type=int,default=1024)
    a=p.parse_args()
    if not 10<=a.duracion<=7200 or a.limite_mib<128:p.error('Duracion 10..7200 s; limite >=128 MiB')
    ejecutar(a.duracion,a.limite_mib)
