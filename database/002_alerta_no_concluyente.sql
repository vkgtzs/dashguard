BEGIN;
ALTER TABLE public.alertas DROP CONSTRAINT IF EXISTS alertas_tipo_check;
ALTER TABLE public.alertas ADD CONSTRAINT alertas_tipo_check
    CHECK (tipo IN ('conductor_no_reconocido', 'verificacion_no_concluyente', 'exceso_velocidad'));
COMMIT;
