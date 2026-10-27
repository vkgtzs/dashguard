"""Ensayo privado acotado: una Picamera2, H264 principal y deteccion lores.

No identifica personas, no sincroniza y no modifica el catalogo de produccion.
Dependencias de hardware se importan solo al ejecutar, no al probar la logica.
"""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import time


def estadistica(valores):
    if not valores:
        return None
    orden = sorted(valores)
    return dict(n=len(orden), media=statistics.mean(orden),
                p95=orden[max(0, math.ceil(len(orden)*.95)-1)], maximo=orden[-1])


def cadencia(timestamps):
    diferencias = [(b-a)/1e6 for a, b in zip(timestamps, timestamps[1:])]
    return dict(frames=len(timestamps), intervalos_ms=estadistica(diferencias),
                fps=(len(timestamps)-1)*1e9/(timestamps[-1]-timestamps[0])
                if len(timestamps)>1 and timestamps[-1]>timestamps[0] else None,
                huecos_mayores_100ms=sum(d>100 for d in diferencias),
                no_crecientes=sum(d<=0 for d in diferencias))


def recursos():
    estado = {}
    for linea in Path('/proc/self/status').read_text().splitlines():
        if linea.startswith(('VmRSS:', 'VmHWM:')):
            k, v = linea.split(':', 1)
            estado[k+'_kib'] = int(v.split()[0])
    estado['carga_1_5_15'] = os.getloadavg()
    estado['cpu_sistema_ticks'] = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
    estado['mem_disponible_kib'] = int(next(l.split()[1] for l in
        Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))
    ruta = Path('/sys/class/thermal/thermal_zone0/temp')
    estado['temperatura_c'] = int(ruta.read_text())/1000 if ruta.exists() else None
    if shutil.which('vcgencmd'):
        estado['throttled'] = subprocess.check_output(
            ['vcgencmd', 'get_throttled'], text=True, timeout=3).strip()
    return estado


def modelo(cv2, solicitado):
    candidatos = [Path(solicitado)] if solicitado else [
        Path(getattr(getattr(cv2, 'data', None), 'haarcascades', '/no-existe')) /
        'haarcascade_frontalface_default.xml',
        Path('/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml'),
        Path('/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml')]
    for ruta in candidatos:
        if ruta.is_file():
            detector = cv2.CascadeClassifier(str(ruta))
            if not detector.empty():
                return detector, ruta
    raise RuntimeError('No hay cascade Haar valida; indicar --modelo. No se descarga automaticamente.')


def ejecutar(args):
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FileOutput
    import signal

    for unidad in ('dashguard-sync.timer', 'dashguard-sync.service'):
        r = subprocess.run(['systemctl', '--user', 'is-active', unidad],
                           capture_output=True, text=True, timeout=5)
        if r.stdout.strip() != 'inactive':
            raise RuntimeError('Verificar sincronizacion pausada antes del ensayo: '+unidad)
    # Detectar grabadores conocidos; libcamera tambien rechazara una camara ocupada.
    for ruta in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            partes = ruta.read_bytes().split(b'\0')
        except (OSError, ProcessLookupError):
            continue
        if int(ruta.parent.name) == os.getpid():
            continue
        nombres = [Path(p.decode(errors='replace')).name for p in partes[:3]]
        if any(n in nombres for n in ('rpicam-vid', 'rpicam-hello',
                'video_espacio.py', 'video_continuo.py', 'prueba_rostros.py')):
            raise RuntimeError('Hay otro proceso de camara; no se inicia una segunda captura')
    os.umask(0o077)
    cv2, detector, ruta_modelo = None, None, None
    if args.modo == 'deteccion':
        import cv2
        cv2.setNumThreads(1)
        detector, ruta_modelo = modelo(cv2, args.modelo)
    # Una carpeta nueva por ensayo; nunca sobreescribir ni rotar evidencia previa.
    salida = args.salida.expanduser()
    salida.mkdir(parents=True, exist_ok=False)
    if shutil.disk_usage(salida).free < 256*1024**2:
        raise RuntimeError('Se requieren 256 MiB libres antes del ensayo')
    def expirar(*_):
        raise TimeoutError('Tiempo maximo del ensayo excedido')
    signal.signal(signal.SIGALRM, expirar)
    signal.alarm(args.duracion+45)
    camara = Picamera2()
    frames, analisis, sistema = [], [], []
    informe = dict(estado='iniciado', modo=args.modo, duracion_solicitada_s=args.duracion,
                   opencv=cv2.__version__ if cv2 else None,
                   modelo=str(ruta_modelo) if ruta_modelo else None,
                   advertencia='Deteccion no es identidad. Sin rostro o poca luz son inciertos.')
    grabando = False
    inicio = time.monotonic()
    cpu = time.process_time()
    try:
        config = camara.create_video_configuration(
            main={'size': (1280, 720), 'format': 'YUV420'},
            lores={'size': (320, 180), 'format': 'YUV420'},
            controls={'FrameRate': 15}, buffer_count=4)
        camara.configure(config)
        informe['configuracion'] = camara.camera_configuration()
        def registrar(request):
            marca = request.get_metadata().get('SensorTimestamp')
            if marca is not None:
                frames.append(int(marca))
        camara.post_callback = registrar
        encoder = H264Encoder(bitrate=2_000_000, repeat=True, iperiod=15)
        output = FileOutput(str(salida/'video.h264'), pts=str(salida/'video.pts'))
        camara.start_recording(encoder, output)
        grabando = True
        inicio = time.monotonic()
        cpu = time.process_time()
        siguiente = inicio
        prox_sistema = inicio
        while time.monotonic()-inicio < args.duracion:
            ahora = time.monotonic()
            if ahora >= prox_sistema:
                sistema.append(dict(t_s=ahora-inicio, **recursos()))
                prox_sistema = ahora+1
            if args.modo == 'deteccion' and ahora >= siguiente:
                t0 = time.monotonic()
                request = camara.capture_request()
                try:
                    metadata = request.get_metadata()
                    ancho, alto = camara.stream_configuration('lores')['size']
                    gris = request.make_array('lores')[:alto, :ancho].copy()
                finally:
                    request.release()
                # Se libera el buffer antes de ejecutar OpenCV.
                t1 = time.monotonic()
                caras = detector.detectMultiScale(gris, scaleFactor=1.1,
                    minNeighbors=5, minSize=(30, 30))
                t2 = time.monotonic()
                analisis.append(dict(t_s=t2-inicio,
                    sensor_timestamp_ns=metadata.get('SensorTimestamp'),
                    analisis_ms=(t2-t1)*1000, captura_y_copia_ms=(t1-t0)*1000,
                    total_ms=(t2-t0)*1000, luminancia_media=float(gris.mean()),
                    rostros=[list(map(int, r)) for r in caras],
                    resultado='rostro_detectado' if len(caras) else 'incierto_sin_rostro',
                    identidad='no_evaluada'))
                siguiente = max(siguiente+1/args.hz, t2)
            time.sleep(.005)
        informe['estado'] = 'completado'
    except BaseException as error:
        informe['estado'] = 'interrumpido'
        informe['error'] = type(error).__name__+': '+str(error)
        raise
    finally:
        transcurrido = time.monotonic()-inicio
        try:
            if grabando:
                camara.stop_recording()
        finally:
            camara.close()
            signal.alarm(0)
            informe.update(duracion_real_s=transcurrido,
                cpu_proceso_porcentaje_un_nucleo=100*(time.process_time()-cpu)/transcurrido,
                cadencia_camara=cadencia(frames),
                frecuencia_analisis_hz=len(analisis)/transcurrido,
                tiempo_analisis_ms=estadistica([a['analisis_ms'] for a in analisis]),
                tiempo_total_ms=estadistica([a['total_ms'] for a in analisis]),
                frames_sensor_timestamp_ns=frames, analisis=analisis, sistema=sistema)
            # default=str solo para objetos de configuracion libcamera.
            (salida/'metricas.json').write_text(json.dumps(informe, default=str, indent=2), encoding='utf-8')
            print(json.dumps({k: v for k,v in informe.items() if k not in
                ('frames_sensor_timestamp_ns', 'analisis', 'sistema', 'configuracion')}, indent=2))
    with (salida/'ffprobe.json').open('w') as verificacion:
        subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
            '-show_entries', 'stream=nb_read_frames,r_frame_rate,width,height', '-of', 'json',
            str(salida/'video.h264')], stdout=verificacion, check=True, timeout=120)
    subprocess.run(['ffmpeg', '-v', 'error', '-n', '-r', '15', '-i', str(salida/'video.h264'),
        '-c:v', 'copy', '-movflags', '+faststart', str(salida/'video.mp4')], check=True, timeout=30)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--duracion', type=int, default=60)
    p.add_argument('--hz', type=float, default=2)
    p.add_argument('--modo', choices=['base', 'deteccion'], default='deteccion')
    p.add_argument('--modelo')
    p.add_argument('--salida', type=Path, required=True)
    a = p.parse_args()
    if not 10 <= a.duracion <= 180 or not .2 <= a.hz <= 5:
        p.error('duracion entre 10 y 180 s; hz entre 0.2 y 5')
    ejecutar(a)
