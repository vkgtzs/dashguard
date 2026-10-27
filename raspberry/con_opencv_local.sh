#!/bin/sh
# Solo afecta al proceso hijo; no instala paquetes ni modifica el Python global.
set -eu
raiz="${DASHGUARD_OPENCV_ROOT:-$HOME/dashguard/ensayos-rostros/opencv-local}"
test -d "$raiz/usr/lib/python3/dist-packages"
export PYTHONPATH="$raiz/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$raiz/usr/lib/arm-linux-gnueabihf:$raiz/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec /usr/bin/python3 "$@"
