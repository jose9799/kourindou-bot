# Roadmap — Kourindou Bot

**Estado global:** Fases 0–6 implementadas · pendiente de verificación en servidor real
**Última actualización:** 2026-09-01

Marca las casillas conforme se completen. Cada fase debe quedar **funcionando y probada en un
servidor real** antes de darla por cerrada.

Leyenda: `[ ]` pendiente · `[~]` en progreso · `[x]` hecho

> ⚠️ **Los bloques "Verificación de la fase" están sin marcar a propósito.** El código está
> escrito, pero no se ha ejecutado: el entorno de desarrollo no tiene Python instalado, así que
> no se ha podido lanzar el bot ni pasar `ruff`. Son las primeras tareas a hacer.

---

## Fase 0 — Diseño y Especificación `[x]`

- [x] Definir visión, temática y alcance del bot
- [x] Elegir stack: Python 3.10+, `discord.py` v2, `aiosqlite`, arquitectura de Cogs
- [x] Cerrar decisión de moneda: **una sola** (Puntos de Fe 🌸)
- [x] Cerrar decisión de comandos: **híbridos** (`/slash` + `!prefijo`)
- [x] Cerrar decisión de alcance: **multi-guild** (todo lleva `guild_id`)
- [x] Diseñar el modelo de datos completo
- [x] Definir reglas anti-abuso de economía (voz, chat, transferencias)
- [x] Redactar `specs.md`, `roadmap.md`, `README.md` y `codestyle.md`

---

## Fase 1 — Estructura y Base de Datos `[x]`

**Andamiaje del proyecto**
- [x] `git init` + `.gitignore` (`.env`, `*.db`, `__pycache__/`, `.venv/`)
- [ ] Crear entorno virtual e instalar dependencias
- [x] `requirements.txt` con las 3 dependencias
- [x] `.env.example` como plantilla, y `.env` real fuera del control de versiones

**Configuración**
- [x] `config.py`: carga de `.env` con `python-dotenv`
- [x] Constantes de balance por defecto (Fe diaria, Fe/minuto, rangos de chat, cooldowns)
- [x] Fallo temprano y con mensaje claro si falta `DISCORD_TOKEN`

**Base de datos**
- [x] `database/schema.sql` con el DDL de `specs.md` §4
- [x] `database/db_manager.py`: conexión, `PRAGMA foreign_keys = ON`, `journal_mode = WAL`
- [x] Ejecución idempotente del esquema al arrancar
- [x] `ensure_user(user_id, guild_id)` como base de todo lo demás
- [x] Helpers de tiempo: epoch UTC en enteros, un único punto de verdad

**Bot**
- [x] `main.py` con subclase de `commands.Bot` e intents correctos
- [x] `setup_hook`: abrir BD, cargar Cogs desde `config.COGS`
- [x] Sync de app commands: instantáneo a `DEV_GUILD_ID`, global si no está definido
- [x] Logging rotativo a fichero + consola
- [x] Manejadores globales `on_command_error` y `on_app_command_error`
- [x] Cierre limpio de la conexión a BD al apagar

**Verificación de la fase**
- [ ] El bot aparece en línea en Gensokyolis:Re
- [ ] El fichero `.db` se crea con todas las tablas
- [ ] `/ping` responde por slash y por prefijo

---

## Fase 2 — Economía de Fe `[x]`

**Capa de datos**
- [x] `add_faith(...)` y `try_spend(...)` — escriben siempre en `transactions`
- [x] `transfer_faith(...)` en una sola transacción atómica
- [x] `try_claim_daily(...)` — devuelve resultado + tiempo restante si está en cooldown
- [x] `get_leaderboard(...)` y `get_rank(...)`

**Comandos (`cogs/economy.py`)**
- [x] `/daily` — Ofrenda al Santuario Hakurei, cooldown rodante de 22h
- [x] Lógica de racha: +10% por día, tope +100%, se reinicia pasadas 48h
- [x] `/faith [miembro]` (alias `!balance`) con embed temático
- [x] `/transfer <miembro> <cantidad>` (alias `!pay`)
- [x] Validaciones: no a uno mismo, no a bots, cantidad ≥ mínimo, saldo, antigüedad 24h
- [x] `/leaderboard` — Top 10 con puesto del invocador aunque no esté en el top

**Verificación de la fase**
- [ ] Reclamar `/daily` dos veces seguidas muestra el cooldown, no duplica Fe
- [ ] Transferir más de lo que se tiene falla limpiamente y no altera saldos
- [ ] Cada movimiento queda registrado en `transactions`

---

## Fase 3 — Actividad en Voz y Chat `[x]`

**Fe por chat**
- [x] `on_message`: 5-15 🌸 aleatorio, cooldown de 60s aplicado dentro del `UPDATE`
- [x] Filtros: bots, mensajes cortos, canales excluidos, invocaciones de comandos
- [x] Lista de canales excluidos leída de `guild_config`

**Fe por voz**
- [x] `on_voice_state_update`: abrir, mover y cerrar filas en `voice_sessions`
- [x] `tasks.loop` cada 5 min que liquida el tiempo acumulado y paga
- [x] Condiciones anti-abuso: ≥2 humanos, no ensordecido, no canal AFK
- [x] Reconciliación en `on_ready`: cerrar huérfanas, abrir las que falten
- [x] Actualizar `voice_minutes` como estadística acumulada

**Verificación de la fase**
- [ ] Estar solo en un canal de voz **no** genera Fe
- [ ] Reiniciar el bot con gente conectada no duplica ni pierde el tiempo acumulado
- [ ] El spam de mensajes no salta el cooldown de 60s

---

## Fase 4 — Tienda Kourindou `[x]`

**Catálogo**
- [x] CRUD de `shop_items` en `db_manager`
- [x] Validación al alta de ítems `role`: el rol existe y el bot puede asignarlo
- [x] Semilla inicial de artículos temáticos (`/shopadmin seed`)

**Interfaz**
- [x] `/shop` con selector de categoría y selector de artículo
- [x] Botón de compra con diálogo de confirmación efímero
- [x] Timeout de 120s que deshabilita los componentes
- [x] La view solo responde a quien invocó el comando

**Compra e inventario**
- [x] Compra atómica: cobrar y registrar en `inventory` en la misma transacción
- [x] Asignación real del rol, con reembolso si la API de Discord falla
- [x] Respetar `stock` y `unique_owned`
- [x] `/inventory [miembro]`

**Verificación de la fase**
- [ ] Comprar sin saldo suficiente falla sin cobrar
- [ ] Si la asignación de rol falla por jerarquía, la Fe se devuelve
- [ ] No se puede comprar dos veces un ítem con `unique_owned = 1`

---

## Fase 5 — Minijuegos y Utilidades `[x]`

**Minijuegos (`cogs/games.py`)**
- [x] Helper compartido de apuesta: valida, cobra y corta si no hay saldo
- [x] `/danmaku_flip <cantidad> <cara|cruz>` — pago 2x
- [x] `/kappa_slots <cantidad>` — 3 símbolos con multiplicadores calibrados
- [x] Documentar el cálculo de probabilidades junto a la tabla de símbolos (RTP 95,01%)
- [x] `/roulette <cantidad> <apuesta>` — color 2x, rango 3x (RTP 97,3%)
- [x] Límites de apuesta y cooldown de 10s por usuario

**Utilidades (`cogs/utils.py`)**
- [x] `/teams [equipos]` — reparto aleatorio y equilibrado del canal de voz
- [x] `/squad <juego> [hora]` — convocatoria con 3 botones y embed que se edita en vivo
- [x] View persistente para `/squad`, con barrido que cierra las de más de 12h
- [x] `/addquote`, `/quote`, `/quotes`, `/delquote`

**Verificación de la fase**
- [ ] Simular 10.000 tiradas de slots y confirmar que el RTP real ronda el 95%
- [ ] `/teams` falla con mensaje claro si el invocador no está en voz
- [ ] Los botones de `/squad` siguen funcionando tras reiniciar el bot

---

## Fase 6 — Administración `[x]`

- [x] `cogs/admin.py` restringido por `Manage Server`
- [x] `/config view`, `/config set <clave> <valor>`, `/config reset <clave>`
- [x] `/shopadmin list|add|remove|toggle|seed`
- [x] `/eco give|take|set` con registro en `transactions`
- [x] `/eco <miembro>` — historial de movimientos de Fe
- [ ] Script de backup de la base de datos

---

## Pendiente Inmediato

Lo que hay que hacer antes de dar el proyecto por operativo:

- [ ] Instalar Python 3.10+ en la máquina de desarrollo
- [ ] `pip install -r requirements.txt`
- [ ] `ruff format . && ruff check .` y corregir lo que salga
- [ ] Regenerar el token del bot (el actual se ha expuesto en texto plano)
- [ ] Activar los intents privilegiados en el Discord Developer Portal
- [ ] Primer arranque y recorrido de todas las verificaciones de fase

---

## Mejoras Futuras

- [ ] Sistema de niveles/rangos con roles automáticos por Fe acumulada
- [ ] Eventos temporales tipo *Incidente de Gensokyo* (multiplicadores durante X horas)
- [ ] Perfil de usuario con tarjeta generada en imagen
- [ ] Ítems `consumable` con efectos reales (multiplicador temporal, protección de racha)
- [ ] Paginación real en `/shop` cuando una categoría supere los 25 artículos
- [ ] Tests automatizados de la capa `db_manager`
- [ ] Migrar a PostgreSQL si el servidor crece lo suficiente

---

## Cuestiones Abiertas

- [ ] Hosting de producción (VPS / Raspberry Pi / servicio gestionado)
- [ ] Frecuencia y destino de los backups
- [ ] Precios reales del catálogo — medir el ritmo de generación de Fe tras la Fase 3
- [ ] Lista definitiva de canales excluidos de la Fe por chat
