# agent/memory.py — Memoria de conversaciones con SQLite
# Generado por AgentKit

"""
Sistema de memoria del agente. Guarda el historial de conversaciones
por número de teléfono usando SQLite (local) o PostgreSQL (producción).
"""

import os
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, select, Integer, func
from dotenv import load_dotenv

load_dotenv()

# Configuración de base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentkit.db")

# Si es PostgreSQL en producción, ajustar el esquema de URL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Mensaje(Base):
    """Modelo de mensaje en la base de datos."""
    __tablename__ = "mensajes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    role: Mapped[str] = mapped_column(String(20))  # "user" o "assistant"
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Recordatorio(Base):
    """Registra el último recordatorio de 30 días enviado a cada cliente."""
    __tablename__ = "recordatorios"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    ultimo_mensaje_cliente: Mapped[datetime] = mapped_column(DateTime)
    enviado_en: Mapped[datetime] = mapped_column(DateTime)


async def inicializar_db():
    """Crea las tablas si no existen."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def guardar_mensaje(telefono: str, role: str, content: str):
    """Guarda un mensaje en el historial de conversación."""
    async with async_session() as session:
        mensaje = Mensaje(
            telefono=telefono,
            role=role,
            content=content,
            timestamp=datetime.utcnow()
        )
        session.add(mensaje)
        await session.commit()


async def obtener_historial(telefono: str, limite: int = 20) -> list[dict]:
    """
    Recupera los últimos N mensajes de una conversación.

    Args:
        telefono: Número de teléfono del cliente
        limite: Máximo de mensajes a recuperar (default: 20)

    Returns:
        Lista de diccionarios con role y content
    """
    async with async_session() as session:
        query = (
            select(Mensaje)
            .where(Mensaje.telefono == telefono)
            .order_by(Mensaje.timestamp.desc())
            .limit(limite)
        )
        result = await session.execute(query)
        mensajes = result.scalars().all()

        # Invertir para orden cronológico (los más recientes están primero)
        mensajes.reverse()

        return [
            {"role": msg.role, "content": msg.content}
            for msg in mensajes
        ]


async def limpiar_historial(telefono: str):
    """Borra todo el historial de una conversación."""
    async with async_session() as session:
        query = select(Mensaje).where(Mensaje.telefono == telefono)
        result = await session.execute(query)
        mensajes = result.scalars().all()
        for msg in mensajes:
            session.delete(msg)
        await session.commit()


async def obtener_clientes_para_recordar(dias: int = 30) -> list[dict]:
    """
    Retorna los clientes cuyo último mensaje fue hace `dias` días o más,
    y que todavía no recibieron un recordatorio para ese último mensaje
    (evita mandarles el recordatorio todos los días una vez que pasan los 30).

    Returns:
        Lista de {"telefono": str, "ultimo_mensaje": datetime}
    """
    limite = datetime.utcnow() - timedelta(days=dias)

    async with async_session() as session:
        query = (
            select(Mensaje.telefono, func.max(Mensaje.timestamp).label("ultimo"))
            .where(Mensaje.role == "user")
            .group_by(Mensaje.telefono)
        )
        result = await session.execute(query)

        candidatos = []
        for telefono, ultimo_mensaje in result.all():
            if ultimo_mensaje > limite:
                continue  # todavía no pasaron los `dias` días

            recordatorio = await session.get(Recordatorio, telefono)
            if recordatorio and recordatorio.ultimo_mensaje_cliente == ultimo_mensaje:
                continue  # ya se le mandó el recordatorio para este último mensaje

            candidatos.append({"telefono": telefono, "ultimo_mensaje": ultimo_mensaje})

        return candidatos


async def marcar_recordatorio_enviado(telefono: str, ultimo_mensaje: datetime):
    """Registra que ya se envió el recordatorio de 30 días a este cliente."""
    async with async_session() as session:
        recordatorio = await session.get(Recordatorio, telefono)
        if recordatorio:
            recordatorio.ultimo_mensaje_cliente = ultimo_mensaje
            recordatorio.enviado_en = datetime.utcnow()
        else:
            session.add(Recordatorio(
                telefono=telefono,
                ultimo_mensaje_cliente=ultimo_mensaje,
                enviado_en=datetime.utcnow(),
            ))
        await session.commit()
