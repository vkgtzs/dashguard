"""Diagnostico de 15 segundos: tiempos de sensor y PTS, sin tocar SQLite."""
import json
import statistics
import subprocess
import time
import uuid
from pathlib import Path


def analizar(metadata, pts):
    sensores = [f.get('SensorTimestamp') for f in metadata]
    if not sensores or any(not isinstance(s, int) or isinstance(s, bool) for s in sensores):
        raise ValueError('Falta SensorTimestamp numerico en uno o mas fotogramas')
    deltas = [(b-a)/1e6 for a,b in zip(sensores,sensores[1:])]
    if not deltas or any(d<=0 for d in deltas):
        raise ValueError('Timestamps insuficientes o no crecientes')
    mediana = statistics.median(deltas)
    return dict(fotogramas_metadata=len(sensores),fotogramas_pts=len(pts),
        conteos_coinciden=len(sensores)==len(pts),
        primer_sensor_ns=sensores[0],ultimo_sensor_ns=sensores[-1],
        intervalo_mediano_ms=mediana,intervalo_maximo_ms=max(deltas),
        intervalos_mayores_1_5_mediana=sum(d>1.5*mediana for d in deltas),
        pts_crecientes=all(b>a for a,b in zip(pts,pts[1:])),
        nota='Conteos e intervalos son diagnostico; no prueban correspondencia exacta ni ausencia de perdidas')


def relojes():
    antes=time.monotonic_ns()
    boot=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    despues=time.monotonic_ns()
    return dict(monotonic_ns=(antes+despues)//2,boottime_ns=boot,
        diferencia_ns=boot-(antes+despues)//2,incertidumbre_lectura_ns=despues-antes)


def main():
    carpeta=Path.home()/'dashguard/videos/tiempos'/str(uuid.uuid4())
    carpeta.mkdir(parents=True)
    inicio=relojes()
    subprocess.run(['rpicam-vid','--nopreview','--timeout','15000',
        '--width','1280','--height','720','--framerate','15','--codec','h264',
        '--bitrate','2000000','--inline','--save-pts',str(carpeta/'frames.pts'),
        '--metadata',str(carpeta/'metadata.json'),'--metadata-format','json',
        '--output',str(carpeta/'video.h264')],check=True)
    fin=relojes()
    metadata=json.loads((carpeta/'metadata.json').read_text())
    pts=[float(l) for l in (carpeta/'frames.pts').read_text().splitlines()
         if l.strip() and not l.startswith('#')]
    reporte=analizar(metadata,pts)
    reporte.update(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                   reloj_inicio=inicio,reloj_fin=fin)
    (carpeta/'reporte.json').write_text(json.dumps(reporte,indent=2))
    print(json.dumps(reporte,indent=2))
    print('Archivos conservados en:',carpeta)


if __name__=='__main__':
    main()
