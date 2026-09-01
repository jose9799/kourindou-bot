# Roadmap — Kourindou Bot

**Estado global:** Fase 0 completada · Fase 1 lista para empezar
**Última actualización:** 2026-09-01

Marca las casillas conforme se completen. Cada fase debe quedar **funcionando y probada en un
servidor real** antes de pasar a la siguiente — no se acumulan fases a medias.

Leyenda: `[ ]` pendiente · `[~]` en progreso · `[x]` hecho

---

## Fase 0 — Diseño y Especificación `[x]`

- [x] Definir visión, temática y alcance del bot
- [x] Elegir stack: Python 3.10+, `discord.py` v2, `aiosqlite`, arquitectura de Cogs
- [x] Cerrar decisión de moneda: **una sola** (Puntos de Fe 🌸)
- [x] Cerrar decisión de comandos: **híbridos** (`/slash` + `!prefijo`)
- [x] Cerrar decisión de alcance: **multi-guild** (todo lleva `guild_id`)
- [x] Diseñar el modelo de datos completo (7 tablas + índices)
- [x] Definir reglas anti-abuso de economía (voz, chat, transferencias)
- [x] Redactar `specs.md` v1.2.0
- [x] Redactar `roadmap.md` y `README.md`

---

## Fase 1 — Estructura y Base de Datos `[ ]`

> **Objetivo:** un bot que arranca, se conecta a Discord, crea su base de datos y sincroniza
> comandos. Sin funcionalidad de juego todavía.

**Andamiaje del proyecto**
- [ ] `git init` + `.gitignore` (`.env`, `*.db`, `__pycache__/`, `.venv/`)
- [ ] Crear entorno virtual e instalar dependencias
- [ ] `requirements.txt` con las 3 dependencias
- [ ] `.env.example` como plantilla, y `.env` real fuera del control de versiones

**Configuración**
- [ ] `config.py`: carga de `.env` con `python-dotenv`
- [ ] Constantes de balance por defecto (Fe diaria, Fe/minuto, rangos de chat, cooldowns)
- [ ] Fallo temprano y con mensaje claro si falta `DISCORD_TOKEN`

**Base de datos**
- [ ] `database/schema.sql` con el DDL de `specs.md` §4
- [ ] `database/db_manager.py`: conexión, `PRAGMA foreign_keys = ON`, `journal_mode = WAL`
- [ ] Ejecución idempotente del esquema al arrancar
- [ ] `get_or_create_user(user_id, guild_id)` como base de todo lo demás
- [ ] Helpers de tiempo: epoch UTC en enteros, un único punto de verdad

**Bot**
- [ ] `main.py` con subclase de `commands.Bot` e intents correctos
- [ ] `setup_hook`: abrir BD, cargar Cogs dinámicamente desde `cogs/`
- [ ] Sync de app commands: instantáneo a `DEV_GUILD_ID` en desarrollo, global en producción
- [ ] Logging configurado a fichero + consola
- [ ] Manejadores globales `on_command_error` / `on_app_command_error`
- [ ] Cierre limpio de la conexión a BD al apagar

**Verificación de la fase**
- [ ] El bot aparece en línea en Gensokyolis:Re
- [ ] El fichero `.db` se crea con las 7 tablas
- [ ] Un comando `/ping` de prueba responde por slash y por prefijo

---

## Fase 2 — Economía de Fe `[ ]`

> **Objetivo:** ganar, consultar y mover Puntos de Fe.

**Capa de datos**
- [ ] `add_faith(user, guild, delta, reason)` — escribe siempre en `transactions`
- [ ] `transfer_faith(origen, destino, cantidad)` en **una sola transacción atómica**
- [ ] `try_claim_daily(user, guild)` — devuelve resultado + tiempo restante si está en cooldown
- [ ] `get_leaderboard(guild, limite)`

**Comandos (`cogs/economy.py`)**
- [ ] `/daily` — Ofrenda al Santuario Hakurei, cooldown rodante de 22h
- [ ] Lógica de racha: +10% por día, tope +100%, se reinicia pasadas 48h
- [ ] `/faith [miembro]` (alias `/balance`) con embed temático
- [ ] `/transfer <miembro> <cantidad>` (alias `/pay`)
- [ ] Validaciones: no a uno mismo, no a bots, cantidad ≥ 1, saldo suficiente, antigüedad 24h
- [ ] `/leaderboard` — Top 10 con posición del invocador aunque no esté en el top

**Verificación de la fase**
- [ ] Reclamar `/daily` dos veces seguidas muestra el cooldown, no duplica Fe
- [ ] Transferir más de lo que se tiene falla limpiamente y no altera saldos
- [ ] Cada movimiento queda registrado en `transactions`

---

## Fase 3 — Actividad en Voz y Chat `[ ]`

> **Objetivo:** la economía se alimenta sola con la actividad del servidor.

**Fe por chat**
- [ ] `on_message`: 5-15 🌸 aleatorio, cooldown de 60s por usuario
- [ ] Filtros: bots, mensajes < 3 caracteres, canales excluidos, invocaciones de comandos
- [ ] Lista de canales excluidos leída de `guild_config`

**Fe por voz**
- [ ] `on_voice_state_update`: abrir y cerrar filas en `voice_sessions`
- [ ] `tasks.loop` cada 5 min que liquida el tiempo acumulado y paga
- [ ] Condiciones anti-abuso: ≥2 humanos en el canal, no `deaf`, no canal AFK
- [ ] Reconciliación en `on_ready`: cerrar sesiones huérfanas, abrir las que falten
- [ ] Actualizar `voice_minutes` como estadística acumulada

**Verificación de la fase**
- [ ] Estar solo en un canal de voz **no** genera Fe
- [ ] Reiniciar el bot con gente conectada no duplica ni pierde el tiempo acumulado
- [ ] El spam de mensajes no salta el cooldown de 60s

---

## Fase 4 — Tienda Kourindou `[ ]`

> **Objetivo:** gastar la Fe en algo que valga la pena.

**Catálogo**
- [ ] CRUD de `shop_items` en `db_manager`
- [ ] Validación al alta de ítems `role`: el rol existe y el bot puede asignarlo
- [ ] Semilla inicial de ítems temáticos (Mansión Escarlata, Tengu, Hadas, Hermitaños)

**Interfaz**
- [ ] `/shop` con `discord.ui.Select` paginado por categoría
- [ ] Botón de confirmación de compra con resumen de precio y saldo restante
- [ ] Timeout de 120s que deshabilita los componentes
- [ ] La view solo responde a quien invocó el comando

**Compra e inventario**
- [ ] Compra atómica: cobrar y registrar en `inventory` en la misma transacción
- [ ] Asignación real del rol de Discord, con rollback del cobro si la API falla
- [ ] Respetar `stock` y `unique_owned`
- [ ] `/inventory [miembro]` — lista lo que posee un usuario

**Verificación de la fase**
- [ ] Comprar sin saldo suficiente falla sin cobrar
- [ ] Si la asignación de rol falla por jerarquía, la Fe se devuelve
- [ ] No se puede comprar dos veces un ítem con `unique_owned = 1`

---

## Fase 5 — Minijuegos y Utilidades `[ ]`

> **Objetivo:** dar razones para volver cada día.

**Minijuegos (`cogs/games.py`)**
- [ ] Helper compartido de apuesta: valida, cobra y devuelve un contexto de juego
- [ ] `/danmaku_flip <cantidad> <cara|cruz>` — pago 2x
- [ ] `/kappa_slots <cantidad>` — 3 símbolos con multiplicadores calculados a RTP ~95%
- [ ] Documentar el cálculo de probabilidades en un comentario del módulo
- [ ] `/roulette <cantidad> <apuesta>` — color 2x, rango numérico 3x
- [ ] Límites de apuesta (mín. 10 🌸, máx. configurable) y cooldown de 10s

**Utilidades (`cogs/utils.py`)**
- [ ] `/teams [equipos]` — reparto aleatorio y equilibrado del canal de voz
- [ ] `/squad <juego> [hora]` — convocatoria con 3 botones y embed que se edita en vivo
- [ ] View persistente para `/squad` (sobrevive reinicios), autocierre a las 12h
- [ ] `/addquote`, `/quote`, `/quotes` sobre la tabla `quotes`

**Verificación de la fase**
- [ ] Simular 10.000 tiradas de slots y confirmar que el RTP real ronda el objetivo
- [ ] `/teams` falla con mensaje claro si el invocador no está en voz
- [ ] Los botones de `/squad` siguen funcionando tras reiniciar el bot

---

## Fase 6 — Administración `[ ]`

> **Objetivo:** poder operar el bot sin editar código ni la base de datos a mano.

- [ ] `cogs/admin.py` restringido por permisos de servidor
- [ ] `/config set <clave> <valor>` y `/config view` sobre `guild_config`
- [ ] Gestión de la tienda: añadir, editar, deshabilitar ítems
- [ ] `/eco give|take|set` para ajustes manuales de saldo, con registro en `transactions`
- [ ] `/audit <miembro>` — historial de movimientos de Fe
- [ ] Script de backup de la base de datos

---

## Mejoras Futuras (sin fase asignada)

- [ ] Sistema de niveles/rangos con roles automáticos por Fe acumulada
- [ ] Eventos temporales tipo *Incidente de Gensokyo* (multiplicadores durante X horas)
- [ ] Perfil de usuario con tarjeta generada en imagen
- [ ] Ítems `consumable` con efectos reales (multiplicador temporal, protección de racha)
- [ ] Migrar a PostgreSQL si el servidor crece lo suficiente
- [ ] Tests automatizados de la capa `db_manager`

---

## Cuestiones Abiertas

Se resuelven cuando toque, no bloquean nada ahora:

- [ ] Hosting de producción (VPS / Raspberry Pi / servicio gestionado)
- [ ] Frecuencia y destino de los backups
- [ ] Precios reales del catálogo — medir primero el ritmo de generación de Fe tras la Fase 3
- [ ] Lista definitiva de canales excluidos de la Fe por chat
