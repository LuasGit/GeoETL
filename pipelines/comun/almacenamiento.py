"""Preservación inmutable de respuestas HTTP: exactamente los bytes recibidos."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ArchivoBronze:
    ruta_relativa: str
    checksum_sha256: str
    tamanio_bytes: int
    ruta_absoluta: Path


def guardar_bronze(
    datos: bytes, raiz: Path, fuente: str, id_ejecucion: UUID,
    extension: str = "geojson", fecha: datetime | None = None,
) -> ArchivoBronze:
    """Escribe de forma atómica; nunca modifica archivos Bronze previos."""
    fecha = fecha or datetime.now(timezone.utc)
    fecha = fecha.astimezone(timezone.utc)
    relativa = Path("bronze") / fuente.lower() / fecha.strftime("%Y/%m/%d") / f"{id_ejecucion}.{extension}"
    destino = raiz / relativa
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        raise FileExistsError(f"Archivo Bronze ya existe: {destino}")
    temporal = destino.with_name(destino.name + f".{uuid4().hex}.tmp")
    try:
        with temporal.open("xb") as archivo:
            archivo.write(datos)
            archivo.flush()
            os.fsync(archivo.fileno())
        # No se pisa destino creado durante otra ejecución.
        if destino.exists():
            raise FileExistsError(f"Archivo Bronze ya existe: {destino}")
        temporal.rename(destino)
    finally:
        temporal.unlink(missing_ok=True)
    return ArchivoBronze(
        ruta_relativa=relativa.as_posix(),
        checksum_sha256=hashlib.sha256(datos).hexdigest(),
        tamanio_bytes=len(datos),
        ruta_absoluta=destino,
    )


def verificar_bronze(archivo: ArchivoBronze) -> bool:
    return (hashlib.sha256(archivo.ruta_absoluta.read_bytes()).hexdigest()
            == archivo.checksum_sha256)
