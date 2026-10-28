"""Recuperacion aditiva de un H264; conserva bruto, tiempos y cierre original."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import uuid
from dashcam_estado import abrir,encolar,sha_archivo,partes_archivo
from video_espacio import contar_frames,validar_tiempos


def recuperar(recorrido,sesion,nombre):
    os.umask(0o077)
    uuid.UUID(recorrido)
    if Path(sesion).name!=sesion or Path(nombre).name!=nombre or not nombre.endswith('.h264'):
        raise ValueError('Se requieren nombres relativos simples')
    raiz=Path.home()/'dashguard'
    db=abrir(raiz/'datos/dashguard.sqlite3')
    trip=db.execute('SELECT * FROM dashcam_recorridos WHERE id=?',(recorrido,)).fetchone()
    if not trip or trip['estado'] not in ('incompleto','error','interrumpido'):
        raise ValueError('Recuperar solo recorridos cerrados con fallo')
    carpeta=Path(trip['carpeta']);directorio=carpeta/sesion;bruto=directorio/nombre
    if bruto.resolve().parent.parent!=carpeta.resolve():raise ValueError('Ruta fuera del recorrido')
    pendientes=json.loads((directorio/'tiempos_pendientes.json').read_text())
    if pendientes['boot_id']!=trip['boot_id']:raise ValueError('Boot incompatible')
    brutos=sorted(directorio.glob('*.h264'))
    if brutos!=[bruto]:raise ValueError('Multiples brutos: requiere revisar orden antes de recuperar')
    n=contar_frames(bruto);s=pendientes['sensor_timestamps_ns'];p=pendientes['pts_ms']
    k=min(n,len(s),len(p))
    if k<=0 or n-k>1 or abs(len(p)-n)>1:raise ValueError('Desajuste superior a un fotograma: revisar manualmente')
    validar_tiempos(s[:k],p[:k],pendientes['base_sensor'],pendientes['base_pts'],None)
    sha_bruto=sha_archivo(bruto)
    id=str(uuid.uuid5(uuid.UUID(recorrido),'recuperacion:'+sha_bruto))
    if db.execute('SELECT 1 FROM dashcam_archivos WHERE id=?',(id,)).fetchone():
        print(json.dumps(dict(video_id=id,ya_recuperado=True)));return
    final=carpeta/(id+'.mp4');sidecar=final.with_suffix('.json')
    if final.exists() or sidecar.exists():raise ValueError('Destino existe: no sobrescribir; revisar recuperacion anterior')
    subprocess.run(['ffmpeg','-v','error','-n','-fflags','+genpts','-r','15','-i',str(bruto),
                    '-c:v','copy','-movflags','+faststart',str(final)],check=True,timeout=180)
    if contar_frames(final)!=n:raise ValueError('Conteo distinto: conservar y revisar')
    sha=sha_archivo(final);bytes_video=final.stat().st_size
    muestras=db.execute('SELECT muestra_id,fecha_hora_pc,boottime_ns,datos_json FROM muestras WHERE boot_id=? AND boottime_ns>=? AND boottime_ns<=? ORDER BY boottime_ns',
                        (trip['boot_id'],s[0],s[k-1])).fetchall()
    meta=dict(video_id=id,archivo=final.name,boot_id=trip['boot_id'],inicio_ns=s[0],fin_exclusivo_ns=s[k-1]+1,
        sensor_timestamps_ns=s[:k],pts_originales_ms=p[:k],frames_video=n,frames_con_tiempos=k,
        asociacion_incompleta=n!=k,recuperado=True,
        advertencia=f'Recuperado sin recodificar. {n-k} fotogramas sin SensorTimestamp. Fin temporal corresponde solo a marcas conocidas. Cierre original conservado.',
        bruto_origen=nombre,bruto_sha256=sha_bruto,pts_sin_sensor_ms=p[k:],
        muestras=[dict(muestra_id=m[0],fecha_hora=m[1],boottime_ns=m[2],datos=json.loads(m[3])) for m in muestras])
    with sidecar.open('x',encoding='utf-8') as f:json.dump(meta,f,ensure_ascii=False)
    config=json.loads((raiz/'config/dashcam.json').read_text(encoding='utf-8-sig'))
    contenido=dict(metadata=meta,bytes=bytes_video,sha256=sha,recuperado=True,
        segundos_solicitados=300,numero=1+db.execute('SELECT count(*) FROM dashcam_archivos WHERE recorrido_id=?',(recorrido,)).fetchone()[0])
    if bytes_video>8*1024**2:contenido['partes']=partes_archivo(final,config['device_id'],recorrido,id)
    with db:
        db.execute('INSERT INTO videos_espacio(id,archivo,boot_id,inicio_ns,fin_ns,protegido) VALUES(?,?,?,?,?,1)',
                   (id,final.name,trip['boot_id'],s[0],s[k-1]+1))
        db.executemany('INSERT INTO video_muestras VALUES(?,?)',[(id,m[0]) for m in muestras if m[0]])
        db.execute('INSERT INTO dashcam_archivos(id,recorrido_id,ruta,sha256,bytes) VALUES(?,?,?,?,?)',
                   (id,recorrido,str(final),sha,bytes_video))
        encolar(db,id,recorrido,'video',contenido)
    db.close()
    print(json.dumps(dict(video_id=id,frames=n,frames_con_tiempos=k,segundos_nominales=n/15,
        bytes=bytes_video,original_conservado=bruto.exists(),cierre_original_sin_modificar=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('recorrido');p.add_argument('sesion');p.add_argument('archivo')
    a=p.parse_args();recuperar(a.recorrido,a.sesion,a.archivo)
