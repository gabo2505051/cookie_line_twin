# **Cookie Production Line Digital Twin — Real-Time OEE Monitor**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python) ![MQTT](https://img.shields.io/badge/MQTT-HiveMQ%20Cloud-6200ea?logo=mqtt) ![Node-RED](https://img.shields.io/badge/Node--RED-3.x-red?logo=node-red) ![Status](https://img.shields.io/badge/Status-Active-brightgreen)

> 🌐 **Language / Idioma:** You are reading the English version. | [Leer en Español → READMEES.md](READMEES.md)

---

Python simulator that replicates the behavior of a 5-machine production line in sequence, publishing process data via **MQTT over TLS to HiveMQ Cloud**. Enables real-time monitoring of line efficiency (OEE), fault detection per equipment, and visualization of production, waste, and oven temperature from a **Node-RED** dashboard.

---

## 🎯 Problem it Solves

In industrial environments, validating an IIoT monitoring system requires having physical equipment running. This digital twin eliminates that dependency:

- **Simulates realistic behavior** of 5 chained machines (Mixer → Sheeter → Cutter → Oven → Packager) with states `running`, `fault`, `startup`, and `stopped`
- **Generates stochastic faults** per machine with alarm codes (`FLT-M2-004`), variable duration, and degraded startup period after a fault
- **Models micro-stoppages** (2–10 sec) that impact OEE as performance losses, not availability losses
- **Calculates real-time OEE** (Availability × Performance × Quality) with automatic reset every 8-hour shift
- **Publishes everything via MQTT/TLS** to the cloud, ready to connect to any dashboard or SCADA system

---

## 🚀 Simulator Features

- **Fault cascade**: if the Cutter (M3) fails, downstream machines (Oven + Packager) stop automatically — just like a real line
- **Machine-specific speed ranges**: each machine varies within its own limits (e.g., Cutter 65–100%) with *random walk* and *mean-reversion*
- **Realistic oven temperature**: slow drift with *mean-reversion* to setpoint (185°C), gradual cooling during fault and progressive warm-up on startup
- **Sporadic quality events**: waste spikes (×6 for 1–2 min) that generate visible trends in the production chart
- **Dynamic scrap rate**: rejection rate varies per cycle, multiplied during post-fault startup and at low speeds
- **8-hour shift**: automatic reset of all counters without interrupting MQTT publishing

---

## 🛠️ Technology Stack

| Tool | Function |
|---|---|
| **Python 3.10+** | Digital twin engine |
| **paho-mqtt 2.x** | MQTT client with native TLS support |
| **HiveMQ Cloud** | Cloud MQTT broker (free tier, TLS/8883) |
| **Node-RED** | MQTT subscription, processing, and dashboard |
| **node-red-dashboard** | Real-time gauges, charts, and text |

---

## 📁 Project Structure

```
cookie-line-twin/
├── twin.py              # Main loop: tick → cascade → OEE → MQTT publish
├── machines.py          # Machine model: states, faults, micro-stops, temperature
├── oee.py               # ShiftOEE: Availability × Performance × Quality + shift reset
├── config.py            # All configurable parameters (broker, rates, ranges)
├── requirements.txt     # paho-mqtt>=2.0.0
├── nodered/
│   └── flows.json       # Node-RED flow ready to import (HiveMQ broker pre-configured)
└── README.md
```

---

## ⚙️ Installation & Usage

**Install dependencies:**
```powershell
pip install -r requirements.txt
```

**Run the twin:**
```powershell
python twin.py
```

**Expected console output:**
```
10:20:23  INFO  ▶  Digital twin started. Publishing every 2.0s on 'factory/cookie-line/#'
10:20:23  INFO  Connected to MQTT broker at xxxx.hivemq.cloud:8883
10:20:25  INFO  OEE= 87.3%  Active=5/5  Shift=0.1min
10:20:41  INFO  OEE= 74.1%  Active=4/5  Shift=0.3min  ⚠FAULT:M2(FLT-M2-004)
10:21:26  INFO  OEE= 71.8%  Active=4/5  Shift=1.1min  🔄STARTUP:M2
```

**Import flow into Node-RED:**
1. Open `http://localhost:1880`
2. ☰ → **Import** → paste content of `nodered/flows.json`
3. **Deploy**
4. Dashboard at `http://localhost:1880/ui`

> **Requirement:** `node-red-dashboard` installed (`☰ → Manage palette → node-red-dashboard`)

---

## 📡 Published MQTT Topics

| Topic | Content |
|---|---|
| `factory/cookie-line/M1..M5/status` | State, speed %, counter, rejects, alarm |
| `factory/cookie-line/M4/status` | Adds `temperature_c`, `temp_setpoint`, `temp_deviation` |
| `factory/cookie-line/oee` | Availability, Performance, Quality, OEE %, shift |
| `factory/cookie-line/line/summary` | Global state, production, scrap %, `fault_details` |

**Example OEE payload:**
```json
{
  "shift_number": 1,
  "shift_elapsed_min": 47.3,
  "availability": 88.4,
  "performance": 91.2,
  "quality": 95.1,
  "oee": 76.7,
  "timestamp": "2026-06-18T10:47:18"
}
```

**Example fault payload in `line/summary`:**
```json
{
  "line_state": "fault",
  "fault_details": [
    { "machine": "M2", "name": "Sheeter", "alarm": "FLT-M2-004" }
  ]
}
```

---

## 📊 Node-RED Dashboard

| Widget | Description |
|---|---|
| **Global OEE** (gauge) | Real-time OEE %, red/yellow/green traffic light |
| **OEE Over Time** (chart) | Historical trend for the current shift |
| **Line Status** (text) | `▶ RUNNING` / `⚠ FAULT` / `🔄 STARTUP` / `⏹ STOPPED` |
| **Active Alert** (text) | `⚠ Sheeter (M2) → FLT-M2-004` |
| **Shift Scrap** (gauge) | Rejection rate %, alert above 3% |
| **Production vs Rejects** (chart) | Shift cumulative with quality event spikes |
| **M1–M5 Speed** (gauges) | Speed % per machine |
| **Oven Temperature** (gauge) | Current °C with range 150–220°C |
| **Temperature Deviation** (chart) | Drift from setpoint 185°C — realistic oscillation visible |

---

## ⚙️ Configurable Parameters (`config.py`)

| Parameter | Default | Description |
|---|---|---|
| `BROKER_HOST` | `xxxx.hivemq.cloud` | MQTT broker host |
| `BROKER_PORT` | `8883` | TLS port |
| `PUBLISH_INTERVAL` | `2.0` | Seconds between publications |
| `SHIFT_DURATION_MIN` | `480` | Shift duration (minutes) |
| `FAULT_PROB_PER_CYCLE` | `0.015` | Fault probability per cycle (1.5%) |
| `MICRO_STOP_PROB` | `0.04` | Micro-stoppage probability (4%) |
| `QTY_REJECT_RATE_BASE` | `0.05` | Base scrap rate (5%) |
| `CASCADE_TRIGGER_IDS` | `{"M3"}` | Machines whose fault blocks downstream |
| `OVEN_TEMP_SETPOINT` | `185.0` | Oven target temperature (°C) |

---

## 🔍 Verification Without Node-RED

Subscribe directly with `mosquitto_sub`:
```powershell
mosquitto_sub -h xxxx.hivemq.cloud -p 8883 --cafile "" -u Admin -P your_password -t "factory/cookie-line/#" -v
```

Or from the HiveMQ Cloud web console → **Web Client** → subscribe to `factory/cookie-line/#`.

---

**Author:** Gabriel Castro — Automation & IIoT Specialist
