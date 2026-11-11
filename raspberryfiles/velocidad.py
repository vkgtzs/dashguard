"""Deteccion de exceso de velocidad."""


class DetectorExceso:

    def __init__(self, lecturas_necesarias=3):
        self.lecturas_necesarias = lecturas_necesarias
        self._seguidas = 0
        self._avisado = False
        self.maxima_kmh = None

    def actualizar(self, velocidad_kmh, limite_kmh):
        if velocidad_kmh is None:  # lectura sin velocidad: no cuenta ni reinicia
            return False
        if velocidad_kmh <= limite_kmh:
            self._seguidas = 0
            self._avisado = False
            self.maxima_kmh = None
            return False
        self._seguidas += 1
        self.maxima_kmh = max(velocidad_kmh, self.maxima_kmh or 0)
        if self._seguidas >= self.lecturas_necesarias and not self._avisado:
            self._avisado = True
            return True
        return False
