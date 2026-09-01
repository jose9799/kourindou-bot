# Kourindou Bot 🌸

Bot de Discord personalizado para el servidor **Gensokyolis:Re**, con temática de
*Touhou Project*. Nombrado en honor a **Kourindou**, la tienda de antigüedades de Rinnosuke
Morichika donde acaban todos los objetos raros que cruzan la Barrera Hakurei.

El bot implementa una economía de servidor basada en **Puntos de Fe (🌸)** que los miembros
ganan por participar —hablando en chat, estando en canales de voz, reclamando su ofrenda
diaria— y gastan en una tienda de roles y permisos, o apuestan en minijuegos temáticos.

---

## 📍 Estado del Proyecto

| | |
|---|---|
| **Versión de especificación** | 1.2.1 |
| **Fases implementadas** | 0 a 6 — el bot está completo a nivel de código |
| **Estado** | ⚠️ **Sin ejecutar todavía**: falta instalar Python y hacer el primer arranque |
| **Última actualización** | 2026-09-01 |

**Lo siguiente que toca hacer:** instalar Python 3.10+, crear el entorno virtual, pasar `ruff`
y arrancar el bot por primera vez para recorrer las verificaciones de cada fase. La lista
concreta está en [`roadmap.md`](roadmap.md) → *Pendiente Inmediato*.

> 🔐 El token que hay ahora mismo en `.env` se compartió en texto plano y debe considerarse
> comprometido. Regeneralo en el Developer Portal antes de poner el bot en producción.

---

## 📚 Documentos del Proyecto

Tres archivos, tres propósitos distintos. Conviene no mezclarlos:

| Archivo | Qué contiene | Cuándo consultarlo |
|---------|--------------|--------------------|
| [`README.md`](README.md) | Este archivo. Visión general, estado actual y guía de uso. | Para orientarte al retomar el proyecto. |
| [`specs.md`](specs.md) | La especificación técnica: decisiones cerradas, esquema de BD, reglas de cada módulo. | Antes de implementar cualquier cosa. Es la fuente de verdad. |
| [`roadmap.md`](roadmap.md) | Plan de trabajo en fases, con checklist tarea por tarea. | Para saber qué toca ahora y marcar progreso. |
| [`codestyle.md`](codestyle.md) | Reglas de estilo, logging, estructura y checklist de production ready. | Mientras escribes código, y antes de dar una tarea por terminada. |

`specs.v1.1.0.bak.md` es el respaldo de la especificación original, antes de cerrar las
decisiones ambiguas. Se puede borrar cuando ya no aporte contexto.

---

## 🎯 Decisiones de Diseño Cerradas

Estas cinco decisiones estaban ambiguas en la primera versión de la especificación y ya están
fijadas. Todo lo demás las asume:

1. **Una sola moneda.** Puntos de Fe (`faith_points`). "P-Items" y "Poder" son sinónimos
   estéticos del mismo contador, no una segunda economía.
2. **Comandos híbridos.** `commands.hybrid_command` — cada comando funciona como `/slash`
   y como `!prefijo` desde una única implementación.
3. **Multi-guild.** Toda fila de datos lleva `guild_id`. Aunque hoy solo corra en un servidor,
   el esquema no lo asume.
4. **Configuración en dos capas.** Defaults en `config.py`, overrides por servidor en la tabla
   `guild_config`.
5. **Prefijo `!`** por defecto, configurable por servidor.

---

## 🏗️ Arquitectura

```
kourindou_bot/
│
├── main.py                # Entrada principal, carga de Cogs, sync de comandos
├── config.py              # Variables de entorno y defaults de balance
├── .env                   # Secretos reales — NUNCA se commitea
├── .env.example           # Plantilla de secretos
│
├── database/
│   ├── schema.sql         # DDL completo e idempotente
│   ├── db_manager.py      # Capa de acceso asíncrona — única puerta a la BD
│   └── kourindou.db       # Base de datos SQLite (generada, no se commitea)
│
├── cogs/
│   ├── economy.py         # daily, faith, transfer, leaderboard
│   ├── voice.py           # Fe por tiempo en voz y por mensajes
│   ├── shop.py            # Tienda Kourindou e inventario (UI interactiva)
│   ├── games.py           # danmaku_flip, kappa_slots, roulette
│   ├── utils.py           # teams, squad, quote
│   └── admin.py           # Configuración y gestión (Fase 6)
│
├── requirements.txt
├── specs.md
├── roadmap.md
└── README.md
```

**Regla de capas — importante:** los Cogs **nunca** ejecutan SQL. Todo pasa por
`db_manager.py`, que expone funciones de dominio (`add_faith`, `try_claim_daily`,
`transfer_faith`) y no deja escapar detalles de SQLite hacia arriba. Esto mantiene la lógica
de integridad —transacciones atómicas, validación de saldo— en un solo sitio.

---

## 💾 Modelo de Datos

Siete tablas. El DDL completo y comentado está en [`specs.md`](specs.md) §4.

| Tabla | Propósito |
|-------|-----------|
| `users` | Saldo, racha diaria y contadores por usuario **y servidor** (PK compuesta). |
| `shop_items` | Catálogo de la tienda, editable sin tocar código. |
| `inventory` | Qué posee cada usuario. Referencia al catálogo por ID, no por nombre. |
| `voice_sessions` | Sesiones de voz abiertas, **persistidas en BD** para sobrevivir reinicios. |
| `quotes` | Frases célebres del servidor. |
| `guild_config` | Overrides de balance por servidor, en formato clave-valor. |
| `transactions` | Auditoría de todo movimiento de Fe. Sin esto no hay forma de depurar la economía. |

Todas las marcas de tiempo son **enteros Unix epoch en UTC**, nunca strings de fecha ni horas
locales.

---

## 🎮 Funcionalidades Planeadas

### Economía (Fase 2)
- `/daily` — *Ofrenda al Santuario Hakurei*. Cooldown rodante de 22h, con racha acumulable
  (+10% por día, tope +100%).
- `/faith [miembro]` — consulta de saldo.
- `/transfer <miembro> <cantidad>` — donación entre miembros, con validaciones anti-exploit.
- `/leaderboard` — Top 10 de fieles del servidor.

### Actividad (Fase 3)
- **Chat:** 5-15 🌸 por mensaje, cooldown de 60s.
- **Voz:** 2 🌸 por minuto, liquidados cada 5 minutos. No se paga si estás solo en el canal,
  ensordecido, o en el canal AFK.

### Tienda Kourindou (Fase 4)
- Roles temáticos: Mansión del Diablo Escarlata, Tengu de la Montaña Youkai, Hadas del Lago,
  Hermitaños.
- Permisos: canales VIP, adjuntar archivos, Soundboard.
- Recompensas de servidor: elegir el juego de la noche, el icono temporal del servidor.
- Interfaz con menús desplegables y confirmación de compra.

### Minijuegos (Fase 5)
- `/danmaku_flip` — cara o cruz, pago 2x.
- `/kappa_slots` — tragaperras de Nitori, multiplicadores calibrados a RTP ~95%.
- `/roulette` — ruleta de Gensokyo, apuestas a color o rango.

### Utilidades (Fase 5)
- `/teams` — reparte el canal de voz en equipos equilibrados.
- `/squad` — convocatoria de partida con botones "Me sumo / Llego tarde / No puedo".
- `/quote`, `/addquote` — frases célebres y fuera de contexto del servidor.

---

## ⚙️ Instalación y Puesta en Marcha

> Aplicable a partir de que la Fase 1 esté implementada.

**Requisitos:** Python 3.10 o superior.

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

Copia `.env.example` a `.env` y rellena el token:

```
DISCORD_TOKEN=tu_token_aqui
DATABASE_PATH=database/kourindou.db
DEV_GUILD_ID=id_del_servidor_de_pruebas
LOG_LEVEL=INFO
```

```bash
python main.py
```

### Configuración en el Discord Developer Portal

El bot necesita **dos intents privilegiados** que hay que activar a mano en el portal. Si
faltan, el bot arranca pero las funciones fallan silenciosamente:

- ✅ **Message Content Intent** — para la Fe por chat y los comandos con prefijo.
- ✅ **Server Members Intent** — para `/teams`, roles de tienda y menciones.

### Permisos necesarios al invitar el bot

- `Send Messages`, `Embed Links`, `Read Message History`
- `Manage Roles` — para la tienda
- `Connect` / `View Channels` — para el tracking de voz

⚠️ **Jerarquía de roles:** el rol del bot debe estar **por encima** de cualquier rol vendible
en la tienda, o la asignación fallará en tiempo de ejecución. Es el error más común al montar
bots con roles de recompensa.

---

## 🔄 Cómo Iterar en Este Proyecto

Flujo recomendado para cada sesión de trabajo:

1. **Abrir `roadmap.md`** y ver cuál es la primera casilla sin marcar.
2. **Consultar `specs.md`** para la sección correspondiente antes de escribir código — ahí
   están las reglas exactas (cooldowns, validaciones, condiciones anti-abuso).
3. **Implementar** solo esa tarea o ese bloque de tareas, siguiendo
   [`codestyle.md`](codestyle.md).
4. **Verificar** con el bloque "Verificación de la fase" del roadmap y con el checklist de
   *production ready* de `codestyle.md` §13. Una fase no está hecha hasta que se prueba en un
   servidor real.
5. **Marcar la casilla** en `roadmap.md` y actualizar la tabla de estado de este README.

**Si un cambio contradice la especificación**, se actualiza `specs.md` primero y se sube la
versión. La especificación es la fuente de verdad; el código la sigue, no al revés.

---

## 📖 Glosario Touhou

Para quien no conozca el lore y tenga que tocar el código:

| Término | Qué es |
|---------|--------|
| **Gensokyo** | El mundo cerrado donde ocurre *Touhou*, aislado por la Barrera Hakurei. |
| **Kourindou** | Tienda de antigüedades de Rinnosuke Morichika. Da nombre al bot y a la tienda. |
| **Fe / Faith** | En el lore, la energía que sostiene a los dioses y santuarios. Aquí, la moneda. |
| **Santuario Hakurei** | Santuario de Reimu Hakurei. Da nombre a la recompensa diaria. |
| **Danmaku** | "Cortina de balas" — el estilo de duelo característico de la saga. |
| **P-Items** | Ítems de poder que se recogen en los juegos. Sinónimo estético de la Fe. |
| **Kappa / Nitori** | Nitori Kawashiro, kappa ingeniera. Da nombre a la tragaperras. |
| **Tengu** | Youkai de la Montaña Youkai, periodistas y guerreros. Uno de los roles de facción. |

---

## 🛠️ Stack

```txt
discord.py>=2.3.0
aiosqlite>=0.19.0
python-dotenv>=1.0.0
```

Python 3.10+ · SQLite (WAL) · Arquitectura asíncrona con Cogs
