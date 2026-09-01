# Especificaciones Técnicas del Proyecto: Bot de Discord - Kourindou Bot (Discord.py)

**Servidor:** Gensokyolis:Re  
**Temática:** Touhou Project  
**Versión:** 1.1.0 (Touhou Themed)  
**Estado:** Fase de Diseño / Iteración Inicial  
**Entorno de Ejecución:** Python 3.10+ / `discord.py` v2.x  
**Arquitectura recomendada:** Asyncio + Cogs + `aiosqlite`  

---

## 1. Visión General del Proyecto
**Kourindou Bot** es un bot personalizado diseñado para el servidor **Gensokyolis:Re**. Inspirado en el lore y universo de *Touhou Project* (nombrado en honor a la tienda de antigüedades Kourindou de Rinnosuke Morichika), el bot integra un sistema de **economía basada en Fe y Poder (P-Items), recompensas por actividad en voz y chat, minijuegos de azar/Danmaku y utilidades para partidas multijugador**.

---

## 2. Terminoría y Estética de Touhou (Gensokyo Economy)
* **Moneda Principal:** Fe / Puntos de Fe (🌸 `Faith Points`) o P-Items (🔴 `Power Points`).
* **Recompensa Diaria (`/daily`):** *Ofrenda al Santuario Hakurei* (Hakurei Shrine Donation).
* **Tienda (`/shop`):** *Tienda Kourindou* (Venta de artefactos, roles de facciones de Gensokyo y permisos VIP).
* **Minijuegos (`/games`):** *Duelos Danmaku / Apuestas de Gensokyo*.

---

## 3. Arquitectura del Sistema

```
kourindou_bot/
│
├── main.py                # Punto de entrada principal, carga de Cogs y Sync de Slash Commands
├── config.py              # Configuración de variables de entorno (TOKENS, DB PATH)
├── database/
│   ├── schema.sql         # Esquema DDL para la base de datos de Gensokyo
│   └── db_manager.py      # Controladores asíncronos para operaciones CRUD (aiosqlite)
│
├── cogs/
│   ├── economy.py         # Comandos de Fe (!daily, !faith, !pay)
│   ├── shop.py            # Tienda Kourindou e inventario de artefactos (UI Views)
│   ├── voice.py           # Recompensas de Fe por tiempo en canales de voz
│   ├── games.py           # Minijuegos y duelos (slots, ruleta, Danmaku flip)
│   └── utils.py           # Mezclador de equipos para partidas (!teams), convocatorias (!squad), citas (!quote)
│
└── requirements.txt       # Dependencias del proyecto
```

---

## 4. Módulos y Funcionalidades Requeridas

### 4.1. Sistema de Economía de Gensokyo (`cogs/economy.py`)
* **Modelo de Datos (SQLite):**
  * Tabla `users`: `user_id` (PK, INTEGER), `guild_id` (INTEGER), `faith_points` (INTEGER), `last_daily` (TIMESTAMP), `voice_minutes` (INTEGER).
  * Tabla `inventory`: `item_id` (PK), `user_id` (FK), `item_name` (TEXT), `acquired_at` (TIMESTAMP).
* **Comandos:**
  * `/daily` (Ofrenda al Santuario): Otorga un número configurable de Puntos de Fe (ej. 100 🌸) con un *cooldown* de 24 horas.
  * `/faith` o `/balance` (Consulta de Fe): Muestra los Puntos de Fe acumulados por el usuario o un miembro mencionado.
  * `/transfer` o `/pay` (Donación): Transfiere Puntos de Fe entre miembros del servidor con validación de saldo.

### 4.2. Recompensas por Actividad y Tiempo en Gensokyo (`cogs/voice.py`)
* **Puntos de Fe por Chat:** Otorga un rango aleatorio de Fe (ej. 5 a 15 🌸) por cada mensaje enviado en el servidor, con un *cooldown* de 60 segundos para prevenir spam.
* **Puntos de Fe por Voz:** Utiliza el evento `on_voice_state_update` para registrar la permanencia en canales de voz y otorgar Fe proporcional al tiempo en llamada (ej. 2 🌸 por minuto).

### 4.3. Tienda Kourindou e Interfaz Interactiva (`cogs/shop.py`)
* **Catálogo de Tienda (Inspirado en Touhou):**
  * **Roles Temáticos:** Residentes de la Mansión del Diablo Escarlata, Tengu de la Montaña Youkai, Hada del Lago, Hermitaños, etc.
  * **Permisos Especiales:** Acceso a canales VIP, permiso para adjuntar imágenes/archivos o usar Soundboard en canales de voz.
  * **Recompensas del Servidor:** Definir el juego de la noche, elegir el avatar/icono temporal del servidor.
* **UI/UX:** Implementación mediante `discord.ui.Select` (Dropdown) y `discord.ui.Button` con confirmación interactiva de compra.

### 4.4. Minijuegos de Apuestas / Duelos (`cogs/games.py`)
* **`/danmaku_flip` (Cara o Cruz):** Apuesta de Puntos de Fe estilo duelo rápido.
* **`/kappa_slots` (Tragaperras de Nitori):** Generación de 3 símbolos temáticos de Touhou con multiplicadores de recompensa.
* **`/roulette` (Ruleta de Gensokyo):** Apuestas a color o rango numérico.

### 4.5. Utilidad y Convivencia para Gensokyolis:Re (`cogs/utils.py`)
* **`/teams`:** Selecciona a los miembros activos en un canal de voz y los divide de forma aleatoria en 2 equipos equilibrados para jugar.
* **`/squad`:** Crea una convocatoria para organizar partidas con botones de interacción ("Me sumo", "Llego tarde", "No puedo").
* **`/quote`:** Registra y muestra frases célebres o fuera de contexto del servidor (`!addquote`, `!quote`).

---

## 5. Requisitos Técnicos y Dependencias

```txt
discord.py>=2.3.0
aiosqlite>=0.19.0
python-dotenv>=1.0.0
```

---

## 6. Roadmap de Iteración y Desarrollo

1. **Fase 1 (Estructura y BD de Gensokyo):** Configurar la plantilla base con `commands.Bot`, la base de datos `aiosqlite` y la tabla `users` con campo `faith_points`.
2. **Fase 2 (Economía de Fe):** Programar `/daily` (Ofrenda al Santuario), `/faith` y `/transfer`.
3. **Fase 3 (Actividad en Voz/Texto):** Implementar entrega de Fe por `on_message` y `on_voice_state_update`.
4. **Fase 4 (Tienda Kourindou UI):** Diseñar el menú interactivo con `discord.ui.View` y roles temáticos de Touhou.
5. **Fase 5 (Minijuegos y Utilidades):** Añadir los minijuegos, `/teams` y `/squad`.
