-- Recorridos validos (viaje real) y no validos (dispositivo movido sin viajar)
-- Correr una vez en el SQL Editor de Supabase, ANTES de actualizar el backend y la Raspberry
BEGIN;
ALTER TABLE public.sesiones ADD COLUMN IF NOT EXISTS valido boolean;
-- Recorridos anteriores: sin datos de tiempo en marcha, se califican solo por distancia
UPDATE public.sesiones SET valido = coalesce(distancia_m, 0) >= 300
    WHERE fin IS NOT NULL AND valido IS NULL;
COMMIT;
