"""Outbox -> backend HTTPS -> nube. Reintenta segmentos completos, no borra nada."""
import argparse
import json
from pathlib import Path
import signal
import time
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from dashcam_estado import abrir,sha_archivo

PARAR=False
def detener(*_):
    global PARAR
    PARAR=True


def configurar(ruta):
    config=json.loads(ruta.read_text(encoding='utf-8-sig'))
    url=urlsplit(config['backend'])
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise ValueError('Se requiere origen HTTPS del backend, sin credenciales ni ruta')
    if len(config.get('device_token',''))<32:raise ValueError('Token de dispositivo ausente')
    return config


def peticion(config,path,body,method='POST',tipo='application/json',sha=None,enviar=urlopen):
    headers={'Authorization':'Bearer '+config['device_token'],'Content-Type':tipo}
    if sha:headers['X-Content-Sha256']=sha
    req=Request(config['backend'].rstrip('/')+path,data=body,headers=headers,method=method)
    with enviar(req,timeout=120) as r:
        if r.status!=200:raise ValueError('Respuesta HTTP inesperada '+str(r.status))
        return json.load(r)


def una_vez(db,config,enviar=urlopen):
    trabajo=0
    for fila in db.execute('SELECT * FROM dashcam_archivos WHERE confirmado IS NULL ORDER BY rowid LIMIT 10').fetchall():
        ruta=Path(fila['ruta'])
        if not ruta.is_file() or ruta.stat().st_size!=fila['bytes'] or sha_archivo(ruta)!=fila['sha256']:
            raise ValueError('Video local ausente o modificado: '+fila['id'])
        if fila['bytes']>8*1024**2:raise ValueError('Segmento supera limite de subida; conservar y revisar')
        r=peticion(config,f"/dashcam/videos/{fila['recorrido_id']}/{fila['id']}",ruta.read_bytes(),
            method='PUT',tipo='video/mp4',sha=fila['sha256'],enviar=enviar)
        if (r.get('video_id')!=fila['id'] or r.get('recorrido_id')!=fila['recorrido_id'] or
            r.get('sha256')!=fila['sha256'] or r.get('device_id')!=config['device_id'] or r.get('bytes')!=fila['bytes']):
            raise ValueError('Servidor no confirmo video, checksum, tamano y dispositivo')
        with db:db.execute('UPDATE dashcam_archivos SET confirmado=? WHERE id=?',
                          (time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),fila['id']))
        trabajo+=1
        print('Video confirmado:',fila['id'],flush=True)
    filas=db.execute('''SELECT o.* FROM dashcam_outbox o LEFT JOIN dashcam_archivos a ON a.id=o.id
       WHERE o.confirmado IS NULL AND (o.tipo<>'video' OR a.confirmado IS NOT NULL)
       ORDER BY o.rowid LIMIT 100''').fetchall()
    if filas:
        cuerpo={'registros':[{k:f[k] for k in ('id','recorrido_id','tipo','contenido_json','sha256')} for f in filas]}
        r=peticion(config,'/dashcam/registros',json.dumps(cuerpo,allow_nan=False).encode(),enviar=enviar)
        confirmados=r.get('confirmados')
        if not isinstance(confirmados,list) or len(confirmados)!=len(filas):raise ValueError('Confirmacion de lote incompleta')
        por_id={c.get('id'):c for c in confirmados}
        if len(por_id)!=len(filas):raise ValueError('Confirmaciones duplicadas')
        for f in filas:
            c=por_id.get(f['id'],{})
            if c.get('sha256')!=f['sha256'] or c.get('device_id')!=config['device_id']:
                raise ValueError('UUID/checksum/dispositivo no confirmado; lote permanece pendiente')
        with db:
            db.executemany('UPDATE dashcam_outbox SET confirmado=?,ultimo_error=NULL WHERE id=?',
                [(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),f['id']) for f in filas])
        trabajo+=len(filas)
        print('Registros confirmados:',len(filas),flush=True)
    return trabajo


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path.home()/'dashguard/config/dashcam.json')
    p.add_argument('--una-vez',action='store_true')
    a=p.parse_args()
    for s in (signal.SIGINT,signal.SIGTERM):signal.signal(s,detener)
    config=configurar(a.config)
    db=abrir(Path.home()/'dashguard/datos/dashguard.sqlite3')
    try:
        while not PARAR:
            try: trabajo=una_vez(db,config)
            except Exception as error:
                print('Sync pendiente, sin borrar:',type(error).__name__,str(error)[:200],flush=True)
                if a.una_vez:raise
                trabajo=0
            if a.una_vez:break
            for _ in range(1 if trabajo else 30):
                if PARAR:break
                time.sleep(1)
    finally:db.close()
