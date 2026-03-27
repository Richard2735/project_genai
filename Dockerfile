# ============================================================
# Dockerfile — Agente IA Backend (FastAPI + LangChain)
# ============================================================
#
# ¿Qué es un Dockerfile?
# Es una "receta" que le dice a Docker cómo construir una imagen.
# Una imagen es como una foto de un sistema operativo con tu app ya
# instalada. Esa imagen se sube a Artifact Registry y Cloud Run la
# ejecuta como un contenedor (instancia viva de la imagen).
#
# Flujo:
#   Dockerfile → (docker build) → Imagen → (docker push) → Registry → Cloud Run
#
# ============================================================

# ------------------------------------------------------------
# PASO 1: Elegir la imagen base
# ------------------------------------------------------------
# python:3.12-slim es una versión ligera de Debian con Python 3.12.
# "slim" = sin compiladores ni herramientas de desarrollo (~150MB vs ~900MB).
# Ideal para producción: menos peso = arranque más rápido en Cloud Run.
FROM python:3.12-slim

# ------------------------------------------------------------
# PASO 2: Variables de entorno para Python en Docker
# ------------------------------------------------------------
# PYTHONDONTWRITEBYTECODE=1 → No crear archivos .pyc (innecesarios en Docker)
# PYTHONUNBUFFERED=1 → Los logs aparecen en tiempo real (sin buffering)
# Esto es importante porque Cloud Run lee los logs directamente de stdout.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ------------------------------------------------------------
# PASO 3: Definir el directorio de trabajo
# ------------------------------------------------------------
# Todos los comandos que siguen se ejecutan desde /app dentro del contenedor.
# Es como hacer "cd /app" — si no existe, Docker lo crea.
WORKDIR /app

# ------------------------------------------------------------
# PASO 4: Instalar dependencias del sistema
# ------------------------------------------------------------
# Algunas librerías Python (como faiss-cpu) necesitan compiladores de C.
# apt-get instala estas dependencias del sistema operativo.
# El "rm -rf /var/lib/apt/lists/*" limpia la caché para reducir tamaño.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    swig \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# PASO 5: Copiar e instalar dependencias Python
# ------------------------------------------------------------
# Truco de optimización: copiamos SOLO requirements.txt primero.
# ¿Por qué? Docker cachea cada "capa" (cada instrucción).
# Si tu código cambia pero requirements.txt no, Docker reutiliza
# la capa de pip install (que tarda ~2 min) sin reinstalar todo.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------
# PASO 6: Copiar el código de la aplicación
# ------------------------------------------------------------
# Copiamos todo el proyecto al contenedor.
# El .dockerignore excluye archivos innecesarios (venv, .env, etc.)
COPY . .

# ------------------------------------------------------------
# PASO 7: Exponer el puerto
# ------------------------------------------------------------
# EXPOSE es documentación — le dice a otros desarrolladores (y a Cloud Run)
# que la app escucha en el puerto 8080.
# Cloud Run SIEMPRE usa el puerto 8080 por defecto.
EXPOSE 8080

# ------------------------------------------------------------
# PASO 8: Comando de arranque
# ------------------------------------------------------------
# CMD es lo que se ejecuta cuando el contenedor arranca.
# uvicorn api:app → arranca FastAPI desde api.py
# --host 0.0.0.0 → acepta conexiones de cualquier IP (necesario en Docker)
# --port 8080 → Cloud Run espera puerto 8080
# --workers 1 → un solo proceso (Cloud Run escala creando más contenedores)
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
