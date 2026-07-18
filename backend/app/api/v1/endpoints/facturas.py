from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_revisor
from app.db.session import get_db
from app.models.factura import Factura
from app.models.monto_mensual import MontoMensual
from app.models.profesor import Profesor
from app.models.usuario import Usuario
from app.models.validacion_detalle import ValidacionDetalle
from app.schemas.factura import FacturaDetalleOut, FacturaListOut, FacturaOut
from app.services import audit
from app.services.cfdi_parser import parsear_cfdi
from app.services.validador import validar_cfdi
from app.services.excel_parser import parsear_excel
from app.services.excel_montos_parser import parsear_excel_montos, normalizar_nombre
from app.services.revalidacion import revalidar_factura
from app.services.validador_excel import procesar_fila

router = APIRouter()

_ESTADOS = {"pendiente", "aprobada", "rechazada"}


@router.post(
    "/upload",
    response_model=FacturaDetalleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Sube y valida un XML CFDI 4.0",
)
def subir_factura(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    if not (file.filename or "").lower().endswith(".xml"):
        raise HTTPException(status_code=422, detail="El archivo debe ser .xml")

    from app.core.config import settings as _settings
    contenido = file.file.read()
    if len(contenido) > _settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=422, detail=f"El archivo supera el límite de {_settings.MAX_UPLOAD_MB} MB")

    try:
        cfdi = parsear_cfdi(contenido)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if not cfdi.uuid:
        raise HTTPException(status_code=422, detail="El CFDI no tiene TimbreFiscalDigital (UUID)")

    if db.query(Factura).filter(Factura.uuid_cfdi == cfdi.uuid).first():
        raise HTTPException(status_code=409, detail=f"Factura con UUID {cfdi.uuid} ya registrada")

    # Primer concepto para los campos planos del modelo
    primer_concepto = cfdi.conceptos[0] if cfdi.conceptos else None

    detalles_data, estado, motivo = validar_cfdi(cfdi, db)

    factura = Factura(
        uuid_cfdi=cfdi.uuid,
        rfc_emisor=cfdi.rfc_emisor,
        nombre_emisor=cfdi.nombre_emisor,
        regimen_emisor=cfdi.regimen_fiscal,
        rfc_receptor=cfdi.rfc_receptor,
        nombre_receptor=cfdi.nombre_receptor,
        moneda=cfdi.moneda,
        fecha_emision=cfdi.fecha,
        fecha_timbrado=cfdi.fecha_timbrado,
        subtotal=cfdi.subtotal,
        iva_trasladado=cfdi.iva_trasladado,
        iva_retenido=cfdi.iva_retenido,
        isr_retenido=cfdi.isr_retenido,
        total=cfdi.total,
        clave_servicio=primer_concepto.clave_prod_serv if primer_concepto else None,
        clave_unidad=primer_concepto.clave_unidad if primer_concepto else None,
        descripcion_concepto=primer_concepto.descripcion if primer_concepto else None,
        forma_pago=cfdi.forma_pago,
        metodo_pago=cfdi.metodo_pago,
        uso_cfdi=cfdi.uso_cfdi,
        estado=estado,
        motivo_rechazo=motivo,
        fecha_validacion=datetime.now(timezone.utc),
        origen="xml",
        pdf_cotejo="sin_pdf",   # carga manual de XML: no llega PDF
    )
    db.add(factura)
    db.flush()

    for d in detalles_data:
        db.add(ValidacionDetalle(factura_id=factura.id, **d))

    db.commit()
    db.refresh(factura)

    audit.log(db, username=user.username, rol=user.rol, accion="UPLOAD",
              recurso="factura", recurso_id=factura.uuid_cfdi, detalle=f"estado={estado}")

    detalles_obj = db.query(ValidacionDetalle).filter(ValidacionDetalle.factura_id == factura.id).all()
    return {**FacturaOut.model_validate(factura).model_dump(), "detalles": detalles_obj}


@router.post(
    "/upload-excel",
    summary="Carga masiva desde el formato Ejemplo Base BBVA (.xlsx)",
)
def subir_excel(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="El archivo debe ser .xlsx")

    from app.core.config import settings
    contenido = file.file.read()
    if len(contenido) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=422, detail=f"El archivo supera el límite de {settings.MAX_UPLOAD_MB} MB")

    try:
        filas = parsear_excel(contenido)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Error leyendo el Excel: {exc}")

    if not filas:
        raise HTTPException(status_code=422, detail="El archivo no tiene filas con datos")

    resultados = []
    for fila in filas:
        try:
            resultado = procesar_fila(fila, db)
            resultados.append(resultado)
        except Exception as exc:
            db.rollback()
            resultados.append({
                "fila": fila.fila,
                "nombre_emisor": fila.nombre_emisor,
                "estado": "error",
                "errores": [str(exc)],
            })

    aprobadas = sum(1 for r in resultados if r.get("estado") == "aprobadas")
    rechazadas = sum(1 for r in resultados if r.get("estado") == "rechazada")

    audit.log(db, username=user.username, rol=user.rol, accion="UPLOAD",
              recurso="factura", recurso_id="captura_manual",
              detalle=f"filas={len(filas)} (origen=captura_manual)")

    return {
        "total_filas": len(filas),
        "aprobadas": aprobadas,
        "rechazadas": rechazadas,
        "resultados": resultados,
    }


@router.get("", response_model=FacturaListOut)
def listar_facturas(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    estado: Optional[str] = Query(None),
    rfc_emisor: Optional[str] = Query(None),
    mes: Optional[int] = Query(None, ge=1, le=12),
    anio: Optional[int] = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
):
    from sqlalchemy import extract

    if estado and estado not in _ESTADOS:
        raise HTTPException(status_code=422, detail=f"estado debe ser uno de: {sorted(_ESTADOS)}")

    q = db.query(Factura)
    if estado:
        q = q.filter(Factura.estado == estado)
    if rfc_emisor:
        q = q.filter(Factura.rfc_emisor == rfc_emisor.upper())
    if mes:
        q = q.filter(extract("month", Factura.fecha_emision) == mes)
    if anio:
        q = q.filter(extract("year", Factura.fecha_emision) == anio)

    total = q.count()
    items = q.order_by(Factura.fecha_emision.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": items}


@router.get("/{factura_id}", response_model=FacturaDetalleOut)
def obtener_factura(factura_id: UUID, db: Session = Depends(get_db)):
    factura = db.query(Factura).filter(Factura.id == factura_id).first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    detalles = db.query(ValidacionDetalle).filter(ValidacionDetalle.factura_id == factura_id).all()
    return {**FacturaOut.model_validate(factura).model_dump(), "detalles": detalles}


@router.post(
    "/{factura_id}/revalidar",
    response_model=FacturaDetalleOut,
    summary="Revalida una factura contra las reglas y el layout de montos actuales",
)
def revalidar_una(
    factura_id: UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    factura = db.query(Factura).filter(Factura.id == factura_id).first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    estado, _ = revalidar_factura(factura, db)
    db.commit()
    db.refresh(factura)

    audit.log(db, username=user.username, rol=user.rol, accion="REVALIDATE",
              recurso="factura", recurso_id=factura.uuid_cfdi, detalle=f"estado={estado}")

    detalles = db.query(ValidacionDetalle).filter(ValidacionDetalle.factura_id == factura.id).all()
    return {**FacturaOut.model_validate(factura).model_dump(), "detalles": detalles}


@router.post(
    "/revalidar-mes",
    summary="Revalida todas las facturas de un mes/año (útil tras cargar el layout)",
)
def revalidar_mes(
    mes: int = Query(..., ge=1, le=12),
    anio: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    from sqlalchemy import extract
    facturas = (
        db.query(Factura)
        .filter(
            extract("month", Factura.fecha_emision) == mes,
            extract("year", Factura.fecha_emision) == anio,
        )
        .all()
    )

    cambios = []
    for f in facturas:
        estado_previo = f.estado
        estado_nuevo, _ = revalidar_factura(f, db)
        if estado_nuevo != estado_previo:
            cambios.append({
                "uuid": f.uuid_cfdi,
                "emisor": f.nombre_emisor,
                "antes": estado_previo,
                "despues": estado_nuevo,
            })
    db.commit()

    audit.log(db, username=user.username, rol=user.rol, accion="REVALIDATE",
              recurso="factura", recurso_id=f"{mes:02d}/{anio}",
              detalle=f"revalidadas={len(facturas)} cambios={len(cambios)}")

    return {
        "mes": mes,
        "anio": anio,
        "revalidadas": len(facturas),
        "con_cambio": len(cambios),
        "cambios": cambios,
    }


@router.post(
    "/upload-montos",
    summary="Carga el layout de montos mensuales (.xlsx) para conciliación",
)
def subir_montos_mensuales(
    file: UploadFile,
    mes: int = Query(..., ge=1, le=12, description="Mes del layout (1-12)"),
    anio: int = Query(..., ge=2000, le=2100, description="Año del layout"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="El archivo debe ser .xlsx")

    from app.core.config import settings as _settings
    contenido = file.file.read()
    if len(contenido) > _settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=422, detail=f"El archivo supera el límite de {_settings.MAX_UPLOAD_MB} MB")
    try:
        filas = parsear_excel_montos(contenido)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Error leyendo el Excel: {exc}")

    if not filas:
        raise HTTPException(status_code=422, detail="El archivo no tiene filas con datos")

    # ── Guard 1: cotejar el mes/año del archivo (si lo trae) contra lo seleccionado ──
    desajustes = [
        f"fila {f.fila} ({f.nombre_emisor}): archivo dice "
        f"{(f.mes or '—')}/{(f.anio or '—')}"
        for f in filas
        if (f.mes is not None and f.mes != mes) or (f.anio is not None and f.anio != anio)
    ]
    if desajustes:
        raise HTTPException(
            status_code=422,
            detail=(
                f"El periodo seleccionado ({mes:02d}/{anio}) no coincide con el que trae el "
                f"archivo. Verifica que estés cargando el layout del mes correcto. "
                f"Filas en conflicto: {'; '.join(desajustes[:5])}"
                + (f" (+{len(desajustes) - 5} más)" if len(desajustes) > 5 else "")
            ),
        )

    # ── Guard 2: detectar filas duplicadas del mismo emisor en el archivo ──────────
    vistos: dict[str, int] = {}
    duplicados = []
    for f in filas:
        clave = (f.rfc_emisor or "").upper() or f.nombre_emisor
        if clave in vistos:
            duplicados.append(f"{f.nombre_emisor} (filas {vistos[clave]} y {f.fila})")
        else:
            vistos[clave] = f.fila
    if duplicados:
        raise HTTPException(
            status_code=422,
            detail=(
                "El archivo tiene emisores repetidos para el mismo mes; cada emisor debe "
                f"aparecer una sola vez. Duplicados: {'; '.join(duplicados[:5])}"
                + (f" (+{len(duplicados) - 5} más)" if len(duplicados) > 5 else "")
            ),
        )

    # ── Guard 3: advertir si el periodo es futuro (año mal tecleado, etc.) ─────────
    hoy = datetime.now(timezone.utc)
    periodo_futuro = (anio, mes) > (hoy.year, hoy.month)

    # Eliminar montos previos del mismo mes/año para permitir re-carga
    borrados = db.query(MontoMensual).filter(
        MontoMensual.mes == mes, MontoMensual.anio == anio
    ).delete()

    cargados = []
    sin_match = []

    # Índice de profesores en memoria: por RFC y por nombre normalizado
    profesores = db.query(Profesor).all()
    por_rfc = {p.rfc.upper(): p for p in profesores if p.rfc}
    por_nombre = {normalizar_nombre(p.nombre): p for p in profesores}

    for fila in filas:
        # Emparejar preferentemente por RFC; si no, por nombre normalizado.
        profesor = None
        if fila.rfc_emisor:
            profesor = por_rfc.get(fila.rfc_emisor.upper())
        if profesor is None:
            profesor = por_nombre.get(fila.nombre_emisor)

        monto = MontoMensual(
            profesor_id=profesor.id if profesor else None,
            nombre_layout=fila.nombre_emisor,
            rfc_emisor=fila.rfc_emisor,
            regimen_fiscal=fila.regimen_fiscal,
            categoria=fila.categoria,
            mes=mes,
            anio=anio,
            subtotal=fila.subtotal,
            iva_trasladado=fila.iva_trasladado,
            iva_retenido=fila.iva_retenido,
            isr_retenido=fila.isr_retenido,
            total=fila.total,
        )
        db.add(monto)

        entrada = {"nombre": fila.nombre_emisor, "subtotal": float(fila.subtotal)}
        if profesor:
            entrada["profesor_id"] = str(profesor.id)
            cargados.append(entrada)
        else:
            sin_match.append(entrada)

    db.commit()

    audit.log(db, username=user.username, rol=user.rol, accion="UPLOAD",
              recurso="montos_mensuales", recurso_id=f"{mes:02d}/{anio}",
              detalle=f"filas={len(filas)} emparejados={len(cargados)} reemplazados={borrados}")

    advertencias = []
    if periodo_futuro:
        advertencias.append(
            f"El periodo {mes:02d}/{anio} es futuro respecto a hoy "
            f"({hoy.month:02d}/{hoy.year}); confirma que el año/mes sea correcto."
        )

    return {
        "mes": mes,
        "anio": anio,
        "total_filas": len(filas),
        "emparejados": len(cargados),
        "sin_match": len(sin_match),
        "montos_previos_reemplazados": borrados,
        "advertencias": advertencias,
        "detalle_sin_match": sin_match,
    }


@router.get(
    "/montos/{mes}/{anio}",
    summary="Lista los montos esperados de un mes/año",
)
def listar_montos_mensuales(
    mes: int,
    anio: int,
    db: Session = Depends(get_db),
):
    filas = (
        db.query(MontoMensual)
        .filter(MontoMensual.mes == mes, MontoMensual.anio == anio)
        .order_by(MontoMensual.nombre_layout)
        .all()
    )
    return {
        "mes": mes,
        "anio": anio,
        "total": len(filas),
        "items": [
            {
                "id": str(f.id),
                "nombre_layout": f.nombre_layout,
                "rfc_emisor": f.rfc_emisor,
                "categoria": f.categoria,
                "regimen_fiscal": f.regimen_fiscal,
                "profesor_id": str(f.profesor_id) if f.profesor_id else None,
                "subtotal": float(f.subtotal),
                "iva_trasladado": float(f.iva_trasladado),
                "iva_retenido": float(f.iva_retenido),
                "isr_retenido": float(f.isr_retenido),
                "total": float(f.total),
            }
            for f in filas
        ],
    }
