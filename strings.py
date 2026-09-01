"""User facing text, in Spanish.

Kept out of the logic so the code stays in English and the wording can be tuned
without touching behaviour.
"""

# --- generic ---------------------------------------------------------------
ERROR_GENERIC = "⚠️ Algo salió mal. El incidente ha quedado registrado."
ERROR_GUILD_ONLY = "⛩️ Este comando solo funciona dentro del servidor."
ERROR_MISSING_PERMS = "🚫 No tienes permiso para usar este comando."
ERROR_COOLDOWN = "⏳ Demasiado rápido. Inténtalo de nuevo en **{remaining}**."
ERROR_BAD_ARGUMENT = "❓ Argumentos inválidos. Revisa el uso del comando."
NOT_YOUR_MENU = "🚫 Este menú pertenece a otra persona. Usa el comando tú mismo."

# --- economy ---------------------------------------------------------------
DAILY_TITLE = "⛩️ Ofrenda al Santuario Hakurei"
DAILY_SUCCESS = "Reimu acepta tu ofrenda y recibes **{amount}** {currency}."
DAILY_STREAK = "Racha de **{streak}** días · bono de **+{bonus}** {currency}"
DAILY_COOLDOWN = "El santuario aún descansa. Vuelve en **{remaining}**."
BALANCE_TITLE = "🌸 Puntos de Fe"
BALANCE_LINE = "**{amount}** {currency}"
BALANCE_RANK = "Puesto **#{rank}** del servidor"
BALANCE_VOICE = "**{minutes}** minutos en los canales de voz"

TRANSFER_TO_SELF = "🌀 No puedes donarte Fe a ti mismo."
TRANSFER_TO_BOT = "🤖 Los youkai mecánicos no aceptan ofrendas."
TRANSFER_INVALID_AMOUNT = "❌ La cantidad debe ser un número mayor que **{minimum}**."
TRANSFER_INSUFFICIENT = "💸 No tienes suficiente Fe. Tu saldo es **{balance}** {currency}."
TRANSFER_TOO_YOUNG = "🕰️ Tu cuenta es demasiado reciente para donar. Espera **{remaining}**."
TRANSFER_SUCCESS = "🎁 Has donado **{amount}** {currency} a {receiver}."
TRANSFER_FEE_NOTE = "Comisión del santuario: **{fee}** {currency}."

LEADERBOARD_TITLE = "🏆 Los más devotos de Gensokyo"
LEADERBOARD_EMPTY = "Todavía nadie ha acumulado Fe en este servidor."
LEADERBOARD_YOU = "Tu puesto: **#{rank}** con **{amount}** {currency}"

# --- shop ------------------------------------------------------------------
SHOP_TITLE = "🏮 Tienda Kourindou"
SHOP_DESCRIPTION = "Rinnosuke te observa en silencio. Elige un artículo del catálogo."
SHOP_EMPTY = "El almacén está vacío. Un administrador debe añadir artículos."
SHOP_FOOTER = "Tu saldo: {balance} {currency}"
SHOP_SELECT_PLACEHOLDER = "Selecciona un artículo..."
SHOP_ITEM_PRICE = "Precio: **{price}** {currency}"
SHOP_ITEM_STOCK = "Quedan **{stock}** unidades"
SHOP_CONFIRM = "¿Confirmas la compra de **{name}** por **{price}** {currency}?"
SHOP_BUY = "Comprar"
SHOP_CANCEL = "Cancelar"
SHOP_CANCELLED = "🚪 Compra cancelada."
SHOP_PURCHASE_OK = "✅ Has adquirido **{name}**. Rinnosuke anota la venta en su libro."
SHOP_INSUFFICIENT = "💸 Te faltan **{missing}** {currency} para llevarte eso."
SHOP_ALREADY_OWNED = "📦 Ya posees **{name}**."
SHOP_OUT_OF_STOCK = "📭 **{name}** está agotado."
SHOP_UNAVAILABLE = "🚫 Ese artículo ya no está a la venta."
SHOP_ROLE_FAILED = (
    "⚠️ No pude entregarte el rol y te he devuelto la Fe. "
    "Avisa a un administrador: revisar la jerarquía de roles del bot."
)

SHOP_KIND_LABELS = {
    "role": "🎭 Roles de facción",
    "perk": "🔑 Permisos",
    "cosmetic": "✨ Recompensas del servidor",
    "consumable": "🧪 Consumibles",
}
SHOP_CATEGORY_PLACEHOLDER = "Categoría..."
SHOP_TRUNCATED = "Mostrando los primeros {shown} de {total} artículos."

INVENTORY_TITLE = "🎒 Inventario de {user}"
INVENTORY_EMPTY = "No posees nada todavía. Pásate por la Tienda Kourindou."

# --- games -----------------------------------------------------------------
BET_INVALID = "❌ La apuesta debe estar entre **{minimum}** y **{maximum}** {currency}."
BET_INSUFFICIENT = "💸 No tienes suficiente Fe para esa apuesta."

FLIP_TITLE = "🎴 Duelo Danmaku"
FLIP_WIN = "Sale **{result}**. Ganas **{amount}** {currency}."
FLIP_LOSS = "Sale **{result}**. Pierdes **{amount}** {currency}."

SLOTS_TITLE = "🔧 Tragaperras de Nitori"
SLOTS_JACKPOT = "¡Triple **{symbol}**! Ganas **{amount}** {currency} (x{multiplier})."
SLOTS_PAIR = "Pareja de **{symbol}**. Recuperas tu apuesta."
SLOTS_LOSS = "Nada. La máquina de Nitori se traga **{amount}** {currency}."

ROULETTE_TITLE = "🎡 Ruleta de Gensokyo"
ROULETTE_RESULT = "La bola cae en **{number}** ({color})."
ROULETTE_WIN = "Ganas **{amount}** {currency}."
ROULETTE_LOSS = "Pierdes **{amount}** {currency}."
ROULETTE_BAD_BET = (
    "❓ Apuesta no válida. Usa `rojo`, `negro`, o un rango: `1-12`, `13-24`, `25-36`."
)

BALANCE_AFTER = "Saldo: **{balance}** {currency}"

# --- utils -----------------------------------------------------------------
TEAMS_TITLE = "⚔️ Reparto de equipos"
TEAMS_NOT_IN_VOICE = "🔇 Tienes que estar en un canal de voz para usar esto."
TEAMS_NOT_ENOUGH = "👥 Hacen falta al menos **{needed}** miembros en el canal."
TEAMS_TOO_MANY = "❌ El número de equipos debe estar entre 2 y {maximum}."
TEAMS_TEAM_NAME = "Equipo {index}"

SQUAD_TITLE = "📣 Convocatoria: {game}"
SQUAD_HOST = "Convoca {host}"
SQUAD_TIME = "🕒 Hora: **{time}**"
SQUAD_IN = "✅ Me sumo"
SQUAD_LATE = "🕗 Llego tarde"
SQUAD_OUT = "❌ No puedo"
SQUAD_LIST_IN = "✅ Se apuntan ({count})"
SQUAD_LIST_LATE = "🕗 Llegan tarde ({count})"
SQUAD_LIST_OUT = "❌ No pueden ({count})"
SQUAD_NOBODY = "*Nadie todavía*"
SQUAD_CLOSED = "🔒 Esta convocatoria ya está cerrada."
SQUAD_REGISTERED = "Respuesta registrada."

QUOTE_TITLE = "💬 Frase de Gensokyo"
QUOTE_ADDED = "✅ Frase registrada con el número **#{quote_id}**."
QUOTE_EMPTY = "📭 No hay frases registradas todavía. Usa `/addquote`."
QUOTE_TOO_LONG = "❌ La frase no puede superar los **{maximum}** caracteres."
QUOTE_LIST_TITLE = "💬 Frases registradas"
QUOTE_DELETED = "🗑️ Frase **#{quote_id}** eliminada."
QUOTE_NOT_FOUND = "❓ No existe una frase con ese número."

# --- admin -----------------------------------------------------------------
ADMIN_CONFIG_TITLE = "⚙️ Configuración del servidor"
ADMIN_CONFIG_SET = "✅ `{key}` establecido a **{value}**."
ADMIN_CONFIG_CLEARED = "♻️ `{key}` vuelve a su valor por defecto."
ADMIN_CONFIG_UNKNOWN = "❓ Clave desconocida. Claves válidas:\n{keys}"
ADMIN_CONFIG_BAD_VALUE = "❌ El valor debe ser un número entero."
ADMIN_ITEM_CREATED = "✅ Artículo **{name}** creado con el id **{item_id}**."
ADMIN_ITEM_DUPLICATE = "❌ Ya existe un artículo con ese nombre."
ADMIN_ITEM_DELETED = "🗑️ Artículo **{item_id}** eliminado."
ADMIN_ITEM_NOT_FOUND = "❓ No existe un artículo con ese id en este servidor."
ADMIN_ITEM_TOGGLED = "✅ Artículo **{item_id}** ahora está **{state}**."
ADMIN_ROLE_TOO_HIGH = (
    "⚠️ Ese rol está por encima del rol del bot en la jerarquía: no podría asignarlo. "
    "Mueve el rol del bot más arriba antes de venderlo."
)
ADMIN_ECO_DONE = "✅ Saldo de {user} actualizado a **{balance}** {currency}."
ADMIN_AUDIT_TITLE = "🧾 Movimientos de {user}"
ADMIN_AUDIT_EMPTY = "Sin movimientos registrados."
