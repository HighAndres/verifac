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
    # create_savepoint: los commit()/rollback() internos de los servicios (envío
    # de correos, credenciales) operan sobre SAVEPOINTs y la transacción externa
    # sigue viva, así el rollback final sí limpia todo y nada escapa a la BD.
    session = Session(bind=connection, autoflush=False,
                      join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()
