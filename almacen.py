# -*- coding: utf-8 -*-
"""
ALMACEN COMPARTIDO (SQLite)
===========================
Un unico fichero `revisor_ssaa.db` en la carpeta de datos (config.CARPETA_DATOS) con:

  usuarios              usuario, nombre, contrasena (PBKDF2-SHA256 con sal), admin, activo
  contratos             ficha vigente de cada CUPS y quien/cuando la guardo
  contratos_historial   todas las versiones de cada ficha (quien, cuando, que)
  revisiones            cada revision: usuario, fecha, factura, importes, veredicto e informe

SQLite en modo WAL admite varios compañeros a la vez desde la misma app (servidor).
La primera vez se importan las fichas de contratos_ssaa.json si existe.
"""

import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading

from contextlib import contextmanager

import config

ITERACIONES = 240_000
_bloqueo = threading.Lock()
_iniciado = set()

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    usuario TEXT PRIMARY KEY, nombre TEXT NOT NULL, sal TEXT NOT NULL, clave TEXT NOT NULL,
    admin INTEGER NOT NULL DEFAULT 0, activo INTEGER NOT NULL DEFAULT 1,
    cambiar_clave INTEGER NOT NULL DEFAULT 0, creado TEXT NOT NULL, ultimo_acceso TEXT,
    intentos_fallidos INTEGER NOT NULL DEFAULT 0, bloqueado_hasta TEXT);
CREATE TABLE IF NOT EXISTS contratos (
    cups TEXT PRIMARY KEY, datos TEXT NOT NULL, actualizado TEXT NOT NULL, usuario TEXT);
CREATE TABLE IF NOT EXISTS contratos_historial (
    id INTEGER PRIMARY KEY AUTOINCREMENT, cups TEXT NOT NULL, datos TEXT NOT NULL,
    fecha TEXT NOT NULL, usuario TEXT, accion TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS revisiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, usuario TEXT,
    cups TEXT, comercializadora TEXT, factura TEXT, emision TEXT, periodo TEXT,
    clausula TEXT, lineas INTEGER, facturado REAL, recalculado REAL, diferencia REAL,
    veredicto TEXT, detalle TEXT, informe BLOB);
CREATE INDEX IF NOT EXISTS ix_rev_cups ON revisiones(cups);
CREATE INDEX IF NOT EXISTS ix_hist_cups ON contratos_historial(cups);
"""


def ruta_bd():
    return config.CARPETA_DATOS / "revisor_ssaa.db"


def _ahora():
    return dt.datetime.now().isoformat(timespec="seconds")


def conectar():
    ruta = ruta_bd()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None: las transacciones se abren a mano en _con()
    con = sqlite3.connect(ruta, timeout=30, check_same_thread=False, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    clave = str(ruta)
    if clave not in _iniciado:
        with _bloqueo:
            if clave not in _iniciado:
                con.execute("PRAGMA journal_mode=WAL")     # queda guardado en el fichero
                con.executescript(ESQUEMA)
                _importar_json(con)
                _iniciado.add(clave)
    return con


@contextmanager
def _con(escribir=False):
    """Conexion en una transaccion que se confirma al salir (o se deshace si hay error) y
    se cierra siempre. Para escribir se reserva la base de datos al empezar (BEGIN
    IMMEDIATE): si otro compañero esta guardando, se espera en vez de fallar."""
    con = conectar()
    try:
        con.execute("BEGIN IMMEDIATE" if escribir else "BEGIN")
        try:
            yield con
        except BaseException:
            con.execute("ROLLBACK")
            raise
        con.execute("COMMIT")
    finally:
        con.close()


def _importar_json(con):
    """Primera vez: pasa las fichas de contratos_ssaa.json a la base de datos."""
    if con.execute("SELECT COUNT(*) FROM contratos").fetchone()[0]:
        return
    if not config.FICHERO_CONTRATOS.exists():
        return
    with open(config.FICHERO_CONTRATOS, encoding="utf-8") as f:
        fichas = json.load(f)
    ahora = _ahora()
    con.execute("BEGIN IMMEDIATE")
    try:
        for cups, datos in fichas.items():
            txt = json.dumps(datos, ensure_ascii=False, sort_keys=True)
            con.execute("INSERT OR IGNORE INTO contratos VALUES (?,?,?,?)",
                        (cups, txt, ahora, "importado de contratos_ssaa.json"))
            con.execute("INSERT INTO contratos_historial (cups, datos, fecha, usuario, accion) "
                        "VALUES (?,?,?,?,?)", (cups, txt, ahora, None, "importada"))
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


# ------------------------------------------------------------------- usuarios
def _hash(clave, sal):
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), bytes.fromhex(sal),
                               ITERACIONES).hex()


def hay_usuarios():
    with _con() as con:
        return con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] > 0


def validar_clave(clave):
    """Mensaje de error o None. Minimo 10 caracteres con letras y numeros."""
    if len(clave) < 10:
        return "La contraseña debe tener al menos 10 caracteres."
    if not any(c.isdigit() for c in clave) or not any(c.isalpha() for c in clave):
        return "La contraseña debe tener letras y números."
    return None


def crear_usuario(usuario, nombre, clave, admin=False, cambiar_clave=True):
    usuario = usuario.strip().lower()
    if not usuario or not nombre.strip():
        raise ValueError("Usuario y nombre son obligatorios.")
    error = validar_clave(clave)
    if error:
        raise ValueError(error)
    sal = secrets.token_hex(16)
    with _con(escribir=True) as con:
        if con.execute("SELECT 1 FROM usuarios WHERE usuario=?", (usuario,)).fetchone():
            raise ValueError("Ya existe el usuario %s." % usuario)
        con.execute("INSERT INTO usuarios (usuario, nombre, sal, clave, admin, activo, "
                    "cambiar_clave, creado) VALUES (?,?,?,?,?,1,?,?)",
                    (usuario, nombre.strip(), sal, _hash(clave, sal), int(admin),
                     int(cambiar_clave), _ahora()))


def comprobar(usuario, clave):
    """dict del usuario si la contrasena es correcta; ValueError con el motivo si no.
    Tras 5 intentos fallidos el usuario queda bloqueado 15 minutos."""
    usuario = usuario.strip().lower()
    error = None
    with _con(escribir=True) as con:
        u = con.execute("SELECT * FROM usuarios WHERE usuario=?", (usuario,)).fetchone()
        if u is None or not u["activo"]:
            error = "Usuario o contraseña incorrectos."
        elif u["bloqueado_hasta"] and u["bloqueado_hasta"] > _ahora():
            error = ("Demasiados intentos fallidos. Prueba de nuevo a las %s."
                     % u["bloqueado_hasta"][11:16])
        elif not hmac.compare_digest(_hash(clave, u["sal"]), u["clave"]):
            fallos = u["intentos_fallidos"] + 1
            bloqueo = (dt.datetime.now() + dt.timedelta(minutes=15)).isoformat(
                timespec="seconds") if fallos >= 5 else None
            con.execute("UPDATE usuarios SET intentos_fallidos=?, bloqueado_hasta=? "
                        "WHERE usuario=?", (0 if bloqueo else fallos, bloqueo, usuario))
            error = "Usuario o contraseña incorrectos."
        else:
            con.execute("UPDATE usuarios SET intentos_fallidos=0, bloqueado_hasta=NULL, "
                        "ultimo_acceso=? WHERE usuario=?", (_ahora(), usuario))
            datos = {k: u[k] for k in ("usuario", "nombre", "admin", "cambiar_clave")}
    if error:                    # fuera del with: el contador de fallos ya esta guardado
        raise ValueError(error)
    return datos


def cambiar_clave(usuario, nueva, obligar_cambio=False):
    error = validar_clave(nueva)
    if error:
        raise ValueError(error)
    sal = secrets.token_hex(16)
    with _con(escribir=True) as con:
        con.execute("UPDATE usuarios SET sal=?, clave=?, cambiar_clave=?, intentos_fallidos=0, "
                    "bloqueado_hasta=NULL WHERE usuario=?",
                    (sal, _hash(nueva, sal), int(obligar_cambio), usuario))


def listar_usuarios():
    with _con() as con:
        return [dict(r) for r in con.execute(
            "SELECT usuario, nombre, admin, activo, creado, ultimo_acceso FROM usuarios "
            "ORDER BY nombre")]


def actualizar_usuario(usuario, admin=None, activo=None):
    """Si el cambio dejara sin administradores activos, se deshace y da error."""
    with _con(escribir=True) as con:
        if admin is not None:
            con.execute("UPDATE usuarios SET admin=? WHERE usuario=?", (int(admin), usuario))
        if activo is not None:
            con.execute("UPDATE usuarios SET activo=? WHERE usuario=?", (int(activo), usuario))
        if not con.execute("SELECT COUNT(*) FROM usuarios WHERE admin=1 AND activo=1"
                           ).fetchone()[0]:
            raise ValueError("Tiene que quedar al menos un administrador activo.")


def clave_temporal():
    """Contrasena provisional para altas y reseteos (se obliga a cambiarla al entrar)."""
    return "Ssaa-" + secrets.token_urlsafe(6) + str(secrets.randbelow(90) + 10)


# ------------------------------------------------------------------- contratos
def cargar_contratos():
    with _con() as con:
        return {r["cups"]: json.loads(r["datos"]) for r in con.execute("SELECT * FROM contratos")}


def info_contratos():
    """{cups: (fecha, usuario)} de la ultima modificacion de cada ficha."""
    with _con() as con:
        return {r["cups"]: (r["actualizado"], r["usuario"])
                for r in con.execute("SELECT cups, actualizado, usuario FROM contratos")}


def guardar_contrato(cups, datos, usuario):
    txt = json.dumps(datos, ensure_ascii=False, sort_keys=True)
    ahora = _ahora()
    with _con(escribir=True) as con:
        previa = con.execute("SELECT datos FROM contratos WHERE cups=?", (cups,)).fetchone()
        if previa and previa["datos"] == txt:
            return False                              # sin cambios
        con.execute("INSERT INTO contratos VALUES (?,?,?,?) ON CONFLICT(cups) DO UPDATE SET "
                    "datos=excluded.datos, actualizado=excluded.actualizado, "
                    "usuario=excluded.usuario", (cups, txt, ahora, usuario))
        con.execute("INSERT INTO contratos_historial (cups, datos, fecha, usuario, accion) "
                    "VALUES (?,?,?,?,?)", (cups, txt, ahora, usuario,
                                           "modificada" if previa else "creada"))
    return True


def historial_contrato(cups):
    with _con() as con:
        return [dict(r) for r in con.execute(
            "SELECT fecha, usuario, accion, datos FROM contratos_historial WHERE cups=? "
            "ORDER BY id DESC", (cups,))]


# ------------------------------------------------------------------- revisiones
def guardar_revision(usuario, cabecera, lineas, informe_xlsx):
    """cabecera: dict con cups, comercializadora, factura, emision, periodo, clausula.
    lineas: filas de resumen (dicts). Devuelve el id."""
    fact = sum(l.get("Facturado €") or 0 for l in lineas)
    rec = sum(l.get("Recalculado €") or 0 for l in lineas)
    veredictos = {l.get("Veredicto") for l in lineas}
    veredicto = veredictos.pop() if len(veredictos) == 1 else "VARIOS"
    with _con(escribir=True) as con:
        cur = con.execute(
            "INSERT INTO revisiones (fecha, usuario, cups, comercializadora, factura, emision, "
            "periodo, clausula, lineas, facturado, recalculado, diferencia, veredicto, detalle, "
            "informe) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_ahora(), usuario, cabecera.get("cups"), cabecera.get("comercializadora"),
             cabecera.get("factura"), cabecera.get("emision"), cabecera.get("periodo"),
             cabecera.get("clausula"), len(lineas), round(fact, 2), round(rec, 2),
             round(fact - rec, 2), veredicto,
             json.dumps(lineas, ensure_ascii=False, default=str), informe_xlsx))
        return cur.lastrowid


def listar_revisiones(limite=500):
    with _con() as con:
        return [dict(r) for r in con.execute(
            "SELECT id, fecha, usuario, cups, comercializadora, factura, emision, periodo, "
            "clausula, lineas, facturado, recalculado, diferencia, veredicto FROM revisiones "
            "ORDER BY id DESC LIMIT ?", (limite,))]


def informe_revision(id_revision):
    with _con() as con:
        r = con.execute("SELECT informe, cups, factura FROM revisiones WHERE id=?",
                        (id_revision,)).fetchone()
        return (r["informe"], r["cups"], r["factura"]) if r else (None, None, None)


# ------------------------------------------------------------------- copias
def copia_seguridad(carpeta_destino, conservar=30):
    """Copia consistente de la base de datos (aunque haya gente usandola) y borra las mas
    antiguas, dejando las `conservar` ultimas. Devuelve la ruta de la copia."""
    from pathlib import Path
    destino = Path(carpeta_destino)
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / ("revisor_ssaa_%s.db" % dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
    origen = conectar()
    copia = sqlite3.connect(ruta)
    try:
        origen.backup(copia)
    finally:
        copia.close()
        origen.close()
    for vieja in sorted(destino.glob("revisor_ssaa_*.db"))[:-conservar]:
        vieja.unlink()
    return ruta


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Utilidades de la base de datos del revisor de SSAA")
    p.add_argument("--copia", metavar="CARPETA", help="hace una copia de seguridad en CARPETA")
    p.add_argument("--conservar", type=int, default=30, help="copias que se conservan (30)")
    a = p.parse_args()
    if a.copia:
        print("Copia guardada en %s" % copia_seguridad(a.copia, a.conservar))
    else:
        p.print_help()
