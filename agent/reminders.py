# agent/reminders.py — Recordatorios automáticos de 30 días
# Generado por AgentKit

"""
Revisa qué clientes no le escriben al agente hace 30 días y les manda
un recordatorio por WhatsApp para que vuelvan a agendar un corte.
"""

import logging
import yaml

from agent.memory import obtener_clientes_para_recordar, marcar_recordatorio_enviado
from agent.providers import obtener_proveedor

logger = logging.getLogger("agentkit")

MENSAJE_POR_DEFECTO = "¡Hola! Ya pasó un tiempo desde tu última visita. ¿Vamos agendando un corte?"


def cargar_mensaje_recordatorio() -> str:
    """Lee el texto del recordatorio desde config/prompts.yaml."""
    try:
        with open("config/prompts.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        return config.get("recordatorio_message", MENSAJE_POR_DEFECTO)
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return MENSAJE_POR_DEFECTO


async def ejecutar_recordatorios():
    """Manda el recordatorio de 30 días a los clientes que correspondan."""
    proveedor = obtener_proveedor()
    mensaje = cargar_mensaje_recordatorio()
    candidatos = await obtener_clientes_para_recordar(dias=30)

    logger.info(f"Recordatorios: {len(candidatos)} cliente(s) a contactar")

    for cliente in candidatos:
        telefono = cliente["telefono"]
        enviado = await proveedor.enviar_mensaje(telefono, mensaje)
        if enviado:
            await marcar_recordatorio_enviado(telefono, cliente["ultimo_mensaje"])
            logger.info(f"Recordatorio enviado a {telefono}")
        else:
            logger.warning(f"No se pudo enviar el recordatorio a {telefono}")
