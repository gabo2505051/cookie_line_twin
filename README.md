# **Gemelo Digital de Línea de Producción de Galletas — Monitor OEE en Tiempo Real**

# ![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python) ![MQTT](https://img.shields.io/badge/MQTT-HiveMQ%20Cloud-6200ea?logo=mqtt) ![Node-RED](https://img.shields.io/badge/Node--RED-3.x-red?logo=node-red) ![Status](https://img.shields.io/badge/Estado-Activo-brightgreen)

---

## Proyecto 5 – Portafolio IIoT

Simulador Python que replica el comportamiento de una línea productiva de 5 máquinas en cadena, publicando datos de proceso vía **MQTT sobre TLS hacia HiveMQ Cloud**. Permite monitorear en tiempo real la eficiencia de la línea (OEE), detectar fallas por equipo y visualizar producción, merma y temperatura del horno desde un dashboard en **Node-RED**.

---

## 🎯 Problema que Resuelve

En entornos industriales, validar un sistema de monitoreo IIoT requiere tener equipos físicos funcionando. Este gemelo digital elimina esa dependencia:

- **Simula comportamiento realista** de 5 máquinas en cadena (Mezcladora → Laminadora → Cortadora → Horno → Empacadora) con estados `running`, `fault`, `startup` y `stopped`
- **Genera fallas estocásticas** por máquina con código de alarma (`FLT-M2-004`), duración variable y período de arranque degradado post-falla
- **Modela micro-detenciones** (2–10 seg) que impactan el OEE como pérdidas de rendimiento, no de disponibilidad
- **Calcula OEE en tiempo real** (Disponibilidad × Rendimiento × Calidad) con reset automático cada 8 horas de turno
- **Publica todo vía MQTT/TLS** hacia la nube, listo para conectar a cualquier dashboard o sistema SCADA

---

## 🚀 Características del Simulador

- **Cascada de fallas**: si la Cortadora (M3) falla, las máquinas aguas abajo (Horno + Empacadora) se detienen automáticamente — igual que en una línea real
- **Velocidades con rango propio**: cada máquina varía dentro de sus límites (ej: Cortadora 65–100%) con *random walk* y *mean-reversion*
- **Temperatura del horno realista**: deriva lenta con *mean-reversion* al setpoint (185°C), enfriamiento gradual en falla y calentamiento progresivo en arranque
- **Eventos de calidad esporádicos**: spikes de merma (×6 durante 1–2 min) que generan tendencias visibles en el gráfico de producción
- **Merma dinámica**: tasa de rechazo varía por ciclo, se multiplica en arranque post-falla y a velocidades bajas
- **Turno de 8 horas**: reset automático de todos los contadores sin interrumpir la publicación MQTT

---

## 🛠️ Stack Tecnológico

| Herramienta | Función |
|---|---|
| **Python 3.10+** | Motor del gemelo digital |
| **paho-mqtt 2.x** | Cliente MQTT con soporte TLS nativo |
| **HiveMQ Cloud** | Broker MQTT en la nube (free tier, TLS/8883) |
| **Node-RED** | Suscripción MQTT, procesamiento y dashboard |
| **node-red-dashboard** | Gauges, charts y texto en tiempo real |

---

## 📁 Estructura del Proyecto

```
cookie-line-twin/
├── twin.py              # Loop principal: tick → cascada → OEE → publicación MQTT
├── machines.py          # Modelo Machine: estados, fallas, micro-stops, temperatura
├── oee.py               # ShiftOEE: Disponibilidad × Rendimiento × Calidad + reset turno
├── config.py            # Todos los parámetros configurables (broker, tasas, rangos)
├── requirements.txt     # paho-mqtt>=2.0.0
├── nodered/
│   └── flows.json       # Flujo Node-RED listo para importar (broker HiveMQ pre-config)
└── README.md
```

---

## ⚙️ Instalación y Uso

**Instalar dependencias:**
```powershell
pip install -r requirements.txt
```

**Ejecutar el gemelo:**
```powershell
python twin.py
```

**Salida esperada en consola:**
```
10:20:23  INFO  ▶  Gemelo digital iniciado. Publicando cada 2.0s en 'factory/cookie-line/#'
10:20:23  INFO  Conectado al broker MQTT en xxxx.hivemq.cloud:8883
10:20:25  INFO  OEE= 87.3%  Activas=5/5  Turno=0.1min
10:20:41  INFO  OEE= 74.1%  Activas=4/5  Turno=0.3min  ⚠FALLA:M2(FLT-M2-004)
10:21:26  INFO  OEE= 71.8%  Activas=4/5  Turno=1.1min  🔄ARRANQUE:M2
```

**Importar flujo en Node-RED:**
1. Abrir `http://localhost:1880`
2. ☰ → **Import** → pegar contenido de `nodered/flows.json`
3. **Deploy**
4. Dashboard en `http://localhost:1880/ui`

> **Requisito:** `node-red-dashboard` instalado (`☰ → Manage palette → node-red-dashboard`)

---

## 📡 Topics MQTT Publicados

| Topic | Contenido |
|---|---|
| `factory/cookie-line/M1..M5/status` | Estado, velocidad %, contador, rechazos, alarma |
| `factory/cookie-line/M4/status` | Agrega `temperature_c`, `temp_setpoint`, `temp_deviation` |
| `factory/cookie-line/oee` | Disponibilidad, Rendimiento, Calidad, OEE %, turno |
| `factory/cookie-line/line/summary` | Estado global, producción, merma %, `fault_details` |

**Ejemplo payload OEE:**
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

**Ejemplo payload falla en `line/summary`:**
```json
{
  "line_state": "fault",
  "fault_details": [
    { "machine": "M2", "name": "Laminadora", "alarm": "FLT-M2-004" }
  ]
}
```

---

## 📊 Dashboard Node-RED

| Widget | Descripción |
|---|---|
| **OEE Global** (gauge) | OEE % en tiempo real, semáforo rojo/amarillo/verde |
| **OEE en el tiempo** (chart) | Tendencia histórica del turno |
| **Estado de Línea** (texto) | `▶ CORRIENDO` / `⚠ FALLA` / `🔄 ARRANQUE` / `⏹ DETENIDA` |
| **Alerta activa** (texto) | `⚠ Laminadora (M2) → FLT-M2-004` |
| **Merma del Turno** (gauge) | Tasa de rechazos %, alerta arriba del 3% |
| **Producción vs Rechazos** (chart) | Acumulado del turno con spikes de eventos de calidad |
| **M1–M5 Velocidad** (gauges) | Velocidad % por máquina |
| **Temperatura Horno** (gauge) | °C actual con rango 150–220°C |
| **Desviación Temperatura** (chart) | Deriva desde setpoint 185°C — visible la oscilación realista |

---

## ⚙️ Parámetros Configurables (`config.py`)

| Parámetro | Default | Descripción |
|---|---|---|
| `BROKER_HOST` | `xxxx.hivemq.cloud` | Host del broker MQTT |
| `BROKER_PORT` | `8883` | Puerto TLS |
| `PUBLISH_INTERVAL` | `2.0` | Segundos entre publicaciones |
| `SHIFT_DURATION_MIN` | `480` | Duración del turno (minutos) |
| `FAULT_PROB_PER_CYCLE` | `0.015` | Probabilidad de falla por ciclo (1.5%) |
| `MICRO_STOP_PROB` | `0.04` | Probabilidad de micro-detención (4%) |
| `QTY_REJECT_RATE_BASE` | `0.05` | Tasa base de merma (5%) |
| `CASCADE_TRIGGER_IDS` | `{"M3"}` | Máquinas cuya falla bloquea aguas abajo |
| `OVEN_TEMP_SETPOINT` | `185.0` | Temperatura objetivo del horno (°C) |

---

## 🔍 Verificación sin Node-RED

Suscribirse directamente con `mosquitto_sub`:
```powershell
mosquitto_sub -h xxxx.hivemq.cloud -p 8883 --cafile "" -u Admin -P tu_password -t "factory/cookie-line/#" -v
```

O desde la consola web de HiveMQ Cloud → **Web Client** → suscribir a `factory/cookie-line/#`.

---

## 🗺️ Roadmap Sugerido

- [ ] Persistencia histórica en InfluxDB
- [ ] Grafana como alternativa al dashboard Node-RED
- [ ] API REST (FastAPI) para consultas externas
- [ ] Modo replay con datos históricos grabados
- [ ] Integración con agente IA para detección predictiva de fallas (MantOS)

---

**Autor:** Gabriel Castro — Especialista en Automatización e IIoT
