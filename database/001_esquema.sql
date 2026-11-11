-- DashGuard: esquema inicial. Ejecutar una vez en el editor SQL de Supabase.
-- RLS activado y sin politicas: solo el backend (service_role) accede.

BEGIN;

CREATE TABLE public.dispositivos (
    id text PRIMARY KEY CHECK (id ~ '^[a-z0-9-]{1,80}$'),
    supervisor_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    nombre text NOT NULL,
    token_sha256 text NOT NULL UNIQUE CHECK (token_sha256 ~ '^[a-f0-9]{64}$'),
    limite_velocidad_kmh integer NOT NULL DEFAULT 80
        CHECK (limite_velocidad_kmh BETWEEN 10 AND 200),
    visto_en timestamptz,
    creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.conductores (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    supervisor_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    nombre text NOT NULL CHECK (length(trim(nombre)) BETWEEN 1 AND 80),
    activo boolean NOT NULL DEFAULT true,
    rostro_registrado boolean NOT NULL DEFAULT false,
    creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.sesiones (
    id uuid PRIMARY KEY,
    dispositivo_id text NOT NULL REFERENCES public.dispositivos(id) ON DELETE CASCADE,
    inicio timestamptz NOT NULL,
    fin timestamptz,
    verificacion text CHECK (verificacion IN ('autorizado', 'no_reconocido', 'no_concluyente')),
    conductor_id uuid REFERENCES public.conductores(id) ON DELETE SET NULL,
    distancia_m double precision CHECK (distancia_m IS NULL OR distancia_m >= 0),
    recibido_en timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, dispositivo_id)
);
CREATE INDEX sesiones_por_dispositivo ON public.sesiones (dispositivo_id, inicio DESC);

CREATE TABLE public.puntos (
    id uuid PRIMARY KEY,
    sesion_id uuid NOT NULL,
    dispositivo_id text NOT NULL,
    fecha timestamptz NOT NULL,
    latitud double precision NOT NULL CHECK (latitud BETWEEN -90 AND 90),
    longitud double precision NOT NULL CHECK (longitud BETWEEN -180 AND 180),
    velocidad_kmh double precision CHECK (velocidad_kmh IS NULL OR velocidad_kmh >= 0),
    satelites integer,
    hdop double precision,
    FOREIGN KEY (sesion_id, dispositivo_id)
        REFERENCES public.sesiones (id, dispositivo_id) ON DELETE CASCADE
);
CREATE INDEX puntos_por_sesion ON public.puntos (sesion_id, fecha);

CREATE TABLE public.comandos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dispositivo_id text NOT NULL REFERENCES public.dispositivos(id) ON DELETE CASCADE,
    tipo text NOT NULL CHECK (tipo IN ('foto', 'video')),
    estado text NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'completado', 'fallido', 'expirado')),
    error text,
    solicitado_por uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX comandos_pendientes ON public.comandos (dispositivo_id, creado_en)
    WHERE estado = 'pendiente';

CREATE TABLE public.alertas (
    id uuid PRIMARY KEY,
    dispositivo_id text NOT NULL REFERENCES public.dispositivos(id) ON DELETE CASCADE,
    sesion_id uuid,
    tipo text NOT NULL CHECK (tipo IN ('conductor_no_reconocido', 'exceso_velocidad')),
    fecha timestamptz NOT NULL,
    latitud double precision CHECK (latitud BETWEEN -90 AND 90),
    longitud double precision CHECK (longitud BETWEEN -180 AND 180),
    detalle jsonb NOT NULL DEFAULT '{}',
    leida boolean NOT NULL DEFAULT false,
    recibido_en timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (sesion_id, dispositivo_id)
        REFERENCES public.sesiones (id, dispositivo_id) ON DELETE CASCADE
);
CREATE INDEX alertas_por_dispositivo ON public.alertas (dispositivo_id, fecha DESC);

CREATE TABLE public.evidencias (
    id uuid PRIMARY KEY,
    dispositivo_id text NOT NULL REFERENCES public.dispositivos(id) ON DELETE CASCADE,
    sesion_id uuid,
    comando_id uuid REFERENCES public.comandos(id) ON DELETE SET NULL,
    tipo text NOT NULL CHECK (tipo IN ('foto', 'video')),
    ruta text NOT NULL,
    sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    bytes integer NOT NULL CHECK (bytes > 0),
    fecha timestamptz NOT NULL,
    latitud double precision CHECK (latitud BETWEEN -90 AND 90),
    longitud double precision CHECK (longitud BETWEEN -180 AND 180),
    recibido_en timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (sesion_id, dispositivo_id)
        REFERENCES public.sesiones (id, dispositivo_id) ON DELETE CASCADE
);
CREATE INDEX evidencias_por_dispositivo ON public.evidencias (dispositivo_id, fecha DESC);

DO $$
DECLARE tabla text;
BEGIN
    FOREACH tabla IN ARRAY ARRAY['dispositivos', 'conductores', 'sesiones', 'puntos',
                                 'comandos', 'alertas', 'evidencias'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tabla);
        EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated', tabla);
        EXECUTE format('GRANT ALL ON public.%I TO service_role', tabla);
    END LOOP;
END $$;

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('dashguard-evidencias', 'dashguard-evidencias', false, 10485760,
        ARRAY['image/jpeg', 'video/mp4'])
ON CONFLICT (id) DO NOTHING;

COMMIT;
