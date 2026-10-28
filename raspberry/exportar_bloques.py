"""Convierte un recorrido cerrado en bloques MP4 ~5 min, sin recodificar/borrar."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
from dashcam_estado import sha_archivo


def contar_paquetes(archivo):
    r=subprocess.run(['ffmpeg','-v','error','-nostats','-i',str(archivo),'-map','0:v:0',
        '-c:v','copy','-f','null','-','-progress','pipe:1'],capture_output=True,text=True,check=True,timeout=300)
    valores=re.findall(r'^frame=(\d+)',r.stdout,re.M)
    if not valores or r.stderr.strip():raise ValueError('No se pudo verificar el bloque')
    return int(valores[-1])


def ejecutar(recorrido,segundos):
    os.umask(0o077)
    raiz=Path.home()/'dashguard'
    db=sqlite3.connect((raiz/'datos/dashguard.sqlite3').as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    trip=db.execute('SELECT * FROM dashcam_recorridos WHERE id=?',(recorrido,)).fetchone()
    if not trip or trip['estado'] not in ('completo','detenido'):raise ValueError('Recorrido no cerrado correctamente')
    videos=db.execute('SELECT * FROM dashcam_archivos WHERE recorrido_id=?',(recorrido,)).fetchall()
    fuentes=[]
    for v in videos:
        archivo=Path(v['ruta'])
        if archivo.resolve().parent!=Path(trip['carpeta']).resolve():raise ValueError('Ruta fuera del recorrido')
        if sha_archivo(archivo)!=v['sha256']:raise ValueError('Fuente modificada')
        meta=json.loads(archivo.with_suffix('.json').read_text())
        fuentes.append((meta['inicio_ns'],archivo,len(meta['sensor_timestamps_ns'])))
    fuentes.sort()
    if not fuentes:raise ValueError('Sin fuentes')
    salida=raiz/'exportaciones'/recorrido/('bloques_'+str(segundos))
    salida.mkdir(parents=True,exist_ok=False)
    if shutil.disk_usage(salida).free<sum(a.stat().st_size for _,a,_ in fuentes)*1.1+256*1024**2:
        raise ValueError('Falta espacio para exportar sin borrar fuentes')
    listado=salida/'fuentes.ffconcat'
    listado.write_text(''.join("file '"+str(a).replace("'","'\\''")+"'\n" for _,a,_ in fuentes))
    subprocess.run(['ffmpeg','-v','error','-n','-f','concat','-safe','0','-i',str(listado),
       '-map','0:v:0','-c:v','copy','-f','segment','-segment_time',str(segundos),
       '-reset_timestamps','1','-segment_format','mp4','-segment_format_options','movflags=+faststart',
       str(salida/'bloque_%03d.mp4')],check=True,timeout=1200)
    bloques=[]
    for i,archivo in enumerate(sorted(salida.glob('bloque_*.mp4')),1):
        n=contar_paquetes(archivo)
        bloques.append(dict(numero=i,archivo=archivo.name,frames=n,duracion_nominal_s=n/15,
                            bytes=archivo.stat().st_size,sha256=sha_archivo(archivo)))
    total=sum(b['frames'] for b in bloques)
    if total!=sum(n for _,_,n in fuentes):raise ValueError('Conteo distinto: conservar todo y revisar')
    informe=dict(recorrido_id=recorrido,bloques=bloques,frames=total,
                 originales_conservados=True,recodificado=False,
                 nota='Cortes en fotogramas clave; duraciones pueden diferir hasta un GOP')
    (salida/'bloques.json').write_text(json.dumps(informe,indent=2))
    print(json.dumps(informe,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('recorrido')
    p.add_argument('--segundos',type=int,choices=[300,600],default=300)
    a=p.parse_args();ejecutar(a.recorrido,a.segundos)
