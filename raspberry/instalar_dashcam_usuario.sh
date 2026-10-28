#!/bin/sh
# Ejecutar desde un release completo. No necesita sudo ni descarga paquetes.
set -eu
umask 077
codigo_dashcam=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
raiz_dashcam="$HOME/dashguard"
for programa_dashcam in python3 rpicam-vid ffmpeg ffprobe; do command -v "$programa_dashcam" >/dev/null; done
python3 -c 'import serial; from smbus import SMBus'
for archivo_dashcam in dashcam_captura.py dashcam_estado.py dashcam_sync.py dashguard_local.py imu_segura.py video_espacio.py sincronizar.py retencion.py; do
    test -f "$codigo_dashcam/$archivo_dashcam"
done
test -f "$raiz_dashcam/config/dashcam.json"
python3 -c 'import json,pathlib; c=json.loads((pathlib.Path.home()/"dashguard/config/dashcam.json").read_text()); assert c["backend"].startswith("https://") and len(c["device_token"])>=32'
if test "$(loginctl show-user "$(id -un)" -p Linger --value)" != yes; then
    echo 'Falta habilitar linger con sudo loginctl enable-linger para este usuario.' >&2
    exit 1
fi
if test -e "$raiz_dashcam/app" && ! test -L "$raiz_dashcam/app"; then
    echo 'app existe y no es un enlace: revisar sin sobrescribir.' >&2
    exit 1
fi
# Un solo registrador. Stop no sustituye a disable al preparar el proximo boot.
for unidad_dashcam in dashcam-captura.service dashcam-sync.service dashguard-captura.service dashguard-sync.timer dashguard-sync.service; do
    if systemctl --user cat "$unidad_dashcam" >/dev/null 2>&1; then
        systemctl --user stop "$unidad_dashcam"
    fi
done
for unidad_dashcam in dashguard-captura.service dashguard-sync.timer dashguard-sync.service; do
    if systemctl --user cat "$unidad_dashcam" >/dev/null 2>&1; then
        systemctl --user disable "$unidad_dashcam"
    fi
done
respaldo_dashcam="$raiz_dashcam/respaldos/unidades-$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$raiz_dashcam/respaldos" "$HOME/.config/systemd/user"
mkdir "$respaldo_dashcam"
if test -L "$raiz_dashcam/app"; then readlink "$raiz_dashcam/app" > "$respaldo_dashcam/release-anterior.txt"; fi
for unidad_dashcam in dashcam-captura.service dashcam-sync.service; do
    if test -f "$HOME/.config/systemd/user/$unidad_dashcam"; then
        cp -p "$HOME/.config/systemd/user/$unidad_dashcam" "$respaldo_dashcam/"
    fi
    install -m 600 "$codigo_dashcam/$unidad_dashcam" "$HOME/.config/systemd/user/"
done
if test "$(readlink -f "$raiz_dashcam/app" 2>/dev/null || true)" != "$codigo_dashcam"; then
    ln -s "$codigo_dashcam" "$raiz_dashcam/app-nuevo-$$"
    mv -Tf "$raiz_dashcam/app-nuevo-$$" "$raiz_dashcam/app"
fi
chmod 600 "$raiz_dashcam/config/dashcam.json"
systemctl --user daemon-reload
systemd-analyze --user verify "$HOME/.config/systemd/user/dashcam-captura.service" "$HOME/.config/systemd/user/dashcam-sync.service"
systemctl --user enable dashcam-captura.service dashcam-sync.service
systemctl --user start dashcam-sync.service
echo 'Instalado. Captura habilitada para el proximo arranque; sincronizador activo. No se borraron datos.'
