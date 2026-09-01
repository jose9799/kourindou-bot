# Guía de Estilo de Código — Kourindou Bot

**Versión:** 1.0.0
**Última actualización:** 2026-09-01
**Ámbito:** todo el código Python del proyecto.

Este documento es **normativo**, no una sugerencia. El código que no cumple estas reglas no se
considera terminado. La prosa de este documento está en español, igual que el resto de la
documentación del proyecto; **todos los ejemplos de código están en inglés**, que es como debe
escribirse el código real.

---

## 1. Reglas Fundamentales

Las cuatro reglas que rigen por encima del resto. Todo lo demás en este documento es una
consecuencia práctica de estas:

1. **Todo el código en inglés.** Sin excepciones.
2. **El código debe ser depurable.** Si falla en producción a las 3 de la mañana, los logs
   tienen que bastar para entender qué pasó.
3. **Comentarios escasos y solo técnicos.** El código explica el *qué*; los comentarios existen
   únicamente para el *por qué* no evidente.
4. **Formateo automatizado y estructura consistente.** Nada de estilo negociado a mano.

---

## 2. Idioma

**Todo el código en inglés:** nombres de variables, funciones, clases, módulos, ficheros,
docstrings, comentarios, mensajes de log, mensajes de excepción, nombres de tablas y columnas,
y mensajes de commit.

```python
# ✅ Correcto
async def try_claim_daily(user_id: int, guild_id: int) -> DailyResult:
    """Grant the daily reward if the cooldown has elapsed."""
    logger.info("Daily claimed | user=%s guild=%s amount=%s", user_id, guild_id, amount)
```

```python
# ❌ Incorrecto
async def intentar_reclamar_diario(id_usuario: int) -> ResultadoDiario:
    """Otorga la recompensa diaria si pasó el cooldown."""
    logger.info("Diario reclamado por %s", id_usuario)
```

**Única excepción:** los textos que ve el usuario final en Discord (embeds, respuestas de
comandos, descripciones de comandos) van **en español**, porque el servidor es hispanohablante.
Esos strings se centralizan en un módulo de textos, no se esparcen por la lógica.

```python
# ✅ La lógica en inglés, el texto visible en español y aislado
# strings.py
DAILY_SUCCESS = "🌸 Has ofrendado en el Santuario Hakurei y recibes **{amount}** Puntos de Fe."
DAILY_COOLDOWN = "⛩️ El santuario aún descansa. Vuelve en **{remaining}**."
```

---

## 3. Formateo y Herramientas

**Ruff** hace de formateador y linter. Sustituye a Black, isort y flake8 con una sola
herramienta y una sola configuración.

```bash
pip install ruff
```

Configuración en `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "ASYNC", "S", "SIM", "RUF"]
ignore = ["S101"]  # assert is fine in tests

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S"]

[tool.ruff.format]
quote-style = "double"
```

Los conjuntos de reglas que importan aquí: `ASYNC` detecta llamadas bloqueantes dentro de
corrutinas —el error más frecuente y más difícil de diagnosticar en un bot de Discord—, `S`
(bandit) detecta problemas de seguridad como SQL construido por concatenación, y `B` detecta
bugs reales como los argumentos por defecto mutables.

**Antes de cada commit:**

```bash
ruff format . && ruff check --fix .
```

**Reglas de formato no negociables:**
- Longitud de línea: **100** caracteres.
- Comillas dobles.
- Indentación: 4 espacios, nunca tabuladores.
- Una sentencia por línea.
- Fichero terminado en salto de línea, sin espacios en blanco al final de línea.

---

## 4. Nomenclatura

| Elemento | Convención | Ejemplo |
|----------|-----------|---------|
| Módulos y ficheros | `snake_case` | `db_manager.py` |
| Funciones y variables | `snake_case` | `faith_points`, `get_balance` |
| Clases y Cogs | `PascalCase` | `EconomyCog`, `ShopView` |
| Constantes | `UPPER_SNAKE_CASE` | `DAILY_COOLDOWN_SECONDS` |
| Privado del módulo | prefijo `_` | `_build_embed` |
| Booleanos | prefijo `is_` / `has_` / `can_` | `is_on_cooldown`, `can_afford` |
| Funciones async | verbo, sin prefijo `async_` | `fetch_user`, no `async_fetch_user` |

**Nombres descriptivos, sin abreviar.** El autocompletado existe; la ambigüedad a los seis
meses no se arregla sola.

```python
# ✅
remaining_cooldown_seconds = compute_remaining(last_claim, DAILY_COOLDOWN_SECONDS)

# ❌
rem = calc(lc, DCS)
```

**Nada de números mágicos.** Todo valor de balance vive en `config.py` como constante con
nombre.

```python
# ✅
if elapsed < DAILY_COOLDOWN_SECONDS:

# ❌
if elapsed < 79200:
```

---

## 5. Comentarios y Docstrings

**Regla:** los comentarios explican **por qué**, nunca **qué**. Si necesitas un comentario para
explicar qué hace una línea, el problema es la línea, no la falta de comentario.

```python
# ❌ Ruido. La línea ya lo dice.
# Increment the streak by one
streak += 1

# ❌ Peor: mentirá en cuanto alguien cambie el valor y no el comentario.
# Wait 24 hours
if elapsed < DAILY_COOLDOWN_SECONDS:
```

```python
# ✅ Explica una decisión que el código no puede expresar.
# 22h instead of 24h so the claim window does not drift later each day.
DAILY_COOLDOWN_SECONDS = 22 * 3600

# ✅ Explica un requisito externo no obvio.
# SQLite ships with foreign keys disabled; this must run on every connection.
await db.execute("PRAGMA foreign_keys = ON")
```

**Docstrings:** obligatorios en las funciones públicas de `db_manager.py` y en cualquier
función cuyo contrato no sea evidente por la firma. Una línea imperativa basta. No se
documentan los parámetros obvios ni se replica lo que ya dicen las anotaciones de tipo.

```python
# ✅ Contrato no evidente: hace falta decir que es atómico y qué devuelve al fallar.
async def transfer_faith(sender_id: int, receiver_id: int, guild_id: int, amount: int) -> bool:
    """Move faith between users atomically. Returns False if the sender lacks funds."""

# ❌ Docstring que no aporta nada sobre la firma.
async def get_balance(user_id: int, guild_id: int) -> int:
    """Gets the balance of a user.

    Args:
        user_id: The user id.
        guild_id: The guild id.
    Returns:
        The balance.
    """
```

**Prohibido:** código comentado (para eso está el control de versiones), comentarios
decorativos con líneas de `#####`, y `TODO` sin contexto. Un `TODO` lleva quién y qué falta:
`# TODO(jose): validate role hierarchy before selling the item`.

---

## 6. Depurabilidad

El objetivo es que un fallo en producción sea diagnosticable **solo con los logs**, sin
reproducirlo.

### 6.1. Logging, nunca `print`

```python
import logging

logger = logging.getLogger(__name__)  # one logger per module, named after it
```

`print()` está prohibido fuera de scripts de un solo uso. No tiene niveles, ni timestamp, ni
destino configurable.

### 6.2. Los logs llevan contexto identificable

Un log sin IDs es inútil: no puedes correlacionarlo con nada.

```python
# ✅ Se puede rastrear al usuario, al servidor y a la operación exacta.
logger.info("Purchase completed | user=%s guild=%s item=%s price=%s balance_after=%s",
            user_id, guild_id, item_id, price, new_balance)

# ❌ ¿Quién? ¿Dónde? ¿Qué compró?
logger.info("Purchase completed")
```

Usa **formato con `%s` diferido**, no f-strings: el string no se construye si el nivel de log
está desactivado.

### 6.3. Niveles con criterio

| Nivel | Cuándo |
|-------|--------|
| `DEBUG` | Detalle de flujo interno. Silenciado en producción. |
| `INFO` | Eventos de negocio: compras, transferencias, pagos de Fe, arranque de Cogs. |
| `WARNING` | Situación anómala recuperable: rol no asignable, sesión de voz huérfana. |
| `ERROR` | Fallo de una operación, con `exc_info=True`. |
| `CRITICAL` | El bot no puede seguir operando. |

### 6.4. Excepciones

```python
# ❌ Prohibido. Borra la evidencia del fallo.
try:
    await member.add_roles(role)
except Exception:
    pass

# ❌ Prohibido. Captura demasiado y no dice nada.
except Exception as e:
    logger.error(f"Error: {e}")
```

```python
# ✅ Excepción concreta, contexto completo, traceback preservado.
try:
    await member.add_roles(role, reason="Kourindou shop purchase")
except discord.Forbidden:
    logger.warning(
        "Role assignment denied, check bot hierarchy | guild=%s role=%s user=%s",
        guild_id, role.id, member.id,
    )
    await refund_purchase(member.id, guild_id, price)
    return PurchaseResult.ROLE_ASSIGNMENT_FAILED
except discord.HTTPException:
    logger.exception("Discord API failure during role assignment | user=%s", member.id)
    raise
```

**`logger.exception()`** dentro de un `except` incluye el traceback automáticamente. Úsalo.

**Nunca dejes que un traceback llegue al chat de Discord.** El usuario ve un mensaje genérico;
el traceback completo va al log.

### 6.5. Estado observable

Las operaciones que mueven Fe registran fila en `transactions` **siempre**, sin excepción. Es la
diferencia entre poder responder "¿por qué tengo 40.000 🌸?" y encogerse de hombros.

---

## 7. Estructura del Código

### 7.1. Separación de capas

```
Cog (comandos, validación de entrada, embeds)
  ↓ llama a
db_manager (lógica de dominio, transacciones, SQL)
  ↓ usa
aiosqlite
```

**Los Cogs nunca ejecutan SQL.** Ni una consulta. Si un Cog necesita datos, se añade una
función de dominio en `db_manager.py`.

```python
# ❌ SQL dentro de un Cog.
async with self.bot.db.execute("SELECT faith_points FROM users WHERE user_id = ?", (uid,)):

# ✅ Función de dominio.
balance = await db.get_balance(user_id, guild_id)
```

`db_manager` tampoco devuelve objetos de Discord ni construye embeds. Cada capa habla su propio
idioma.

### 7.2. Tamaño

- **Funciones:** idealmente por debajo de 40 líneas. Una función hace una cosa.
- **Módulos:** por encima de ~400 líneas, dividir. Un Cog gigante es un Cog que hace demasiado.
- **Anidamiento:** máximo 3 niveles. Más que eso pide *early return*.

```python
# ✅ Cláusulas de guarda primero, camino feliz sin anidar.
async def transfer(self, ctx, member: discord.Member, amount: int) -> None:
    if member.bot:
        return await ctx.send(strings.TRANSFER_TO_BOT)
    if member.id == ctx.author.id:
        return await ctx.send(strings.TRANSFER_TO_SELF)
    if amount < 1:
        return await ctx.send(strings.TRANSFER_INVALID_AMOUNT)

    success = await db.transfer_faith(ctx.author.id, member.id, ctx.guild.id, amount)
    ...
```

### 7.3. Imports

Tres bloques separados por línea en blanco, ordenados por Ruff (`I`): librería estándar,
terceros, local. **Imports absolutos siempre**, nunca relativos ni comodines.

```python
import logging
from datetime import UTC, datetime

import discord
from discord.ext import commands, tasks

import config
from database import db_manager
```

### 7.4. Anotaciones de tipo

**Obligatorias** en toda firma de función: parámetros y retorno. Sin `Any` salvo justificación
en comentario.

```python
async def get_leaderboard(guild_id: int, limit: int = 10) -> list[LeaderboardEntry]:
```

Usa sintaxis moderna (`list[int]`, `int | None`), no `List`/`Optional` de `typing`.

Para datos estructurados que cruzan capas, `@dataclass` o `NamedTuple`, nunca diccionarios
sueltos ni tuplas anónimas:

```python
# ✅ El consumidor sabe qué recibe, y el editor lo autocompleta.
@dataclass(frozen=True, slots=True)
class DailyResult:
    granted: bool
    amount: int
    streak: int
    remaining_seconds: int

# ❌ ¿Qué contiene? ¿En qué orden?
return (True, 150, 3, 0)
```

---

## 8. Reglas Asíncronas

**Nunca bloquees el event loop.** Un bot es un único hilo: una llamada bloqueante congela todos
los comandos de todos los usuarios simultáneamente.

```python
# ❌ Congela el bot entero.
import time, requests
time.sleep(5)
response = requests.get(url)

# ✅
import asyncio, aiohttp
await asyncio.sleep(5)
async with session.get(url) as response:
```

- Nada de `sqlite3` síncrono. Solo `aiosqlite`.
- Trabajo pesado de CPU → `asyncio.to_thread()`.
- Toda corrutina se espera. Un `await` olvidado no da error, simplemente no hace nada:
  Ruff lo detecta, respeta el aviso.
- Las tareas de fondo usan `@tasks.loop` de discord.py, no `asyncio.create_task` a pelo, y
  llevan `@loop.before_loop` con `await self.bot.wait_until_ready()`.

---

## 9. Reglas Específicas de discord.py

- **Comandos híbridos** (`@commands.hybrid_command`) por defecto, según la decisión D2 de
  `specs.md`.
- **Defer si tarda:** una interacción caduca en 3 segundos. Si la operación puede tardar más,
  `await interaction.response.defer()` primero.
- **Errores en efímero:** los mensajes de error van con `ephemeral=True`; no ensucian el canal.
- **Views con timeout:** toda `discord.ui.View` define `timeout` y deshabilita sus componentes
  en `on_timeout`. Las views que deben sobrevivir reinicios llevan `timeout=None` y `custom_id`
  fijo, y se registran en `setup_hook`.
- **Validación de interacción:** una view solo responde a quien invocó el comando, salvo que
  sea intencionadamente pública (como `/squad`). Se implementa en `interaction_check`.
- **Embeds construidos en helpers**, no inline dentro del comando. El comando orquesta; el
  helper presenta.
- **Cog = un dominio.** Si un Cog necesita lógica de otro, esa lógica pertenece a `db_manager`
  o a un módulo compartido, no se importan Cogs entre sí.

---

## 10. Base de Datos

**Consultas siempre parametrizadas.** Sin excepciones, aunque el valor "venga de dentro".

```python
# ❌ Inyección SQL. Ruff (regla S) lo marca.
await db.execute(f"SELECT * FROM users WHERE user_id = {user_id}")

# ✅
await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
```

**Toda operación que mueve saldo es atómica.** Nada de leer, decidir en Python y luego escribir:
dos comandos concurrentes gastarían el mismo saldo dos veces.

```python
# ❌ Condición de carrera.
balance = await get_balance(user_id, guild_id)
if balance >= amount:
    await set_balance(user_id, guild_id, balance - amount)

# ✅ La condición vive en el UPDATE; rowcount dice si se aplicó.
cursor = await db.execute(
    "UPDATE users SET faith_points = faith_points - ? "
    "WHERE user_id = ? AND guild_id = ? AND faith_points >= ?",
    (amount, user_id, guild_id, amount),
)
if cursor.rowcount == 0:
    return TransferResult.INSUFFICIENT_FUNDS
```

- SQL en mayúsculas para las palabras clave, sobre varias líneas si no cabe en 100 caracteres.
- Timestamps como enteros epoch UTC. Un único helper `utcnow_ts()` los genera; nadie llama a
  `datetime.now()` por su cuenta.
- Los cambios de esquema van a `schema.sql`, que debe ser idempotente
  (`CREATE TABLE IF NOT EXISTS`).

---

## 11. Configuración y Secretos

- **Ningún secreto en el código.** Tokens, IDs e rutas salen de `.env` vía `config.py`.
- `.env` está en `.gitignore`. `.env.example` se commitea con las claves vacías.
- `config.py` **falla al arrancar** si falta una variable obligatoria, con mensaje explícito. Un
  bot que arranca a medias y falla dos horas después es peor que uno que no arranca.
- Ningún ID de servidor, canal o rol hardcodeado en la lógica: van a `config.py` o a
  `guild_config`.

---

## 12. Control de Versiones

**Commits en inglés**, formato *Conventional Commits*:

```
feat(economy): add daily streak bonus with 100% cap
fix(voice): prevent faith payout when user is alone in channel
refactor(db): extract transaction logging into helper
docs(specs): close currency and command-type decisions
chore(deps): bump discord.py to 2.4.0
```

- Un commit = un cambio lógico coherente. Nada de "varios arreglos".
- No se commitea código que no pasa `ruff check`.
- No se commitean `.db`, `.env`, `__pycache__/` ni logs.

---

## 13. Checklist de "Production Ready"

Una tarea del roadmap no se marca como hecha hasta que cumple **todo** esto:

- [ ] `ruff format` y `ruff check` pasan sin avisos
- [ ] Todas las firmas llevan anotaciones de tipo
- [ ] Sin `print()`, sin código comentado, sin `TODO` anónimos
- [ ] Los caminos de error registran log con contexto identificable (user, guild, operación)
- [ ] Ninguna excepción genérica silenciada; ningún traceback expuesto al usuario
- [ ] Las operaciones sobre saldo son atómicas y quedan en `transactions`
- [ ] Ninguna llamada bloqueante dentro de una corrutina
- [ ] Los valores configurables están en `config.py`, no incrustados en la lógica
- [ ] Probado manualmente en un servidor real, incluyendo el camino de fallo
- [ ] Comportamiento verificado tras reiniciar el bot, si la función mantiene estado
