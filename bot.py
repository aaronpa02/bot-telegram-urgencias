# bot.py
import os
import calendar
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

# -------------------------
# CARGAR .env
# -------------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
COORD_CHAT_ID = int(os.getenv("COORD_CHAT_ID"))

# -------------------------
# ESTADOS
# -------------------------
(
    STATE_UNIT,        # seleccionar unidad (A-5 .. A-17)
    STATE_MONTH,       # seleccionar mes
    STATE_DAY,         # seleccionar dia
    STATE_HOUR,        # seleccionar hora
    STATE_MINUTE,      # seleccionar minuto
    STATE_EMER_NUM,    # número de emergencia
    STATE_ADDRESS,     # dirección
    STATE_PATIENT,     # nombre paciente
    STATE_DOC,         # documento
    STATE_ASSIST,      # asistencia
    STATE_DEST,        # destino
) = range(11)

# almacenamiento temporal por usuario
user_data = {}

# helpers para crear teclados
def chunked(lst, n):
    """Divide lista en filas de n elementos."""
    return [lst[i : i + n] for i in range(0, len(lst), n)]

def month_buttons():
    months = [
        ("Ene", 1), ("Feb", 2), ("Mar", 3), ("Abr", 4),
        ("May", 5), ("Jun", 6), ("Jul", 7), ("Ago", 8),
        ("Sep", 9), ("Oct", 10), ("Nov", 11), ("Dic", 12),
    ]
    kb = [[InlineKeyboardButton(name, callback_data=f"MON_{num}")] for name, num in months]
    return InlineKeyboardMarkup(chunked([InlineKeyboardButton(name, callback_data=f"MON_{num}") for name, num in months], 4))

def day_buttons(year, month):
    _, ndays = calendar.monthrange(year, month)
    buttons = [InlineKeyboardButton(str(d), callback_data=f"DAY_{d}") for d in range(1, ndays + 1)]
    # filas de 7 (estilo calendario)
    rows = chunked(buttons, 7)
    return InlineKeyboardMarkup(rows)

def hour_buttons():
    buttons = [InlineKeyboardButton(f"{h:02d}", callback_data=f"H_{h}") for h in range(24)]
    rows = chunked(buttons, 6)  # 6 por fila -> 4 filas
    return InlineKeyboardMarkup(rows)

def minute_buttons():
    buttons = [InlineKeyboardButton(f"{m:02d}", callback_data=f"M_{m}") for m in range(60)]
    rows = chunked(buttons, 6)  # 10 filas x 6 = 60
    return InlineKeyboardMarkup(rows)

# -------------------------
# HANDLERS
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚨 Enviar aviso", callback_data="NEW_AV")]])
    await update.message.reply_text("👋 Bienvenido. Pulsa para crear un aviso:", reply_markup=kb)

# inicio flujo
async def begin_aviso_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    # mostrar unidades A-5 .. A-17 en filas de 4
    units = [InlineKeyboardButton(f"A-{i}", callback_data=f"U_{i}") for i in range(5, 18)]
    kb = InlineKeyboardMarkup(chunked(units, 4))
    await q.edit_message_text("📟 Selecciona tu unidad:", reply_markup=kb)
    return STATE_UNIT

# unidad seleccionada -> elegir mes
async def unit_selected_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    unit_raw = q.data  # "U_7"
    _, num = unit_raw.split("_")
    unidad = f"A-{num}"
    user_data[user.id] = {"unidad": unidad}
    # mostrar meses (año actual solo)
    kb = month_buttons()
    await q.edit_message_text(f"🟩 Unidad: {unidad}\n\n📅 Selecciona el mes (año {datetime.now().year}):", reply_markup=kb)
    return STATE_MONTH

# mes seleccionado -> mostrar dias del mes
async def month_selected_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    _, mon = q.data.split("_")
    month = int(mon)
    year = datetime.now().year
    user_data.setdefault(user.id, {})["month"] = month
    user_data[user.id]["year"] = year
    # mostrar dias
    kb = day_buttons(year, month)
    await q.edit_message_text(f"📅 Mes seleccionado: {calendar.month_name[month]} {year}\n\nSelecciona el día:", reply_markup=kb)
    return STATE_DAY

# dia seleccionado -> elegir hora
async def day_selected_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    _, d = q.data.split("_")
    day = int(d)
    user_data.setdefault(user.id, {})["day"] = day
    kb = hour_buttons()
    await q.edit_message_text(f"📅 Día seleccionado: {day}/{user_data[user.id]['month']}/{user_data[user.id]['year']}\n\n🕒 Selecciona la HORA (00-23):", reply_markup=kb)
    return STATE_HOUR

# hora seleccionada -> elegir minuto
async def hour_selected_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    _, h = q.data.split("_")
    hour = int(h)
    user_data.setdefault(user.id, {})["hour"] = hour
    kb = minute_buttons()
    await q.edit_message_text(f"🕒 Hora seleccionada: {hour:02d}\n\n⏱ Ahora selecciona los MINUTOS (00-59):", reply_markup=kb)
    return STATE_MINUTE

# minuto seleccionado -> continuar formulario (número emergencia)
async def minute_selected_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    _, m = q.data.split("_")
    minute = int(m)
    user_data.setdefault(user.id, {})["minute"] = minute

    # Formar fecha final
    data = user_data[user.id]
    year = data["year"]
    month = data["month"]
    day = data["day"]
    hour = data["hour"]
    minute = data["minute"]
    fecha_hora = f"{day:02d}/{month:02d}/{year} {hour:02d}:{minute:02d}"
    data["fecha_hora"] = fecha_hora

    # Confirmación y paso siguiente
    await q.edit_message_text(f"📅 Fecha y hora seleccionadas: *{fecha_hora}*\n\n📞 Ahora introduce el NÚMERO DE EMERGENCIA:",
                              parse_mode="Markdown")
    return STATE_EMER_NUM

# mensaje: número emergencia
async def emerg_num_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    user_data.setdefault(uid, {})["numero_emergencia"] = update.message.text
    await update.message.reply_text("📍 Introduce la DIRECCIÓN del aviso:")
    return STATE_ADDRESS

# dirección
async def address_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    user_data[uid]["direccion"] = update.message.text
    await update.message.reply_text("👤 Nombre y apellidos del paciente:")
    return STATE_PATIENT

# paciente
async def patient_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    user_data[uid]["paciente"] = update.message.text
    await update.message.reply_text("🪪 Documento (SIP o DNI):")
    return STATE_DOC

# documento
async def doc_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    user_data[uid]["documento"] = update.message.text
    await update.message.reply_text("💊 Describe brevemente la ASISTENCIA realizada:")
    return STATE_ASSIST

# asistencia
async def assist_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    user_data[uid]["asistencia"] = update.message.text
    await update.message.reply_text("🏥 Introduce el DESTINO del paciente:")
    return STATE_DEST

# destino -> enviar aviso
async def dest_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    user_data[uid]["destino"] = update.message.text

    d = user_data[uid]
    fecha_hora = d.get("fecha_hora", "—")
    texto = (
        f"🚨 *AVISO RECIBIDO*\n"
        f"🚑 Unidad: {d.get('unidad','—')}\n"
        f"📅 Fecha y hora: {fecha_hora}\n"
        f"📞 Emergencia: {d.get('numero_emergencia','—')}\n"
        f"📍 Dirección: {d.get('direccion','—')}\n"
        f"👤 Paciente: {d.get('paciente','—')} ({d.get('documento','—')})\n"
        f"💊 Asistencia: {d.get('asistencia','—')}\n"
        f"🏥 Destino: {d.get('destino','—')}"
    )

    # enviar al chat de coordinación
    try:
        await context.bot.send_message(chat_id=COORD_CHAT_ID, text=texto, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error al enviar al centro de coordinación: {e}")
        # no se borra user_data para poder reintentar
        return ConversationHandler.END

    # confirmar al usuario y ofrecer nuevo aviso
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚨 Enviar nuevo aviso", callback_data="NEW_AV")]])
    await update.message.reply_text("✅ Aviso enviado correctamente al centro de coordinación.", reply_markup=kb)

    # limpiar datos del usuario
    user_data.pop(uid, None)
    return ConversationHandler.END

# cancelar
async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data.pop(uid, None)
    await update.message.reply_text("❌ Aviso cancelado.")
    return ConversationHandler.END

# -------------------------
# MAIN
# -------------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(begin_aviso_cb, pattern="^NEW_AV$")],
        states={
            STATE_UNIT: [CallbackQueryHandler(unit_selected_cb, pattern="^U_")],
            STATE_MONTH: [CallbackQueryHandler(month_selected_cb, pattern="^MON_")],
            STATE_DAY: [CallbackQueryHandler(day_selected_cb, pattern="^DAY_")],
            STATE_HOUR: [CallbackQueryHandler(hour_selected_cb, pattern="^H_")],
            STATE_MINUTE: [CallbackQueryHandler(minute_selected_cb, pattern="^M_")],
            STATE_EMER_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, emerg_num_msg)],
            STATE_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_msg)],
            STATE_PATIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, patient_msg)],
            STATE_DOC: [MessageHandler(filters.TEXT & ~filters.COMMAND, doc_msg)],
            STATE_ASSIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, assist_msg)],
            STATE_DEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, dest_msg)],
        },
        fallbacks=[CommandHandler("cancelar", cancel_cmd)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    print("✅ Bot iniciado correctamente. Esperando avisos...")
    app.run_polling()


if __name__ == "__main__":
    main()
