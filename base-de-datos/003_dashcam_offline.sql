-- Adicion aislada. No altera mediciones, recorridos ni funciones anteriores.
BEGIN;
CREATE TABLE IF NOT EXISTS public.dashcam_registros (
 id uuid PRIMARY KEY,
 device_id text NOT NULL,
 recorrido_id uuid NOT NULL,
 tipo text NOT NULL CHECK (tipo IN ('inicio','fin','muestra','video')),
 contenido jsonb NOT NULL,
 contenido_sha256 text NOT NULL CHECK (contenido_sha256 ~ '^[a-f0-9]{64}$'),
 recibido_en timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dashcam_por_recorrido ON public.dashcam_registros(device_id,recorrido_id,tipo);
ALTER TABLE public.dashcam_registros ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.dashcam_registros FROM anon,authenticated;
GRANT ALL ON public.dashcam_registros TO service_role;
INSERT INTO storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
VALUES ('dashguard-videos','dashguard-videos',false,8388608,ARRAY['video/mp4'])
ON CONFLICT(id) DO NOTHING;
-- No se crean politicas publicas. Solo backend con service_role.
COMMIT;
