"""Medición reproducible de líneas físicas de código no vacías, excluye comentarios de línea.
Uso: python docs/cocomo.py [directorio raíz]. Python, SQL, JS/JSX de producción.
Excluye CSS minificado, pruebas, configuración, documentación, dependencias y archivos generados.
No equivale a DSI exactas: incluye docstrings y líneas de continuación.
"""
from pathlib import Path
import sys

def contar(root):
    tot={}
    for carpeta in ('pipelines','apps/api','apps/web/src','sql'):
        n=0
        for p in (root/carpeta).rglob('*'):
            if p.suffix not in ('.py','.sql','.js','.jsx'): continue
            n+=sum(bool(l.strip()) and not l.lstrip().startswith(('#','--','//')) for l in p.read_text(encoding='utf-8').splitlines())
        tot[carpeta]=n
    return tot

def estimar(n):
    e=2.4*(n/1000)**1.05
    t=2.5*e**.38
    return e,t,e/t

if __name__=='__main__':
    d=contar(Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]); n=sum(d.values()); print(d, n, estimar(n))
