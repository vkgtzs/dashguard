-- Ejecutar despues de 001, antes de usar el backend nuevo.
-- Conserva la asignacion automatica para el firmware ESP32 sin muestra_id.
BEGIN;
CREATE OR REPLACE FUNCTION public.dashguard_asociar_recorrido()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'public'
AS $function$
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.device_id, 0));
    IF NEW.muestra_id IS NULL THEN
        SELECT id INTO NEW.recorrido_id
        FROM public.recorridos
        WHERE device_id = NEW.device_id AND estado = 'activo';
    ELSIF NEW.recorrido_id IS NOT NULL THEN
        -- Un UUID de muestra no implica que ya exista gestion offline de recorridos.
        -- Si se envia un recorrido, debe existir, pertenecer al equipo y cubrir la captura.
        PERFORM 1 FROM public.recorridos
        WHERE id = NEW.recorrido_id
          AND device_id = NEW.device_id
          AND NEW.fecha_hora >= inicio_fecha
          AND (final_fecha IS NULL OR NEW.fecha_hora <= final_fecha);
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Recorrido incompatible con dispositivo o fecha de captura'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    -- Muestras con UUID y recorrido null permanecen sin recorrido.
    RETURN NEW;
END;
$function$;
COMMIT;
