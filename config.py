# config.py — Parámetros globales del gemelo digital
# Modificá estos valores para adaptar el simulador a tu entorno.

# ─── MQTT ──────────────────────────────────────────────────────────────────────
BROKER_HOST = "928f0d8b3400427183987b0d6b7938a8.s1.eu.hivemq.cloud"
BROKER_PORT = 8883
MQTT_KEEPALIVE = 60
MQTT_USERNAME= "Admin"
MQTT_PASSWORD= "Gabo.2505"
BASE_TOPIC = "factory/cookie-line"

# ─── LOOP DE PUBLICACIÓN ───────────────────────────────────────────────────────
PUBLISH_INTERVAL = 2.0   # segundos entre cada ciclo de publicación

# ─── TURNO ─────────────────────────────────────────────────────────────────────
SHIFT_DURATION_MIN = 480  # 8 horas en minutos (reset automático al cumplirse)

# ─── PARÁMETROS DE FALLA ───────────────────────────────────────────────────────
FAULT_PROB_PER_CYCLE = 0.015      # probabilidad de entrar en fault por ciclo (1.5 %)
FAULT_DURATION_MIN_S = 30         # duración mínima de una falla (segundos)
FAULT_DURATION_MAX_S = 120        # duración máxima de una falla (segundos)

# ─── ARRANQUE POST-FALLA ───────────────────────────────────────────────────────
STARTUP_DURATION_S    = 45        # segundos de arranque con parámetros degradados
STARTUP_REJECT_MULT   = 8.0       # multiplicador de rechazos durante arranque (8x)
STARTUP_SPEED_CAP     = 0.70      # velocidad máxima durante arranque (70 % nominal)

# ─── RECHAZOS ──────────────────────────────────────────────────────────
QTY_REJECT_RATE_BASE  = 0.05      # tasa base de rechazos en operación normal (5 %)
REJECT_RATE_VARIATION = (0.5, 2.0) # rango de variación aleatoria por ciclo
# A velocidades bajas la tasa de rechazo sube proporcionalmente
LOW_SPEED_REJECT_MULT = 3.0       # multiplicador extra cuando speed_pct < 0.80

# ─── MICRO-DETENCIONES ────────────────────────────────────────────────────
MICRO_STOP_PROB        = 0.04     # probabilidad de micro-detención por ciclo (4 %)
MICRO_STOP_MIN_S       = 2        # duración mínima (segundos)
MICRO_STOP_MAX_S       = 10       # duración máxima (segundos)

# ─── EVENTOS DE CALIDAD ───────────────────────────────────────────────────
QUALITY_EVENT_PROB     = 0.008    # probabilidad de disparar un spike de rechazo (0.8 %)
QUALITY_EVENT_MULT     = 6.0     # multiplicador de rechazos durante el evento
QUALITY_EVENT_MIN_S    = 60       # duración mínima del evento (segundos)
QUALITY_EVENT_MAX_S    = 120      # duración máxima del evento (segundos)

# ─── VELOCIDADES ───────────────────────────────────────────────────────────────
SPEED_NOISE_STD = 0.015           # paso de random walk por ciclo (más suave)
# Cada máquina define su propio rango en MACHINES_CONFIG

# ─── DEFINICIÓN DE MÁQUINAS ────────────────────────────────────────────────────
# Campos: (machine_id, name, nominal_rate, unit, has_temperature, speed_min_pct, speed_max_pct)
MACHINES_CONFIG = [
    ("M1", "Mezcladora",  500,  "kg/h",          False, 0.70, 1.00),
    ("M2", "Laminadora",  200,  "laminas/min",    False, 0.75, 1.00),
    ("M3", "Cortadora",  1200,  "galletas/min",   False, 0.65, 1.00),  # mayor variación
    ("M4", "Horno",       180,  "bandas/h",       True,  0.82, 1.00),  # más estable
    ("M5", "Empacadora",   60,  "paquetes/min",   False, 0.75, 1.00),
]

# ─── TEMPERATURA DEL HORNO ─────────────────────────────────────────────────────
OVEN_TEMP_SETPOINT   = 185.0   # temperatura objetivo (°C)
OVEN_TEMP_NOISE_STD  = 0.6     # ruido blanco ciclo a ciclo
OVEN_TEMP_DRIFT_STD  = 0.08    # paso de deriva aleatoria por ciclo
OVEN_TEMP_REVERSION  = 0.04    # fuerza de retorno al setpoint (mean-reversion)
OVEN_TEMP_MAX_DRIFT  = 8.0     # deriva máxima permitida desde el setpoint (°C)
OVEN_TEMP_COOL_RATE  = 1.2     # °C/ciclo de enfriamiento cuando está detenido
OVEN_TEMP_HEAT_RATE  = 0.8     # °C/ciclo de calentamiento durante arranque

# ─── CASCADA DE FALLAS ──────────────────────────────────────────────────────────
# Solo M3 (Cortadora) bloquea aguas abajo al fallar.
# M1 y M2 fallan de forma independiente sin bloquear la línea completa.
CASCADE_TRIGGER_IDS = {"M3"}
