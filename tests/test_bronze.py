import hashlib
from uuid import uuid4

import pytest
from pipelines.comun.almacenamiento import guardar_bronze, verificar_bronze


def test_bronze_bytes_originales_e_inmutabilidad(tmp_path):
    cuerpo = b'{ "features": [], "texto": "\xc3\xb1" }\n'
    run_id = uuid4()
    resultado = guardar_bronze(cuerpo, tmp_path, "usgs", run_id)
    assert resultado.ruta_absoluta.read_bytes() == cuerpo
    assert resultado.checksum_sha256 == hashlib.sha256(cuerpo).hexdigest()
    assert verificar_bronze(resultado)
    with pytest.raises(FileExistsError):
        guardar_bronze(b"otro", tmp_path, "usgs", run_id)
    resultado.ruta_absoluta.write_bytes(b"alterado")
    assert not verificar_bronze(resultado)
