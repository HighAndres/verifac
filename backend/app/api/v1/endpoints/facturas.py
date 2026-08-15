from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_lectura, require_revisor
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
from app.services.excel_montos_parser import parsear_excel_montos, normalizar_nombre
from app.services.revalidacion import revalidar_factura

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

    if estado == "aprobada":
        from app.services.email_confirmacion import procesar_confirmaciones
        procesar_confirmaciones(db)

    detalles_obj = db.query(ValidacionDetalle).filter(ValidacionDetalle.factura_id == factura.id).all()
    return {**FacturaOut.model_validate(factura).model_dump(), "detalles": detalles_obj}


@router.get("", response_model=FacturaListOut)
def listar_facturas(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    estado: Optional[str] = Query(None),
    origen: Optional[str] = Query(None, description="xml (correo) | portal (subida del profesor)"),
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
    if origen:
        q = q.filter(Factura.origen == origen)
    if rfc_emisor:
        q = q.filter(Factura.rfc_emisor == rfc_emisor.upper())
    if mes:
        q = q.filter(extract("month", Factura.fecha_emision) == mes)
    if anio:
        q = q.filter(extract("year", Factura.fecha_emision) == anio)

    from sqlalchemy import func

    total = q.count()
    suma_total = q.with_entities(func.coalesce(func.sum(Factura.total), 0)).scalar()
    items = q.order_by(Factura.fecha_emision.desc()).offset(skip).limit(limit).all()
    return {"total": total, "suma_total": suma_total, "items": items}


@router.get(
    "/export-mes",
    summary="Descarga el mes conciliado en Excel (resumen + formato Base BBVA)",
)
def exportar_mes(
    mes: int = Query(..., ge=1, le=12),
    anio: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_lectura),
):
    from fastapi.responses import Response as _Response
    from app.services.export_excel import generar_excel_mes, nombre_archivo

    contenido = generar_excel_mes(db, mes, anio)
    audit.log(db, username=user.username, rol=user.rol, accion="EXPORT",
              recurso="conciliacion", recurso_id=f"{mes:02d}/{anio}")
    return _Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo(mes, anio)}"'},
    )


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

    if estado == "aprobada":
        from app.services.email_confirmacion import procesar_confirmaciones
        procesar_confirmaciones(db)

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

    from app.services.email_confirmacion import procesar_confirmaciones
    procesar_confirmaciones(db)

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

    # ── Guard 0: el REVISOR solo puede cargar el layout del MES EN CURSO ───────────
    # El superadmin puede cargar cualquier mes (mientras coincida con lo seleccionado,
    # ver Guard 1). Se usa la hora de México (no UTC) para no bloquear cargas válidas
    # en las últimas horas del mes, cuando UTC ya marca el mes siguiente.
    if user.rol == "revisor":
        try:
            from zoneinfo import ZoneInfo
            ahora_mx = datetime.now(ZoneInfo("America/Mexico_City"))
        except Exception:
            ahora_mx = datetime.now(timezone.utc)
        if (anio, mes) != (ahora_mx.year, ahora_mx.month):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Como revisor solo puedes cargar el layout del mes en curso "
                    f"({ahora_mx.month:02d}/{ahora_mx.year}). "
                    f"Seleccionaste {mes:02d}/{anio}. Cambia el periodo al mes actual "
                    f"para poder subir el archivo."
                ),
            )

    # ── Guard 1a: el archivo DEBE declarar Mes y Año en cada fila ──────────────────
    # Sin esto no se puede verificar que el layout corresponde al periodo seleccionado.
    faltantes = [
        f"fila {f.fila} ({f.nombre_emisor})"
        for f in filas
        if f.mes is None or f.anio is None
    ]
    if faltantes:
        raise HTTPException(
            status_code=422,
            detail=(
                f"El archivo debe indicar el Mes y el Año en cada fila para verificar que "
                f"corresponde al periodo seleccionado ({mes:02d}/{anio}). Completa esas "
                f"columnas en la plantilla. Filas sin Mes/Año: {'; '.join(faltantes[:5])}"
                + (f" (+{len(faltantes) - 5} más)" if len(faltantes) > 5 else "")
            ),
        )

    # ── Guard 1b: el Mes/Año del archivo debe COINCIDIR con lo seleccionado ─────────
    desajustes = [
        f"fila {f.fila} ({f.nombre_emisor}): archivo dice {f.mes:02d}/{f.anio}"
        for f in filas
        if f.mes != mes or f.anio != anio
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

    # ── Guard 3: régimen fiscal con formato inválido (columna VARCHAR(3) en BD) ────
    regimenes_malos = [
        f"fila {f.fila} ({f.nombre_emisor}): {f.regimen_fiscal}"
        for f in filas
        if len(f.regimen_fiscal) > 3
    ]
    if regimenes_malos:
        raise HTTPException(
            status_code=422,
            detail=(
                "Régimen fiscal inválido (revisa que esa columna del Excel esté como "
                "texto, no como número; ej. '626' y no '626.0'). Filas en conflicto: "
                + "; ".join(regimenes_malos[:5])
                + (f" (+{len(regimenes_malos) - 5} más)" if len(regimenes_malos) > 5 else "")
            ),
        )

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

    advertencias: list[str] = []

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
