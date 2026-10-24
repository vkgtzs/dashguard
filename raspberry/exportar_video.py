"""Une la ultima secuencia retenida de loop_espacio; no borra originales."""
import bisect
import json
import shutil
import sqlite3
import subprocess
import uuid
from contextlib import closing
from fractions import Fraction
from pathlib import Path
try:
    import fcntl
except ImportError:
    fcntl = None


def ultima_secuencia(filas):
    # Entrada cronologica del catalogo; nunca ordenar UUID alfabeticamente.
    if not filas:
        raise ValueError('No hay segmentos registrados')
    resultado=[filas[-1]]
    for fila in reversed(filas[:-1]):
        siguiente=resultado[0]
        if fila['boot_id']!=siguiente['boot_id'] or fila['fin_ns']!=siguiente['inicio_ns']:
            break
        resultado.insert(0,fila)
    return resultado


def informacion(ruta):
    r=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames',
        '-show_entries','stream=codec_name,width,height,avg_frame_rate,nb_read_frames,duration',
        '-of','json',str(ruta)],check=True,capture_output=True,text=True,timeout=120)
    if r.stderr.strip():
        raise ValueError('Error de decodificacion: '+r.stderr)
    return json.loads(r.stdout)['streams'][0]


def metadatos_segmento(datos, info, desplazamiento):
    sensores=datos['sensor_timestamps_ns']
    fps=float(Fraction(info['avg_frame_rate']))
    frames=int(info['nb_read_frames'])
    if frames!=len(sensores) or fps<=0 or any(b<=a for a,b in zip(sensores,sensores[1:])):
        raise ValueError('No coincide numero u orden de frames con JSON')
    duracion=frames/fps
    if abs(float(info['duration'])-duracion)>0.05:
        raise ValueError('Duracion incompatible con exportacion CFR')
    muestras=[]
    for muestra in datos['muestras']:
        indice=bisect.bisect_right(sensores,muestra['boottime_ns'])-1
        if not 0<=indice<frames:
            raise ValueError('Medicion fuera del segmento')
        muestras.append({**muestra,
            'tiempo_video_s_aproximado':desplazamiento+indice/fps,
            'frame_precedente_en_segmento':indice})
    return dict(video_id=datos['video_id'],archivo_original=datos['archivo'],
        inicio_video_s=desplazamiento,duracion_video_s=duracion,
        inicio_ns=datos['inicio_ns'],fin_exclusivo_ns=datos['fin_exclusivo_ns'],
        sensor_timestamps_ns=sensores,pts_originales_ms=datos['pts_originales_ms'],
        muestras=muestras),duracion


def main():
    if fcntl is None:
        raise RuntimeError('Ejecutar exportacion en Raspberry/Linux')
    base=Path.home()/'dashguard'
    carpeta=base/'videos/loop_espacio'
    if not carpeta.is_dir(): raise RuntimeError('No existe carpeta loop_espacio')
    # El mismo bloqueo del grabador impide que rote archivos durante exportacion.
    with (carpeta/'.grabacion.lock').open('a') as bloqueo:
        try: fcntl.flock(bloqueo,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('Detener video_espacio.py antes de exportar')
        ruta=base/'datos/dashguard.sqlite3'
        with closing(sqlite3.connect(f'{ruta.as_uri()}?mode=ro',uri=True)) as db:
            db.row_factory=sqlite3.Row
            filas=db.execute('SELECT * FROM videos_espacio ORDER BY rowid').fetchall()
            seleccion=ultima_secuencia(filas)
        archivos=[]; metadata=[]; offset=0; firma=None; total_frames=0
        for fila in seleccion:
            nombre=fila['archivo']
            if nombre!=str(uuid.UUID(fila['id']))+'.mp4':
                raise ValueError('Nombre no coincide con UUID registrado')
            archivo=carpeta/nombre
            if archivo.resolve().parent!=carpeta.resolve(): raise ValueError('Ruta fuera de carpeta')
            datos=json.loads(archivo.with_suffix('.json').read_text())
            if (datos['video_id']!=fila['id'] or datos['boot_id']!=fila['boot_id']
                    or datos['inicio_ns']!=fila['inicio_ns'] or datos['fin_exclusivo_ns']!=fila['fin_ns']):
                raise ValueError('JSON no coincide con catalogo')
            info=informacion(archivo)
            actual=tuple(info[k] for k in ('codec_name','width','height','avg_frame_rate'))
            if firma is not None and firma!=actual: raise ValueError('Formatos de video distintos')
            firma=actual
            segmento,duracion=metadatos_segmento(datos,info,offset)
            metadata.append(segmento); offset+=duracion
            total_frames+=int(info['nb_read_frames']); archivos.append(archivo)
        salida=base/'exportaciones'
        salida.mkdir(exist_ok=True)
        necesarios=sum(p.stat().st_size for p in archivos)*1.2+256*1024**2
        if shutil.disk_usage(salida).free<necesarios: raise RuntimeError('Espacio insuficiente para exportar')
        sesion=salida/('exportacion_'+str(uuid.uuid4()))
        sesion.mkdir()
        listado=sesion/'segmentos.txt'
        # Los nombres son UUID verificados; escapar tambien el directorio del usuario.
        listado.write_text(''.join("file '"+str(p).replace("'", "'\\''")+"'\n" for p in archivos),encoding='utf-8')
        temporal=sesion/'recorrido.part.mp4'
        subprocess.run(['ffmpeg','-v','error','-n','-f','concat','-safe','0','-i',str(listado),
            '-c:v','copy','-movflags','+faststart',str(temporal)],check=True,timeout=600)
        final_info=informacion(temporal)
        if int(final_info['nb_read_frames'])!=total_frames:
            raise ValueError('El video exportado no conserva todos los frames')
        if abs(float(final_info['duration'])-offset)>0.1:
            raise ValueError('Duracion final distinta de la suma; revisar antes de usar timeline')
        temporal.rename(sesion/'recorrido.mp4')
        resultado=dict(archivo='recorrido.mp4',boot_id=seleccion[0]['boot_id'],
            duracion_video_s=offset,fotogramas=total_frames,segmentos=metadata,
            aviso='Solo ultima secuencia conservada; no incluye clips rotados. Tiempos de reproduccion CFR; '+
            'mediciones mapeadas al frame precedente, sin interpolar IMU/GPS.')
        (sesion/'recorrido.json').write_text(json.dumps(resultado,ensure_ascii=False),encoding='utf-8')
        listado.unlink()
        print(f'Exportados {len(archivos)} segmentos, {total_frames} frames, {offset:.2f} segundos')
        print('Video:',sesion/'recorrido.mp4')
        print('Telemetria:',sesion/'recorrido.json')
        print('Originales conservados. La exportacion no cuenta en la cuota de 30 MiB.')


if __name__=='__main__': main()
