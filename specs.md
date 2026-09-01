# Especificaciones Técnicas del Proyecto: Kourindou Bot (Discord.py)

**Servidor:** Gensokyolis:Re
**Temática:** Touhou Project
**Versión:** 1.2.0 (Modelo de datos cerrado)
**Estado:** Fase de Diseño / Listo para Fase 1
**Entorno de Ejecución:** Python 3.10+ / `discord.py` v2.x
**Arquitectura:** Asyncio + Cogs + `aiosqlite`

---

## 0. Decisiones de Diseño Cerradas

Estas decisiones estaban ambiguas en la v1.1.0 y quedan fijadas aquí. Todo el resto del
documento asume que son verdad.

| # | Decisión | Resolución |
|---|----------|-----------|
| D1 | **Moneda** | **Una sola moneda: Puntos de Fe (🌸 `faith_points`).** "P-Items / Power Points" queda como sinónimo puramente estético en textos de sabor. No existe una segunda economía. |
| D2 | **Tipo de comando** | **Híbridos** (`commands.hybrid_command`). Cada comando responde tanto a `/comando` como a `!comando` desde una única implementación. |
| D3 | **Alcance** | **Multi-guild por diseño.** Toda fila de datos lleva `guild_id`. Aunque hoy solo corra en Gensokyolis:Re, el esquema no asume un único servidor. |
| D4 | **Configuración** | Valores de balance en `config.py` como *defaults*, sobreescribibles por servidor vía tabla `guild_config` (comandos de admin en fase posterior). |
| D5 | **Prefijo** | `!` por defecto, configurable por servidor. |

---

## 1. Visión General del Proyecto

**Kourindou Bot** es un bot personalizado para el servidor **Gensokyolis:Re**. Inspirado en el
lore de *Touhou Project* (nombrado por la tienda de antigüedades Kourindou de Rinnosuke
Morichika), integra un sistema de **economía basada en Fe**, recompensas por actividad en voz y
chat, minijuegos de azar/Danmaku y utilidades para organizar partidas multijugador.

---

## 2. Terminología y Estética (Gensokyo Economy)

* **Moneda Principal:** Puntos de Fe (🌸 `Faith Points`). Referida en textos de sabor como
  "P-Items" o "Poder" indistintamente, pero es **el mismo contador**.
* **Recompensa Diaria (`/daily`):** *Ofrenda al Santuario Hakurei*.
* **Tienda (`/shop`):** *Tienda Kourindou* — artefactos, roles de facción y permisos VIP.
* **Minijuegos (`/games`):** *Duelos Danmaku / Apuestas de Gensokyo*.

---

## 3. Arquitectura del Sistema

```
kourindou_bot/
│
├── main.py                # Entrada principal, carga de Cogs, sync de app commands
├── config.py              # Variables de entorno y defaults de balance
├── .env.example           # Plantilla de secretos (nunca commitear .env)
│
├── database/
│   ├── schema.sql         # DDL completo (idempotente, CREATE TABLE IF NOT EXISTS)
│   └── db_manager.py      # Capa de acceso asíncrona (aiosqlite), única puerta a la BD
│
├── cogs/
│   ├── economy.py         # daily, faith, transfer, leaderboard
│   ├── shop.py            # Tienda Kourindou e inventario (discord.ui Views)
│   ├── voice.py           # Fe por tiempo en voz y por mensajes
│   ├── games.py           # danmaku_flip, kappa_slots, roulette
│   ├── utils.py           # teams, squad, quote
│   └── admin.py           # Configuración por servidor, ajustes de saldo (fase 6)
│
├── requirements.txt
└── specs.md               # Este documento
```

**Regla de capas:** los Cogs nunca ejecutan SQL directamente. Todo pasa por `db_manager.py`,
que expone funciones de dominio (`add_faith`, `try_claim_daily`, ...) y no filtra detalles de
SQLite hacia arriba.

---

## 4. Modelo de Datos

Todas las marcas de tiempo se guardan como **enteros Unix epoch en UTC**. Nada de strings de
fecha ni de horas locales: evita ambigüedad de zona horaria y hace triviales las comparaciones
de cooldown.

```sql
-- Un usuario por servidor. La PK es COMPUESTA: el mismo usuario de Discord en dos
-- guilds son dos economías independientes.
CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER NOT NULL,
    guild_id       INTEGER NOT NULL,
    faith_points   INTEGER NOT NULL DEFAULT 0,
    last_daily     INTEGER,            -- epoch UTC del último /daily reclamado
    daily_streak   INTEGER NOT NULL DEFAULT 0,
    voice_minutes  INTEGER NOT NULL DEFAULT 0,  -- acumulado histórico (estadística)
    last_message   INTEGER,            -- epoch UTC, para el cooldown de Fe por chat
    created_at     INTEGER NOT NULL,
    PRIMARY KEY (user_id, guild_id)
);

-- Catálogo de la tienda. Editable en caliente sin tocar código.
CREATE TABLE IF NOT EXISTS shop_items (
    item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     INTEGER NOT NULL,
    name         TEXT    NOT NULL,
    description  TEXT,
    price        INTEGER NOT NULL,
    kind         TEXT    NOT NULL,     -- 'role' | 'perk' | 'cosmetic' | 'consumable'
    payload      TEXT,                 -- role_id, clave de permiso, etc. según kind
    stock        INTEGER,              -- NULL = ilimitado
    unique_owned INTEGER NOT NULL DEFAULT 1,  -- 1 = no se puede comprar dos veces
    enabled      INTEGER NOT NULL DEFAULT 1,
    UNIQUE (guild_id, name)
);

-- Qué posee cada usuario. Referencia al catálogo por ID, NO por nombre:
-- renombrar un ítem no rompe el inventario existente.
CREATE TABLE IF NOT EXISTS inventory (
    entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    guild_id     INTEGER NOT NULL,
    item_id      INTEGER NOT NULL,
    acquired_at  INTEGER NOT NULL,
    FOREIGN KEY (user_id, guild_id) REFERENCES users (user_id, guild_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES shop_items (item_id) ON DELETE CASCADE
);

-- Sesiones de voz abiertas. Persistidas en BD, NO en memoria: si el bot
-- reinicia con gente en un canal, el tiempo no se pierde ni se duplica.
CREATE TABLE IF NOT EXISTS voice_sessions (
    user_id      INTEGER NOT NULL,
    guild_id     INTEGER NOT NULL,
    channel_id   INTEGER NOT NULL,
    joined_at    INTEGER NOT NULL,
    PRIMARY KEY (user_id, guild_id)
);

CREATE TABLE IF NOT EXISTS quotes (
    quote_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     INTEGER NOT NULL,
    author_id    INTEGER NOT NULL,     -- a quién se le atribuye la frase
    added_by     INTEGER NOT NULL,     -- quién la registró
    content      TEXT    NOT NULL,
    message_link TEXT,                 -- enlace al mensaje original si existe
    created_at   INTEGER NOT NULL
);

-- Overrides de balance por servidor. Clave-valor para no migrar el esquema
-- cada vez que se añade un parámetro nuevo.
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id     INTEGER NOT NULL,
    key          TEXT    NOT NULL,
    value        TEXT    NOT NULL,
    PRIMARY KEY (guild_id, key)
);

-- Auditoría de todo movimiento de Fe. Imprescindible para depurar la economía
-- y detectar abuso.
CREATE TABLE IF NOT EXISTS transactions (
    tx_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    delta        INTEGER NOT NULL,     -- positivo o negativo
    reason       TEXT    NOT NULL,     -- 'daily' | 'chat' | 'voice' | 'transfer_in' | ...
    counterparty INTEGER,              -- el otro usuario, en transferencias
    created_at   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_faith ON users (guild_id, faith_points DESC);
CREATE INDEX IF NOT EXISTS idx_inv_user    ON inventory (guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_tx_user     ON transactions (guild_id, user_id, created_at DESC);
```

**Notas de integridad:**
* `PRAGMA foreign_keys = ON` en cada conexión (SQLite lo trae desactivado por defecto).
* `PRAGMA journal_mode = WAL` para no bloquear lecturas durante escrituras.
* Las operaciones que mueven saldo (`/transfer`, compras, apuestas) se ejecutan en una
  **única transacción** con `UPDATE ... WHERE faith_points >= ?`, comprobando `rowcount` para
  detectar saldo insuficiente. Nunca leer-y-luego-escribir sin transacción: dos comandos
  concurrentes podrían gastar el mismo saldo dos veces.

---

## 5. Módulos y Funcionalidades

### 5.1. Economía (`cogs/economy.py`)

| Comando | Alias | Descripción |
|---------|-------|-------------|
| `/daily` | `!daily` | *Ofrenda al Santuario Hakurei*. Otorga Fe con cooldown. |
| `/faith [miembro]` | `!balance` | Consulta el saldo propio o de un miembro. |
| `/transfer <miembro> <cantidad>` | `!pay` | Donación de Fe entre miembros. |
| `/leaderboard` | `!top` | Top 10 de fieles del servidor. |

**Reglas de `/daily`:**
* **Cooldown rodante de 22 horas** (no reset a medianoche). 22 en vez de 24 para que el
  usuario no vaya retrasando su hora de reclamo cada día.
* Racha (`daily_streak`): se incrementa si se reclama antes de 48h desde el anterior; se
  reinicia a 1 si se pasa. Bonus de `+10%` por día de racha, con tope de `+100%`.

**Reglas de `/transfer`:**
* Bloqueado hacia uno mismo y hacia bots.
* Cantidad debe ser `>= 1`; se rechazan negativos y cero (evita el exploit clásico de
  "transferir -1000 para robar").
* Requiere que la cuenta emisora tenga al menos 24h de antigüedad en la BD (anti-alt).
* Comisión configurable, **0% por defecto**.
* Ambas patas se registran en `transactions`.

### 5.2. Actividad: Voz y Chat (`cogs/voice.py`)

**Fe por chat:**
* `5-15 🌸` aleatorio por mensaje, cooldown de `60s` por usuario.
* No cuenta: bots, canales excluidos, mensajes de menos de 3 caracteres, ni invocaciones de
  comandos del propio bot.

**Fe por voz:**
* `2 🌸` por minuto, acreditados mediante una `tasks.loop` de barrido cada 5 minutos que
  liquida el tiempo acumulado. **No** se acredita solo al salir del canal: si el bot cae, el
  usuario ya cobró casi todo.
* **Condiciones anti-abuso — no se otorga Fe si:**
  * el usuario está solo en el canal (se exigen ≥2 humanos no-bot),
  * está `self_deaf` o ensordecido por el servidor,
  * el canal es el **canal AFK** del servidor.
* Al arrancar el bot (`on_ready`), se reconcilian las `voice_sessions` de BD contra el estado
  real de los canales de voz: se cierran las huérfanas y se abren las que falten.

### 5.3. Tienda Kourindou (`cogs/shop.py`)

**Tipos de ítem (`shop_items.kind`):**
* `role` — roles temáticos: Residentes de la Mansión del Diablo Escarlata, Tengu de la
  Montaña Youkai, Hadas del Lago, Hermitaños. `payload` = ID del rol de Discord.
* `perk` — permisos: acceso a canal VIP, adjuntar imágenes/archivos, Soundboard en voz.
* `cosmetic` — recompensas de servidor: definir el juego de la noche, elegir el icono
  temporal del servidor.
* `consumable` — de un solo uso; se elimina del inventario al consumirse.

**UI/UX:** `discord.ui.Select` para el catálogo + `discord.ui.Button` de confirmación.
Timeout de 120s en las views; los componentes se deshabilitan al expirar.

**Requisitos operativos (documentar en el README):**
* El bot necesita el permiso **`Manage Roles`**.
* El rol del bot debe estar **por encima** en la jerarquía de todo rol vendible, o la
  asignación fallará en runtime.
* Al crear un ítem `role`, `db_manager` valida que el `payload` corresponda a un rol existente
  y asignable antes de guardarlo.
* Las views persistentes se registran en `setup_hook` con `custom_id` fijo para sobrevivir
  reinicios.

### 5.4. Minijuegos (`cogs/games.py`)

| Comando | Mecánica |
|---------|----------|
| `/danmaku_flip <cantidad> <cara/cruz>` | Cara o cruz. Pago 2x. |
| `/kappa_slots <cantidad>` | 3 símbolos Touhou. Multiplicadores por combinación. |
| `/roulette <cantidad> <apuesta>` | Color (2x) o rango numérico (3x). |

**Reglas transversales:**
* Apuesta mínima `10 🌸`, máxima configurable (default `5000 🌸`).
* La apuesta se **descuenta antes** de resolver el juego, en la misma transacción.
* Cooldown de `10s` por usuario y comando, para no saturar la BD con spam.
* **RTP objetivo ~95%.** Los multiplicadores de `kappa_slots` deben calcularse contra las
  probabilidades reales de la tabla de símbolos, no elegirse a ojo — el cálculo se documenta
  en un comentario del módulo.

### 5.5. Utilidades (`cogs/utils.py`)

* **`/teams [equipos]`** — toma los miembros del canal de voz de quien invoca y los reparte
  aleatoriamente en N equipos (default 2), lo más equilibrados posible en tamaño. Falla con
  mensaje claro si el invocador no está en un canal de voz o hay menos de 2 miembros.
* **`/squad <juego> [hora]`** — convocatoria con botones **"Me sumo" / "Llego tarde" /
  "No puedo"**. El embed se edita en vivo con las listas. View persistente (sobrevive
  reinicios); se cierra automáticamente a las 12h.
* **`/quote`** — muestra una frase aleatoria del servidor.
  **`/addquote <miembro> <texto>`** — registra una frase.
  **`/quotes [miembro]`** — lista paginada.

---

## 6. Requisitos Técnicos

```txt
discord.py>=2.3.0
aiosqlite>=0.19.0
python-dotenv>=1.0.0
```

**Intents requeridos** (activar también en el Discord Developer Portal):
* `message_content` — privilegiado, necesario para Fe por chat y comandos con prefijo.
* `members` — privilegiado, necesario para `/teams`, roles de tienda y menciones.
* `voice_states` — necesario para el tracking de voz.
* `guilds` — base.

**Variables de entorno** (`.env`, nunca en el repositorio):

```
DISCORD_TOKEN=
DATABASE_PATH=database/kourindou.db
DEV_GUILD_ID=          # sync instantáneo de comandos durante desarrollo
LOG_LEVEL=INFO
```

**Manejo de errores:** un `on_command_error` / `on_app_command_error` global que distingue
error esperado (saldo insuficiente, cooldown → mensaje amable, efímero) de error inesperado
(→ log completo con traceback + mensaje genérico al usuario). Nunca dejar que un traceback
llegue al chat.

---

## 7. Roadmap de Iteración

1. **Fase 1 — Estructura y BD.** `main.py`, `config.py`, `schema.sql`, `db_manager.py`.
   Bot que arranca, conecta, crea el esquema y sincroniza comandos. Sin funcionalidad de juego.
2. **Fase 2 — Economía de Fe.** `/daily` con racha, `/faith`, `/transfer`, `/leaderboard`,
   registro en `transactions`.
3. **Fase 3 — Actividad.** Fe por chat y por voz, con la `tasks.loop` de liquidación y la
   reconciliación de sesiones al arranque.
4. **Fase 4 — Tienda Kourindou.** Catálogo en BD, views interactivas, asignación de roles,
   inventario.
5. **Fase 5 — Minijuegos y Utilidades.** `danmaku_flip`, `kappa_slots`, `roulette`, `/teams`,
   `/squad`, `/quote`.
6. **Fase 6 — Administración.** `admin.py`: editar `guild_config`, gestionar `shop_items`,
   ajustar saldos, exportar auditoría.

---

## 8. Cuestiones Abiertas

Pendientes de decidir, no bloquean la Fase 1:

* **Hosting:** ¿dónde corre el bot en producción (VPS, Raspberry Pi, servicio gestionado)?
  Determina la estrategia de backup del `.db`.
* **Backups:** frecuencia y destino del respaldo de la base de datos.
* **Precios reales del catálogo:** los ítems están descritos pero sin cifras. Depende del ritmo
  real de generación de Fe, que se puede medir tras la Fase 3.
* **Canales excluidos:** lista de canales donde no se otorga Fe por chat (spam, bots, logs).
