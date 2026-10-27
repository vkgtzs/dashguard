"""Resume evidencia privada del ensayo sin publicar videos ni rectangulos."""
import argparse
import json
from pathlib import Path
from prueba_rostros import estadistica


def resumir(carpeta):
    datos = json.loads((carpeta/'metricas.json').read_text(encoding='utf-8'))
    sistema = datos['sistema']
    ticks = [r['cpu_sistema_ticks'] for r in sistema]
    cpu = []
    for a, b in zip(ticks, ticks[1:]):
        delta = [y-x for x,y in zip(a,b)]
        total = sum(delta)
        if total>0:
            cpu.append(100*(total-delta[3]-delta[4])/total)
    pts = [float(l) for l in (carpeta/'video.pts').read_text().splitlines()
           if l.strip() and not l.startswith('#')]
    intervalos = [b-a for a,b in zip(pts, pts[1:])]
    probe = json.loads((carpeta/'ffprobe.json').read_text())
    decodificados = int(probe['streams'][0]['nb_read_frames'])
    return dict(ensayo=carpeta.name, estado=datos['estado'], modo=datos['modo'],
        duracion_real_s=datos['duracion_real_s'],
        analisis_ms=datos['tiempo_analisis_ms'], total_ms=datos['tiempo_total_ms'],
        analisis_hz=datos['frecuencia_analisis_hz'],
        analisis_con_rostro=sum(bool(a['rostros']) for a in datos['analisis']),
        analisis_totales=len(datos['analisis']),
        cpu_proceso_porcentaje_un_nucleo=datos['cpu_proceso_porcentaje_un_nucleo'],
        cpu_sistema_porcentaje=estadistica(cpu),
        carga_maxima_1min=max(r['carga_1_5_15'][0] for r in sistema),
        temperatura_maxima_c=max(r['temperatura_c'] for r in sistema if r['temperatura_c'] is not None),
        rss_maximo_mib=max(r['VmRSS_kib'] for r in sistema)/1024,
        memoria_disponible_minima_mib=min(r['mem_disponible_kib'] for r in sistema)/1024,
        throttled_observados=sorted(set(r.get('throttled','no_disponible') for r in sistema)),
        cadencia_camara=datos['cadencia_camara'], frames_decodificados=decodificados,
        pts_numero=len(pts), pts_intervalos_ms=estadistica(intervalos),
        pts_fps=(len(pts)-1)*1000/(pts[-1]-pts[0]) if len(pts)>1 else None,
        conteos_coinciden=decodificados==len(pts)==datos['cadencia_camara']['frames'],
        advertencia='No mide exactitud ni identidad. Revisar imagen y condiciones presencialmente.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('carpetas', nargs='+', type=Path)
    a = p.parse_args()
    print(json.dumps([resumir(c.expanduser()) for c in a.carpetas],indent=2))
