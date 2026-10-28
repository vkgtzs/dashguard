"""Informe agregado local: continuidad, integridad, sensores y confirmaciones.
No exporta coordenadas, imagenes ni credenciales. No modifica ni borra datos.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import statistics
from dashcam_estado import sha_archivo


def verificar(db,recorrido=None):
    db.row_factory=sqlite3.Row
    trip=db.execute('SELECT * FROM dashcam_recorridos '+('WHERE id=?' if recorrido else 'ORDER BY rowid DESC LIMIT 1'),
                    (recorrido,) if recorrido else ()).fetchone()
    if trip is None:raise ValueError('No hay recorrido local')
    filas=db.execute('SELECT * FROM dashcam_outbox WHERE recorrido_id=?',(trip['id'],)).fetchall()
    grupos={tipo:[f for f in filas if f['tipo']==tipo] for tipo in ('inicio','fin','muestra','video')}
    inicio=json.loads(grupos['inicio'][0]['contenido_json']) if grupos['inicio'] else {}
    fin=json.loads(grupos['fin'][0]['contenido_json']) if grupos['fin'] else {}
    muestras=[json.loads(f['contenido_json']) for f in grupos['muestra']]
    errores=[];marcas=[];frames=0;pesos=0
    videos=db.execute('SELECT * FROM dashcam_archivos WHERE recorrido_id=?',(trip['id'],)).fetchall()
    orden=[]
    for video in videos:
        ruta=Path(video['ruta'])
        if ruta.resolve().parent!=Path(trip['carpeta']).resolve():
            errores.append('Ruta fuera del recorrido: '+video['id']);continue
        if not ruta.is_file():errores.append('Falta video: '+video['id']);continue
        if ruta.stat().st_size!=video['bytes'] or sha_archivo(ruta)!=video['sha256']:
            errores.append('No coincide integridad: '+video['id'])
        pesos+=ruta.stat().st_size
        meta=json.loads(ruta.with_suffix('.json').read_text(encoding='utf-8'))
        s=meta['sensor_timestamps_ns'];p=meta['pts_originales_ms']
        if len(s)!=len(p) or not s:errores.append('Conteos de tiempos: '+video['id'])
        if meta['boot_id']!=trip['boot_id']:errores.append('boot_id distinto: '+video['id'])
        orden.append((s,meta['fin_exclusivo_ns']))
        protegido=db.execute('SELECT protegido FROM videos_espacio WHERE id=?',(video['id'],)).fetchone()
        if not protegido or not protegido[0]:errores.append('Video sin proteccion: '+video['id'])
    orden.sort(key=lambda v:v[0][0])
    for s,_ in orden:marcas.extend(s);frames+=len(s)
    deltas=[(b-a)/1e6 for a,b in zip(marcas,marcas[1:])]
    fronteras=sum(a[1]!=b[0][0] for a,b in zip(orden,orden[1:]))
    media=statistics.mean(deltas) if deltas else None
    salud=[];ruta=Path(trip['carpeta'])/'salud.jsonl'
    if ruta.is_file():salud=[json.loads(l) for l in ruta.read_text().splitlines() if l.strip()]
    return dict(recorrido_id=trip['id'],estado=trip['estado'],boot_id=trip['boot_id'],
       duracion_solicitada_s=inicio.get('duracion_solicitada_s'),
       duracion_supervisor_s=(trip['fin_ns']-trip['inicio_ns'])/1e9 if trip['fin_ns'] else None,
       ntp_inicio=inicio.get('reloj',{}).get('ntp_sincronizado'),ntp_cierre=fin.get('reloj',{}).get('ntp_sincronizado'),
       videos=len(videos),videos_confirmados=sum(bool(v['confirmado']) for v in videos),
       video_mib=pesos/1024**2,frames_catalogados=frames,
       duracion_video_nominal_s=frames/15,
       duracion_sensor_aproximada_s=(marcas[-1]-marcas[0])/1e9+media/1000 if deltas else None,
       fps_sensor=1000/media if media else None,
       intervalo_maximo_ms=max(deltas) if deltas else None,
       huecos_mayores_100ms=sum(d>100 for d in deltas),timestamps_no_crecientes=sum(d<=0 for d in deltas),
       fronteras_discontinuas=fronteras,errores_integridad=errores,
       muestras=len(muestras),gps_validas=sum(m['datos'].get('gps_valido') is True for m in muestras),
       imu_validas=sum(m['datos'].get('imu_valida') is True for m in muestras),
       registros=len(filas),registros_confirmados=sum(bool(f['confirmado']) for f in filas),
       parciales=[str(p.relative_to(Path(trip['carpeta']))) for p in Path(trip['carpeta']).rglob('*.h264')],
       salud=fin.get('salud'),muestras_salud=len(salud),
       wifi_observado=sorted(set(m['wifi'] for m in salud)),error_cierre=fin.get('error'),
       limite='PTS/camara y marcas host; no garantiza precision fisica ni ausencia absoluta de perdidas')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--recorrido')
    p.add_argument('--db',type=Path,default=Path.home()/'dashguard/datos/dashguard.sqlite3')
    a=p.parse_args()
    with sqlite3.connect(a.db.resolve().as_uri()+'?mode=ro',uri=True) as db:
        print(json.dumps(verificar(db,a.recorrido),indent=2))
