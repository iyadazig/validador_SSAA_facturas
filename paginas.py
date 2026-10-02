# -*- coding: utf-8 -*-
"""
Paginas de la app ademas de la revision: acceso, historial, fichas y usuarios.
"""

import datetime as dt
import json

import pandas as pd
import streamlit as st

import almacen
import estilo
import ssaa_motor as motor

ss = st.session_state


# ------------------------------------------------------------------- acceso
def acceso():
    """Pide usuario y contrasena (o crea el primer administrador). Devuelve el usuario
    conectado o detiene la pagina."""
    if ss.get("usuario"):
        if ss.usuario.get("cambiar_clave"):
            _cambio_obligatorio()
            st.stop()
        return ss.usuario

    estilo.cabecera("Revisión de servicios de ajuste en facturas", "Acceso para el equipo de GE&PE")
    _, centro, _ = st.columns([1, 1.3, 1])
    with centro:
        if not almacen.hay_usuarios():
            st.markdown("### Primer acceso: crear el administrador")
            st.caption("Todavía no hay usuarios. Crea el usuario administrador, que podrá dar de "
                       "alta al resto del equipo desde la sección «Usuarios».")
            with st.form("primer_admin"):
                usuario = st.text_input("Usuario (por ejemplo, nlibrero)")
                nombre = st.text_input("Nombre y apellidos")
                c1 = st.text_input("Contraseña", type="password",
                                   help="Al menos 10 caracteres, con letras y números.")
                c2 = st.text_input("Repite la contraseña", type="password")
                if st.form_submit_button("Crear administrador", type="primary"):
                    if c1 != c2:
                        st.error("Las contraseñas no coinciden.")
                    else:
                        try:
                            almacen.crear_usuario(usuario, nombre, c1, admin=True,
                                                  cambiar_clave=False)
                        except ValueError as e:
                            st.error(str(e))
                        else:
                            ss.usuario = almacen.comprobar(usuario, c1)
                            st.rerun()
        else:
            st.markdown("### Iniciar sesión")
            with st.form("acceso"):
                usuario = st.text_input("Usuario")
                clave = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                    try:
                        ss.usuario = almacen.comprobar(usuario, clave)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        st.rerun()
            st.caption("¿Has olvidado la contraseña? Pide a un administrador que te la restablezca.")
    estilo.pie()
    st.stop()


def _cambio_obligatorio():
    estilo.cabecera("Cambia tu contraseña", "Es tu primer acceso o un administrador la ha "
                    "restablecido")
    _, centro, _ = st.columns([1, 1.3, 1])
    with centro:
        _formulario_clave(obligatorio=True)
    estilo.pie()


def _formulario_clave(obligatorio=False):
    with st.form("cambio_clave_%s" % ("obl" if obligatorio else "vol")):
        actual = st.text_input("Contraseña actual (o la provisional)", type="password")
        c1 = st.text_input("Contraseña nueva", type="password",
                           help="Al menos 10 caracteres, con letras y números.")
        c2 = st.text_input("Repite la contraseña nueva", type="password")
        if st.form_submit_button("Cambiar contraseña", type="primary"):
            try:
                almacen.comprobar(ss.usuario["usuario"], actual)
                if c1 != c2:
                    raise ValueError("Las contraseñas nuevas no coinciden.")
                if c1 == actual:
                    raise ValueError("La contraseña nueva tiene que ser distinta.")
                almacen.cambiar_clave(ss.usuario["usuario"], c1)
            except ValueError as e:
                st.error(str(e))
            else:
                ss.usuario["cambiar_clave"] = 0
                st.success("Contraseña cambiada.")
                st.rerun()


def barra_usuario():
    """Bloque de la barra lateral con el usuario conectado."""
    u = ss.usuario
    st.markdown("**%s**%s" % (u["nombre"], " · administrador" if u["admin"] else ""))
    c1, c2 = st.columns(2)
    if c1.button("Cerrar sesión", use_container_width=True):
        for k in list(ss.keys()):
            del ss[k]
        st.rerun()
    with c2.popover("Contraseña", use_container_width=True):
        _formulario_clave()


# ------------------------------------------------------------------- historial
def pagina_historial():
    estilo.seccion("☰", "Historial de revisiones", "Todas las revisiones del equipo")
    filas = almacen.listar_revisiones(limite=5000)
    if not filas:
        st.info("Todavía no hay revisiones. Cada vez que se pulsa «Revisar SSAA» queda "
                "registrada aquí.")
        return
    df = pd.DataFrame(filas)
    df["fecha"] = pd.to_datetime(df["fecha"])
    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
    texto = f1.text_input("Buscar por CUPS, factura o comercializadora").strip().upper()
    usuario = f2.selectbox("Usuario", ["Todos"] + sorted(df["usuario"].dropna().unique()))
    comer = f3.selectbox("Comercializadora", ["Todas"] + sorted(
        df["comercializadora"].dropna().replace("", pd.NA).dropna().unique()))
    veredicto = f4.selectbox("Veredicto", ["Todos"] + sorted(df["veredicto"].dropna().unique()))
    if texto:
        df = df[df[["cups", "factura", "comercializadora"]].fillna("").apply(
            lambda c: c.str.upper().str.contains(texto, regex=False)).any(axis=1)]
    if usuario != "Todos":
        df = df[df["usuario"] == usuario]
    if comer != "Todas":
        df = df[df["comercializadora"] == comer]
    if veredicto != "Todos":
        df = df[df["veredicto"] == veredicto]

    m = st.columns(3)
    m[0].metric("Revisiones", len(df))
    m[1].metric("Facturado", "%s €" % estilo_num(df["facturado"].sum()))
    m[2].metric("Diferencia (facturado − recalculado)", "%s €" % estilo_num(df["diferencia"].sum()))
    vista = df.rename(columns={
        "id": "Nº", "fecha": "Fecha", "usuario": "Usuario", "cups": "CUPS",
        "comercializadora": "Comercializadora", "factura": "Factura", "emision": "Emisión",
        "periodo": "Periodo", "clausula": "Cláusula", "lineas": "Líneas",
        "facturado": "Facturado €", "recalculado": "Recalculado €", "diferencia": "Diferencia €",
        "veredicto": "Veredicto"})
    st.dataframe(vista, hide_index=True, use_container_width=True,
                 column_config={"Fecha": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
                                "Facturado €": st.column_config.NumberColumn(format="%.2f"),
                                "Recalculado €": st.column_config.NumberColumn(format="%.2f"),
                                "Diferencia €": st.column_config.NumberColumn(format="%.2f")})
    if len(df):
        opciones = {int(r["id"]): "Nº %d · %s · %s · %s" % (
            r["id"], r["fecha"].strftime("%d/%m/%Y %H:%M"), r["cups"] or "—", r["factura"] or "—")
            for _, r in df.iterrows()}
        c1, c2 = st.columns([3, 1])
        elegido = c1.selectbox("Informe de la revisión", list(opciones), format_func=opciones.get)
        datos, cups, factura = almacen.informe_revision(elegido)
        if datos:
            c2.download_button("Descargar informe Excel", datos,
                               "revision_SSAA_%s_%s.xlsx" % (cups or "sin_cups", factura or elegido),
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)


def estilo_num(v, d=2):
    return ("{:,.%df}" % d).format(v or 0).replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------------- fichas
def pagina_fichas():
    estilo.seccion("☰", "Fichas de contrato", "Condiciones de SSAA guardadas por CUPS")
    fichas = almacen.cargar_contratos()
    info = almacen.info_contratos()
    if not fichas:
        st.info("Todavía no hay fichas. Se guardan desde «Revisar factura» → «Guardar ficha de "
                "contrato».")
        return
    filas = []
    for cups, d in sorted(fichas.items()):
        c = motor.Contrato.desde_dict(d)
        filas.append({"CUPS": cups, "Comercializadora": c.comercializadora,
                      "Cláusula tipo": c.plantilla or "personalizada",
                      "Cobertura": motor.MECANISMOS.get(c.mecanismo, c.mecanismo),
                      "Referencias €/MWh": _referencias(c), "Tarifa": c.tarifa,
                      "Última modificación": pd.to_datetime(info[cups][0]),
                      "Por": info[cups][1] or "—"})
    st.dataframe(pd.DataFrame(filas), hide_index=True, use_container_width=True,
                 column_config={"Última modificación": st.column_config.DatetimeColumn(
                     format="DD/MM/YYYY HH:mm")})
    cups = st.selectbox("Ver los cambios de una ficha", sorted(fichas))
    cambios = []
    for h in almacen.historial_contrato(cups):
        c = motor.Contrato.desde_dict(json.loads(h["datos"]))
        cambios.append({"Fecha": pd.to_datetime(h["fecha"]), "Usuario": h["usuario"] or "—",
                        "Acción": h["accion"], "Cláusula tipo": c.plantilla or "personalizada",
                        "Referencias €/MWh": _referencias(c),
                        "Pérdidas": motor.PERDIDAS.get(c.perdidas, c.perdidas),
                        "Factor": c.factor})
    st.dataframe(pd.DataFrame(cambios), hide_index=True, use_container_width=True,
                 column_config={"Fecha": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")})


def _referencias(c):
    f = lambda v: ("%.3f" % v).replace(".", ",")
    if c.mecanismo == "banda":
        return "%s / %s" % (f(c.ref_superior), f(c.ref_inferior))
    if c.mecanismo in ("techo", "indexado_techo"):
        return f(c.techo)
    if c.mecanismo == "indexado_suelo_techo":
        return "%s / %s" % (f(c.techo), f(c.suelo))
    if c.mecanismo == "fijo":
        return f(c.precio_fijo)
    return "—"


# ------------------------------------------------------------------- usuarios
def pagina_usuarios():
    estilo.seccion("☰", "Usuarios", "Altas, contraseñas y permisos")
    if not ss.usuario["admin"]:
        st.warning("Solo los administradores pueden gestionar usuarios.")
        return
    usuarios = almacen.listar_usuarios()
    st.dataframe(pd.DataFrame([{
        "Usuario": u["usuario"], "Nombre": u["nombre"],
        "Administrador": "Sí" if u["admin"] else "", "Activo": "Sí" if u["activo"] else "No",
        "Alta": pd.to_datetime(u["creado"]),
        "Último acceso": pd.to_datetime(u["ultimo_acceso"]) if u["ultimo_acceso"] else None}
        for u in usuarios]), hide_index=True, use_container_width=True,
        column_config={"Alta": st.column_config.DatetimeColumn(format="DD/MM/YYYY"),
                       "Último acceso": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")})

    if ss.get("clave_mostrada"):
        u, clave = ss.clave_mostrada
        st.success("Contraseña provisional de **%s**: `%s` — dásela en persona o por teléfono. "
                   "Tendrá que cambiarla al entrar. No se volverá a mostrar." % (u, clave))
        if st.button("Ya la he anotado"):
            del ss["clave_mostrada"]
            st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Dar de alta")
        with st.form("alta_usuario", clear_on_submit=True):
            usuario = st.text_input("Usuario (por ejemplo, la parte del correo antes de la @)")
            nombre = st.text_input("Nombre y apellidos")
            admin = st.checkbox("Administrador (puede gestionar usuarios)")
            if st.form_submit_button("Dar de alta", type="primary"):
                clave = almacen.clave_temporal()
                try:
                    almacen.crear_usuario(usuario, nombre, clave, admin=admin, cambiar_clave=True)
                except ValueError as e:
                    st.error(str(e))
                else:
                    ss.clave_mostrada = (usuario.strip().lower(), clave)
                    st.rerun()
    with c2:
        st.markdown("### Modificar")
        nombres = {u["usuario"]: "%s (%s)" % (u["nombre"], u["usuario"]) for u in usuarios}
        elegido = st.selectbox("Usuario", list(nombres), format_func=nombres.get)
        u = next(x for x in usuarios if x["usuario"] == elegido)
        b1, b2, b3 = st.columns(3)
        if b1.button("Restablecer contraseña", use_container_width=True):
            clave = almacen.clave_temporal()
            almacen.cambiar_clave(elegido, clave, obligar_cambio=True)
            ss.clave_mostrada = (elegido, clave)
            st.rerun()
        try:
            if b2.button("Desactivar" if u["activo"] else "Reactivar", use_container_width=True):
                if elegido == ss.usuario["usuario"]:
                    raise ValueError("No puedes desactivarte a ti mismo.")
                almacen.actualizar_usuario(elegido, activo=not u["activo"])
                st.rerun()
            if b3.button("Quitar admin" if u["admin"] else "Hacer admin", use_container_width=True):
                almacen.actualizar_usuario(elegido, admin=not u["admin"])
                st.rerun()
        except ValueError as e:
            st.error(str(e))
