# agent/tools.py — Herramientas del agente
# Generado por AgentKit

"""
Herramientas específicas del negocio: Roma Barber Club.
Casos de uso: preguntas frecuentes + agendar citas.
"""

import os
import sqlite3
import yaml
import logging
from datetime import datetime

logger = logging.getLogger("agentkit")

CITAS_DB = "citas.db"


def cargar_info_negocio() -> dict:
    """Carga la información del negocio desde business.yaml."""
    try:
        with open("config/business.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config/business.yaml no encontrado")
        return {}


def obtener_horario() -> dict:
    """Retorna el horario de atención del negocio."""
    info = cargar_info_negocio()
    return {
        "horario": info.get("negocio", {}).get("horario", "No disponible"),
        "esta_abierto": True,  # TODO: calcular según hora actual y horario
    }


def buscar_en_knowledge(consulta: str) -> str:
    """
    Busca información relevante en los archivos de /knowledge.
    Retorna el contenido más relevante encontrado.
    """
    resultados = []
    knowledge_dir = "knowledge"

    if not os.path.exists(knowledge_dir):
        return "No hay archivos de conocimiento disponibles."

    for archivo in os.listdir(knowledge_dir):
        ruta = os.path.join(knowledge_dir, archivo)
        if archivo.startswith(".") or not os.path.isfile(ruta):
            continue
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
                # Búsqueda simple por coincidencia de texto
                if consulta.lower() in contenido.lower():
                    resultados.append(f"[{archivo}]: {contenido[:500]}")
        except (UnicodeDecodeError, IOError):
            continue

    if resultados:
        return "\n---\n".join(resultados)
    return "No encontré información específica sobre eso en mis archivos."


def _conectar_citas() -> sqlite3.Connection:
    """Abre conexión a la base de citas y crea la tabla si no existe."""
    conn = sqlite3.connect(CITAS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS citas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telefono TEXT NOT NULL,
            servicio TEXT,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            estado TEXT DEFAULT 'confirmada',
            creado_en TEXT
        )
    """)
    return conn


def reservar_cita(telefono: str, fecha: str, hora: str, servicio: str = "") -> dict:
    """
    Agenda una cita para el cliente.

    Args:
        telefono: Número de teléfono del cliente
        fecha: Fecha de la cita (ej: "2026-07-25")
        hora: Hora de la cita (ej: "18:00")
        servicio: Servicio solicitado (ej: "corte + barba")

    Returns:
        Diccionario con el id de la cita creada
    """
    conn = _conectar_citas()
    cursor = conn.execute(
        "INSERT INTO citas (telefono, servicio, fecha, hora, creado_en) VALUES (?, ?, ?, ?, ?)",
        (telefono, servicio, fecha, hora, datetime.utcnow().isoformat()),
    )
    conn.commit()
    cita_id = cursor.lastrowid
    conn.close()
    logger.info(f"Cita #{cita_id} agendada para {telefono} el {fecha} a las {hora}")
    return {"cita_id": cita_id, "telefono": telefono, "fecha": fecha, "hora": hora, "servicio": servicio}


def obtener_citas(telefono: str) -> list[dict]:
    """Retorna las citas activas de un cliente."""
    conn = _conectar_citas()
    filas = conn.execute(
        "SELECT id, servicio, fecha, hora, estado FROM citas WHERE telefono = ? AND estado != 'cancelada'",
        (telefono,),
    ).fetchall()
    conn.close()
    return [
        {"cita_id": f[0], "servicio": f[1], "fecha": f[2], "hora": f[3], "estado": f[4]}
        for f in filas
    ]


def cancelar_cita(cita_id: int) -> bool:
    """Cancela una cita existente."""
    conn = _conectar_citas()
    conn.execute("UPDATE citas SET estado = 'cancelada' WHERE id = ?", (cita_id,))
    conn.commit()
    conn.close()
    logger.info(f"Cita #{cita_id} cancelada")
    return True
