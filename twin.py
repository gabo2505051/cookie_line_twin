# twin.py — Loop principal del gemelo digital
# Publica el estado de la línea de galletas vía MQTT cada PUBLISH_INTERVAL segundos.
#
# Uso:
#   python twin.py
#
# Requisitos:
#   pip install paho-mqtt

import json
import logging
import signal
import ssl
import sys
import time
from datetime import datetime

import paho.mqtt.client as mqtt

import config
from machines import Machine, STATE_FAULT, STATE_STARTUP, STATE_STOPPED, build_machines
from oee import ShiftOEE

# ─── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("twin")

# ─── SEÑAL DE SALIDA LIMPIA ────────────────────────────────────────────────────
_running = True

def _handle_sigint(sig, frame):
    global _running
    log.info("Interrupción recibida. Cerrando gemelo digital...")
    _running = False

signal.signal(signal.SIGINT, _handle_sigint)


# ─── CALLBACKS MQTT (paho-mqtt v2 — firma con 5 argumentos) ───────────────────
def on_connect(client, userdata, connect_flags, reason_code, properties):
    if reason_code.is_failure:
        log.error(f"Error de conexión MQTT — {reason_code}")
    else:
        log.info(f"Conectado al broker MQTT en {config.BROKER_HOST}:{config.BROKER_PORT}")

def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    if reason_code != 0:
        log.warning(f"Desconexión inesperada del broker (rc={reason_code}). Reintentando...")


# ─── PUBLICACIÓN ───────────────────────────────────────────────────────────────
def publish(client: mqtt.Client, topic: str, payload: dict):
    payload["timestamp"] = datetime.now().isoformat(timespec="seconds")
    msg = json.dumps(payload, ensure_ascii=False)
    result = client.publish(topic, msg, qos=1, retain=False)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        log.warning(f"Fallo al publicar en {topic}: rc={result.rc}")


# ─── LÓGICA DE CASCADA ─────────────────────────────────────────────────────────
def apply_cascade(machines: list[Machine]):
    """
    Si una máquina de CASCADE_TRIGGER_IDS entra en fault,
    todas las máquinas aguas abajo pasan a stopped.
    El arranque (startup) NO bloquea la cascada — la línea puede continuar.
    """
    ids = [m.machine_id for m in machines]
    blocked = False

    for machine in machines:
        if machine.machine_id in config.CASCADE_TRIGGER_IDS and machine.state == STATE_FAULT:
            blocked = True
            trigger_idx = ids.index(machine.machine_id)
            for downstream in machines[trigger_idx + 1:]:
                downstream.force_stopped(True)
            break

    if not blocked:
        for machine in machines:
            if machine._forced_stopped:
                machine.force_stopped(False)


# ─── RESUMEN DE LÍNEA ──────────────────────────────────────────────────────────
def build_line_summary(machines: list[Machine]) -> dict:
    # Usamos M3 (Cortadora) como referencia de producción principal
    m3 = next((m for m in machines if m.machine_id == "M3"), None)
    total_produced = m3.counter if m3 else 0
    total_rejected = m3.rejects if m3 else 0

    faulted  = [m.machine_id for m in machines if m.state == STATE_FAULT]
    starting = [m.machine_id for m in machines if m.state == STATE_STARTUP]
    stopped  = [m.machine_id for m in machines if m.state == STATE_STOPPED]

    # Detalle de la falla activa (máquina + código de alarma)
    fault_details = [
        {"machine": m.machine_id, "name": m.name, "alarm": m.alarm}
        for m in machines if m.state == STATE_FAULT
    ]

    # Throughput: promedio de máquinas activas (running + startup)
    active = [m for m in machines if m.state in ("running", "startup")]
    throughput_pct = round(
        sum(m.speed_pct for m in active) / len(machines) * 100, 1
    ) if active else 0.0

    line_state = "running"
    if faulted:
        line_state = "fault"
    elif starting:
        line_state = "startup"
    elif len(stopped) == len(machines):
        line_state = "stopped"

    return {
        "line_state":      line_state,
        "total_produced":  total_produced,
        "total_rejected":  total_rejected,
        "reject_rate_pct": round(total_rejected / total_produced * 100, 2)
                           if total_produced > 0 else 0.0,
        "throughput_pct":  throughput_pct,
        "machines_faulted":  faulted,
        "machines_starting": starting,
        "machines_stopped":  stopped,
        "fault_details":     fault_details,
    }


# ─── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    # Inicializar máquinas y OEE
    machines = build_machines()
    shift_oee = ShiftOEE()

    # Configurar cliente MQTT
    client = mqtt.Client(
        client_id="cookie-line-twin",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    # ── NUEVO: TLS + autenticación ──────────────────────────────────
    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)  # TLS nativo
    client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)

    try:
        client.connect(config.BROKER_HOST, config.BROKER_PORT, config.MQTT_KEEPALIVE)
    except Exception as e:
        log.error(f"No se pudo conectar al broker: {e}")
        sys.exit(1)

    client.loop_start()
    log.info("▶  Gemelo digital iniciado. Publicando cada "
             f"{config.PUBLISH_INTERVAL}s en '{config.BASE_TOPIC}/#'")
    log.info(f"   Turno: {config.SHIFT_DURATION_MIN} min | "
             f"Broker: {config.BROKER_HOST}:{config.BROKER_PORT}")
    log.info("   Ctrl+C para detener.")

    dt = config.PUBLISH_INTERVAL  # delta tiempo entre ticks

    while _running:
        loop_start = time.time()

        # 1. Avanzar simulación de cada máquina
        for machine in machines:
            machine.tick(dt)

        # 2. Aplicar lógica de cascada
        apply_cascade(machines)

        # 3. Actualizar OEE / detectar reset de turno
        shift_reset = shift_oee.update(machines)
        if shift_reset:
            log.info(f"🔄  Turno {shift_oee.shift_number - 1} completado. "
                     f"Iniciando turno {shift_oee.shift_number}.")

        # 4. Publicar estado de cada máquina
        for machine in machines:
            topic = f"{config.BASE_TOPIC}/{machine.machine_id}/status"
            publish(client, topic, machine.to_payload())

        # 5. Publicar OEE
        publish(client, f"{config.BASE_TOPIC}/oee", shift_oee.to_payload())

        # 6. Publicar resumen de línea
        summary = build_line_summary(machines)
        publish(client, f"{config.BASE_TOPIC}/line/summary", summary)

        # 7. Log compacto en consola
        oee_val = shift_oee.oee * 100
        active_count = sum(1 for m in machines if m.state in ("running", "startup"))
        fault_names  = [f"{m.machine_id}({m.alarm})" for m in machines if m.state == STATE_FAULT]
        start_names  = [m.machine_id for m in machines if m.state == STATE_STARTUP]
        status_str   = ""
        if fault_names:  status_str += f" ⚠FALLA:{','.join(fault_names)}"
        if start_names:  status_str += f" 🔄ARRANQUE:{','.join(start_names)}"
        log.info(
            f"OEE={oee_val:5.1f}%  "
            f"Activas={active_count}/{len(machines)}  "
            f"Turno={shift_oee.shift_elapsed_min}min"
            f"{status_str}"
        )

        # 8. Esperar hasta el próximo ciclo
        elapsed = time.time() - loop_start
        sleep_time = max(0.0, dt - elapsed)
        time.sleep(sleep_time)

    # Cierre limpio
    client.loop_stop()
    client.disconnect()
    log.info("Gemelo digital detenido correctamente.")


if __name__ == "__main__":
    main()
