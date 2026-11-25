from datetime import date
import pytest
from pipelines.historico import ventanas


def test_backfill_separa_periodos_y_no_deja_huecos():
    res=list(ventanas(date(2026,1,1),date(2026,1,20),7))
    assert [x[2] for x in res]==[7,7,5]
    assert res[0][0]==date(2026,1,1)
    assert res[-1][1]==date(2026,1,20)
    for a,b in zip(res,res[1:]): assert a[1]==b[0]


def test_backfill_rechaza_rango_excesivo():
    with pytest.raises(ValueError):list(ventanas(date(2025,1,1),date(2026,4,1)))
