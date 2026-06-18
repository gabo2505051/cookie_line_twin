# oee.py — Cálculo de OEE y gestión del turno de 8 horas
#
# OEE = Disponibilidad × Rendimiento × Calidad
#
# Disponibilidad = tiempo_corriendo / tiempo_turno_total
# Rendimiento    = velocidad_real_promedio / velocidad_nominal  (proxy: avg speed_pct)
# Calidad        = (producidas - rechazadas) / producidas

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from machines import Machine


@dataclass
class ShiftOEE:
    """
    Gestiona un turno de duración fija y calcula OEE en tiempo real.
    Al expirar el turno, se reinicia automáticamente.
    """

    shift_duration_s: float = field(
        default_factory=lambda: config.SHIFT_DURATION_MIN * 60.0
    )

    # Acumuladores internos
    _shift_start: float = field(default_factory=time.time, repr=False)
    _running_ticks: int = field(default=0, repr=False)   # ciclos donde al menos 1 máq corre
    _total_ticks: int = field(default=0, repr=False)      # ciclos totales en el turno
    _speed_pct_sum: float = field(default=0.0, repr=False)  # suma de speed_pct medias

    # Último cálculo publicable
    availability: float = 0.0
    performance: float = 0.0
    quality: float = 0.0
    oee: float = 0.0
    shift_elapsed_min: float = 0.0
    shift_number: int = 1

    def update(self, machines: list["Machine"]) -> bool:
        """
        Actualiza acumuladores con el estado actual de las máquinas.
        Devuelve True si el turno acaba de reiniciarse en este ciclo.
        """
        now = time.time()
        elapsed = now - self._shift_start
        self.shift_elapsed_min = round(elapsed / 60.0, 1)

        # ── Detección de fin de turno ─────────────────────────────────────────
        shift_reset = False
        if elapsed >= self.shift_duration_s:
            self._reset_shift(machines)
            shift_reset = True
            elapsed = 0.0

        # ── Acumular ticks ────────────────────────────────────────────────────
        self._total_ticks += 1
        running_machines = [m for m in machines if m.state == "running"]
        if running_machines:
            self._running_ticks += 1

        # Velocidad media de la línea (sólo máquinas corriendo)
        avg_speed = (
            sum(m.speed_pct for m in running_machines) / len(running_machines)
            if running_machines else 0.0
        )
        self._speed_pct_sum += avg_speed

        # ── Calcular OEE ──────────────────────────────────────────────────────
        self.availability = (
            self._running_ticks / self._total_ticks
            if self._total_ticks else 0.0
        )
        self.performance = (
            self._speed_pct_sum / self._running_ticks
            if self._running_ticks else 0.0
        )

        # Calidad basada en la máquina contadora principal (M3 — Cortadora)
        counter_machine = next((m for m in machines if m.machine_id == "M3"), None)
        if counter_machine and counter_machine.counter > 0:
            self.quality = (
                (counter_machine.counter - counter_machine.rejects)
                / counter_machine.counter
            )
        else:
            self.quality = 1.0

        self.oee = self.availability * self.performance * self.quality

        return shift_reset

    def to_payload(self) -> dict:
        return {
            "shift_number": self.shift_number,
            "shift_elapsed_min": self.shift_elapsed_min,
            "shift_duration_min": config.SHIFT_DURATION_MIN,
            "availability": round(self.availability * 100, 2),
            "performance": round(self.performance * 100, 2),
            "quality": round(self.quality * 100, 2),
            "oee": round(self.oee * 100, 2),
        }

    def _reset_shift(self, machines: list["Machine"]):
        """Reinicia el turno: contadores internos y estado de máquinas."""
        self._shift_start = time.time()
        self._running_ticks = 0
        self._total_ticks = 0
        self._speed_pct_sum = 0.0
        self.shift_elapsed_min = 0.0
        self.shift_number += 1
        for m in machines:
            m.reset_shift()
