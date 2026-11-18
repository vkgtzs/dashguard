-- Rostros guardados en el backend, comando de registro de rostro e indice para la ubicacion actual
BEGIN;

ALTER TABLE public.conductores
    ADD COLUMN IF NOT EXISTS descriptores jsonb,
    ADD COLUMN IF NOT EXISTS rostro_actualizado timestamptz;
UPDATE public.conductores SET rostro_registrado = false WHERE descriptores IS NULL;

ALTER TABLE public.comandos
    ADD COLUMN IF NOT EXISTS conductor_id uuid REFERENCES public.conductores(id) ON DELETE CASCADE;
ALTER TABLE public.comandos DROP CONSTRAINT IF EXISTS comandos_tipo_check;
ALTER TABLE public.comandos ADD CONSTRAINT comandos_tipo_check
    CHECK (tipo IN ('foto', 'video', 'registro_rostro'));
ALTER TABLE public.comandos DROP CONSTRAINT IF EXISTS comandos_conductor_check;
ALTER TABLE public.comandos ADD CONSTRAINT comandos_conductor_check
    CHECK ((tipo = 'registro_rostro') = (conductor_id IS NOT NULL));

CREATE INDEX IF NOT EXISTS puntos_por_dispositivo ON public.puntos (dispositivo_id, fecha DESC);
CREATE INDEX IF NOT EXISTS alertas_pendientes ON public.alertas (dispositivo_id) WHERE NOT leida;

COMMIT;
