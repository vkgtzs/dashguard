#!/bin/sh
# Ejecutar como root SOLO con usuario listo para cambiar a powerbank.
# No toca redes guardadas, contrasenas ni conexiones del PC.
set -eu
raiz=/home/vkgtzs/dashguard/app
test -x /usr/bin/nmcli
test -f "$raiz/dashcam-wifi-reconectar.timer"
test ! -e /etc/systemd/system/dashcam-wifi-reconectar.timer
test ! -e /etc/systemd/system/dashcam-wifi-reconectar.service
install -m 644 "$raiz/dashcam-wifi-reconectar.timer" /etc/systemd/system/
install -m 644 "$raiz/dashcam-wifi-reconectar.service" /etc/systemd/system/
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/dashcam-wifi-reconectar.timer /etc/systemd/system/dashcam-wifi-reconectar.service
# Habilitar SIN arrancar: OnBootSec debe contar desde el proximo arranque.
systemctl enable dashcam-wifi-reconectar.timer
# Rescate en este arranque si el apagado falla. No persiste tras reiniciar.
systemd-run --unit=dashcam-wifi-rescate --on-active=120s /usr/bin/nmcli radio wifi on
# Desconectar y apagar desde systemd; la perdida SSH no cancela este trabajo.
systemd-run --unit=dashcam-apagar-offline --on-active=10s /bin/sh -c '/usr/bin/nmcli radio wifi off && /usr/bin/systemctl poweroff'
echo 'PREPARADO: apagado en 10 segundos; reconexion 33 minutos despues del siguiente arranque.'
