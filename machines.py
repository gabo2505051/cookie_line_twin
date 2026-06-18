# machines.py — Modelo de máquina para el gemelo digital
# Encapsula el estado, contadores y lógica de transición de cada máquina.

import random
import time
from dataclasses import dataclass, field
from typing import Optional

import config

# ─── ESTADOS ───────────────────────────────────────────────────────────────────
STATE_RUNNING = "running"
STATE_STARTUP = "startup"   # arranque post-falla: velocidad y calidad degradadas
STATE_STOPPED = "stopped"
STATE_FAULT   = "fault"


@dataclass
class Machine:
    """Representa una máquina de la línea productiva."""

    machine_id: str
    name: str
    nominal_rate: float
    unit: str
    has_temperature: bool = False
    speed_min_pct: float = 0.70    # velocidad mínima normalizada (0-1)
    speed_max_pct: float = 1.00    # velocidad máxima normalizada (0-1)

    # Estado público
    state: str = STATE_RUNNING
    speed_pct: float = 1.0          # fracción de velocidad actual vs nominal
    counter: int = 0
    rejects: int = 0
    alarm: Optional[str] = None
    is_startup: bool = False        # True durante el arranque post-falla

    # Control interno de fallas y arranque
    _fault_end_time: float    = field(default=0.0,   repr=False)
    _startup_end_time: float  = field(default=0.0,   repr=False)
    _forced_stopped: bool     = field(default=False,  repr=False)
    _micro_stop_end: float    = field(default=0.0,   repr=False)  # fin de micro-detención
    _quality_event_end: float = field(default=0.0,   repr=False)  # fin de evento de calidad

    # Temperatura (solo Horno M4)
    temperature_c: Optional[float] = field(default=None, repr=False)
    _oven_drift: float             = field(default=0.0,   repr=False)  # deriva acumulada

    def __post_init__(self):
        # Inicializar velocidad en el centro del rango
        self.speed_pct = (self.speed_min_pct + self.speed_max_pct) / 2
        if self.has_temperature:
            self.temperature_c = config.OVEN_TEMP_SETPOINT

    # ── API pública ────────────────────────────────────────────────────────────

    def force_stopped(self, active: bool):
        """Fuerza parada por cascada aguas abajo."""
        self._forced_stopped = active
        if active:
            self.state = STATE_STOPPED
            self.speed_pct = 0.0

    def tick(self, dt: float):
        """Avanza la simulación dt segundos."""
        now = time.time()

        # ── Máquina detenida por cascada ──────────────────────────────────────
        if self._forced_stopped:
            self.state = STATE_STOPPED
            self.speed_pct = 0.0
            self.alarm = None
            self.is_startup = False
            self._tick_oven_stopped()
            return

        # ── Recuperación de falla → arranque ──────────────────────────────────
        if self.state == STATE_FAULT:
            if now >= self._fault_end_time:
                # Pasa a modo arranque
                self.state = STATE_STARTUP
                self.is_startup = True
                self._startup_end_time = now + config.STARTUP_DURATION_S
                self.alarm = None
                self.speed_pct = self.speed_min_pct * 0.6  # arranca lento
            else:
                self.speed_pct = 0.0
                self._tick_oven_stopped()
                return

        # ── Fin de arranque → operación normal ────────────────────────────────
        if self.state == STATE_STARTUP and now >= self._startup_end_time:
            self.state = STATE_RUNNING
            self.is_startup = False

        # ── Micro-detención (velocidad=0, state sigue running) ─────────────────
        if now < self._micro_stop_end:
            self.speed_pct = 0.0   # paralizada brevemente, NO es fault
            return

        # ── Probabilidad de nueva falla (solo si está corriendo, no arrancando) ─
        if self.state == STATE_RUNNING:
            # Sorteo de micro-detención (tiene prioridad sobre falla completa)
            if random.random() < config.MICRO_STOP_PROB:
                self._micro_stop_end = now + random.uniform(
                    config.MICRO_STOP_MIN_S, config.MICRO_STOP_MAX_S
                )
                return

            if random.random() < config.FAULT_PROB_PER_CYCLE:
                duration = random.uniform(
                    config.FAULT_DURATION_MIN_S,
                    config.FAULT_DURATION_MAX_S,
                )
                self.state = STATE_FAULT
                self._fault_end_time = now + duration
                self.alarm = f"FLT-{self.machine_id}-{random.randint(1, 9):03d}"
                self.speed_pct = 0.0
                self.is_startup = False
                self._tick_oven_stopped()
                return

        # ── Operación: running o startup ──────────────────────────────────────
        self._tick_speed(dt)
        self._tick_production(dt)
        self._tick_oven_running()

    # ── Helpers privados ───────────────────────────────────────────────────────

    def _tick_speed(self, dt: float):
        """Random walk de velocidad dentro del rango de la máquina."""
        if self.state == STATE_STARTUP:
            # Arranque: sube gradualmente hasta el rango normal con cap
            target_max = min(config.STARTUP_SPEED_CAP, self.speed_max_pct)
            step = random.gauss(0.02, 0.01)  # sube positivamente en arranque
            self.speed_pct = max(
                self.speed_min_pct * 0.5,
                min(target_max, self.speed_pct + step),
            )
        else:
            # Normal: random walk con reversión al centro del rango
            center = (self.speed_min_pct + self.speed_max_pct) / 2
            reversion = 0.01 * (center - self.speed_pct)
            step = random.gauss(reversion, config.SPEED_NOISE_STD)
            self.speed_pct = max(
                self.speed_min_pct,
                min(self.speed_max_pct, self.speed_pct + step),
            )

    def _tick_production(self, dt: float):
        """Calcula producción y rechazos del ciclo actual."""
        produced = int(self.nominal_rate * self.speed_pct * (dt / 60.0))

        # Tasa base con variación aleatoria por ciclo
        lo, hi = config.REJECT_RATE_VARIATION
        reject_rate = config.QTY_REJECT_RATE_BASE * random.uniform(lo, hi)

        # Multiplicador por velocidad baja
        if self.speed_pct < 0.80:
            reject_rate *= config.LOW_SPEED_REJECT_MULT * (1.0 - self.speed_pct)

        # Multiplicador por arranque post-falla
        if self.state == STATE_STARTUP:
            reject_rate *= config.STARTUP_REJECT_MULT

        # Evento de calidad: spike periódico de rechazos
        now = time.time()
        if now < self._quality_event_end:
            reject_rate *= config.QUALITY_EVENT_MULT
        elif random.random() < config.QUALITY_EVENT_PROB:
            self._quality_event_end = now + random.uniform(
                config.QUALITY_EVENT_MIN_S, config.QUALITY_EVENT_MAX_S
            )

        rejects = int(produced * min(reject_rate, 0.80))  # cap: máx 80 % rechazo

        self.counter += produced
        self.rejects += rejects

    def _tick_oven_running(self):
        """Temperatura del horno: deriva lenta + ruido blanco + mean-reversion."""
        if not self.has_temperature:
            return

        # Deriva aleatoria (random walk)
        self._oven_drift += random.gauss(0, config.OVEN_TEMP_DRIFT_STD)
        # Limitar la deriva máxima
        self._oven_drift = max(-config.OVEN_TEMP_MAX_DRIFT,
                               min(config.OVEN_TEMP_MAX_DRIFT, self._oven_drift))
        # Mean-reversion: la deriva tiende a volver a cero lentamente
        self._oven_drift *= (1.0 - config.OVEN_TEMP_REVERSION)

        # Temperatura = setpoint + deriva + ruido ciclo a ciclo
        noise = random.gauss(0, config.OVEN_TEMP_NOISE_STD)
        raw = config.OVEN_TEMP_SETPOINT + self._oven_drift + noise

        # En modo arranque, temperatura sube desde un valor bajo
        if self.state == STATE_STARTUP:
            raw = min(raw, self.temperature_c + config.OVEN_TEMP_HEAT_RATE)

        self.temperature_c = round(raw, 1)

    def _tick_oven_stopped(self):
        """El horno se enfría cuando está detenido o en falla."""
        if not self.has_temperature:
            return
        self.temperature_c = round(
            max(20.0, self.temperature_c - config.OVEN_TEMP_COOL_RATE), 1
        )
        self._oven_drift *= 0.95  # la deriva también decae

    def reset_shift(self):
        """Reinicia contadores al comienzo de un nuevo turno."""
        self.counter = 0
        self.rejects = 0
        self.alarm = None
        self.state = STATE_RUNNING
        self.is_startup = False
        self.speed_pct = (self.speed_min_pct + self.speed_max_pct) / 2
        self._forced_stopped = False
        self._oven_drift = 0.0
        if self.has_temperature:
            self.temperature_c = config.OVEN_TEMP_SETPOINT

    def to_payload(self) -> dict:
        """Serializa el estado de la máquina como diccionario MQTT."""
        payload = {
            "machine_id":   self.machine_id,
            "name":         self.name,
            "state":        self.state,
            "is_startup":   self.is_startup,
            "speed_pct":    round(self.speed_pct * 100, 1),   # % vs nominal
            "speed_min":    round(self.speed_min_pct * 100, 0),
            "speed_max":    round(self.speed_max_pct * 100, 0),
            "nominal_rate": self.nominal_rate,
            "unit":         self.unit,
            "counter":      self.counter,
            "rejects":      self.rejects,
            "reject_rate":  round(self.rejects / self.counter * 100, 2)
                            if self.counter > 0 else 0.0,
            "alarm":        self.alarm,
        }
        if self.has_temperature:
            payload["temperature_c"]  = self.temperature_c
            payload["temp_setpoint"]  = config.OVEN_TEMP_SETPOINT
            payload["temp_deviation"] = round(
                self.temperature_c - config.OVEN_TEMP_SETPOINT, 1
            )
        return payload


def build_machines() -> list[Machine]:
    """Instancia las máquinas a partir de MACHINES_CONFIG."""
    return [
        Machine(
            machine_id=mid,
            name=name,
            nominal_rate=rate,
            unit=unit,
            has_temperature=has_temp,
            speed_min_pct=speed_min,
            speed_max_pct=speed_max,
        )
        for mid, name, rate, unit, has_temp, speed_min, speed_max in config.MACHINES_CONFIG
    ]
