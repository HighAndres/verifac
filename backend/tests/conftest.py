"""
Configuración de pruebas. Cada test corre dentro de una transacción que se
revierte al terminar, así no deja basura en la base de datos.
"""
import pytest
from sqlalchemy.orm import Session

from app.db.session import engine


@pytest.fixture
def db():
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, autoflush=False)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()
