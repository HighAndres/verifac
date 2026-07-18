"""
Parser para CFDI 4.0 (namespace http://www.sat.gob.mx/cfd/4).
Extrae todos los campos necesarios para la validación de retenciones.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from lxml import etree

NSMAP = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
}

CFDI4_NS = "http://www.sat.gob.mx/cfd/4"


@dataclass
class ConceptoCFDI:
    clave_prod_serv: str
    clave_unidad: str
    descripcion: str
    valor_unitario: Decimal
    objeto_imp: str


@dataclass
class CFDIData:
    # Comprobante
    fecha: datetime
    subtotal: Decimal
    total: Decimal
    forma_pago: Optional[str]
    metodo_pago: Optional[str]

    # Emisor
    rfc_emisor: str
    nombre_emisor: str
    regimen_fiscal: str

    # Receptor
    rfc_receptor: str
    nombre_receptor: str
    uso_cfdi: str
    moneda: str

    # Conceptos
    conceptos: list[ConceptoCFDI] = field(default_factory=list)

    # Impuestos calculados del XML
    iva_trasladado: Decimal = Decimal("0")
    isr_retenido: Decimal = Decimal("0")
    iva_retenido: Decimal = Decimal("0")

    # Timbre
    uuid: str = ""
    fecha_timbrado: Optional[datetime] = None


def _dec(value: Optional[str], default: Decimal = Decimal("0")) -> Decimal:
    if not value:
        return default
    try:
        return Decimal(value)
    except InvalidOperation:
        return default


def _fecha(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    # CFDI usa ISO 8601: "2024-01-15T12:00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


_SAFE_PARSER = etree.XMLParser(
    resolve_entities=False,   # bloquea XXE
    no_network=True,          # bloquea DTD remotas
    load_dtd=False,
    dtd_validation=False,
)

MAX_XML_SIZE = 5 * 1024 * 1024  # 5 MB


def parsear_cfdi(xml_bytes: bytes) -> CFDIData:
    if len(xml_bytes) > MAX_XML_SIZE:
        raise ValueError("El XML supera el límite de 5 MB")
    try:
        root = etree.fromstring(xml_bytes, _SAFE_PARSER)
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"XML inválido: {exc}") from exc

    # Verificar que sea CFDI 4.0
    if not root.tag.startswith(f"{{{CFDI4_NS}}}"):
        raise ValueError(
            f"No es un CFDI 4.0. Namespace detectado: {root.tag}"
        )

    # ---------- Comprobante ----------
    fecha = _fecha(root.get("Fecha"))
    if fecha is None:
        raise ValueError("Atributo Fecha faltante o inválido en Comprobante")
    subtotal = _dec(root.get("SubTotal"))
    total = _dec(root.get("Total"))
    forma_pago = root.get("FormaPago")
    metodo_pago = root.get("MetodoPago")

    # ---------- Emisor ----------
    emisor_el = root.find("cfdi:Emisor", NSMAP)
    if emisor_el is None:
        raise ValueError("Nodo cfdi:Emisor no encontrado")
    rfc_emisor = (emisor_el.get("Rfc") or "").strip().upper()
    nombre_emisor = emisor_el.get("Nombre") or ""
    regimen_fiscal = emisor_el.get("RegimenFiscal") or ""

    # ---------- Receptor ----------
    receptor_el = root.find("cfdi:Receptor", NSMAP)
    if receptor_el is None:
        raise ValueError("Nodo cfdi:Receptor no encontrado")
    rfc_receptor = (receptor_el.get("Rfc") or "").strip().upper()
    nombre_receptor = receptor_el.get("Nombre") or ""
    uso_cfdi = receptor_el.get("UsoCFDI") or ""
    moneda = root.get("Moneda") or ""

    # ---------- Conceptos ----------
    conceptos: list[ConceptoCFDI] = []
    for concepto_el in root.findall("cfdi:Conceptos/cfdi:Concepto", NSMAP):
        conceptos.append(
            ConceptoCFDI(
                clave_prod_serv=concepto_el.get("ClaveProdServ") or "",
                clave_unidad=concepto_el.get("ClaveUnidad") or "",
                descripcion=concepto_el.get("Descripcion") or "",
                valor_unitario=_dec(concepto_el.get("ValorUnitario")),
                objeto_imp=concepto_el.get("ObjetoImp") or "",
            )
        )

    # ---------- Impuestos del comprobante ----------
    # Traslados
    iva_trasladado = Decimal("0")
    for traslado in root.findall("cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado", NSMAP):
        if traslado.get("Impuesto") == "002":
            iva_trasladado += _dec(traslado.get("Importe"))

    # Retenciones
    isr_retenido = Decimal("0")
    iva_retenido = Decimal("0")
    for retencion in root.findall("cfdi:Impuestos/cfdi:Retenciones/cfdi:Retencion", NSMAP):
        impuesto = retencion.get("Impuesto")
        importe = _dec(retencion.get("Importe"))
        if impuesto == "001":
            isr_retenido += importe
        elif impuesto == "002":
            iva_retenido += importe

    # ---------- Timbre Fiscal Digital ----------
    tfd_el = root.find("cfdi:Complemento/tfd:TimbreFiscalDigital", NSMAP)
    uuid = ""
    fecha_timbrado = None
    if tfd_el is not None:
        uuid = tfd_el.get("UUID") or ""
        fecha_timbrado = _fecha(tfd_el.get("FechaTimbrado"))

    return CFDIData(
        fecha=fecha,
        subtotal=subtotal,
        total=total,
        forma_pago=forma_pago,
        metodo_pago=metodo_pago,
        rfc_emisor=rfc_emisor,
        nombre_emisor=nombre_emisor,
        regimen_fiscal=regimen_fiscal,
        rfc_receptor=rfc_receptor,
        nombre_receptor=nombre_receptor,
        uso_cfdi=uso_cfdi,
        moneda=moneda,
        conceptos=conceptos,
        iva_trasladado=iva_trasladado,
        isr_retenido=isr_retenido,
        iva_retenido=iva_retenido,
        uuid=uuid,
        fecha_timbrado=fecha_timbrado,
    )
