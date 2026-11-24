-- Posicion del vehiculo estacionado (fuera de recorrido), nivel de bateria y alerta de bateria baja.
BEGIN;
ALTER TABLE public.dispositivos
    ADD COLUMN IF NOT EXISTS posicion_latitud double precision CHECK (posicion_latitud BETWEEN -90 AND 90),
    ADD COLUMN IF NOT EXISTS posicion_longitud double precision CHECK (posicion_longitud BETWEEN -180 AND 180),
    ADD COLUMN IF NOT EXISTS posicion_velocidad_kmh double precision,
    ADD COLUMN IF NOT EXISTS posicion_fecha timestamptz,
    ADD COLUMN IF NOT EXISTS bateria_porcentaje integer CHECK (bateria_porcentaje BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS bateria_cargando boolean,
    ADD COLUMN IF NOT EXISTS bateria_fecha timestamptz;

ALTER TABLE public.alertas DROP CONSTRAINT IF EXISTS alertas_tipo_check;
ALTER TABLE public.alertas ADD CONSTRAINT alertas_tipo_check
    CHECK (tipo IN ('conductor_no_reconocido', 'verificacion_no_concluyente', 'exceso_velocidad',
                    'bateria_baja'));
COMMIT;
