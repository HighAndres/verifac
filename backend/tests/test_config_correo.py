"""Pruebas de la config de correo (parseo de remitentes permitidos)."""
from app.models.configuracion_correo import ConfiguracionCorreo
from app.services.config_correo import obtener_config, remitentes_lista


def test_remitentes_vacio_es_lista_vacia():
    cfg = ConfiguracionCorreo(remitentes_permitidos=None)
    assert remitentes_lista(cfg) == []


def test_remitentes_parsea_comas_saltos_y_puntoycoma():
    cfg = ConfiguracionCorreo(remitentes_permitidos="A@X.com, b@y.com\n c@z.com; d@w.com")
    assert remitentes_lista(cfg) == ["a@x.com", "b@y.com", "c@z.com", "d@w.com"]


def test_obtener_config_devuelve_la_existente(db):
    db.query(ConfiguracionCorreo).delete()
    db.add(ConfiguracionCorreo(imap_host="mi-host", imap_port=993, imap_user="u@x.com",
                               imap_folder="INBOX", poll_minutos=7, auto_activo=False))
    db.flush()
    cfg = obtener_config(db)
    assert cfg.imap_host == "mi-host"
    assert cfg.poll_minutos == 7
    assert cfg.auto_activo is False
