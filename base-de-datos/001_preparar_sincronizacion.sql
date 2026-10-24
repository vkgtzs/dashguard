-- Ejecutar en Supabase SQL Editor. No elimina registros ni modifica el trigger.
BEGIN;

ALTER TABLE public.mediciones
    ADD COLUMN muestra_id uuid,
    ADD COLUMN ax_ms2 double precision,
    ADD COLUMN ay_ms2 double precision,
    ADD COLUMN az_ms2 double precision,
    ADD COLUMN gx_grados_s double precision,
    ADD COLUMN gy_grados_s double precision,
    ADD COLUMN gz_grados_s double precision,
    ADD COLUMN velocidad_kmh double precision;

-- NULL permite conservar los envios antiguos del ESP32 sin UUID.
ALTER TABLE public.mediciones
    ADD CONSTRAINT mediciones_dispositivo_muestra_unique
        UNIQUE (device_id, muestra_id),
    ADD CONSTRAINT mediciones_velocidad_no_negativa
        CHECK (velocidad_kmh IS NULL OR velocidad_kmh >= 0);

-- Quitar textos de relleno; conservar las restricciones NOT NULL existentes.
ALTER TABLE public.mediciones
    ALTER COLUMN device_id DROP DEFAULT,
    ALTER COLUMN variable DROP DEFAULT,
    ALTER COLUMN unidad DROP DEFAULT,
    ALTER COLUMN source DROP DEFAULT;

COMMIT;
