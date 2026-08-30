import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
import os
import matplotlib.pyplot as plt

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    PageBreak
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from io import BytesIO
from datetime import date, timedelta, datetime

st.set_page_config(
    page_title="Observatorio Social Asociación Ciudad Futuro",
    page_icon="📊",
    layout="wide"
)

engine = create_engine(st.secrets["DATABASE_URL"])

if "page" not in st.session_state:
    st.session_state.page = "home"


# ============================================================
# V12 - AUTENTICACIÓN POR CÉDULA Y ROLES
# ============================================================
def _tabla_usuarios_disponible():
    try:
        with engine.connect() as conn:
            return bool(conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema='public'
                      AND table_name='funcionarios_sistema'
                )
            """)).scalar())
    except Exception:
        return False


def _autenticar_funcionario(cedula, clave):
    doc = str(cedula or "").strip()
    if doc.endswith(".0"):
        doc = doc[:-2]

    if not doc or not clave:
        return None

    try:
        with engine.connect() as conn:
            fila = conn.execute(
                text("""
                    SELECT
                        cedula,
                        nombre,
                        rol,
                        activo,
                        password_hash = crypt(
                            :clave,
                            password_hash
                        ) AS clave_ok
                    FROM public.funcionarios_sistema
                    WHERE TRIM(cedula) = :cedula
                    LIMIT 1
                """),
                {"cedula": doc, "clave": clave}
            ).mappings().first()

        if not fila:
            return None
        if not bool(fila["activo"]):
            return None
        if not bool(fila["clave_ok"]):
            return None
        return dict(fila)

    except Exception:
        return None


def cerrar_sesion_v12():
    for clave in [
        "autenticado",
        "usuario_actual",
        "documento_funcionario",
        "rol_actual",
        "nombre_funcionario",
    ]:
        st.session_state.pop(clave, None)

    st.session_state.page = "home"
    st.rerun()


def exigir_login_v12():
    if st.session_state.get("autenticado"):
        return

    st.markdown("""
        <div style="
            max-width:520px;
            margin:3rem auto 1rem auto;
            text-align:center;
        ">
            <h1>🔐 Observatorio Social</h1>
            <p><b>Asociación Ciudad Futuro</b></p>
            <p style="opacity:.7">Acceso del equipo</p>
        </div>
    """, unsafe_allow_html=True)

    if not _tabla_usuarios_disponible():
        st.error(
            "Falta crear la tabla funcionarios_sistema. "
            "Ejecute primero la migración SQL de la V12 en Supabase."
        )
        st.stop()

    with st.form("login_v12"):
        cedula = st.text_input(
            "Número de cédula",
            placeholder="Digite su cédula"
        )
        clave = st.text_input(
            "Contraseña",
            type="password"
        )
        entrar = st.form_submit_button(
            "🔐 Ingresar",
            use_container_width=True,
            type="primary"
        )

    if entrar:
        usuario = _autenticar_funcionario(cedula, clave)

        if not usuario:
            st.error(
                "Cédula o contraseña incorrecta, "
                "o el usuario se encuentra inactivo."
            )
        else:
            rol = str(usuario["rol"]).strip().upper()
            nombre = str(usuario["nombre"]).strip()
            doc = str(usuario["cedula"]).strip()

            st.session_state["autenticado"] = True
            st.session_state["rol_actual"] = rol
            st.session_state["nombre_funcionario"] = nombre
            st.session_state["documento_funcionario"] = doc

            # Esta cadena queda almacenada automáticamente en movimientos
            # y auditoría para identificar al funcionario.
            st.session_state["usuario_actual"] = (
                f"{nombre} | CC {doc} | {rol}"
            )

            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            UPDATE public.funcionarios_sistema
                            SET ultimo_acceso=NOW()
                            WHERE cedula=:cedula
                        """),
                        {"cedula": doc}
                    )
            except Exception:
                pass

            if rol in ["INSPIRADOR", "PROFESIONAL"]:
                st.session_state.page = "gestion_movil"
            else:
                st.session_state.page = "dashboard_ejecutivo"

            st.rerun()

    st.stop()



# ============================================================
# CONFIGURACIÓN Y UTILIDADES CENTRALES
# ============================================================
@st.cache_data(ttl=60, show_spinner=False)
def cargar_tabla(nombre_tabla: str):
    """Carga una tabla completa con caché corta para reducir consultas repetidas."""
    tablas_permitidas = {
        "habitante_de_calle",
        "personas_caracterizacion",
        "pai_objetivos",
        "pai_novedades",
        "movimientos_habitante",
        "caracterizacion_genero_diversidad",
    }
    if nombre_tabla not in tablas_permitidas:
        raise ValueError("Tabla no autorizada.")
    return pd.read_sql(text(f'SELECT * FROM "{nombre_tabla}"'), engine)


def limpiar_documento(valor):
    """Normaliza identificaciones para búsquedas y comparaciones."""
    if valor is None:
        return ""
    valor = str(valor).strip()
    if valor.endswith(".0"):
        valor = valor[:-2]
    return valor


def registrar_auditoria(
    accion,
    documento=None,
    modulo=None,
    valor_anterior=None,
    valor_nuevo=None,
    observacion=None,
):
    """
    Registra auditoría si existe la tabla auditoria_sistema.
    Si aún no existe, no bloquea la operación principal.
    """
    usuario = st.session_state.get("usuario_actual", "sistema")
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO auditoria_sistema (
                        fecha_hora,
                        usuario,
                        modulo,
                        accion,
                        numero_identificacion,
                        valor_anterior,
                        valor_nuevo,
                        observacion
                    )
                    VALUES (
                        NOW(),
                        :usuario,
                        :modulo,
                        :accion,
                        :documento,
                        :valor_anterior,
                        :valor_nuevo,
                        :observacion
                    )
                """),
                {
                    "usuario": usuario,
                    "modulo": modulo,
                    "accion": accion,
                    "documento": limpiar_documento(documento),
                    "valor_anterior": None if valor_anterior is None else str(valor_anterior),
                    "valor_nuevo": None if valor_nuevo is None else str(valor_nuevo),
                    "observacion": observacion,
                },
            )
    except Exception:
        # La auditoría es complementaria: no debe romper el flujo principal
        pass


def validar_documento_no_duplicado(numero_documento):
    """Comprueba si ya existe una identificación en habitante_de_calle."""
    doc = limpiar_documento(numero_documento)
    if not doc:
        return False, "El número de identificación es obligatorio."

    consulta = pd.read_sql(
        text("""
            SELECT COUNT(*) AS total
            FROM habitante_de_calle
            WHERE TRIM(numero_identificacion::TEXT) = :doc
        """),
        engine,
        params={"doc": doc},
    )
    existe = int(consulta.iloc[0]["total"] or 0) > 0
    if existe:
        return False, "Ya existe una persona registrada con esta identificación."
    return True, "OK"


def invalidar_cache_datos():
    """Limpia la caché después de operaciones de escritura."""
    try:
        cargar_tabla.clear()
    except Exception:
        pass


from sqlalchemy import create_engine, text
#from ollama import Client

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak
)

from reportlab.lib.styles import getSampleStyleSheet
import uuid
import urllib.parse
def generar_historia_integral(documento, engine):
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    styles = getSampleStyleSheet()
    elements = []

    documento = str(documento).strip()
    from datetime import datetime

    fecha_reporte = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reporte_id = str(uuid.uuid4())[:8]
    # =========================
    # 1. USUARIO
    # =========================
    usuario_df = pd.read_sql(text("""
        SELECT nombres, apellidos, numero_identificacion, edad, sexo_al_nacer
        FROM habitante_de_calle
        WHERE numero_identificacion::TEXT = :doc
    """), engine, params={"doc": documento})

    if usuario_df.empty:
        elements.append(Paragraph("NO SE ENCONTRÓ EL USUARIO", styles["Title"]))
        doc.build(elements)
        buffer.seek(0)
        return buffer

    u = usuario_df.iloc[0]

    elements.append(Paragraph("HISTORIA INTEGRAL DE ATENCIÓN", styles["Title"]))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"ID de informe: PAI-{reporte_id}", styles["BodyText"]))
    elements.append(Paragraph(f"Fecha de generación: {fecha_reporte}", styles["BodyText"]))
    elements.append(Paragraph("Sistema: PAI - Historia Integral de Atención", styles["BodyText"]))

    elements.append(Spacer(1, 12))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("1. IDENTIFICACIÓN", styles["Heading2"]))
    elements.append(Paragraph(f"{u['nombres']} {u['apellidos']}", styles["BodyText"]))
    elements.append(Paragraph(f"Documento: {u['numero_identificacion']}", styles["BodyText"]))
    elements.append(Paragraph(f"Edad: {u['edad']} | Sexo: {u['sexo_al_nacer']}", styles["BodyText"]))
    elements.append(Spacer(1, 12))
    resumen_obj = pd.read_sql(text("""
        SELECT
            COUNT(*) AS objetivos,
            AVG(porcentaje_avance) AS avance_promedio
        FROM pai_objetivos
        WHERE documento_usuario = :doc
    """), engine, params={"doc": documento})


    resumen_nov = pd.read_sql(text("""
        SELECT COUNT(*) AS novedades
        FROM pai_novedades n
        JOIN pai_objetivos o ON o.id = n.id_objetivo
        WHERE o.documento_usuario = :doc
    """), engine, params={"doc": documento})
    objetivos = int(resumen_obj.iloc[0]["objetivos"] or 0)
    avance_promedio = float(resumen_obj.iloc[0]["avance_promedio"] or 0)
    novedades = int(resumen_nov.iloc[0]["novedades"] or 0)
    elements.append(Paragraph("RESUMEN EJECUTIVO", styles["Heading2"]))
    elements.append(Spacer(1, 6))

    elements.append(Paragraph(f"Objetivos registrados: {objetivos}", styles["BodyText"]))
    elements.append(Paragraph(f"Avance promedio: {round(avance_promedio, 1)}%", styles["BodyText"]))
    elements.append(Paragraph(f"Novedades registradas: {novedades}", styles["BodyText"]))

    elements.append(Spacer(1, 12))
    # =========================
    # 2. MOVIMIENTOS
    # =========================
    mov_df = pd.read_sql(text("""
        SELECT fecha_movimiento, tipo_movimiento, modalidad, observacion
        FROM movimientos_habitante
        WHERE numero_identificacion::TEXT = :doc
        ORDER BY fecha_movimiento
    """), engine, params={"doc": documento})

    elements.append(Paragraph("2. MOVIMIENTOS", styles["Heading2"]))

    if mov_df.empty:
        elements.append(Paragraph("Sin registros de movimientos", styles["BodyText"]))
    else:
        data = [["Fecha", "Tipo", "Modalidad", "Observación"]]

        for _, r in mov_df.iterrows():
            data.append([
                str(r["fecha_movimiento"]),
                str(r["tipo_movimiento"]),
                str(r["modalidad"]),
                str(r["observacion"])
            ])

        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.grey),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("GRID", (0,0), (-1,-1), 0.5, colors.black),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
        ]))

        elements.append(table)

    elements.append(Spacer(1, 12))

    # =========================
    # 3. PAI REAL
    # =========================
    elements.append(Paragraph("3. PLAN DE ATENCIÓN INDIVIDUAL (PAI)", styles["Heading2"]))

    pai_objetivos_df = pd.read_sql(text("""
        SELECT *
        FROM pai_objetivos
        WHERE documento_usuario = :doc
        ORDER BY fecha_apertura DESC
    """), engine, params={"doc": documento})

    if pai_objetivos_df.empty:
        elements.append(Paragraph("Sin objetivos PAI registrados", styles["BodyText"]))
    else:

        for _, obj in pai_objetivos_df.iterrows():

            elements.append(Spacer(1, 8))

            elements.append(Paragraph(
                f"🎯 {obj['objetivo_tipo']} ({obj['estado']})",
                styles["Heading3"]
            ))

            elements.append(Paragraph(
                f"📅 Apertura: {obj['fecha_apertura']} | Meta: {obj['fecha_meta']}",
                styles["BodyText"]
            ))

            elements.append(Paragraph(
                f"📈 Avance: {obj['porcentaje_avance']}% | ODS: {obj['ods_principal']}",
                styles["BodyText"]
            ))

            elements.append(Paragraph(
                f"🧭 Línea política: {obj['linea_politica']}",
                styles["BodyText"]
            ))

            elements.append(Paragraph(
                f"📝 Descripción: {obj['objetivo_descripcion']}",
                styles["BodyText"]
            ))

            elements.append(Spacer(1, 6))

            # NOVEDADES POR OBJETIVO
            novedades_df = pd.read_sql(text("""
                SELECT *
                FROM pai_novedades
                WHERE id_objetivo = :id
                ORDER BY fecha DESC
            """), engine, params={"id": int(obj["id"])})

            if novedades_df.empty:
                elements.append(Paragraph("Sin novedades registradas", styles["BodyText"]))
            else:

                elements.append(Paragraph("📌 Novedades:", styles["Heading4"]))

                data = [["Fecha", "Profesional", "Tipo", "Descripción", "Avance"]]

                for _, n in novedades_df.iterrows():
                    data.append([
                        str(n["fecha"]),
                        str(n["profesional"]),
                        str(n["tipo_novedad"]),
                        str(n["descripcion"]),
                        str(n["avance_generado"])
                    ])

                table = Table(data)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), colors.darkblue),
                    ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                    ("GRID", (0,0), (-1,-1), 0.5, colors.black),
                    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                    ("FONTSIZE", (0,0), (-1,-1), 7),
                    ("VALIGN", (0,0), (-1,-1), "TOP"),
                ]))

                elements.append(table)
        timeline_df = pd.read_sql(text("""
        SELECT
            o.fecha_apertura AS fecha,
            'OBJETIVO' AS tipo_evento,
            o.objetivo_tipo AS descripcion,
            o.objetivo_descripcion AS detalle
        FROM pai_objetivos o
        WHERE o.documento_usuario = :doc

        UNION ALL

        SELECT
            n.fecha AS fecha,
            n.tipo_novedad AS tipo_evento,
            n.descripcion AS descripcion,
            n.evidencia AS detalle
        FROM pai_novedades n
        JOIN pai_objetivos o ON o.id = n.id_objetivo
        WHERE o.documento_usuario = :doc

        ORDER BY fecha ASC
    """), engine, params={"doc": documento})
        timeline_df["fecha"] = pd.to_datetime(timeline_df["fecha"], errors="coerce")
        timeline_df = timeline_df.dropna(subset=["fecha"])
        elements.append(Paragraph("LÍNEA DE TIEMPO DEL CASO", styles["Heading2"]))
        elements.append(Spacer(1, 6))
        
        for _, r in timeline_df.iterrows():
    
            fecha = r["fecha"].strftime("%Y-%m-%d %H:%M")

            elements.append(Paragraph(
                f"{fecha} | {r['tipo_evento']} | {r['descripcion']}",
                styles["BodyText"]
            ))

            if pd.notnull(r["detalle"]) and str(r["detalle"]).strip():
                elements.append(Paragraph(
                    f"   ➜ {r['detalle']}",
                    styles["BodyText"]
                ))

            elements.append(Spacer(1, 4))
    # =========================
    # FINAL
    # =========================
    doc.build(elements)
    buffer.seek(0)
    return buffer


def gestion_usuarios():

    st.title("👥 Gestión Integral de Usuarios")
    st.caption(
        "Ingreso, actualización operativa, medidas disciplinarias y "
        "completitud progresiva de la caracterización."
    )

    # ========================================================
    # UTILIDADES DE ESQUEMA
    # ========================================================
    @st.cache_data(ttl=300)
    def _columnas_habitante():
        cols = pd.read_sql(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'habitante_de_calle'
            """),
            engine
        )
        return set(cols["column_name"].astype(str).tolist())

    columnas_bd = _columnas_habitante()

    def _col_real(*candidatas):
        for c in candidatas:
            if c in columnas_bd:
                return c
        return None

    def _valor_persona(persona, *candidatas, default=""):
        for c in candidatas:
            if c in persona.index:
                v = persona.get(c)
                if pd.notna(v) and str(v).strip().lower() not in ("", "nan", "none"):
                    return v
        return default

    def _actualizar_campos_persona(documento, cambios):
        """
        cambios = {columna_real: valor}
        Solo usa columnas previamente verificadas contra information_schema.
        """
        cambios = {
            k: v for k, v in cambios.items()
            if k and k in columnas_bd
        }
        if not cambios:
            return False

        asignaciones = []
        params = {"doc": str(documento).strip()}

        for i, (col, valor) in enumerate(cambios.items()):
            param = f"v{i}"
            asignaciones.append(f'"{col}" = :{param}')
            params[param] = valor

        sql = text(
            """
            UPDATE habitante_de_calle
            SET """ + ", ".join(asignaciones) + """
            WHERE TRIM(CAST(numero_identificacion AS TEXT)) = :doc
            """
        )

        with engine.begin() as conn:
            conn.execute(sql, params)

        return True

    # Columnas posibles según las distintas versiones de tu base
    C = {
        "tipo_id": _col_real("tipo_identificacion", "tipo_de_identificacion"),
        "fecha_nacimiento": _col_real(
            "fecha_nacimiento",
            "fecha_de_nacimiento_dd_mm_aa"
        ),
        "salud": _col_real(
            "tipo_seguridad_salud",
            "tipo_de_seguridad_social_en_salud"
        ),
        "telefono": _col_real("telefono", "telefono_y_o_celular"),
        "procedencia": _col_real(
            "departamento_procedencia",
            "departamento_de_procedencia"
        ),
        "consumo": _col_real("tipo_consumo", "tipo_de_consumo"),
        "sisben": _col_real("grupo_sisben"),
        "discapacidad": _col_real("personas_con_discapacidad"),
        "categoria_discapacidad": _col_real("categoria_discapacidad"),
        "cabeza_familia": _col_real("cabeza_de_familia", "cabeza_familia"),
        "gestante": _col_real(
            "mujer_gestante_lactante",
            "mujer_gestante_o_lactante"
        ),
        "migracion": _col_real(
            "experiencia_migratoria",
            "indicador_migracion"
        ),
        "etnia": _col_real(
            "grupos_etnicos",
            "grupos_etnicos_afro_indigena"
        ),
        "educacion": _col_real(
            "nivel_educativo",
            "nivel_educativo_que_tiene_o_cursa"
        ),
        "ocupacion": _col_real(
            "condicion_ocupacional",
            "perfil_ocupacional_su_principal_fuente_de_ingreso_es"
        ),
        "barrio": _col_real(
            "barrio_vereda",
            "barrio_o_vereda_de_residencia"
        ),
        "comuna": _col_real(
            "comuna_corregimiento",
            "comuna_o_corregimiento_de_residencia"
        ),
        "zona": _col_real("zona_residencia"),
        "direccion": _col_real("direccion"),
        "correo": _col_real("correo"),
        "orientacion": _col_real(
            "orientacion_sexual_lgtbi",
            "orientacion_lgbti",
            "orientacion_sexual"
        ),
        "poblacion": _col_real("poblacion"),
        "enfermedad_mental": _col_real("enfermedad_mental"),
        "fecha_ingreso": _col_real("fecha_ingreso_albergue"),
        "numero_atenciones": _col_real("numero_atenciones")
    }

    # ========================================================
    # BASE GENERAL
    # ========================================================
    df_gestion = pd.read_sql(
        text("""
            SELECT *
            FROM habitante_de_calle
            ORDER BY nombres, apellidos
        """),
        engine
    )

    if df_gestion.empty:
        st.warning("No hay usuarios registrados.")
        return

    for columna in ["modalidad", "estado_caso"]:
        if columna not in df_gestion.columns:
            df_gestion[columna] = ""

    df_gestion["modalidad"] = (
        df_gestion["modalidad"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df_gestion["estado_caso"] = (
        df_gestion["estado_caso"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df_gestion["numero_identificacion"] = (
        df_gestion["numero_identificacion"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )

    df_gestion["nombre_completo"] = (
        df_gestion["nombres"].fillna("").astype(str).str.strip()
        + " "
        + df_gestion["apellidos"].fillna("").astype(str).str.strip()
    ).str.strip()

    # ========================================================
    # INDICADORES
    # ========================================================
    total_gestion = len(df_gestion)
    activos_gestion = int(df_gestion["estado_caso"].eq("ACTIVO").sum())
    urbano_gestion = int(
        (
            df_gestion["estado_caso"].eq("ACTIVO")
            & df_gestion["modalidad"].eq("URBANO")
        ).sum()
    )
    granja_gestion = int(
        (
            df_gestion["estado_caso"].eq("ACTIVO")
            & df_gestion["modalidad"].eq("GRANJA")
        ).sum()
    )

    try:
        sanciones_activas = int(
            pd.read_sql(
                text("""
                    SELECT COUNT(*) AS total
                    FROM sanciones_usuarios
                    WHERE UPPER(TRIM(COALESCE(estado_medida,''))) = 'ACTIVA'
                """),
                engine
            ).iloc[0]["total"] or 0
        )
        sanciones_disponibles = True
    except Exception:
        sanciones_activas = 0
        sanciones_disponibles = False

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("👥 Total", total_gestion)
    m2.metric("🟢 Activos", activos_gestion)
    m3.metric("🏙️ Urbano", urbano_gestion)
    m4.metric("🌱 Granja", granja_gestion)
    m5.metric("⛔ Medidas activas", sanciones_activas)

    st.divider()

    tab_consulta, tab_nuevo, tab_caracterizacion, tab_listado = st.tabs([
        "🔎 Consultar / actualizar",
        "➕ Nuevo ingreso",
        "🧾 Completar caracterización",
        "📋 Listado"
    ])

    # ========================================================
    # 1. CONSULTAR / ACTUALIZAR
    # ========================================================
    with tab_consulta:

        indice_usuario = st.selectbox(
            "Buscar por nombre o documento",
            df_gestion.index.tolist(),
            key="gestion_usuario_v9",
            format_func=lambda i: (
                f"{df_gestion.loc[i, 'nombre_completo']} - "
                f"{df_gestion.loc[i, 'numero_identificacion']}"
            )
        )

        persona = df_gestion.loc[indice_usuario]
        documento = str(persona["numero_identificacion"]).strip()

        # PAI breve
        try:
            resumen_pai = pd.read_sql(
                text("""
                    SELECT
                        COUNT(*) AS objetivos,
                        COUNT(*) FILTER (
                            WHERE UPPER(TRIM(COALESCE(estado,''))) = 'CUMPLIDO'
                               OR COALESCE(porcentaje_avance,0) >= 100
                        ) AS cumplidos,
                        COUNT(*) FILTER (
                            WHERE fecha_meta < CURRENT_DATE
                              AND COALESCE(porcentaje_avance,0) < 100
                        ) AS vencidos,
                        MAX(fecha_ultimo_seguimiento) AS ultimo_seguimiento
                    FROM pai_objetivos
                    WHERE TRIM(CAST(documento_usuario AS TEXT)) = :doc
                """),
                engine,
                params={"doc": documento}
            )
        except Exception:
            resumen_pai = pd.DataFrame()

        objetivos = cumplidos = vencidos = 0
        ultimo_seg = None
        if not resumen_pai.empty:
            objetivos = int(resumen_pai.iloc[0]["objetivos"] or 0)
            cumplidos = int(resumen_pai.iloc[0]["cumplidos"] or 0)
            vencidos = int(resumen_pai.iloc[0]["vencidos"] or 0)
            ultimo_seg = resumen_pai.iloc[0]["ultimo_seguimiento"]

        # Completitud rápida
        campos_clave = [
            ("Identificación", "numero_identificacion"),
            ("Sexo", "sexo_al_nacer"),
            ("Edad", "edad"),
            ("Salud", C["salud"]),
            ("Procedencia", C["procedencia"]),
            ("Consumo", C["consumo"]),
            ("Educación", C["educacion"]),
            ("Ocupación", C["ocupacion"]),
            ("Discapacidad", C["discapacidad"]),
            ("Etnia", C["etnia"]),
            ("Residencia", C["barrio"]),
            ("Teléfono", C["telefono"]),
        ]

        completos = 0
        evaluables = 0
        pendientes = []

        for etiqueta, col in campos_clave:
            if not col or col not in persona.index:
                continue
            evaluables += 1
            v = persona.get(col)
            tiene = (
                pd.notna(v)
                and str(v).strip().lower() not in ("", "nan", "none")
            )
            if tiene:
                completos += 1
            else:
                pendientes.append(etiqueta)

        completitud = round(
            completos / evaluables * 100, 1
        ) if evaluables else 0

        st.markdown("### 👤 Ficha rápida")

        f1, f2, f3, f4, f5, f6 = st.columns(6)
        f1.metric("📌 Estado", persona.get("estado_caso", "") or "Sin dato")
        f2.metric("🏠 Modalidad", persona.get("modalidad", "") or "Sin dato")
        f3.metric("🎯 PAI", objetivos)
        f4.metric("🔴 PAI vencidos", vencidos)
        f5.metric("🟢 Cumplidos", cumplidos)
        f6.metric("🧾 Caracterización", f"{completitud:.0f}%")

        if pendientes:
            st.caption("Pendiente por completar: " + ", ".join(pendientes))

        if ultimo_seg is not None and not pd.isna(ultimo_seg):
            st.caption(
                "🕒 Último seguimiento: "
                + pd.to_datetime(ultimo_seg).strftime("%d/%m/%Y %H:%M")
            )

        # ----------------------------------------------------
        # ACTUALIZACIÓN OPERATIVA
        # ----------------------------------------------------
        st.markdown("### ✏️ Estado y modalidad")

        a1, a2, a3 = st.columns(3)

        estados_disponibles = ["ACTIVO", "INACTIVO", "EGRESADO"]
        estado_actual = (
            persona.get("estado_caso", "")
            if persona.get("estado_caso", "") in estados_disponibles
            else "ACTIVO"
        )

        modalidades = ["URBANO", "GRANJA"]
        modalidad_actual = persona.get("modalidad", "")

        nuevo_estado = a1.selectbox(
            "Estado",
            estados_disponibles,
            index=estados_disponibles.index(estado_actual),
            key=f"gestion_estado_v9_{documento}"
        )

        nueva_modalidad = a2.selectbox(
            "Modalidad",
            modalidades,
            index=(
                modalidades.index(modalidad_actual)
                if modalidad_actual in modalidades
                else 0
            ),
            key=f"gestion_modalidad_v9_{documento}"
        )

        with a3:
            st.write("")
            st.write("")
            guardar_cambios = st.button(
                "💾 Guardar cambios",
                key=f"gestion_guardar_v9_{documento}",
                use_container_width=True
            )

        if guardar_cambios:
            estado_anterior = str(persona.get("estado_caso", "") or "")
            modalidad_anterior = str(persona.get("modalidad", "") or "")

            if (
                nuevo_estado == estado_anterior
                and nueva_modalidad == modalidad_anterior
            ):
                st.info("No hay cambios para guardar.")
            else:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            UPDATE habitante_de_calle
                            SET estado_caso = :estado,
                                modalidad = :modalidad
                            WHERE TRIM(
                                CAST(numero_identificacion AS TEXT)
                            ) = :doc
                        """),
                        {
                            "estado": nuevo_estado,
                            "modalidad": nueva_modalidad,
                            "doc": documento
                        }
                    )

                    conn.execute(
                        text("""
                            INSERT INTO movimientos_habitante (
                                numero_identificacion,
                                tipo_movimiento,
                                modalidad,
                                usuario_registra,
                                observacion
                            )
                            VALUES (
                                :doc,
                                'ACTUALIZACION_USUARIO',
                                :modalidad,
                                :usuario,
                                :observacion
                            )
                        """),
                        {
                            "doc": documento,
                            "modalidad": nueva_modalidad,
                            "usuario": st.session_state.get(
                                "usuario_actual", "sistema"
                            ),
                            "observacion": (
                                f"Estado {estado_anterior} -> {nuevo_estado}; "
                                f"modalidad {modalidad_anterior} -> {nueva_modalidad}"
                            )
                        }
                    )

                registrar_auditoria(
                    "ACTUALIZAR_USUARIO",
                    documento=documento,
                    modulo="Gestión Usuarios",
                    valor_anterior=(
                        f"Estado={estado_anterior}; Modalidad={modalidad_anterior}"
                    ),
                    valor_nuevo=(
                        f"Estado={nuevo_estado}; Modalidad={nueva_modalidad}"
                    )
                )

                invalidar_cache_datos()
                st.success("✅ Usuario actualizado.")
                st.rerun()

        # ----------------------------------------------------
        # EGRESO ESTRUCTURADO
        # ----------------------------------------------------
        st.divider()
        st.markdown("### 🏆 Registrar egreso")
        st.caption(
            "El egreso se registra en la base de egresos y, al mismo tiempo, "
            "actualiza el estado del usuario en habitante_de_calle. "
            "No se confunde con suspensión o expulsión."
        )

        # Detectar estructura real de la tabla de egresos.
        @st.cache_data(ttl=300)
        def _columnas_tabla_egresos():
            cols = pd.read_sql(
                text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'personas_caracterizacion'
                """),
                engine
            )
            return set(cols["column_name"].astype(str).tolist())

        columnas_egreso = _columnas_tabla_egresos()

        def _col_egreso(*candidatas):
            for c in candidatas:
                if c in columnas_egreso:
                    return c
            return None

        # Columnas observadas en la tabla/archivo de egresos
        CE = {
            "numero": _col_egreso("numero"),
            "cedula_validada": _col_egreso("cedula_validada"),
            "mes_validacion": _col_egreso("mes_validacion"),
            "nombres": _col_egreso("nombres"),
            "apellidos": _col_egreso("apellidos"),
            "sexo_nacer": _col_egreso("sexo_nacer", "sexo_al_nacer"),
            "edad": _col_egreso("edad"),
            "fecha_nacimiento": _col_egreso("fecha_nacimiento"),
            "numero_identidad": _col_egreso(
                "numero_identidad",
                "numero_identificacion"
            ),
            "categoria_discapacidad": _col_egreso("categoria_discapacidad"),
            "se_reconoce_como": _col_egreso("se_reconoce_como"),
            "orientacion_lgbti": _col_egreso(
                "orientacion_lgbti",
                "orientacion_sexual_lgtbi"
            ),
            "grupo_etnico": _col_egreso("grupo_etnico", "grupos_etnicos"),
            "departamento_procedencia": _col_egreso(
                "departamento_procedencia"
            ),
            "estado_caso": _col_egreso("estado_caso"),
            "fecha_egreso": _col_egreso("fecha_egreso"),
            "observaciones_egreso": _col_egreso("observaciones_egreso"),
            "funcionario_egreso": _col_egreso("funcionario_egreso")
        }

        if not columnas_egreso:
            st.warning(
                "No fue posible leer la estructura de personas_caracterizacion."
            )
        else:
            # Verificar si ya tiene un egreso registrado
            try:
                col_doc_busqueda = CE["numero_identidad"]
                if col_doc_busqueda:
                    egresos_previos = pd.read_sql(
                        text(
                            f"""
                            SELECT *
                            FROM personas_caracterizacion
                            WHERE TRIM(CAST("{col_doc_busqueda}" AS TEXT)) = :doc
                            ORDER BY
                                {
                                    '"fecha_egreso" DESC'
                                    if CE["fecha_egreso"]
                                    else "1"
                                }
                            """
                        ),
                        engine,
                        params={"doc": documento}
                    )
                else:
                    egresos_previos = pd.DataFrame()
            except Exception:
                egresos_previos = pd.DataFrame()

            if not egresos_previos.empty:
                st.info(
                    f"ℹ️ Esta persona ya tiene {len(egresos_previos)} "
                    "registro(s) histórico(s) de egreso."
                )
                with st.expander("📚 Ver egresos anteriores"):
                    cols_ver = [
                        c for c in [
                            CE["fecha_egreso"],
                            CE["observaciones_egreso"],
                            CE["funcionario_egreso"],
                            CE["estado_caso"]
                        ]
                        if c
                    ]
                    if cols_ver:
                        st.dataframe(
                            egresos_previos[cols_ver],
                            use_container_width=True,
                            hide_index=True
                        )

            with st.form(f"form_egreso_v10_{documento}"):

                eg1, eg2, eg3 = st.columns(3)

                fecha_egreso_form = eg1.date_input(
                    "Fecha de egreso *",
                    value=date.today()
                )

                cedula_validada_form = eg2.selectbox(
                    "Cédula validada",
                    ["SÍ", "NO", "NO APLICA"],
                    index=0
                )

                funcionario_default = st.session_state.get(
                    "usuario_actual", ""
                )
                funcionario_egreso_form = eg3.text_input(
                    "Funcionario que registra *",
                    value=(
                        ""
                        if funcionario_default == "sistema"
                        else str(funcionario_default)
                    )
                )

                st.markdown("#### Resultado / motivo del egreso")

                opciones_egreso = [
                    "PLAN RETORNO",
                    "VINCULACIÓN FAMILIAR",
                    "VINCULACIÓN LABORAL",
                    "TRASLADO A CENTRO DE PROTECCIÓN",
                    "INGRESO A TRATAMIENTO",
                    "AUTONOMÍA / SUPERACIÓN DE VIDA EN CALLE",
                    "OTRO"
                ]

                motivo_egreso_form = st.selectbox(
                    "Tipo de egreso *",
                    opciones_egreso
                )

                detalle_egreso_form = st.text_area(
                    "Observaciones del egreso",
                    placeholder=(
                        "Amplíe la información cuando sea necesario: "
                        "destino, institución, familiar, empleador, etc."
                    )
                )

                confirmar_egreso = st.checkbox(
                    "Confirmo que corresponde a un egreso real y no a una sanción o expulsión."
                )

                guardar_egreso = st.form_submit_button(
                    "🏆 Registrar egreso",
                    use_container_width=True,
                    type="primary"
                )

            if guardar_egreso:

                if not funcionario_egreso_form.strip():
                    st.error("Debe indicar el funcionario que registra el egreso.")
                elif not confirmar_egreso:
                    st.error(
                        "Debe confirmar que corresponde a un egreso real."
                    )
                else:
                    meses_es = {
                        1: "ENERO",
                        2: "FEBRERO",
                        3: "MARZO",
                        4: "ABRIL",
                        5: "MAYO",
                        6: "JUNIO",
                        7: "JULIO",
                        8: "AGOSTO",
                        9: "SEPTIEMBRE",
                        10: "OCTUBRE",
                        11: "NOVIEMBRE",
                        12: "DICIEMBRE"
                    }

                    # Datos tomados automáticamente de habitante_de_calle
                    def _p(*candidatas, default=None):
                        for c in candidatas:
                            if c and c in persona.index:
                                v = persona.get(c)
                                if pd.notna(v):
                                    return v
                        return default

                    observacion_final = motivo_egreso_form.strip()
                    if detalle_egreso_form.strip():
                        observacion_final += " - " + detalle_egreso_form.strip()

                    datos_egreso = {
                        CE["cedula_validada"]: cedula_validada_form,
                        CE["mes_validacion"]: meses_es[fecha_egreso_form.month],
                        CE["nombres"]: _p("nombres", default=""),
                        CE["apellidos"]: _p("apellidos", default=""),
                        CE["sexo_nacer"]: _p(
                            "sexo_al_nacer",
                            "sexo_nacer",
                            default=""
                        ),
                        CE["edad"]: _p("edad"),
                        CE["fecha_nacimiento"]: _p(
                            "fecha_nacimiento",
                            "fecha_de_nacimiento_dd_mm_aa"
                        ),
                        CE["numero_identidad"]: documento,
                        CE["categoria_discapacidad"]: _p(
                            "categoria_discapacidad",
                            default=""
                        ),
                        CE["se_reconoce_como"]: _p(
                            "se_reconoce_como",
                            default=""
                        ),
                        CE["orientacion_lgbti"]: _p(
                            "orientacion_sexual_lgtbi",
                            "orientacion_lgbti",
                            "orientacion_sexual",
                            default=""
                        ),
                        CE["grupo_etnico"]: _p(
                            "grupos_etnicos",
                            "grupo_etnico",
                            default=""
                        ),
                        CE["departamento_procedencia"]: _p(
                            "departamento_procedencia",
                            "departamento_de_procedencia",
                            default=""
                        ),
                        CE["estado_caso"]: "EGRESADO",
                        CE["fecha_egreso"]: fecha_egreso_form,
                        CE["observaciones_egreso"]: observacion_final,
                        CE["funcionario_egreso"]: funcionario_egreso_form.strip()
                    }

                    # Si la tabla usa una columna consecutiva "numero",
                    # obtener el siguiente valor de forma segura dentro de la transacción.
                    with engine.begin() as conn:

                        if CE["numero"]:
                            siguiente_numero = conn.execute(
                                text("""
                                    SELECT COALESCE(MAX(numero), 0) + 1
                                    FROM personas_caracterizacion
                                """)
                            ).scalar()
                            datos_egreso[CE["numero"]] = siguiente_numero

                        datos_egreso = {
                            k: v for k, v in datos_egreso.items()
                            if k and k in columnas_egreso
                        }

                        cols_ins = list(datos_egreso.keys())
                        params_ins = {}
                        valores_ins = []

                        for i, col in enumerate(cols_ins):
                            par = f"e{i}"
                            valores_ins.append(f":{par}")
                            params_ins[par] = datos_egreso[col]

                        sql_egreso = text(
                            "INSERT INTO personas_caracterizacion ("
                            + ", ".join(f'"{c}"' for c in cols_ins)
                            + ") VALUES ("
                            + ", ".join(valores_ins)
                            + ")"
                        )

                        conn.execute(sql_egreso, params_ins)

                        # Actualizar base general sin borrar la persona
                        sets_estado = [
                            "estado_caso = 'EGRESADO'",
                            "modalidad = NULL"
                        ]

                        if "fecha_ultimo_egreso" in columnas_bd:
                            sets_estado.append(
                                "fecha_ultimo_egreso = :fecha_egreso"
                            )

                        conn.execute(
                            text(
                                """
                                UPDATE habitante_de_calle
                                SET """ + ", ".join(sets_estado) + """
                                WHERE TRIM(
                                    CAST(numero_identificacion AS TEXT)
                                ) = :doc
                                """
                            ),
                            {
                                "doc": documento,
                                "fecha_egreso": fecha_egreso_form
                            }
                        )

                        # Movimiento institucional
                        conn.execute(
                            text("""
                                INSERT INTO movimientos_habitante (
                                    numero_identificacion,
                                    tipo_movimiento,
                                    modalidad,
                                    usuario_registra,
                                    observacion
                                )
                                VALUES (
                                    :doc,
                                    'EGRESO',
                                    :modalidad,
                                    :usuario,
                                    :observacion
                                )
                            """),
                            {
                                "doc": documento,
                                "modalidad": modalidad_actual or None,
                                "usuario": funcionario_egreso_form.strip(),
                                "observacion": observacion_final
                            }
                        )

                    registrar_auditoria(
                        "REGISTRAR_EGRESO",
                        documento=documento,
                        modulo="Gestión Usuarios",
                        valor_anterior=str(
                            persona.get("estado_caso", "") or ""
                        ),
                        valor_nuevo="EGRESADO",
                        observacion=observacion_final[:500]
                    )

                    _columnas_tabla_egresos.clear()
                    invalidar_cache_datos()

                    st.success(
                        "✅ Egreso registrado en personas_caracterizacion, "
                        "habitante_de_calle y movimientos_habitante."
                    )
                    st.rerun()

        # ----------------------------------------------------
        # MEDIDAS DISCIPLINARIAS
        # ----------------------------------------------------
        st.divider()
        st.markdown("### ⛔ Suspensiones y expulsiones")
        st.caption(
            "Los llamados de atención continúan manejándose mediante actas. "
            "Aquí solo se registran medidas que afectan la permanencia del usuario."
        )

        if not sanciones_disponibles:
            st.warning(
                "Falta crear la tabla sanciones_usuarios. "
                "Ejecuta el SQL de migración V9 una sola vez en Supabase."
            )
        else:
            try:
                historial_medidas = pd.read_sql(
                    text("""
                        SELECT
                            id,
                            tipo_medida,
                            motivo,
                            fecha_inicio,
                            fecha_fin,
                            estado_medida,
                            observacion,
                            usuario_registra,
                            creado_en
                        FROM sanciones_usuarios
                        WHERE TRIM(
                            CAST(numero_identificacion AS TEXT)
                        ) = :doc
                        ORDER BY creado_en DESC
                    """),
                    engine,
                    params={"doc": documento}
                )
            except Exception:
                historial_medidas = pd.DataFrame()

            if not historial_medidas.empty:
                activas_persona = historial_medidas[
                    historial_medidas["estado_medida"]
                    .fillna("")
                    .astype(str)
                    .str.upper()
                    .eq("ACTIVA")
                ]
                if not activas_persona.empty:
                    st.error(
                        f"⛔ Esta persona tiene {len(activas_persona)} "
                        "medida(s) activa(s)."
                    )

                with st.expander("📚 Ver historial de medidas"):
                    st.dataframe(
                        historial_medidas,
                        use_container_width=True,
                        hide_index=True
                    )

            with st.form(f"medida_v9_{documento}"):

                s1, s2, s3 = st.columns(3)

                tipo_medida = s1.selectbox(
                    "Medida",
                    ["SUSPENSIÓN", "EXPULSIÓN"]
                )

                fecha_inicio_medida = s2.date_input(
                    "Fecha de inicio",
                    value=date.today()
                )

                fecha_fin_medida = s3.date_input(
                    "Fecha de finalización",
                    value=date.today() + timedelta(days=3),
                    help=(
                        "Para expulsión puede usarse como fecha de revisión "
                        "si la medida no tiene término definido."
                    )
                )

                motivo_medida = st.text_area(
                    "Motivo de la medida *",
                    placeholder="Describa el hecho o causal que sustenta la medida."
                )

                observacion_medida = st.text_area(
                    "Observación adicional"
                )

                confirmar_medida = st.checkbox(
                    "Confirmo que la medida fue definida conforme al procedimiento institucional."
                )

                guardar_medida = st.form_submit_button(
                    "⛔ Registrar medida",
                    use_container_width=True
                )

            if guardar_medida:
                if not motivo_medida.strip():
                    st.error("Debe registrar el motivo de la medida.")
                elif not confirmar_medida:
                    st.error("Debe confirmar la aplicación de la medida.")
                elif fecha_fin_medida < fecha_inicio_medida:
                    st.error(
                        "La fecha final no puede ser anterior a la fecha inicial."
                    )
                else:
                    usuario_registra = st.session_state.get(
                        "usuario_actual", "sistema"
                    )

                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                INSERT INTO sanciones_usuarios (
                                    numero_identificacion,
                                    tipo_medida,
                                    motivo,
                                    fecha_inicio,
                                    fecha_fin,
                                    estado_medida,
                                    observacion,
                                    usuario_registra
                                )
                                VALUES (
                                    :doc,
                                    :tipo,
                                    :motivo,
                                    :inicio,
                                    :fin,
                                    'ACTIVA',
                                    :observacion,
                                    :usuario
                                )
                            """),
                            {
                                "doc": documento,
                                "tipo": tipo_medida,
                                "motivo": motivo_medida.strip(),
                                "inicio": fecha_inicio_medida,
                                "fin": fecha_fin_medida,
                                "observacion": observacion_medida.strip(),
                                "usuario": usuario_registra
                            }
                        )

                        # La medida afecta permanencia, pero NO se registra como
                        # "egreso exitoso". Se conserva diferenciación conceptual.
                        conn.execute(
                            text("""
                                UPDATE habitante_de_calle
                                SET estado_caso = 'INACTIVO',
                                    modalidad = NULL
                                WHERE TRIM(
                                    CAST(numero_identificacion AS TEXT)
                                ) = :doc
                            """),
                            {"doc": documento}
                        )

                        conn.execute(
                            text("""
                                INSERT INTO movimientos_habitante (
                                    numero_identificacion,
                                    tipo_movimiento,
                                    modalidad,
                                    usuario_registra,
                                    observacion
                                )
                                VALUES (
                                    :doc,
                                    :tipo_mov,
                                    :modalidad,
                                    :usuario,
                                    :observacion
                                )
                            """),
                            {
                                "doc": documento,
                                "tipo_mov": (
                                    "SUSPENSION"
                                    if tipo_medida == "SUSPENSIÓN"
                                    else "EXPULSION"
                                ),
                                "modalidad": modalidad_actual or None,
                                "usuario": usuario_registra,
                                "observacion": motivo_medida.strip()
                            }
                        )

                    registrar_auditoria(
                        "REGISTRAR_MEDIDA_DISCIPLINARIA",
                        documento=documento,
                        modulo="Gestión Usuarios",
                        valor_nuevo=tipo_medida,
                        observacion=motivo_medida.strip()[:500]
                    )

                    invalidar_cache_datos()
                    st.success(
                        f"✅ {tipo_medida.title()} registrada. "
                        "El usuario quedó INACTIVO y la medida conserva trazabilidad."
                    )
                    st.rerun()

            # Cerrar / levantar medidas activas
            if not historial_medidas.empty:
                activas = historial_medidas[
                    historial_medidas["estado_medida"]
                    .fillna("")
                    .astype(str)
                    .str.upper()
                    .eq("ACTIVA")
                ]

                if not activas.empty:
                    st.markdown("#### ✅ Cerrar o levantar medida")

                    id_medida = st.selectbox(
                        "Medida activa",
                        activas["id"].tolist(),
                        key=f"medida_activa_{documento}",
                        format_func=lambda x: (
                            f"#{x} - "
                            + str(
                                activas.loc[
                                    activas["id"] == x,
                                    "tipo_medida"
                                ].iloc[0]
                            )
                        )
                    )

                    estado_cierre = st.selectbox(
                        "Resultado",
                        ["CUMPLIDA", "REVOCADA"],
                        key=f"resultado_medida_{documento}"
                    )

                    reactivar_usuario = st.checkbox(
                        "Reactivar usuario al cerrar la medida",
                        value=False,
                        key=f"reactivar_medida_{documento}"
                    )

                    if st.button(
                        "✅ Cerrar medida",
                        key=f"cerrar_medida_{documento}"
                    ):
                        with engine.begin() as conn:
                            conn.execute(
                                text("""
                                    UPDATE sanciones_usuarios
                                    SET estado_medida = :estado,
                                        cerrado_en = NOW()
                                    WHERE id = :id
                                """),
                                {
                                    "estado": estado_cierre,
                                    "id": int(id_medida)
                                }
                            )

                            if reactivar_usuario:
                                conn.execute(
                                    text("""
                                        UPDATE habitante_de_calle
                                        SET estado_caso = 'ACTIVO'
                                        WHERE TRIM(
                                            CAST(numero_identificacion AS TEXT)
                                        ) = :doc
                                    """),
                                    {"doc": documento}
                                )

                                conn.execute(
                                    text("""
                                        INSERT INTO movimientos_habitante (
                                            numero_identificacion,
                                            tipo_movimiento,
                                            modalidad,
                                            usuario_registra,
                                            observacion
                                        )
                                        VALUES (
                                            :doc,
                                            'REACTIVACION_POST_MEDIDA',
                                            NULL,
                                            :usuario,
                                            :observacion
                                        )
                                    """),
                                    {
                                        "doc": documento,
                                        "usuario": st.session_state.get(
                                            "usuario_actual", "sistema"
                                        ),
                                        "observacion": (
                                            f"Medida #{id_medida} cerrada como "
                                            f"{estado_cierre}"
                                        )
                                    }
                                )

                        registrar_auditoria(
                            "CERRAR_MEDIDA_DISCIPLINARIA",
                            documento=documento,
                            modulo="Gestión Usuarios",
                            valor_nuevo=estado_cierre,
                            observacion=f"Medida #{id_medida}"
                        )

                        invalidar_cache_datos()
                        st.success("✅ Medida actualizada.")
                        st.rerun()

        # ----------------------------------------------------
        # HISTORIA BREVE
        # ----------------------------------------------------
        st.divider()
        e1, e2, e3 = st.columns(3)

        with e1:
            with st.expander("📝 Últimos seguimientos"):
                try:
                    nov = pd.read_sql(
                        text("""
                            SELECT
                                n.fecha,
                                n.profesional,
                                o.objetivo_tipo,
                                n.tipo_novedad,
                                n.descripcion
                            FROM pai_novedades n
                            INNER JOIN pai_objetivos o
                                ON o.id = n.id_objetivo
                            WHERE TRIM(
                                CAST(o.documento_usuario AS TEXT)
                            ) = :doc
                            ORDER BY n.fecha DESC
                            LIMIT 10
                        """),
                        engine,
                        params={"doc": documento}
                    )
                    if nov.empty:
                        st.caption("Sin seguimientos.")
                    else:
                        st.dataframe(nov, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.caption(str(e))

        with e2:
            with st.expander("🔄 Movimientos recientes"):
                try:
                    mov = pd.read_sql(
                        text("""
                            SELECT
                                fecha_movimiento,
                                tipo_movimiento,
                                modalidad,
                                observacion
                            FROM movimientos_habitante
                            WHERE TRIM(
                                CAST(numero_identificacion AS TEXT)
                            ) = :doc
                            ORDER BY fecha_movimiento DESC
                            LIMIT 10
                        """),
                        engine,
                        params={"doc": documento}
                    )
                    if mov.empty:
                        st.caption("Sin movimientos.")
                    else:
                        st.dataframe(mov, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.caption(str(e))

        with e3:
            with st.expander("🎯 Objetivos PAI"):
                try:
                    pai_u = pd.read_sql(
                        text("""
                            SELECT
                                objetivo_tipo,
                                porcentaje_avance,
                                estado,
                                fecha_meta,
                                fecha_ultimo_seguimiento
                            FROM pai_objetivos
                            WHERE TRIM(
                                CAST(documento_usuario AS TEXT)
                            ) = :doc
                            ORDER BY fecha_meta NULLS LAST
                        """),
                        engine,
                        params={"doc": documento}
                    )
                    if pai_u.empty:
                        st.caption("Sin objetivos PAI.")
                    else:
                        st.dataframe(pai_u, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.caption(str(e))

    # ========================================================
    # 2. NUEVO INGRESO
    # ========================================================
    with tab_nuevo:

        st.subheader("➕ Registro inicial")
        st.caption(
            "Se capturan los datos necesarios para operar el ingreso. "
            "La caracterización social completa puede terminarse posteriormente."
        )

        with st.form("nuevo_usuario_v9"):

            n1, n2, n3 = st.columns(3)
            nombres_n = n1.text_input("Nombres *")
            apellidos_n = n2.text_input("Apellidos *")
            numero_n = n3.text_input("Número de identificación *")

            n4, n5, n6 = st.columns(3)

            tipo_n = n4.selectbox(
                "Tipo identificación",
                ["CC", "TI", "CE", "PEP", "PPT", "Otro"]
            )

            sexo_n = n5.selectbox(
                "Sexo al nacer",
                ["Masculino", "Femenino"]
            )

            fecha_nac_n = n6.date_input(
                "Fecha de nacimiento",
                value=date.today() - timedelta(days=30 * 365)
            )

            n7, n8, n9 = st.columns(3)

            modalidad_n = n7.selectbox(
                "Modalidad",
                ["URBANO", "GRANJA"]
            )

            salud_n = n8.selectbox(
                "Seguridad social",
                [
                    "Subsidiado",
                    "Contributivo",
                    "Especial",
                    "No afiliado",
                    "Sin información"
                ]
            )

            procedencia_n = n9.text_input(
                "Departamento / lugar de procedencia *",
                placeholder="Ej. Risaralda, Caldas, Valle del Cauca"
            )

            n10, n11 = st.columns(2)

            consumo_n = n10.selectbox(
                "Consumo principal",
                [
                    "No refiere consumo",
                    "Alcohol",
                    "Marihuana",
                    "Bazuco",
                    "Cocaína",
                    "Heroína",
                    "Inhalables",
                    "Medicamentos sin fórmula",
                    "Policonsumo",
                    "Otro",
                    "Sin información"
                ]
            )

            telefono_n = n11.text_input("Teléfono")

            guardar_n = st.form_submit_button(
                "💾 Registrar ingreso",
                use_container_width=True,
                type="primary"
            )

        if guardar_n:

            doc_n = limpiar_documento(numero_n)

            if (
                not nombres_n.strip()
                or not apellidos_n.strip()
                or not doc_n
                or not procedencia_n.strip()
            ):
                st.error(
                    "Nombres, apellidos, identificación y procedencia son obligatorios."
                )
            else:
                valido, mensaje = validar_documento_no_duplicado(doc_n)

                if not valido:
                    st.error(mensaje)
                else:
                    edad_n = max(
                        0,
                        date.today().year
                        - fecha_nac_n.year
                        - (
                            (date.today().month, date.today().day)
                            < (fecha_nac_n.month, fecha_nac_n.day)
                        )
                    )

                    # INSERT dinámico: usa solamente columnas que realmente existen.
                    datos_insert = {
                        "nombres": nombres_n.strip(),
                        "apellidos": apellidos_n.strip(),
                        "sexo_al_nacer": sexo_n,
                        "edad": edad_n,
                        "numero_identificacion": doc_n,
                        "estado_caso": "ACTIVO",
                        "modalidad": modalidad_n
                    }

                    opcionales = {
                        C["tipo_id"]: tipo_n,
                        C["fecha_nacimiento"]: fecha_nac_n,
                        C["salud"]: salud_n,
                        C["telefono"]: telefono_n.strip(),
                        C["procedencia"]: procedencia_n.strip(),
                        C["consumo"]: consumo_n,
                        C["fecha_ingreso"]: date.today(),
                        C["numero_atenciones"]: 0
                    }

                    for col, val in opcionales.items():
                        if col:
                            datos_insert[col] = val

                    cols_insert = [
                        c for c in datos_insert.keys()
                        if c in columnas_bd
                    ]

                    params_insert = {}
                    placeholders = []

                    for i, col in enumerate(cols_insert):
                        p = f"p{i}"
                        placeholders.append(f":{p}")
                        params_insert[p] = datos_insert[col]

                    sql_insert = text(
                        "INSERT INTO habitante_de_calle ("
                        + ", ".join(f'"{c}"' for c in cols_insert)
                        + ") VALUES ("
                        + ", ".join(placeholders)
                        + ")"
                    )

                    with engine.begin() as conn:
                        conn.execute(sql_insert, params_insert)

                        conn.execute(
                            text("""
                                INSERT INTO movimientos_habitante (
                                    numero_identificacion,
                                    tipo_movimiento,
                                    modalidad,
                                    usuario_registra,
                                    observacion
                                )
                                VALUES (
                                    :doc,
                                    'INGRESO',
                                    :modalidad,
                                    :usuario,
                                    'Registro inicial desde Gestión Integral'
                                )
                            """),
                            {
                                "doc": doc_n,
                                "modalidad": modalidad_n,
                                "usuario": st.session_state.get(
                                    "usuario_actual", "sistema"
                                )
                            }
                        )

                    registrar_auditoria(
                        "CREAR_USUARIO",
                        documento=doc_n,
                        modulo="Gestión Usuarios",
                        valor_nuevo=(
                            f"{nombres_n.strip()} {apellidos_n.strip()} - "
                            f"{modalidad_n}; procedencia={procedencia_n.strip()}; "
                            f"consumo={consumo_n}"
                        )
                    )

                    _columnas_habitante.clear()
                    invalidar_cache_datos()

                    st.success(
                        "✅ Usuario registrado. "
                        "Ahora puede completarse la caracterización social."
                    )
                    st.rerun()

    # ========================================================
    # 3. COMPLETAR CARACTERIZACIÓN
    # ========================================================
    with tab_caracterizacion:

        st.subheader("🧾 Caracterización progresiva")
        st.caption(
            "Permite completar los campos sociales sin exigir toda la información "
            "en el momento del ingreso."
        )

        indice_car = st.selectbox(
            "Seleccione usuario",
            df_gestion.index.tolist(),
            key="caracterizacion_usuario_v9",
            format_func=lambda i: (
                f"{df_gestion.loc[i, 'nombre_completo']} - "
                f"{df_gestion.loc[i, 'numero_identificacion']}"
            )
        )

        persona_car = df_gestion.loc[indice_car]
        doc_car = str(persona_car["numero_identificacion"]).strip()

        campos_control = [
            ("Salud", C["salud"]),
            ("Procedencia", C["procedencia"]),
            ("Consumo", C["consumo"]),
            ("SISBÉN", C["sisben"]),
            ("Discapacidad", C["discapacidad"]),
            ("Etnia", C["etnia"]),
            ("Educación", C["educacion"]),
            ("Ocupación", C["ocupacion"]),
            ("Barrio / vereda", C["barrio"]),
            ("Comuna", C["comuna"]),
            ("Teléfono", C["telefono"]),
            ("Orientación sexual", C["orientacion"]),
            ("Población diferencial", C["poblacion"]),
            ("Salud mental", C["enfermedad_mental"])
        ]

        pendientes_car = []
        completos_car = 0
        total_car = 0

        for etiqueta, col in campos_control:
            if not col or col not in persona_car.index:
                continue
            total_car += 1
            v = persona_car.get(col)
            tiene = (
                pd.notna(v)
                and str(v).strip().lower() not in ("", "nan", "none")
            )
            if tiene:
                completos_car += 1
            else:
                pendientes_car.append(etiqueta)

        pct_car = round(
            completos_car / total_car * 100, 1
        ) if total_car else 0

        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("🧾 Completitud", f"{pct_car:.0f}%")
        cc2.metric("✅ Campos completos", completos_car)
        cc3.metric("⚠️ Pendientes", len(pendientes_car))

        st.progress(min(max(pct_car / 100, 0), 1))

        if pendientes_car:
            st.warning(
                "Pendiente: " + ", ".join(pendientes_car)
            )
        else:
            st.success("✅ Caracterización prioritaria completa.")

        with st.form(f"completar_caracterizacion_v9_{doc_car}"):

            st.markdown("#### 🧍 Datos sociales y diferenciales")

            c1, c2, c3 = st.columns(3)

            sisben_car = c1.text_input(
                "Grupo SISBÉN",
                value=str(_valor_persona(
                    persona_car,
                    C["sisben"] if C["sisben"] else "__none__"
                ))
            )

            discapacidad_actual = str(_valor_persona(
                persona_car,
                C["discapacidad"] if C["discapacidad"] else "__none__",
                default="No"
            ))
            discapacidad_car = c2.selectbox(
                "Persona con discapacidad",
                ["No", "Sí"],
                index=1 if discapacidad_actual.strip().lower() in ("sí", "si", "1", "true") else 0
            )

            categoria_disc_car = c3.text_input(
                "Categoría de discapacidad",
                value=str(_valor_persona(
                    persona_car,
                    C["categoria_discapacidad"]
                    if C["categoria_discapacidad"] else "__none__"
                ))
            )

            c4, c5, c6 = st.columns(3)

            cabeza_actual = str(_valor_persona(
                persona_car,
                C["cabeza_familia"] if C["cabeza_familia"] else "__none__",
                default="No"
            ))
            cabeza_car = c4.selectbox(
                "Cabeza de familia",
                ["No", "Sí"],
                index=1 if cabeza_actual.strip().lower() in ("sí", "si", "1", "true") else 0
            )

            gestante_actual = str(_valor_persona(
                persona_car,
                C["gestante"] if C["gestante"] else "__none__",
                default="No"
            ))
            gestante_car = c5.selectbox(
                "Gestante / lactante",
                ["No", "Sí", "No aplica"],
                index=(
                    1 if gestante_actual.strip().lower() in ("sí", "si", "1", "true")
                    else 2 if "aplica" in gestante_actual.lower()
                    else 0
                )
            )

            migracion_car = c6.text_input(
                "Experiencia migratoria",
                value=str(_valor_persona(
                    persona_car,
                    C["migracion"] if C["migracion"] else "__none__"
                ))
            )

            st.markdown("#### 🎓 Educación, ocupación y procedencia")

            c7, c8, c9 = st.columns(3)

            educacion_car = c7.text_input(
                "Nivel educativo",
                value=str(_valor_persona(
                    persona_car,
                    C["educacion"] if C["educacion"] else "__none__"
                ))
            )

            ocupacion_car = c8.text_input(
                "Condición / perfil ocupacional",
                value=str(_valor_persona(
                    persona_car,
                    C["ocupacion"] if C["ocupacion"] else "__none__"
                ))
            )

            procedencia_car = c9.text_input(
                "Departamento / lugar de procedencia",
                value=str(_valor_persona(
                    persona_car,
                    C["procedencia"] if C["procedencia"] else "__none__"
                ))
            )

            st.markdown("#### 🏠 Residencia y contacto")

            c10, c11, c12 = st.columns(3)

            barrio_car = c10.text_input(
                "Barrio / vereda",
                value=str(_valor_persona(
                    persona_car,
                    C["barrio"] if C["barrio"] else "__none__"
                ))
            )

            comuna_car = c11.text_input(
                "Comuna / corregimiento",
                value=str(_valor_persona(
                    persona_car,
                    C["comuna"] if C["comuna"] else "__none__"
                ))
            )

            zona_car = c12.text_input(
                "Zona de residencia",
                value=str(_valor_persona(
                    persona_car,
                    C["zona"] if C["zona"] else "__none__"
                ))
            )

            c13, c14, c15 = st.columns(3)

            direccion_car = c13.text_input(
                "Dirección",
                value=str(_valor_persona(
                    persona_car,
                    C["direccion"] if C["direccion"] else "__none__"
                ))
            )

            telefono_car = c14.text_input(
                "Teléfono",
                value=str(_valor_persona(
                    persona_car,
                    C["telefono"] if C["telefono"] else "__none__"
                ))
            )

            correo_car = c15.text_input(
                "Correo",
                value=str(_valor_persona(
                    persona_car,
                    C["correo"] if C["correo"] else "__none__"
                ))
            )

            st.markdown("#### 🩺 Salud, consumo y diversidad")

            c16, c17, c18 = st.columns(3)

            salud_car = c16.text_input(
                "Seguridad social en salud",
                value=str(_valor_persona(
                    persona_car,
                    C["salud"] if C["salud"] else "__none__"
                ))
            )

            consumo_car = c17.text_input(
                "Tipo de consumo",
                value=str(_valor_persona(
                    persona_car,
                    C["consumo"] if C["consumo"] else "__none__"
                ))
            )

            salud_mental_car = c18.text_input(
                "Salud / enfermedad mental",
                value=str(_valor_persona(
                    persona_car,
                    C["enfermedad_mental"]
                    if C["enfermedad_mental"] else "__none__"
                ))
            )

            c19, c20, c21 = st.columns(3)

            etnia_car = c19.text_input(
                "Grupo étnico",
                value=str(_valor_persona(
                    persona_car,
                    C["etnia"] if C["etnia"] else "__none__"
                ))
            )

            orientacion_car = c20.text_input(
                "Orientación sexual / LGBTI",
                value=str(_valor_persona(
                    persona_car,
                    C["orientacion"] if C["orientacion"] else "__none__"
                ))
            )

            poblacion_car = c21.text_input(
                "Población diferencial",
                value=str(_valor_persona(
                    persona_car,
                    C["poblacion"] if C["poblacion"] else "__none__"
                ))
            )

            guardar_car = st.form_submit_button(
                "💾 Guardar caracterización",
                use_container_width=True,
                type="primary"
            )

        if guardar_car:

            cambios_car = {
                C["sisben"]: sisben_car.strip(),
                C["discapacidad"]: discapacidad_car,
                C["categoria_discapacidad"]: categoria_disc_car.strip(),
                C["cabeza_familia"]: cabeza_car,
                C["gestante"]: gestante_car,
                C["migracion"]: migracion_car.strip(),
                C["educacion"]: educacion_car.strip(),
                C["ocupacion"]: ocupacion_car.strip(),
                C["procedencia"]: procedencia_car.strip(),
                C["barrio"]: barrio_car.strip(),
                C["comuna"]: comuna_car.strip(),
                C["zona"]: zona_car.strip(),
                C["direccion"]: direccion_car.strip(),
                C["telefono"]: telefono_car.strip(),
                C["correo"]: correo_car.strip(),
                C["salud"]: salud_car.strip(),
                C["consumo"]: consumo_car.strip(),
                C["enfermedad_mental"]: salud_mental_car.strip(),
                C["etnia"]: etnia_car.strip(),
                C["orientacion"]: orientacion_car.strip(),
                C["poblacion"]: poblacion_car.strip()
            }

            ok = _actualizar_campos_persona(
                doc_car,
                cambios_car
            )

            if ok:
                registrar_auditoria(
                    "ACTUALIZAR_CARACTERIZACION",
                    documento=doc_car,
                    modulo="Gestión Usuarios",
                    observacion="Actualización progresiva de caracterización social."
                )

                invalidar_cache_datos()
                st.success("✅ Caracterización actualizada.")
                st.rerun()
            else:
                st.warning(
                    "No se encontraron columnas compatibles para actualizar."
                )

    # ========================================================
    # 4. LISTADO
    # ========================================================
    with tab_listado:

        l1, l2, l3 = st.columns(3)

        filtro_estado = l1.multiselect(
            "Estado",
            ["ACTIVO", "INACTIVO", "EGRESADO"],
            key="gestion_lista_estado_v9"
        )

        filtro_modalidad = l2.multiselect(
            "Modalidad",
            ["URBANO", "GRANJA"],
            key="gestion_lista_modalidad_v9"
        )

        texto_lista = l3.text_input(
            "Nombre / documento",
            key="gestion_lista_texto_v9"
        )

        df_lista = df_gestion.copy()

        if filtro_estado:
            df_lista = df_lista[
                df_lista["estado_caso"].isin(filtro_estado)
            ]

        if filtro_modalidad:
            df_lista = df_lista[
                df_lista["modalidad"].isin(filtro_modalidad)
            ]

        if texto_lista.strip():
            patron = texto_lista.strip().lower()
            df_lista = df_lista[
                df_lista["nombre_completo"]
                .str.lower()
                .str.contains(patron, na=False, regex=False)
                |
                df_lista["numero_identificacion"]
                .str.lower()
                .str.contains(patron, na=False, regex=False)
            ]

        columnas_lista = [
            "nombre_completo",
            "numero_identificacion",
            "estado_caso",
            "modalidad",
            "edad"
        ]

        for col in [
            C["procedencia"],
            C["consumo"],
            C["salud"]
        ]:
            if col and col not in columnas_lista:
                columnas_lista.append(col)

        columnas_lista = [
            c for c in columnas_lista
            if c in df_lista.columns
        ]

        st.caption(f"Registros mostrados: {len(df_lista)}")

        st.dataframe(
            df_lista[columnas_lista],
            use_container_width=True,
            hide_index=True
        )



# ============================================================
# V11 - VISTA MÓVIL PARA TRABAJO EN CAMPO
# ============================================================
# ============================================================
# V11.2 - AJUSTES RESPONSIVE PARA CELULAR
# ============================================================
st.markdown("""
<style>
@media (max-width: 768px) {
    .block-container {
        padding-top: 1rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        padding-bottom: 4rem !important;
    }
    div[data-testid="stButton"] > button,
    div[data-testid="stFormSubmitButton"] > button {
        width: 100% !important;
        min-height: 3rem !important;
        font-size: 1rem !important;
        border-radius: 0.75rem !important;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stDateInput"] input {
        min-height: 2.8rem !important;
    }
    h1 { font-size: 1.65rem !important; }
    h2 { font-size: 1.4rem !important; }
    h3 { font-size: 1.2rem !important; }
}
</style>
""", unsafe_allow_html=True)


def _texto_whatsapp_movimiento(
    tipo,
    nombres,
    apellidos,
    documento,
    modalidad="",
    fecha=None,
    hora=None,
    detalle="",
    responsable=""
):
    """Construye un reporte corto para compartir por WhatsApp."""
    fecha_txt = (
        fecha.strftime("%d/%m/%Y")
        if hasattr(fecha, "strftime")
        else str(fecha or "")
    )
    hora_txt = (
        hora.strftime("%H:%M")
        if hasattr(hora, "strftime")
        else str(hora or "")
    )

    lineas = [
        f"*{tipo.upper()}*",
        f"*NOMBRE COMPLETO:* {str(nombres).strip()} {str(apellidos).strip()}",
        f"*CC:* {str(documento).strip()}",
    ]

    if modalidad:
        lineas.append(f"*ALBERGUE:* {str(modalidad).strip()}")
    if fecha_txt:
        lineas.append(f"*FECHA:* {fecha_txt}")
    if hora_txt:
        lineas.append(f"*HORA:* {hora_txt}")
    if detalle:
        lineas.append(f"*OBSERVACIÓN:* {str(detalle).strip()}")
    if responsable:
        lineas.append(f"*REGISTRA:* {str(responsable).strip()}")

    return "\n".join(lineas)


def _boton_whatsapp(texto, key):
    """Abre WhatsApp con el reporte ya diligenciado."""
    enlace = "https://wa.me/?text=" + urllib.parse.quote(texto)
    st.link_button(
        "🟢 Compartir reporte por WhatsApp",
        enlace,
        use_container_width=True
    )
    st.code(texto, language=None)



def registrar_egreso_profesional_v12(u, documento):

    st.markdown("#### 🏆 Registrar egreso profesional")
    st.caption(
        "El egreso se almacena en personas_caracterizacion y "
        "actualiza la situación de la persona en la base general."
    )

    estado_actual = str(
        u.get("estado_caso") or ""
    ).strip().upper()

    if estado_actual == "EGRESADO":
        st.warning(
            "Esta persona ya figura actualmente como EGRESADO."
        )

    fecha_e = st.date_input(
        "Fecha de egreso",
        value=date.today(),
        key=f"v12_fecha_egreso_{documento}"
    )

    motivo_e = st.selectbox(
        "Tipo de egreso",
        [
            "PLAN RETORNO",
            "VINCULACION FAMILIAR",
            "VINCULACION LABORAL",
            "TRASLADO A CENTRO DE PROTECCION",
            "INGRESO A TRATAMIENTO",
            "AUTONOMIA / SUPERACION DE VIDA EN CALLE",
            "OTRO"
        ],
        key=f"v12_motivo_egreso_{documento}"
    )

    cedula_validada = st.selectbox(
        "Cédula validada",
        ["SI", "NO", "NO APLICA"],
        key=f"v12_cedula_validada_{documento}"
    )

    obs_e = st.text_area(
        "Observaciones",
        key=f"v12_obs_egreso_{documento}"
    )

    responsable = st.session_state.get(
        "usuario_actual", "profesional"
    )
    st.caption(f"Registrado por: {responsable}")

    confirmar = st.checkbox(
        "Confirmo que corresponde a un egreso real",
        key=f"v12_conf_egreso_{documento}"
    )

    if st.button(
        "🏆 Confirmar egreso",
        use_container_width=True,
        type="primary",
        key=f"v12_guardar_egreso_{documento}"
    ):

        if estado_actual == "EGRESADO":
            st.error(
                "No se puede registrar otro egreso mientras "
                "la persona siga en estado EGRESADO."
            )
            return

        if not confirmar:
            st.error("Debe confirmar el egreso.")
            return

        persona_df = pd.read_sql(
            text("""
                SELECT *
                FROM habitante_de_calle
                WHERE TRIM(
                    CAST(numero_identificacion AS TEXT)
                )=:doc
                LIMIT 1
            """),
            engine,
            params={"doc": documento}
        )

        if persona_df.empty:
            st.error("No se encontró la persona en la base general.")
            return

        persona = persona_df.iloc[0]

        columnas_e = set(
            pd.read_sql(
                text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema='public'
                      AND table_name='personas_caracterizacion'
                """),
                engine
            )["column_name"].tolist()
        )

        def ce(*nombres):
            for nombre in nombres:
                if nombre in columnas_e:
                    return nombre
            return None

        def pv(*nombres, default=None):
            for nombre in nombres:
                if nombre in persona.index:
                    valor = persona.get(nombre)
                    if pd.notna(valor):
                        return valor
            return default

        col_doc_egreso = ce(
            "numero_identidad",
            "numero_identificacion"
        )
        col_fecha_egreso = ce("fecha_egreso")

        if col_doc_egreso and col_fecha_egreso:
            consulta_dup = text(
                f"""
                SELECT COUNT(*) AS total
                FROM personas_caracterizacion
                WHERE TRIM(CAST("{col_doc_egreso}" AS TEXT))=:doc
                  AND "{col_fecha_egreso}"=:fecha
                """
            )
            dup = pd.read_sql(
                consulta_dup,
                engine,
                params={
                    "doc": documento,
                    "fecha": fecha_e
                }
            )
            if int(dup.iloc[0]["total"] or 0) > 0:
                st.error(
                    "Ya existe un egreso para esta persona en esa fecha."
                )
                return

        meses = [
            "", "ENERO", "FEBRERO", "MARZO", "ABRIL",
            "MAYO", "JUNIO", "JULIO", "AGOSTO",
            "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"
        ]

        observacion_final = motivo_e
        if obs_e.strip():
            observacion_final += " - " + obs_e.strip()

        datos = {
            ce("cedula_validada"): cedula_validada,
            ce("mes_validacion"): meses[fecha_e.month],
            ce("nombres"): pv("nombres", default=""),
            ce("apellidos"): pv("apellidos", default=""),
            ce("sexo_nacer", "sexo_al_nacer"): pv(
                "sexo_al_nacer",
                "sexo_nacer",
                default=""
            ),
            ce("edad"): pv("edad"),
            ce("fecha_nacimiento"): pv(
                "fecha_nacimiento",
                "fecha_de_nacimiento_dd_mm_aa"
            ),
            col_doc_egreso: documento,
            ce("categoria_discapacidad"): pv(
                "categoria_discapacidad",
                default=""
            ),
            ce("se_reconoce_como"): pv(
                "se_reconoce_como",
                default=""
            ),
            ce(
                "orientacion_lgbti",
                "orientacion_sexual_lgtbi"
            ): pv(
                "orientacion_sexual_lgtbi",
                "orientacion_lgbti",
                default=""
            ),
            ce("grupo_etnico", "grupos_etnicos"): pv(
                "grupos_etnicos",
                "grupos_etnicos_afro_indigena",
                "grupo_etnico",
                default=""
            ),
            ce("departamento_procedencia"): pv(
                "departamento_procedencia",
                "departamento_de_procedencia",
                default=""
            ),
            ce("estado_caso"): "EGRESADO",
            col_fecha_egreso: fecha_e,
            ce("observaciones_egreso"): observacion_final,
            ce("funcionario_egreso"): responsable
        }

        datos = {
            k: v for k, v in datos.items()
            if k and k in columnas_e
        }

        with engine.begin() as conn:

            if "numero" in columnas_e:
                # Evita que dos profesionales obtengan el mismo consecutivo.
                conn.execute(
                    text("""
                        SELECT pg_advisory_xact_lock(
                            hashtext(
                                'personas_caracterizacion_numero'
                            )
                        )
                    """)
                )

                datos["numero"] = conn.execute(
                    text("""
                        SELECT COALESCE(MAX(numero),0)+1
                        FROM personas_caracterizacion
                    """)
                ).scalar()

            columnas = list(datos.keys())
            params_ins = {}
            valores = []

            for i, columna in enumerate(columnas):
                par = f"e{i}"
                params_ins[par] = datos[columna]
                valores.append(f":{par}")

            conn.execute(
                text(
                    "INSERT INTO personas_caracterizacion ("
                    + ", ".join(
                        f'"{c}"' for c in columnas
                    )
                    + ") VALUES ("
                    + ", ".join(valores)
                    + ")"
                ),
                params_ins
            )

            columnas_h = set(
                conn.execute(
                    text("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema='public'
                          AND table_name='habitante_de_calle'
                    """)
                ).scalars().all()
            )

            sets_h = [
                "estado_caso='EGRESADO'",
                "modalidad=NULL"
            ]
            params_h = {"doc": documento}

            if "fecha_ultimo_egreso" in columnas_h:
                sets_h.append(
                    "fecha_ultimo_egreso=:fecha_egreso"
                )
                params_h["fecha_egreso"] = fecha_e

            conn.execute(
                text(
                    "UPDATE habitante_de_calle SET "
                    + ", ".join(sets_h)
                    + """
                    WHERE TRIM(
                        CAST(numero_identificacion AS TEXT)
                    )=:doc
                    """
                ),
                params_h
            )

            conn.execute(
                text("""
                    INSERT INTO movimientos_habitante (
                        numero_identificacion,
                        tipo_movimiento,
                        modalidad,
                        usuario_registra,
                        observacion
                    )
                    VALUES (
                        :doc,
                        'EGRESO',
                        :modalidad,
                        :usuario,
                        :observacion
                    )
                """),
                {
                    "doc": documento,
                    "modalidad": u.get("modalidad"),
                    "usuario": responsable,
                    "observacion": observacion_final
                }
            )

        registrar_auditoria(
            "REGISTRAR_EGRESO",
            documento=documento,
            modulo="Gestión Profesional",
            valor_anterior=estado_actual,
            valor_nuevo="EGRESADO",
            observacion=observacion_final[:500]
        )

        invalidar_cache_datos()
        st.success("✅ Egreso registrado correctamente.")
        st.rerun()



def panel_inspirador_simple_v14():
    """Panel operativo simple integrado a Gestión Móvil."""
    responsable = st.session_state.get("usuario_actual", "inspirador")
    ahora = datetime.now()

    # Permisos actualmente abiertos
    try:
        permisos = pd.read_sql(
            text("""
                SELECT
                    p.id,
                    TRIM(CAST(p.numero_identificacion AS TEXT)) AS documento,
                    p.fecha_salida,
                    p.hora_salida,
                    p.fecha_regreso_estimada,
                    p.hora_regreso_estimada,
                    p.motivo,
                    h.nombres,
                    h.apellidos,
                    h.modalidad
                FROM permisos_usuarios p
                LEFT JOIN habitante_de_calle h
                  ON TRIM(CAST(h.numero_identificacion AS TEXT))
                   = TRIM(CAST(p.numero_identificacion AS TEXT))
                WHERE UPPER(TRIM(COALESCE(p.estado_permiso,'')))='ABIERTO'
                ORDER BY p.fecha_regreso_estimada, p.hora_regreso_estimada
            """),
            engine
        )
    except Exception:
        permisos = pd.DataFrame()

    vencidos = 0
    if not permisos.empty:
        permisos["regreso_dt"] = pd.to_datetime(
            permisos["fecha_regreso_estimada"].astype(str)
            + " "
            + permisos["hora_regreso_estimada"].astype(str),
            errors="coerce"
        )
        permisos["vencido"] = permisos["regreso_dt"].apply(
            lambda x: bool(
                pd.notna(x) and x.to_pydatetime() < ahora
            )
        )
        vencidos = int(permisos["vencido"].sum())

    st.markdown("### 🚪 Personas actualmente con permiso")
    c1, c2 = st.columns(2)
    c1.metric("Fuera con permiso", len(permisos))
    c2.metric("🔴 Pendientes vencidos", vencidos)

    if permisos.empty:
        st.success("✅ En este momento no hay permisos abiertos.")
    else:
        permisos["nombre_completo"] = (
            permisos["nombres"].fillna("").astype(str).str.strip()
            + " "
            + permisos["apellidos"].fillna("").astype(str).str.strip()
        ).str.strip()

        permisos["etiqueta"] = permisos.apply(
            lambda r: (
                f"{'🔴' if r.get('vencido') else '🟢'} "
                f"{r.get('nombre_completo','')} · "
                f"CC {r.get('documento','')} · "
                f"{r.get('modalidad','')}"
            ),
            axis=1
        )

        permiso_id = st.selectbox(
            "Seleccione la persona que regresó",
            permisos["id"].tolist(),
            format_func=lambda x: permisos.loc[
                permisos["id"] == x, "etiqueta"
            ].iloc[0],
            key="v14_regreso_permiso"
        )

        fila = permisos.loc[
            permisos["id"] == permiso_id
        ].iloc[0]

        st.caption(
            f"Salida: {fila.get('fecha_salida','')} "
            f"{fila.get('hora_salida','')} · "
            f"Regreso esperado: {fila.get('fecha_regreso_estimada','')} "
            f"{fila.get('hora_regreso_estimada','')}"
        )

        if st.button(
            "⬅️ REGISTRAR REGRESO",
            use_container_width=True,
            type="primary",
            key="v14_btn_regreso"
        ):
            with engine.begin() as conn:
                actualizado = conn.execute(
                    text("""
                        UPDATE permisos_usuarios
                        SET estado_permiso='CERRADO',
                            fecha_regreso_real=CURRENT_DATE,
                            hora_regreso_real=CURRENT_TIME,
                            observacion_regreso='REGRESA AL ALBERGUE',
                            cerrado_en=NOW()
                        WHERE id=:id
                          AND UPPER(TRIM(COALESCE(estado_permiso,'')))='ABIERTO'
                    """),
                    {
                        "id": int(permiso_id)
                    }
                )

                if actualizado.rowcount:
                    conn.execute(
                        text("""
                            INSERT INTO movimientos_habitante (
                                numero_identificacion,
                                tipo_movimiento,
                                modalidad,
                                usuario_registra,
                                observacion
                            )
                            VALUES (
                                :doc,
                                'REGRESO_PERMISO',
                                :modalidad,
                                :usuario,
                                'REGRESA AL ALBERGUE'
                            )
                        """),
                        {
                            "doc": str(fila.get("documento", "")).strip(),
                            "modalidad": fila.get("modalidad"),
                            "usuario": responsable
                        }
                    )

            invalidar_cache_datos()
            st.success(
                f"✅ Regreso registrado: {fila.get('nombre_completo','')}."
            )
            st.rerun()

    # Novedad rápida
    with st.expander("📝 Registrar novedad del turno"):
        with st.form("v14_novedad_simple"):
            prioridad = st.selectbox(
                "Prioridad",
                ["NORMAL", "IMPORTANTE", "URGENTE"]
            )
            novedad = st.text_area(
                "Novedad",
                placeholder="Escriba únicamente lo que debe conocer el siguiente turno."
            )
            guardar = st.form_submit_button(
                "💾 Guardar novedad",
                use_container_width=True
            )

        if guardar:
            if not novedad.strip():
                st.error("Escriba la novedad.")
            else:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO novedades_turno (
                                tipo_novedad,
                                novedad,
                                prioridad,
                                estado,
                                usuario_registra
                            )
                            VALUES (
                                'GENERAL',
                                :novedad,
                                :prioridad,
                                'PENDIENTE',
                                :usuario
                            )
                        """),
                        {
                            "novedad": novedad.strip(),
                            "prioridad": prioridad,
                            "usuario": responsable
                        }
                    )
                st.success("✅ Novedad registrada.")
                st.rerun()

    # Reporte WhatsApp simple
    with st.expander("📲 Reporte rápido para WhatsApp"):
        try:
            pendientes = pd.read_sql(
                text("""
                    SELECT prioridad, novedad
                    FROM novedades_turno
                    WHERE estado='PENDIENTE'
                    ORDER BY creado_en DESC
                    LIMIT 8
                """),
                engine
            )
        except Exception:
            pendientes = pd.DataFrame()

        detalle_perm = []
        if not permisos.empty:
            for _, r in permisos.iterrows():
                detalle_perm.append(
                    f"• {'VENCIDO - ' if r.get('vencido') else ''}"
                    f"{r.get('nombre_completo','')} "
                    f"(CC {r.get('documento','')})"
                )

        detalle_nov = []
        if not pendientes.empty:
            for _, r in pendientes.iterrows():
                detalle_nov.append(
                    f"• [{r.get('prioridad')}] {r.get('novedad')}"
                )

        reporte = "\\n".join([
            "*REPORTE OPERATIVO - ALBERGUE*",
            f"*Fecha:* {ahora.strftime('%d/%m/%Y %H:%M')}",
            f"*Personas con permiso:* {len(permisos)}",
            f"*Permisos vencidos:* {vencidos}",
            "",
            "*Fuera con permiso:*",
            *(detalle_perm if detalle_perm else ["• Ninguno"]),
            "",
            "*Novedades pendientes:*",
            *(detalle_nov if detalle_nov else ["• Ninguna"]),
            "",
            f"*Registra:* {responsable}"
        ])

        _boton_whatsapp(
            reporte,
            "v14_whatsapp_operativo"
        )

def gestion_usuarios_movil():

    st.title("📱 Gestión de Usuarios")
    st.caption("Vista rápida para trabajo desde celular.")

    # --------------------------------------------------------
    # Rol operativo
    # --------------------------------------------------------
    rol_visible = str(
        st.session_state.get("rol_actual", "INSPIRADOR")
    ).strip().upper()

    nombre_login = st.session_state.get(
        "nombre_funcionario", "Funcionario"
    )

    st.info(
        f"👤 {nombre_login} · Perfil: {rol_visible.title()}"
    )

    # V14.1: primero Gestión de usuarios.
    if rol_visible == "INSPIRADOR":
        st.markdown("### 👤 Gestión de usuarios")

    # --------------------------------------------------------
    # Entrada principal móvil
    # --------------------------------------------------------
    if rol_visible == "INSPIRADOR":
        opciones_inicio = [
            "➕ Nuevo usuario",
            "🔎 Buscar usuario existente"
        ]
    elif rol_visible == "PROFESIONAL":
        opciones_inicio = [
            "🔎 Buscar usuario existente"
        ]
    else:
        opciones_inicio = [
            "➕ Nuevo usuario",
            "🔎 Buscar usuario existente"
        ]

    modo = st.radio(
        "¿Qué desea hacer?",
        opciones_inicio,
        horizontal=True,
        key="modo_gestion_movil"
    )

    # ========================================================
    # NUEVO USUARIO - INSPIRADOR / COORDINACIÓN
    # ========================================================
    if modo == "➕ Nuevo usuario":

        if rol_visible not in ["INSPIRADOR", "COORDINACION", "MANAGER"]:
            st.error("Este perfil no tiene habilitado el registro de nuevos usuarios.")
            return

        st.markdown("### ➕ Registrar nuevo usuario")
        st.caption(
            "Registro inicial corto para celular. "
            "La caracterización completa se puede terminar después."
        )

        # Leer columnas reales de habitante_de_calle
        cols_h = set(
            pd.read_sql(
                text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema='public'
                      AND table_name='habitante_de_calle'
                """),
                engine
            )["column_name"].tolist()
        )

        def col_h(*candidatas):
            for c in candidatas:
                if c in cols_h:
                    return c
            return None

        CH = {
            "tipo_id": col_h("tipo_identificacion", "tipo_de_identificacion"),
            "fecha_nacimiento": col_h(
                "fecha_nacimiento",
                "fecha_de_nacimiento_dd_mm_aa"
            ),
            "salud": col_h(
                "tipo_seguridad_salud",
                "tipo_de_seguridad_social_en_salud"
            ),
            "telefono": col_h("telefono", "telefono_y_o_celular"),
            "procedencia": col_h(
                "departamento_procedencia",
                "departamento_de_procedencia"
            ),
            "consumo": col_h("tipo_consumo", "tipo_de_consumo"),
            "fecha_ingreso": col_h("fecha_ingreso_albergue"),
            "numero_atenciones": col_h("numero_atenciones")
        }

        with st.form("nuevo_usuario_movil_v111"):

            nombres = st.text_input("Nombres *")
            apellidos = st.text_input("Apellidos *")
            numero_id = st.text_input("Número de identificación *")

            c1, c2 = st.columns(2)

            tipo_id = c1.selectbox(
                "Tipo identificación",
                ["CC", "TI", "CE", "PEP", "PPT", "Otro"]
            )

            sexo = c2.selectbox(
                "Sexo al nacer",
                ["Masculino", "Femenino"]
            )

            fecha_nacimiento = st.date_input(
                "Fecha de nacimiento",
                value=date.today() - timedelta(days=30 * 365)
            )

            c3, c4 = st.columns(2)

            modalidad = c3.selectbox(
                "Modalidad",
                ["URBANO", "GRANJA"]
            )

            salud = c4.selectbox(
                "Seguridad social",
                [
                    "Subsidiado",
                    "Contributivo",
                    "Especial",
                    "No afiliado",
                    "Sin información"
                ]
            )

            procedencia = st.text_input(
                "Departamento / lugar de procedencia *",
                placeholder="Ej. Risaralda, Caldas, Valle del Cauca"
            )

            consumo = st.selectbox(
                "Consumo principal",
                [
                    "No refiere consumo",
                    "Alcohol",
                    "Marihuana",
                    "Bazuco",
                    "Cocaína",
                    "Heroína",
                    "Inhalables",
                    "Medicamentos sin fórmula",
                    "Policonsumo",
                    "Otro",
                    "Sin información"
                ]
            )

            telefono = st.text_input("Teléfono")

            confirmar = st.checkbox(
                "Confirmo que la información fue verificada con el usuario."
            )

            guardar = st.form_submit_button(
                "💾 Registrar nuevo usuario",
                use_container_width=True,
                type="primary"
            )

        if guardar:

            doc = limpiar_documento(numero_id)

            if not nombres.strip():
                st.error("Debe ingresar los nombres.")
            elif not apellidos.strip():
                st.error("Debe ingresar los apellidos.")
            elif not doc:
                st.error("Debe ingresar el número de identificación.")
            elif not procedencia.strip():
                st.error("Debe registrar la procedencia.")
            elif not confirmar:
                st.error("Confirme la información antes de guardar.")
            else:
                valido, mensaje = validar_documento_no_duplicado(doc)

                if not valido:
                    st.error(mensaje)
                else:
                    edad = max(
                        0,
                        date.today().year
                        - fecha_nacimiento.year
                        - (
                            (date.today().month, date.today().day)
                            < (
                                fecha_nacimiento.month,
                                fecha_nacimiento.day
                            )
                        )
                    )

                    datos = {
                        "nombres": nombres.strip(),
                        "apellidos": apellidos.strip(),
                        "sexo_al_nacer": sexo,
                        "edad": edad,
                        "numero_identificacion": doc,
                        "estado_caso": "ACTIVO",
                        "modalidad": modalidad
                    }

                    opcionales = {
                        CH["tipo_id"]: tipo_id,
                        CH["fecha_nacimiento"]: fecha_nacimiento,
                        CH["salud"]: salud,
                        CH["telefono"]: telefono.strip(),
                        CH["procedencia"]: procedencia.strip(),
                        CH["consumo"]: consumo,
                        CH["fecha_ingreso"]: date.today(),
                        CH["numero_atenciones"]: 0
                    }

                    for col, val in opcionales.items():
                        if col:
                            datos[col] = val

                    datos = {
                        k: v for k, v in datos.items()
                        if k in cols_h
                    }

                    columnas = list(datos.keys())
                    params = {}
                    valores = []

                    for i, col in enumerate(columnas):
                        p = f"n{i}"
                        valores.append(f":{p}")
                        params[p] = datos[col]

                    sql_insert = text(
                        "INSERT INTO habitante_de_calle ("
                        + ", ".join(f'"{c}"' for c in columnas)
                        + ") VALUES ("
                        + ", ".join(valores)
                        + ")"
                    )

                    usuario_registra = st.session_state.get(
                        "usuario_actual", "inspirador"
                    )

                    with engine.begin() as conn:
                        conn.execute(sql_insert, params)

                        conn.execute(
                            text("""
                                INSERT INTO movimientos_habitante (
                                    numero_identificacion,
                                    tipo_movimiento,
                                    modalidad,
                                    usuario_registra,
                                    observacion
                                )
                                VALUES (
                                    :doc,
                                    'INGRESO',
                                    :modalidad,
                                    :usuario,
                                    'Registro inicial desde Gestión Móvil'
                                )
                            """),
                            {
                                "doc": doc,
                                "modalidad": modalidad,
                                "usuario": usuario_registra
                            }
                        )

                    registrar_auditoria(
                        "CREAR_USUARIO",
                        documento=doc,
                        modulo="Gestión Móvil",
                        valor_nuevo=(
                            f"{nombres.strip()} {apellidos.strip()} - "
                            f"{modalidad}; procedencia={procedencia.strip()}; "
                            f"consumo={consumo}"
                        )
                    )

                    invalidar_cache_datos()

                    st.success(
                        "✅ Usuario registrado correctamente. "
                        "Ya puede buscarlo y completar su caracterización."
                    )

        # V14.1: herramientas operativas debajo de Gestión de usuarios.
        if rol_visible == "INSPIRADOR":
            st.divider()
            panel_inspirador_simple_v14()
        return

    # ========================================================
    # BUSCAR USUARIO EXISTENTE
    # ========================================================
    termino = st.text_input(
        "🔎 Buscar usuario",
        placeholder="Digite nombre, apellido o documento",
        key="busqueda_movil_usuario"
    )

    if not termino.strip():
        st.caption("Escriba al menos 2 caracteres para buscar.")
        return

    if len(termino.strip()) < 2:
        st.warning("Digite al menos 2 caracteres.")
        return

    patron = f"%{termino.strip()}%"

    df_resultados = pd.read_sql(
        text("""
            SELECT
                numero_identificacion,
                nombres,
                apellidos,
                edad,
                estado_caso,
                modalidad
            FROM habitante_de_calle
            WHERE CAST(numero_identificacion AS TEXT) ILIKE :patron
               OR COALESCE(nombres,'') ILIKE :patron
               OR COALESCE(apellidos,'') ILIKE :patron
               OR (
                    COALESCE(nombres,'') || ' ' ||
                    COALESCE(apellidos,'')
                  ) ILIKE :patron
            ORDER BY nombres, apellidos
            LIMIT 20
        """),
        engine,
        params={"patron": patron}
    )

    if df_resultados.empty:
        st.warning("No se encontraron usuarios.")
        return

    opciones = df_resultados.index.tolist()
    idx = st.selectbox(
        "Seleccione la persona",
        opciones,
        format_func=lambda i: (
            f"{df_resultados.loc[i, 'nombres']} "
            f"{df_resultados.loc[i, 'apellidos']} · "
            f"{df_resultados.loc[i, 'numero_identificacion']}"
        ),
        key="resultado_busqueda_movil"
    )

    u = df_resultados.loc[idx]
    documento = str(u["numero_identificacion"]).strip()

    st.markdown(
        f"""
### 👤 {str(u['nombres']).strip()} {str(u['apellidos']).strip()}
**Documento:** {documento}  
**Estado:** {u.get('estado_caso') or 'Sin dato'}  
**Modalidad:** {u.get('modalidad') or 'Sin modalidad'}  
**Edad:** {u.get('edad') if pd.notna(u.get('edad')) else 'Sin dato'}
"""
    )

    # --------------------------------------------------------
    # Alertas rápidas
    # --------------------------------------------------------
    try:
        medida_activa = pd.read_sql(
            text("""
                SELECT tipo_medida, fecha_inicio, fecha_fin, motivo
                FROM sanciones_usuarios
                WHERE TRIM(CAST(numero_identificacion AS TEXT)) = :doc
                  AND UPPER(TRIM(COALESCE(estado_medida,''))) = 'ACTIVA'
                ORDER BY creado_en DESC
                LIMIT 1
            """),
            engine,
            params={"doc": documento}
        )
        if not medida_activa.empty:
            m = medida_activa.iloc[0]
            st.error(
                f"⛔ Medida activa: {m['tipo_medida']} · "
                f"desde {m['fecha_inicio']}"
            )
    except Exception:
        pass

    # Alerta de permiso actualmente abierto
    try:
        permiso_actual = pd.read_sql(
            text("""
                SELECT fecha_salida, hora_salida,
                       fecha_regreso_estimada, hora_regreso_estimada,
                       motivo
                FROM permisos_usuarios
                WHERE TRIM(CAST(numero_identificacion AS TEXT)) = :doc
                  AND UPPER(TRIM(COALESCE(estado_permiso,''))) = 'ABIERTO'
                ORDER BY fecha_salida DESC, hora_salida DESC
                LIMIT 1
            """),
            engine,
            params={"doc": documento}
        )
        if not permiso_actual.empty:
            pp = permiso_actual.iloc[0]
            st.warning(
                "🚪 Usuario actualmente fuera con permiso. "
                f"Regreso estimado: "
                f"{pp.get('fecha_regreso_estimada')} "
                f"{pp.get('hora_regreso_estimada')}."
            )
    except Exception:
        pass

    # --------------------------------------------------------
    # Acciones por rol
    # --------------------------------------------------------
    st.markdown("### ⚡ ¿Qué desea registrar?")

    if rol_visible == "INSPIRADOR":
        acciones = [
            "➕ Ingreso / Reingreso",
            "🚪 Salida de permiso",
            "↩️ Regreso de permiso",
            "⛔ Sanción / Expulsión",
            "🧾 Completar información",
            "📚 Ver historia"
        ]
    elif rol_visible == "PROFESIONAL":
        acciones = [
            "🏆 Registrar egreso",
            "🎯 PAI / Seguimiento",
            "🧾 Consultar información",
            "📚 Ver historia"
        ]
    else:
        acciones = [
            "➕ Ingreso / Reingreso",
            "🏆 Registrar egreso",
            "⛔ Sanciones / Expulsiones",
            "🧾 Caracterización",
            "📚 Ver historia"
        ]

    accion = st.radio(
        "Acción",
        acciones,
        label_visibility="collapsed",
        key=f"accion_movil_{documento}"
    )

    # --------------------------------------------------------
    # Ingreso / Reingreso
    # --------------------------------------------------------
    if accion == "➕ Ingreso / Reingreso":

        st.markdown("#### ➕ Ingreso / Reingreso")

        modalidad = st.selectbox(
            "Modalidad",
            ["URBANO", "GRANJA"],
            key=f"movil_modalidad_{documento}"
        )

        observacion = st.text_area(
            "Observación",
            key=f"movil_obs_ingreso_{documento}"
        )

        confirmar = st.checkbox(
            "Confirmo el ingreso/reingreso",
            key=f"movil_conf_ingreso_{documento}"
        )

        if st.button(
            "✅ Guardar ingreso / reingreso",
            use_container_width=True,
            type="primary",
            key=f"movil_guardar_ingreso_{documento}"
        ):
            if not confirmar:
                st.error("Confirme el registro antes de guardar.")
            else:
                estado_anterior = str(u.get("estado_caso") or "").upper()
                tipo_mov = (
                    "REINGRESO"
                    if estado_anterior in ["EGRESADO", "INACTIVO"]
                    else "INGRESO"
                )

                with engine.begin() as conn:
                    cols_h = pd.read_sql(
                        text("""
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_schema='public'
                              AND table_name='habitante_de_calle'
                        """),
                        conn
                    )["column_name"].tolist()

                    sets = [
                        "estado_caso = 'ACTIVO'",
                        "modalidad = :modalidad"
                    ]

                    if "fecha_ultimo_ingreso" in cols_h:
                        sets.append("fecha_ultimo_ingreso = CURRENT_DATE")

                    if tipo_mov == "REINGRESO" and "numero_reingresos" in cols_h:
                        sets.append(
                            "numero_reingresos = COALESCE(numero_reingresos,0) + 1"
                        )

                    conn.execute(
                        text(
                            "UPDATE habitante_de_calle SET "
                            + ", ".join(sets)
                            + """
                            WHERE TRIM(
                                CAST(numero_identificacion AS TEXT)
                            ) = :doc
                            """
                        ),
                        {"modalidad": modalidad, "doc": documento}
                    )

                    conn.execute(
                        text("""
                            INSERT INTO movimientos_habitante (
                                numero_identificacion,
                                tipo_movimiento,
                                modalidad,
                                usuario_registra,
                                observacion
                            )
                            VALUES (
                                :doc, :tipo, :modalidad, :usuario, :obs
                            )
                        """),
                        {
                            "doc": documento,
                            "tipo": tipo_mov,
                            "modalidad": modalidad,
                            "usuario": st.session_state.get(
                                "usuario_actual", "inspirador"
                            ),
                            "obs": observacion.strip()
                        }
                    )

                registrar_auditoria(
                    tipo_mov,
                    documento=documento,
                    modulo="Gestión Móvil",
                    valor_anterior=estado_anterior,
                    valor_nuevo=f"ACTIVO - {modalidad}",
                    observacion=observacion.strip()[:500]
                )
                invalidar_cache_datos()

                reporte = _texto_whatsapp_movimiento(
                    tipo_mov,
                    u.get("nombres"),
                    u.get("apellidos"),
                    documento,
                    modalidad=modalidad,
                    fecha=date.today(),
                    detalle=observacion.strip(),
                    responsable=st.session_state.get(
                        "usuario_actual", "inspirador"
                    )
                )
                st.session_state[
                    f"reporte_whatsapp_{documento}"
                ] = reporte

                st.success(f"✅ {tipo_mov.title()} registrado correctamente.")
                _boton_whatsapp(
                    reporte,
                    f"wa_ingreso_{documento}"
                )

    # --------------------------------------------------------
    # Salida de permiso
    # --------------------------------------------------------
    elif accion == "🚪 Salida de permiso":

        st.markdown("#### 🚪 Salida de permiso")

        # Verificar que no tenga un permiso abierto
        try:
            permiso_abierto = pd.read_sql(
                text("""
                    SELECT *
                    FROM permisos_usuarios
                    WHERE TRIM(CAST(numero_identificacion AS TEXT)) = :doc
                      AND UPPER(TRIM(COALESCE(estado_permiso,''))) = 'ABIERTO'
                    ORDER BY fecha_salida DESC, hora_salida DESC
                    LIMIT 1
                """),
                engine,
                params={"doc": documento}
            )
        except Exception:
            permiso_abierto = pd.DataFrame()

        if not permiso_abierto.empty:
            p = permiso_abierto.iloc[0]
            st.warning(
                "Este usuario ya tiene un permiso abierto "
                f"desde {p.get('fecha_salida')} {p.get('hora_salida')}."
            )
        else:
            c1, c2 = st.columns(2)
            fecha_salida = c1.date_input(
                "Fecha de salida",
                value=date.today(),
                key=f"perm_fecha_salida_{documento}"
            )
            hora_salida = c2.time_input(
                "Hora de salida",
                key=f"perm_hora_salida_{documento}"
            )

            c3, c4 = st.columns(2)
            fecha_regreso_est = c3.date_input(
                "Fecha estimada de regreso",
                value=date.today(),
                key=f"perm_fecha_reg_est_{documento}"
            )
            hora_regreso_est = c4.time_input(
                "Hora estimada de regreso",
                key=f"perm_hora_reg_est_{documento}"
            )

            motivo_permiso = st.text_area(
                "Motivo del permiso *",
                key=f"perm_motivo_{documento}"
            )

            autoriza = st.text_input(
                "Autoriza",
                value=str(st.session_state.get("usuario_actual", "")).replace(
                    "sistema", ""
                ),
                key=f"perm_autoriza_{documento}"
            )

            observacion_permiso = st.text_area(
                "Observación",
                key=f"perm_obs_{documento}"
            )

            conf_permiso = st.checkbox(
                "Confirmo la salida de permiso",
                key=f"perm_conf_{documento}"
            )

            if st.button(
                "🚪 Registrar salida",
                use_container_width=True,
                type="primary",
                key=f"perm_guardar_{documento}"
            ):
                if not motivo_permiso.strip():
                    st.error("Debe registrar el motivo del permiso.")
                elif not conf_permiso:
                    st.error("Debe confirmar la salida.")
                else:
                    usuario_registra = st.session_state.get(
                        "usuario_actual", "inspirador"
                    )

                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                INSERT INTO permisos_usuarios (
                                    numero_identificacion,
                                    fecha_salida,
                                    hora_salida,
                                    motivo,
                                    autoriza,
                                    fecha_regreso_estimada,
                                    hora_regreso_estimada,
                                    estado_permiso,
                                    observacion,
                                    usuario_registra
                                )
                                VALUES (
                                    :doc,
                                    :fecha_salida,
                                    :hora_salida,
                                    :motivo,
                                    :autoriza,
                                    :fecha_regreso_est,
                                    :hora_regreso_est,
                                    'ABIERTO',
                                    :observacion,
                                    :usuario
                                )
                            """),
                            {
                                "doc": documento,
                                "fecha_salida": fecha_salida,
                                "hora_salida": hora_salida,
                                "motivo": motivo_permiso.strip(),
                                "autoriza": autoriza.strip(),
                                "fecha_regreso_est": fecha_regreso_est,
                                "hora_regreso_est": hora_regreso_est,
                                "observacion": observacion_permiso.strip(),
                                "usuario": usuario_registra
                            }
                        )

                        conn.execute(
                            text("""
                                INSERT INTO movimientos_habitante (
                                    numero_identificacion,
                                    tipo_movimiento,
                                    modalidad,
                                    usuario_registra,
                                    observacion
                                )
                                VALUES (
                                    :doc,
                                    'SALIDA_PERMISO',
                                    :modalidad,
                                    :usuario,
                                    :observacion
                                )
                            """),
                            {
                                "doc": documento,
                                "modalidad": u.get("modalidad"),
                                "usuario": usuario_registra,
                                "observacion": motivo_permiso.strip()
                            }
                        )

                    registrar_auditoria(
                        "SALIDA_PERMISO",
                        documento=documento,
                        modulo="Gestión Móvil",
                        valor_nuevo="PERMISO ABIERTO",
                        observacion=motivo_permiso.strip()[:500]
                    )

                    reporte = _texto_whatsapp_movimiento(
                        "SALIDA DE PERMISO",
                        u.get("nombres"),
                        u.get("apellidos"),
                        documento,
                        modalidad=u.get("modalidad"),
                        fecha=fecha_salida,
                        hora=hora_salida,
                        detalle=(
                            f"{motivo_permiso.strip()} | "
                            f"Regreso estimado: "
                            f"{fecha_regreso_est.strftime('%d/%m/%Y')} "
                            f"{hora_regreso_est.strftime('%H:%M')}"
                        ),
                        responsable=usuario_registra
                    )

                    st.session_state[
                        f"reporte_whatsapp_{documento}"
                    ] = reporte
                    st.success("✅ Salida de permiso registrada.")
                    invalidar_cache_datos()

        reporte_guardado = st.session_state.get(
            f"reporte_whatsapp_{documento}"
        )
        if reporte_guardado:
            _boton_whatsapp(
                reporte_guardado,
                f"wa_permiso_{documento}"
            )

    # --------------------------------------------------------
    # Regreso de permiso
    # --------------------------------------------------------
    elif accion == "↩️ Regreso de permiso":

        st.markdown("#### ↩️ Regreso de permiso")

        try:
            permisos_abiertos = pd.read_sql(
                text("""
                    SELECT *
                    FROM permisos_usuarios
                    WHERE TRIM(CAST(numero_identificacion AS TEXT)) = :doc
                      AND UPPER(TRIM(COALESCE(estado_permiso,''))) = 'ABIERTO'
                    ORDER BY fecha_salida DESC, hora_salida DESC
                """),
                engine,
                params={"doc": documento}
            )
        except Exception as e:
            permisos_abiertos = pd.DataFrame()
            st.warning(
                "No fue posible consultar permisos. "
                "Verifique que la tabla permisos_usuarios exista."
            )

        if permisos_abiertos.empty:
            st.info("Este usuario no tiene permisos abiertos.")
        else:
            permiso = permisos_abiertos.iloc[0]

            st.info(
                f"Permiso abierto desde {permiso.get('fecha_salida')} "
                f"{permiso.get('hora_salida')}."
            )

            c1, c2 = st.columns(2)
            fecha_regreso_real = c1.date_input(
                "Fecha de regreso",
                value=date.today(),
                key=f"perm_fecha_reg_real_{documento}"
            )
            hora_regreso_real = c2.time_input(
                "Hora de regreso",
                key=f"perm_hora_reg_real_{documento}"
            )

            obs_regreso = st.text_area(
                "Observación del regreso",
                key=f"perm_obs_regreso_{documento}"
            )

            conf_regreso = st.checkbox(
                "Confirmo el regreso del usuario",
                key=f"perm_conf_regreso_{documento}"
            )

            if st.button(
                "↩️ Registrar regreso",
                use_container_width=True,
                type="primary",
                key=f"perm_guardar_regreso_{documento}"
            ):
                if not conf_regreso:
                    st.error("Debe confirmar el regreso.")
                else:
                    usuario_registra = st.session_state.get(
                        "usuario_actual", "inspirador"
                    )
                    permiso_id = int(permiso["id"])

                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                UPDATE permisos_usuarios
                                SET fecha_regreso_real = :fecha,
                                    hora_regreso_real = :hora,
                                    estado_permiso = 'CERRADO',
                                    observacion_regreso = :obs,
                                    cerrado_en = NOW()
                                WHERE id = :id
                            """),
                            {
                                "fecha": fecha_regreso_real,
                                "hora": hora_regreso_real,
                                "obs": obs_regreso.strip(),
                                "id": permiso_id
                            }
                        )

                        conn.execute(
                            text("""
                                INSERT INTO movimientos_habitante (
                                    numero_identificacion,
                                    tipo_movimiento,
                                    modalidad,
                                    usuario_registra,
                                    observacion
                                )
                                VALUES (
                                    :doc,
                                    'REGRESO_PERMISO',
                                    :modalidad,
                                    :usuario,
                                    :observacion
                                )
                            """),
                            {
                                "doc": documento,
                                "modalidad": u.get("modalidad"),
                                "usuario": usuario_registra,
                                "observacion": obs_regreso.strip()
                            }
                        )

                    registrar_auditoria(
                        "REGRESO_PERMISO",
                        documento=documento,
                        modulo="Gestión Móvil",
                        valor_anterior="PERMISO ABIERTO",
                        valor_nuevo="PERMISO CERRADO",
                        observacion=obs_regreso.strip()[:500]
                    )

                    reporte = _texto_whatsapp_movimiento(
                        "REGRESO DE PERMISO",
                        u.get("nombres"),
                        u.get("apellidos"),
                        documento,
                        modalidad=u.get("modalidad"),
                        fecha=fecha_regreso_real,
                        hora=hora_regreso_real,
                        detalle=obs_regreso.strip(),
                        responsable=usuario_registra
                    )

                    st.session_state[
                        f"reporte_whatsapp_{documento}"
                    ] = reporte
                    st.success("✅ Regreso de permiso registrado.")
                    invalidar_cache_datos()

            reporte_guardado = st.session_state.get(
                f"reporte_whatsapp_{documento}"
            )
            if reporte_guardado:
                _boton_whatsapp(
                    reporte_guardado,
                    f"wa_regreso_{documento}"
                )

    # --------------------------------------------------------
    # Sanción / Expulsión
    # --------------------------------------------------------
    elif accion in ["⛔ Sanción / Expulsión", "⛔ Sanciones / Expulsiones"]:

        st.markdown("#### ⛔ Sanción / Expulsión")

        tipo = st.selectbox(
            "Tipo de medida",
            ["SUSPENSIÓN", "EXPULSIÓN"],
            key=f"movil_tipo_medida_{documento}"
        )

        c1, c2 = st.columns(2)
        inicio = c1.date_input(
            "Inicio",
            value=date.today(),
            key=f"movil_inicio_medida_{documento}"
        )
        fin = c2.date_input(
            "Finalización / revisión",
            value=date.today() + timedelta(days=3),
            key=f"movil_fin_medida_{documento}"
        )

        motivo = st.text_area(
            "Motivo *",
            key=f"movil_motivo_medida_{documento}"
        )

        obs = st.text_area(
            "Observación",
            key=f"movil_obs_medida_{documento}"
        )

        conf = st.checkbox(
            "Confirmo el registro de la medida",
            key=f"movil_conf_medida_{documento}"
        )

        if st.button(
            "⛔ Guardar medida",
            use_container_width=True,
            type="primary",
            key=f"movil_guardar_medida_{documento}"
        ):
            if not motivo.strip():
                st.error("Debe registrar el motivo.")
            elif not conf:
                st.error("Debe confirmar la medida.")
            elif fin < inicio:
                st.error("La fecha final no puede ser anterior al inicio.")
            else:
                usuario = st.session_state.get(
                    "usuario_actual", "inspirador"
                )

                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO sanciones_usuarios (
                                numero_identificacion,
                                tipo_medida,
                                motivo,
                                fecha_inicio,
                                fecha_fin,
                                estado_medida,
                                observacion,
                                usuario_registra
                            )
                            VALUES (
                                :doc, :tipo, :motivo, :inicio, :fin,
                                'ACTIVA', :obs, :usuario
                            )
                        """),
                        {
                            "doc": documento,
                            "tipo": tipo,
                            "motivo": motivo.strip(),
                            "inicio": inicio,
                            "fin": fin,
                            "obs": obs.strip(),
                            "usuario": usuario
                        }
                    )

                    conn.execute(
                        text("""
                            UPDATE habitante_de_calle
                            SET estado_caso='INACTIVO',
                                modalidad=NULL
                            WHERE TRIM(
                                CAST(numero_identificacion AS TEXT)
                            )=:doc
                        """),
                        {"doc": documento}
                    )

                    conn.execute(
                        text("""
                            INSERT INTO movimientos_habitante (
                                numero_identificacion,
                                tipo_movimiento,
                                modalidad,
                                usuario_registra,
                                observacion
                            )
                            VALUES (
                                :doc, :tipo_mov, :modalidad,
                                :usuario, :observacion
                            )
                        """),
                        {
                            "doc": documento,
                            "tipo_mov": (
                                "SUSPENSION"
                                if tipo == "SUSPENSIÓN"
                                else "EXPULSION"
                            ),
                            "modalidad": u.get("modalidad"),
                            "usuario": usuario,
                            "observacion": motivo.strip()
                        }
                    )

                registrar_auditoria(
                    "REGISTRAR_MEDIDA_DISCIPLINARIA",
                    documento=documento,
                    modulo="Gestión Móvil",
                    valor_nuevo=tipo,
                    observacion=motivo.strip()[:500]
                )
                invalidar_cache_datos()
                st.success("✅ Medida registrada correctamente.")
                st.rerun()

    # --------------------------------------------------------
    # Profesional: egreso
    # --------------------------------------------------------
    elif accion == "🏆 Registrar egreso":

        if rol_visible not in ["PROFESIONAL", "COORDINACION"]:
            st.error(
                "El registro de egreso corresponde al equipo profesional."
            )
        else:
            registrar_egreso_profesional_v12(
                u,
                documento
            )

    # --------------------------------------------------------
    # Caracterización / consulta
    # --------------------------------------------------------
    elif accion in ["🧾 Completar información", "🧾 Caracterización", "🧾 Consultar información"]:

        st.markdown("#### 🧾 Información del usuario")

        persona_full = pd.read_sql(
            text("""
                SELECT *
                FROM habitante_de_calle
                WHERE TRIM(CAST(numero_identificacion AS TEXT))=:doc
                LIMIT 1
            """),
            engine,
            params={"doc": documento}
        )

        if persona_full.empty:
            st.warning("No se encontró la ficha.")
        else:
            pf = persona_full.iloc[0]
            editable = rol_visible in ["INSPIRADOR", "COORDINACION"]

            candidatos = [
                ("Departamento de procedencia",
                 ["departamento_procedencia", "departamento_de_procedencia"]),
                ("Consumo",
                 ["tipo_consumo", "tipo_de_consumo"]),
                ("Grupo SISBÉN",
                 ["grupo_sisben"]),
                ("Discapacidad",
                 ["personas_con_discapacidad"]),
                ("Categoría discapacidad",
                 ["categoria_discapacidad"]),
                ("Nivel educativo",
                 ["nivel_educativo"]),
                ("Condición ocupacional",
                 ["condicion_ocupacional"]),
                ("Barrio / vereda",
                 ["barrio_vereda"]),
                ("Comuna / corregimiento",
                 ["comuna_corregimiento"]),
                ("Dirección",
                 ["direccion"]),
                ("Teléfono",
                 ["telefono"]),
                ("Correo",
                 ["correo"]),
                ("Grupo étnico",
                 ["grupos_etnicos"]),
                ("Orientación sexual",
                 ["orientacion_sexual_lgtbi"])
            ]

            existentes = []
            for etiqueta, opciones_col in candidatos:
                encontrada = next(
                    (c for c in opciones_col if c in persona_full.columns),
                    None
                )
                if encontrada:
                    existentes.append((etiqueta, encontrada))

            if editable:
                with st.form(f"movil_car_{documento}"):
                    nuevos = {}
                    for etiqueta, col in existentes:
                        valor = pf.get(col)
                        valor = "" if pd.isna(valor) else str(valor)
                        nuevos[col] = st.text_input(
                            etiqueta,
                            value=valor,
                            key=f"m_{col}_{documento}"
                        )

                    save = st.form_submit_button(
                        "💾 Guardar información",
                        use_container_width=True,
                        type="primary"
                    )

                if save and existentes:
                    sets = []
                    params = {"doc": documento}

                    for i, (_, col) in enumerate(existentes):
                        p = f"p{i}"
                        sets.append(f'"{col}"=:{p}')
                        params[p] = nuevos[col].strip()

                    with engine.begin() as conn:
                        conn.execute(
                            text(
                                "UPDATE habitante_de_calle SET "
                                + ",".join(sets)
                                + """
                                WHERE TRIM(
                                    CAST(numero_identificacion AS TEXT)
                                )=:doc
                                """
                            ),
                            params
                        )

                    registrar_auditoria(
                        "ACTUALIZAR_CARACTERIZACION",
                        documento=documento,
                        modulo="Gestión Móvil"
                    )
                    invalidar_cache_datos()
                    st.success("✅ Información actualizada.")
                    st.rerun()
            else:
                datos_ver = {
                    etiqueta: (
                        "" if pd.isna(pf.get(col)) else pf.get(col)
                    )
                    for etiqueta, col in existentes
                }

                st.dataframe(
                    pd.DataFrame(
                        list(datos_ver.items()),
                        columns=["Campo", "Información"]
                    ),
                    use_container_width=True,
                    hide_index=True
                )

    # --------------------------------------------------------
    # Historia
    # --------------------------------------------------------
    elif accion == "📚 Ver historia":

        st.markdown("#### 📚 Historia reciente")

        try:
            movs = pd.read_sql(
                text("""
                    SELECT
                        fecha_movimiento,
                        tipo_movimiento,
                        modalidad,
                        usuario_registra,
                        observacion
                    FROM movimientos_habitante
                    WHERE TRIM(
                        CAST(numero_identificacion AS TEXT)
                    )=:doc
                    ORDER BY fecha_movimiento DESC
                    LIMIT 30
                """),
                engine,
                params={"doc": documento}
            )

            if movs.empty:
                st.info("Sin movimientos registrados.")
            else:
                st.dataframe(
                    movs,
                    use_container_width=True,
                    hide_index=True
                )

            try:
                permisos_hist = pd.read_sql(
                    text("""
                        SELECT
                            fecha_salida,
                            hora_salida,
                            motivo,
                            fecha_regreso_estimada,
                            hora_regreso_estimada,
                            fecha_regreso_real,
                            hora_regreso_real,
                            estado_permiso,
                            autoriza
                        FROM permisos_usuarios
                        WHERE TRIM(CAST(numero_identificacion AS TEXT))=:doc
                        ORDER BY fecha_salida DESC, hora_salida DESC
                        LIMIT 20
                    """),
                    engine,
                    params={"doc": documento}
                )
                if not permisos_hist.empty:
                    st.markdown("##### 🚪 Historial de permisos")
                    st.dataframe(
                        permisos_hist,
                        use_container_width=True,
                        hide_index=True
                    )
            except Exception:
                pass
        except Exception as e:
            st.warning(f"No fue posible consultar la historia: {e}")

    elif accion == "🎯 PAI / Seguimiento":

        # V15.2 - acceso directo al PAI desde Gestión Profesional
        cedula_pai = str(
            st.session_state.get("documento_funcionario", "")
        ).strip()

        rol_pai = str(
            st.session_state.get("rol_actual", "")
        ).upper()

        acceso_pai_usuario = rol_pai in ["COORDINACION", "MANAGER"]

        if rol_pai == "PROFESIONAL" and cedula_pai:
            try:
                permiso_pai = pd.read_sql(
                    text("""
                        SELECT COALESCE(acceso_pai, FALSE) AS acceso_pai
                        FROM funcionarios_sistema
                        WHERE cedula=:cedula
                          AND activo=TRUE
                        LIMIT 1
                    """),
                    engine,
                    params={"cedula": cedula_pai}
                )

                acceso_pai_usuario = (
                    not permiso_pai.empty
                    and bool(permiso_pai.iloc[0]["acceso_pai"])
                )
            except Exception:
                acceso_pai_usuario = False

        if not acceso_pai_usuario:
            st.warning(
                "Este funcionario no tiene habilitado el acceso al PAI."
            )
        else:
            st.markdown("#### 🎯 PAI y Seguimiento Profesional")
            st.write(
                f"**Usuario:** {u.get('nombres','')} {u.get('apellidos','')}"
            )
            st.write(f"**Documento:** {documento}")

            try:
                objetivos_usuario_pai = pd.read_sql(
                    text("""
                        SELECT
                            id,
                            objetivo_tipo,
                            porcentaje_avance,
                            estado,
                            fecha_meta,
                            fecha_ultimo_seguimiento
                        FROM pai_objetivos
                        WHERE TRIM(CAST(documento_usuario AS TEXT))=:doc
                        ORDER BY fecha_meta NULLS LAST, fecha_apertura DESC
                    """),
                    engine,
                    params={"doc": documento}
                )
            except Exception:
                objetivos_usuario_pai = pd.DataFrame()

            if objetivos_usuario_pai.empty:
                st.info(
                    "Este usuario todavía no tiene objetivos PAI registrados."
                )
            else:
                st.dataframe(
                    objetivos_usuario_pai,
                    use_container_width=True,
                    hide_index=True
                )

            if st.button(
                "🎯 Abrir PAI / Registrar seguimiento",
                use_container_width=True,
                type="primary",
                key=f"abrir_pai_desde_gestion_{documento}"
            ):
                # El panel profesional tomará este usuario como selección inicial
                st.session_state["v15_usuario_pendiente"] = str(documento)
                st.session_state.page = "panel_profesional_v15"
                st.rerun()



# ============================================================
# V12 - ADMINISTRACIÓN DE USUARIOS DEL SISTEMA
# ============================================================
    # V14.1: herramientas operativas al final de Gestión Móvil.
    if rol_visible == "INSPIRADOR":
        st.divider()
        panel_inspirador_simple_v14()


def gestion_personal_v12_1():

    if st.session_state.get("rol_actual") not in ["COORDINACION", "MANAGER"]:
        st.error("Acceso exclusivo para Coordinación o Manager.")
        return

    st.title("👥 Personal autorizado")
    st.caption(
        "Administración del personal autorizado: Inspiradores, Profesionales y Coordinación."
    )

    tab_crear, tab_admin = st.tabs(
        ["➕ Crear cuenta", "📋 Administrar"]
    )

    with tab_crear:
        with st.form("crear_funcionario_v12"):
            nombre = st.text_input("Nombre completo *")
            cedula = st.text_input("Cédula *")
            rol = st.selectbox(
                "Rol",
                [
                    "INSPIRADOR",
                    "PROFESIONAL",
                    "COORDINACION",
                    "MANAGER"
                ]
            )
            clave = st.text_input(
                "Contraseña inicial *",
                type="password"
            )
            clave2 = st.text_input(
                "Confirmar contraseña *",
                type="password"
            )

            crear = st.form_submit_button(
                "✅ Crear cuenta",
                use_container_width=True,
                type="primary"
            )

        if crear:
            doc = limpiar_documento(cedula)

            if not nombre.strip() or not doc:
                st.error(
                    "Nombre y cédula son obligatorios."
                )
            elif len(clave) < 8:
                st.error(
                    "La contraseña debe tener mínimo 8 caracteres."
                )
            elif clave != clave2:
                st.error("Las contraseñas no coinciden.")
            else:
                try:
                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                INSERT INTO public.funcionarios_sistema (
                                    cedula,
                                    nombre,
                                    rol,
                                    password_hash,
                                    activo,
                                    creado_por
                                )
                                VALUES (
                                    :cedula,
                                    :nombre,
                                    :rol,
                                    crypt(
                                        :clave,
                                        gen_salt('bf')
                                    ),
                                    TRUE,
                                    :creado_por
                                )
                            """),
                            {
                                "cedula": doc,
                                "nombre": nombre.strip(),
                                "rol": rol,
                                "clave": clave,
                                "creado_por": st.session_state.get(
                                    "usuario_actual",
                                    "coordinacion"
                                )
                            }
                        )

                    st.success(
                        "✅ Acceso creado correctamente."
                    )

                except Exception:
                    st.error(
                        "No fue posible crear la cuenta. "
                        "Verifique que la cédula no esté registrada."
                    )

    with tab_admin:

        usuarios = pd.read_sql(
            text("""
                SELECT
                    cedula,
                    nombre,
                    rol,
                    activo,
                    creado_en,
                    ultimo_acceso
                FROM public.funcionarios_sistema
                ORDER BY activo DESC, nombre
            """),
            engine
        )

        st.dataframe(
            usuarios,
            use_container_width=True,
            hide_index=True
        )

        if usuarios.empty:
            return

        indices = usuarios.index.tolist()

        ix = st.selectbox(
            "Seleccione un funcionario",
            indices,
            format_func=lambda i: (
                f"{usuarios.loc[i,'nombre']} · "
                f"{usuarios.loc[i,'cedula']} · "
                f"{usuarios.loc[i,'rol']}"
            )
        )

        usr = usuarios.loc[ix]
        doc = str(usr["cedula"]).strip()

        roles = [
            "INSPIRADOR",
            "PROFESIONAL",
            "COORDINACION",
            "MANAGER"
        ]

        c1, c2 = st.columns(2)

        rol_nuevo = c1.selectbox(
            "Rol",
            roles,
            index=roles.index(
                str(usr["rol"]).upper()
            ),
            key=f"v12_rol_{doc}"
        )

        activo_nuevo = c2.checkbox(
            "Cuenta activa",
            value=bool(usr["activo"]),
            key=f"v12_activo_{doc}"
        )

        if st.button(
            "💾 Guardar rol / estado",
            use_container_width=True,
            key=f"v12_guardar_usr_{doc}"
        ):

            if (
                doc
                == st.session_state.get(
                    "documento_funcionario"
                )
                and not activo_nuevo
            ):
                st.error(
                    "No puede desactivar su propia cuenta "
                    "durante la sesión."
                )
            else:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            UPDATE public.funcionarios_sistema
                            SET
                                rol=:rol,
                                activo=:activo,
                                actualizado_en=NOW()
                            WHERE cedula=:cedula
                        """),
                        {
                            "rol": rol_nuevo,
                            "activo": activo_nuevo,
                            "cedula": doc
                        }
                    )

                st.success("✅ Acceso actualizado.")
                st.rerun()

        st.markdown("#### 🔑 Restablecer contraseña")

        nueva = st.text_input(
            "Nueva contraseña",
            type="password",
            key=f"v12_pass_{doc}"
        )

        nueva2 = st.text_input(
            "Confirmar nueva contraseña",
            type="password",
            key=f"v12_pass2_{doc}"
        )

        if st.button(
            "🔑 Restablecer contraseña",
            use_container_width=True,
            key=f"v12_reset_{doc}"
        ):

            if len(nueva) < 8:
                st.error(
                    "La contraseña debe tener mínimo 8 caracteres."
                )
            elif nueva != nueva2:
                st.error("Las contraseñas no coinciden.")
            else:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            UPDATE public.funcionarios_sistema
                            SET
                                password_hash=crypt(
                                    :clave,
                                    gen_salt('bf')
                                ),
                                actualizado_en=NOW()
                            WHERE cedula=:cedula
                        """),
                        {
                            "clave": nueva,
                            "cedula": doc
                        }
                    )

                st.success(
                    "✅ Contraseña restablecida."
                )


# ============================================================
# V12 - HISTORIA INTEGRAL UNIFICADA
# ============================================================
def historia_integral_v12():

    st.title("📚 Historia Integral")
    st.caption(
        "Ingreso, reingresos, permisos, sanciones, expulsiones, "
        "PAI, seguimientos y egresos en una sola línea de tiempo."
    )

    termino = st.text_input(
        "🔎 Buscar persona",
        placeholder="Nombre, apellido o documento",
        key="v12_hist_buscar"
    )

    if len(termino.strip()) < 2:
        st.info("Digite al menos 2 caracteres.")
        return

    patron = f"%{termino.strip()}%"

    personas = pd.read_sql(
        text("""
            SELECT
                numero_identificacion,
                nombres,
                apellidos,
                estado_caso,
                modalidad
            FROM habitante_de_calle
            WHERE CAST(numero_identificacion AS TEXT) ILIKE :patron
               OR COALESCE(nombres,'') ILIKE :patron
               OR COALESCE(apellidos,'') ILIKE :patron
               OR (
                    COALESCE(nombres,'') || ' ' ||
                    COALESCE(apellidos,'')
                  ) ILIKE :patron
            ORDER BY nombres, apellidos
            LIMIT 20
        """),
        engine,
        params={"patron": patron}
    )

    if personas.empty:
        st.warning("No se encontraron personas.")
        return

    indices = personas.index.tolist()

    ix = st.selectbox(
        "Seleccione la persona",
        indices,
        format_func=lambda i: (
            f"{personas.loc[i,'nombres']} "
            f"{personas.loc[i,'apellidos']} · "
            f"{personas.loc[i,'numero_identificacion']}"
        ),
        key="v12_hist_persona"
    )

    persona = personas.loc[ix]
    doc = str(
        persona["numero_identificacion"]
    ).strip()

    st.markdown(
        f"### 👤 {persona['nombres']} {persona['apellidos']}\n"
        f"**Documento:** {doc}  \n"
        f"**Estado:** {persona.get('estado_caso') or 'Sin dato'} · "
        f"**Modalidad:** {persona.get('modalidad') or 'Sin modalidad'}"
    )

    eventos = []

    def agregar(
        fecha,
        evento,
        detalle=""
    ):
        fecha_pd = pd.to_datetime(
            fecha,
            errors="coerce"
        )
        if pd.isna(fecha_pd):
            return

        eventos.append({
            "Fecha": fecha_pd,
            "Evento": evento,
            "Detalle": detalle
        })

    # MOVIMIENTOS
    try:
        mov = pd.read_sql(
            text("""
                SELECT *
                FROM movimientos_habitante
                WHERE TRIM(
                    CAST(numero_identificacion AS TEXT)
                )=:doc
                ORDER BY fecha_movimiento DESC
            """),
            engine,
            params={"doc": doc}
        )

        for _, r in mov.iterrows():
            agregar(
                r.get("fecha_movimiento"),
                str(
                    r.get("tipo_movimiento")
                    or "MOVIMIENTO"
                ),
                " | ".join(
                    x for x in [
                        f"Modalidad: {r.get('modalidad')}"
                        if pd.notna(r.get("modalidad"))
                        else "",
                        f"Registra: {r.get('usuario_registra')}"
                        if pd.notna(r.get("usuario_registra"))
                        else "",
                        f"Obs.: {r.get('observacion')}"
                        if pd.notna(r.get("observacion"))
                        else ""
                    ]
                    if x
                )
            )
    except Exception:
        pass

    # PERMISOS
    try:
        permisos = pd.read_sql(
            text("""
                SELECT *
                FROM permisos_usuarios
                WHERE TRIM(
                    CAST(numero_identificacion AS TEXT)
                )=:doc
            """),
            engine,
            params={"doc": doc}
        )

        for _, r in permisos.iterrows():
            agregar(
                r.get("creado_en")
                if "creado_en" in permisos.columns
                else r.get("fecha_salida"),
                "PERMISO",
                (
                    f"Salida: {r.get('fecha_salida')} "
                    f"{r.get('hora_salida')} | "
                    f"Regreso estimado: "
                    f"{r.get('fecha_regreso_estimada')} "
                    f"{r.get('hora_regreso_estimada')} | "
                    f"Regreso real: "
                    f"{r.get('fecha_regreso_real')} "
                    f"{r.get('hora_regreso_real')} | "
                    f"Estado: {r.get('estado_permiso')} | "
                    f"Motivo: {r.get('motivo')}"
                )
            )
    except Exception:
        pass

    # SANCIONES Y EXPULSIONES
    try:
        sanciones = pd.read_sql(
            text("""
                SELECT *
                FROM sanciones_usuarios
                WHERE TRIM(
                    CAST(numero_identificacion AS TEXT)
                )=:doc
            """),
            engine,
            params={"doc": doc}
        )

        for _, r in sanciones.iterrows():
            agregar(
                r.get("creado_en"),
                str(
                    r.get("tipo_medida")
                    or "MEDIDA"
                ),
                (
                    f"Motivo: {r.get('motivo')} | "
                    f"Inicio: {r.get('fecha_inicio')} | "
                    f"Fin: {r.get('fecha_fin')} | "
                    f"Estado: {r.get('estado_medida')} | "
                    f"Registra: {r.get('usuario_registra')}"
                )
            )
    except Exception:
        pass

    # PAI
    try:
        pai = pd.read_sql(
            text("""
                SELECT *
                FROM pai_objetivos
                WHERE TRIM(
                    CAST(documento_usuario AS TEXT)
                )=:doc
            """),
            engine,
            params={"doc": doc}
        )

        for _, r in pai.iterrows():
            agregar(
                r.get("fecha_apertura"),
                "PAI - OBJETIVO",
                (
                    f"{r.get('objetivo_descripcion')} | "
                    f"Estado: {r.get('estado')} | "
                    f"Avance: {r.get('porcentaje_avance')}% | "
                    f"Meta: {r.get('fecha_meta')}"
                )
            )
    except Exception:
        pass

    # SEGUIMIENTOS PAI
    try:
        novedades = pd.read_sql(
            text("""
                SELECT *
                FROM pai_novedades
                WHERE TRIM(
                    CAST(documento_usuario AS TEXT)
                )=:doc
            """),
            engine,
            params={"doc": doc}
        )

        fecha_col = next(
            (
                c for c in [
                    "fecha_registro",
                    "fecha",
                    "creado_en",
                    "fecha_novedad"
                ]
                if c in novedades.columns
            ),
            None
        )

        if fecha_col:
            for _, r in novedades.iterrows():
                detalle = " | ".join(
                    str(r.get(c))
                    for c in [
                        "actividad",
                        "observacion",
                        "profesional"
                    ]
                    if c in novedades.columns
                    and pd.notna(r.get(c))
                )

                agregar(
                    r.get(fecha_col),
                    "SEGUIMIENTO PAI",
                    detalle
                )
    except Exception:
        pass

    # EGRESOS
    try:
        cols_e = set(
            pd.read_sql(
                text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema='public'
                      AND table_name='personas_caracterizacion'
                """),
                engine
            )["column_name"].tolist()
        )

        col_doc = (
            "numero_identidad"
            if "numero_identidad" in cols_e
            else "numero_identificacion"
        )

        egresos = pd.read_sql(
            text(
                f"""
                SELECT *
                FROM personas_caracterizacion
                WHERE TRIM(
                    CAST("{col_doc}" AS TEXT)
                )=:doc
                  AND UPPER(
                    TRIM(
                        COALESCE(estado_caso,'')
                    )
                  )='EGRESADO'
                """
            ),
            engine,
            params={"doc": doc}
        )

        for _, r in egresos.iterrows():
            agregar(
                r.get("fecha_egreso"),
                "EGRESO",
                (
                    f"{r.get('observaciones_egreso')} | "
                    f"Profesional: "
                    f"{r.get('funcionario_egreso')}"
                )
            )
    except Exception:
        pass

    if not eventos:
        st.info(
            "No hay eventos históricos registrados."
        )
        return

    timeline = pd.DataFrame(eventos)
    timeline = timeline.dropna(
        subset=["Fecha"]
    ).sort_values(
        "Fecha",
        ascending=False
    )

    st.dataframe(
        timeline,
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "⬇️ Descargar historia en CSV",
        timeline.to_csv(
            index=False
        ).encode("utf-8-sig"),
        file_name=f"historia_integral_{doc}.csv",
        mime="text/csv",
        use_container_width=True
    )



# ============================================================
# V13 - CONTROL DE TURNO, PRESENCIA Y NOVEDADES
# ============================================================
def control_turno_v13():

    rol = str(st.session_state.get("rol_actual", "")).upper()
    if rol not in ["INSPIRADOR", "COORDINACION", "MANAGER"]:
        st.error("Este módulo está habilitado para Inspiradores, Coordinación y Manager.")
        return

    st.title("🕐 Control de Turno y Presencia")
    st.caption(
        "Estado operativo del albergue en tiempo real. "
        "La presencia se calcula automáticamente a partir de usuarios activos y permisos abiertos."
    )

    ahora = datetime.now()
    responsable = st.session_state.get("usuario_actual", "sistema")

    # --------------------------------------------------------
    # Base activa
    # --------------------------------------------------------
    activos = pd.read_sql(
        text("""
            SELECT
                TRIM(CAST(numero_identificacion AS TEXT)) AS documento,
                nombres,
                apellidos,
                estado_caso,
                modalidad
            FROM habitante_de_calle
            WHERE UPPER(TRIM(COALESCE(estado_caso,''))) = 'ACTIVO'
              AND modalidad IS NOT NULL
              AND TRIM(CAST(modalidad AS TEXT)) <> ''
        """),
        engine
    )

    # --------------------------------------------------------
    # Permisos abiertos
    # --------------------------------------------------------
    try:
        permisos = pd.read_sql(
            text("""
                SELECT
                    id,
                    TRIM(CAST(numero_identificacion AS TEXT)) AS documento,
                    fecha_salida,
                    hora_salida,
                    fecha_regreso_estimada,
                    hora_regreso_estimada,
                    motivo,
                    autoriza,
                    observacion,
                    usuario_registra
                FROM permisos_usuarios
                WHERE UPPER(TRIM(COALESCE(estado_permiso,''))) = 'ABIERTO'
                ORDER BY fecha_regreso_estimada, hora_regreso_estimada
            """),
            engine
        )
    except Exception:
        permisos = pd.DataFrame()

    docs_fuera = set()
    if not permisos.empty:
        docs_fuera = set(permisos["documento"].astype(str).str.strip())

    presentes = activos[
        ~activos["documento"].astype(str).str.strip().isin(docs_fuera)
    ].copy()

    fuera = activos[
        activos["documento"].astype(str).str.strip().isin(docs_fuera)
    ].copy()

    # Unir datos del permiso para saber vencimiento.
    permisos_det = pd.DataFrame()
    if not permisos.empty:
        permisos_det = permisos.merge(
            activos[
                ["documento", "nombres", "apellidos", "modalidad"]
            ],
            on="documento",
            how="left"
        )

        permisos_det["regreso_estimado_dt"] = pd.to_datetime(
            permisos_det["fecha_regreso_estimada"].astype(str)
            + " "
            + permisos_det["hora_regreso_estimada"].astype(str),
            errors="coerce"
        )

        permisos_det["situacion"] = permisos_det[
            "regreso_estimado_dt"
        ].apply(
            lambda x: (
                "🔴 VENCIDO"
                if pd.notna(x) and x.to_pydatetime() < ahora
                else "🟢 EN TIEMPO"
            )
        )

        vencidos = permisos_det[
            permisos_det["situacion"] == "🔴 VENCIDO"
        ].copy()
    else:
        vencidos = pd.DataFrame()

    # --------------------------------------------------------
    # Movimientos del día
    # --------------------------------------------------------
    try:
        movimientos_hoy = pd.read_sql(
            text("""
                SELECT
                    fecha_movimiento,
                    numero_identificacion,
                    tipo_movimiento,
                    modalidad,
                    usuario_registra,
                    observacion
                FROM movimientos_habitante
                WHERE fecha_movimiento >= CURRENT_DATE
                  AND fecha_movimiento < CURRENT_DATE + INTERVAL '1 day'
                ORDER BY fecha_movimiento DESC
            """),
            engine
        )
    except Exception:
        movimientos_hoy = pd.DataFrame()

    ingresos_hoy = 0
    reingresos_hoy = 0
    salidas_permiso_hoy = 0
    regresos_permiso_hoy = 0

    if not movimientos_hoy.empty:
        tipos_hoy = movimientos_hoy["tipo_movimiento"].astype(str).str.upper()
        ingresos_hoy = int((tipos_hoy == "INGRESO").sum())
        reingresos_hoy = int((tipos_hoy == "REINGRESO").sum())
        salidas_permiso_hoy = int((tipos_hoy == "SALIDA_PERMISO").sum())
        regresos_permiso_hoy = int((tipos_hoy == "REGRESO_PERMISO").sum())

    # --------------------------------------------------------
    # Capacidades configuradas
    # --------------------------------------------------------
    try:
        capacidades = pd.read_sql(
            text("""
                SELECT modalidad, capacidad
                FROM capacidades_modalidad
                WHERE activo = TRUE
                ORDER BY modalidad
            """),
            engine
        )
    except Exception:
        capacidades = pd.DataFrame()

    # --------------------------------------------------------
    # KPIs
    # --------------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🏠 Presentes", len(presentes))
    k2.metric("🚪 Con permiso", len(permisos_det))
    k3.metric("⚠️ Permisos vencidos", len(vencidos))
    k4.metric("🔁 Reingresos hoy", reingresos_hoy)

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("➕ Ingresos hoy", ingresos_hoy)
    k6.metric("➡️ Salidas permiso hoy", salidas_permiso_hoy)
    k7.metric("⬅️ Regresos hoy", regresos_permiso_hoy)
    k8.metric("👥 Activos con modalidad", len(activos))

    # --------------------------------------------------------
    # Ocupación por modalidad
    # --------------------------------------------------------
    st.markdown("### 🏘️ Ocupación actual")

    if presentes.empty:
        ocupacion = pd.DataFrame(columns=["modalidad", "presentes"])
    else:
        ocupacion = (
            presentes.groupby("modalidad")
            .size()
            .reset_index(name="presentes")
        )

    if not capacidades.empty:
        ocupacion = capacidades.merge(
            ocupacion,
            on="modalidad",
            how="left"
        )
        ocupacion["presentes"] = ocupacion["presentes"].fillna(0).astype(int)
        ocupacion["cupos_disponibles"] = (
            ocupacion["capacidad"] - ocupacion["presentes"]
        )
        ocupacion["ocupacion_%"] = (
            ocupacion["presentes"] / ocupacion["capacidad"] * 100
        ).round(1)

        st.dataframe(
            ocupacion,
            use_container_width=True,
            hide_index=True
        )
    else:
        if not ocupacion.empty:
            st.dataframe(
                ocupacion,
                use_container_width=True,
                hide_index=True
            )
        st.info(
            "Aún no hay capacidades configuradas. "
            "Coordinación o Manager puede definirlas en Configuración de cupos."
        )

    # --------------------------------------------------------
    # Tabs operativos
    # --------------------------------------------------------
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏠 Presentes",
        "🚪 Permisos",
        "📝 Novedades",
        "🤝 Entrega de turno",
        "📲 Reporte WhatsApp"
    ])

    with tab1:
        st.markdown("#### Personas presentes")
        if presentes.empty:
            st.info("No hay personas presentes según los registros actuales.")
        else:
            vista_presentes = presentes[
                ["documento", "nombres", "apellidos", "modalidad"]
            ].sort_values(["modalidad", "nombres", "apellidos"])

            filtro_mod = st.selectbox(
                "Filtrar modalidad",
                ["TODAS"] + sorted(
                    vista_presentes["modalidad"]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                ),
                key="v13_filtro_presentes"
            )

            if filtro_mod != "TODAS":
                vista_presentes = vista_presentes[
                    vista_presentes["modalidad"].astype(str) == filtro_mod
                ]

            st.dataframe(
                vista_presentes,
                use_container_width=True,
                hide_index=True
            )

    with tab2:
        st.markdown("#### Personas fuera con permiso")
        st.caption(
            "Seleccione directamente una persona con permiso abierto "
            "para registrar su regreso."
        )

        if permisos_det.empty:
            st.success("No hay permisos abiertos.")
        else:
            # V13.1 - regreso rápido
            permisos_sel = permisos_det.copy()
            permisos_sel["nombre_completo"] = (
                permisos_sel["nombres"].fillna("").astype(str).str.strip()
                + " "
                + permisos_sel["apellidos"].fillna("").astype(str).str.strip()
            ).str.strip()

            permisos_sel["etiqueta"] = permisos_sel.apply(
                lambda r: (
                    f"{r.get('nombre_completo','')} · "
                    f"CC {r.get('documento','')} · "
                    f"{r.get('modalidad','')} · "
                    f"{r.get('situacion','')}"
                ),
                axis=1
            )

            st.markdown("##### ⬅️ Registrar regreso rápido")

            permiso_id_regreso = st.selectbox(
                "¿Quién regresó?",
                permisos_sel["id"].tolist(),
                format_func=lambda x: permisos_sel.loc[
                    permisos_sel["id"] == x, "etiqueta"
                ].iloc[0],
                key="v131_permiso_regreso"
            )

            fila_regreso = permisos_sel.loc[
                permisos_sel["id"] == permiso_id_regreso
            ].iloc[0]

            obs_regreso_rapido = st.text_input(
                "Observación",
                value="REGRESA AL ALBERGUE",
                key="v131_obs_regreso"
            )

            confirmar_regreso_rapido = st.checkbox(
                "Confirmo que la persona ya regresó",
                key="v131_confirma_regreso"
            )

            if st.button(
                "⬅️ Registrar regreso",
                use_container_width=True,
                type="primary",
                key="v131_btn_regreso"
            ):
                if not confirmar_regreso_rapido:
                    st.error("Confirme que la persona ya regresó.")
                else:
                    doc_regreso = str(
                        fila_regreso.get("documento", "")
                    ).strip()

                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                UPDATE permisos_usuarios
                                SET estado_permiso='CERRADO',
                                    fecha_regreso_real=CURRENT_DATE,
                                    hora_regreso_real=CURRENT_TIME,
                                    observacion_regreso=:observacion,
                                    cerrado_en=NOW()
                                WHERE id=:id
                                  AND UPPER(TRIM(COALESCE(estado_permiso,'')))='ABIERTO'
                            """),
                            {
                                "observacion": obs_regreso_rapido.strip(),
                                "id": int(permiso_id_regreso)
                            }
                        )

                        conn.execute(
                            text("""
                                INSERT INTO movimientos_habitante (
                                    numero_identificacion,
                                    tipo_movimiento,
                                    modalidad,
                                    usuario_registra,
                                    observacion
                                )
                                VALUES (
                                    :documento,
                                    'REGRESO_PERMISO',
                                    :modalidad,
                                    :usuario,
                                    :observacion
                                )
                            """),
                            {
                                "documento": doc_regreso,
                                "modalidad": fila_regreso.get("modalidad"),
                                "usuario": responsable,
                                "observacion": obs_regreso_rapido.strip()
                            }
                        )

                    try:
                        registrar_auditoria(
                            accion="REGRESO_PERMISO",
                            modulo="CONTROL_TURNO",
                            numero_identificacion=doc_regreso,
                            valor_anterior="FUERA CON PERMISO",
                            valor_nuevo="PRESENTE",
                            observacion=obs_regreso_rapido.strip()
                        )
                    except Exception:
                        pass

                    try:
                        invalidar_cache_datos()
                    except Exception:
                        pass

                    st.success(
                        f"✅ Regreso registrado: "
                        f"{fila_regreso.get('nombre_completo','')}."
                    )
                    st.rerun()

            st.divider()
            cols_perm = [
                "documento",
                "nombres",
                "apellidos",
                "modalidad",
                "fecha_salida",
                "hora_salida",
                "fecha_regreso_estimada",
                "hora_regreso_estimada",
                "situacion",
                "motivo"
            ]
            cols_perm = [c for c in cols_perm if c in permisos_det.columns]

            st.dataframe(
                permisos_det[cols_perm],
                use_container_width=True,
                hide_index=True
            )

            if not vencidos.empty:
                st.error(
                    f"⚠️ Hay {len(vencidos)} permiso(s) cuyo regreso estimado ya venció."
                )

    with tab3:
        st.markdown("#### 📝 Novedades del turno")
        st.caption(
            "Aquí se registran novedades operativas que debe conocer el siguiente turno."
        )

        with st.form("v13_nueva_novedad"):
            tipo_nov = st.selectbox(
                "Tipo de novedad",
                [
                    "GENERAL",
                    "USUARIO",
                    "CONVIVENCIA",
                    "SALUD",
                    "SEGURIDAD",
                    "INFRAESTRUCTURA",
                    "ALIMENTACIÓN",
                    "OTRA"
                ]
            )

            doc_nov = st.text_input(
                "Documento del usuario relacionado (opcional)"
            )

            novedad = st.text_area(
                "Novedad *",
                placeholder="Describa claramente la situación y lo que queda pendiente."
            )

            prioridad = st.selectbox(
                "Prioridad",
                ["NORMAL", "IMPORTANTE", "URGENTE"]
            )

            guardar_nov = st.form_submit_button(
                "💾 Registrar novedad",
                use_container_width=True,
                type="primary"
            )

        if guardar_nov:
            if not novedad.strip():
                st.error("Debe escribir la novedad.")
            else:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO novedades_turno (
                                tipo_novedad,
                                numero_identificacion,
                                novedad,
                                prioridad,
                                estado,
                                usuario_registra
                            )
                            VALUES (
                                :tipo,
                                NULLIF(:doc,''),
                                :novedad,
                                :prioridad,
                                'PENDIENTE',
                                :usuario
                            )
                        """),
                        {
                            "tipo": tipo_nov,
                            "doc": str(doc_nov).strip(),
                            "novedad": novedad.strip(),
                            "prioridad": prioridad,
                            "usuario": responsable
                        }
                    )
                st.success("✅ Novedad registrada.")
                st.rerun()

        novedades = pd.read_sql(
            text("""
                SELECT
                    id,
                    creado_en,
                    prioridad,
                    tipo_novedad,
                    numero_identificacion,
                    novedad,
                    estado,
                    usuario_registra
                FROM novedades_turno
                WHERE estado = 'PENDIENTE'
                ORDER BY
                    CASE prioridad
                        WHEN 'URGENTE' THEN 1
                        WHEN 'IMPORTANTE' THEN 2
                        ELSE 3
                    END,
                    creado_en DESC
            """),
            engine
        )

        if novedades.empty:
            st.success("No hay novedades pendientes.")
        else:
            st.dataframe(
                novedades,
                use_container_width=True,
                hide_index=True
            )

            if rol in ["COORDINACION", "MANAGER"]:
                ids_nov = novedades["id"].tolist()
                nov_cerrar = st.selectbox(
                    "Marcar novedad como resuelta",
                    ids_nov,
                    format_func=lambda x: (
                        f"#{x} · "
                        + str(
                            novedades.loc[
                                novedades["id"] == x,
                                "novedad"
                            ].iloc[0]
                        )[:80]
                    ),
                    key="v13_cerrar_novedad"
                )

                if st.button(
                    "✅ Marcar como resuelta",
                    use_container_width=True,
                    key="v13_btn_cerrar_novedad"
                ):
                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                UPDATE novedades_turno
                                SET estado='RESUELTA',
                                    resuelto_en=NOW(),
                                    resuelto_por=:usuario
                                WHERE id=:id
                            """),
                            {
                                "usuario": responsable,
                                "id": int(nov_cerrar)
                            }
                        )
                    st.success("Novedad cerrada.")
                    st.rerun()

    with tab4:
        st.markdown("#### 🤝 Entrega / recibo de turno")

        pendientes_count = 0
        try:
            pendientes_count = int(
                pd.read_sql(
                    text("""
                        SELECT COUNT(*) AS total
                        FROM novedades_turno
                        WHERE estado='PENDIENTE'
                    """),
                    engine
                ).iloc[0]["total"]
            )
        except Exception:
            pass

        with st.form("v13_entrega_turno"):
            turno = st.selectbox(
                "Turno",
                ["MAÑANA", "TARDE", "NOCHE"]
            )

            recibe = st.text_input(
                "Nombre de quien recibe el turno *",
                placeholder="Nombre del inspirador que recibe"
            )

            resumen_turno = st.text_area(
                "Resumen / recomendaciones",
                placeholder="Pendientes, situaciones especiales, recomendaciones..."
            )

            confirmar_turno = st.checkbox(
                "Confirmo la entrega del turno"
            )

            guardar_turno = st.form_submit_button(
                "🤝 Registrar entrega de turno",
                use_container_width=True,
                type="primary"
            )

        if guardar_turno:
            if not recibe.strip():
                st.error("Debe indicar quién recibe el turno.")
            elif not confirmar_turno:
                st.error("Debe confirmar la entrega.")
            else:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO entregas_turno (
                                turno,
                                entrega_por,
                                recibe_por,
                                presentes,
                                permisos_abiertos,
                                permisos_vencidos,
                                novedades_pendientes,
                                resumen
                            )
                            VALUES (
                                :turno,
                                :entrega,
                                :recibe,
                                :presentes,
                                :permisos,
                                :vencidos,
                                :novedades,
                                :resumen
                            )
                        """),
                        {
                            "turno": turno,
                            "entrega": responsable,
                            "recibe": recibe.strip(),
                            "presentes": len(presentes),
                            "permisos": len(permisos_det),
                            "vencidos": len(vencidos),
                            "novedades": pendientes_count,
                            "resumen": resumen_turno.strip()
                        }
                    )

                st.success("✅ Entrega de turno registrada.")
                st.rerun()

        ultimas_entregas = pd.read_sql(
            text("""
                SELECT
                    creado_en,
                    turno,
                    entrega_por,
                    recibe_por,
                    presentes,
                    permisos_abiertos,
                    permisos_vencidos,
                    novedades_pendientes,
                    resumen
                FROM entregas_turno
                ORDER BY creado_en DESC
                LIMIT 10
            """),
            engine
        )

        if not ultimas_entregas.empty:
            st.markdown("##### Últimas entregas")
            st.dataframe(
                ultimas_entregas,
                use_container_width=True,
                hide_index=True
            )

    with tab5:
        st.markdown("#### 📲 Reporte operativo para WhatsApp")

        modalidades_txt = []
        if presentes.empty:
            modalidades_txt.append("Sin personas presentes registradas")
        else:
            resumen_mod = (
                presentes.groupby("modalidad")
                .size()
                .sort_values(ascending=False)
            )
            for mod, cantidad in resumen_mod.items():
                modalidades_txt.append(
                    f"• {mod}: {int(cantidad)} presentes"
                )

        vencidos_txt = []
        if not vencidos.empty:
            for _, r in vencidos.head(15).iterrows():
                vencidos_txt.append(
                    f"• {r.get('nombres','')} {r.get('apellidos','')} "
                    f"- CC {r.get('documento','')} "
                    f"- regreso {r.get('fecha_regreso_estimada','')} "
                    f"{r.get('hora_regreso_estimada','')}"
                )

        try:
            nov_pend = pd.read_sql(
                text("""
                    SELECT prioridad, novedad
                    FROM novedades_turno
                    WHERE estado='PENDIENTE'
                    ORDER BY
                        CASE prioridad
                            WHEN 'URGENTE' THEN 1
                            WHEN 'IMPORTANTE' THEN 2
                            ELSE 3
                        END,
                        creado_en DESC
                    LIMIT 10
                """),
                engine
            )
        except Exception:
            nov_pend = pd.DataFrame()

        novedades_txt = []
        if not nov_pend.empty:
            for _, r in nov_pend.iterrows():
                novedades_txt.append(
                    f"• [{r.get('prioridad')}] {r.get('novedad')}"
                )

        reporte = "\n".join([
            "*REPORTE DE TURNO - ALBERGUE*",
            f"*FECHA:* {ahora.strftime('%d/%m/%Y')}",
            f"*HORA:* {ahora.strftime('%H:%M')}",
            "",
            f"*PRESENTES:* {len(presentes)}",
            *modalidades_txt,
            "",
            f"*CON PERMISO:* {len(permisos_det)}",
            f"*PERMISOS VENCIDOS:* {len(vencidos)}",
            f"*INGRESOS HOY:* {ingresos_hoy}",
            f"*REINGRESOS HOY:* {reingresos_hoy}",
            f"*SALIDAS DE PERMISO HOY:* {salidas_permiso_hoy}",
            f"*REGRESOS DE PERMISO HOY:* {regresos_permiso_hoy}",
            "",
            "*PENDIENTES DE REGRESO:*",
            *(vencidos_txt if vencidos_txt else ["• Ninguno"]),
            "",
            "*NOVEDADES PENDIENTES:*",
            *(novedades_txt if novedades_txt else ["• Ninguna"]),
            "",
            f"*GENERA:* {responsable}"
        ])

        _boton_whatsapp(
            reporte,
            "v13_reporte_turno_whatsapp"
        )

    # --------------------------------------------------------
    # Configuración de cupos
    # --------------------------------------------------------
    if rol in ["COORDINACION", "MANAGER"]:
        with st.expander("⚙️ Configuración de cupos por modalidad"):
            st.caption(
                "Esta capacidad se utiliza únicamente para el tablero operativo."
            )

            modalidad_cfg = st.text_input(
                "Modalidad",
                placeholder="Ej. URBANO",
                key="v13_modalidad_cfg"
            )
            capacidad_cfg = st.number_input(
                "Capacidad",
                min_value=1,
                step=1,
                value=100,
                key="v13_capacidad_cfg"
            )

            if st.button(
                "💾 Guardar capacidad",
                use_container_width=True,
                key="v13_guardar_capacidad"
            ):
                if not modalidad_cfg.strip():
                    st.error("Indique la modalidad.")
                else:
                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                INSERT INTO capacidades_modalidad (
                                    modalidad,
                                    capacidad,
                                    activo,
                                    actualizado_por
                                )
                                VALUES (
                                    :modalidad,
                                    :capacidad,
                                    TRUE,
                                    :usuario
                                )
                                ON CONFLICT (modalidad)
                                DO UPDATE SET
                                    capacidad=EXCLUDED.capacidad,
                                    activo=TRUE,
                                    actualizado_por=EXCLUDED.actualizado_por,
                                    actualizado_en=NOW()
                            """),
                            {
                                "modalidad": modalidad_cfg.strip(),
                                "capacidad": int(capacidad_cfg),
                                "usuario": responsable
                            }
                        )
                    st.success("Capacidad actualizada.")
                    st.rerun()


# ============================================================
# DASHBOARD EJECUTIVO
# ============================================================

# ============================================================
# V15 - MI PANEL PROFESIONAL + SUPERVISIÓN PAI
# ============================================================
def _profesional_actual_v15():
    cedula = str(
        st.session_state.get("documento_funcionario", "")
    ).strip()

    if not cedula:
        return None

    try:
        df_map = pd.read_sql(
            text("""
                SELECT
                    m.profesional_id,
                    p.nombre,
                    p.rol
                FROM pai_profesional_funcionario m
                INNER JOIN profesionales p
                    ON p.id = m.profesional_id
                WHERE m.cedula_funcionario = :cedula
                  AND m.activo = TRUE
                LIMIT 1
            """),
            engine,
            params={"cedula": cedula}
        )
        if not df_map.empty:
            return df_map.iloc[0].to_dict()
    except Exception:
        pass

    # Fallback por nombre exacto para no bloquear la operación
    nombre_login = str(
        st.session_state.get("nombre_funcionario", "")
    ).strip()

    if nombre_login:
        try:
            df_prof = pd.read_sql(
                text("""
                    SELECT id AS profesional_id, nombre, rol
                    FROM profesionales
                    WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(:nombre))
                    LIMIT 1
                """),
                engine,
                params={"nombre": nombre_login}
            )
            if not df_prof.empty:
                return df_prof.iloc[0].to_dict()
        except Exception:
            pass

    return None




def _semaforo_integral_usuario_v16(documento):
    """Semáforo integral del caso, tolerante a tablas/campos opcionales."""
    hoy = pd.Timestamp(date.today())
    puntaje = 0
    razones = []

    try:
        objs = pd.read_sql(
            text("""
                SELECT porcentaje_avance, estado, fecha_meta,
                       fecha_ultimo_seguimiento
                FROM pai_objetivos
                WHERE TRIM(CAST(documento_usuario AS TEXT))=:doc
            """),
            engine,
            params={"doc": str(documento)}
        )
    except Exception:
        objs = pd.DataFrame()

    if objs.empty:
        puntaje += 2
        razones.append("Sin objetivos PAI")
    else:
        objs["porcentaje_avance"] = pd.to_numeric(
            objs["porcentaje_avance"], errors="coerce"
        ).fillna(0)
        objs["fecha_meta"] = pd.to_datetime(objs["fecha_meta"], errors="coerce")
        objs["fecha_ultimo_seguimiento"] = pd.to_datetime(
            objs["fecha_ultimo_seguimiento"], errors="coerce"
        )

        cumplido = (
            objs["porcentaje_avance"].ge(100)
            | objs["estado"].fillna("").astype(str).str.upper().eq("CUMPLIDO")
        )
        dias_meta = (objs["fecha_meta"].dt.normalize() - hoy).dt.days
        vencidos = int((~cumplido & dias_meta.lt(0)).sum())

        if vencidos >= 2:
            puntaje += 3
            razones.append(f"{vencidos} objetivos vencidos")
        elif vencidos == 1:
            puntaje += 2
            razones.append("1 objetivo vencido")

        dias_seg = (
            hoy - objs["fecha_ultimo_seguimiento"].dt.normalize()
        ).dt.days
        atrasados = int(
            (
                ~cumplido
                & (
                    objs["fecha_ultimo_seguimiento"].isna()
                    | dias_seg.gt(15)
                )
            ).sum()
        )
        if atrasados >= 2:
            puntaje += 2
            razones.append(f"{atrasados} objetivos sin seguimiento reciente")
        elif atrasados == 1:
            puntaje += 1
            razones.append("Seguimiento pendiente")

    # Las tablas de sanciones/permisos pueden variar entre versiones.
    # Si no están disponibles, el PAI sigue funcionando.
    try:
        sanc = pd.read_sql(
            text("""
                SELECT COUNT(*) AS total
                FROM sanciones_usuarios
                WHERE TRIM(CAST(numero_identificacion AS TEXT))=:doc
                  AND UPPER(TRIM(COALESCE(estado,'')))='ACTIVA'
            """),
            engine,
            params={"doc": str(documento)}
        )
        if not sanc.empty and int(sanc.iloc[0]["total"] or 0) > 0:
            puntaje += 2
            razones.append("Sanción activa")
    except Exception:
        pass

    if puntaje >= 5:
        return "🔴 CRÍTICO", razones
    if puntaje >= 3:
        return "🟠 REQUIERE ATENCIÓN", razones
    if puntaje >= 1:
        return "🟡 EN SEGUIMIENTO", razones
    return "🟢 AL DÍA", razones



def cierre_pai_usuario_v16(documento, profesional_id=None, profesional_nombre=None):
    st.markdown("#### Cierre formal")

    try:
        cierres = pd.read_sql(
            text("""
                SELECT *
                FROM pai_cierres
                WHERE TRIM(CAST(documento_usuario AS TEXT))=:doc
                ORDER BY creado_en DESC
                LIMIT 1
            """),
            engine,
            params={"doc": str(documento)}
        )
    except Exception:
        cierres = pd.DataFrame()

    if not cierres.empty:
        c = cierres.iloc[0]
        st.success(
            f"PAI cerrado el {c.get('fecha_cierre')} · "
            f"Resultado: {c.get('resultado_final')}"
        )
        if c.get("resumen_cierre"):
            st.write(c.get("resumen_cierre"))
        return

    with st.form(f"v16_3_cierre_{documento}"):
        resultado = st.selectbox(
            "Resultado final",
            [
                "METAS CUMPLIDAS",
                "CUMPLIMIENTO PARCIAL",
                "NO CUMPLIDO",
                "EGRESO",
                "RETIRO VOLUNTARIO",
                "TRASLADO",
                "OTRO"
            ]
        )
        resumen = st.text_area("Resumen de cierre *")
        recomendaciones = st.text_area("Recomendaciones posteriores")
        confirmar = st.checkbox("Confirmo el cierre formal del PAI.")
        guardar = st.form_submit_button(
            "✅ Cerrar PAI", use_container_width=True, type="primary"
        )

    if guardar:
        if not resumen.strip():
            st.error("Debe registrar un resumen de cierre.")
        elif not confirmar:
            st.error("Debe confirmar el cierre.")
        else:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO pai_cierres(
                            documento_usuario, fecha_cierre, resultado_final,
                            resumen_cierre, recomendaciones,
                            profesional_referente, cerrado_por
                        )
                        VALUES(
                            :doc, CURRENT_DATE, :resultado, :resumen,
                            :recomendaciones, :profesional_id, :usuario
                        )
                    """),
                    {
                        "doc": str(documento),
                        "resultado": resultado,
                        "resumen": resumen.strip(),
                        "recomendaciones": recomendaciones.strip(),
                        "profesional_id": profesional_id,
                        "usuario": st.session_state.get(
                            "usuario_actual", profesional_nombre or "profesional"
                        )
                    }
                )
            st.success("✅ PAI cerrado formalmente.")
            st.rerun()


def comite_casos_v16():
    rol = str(st.session_state.get("rol_actual", "")).upper()
    if rol not in ["COORDINACION", "MANAGER"]:
        st.error("Acceso exclusivo para Coordinación y Manager.")
        return

    st.title("🧠 Comité de Casos")
    st.caption(
        "Registro de análisis interdisciplinario, decisiones, compromisos "
        "y responsables."
    )

    personas = pd.read_sql(
        text("""
            SELECT
                TRIM(CAST(numero_identificacion AS TEXT)) AS documento,
                nombres,
                apellidos,
                modalidad,
                estado_caso
            FROM habitante_de_calle
            ORDER BY nombres, apellidos
        """),
        engine
    )
    personas["nombre_completo"] = (
        personas["nombres"].fillna("").astype(str).str.strip()
        + " "
        + personas["apellidos"].fillna("").astype(str).str.strip()
    ).str.strip()

    docs = personas["documento"].astype(str).tolist()

    with st.form("v16_nuevo_comite"):
        doc = st.selectbox(
            "Usuario",
            docs,
            format_func=lambda d: (
                personas.loc[
                    personas["documento"].astype(str) == str(d),
                    "nombre_completo"
                ].iloc[0]
                + f" · CC {d}"
            )
        )
        fecha_comite = st.date_input("Fecha del comité", value=date.today())
        situacion = st.text_area("Situación analizada *")
        decision = st.text_area("Decisiones del comité *")
        participantes = st.text_area(
            "Participantes",
            placeholder="Nombres o perfiles participantes"
        )
        crear = st.form_submit_button(
            "💾 Registrar comité",
            use_container_width=True,
            type="primary"
        )

    if crear:
        if not situacion.strip() or not decision.strip():
            st.error("Situación y decisiones son obligatorias.")
        else:
            with engine.begin() as conn:
                res = conn.execute(
                    text("""
                        INSERT INTO comites_casos(
                            documento_usuario,
                            fecha_comite,
                            situacion_analizada,
                            decisiones,
                            participantes,
                            registrado_por
                        )
                        VALUES(
                            :doc,
                            :fecha,
                            :situacion,
                            :decision,
                            :participantes,
                            :usuario
                        )
                        RETURNING id
                    """),
                    {
                        "doc": doc,
                        "fecha": fecha_comite,
                        "situacion": situacion.strip(),
                        "decision": decision.strip(),
                        "participantes": participantes.strip(),
                        "usuario": st.session_state.get(
                            "usuario_actual", "coordinacion"
                        )
                    }
                )
                comite_id = int(res.scalar())
            st.session_state["v16_comite_id"] = comite_id
            st.success("✅ Comité registrado.")

    comites = pd.read_sql(
        text("""
            SELECT
                c.id,
                c.fecha_comite,
                c.documento_usuario,
                h.nombres,
                h.apellidos,
                c.situacion_analizada,
                c.decisiones,
                c.participantes,
                c.registrado_por
            FROM comites_casos c
            LEFT JOIN habitante_de_calle h
              ON TRIM(CAST(h.numero_identificacion AS TEXT))
               = TRIM(CAST(c.documento_usuario AS TEXT))
            ORDER BY c.fecha_comite DESC, c.id DESC
            LIMIT 50
        """),
        engine
    )

    st.markdown("### 📋 Comités recientes")
    if not comites.empty:
        st.dataframe(comites, use_container_width=True, hide_index=True)

        ids = comites["id"].tolist()
        comite_sel = st.selectbox(
            "Comité para agregar compromiso",
            ids,
            key="v16_comite_sel"
        )

        funcionarios = pd.read_sql(
            text("""
                SELECT cedula, nombre
                FROM funcionarios_sistema
                WHERE activo=TRUE
                ORDER BY nombre
            """),
            engine
        )

        with st.form("v16_compromiso"):
            responsable = st.selectbox(
                "Responsable",
                funcionarios["cedula"].astype(str).tolist(),
                format_func=lambda c: (
                    funcionarios.loc[
                        funcionarios["cedula"].astype(str) == str(c),
                        "nombre"
                    ].iloc[0]
                    + f" · CC {c}"
                )
            )
            compromiso = st.text_area("Compromiso *")
            fecha_limite = st.date_input(
                "Fecha límite",
                value=date.today() + timedelta(days=15)
            )
            guardar = st.form_submit_button(
                "➕ Agregar compromiso",
                use_container_width=True
            )

        if guardar:
            if not compromiso.strip():
                st.error("Debe registrar el compromiso.")
            else:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO compromisos_comite(
                                comite_id,
                                compromiso,
                                responsable_cedula,
                                fecha_limite,
                                estado
                            )
                            VALUES(
                                :comite,
                                :compromiso,
                                :responsable,
                                :fecha,
                                'PENDIENTE'
                            )
                        """),
                        {
                            "comite": int(comite_sel),
                            "compromiso": compromiso.strip(),
                            "responsable": str(responsable),
                            "fecha": fecha_limite
                        }
                    )
                st.success("✅ Compromiso agregado.")
                st.rerun()

def panel_profesional_v15():
    st.title("🩺 Mi Panel Profesional")
    st.caption(
        "Seleccione una sola persona y trabaje todo su expediente PAI sin cambiar de contexto."
    )

    rol_actual = str(st.session_state.get("rol_actual", "")).upper()
    cedula_actual = str(st.session_state.get("documento_funcionario", "")).strip()
    nombre_actual = str(st.session_state.get("nombre_funcionario", "")).strip()

    # ------------------------------------------------------------
    # Resolver profesional PAI
    # ------------------------------------------------------------
    prof_id = None
    prof_nombre = None

    if rol_actual == "PROFESIONAL":
        acceso = pd.read_sql(
            text("""
                SELECT acceso_pai
                FROM funcionarios_sistema
                WHERE TRIM(CAST(cedula AS TEXT))=:cedula
                LIMIT 1
            """),
            engine,
            params={"cedula": cedula_actual}
        )
        if acceso.empty or not bool(acceso.iloc[0].get("acceso_pai", False)):
            st.error("No tiene habilitado el acceso al módulo PAI.")
            return

        vinculo = pd.read_sql(
            text("""
                SELECT
                    ppf.profesional_id,
                    p.nombre
                FROM pai_profesional_funcionario ppf
                LEFT JOIN profesionales p
                  ON p.id = ppf.profesional_id
                WHERE TRIM(CAST(ppf.cedula_funcionario AS TEXT))=:cedula
                  AND ppf.activo=TRUE
                LIMIT 1
            """),
            engine,
            params={"cedula": cedula_actual}
        )
        if vinculo.empty:
            st.error("Su cuenta no está vinculada a un registro profesional PAI.")
            return

        prof_id = int(vinculo.iloc[0]["profesional_id"])
        prof_nombre = (
            str(vinculo.iloc[0].get("nombre") or nombre_actual).strip()
        )
    else:
        profesionales = pd.read_sql(
            text("""
                SELECT id, nombre, rol
                FROM profesionales
                ORDER BY nombre
            """),
            engine
        )

        if profesionales.empty:
            st.warning("No hay profesionales PAI disponibles.")
            return

        opciones_prof = profesionales["id"].tolist()
        prof_id = st.selectbox(
            "Profesional PAI a consultar",
            opciones_prof,
            format_func=lambda pid: (
                f"{profesionales.loc[profesionales['id']==pid, 'nombre'].iloc[0]}"
                + (
                    f" · {profesionales.loc[profesionales['id']==pid, 'rol'].iloc[0]}"
                    if pd.notna(profesionales.loc[
                        profesionales["id"]==pid, "rol"
                    ].iloc[0]) else ""
                )
            ),
            key="v16_2_profesional"
        )
        prof_id = int(prof_id)
        prof_row = profesionales.loc[profesionales["id"] == prof_id].iloc[0]
        prof_nombre = str(prof_row.get("nombre") or "").strip()


    # ------------------------------------------------------------
    # V16.4 - MI GESTIÓN PAI
    # ------------------------------------------------------------
    st.markdown("## 📊 Mi gestión PAI")

    try:
        gestion = pd.read_sql(
            text("""
                SELECT
                    p.id,
                    TRIM(CAST(p.documento_usuario AS TEXT)) AS documento,
                    p.objetivo_tipo,
                    p.porcentaje_avance,
                    p.estado,
                    p.fecha_meta,
                    p.fecha_ultimo_seguimiento,
                    h.nombres,
                    h.apellidos,
                    h.modalidad
                FROM pai_objetivos p
                LEFT JOIN habitante_de_calle h
                  ON TRIM(CAST(h.numero_identificacion AS TEXT))
                   = TRIM(CAST(p.documento_usuario AS TEXT))
                WHERE p.profesional_referente=:prof
            """),
            engine,
            params={"prof": prof_id}
        )
    except Exception:
        gestion = pd.DataFrame()

    try:
        seg_total_df = pd.read_sql(
            text("""
                SELECT COUNT(*) AS total
                FROM pai_novedades n
                JOIN pai_objetivos o ON o.id=n.id_objetivo
                WHERE o.profesional_referente=:prof
            """),
            engine,
            params={"prof": prof_id}
        )
        total_seguimientos = (
            int(seg_total_df.iloc[0]["total"])
            if not seg_total_df.empty else 0
        )
    except Exception:
        total_seguimientos = 0

    try:
        cierres_prof = pd.read_sql(
            text("""
                SELECT COUNT(DISTINCT documento_usuario) AS total
                FROM pai_cierres
                WHERE profesional_referente=:prof
            """),
            engine,
            params={"prof": prof_id}
        )
        total_cerrados = (
            int(cierres_prof.iloc[0]["total"])
            if not cierres_prof.empty else 0
        )
    except Exception:
        total_cerrados = 0

    if gestion.empty:
        personas_pai = 0
        objetivos_total = 0
        objetivos_cumplidos = 0
        objetivos_vencidos = 0
        casos_sin_seg = 0
        cumplimiento_promedio = 0
    else:
        gestion["porcentaje_avance"] = pd.to_numeric(
            gestion["porcentaje_avance"], errors="coerce"
        ).fillna(0)
        gestion["fecha_meta"] = pd.to_datetime(
            gestion["fecha_meta"], errors="coerce"
        )
        gestion["fecha_ultimo_seguimiento"] = pd.to_datetime(
            gestion["fecha_ultimo_seguimiento"], errors="coerce"
        )
        hoy_g = pd.Timestamp(date.today())

        cumplido_g = (
            gestion["porcentaje_avance"].ge(100)
            | gestion["estado"].fillna("").astype(str).str.upper().eq("CUMPLIDO")
        )
        dias_meta_g = (gestion["fecha_meta"].dt.normalize() - hoy_g).dt.days
        dias_seg_g = (
            hoy_g - gestion["fecha_ultimo_seguimiento"].dt.normalize()
        ).dt.days

        personas_pai = gestion["documento"].nunique()
        objetivos_total = len(gestion)
        objetivos_cumplidos = int(cumplido_g.sum())
        objetivos_vencidos = int((~cumplido_g & dias_meta_g.lt(0)).sum())

        sin_seg_docs = gestion.loc[
            ~cumplido_g
            & (
                gestion["fecha_ultimo_seguimiento"].isna()
                | dias_seg_g.gt(15)
            ),
            "documento"
        ]
        casos_sin_seg = sin_seg_docs.nunique()
        cumplimiento_promedio = round(
            float(gestion["porcentaje_avance"].mean()), 1
        )

    with st.expander("📊 Ver resumen de mi gestión", expanded=True):
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Personas con PAI", personas_pai)
        k2.metric("Objetivos creados", objetivos_total)
        k3.metric("Objetivos cumplidos", objetivos_cumplidos)
        k4.metric("PAI cerrados", total_cerrados)

        k5, k6, k7, k8 = st.columns(4)
        k5.metric("Objetivos vencidos", objetivos_vencidos)
        k6.metric("Seguimientos realizados", total_seguimientos)
        k7.metric("Casos sin seguimiento +15 días", casos_sin_seg)
        k8.metric("Avance promedio", f"{cumplimiento_promedio}%")

        if not gestion.empty:
            gestion["nombre_completo"] = (
                gestion["nombres"].fillna("").astype(str).str.strip()
                + " "
                + gestion["apellidos"].fillna("").astype(str).str.strip()
            ).str.strip()

            filas = []
            for doc_g, grupo in gestion.groupby("documento", dropna=False):
                grupo = grupo.copy()
                grupo["porcentaje_avance"] = pd.to_numeric(
                    grupo["porcentaje_avance"], errors="coerce"
                ).fillna(0)
                metas = pd.to_datetime(grupo["fecha_meta"], errors="coerce")
                segs = pd.to_datetime(
                    grupo["fecha_ultimo_seguimiento"], errors="coerce"
                )
                cumplidos_g = (
                    grupo["porcentaje_avance"].ge(100)
                    | grupo["estado"].fillna("").astype(str).str.upper().eq(
                        "CUMPLIDO"
                    )
                )
                venc_g = int(
                    (
                        ~cumplidos_g
                        & ((metas.dt.normalize() - pd.Timestamp(date.today())).dt.days < 0)
                    ).sum()
                )
                sin_g = int(
                    (
                        ~cumplidos_g
                        & (
                            segs.isna()
                            | (
                                pd.Timestamp(date.today()) - segs.dt.normalize()
                            ).dt.days.gt(15)
                        )
                    ).sum()
                )

                if venc_g > 0:
                    sem = "🔴 VENCIDO"
                elif sin_g > 0:
                    sem = "🟠 REQUIERE SEGUIMIENTO"
                else:
                    sem = "🟢 AL DÍA"

                filas.append({
                    "Persona": grupo["nombre_completo"].iloc[0],
                    "Documento": doc_g,
                    "Modalidad": grupo["modalidad"].iloc[0],
                    "Objetivos": len(grupo),
                    "Cumplidos": int(cumplidos_g.sum()),
                    "Avance promedio": f"{round(grupo['porcentaje_avance'].mean(), 1)}%",
                    "Último seguimiento": (
                        segs.max().strftime("%d/%m/%Y")
                        if pd.notna(segs.max()) else "Sin seguimiento"
                    ),
                    "Próxima meta": (
                        metas[~cumplidos_g].min().strftime("%d/%m/%Y")
                        if pd.notna(metas[~cumplidos_g].min()) else "—"
                    ),
                    "Estado": sem
                })

            tabla_gestion = pd.DataFrame(filas)
            orden_sem = {
                "🔴 VENCIDO": 0,
                "🟠 REQUIERE SEGUIMIENTO": 1,
                "🟢 AL DÍA": 2
            }
            tabla_gestion["_orden"] = tabla_gestion["Estado"].map(
                orden_sem
            ).fillna(9)
            tabla_gestion = tabla_gestion.sort_values(
                ["_orden", "Persona"]
            ).drop(columns=["_orden"])

            st.markdown("#### 👥 Mis casos PAI")
            st.dataframe(
                tabla_gestion,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Todavía no tiene objetivos PAI registrados.")

    st.divider()

    # ------------------------------------------------------------
    # Cargar personas asignadas o activas
    # ------------------------------------------------------------
    personas = pd.read_sql(
        text("""
            SELECT
                TRIM(CAST(numero_identificacion AS TEXT)) AS documento,
                nombres,
                apellidos,
                modalidad,
                estado_caso
            FROM habitante_de_calle
            WHERE UPPER(TRIM(COALESCE(estado_caso,'')))='ACTIVO'
            ORDER BY nombres, apellidos
        """),
        engine
    )

    if personas.empty:
        st.info("No hay personas activas disponibles.")
        return

    personas["nombre_completo"] = (
        personas["nombres"].fillna("").astype(str).str.strip()
        + " "
        + personas["apellidos"].fillna("").astype(str).str.strip()
    ).str.strip()

    # Si venimos desde Gestión Profesional, conservar usuario pendiente
    pendiente = st.session_state.pop("v15_usuario_pendiente", None)

    docs = personas["documento"].astype(str).tolist()
    default_index = 0
    if pendiente is not None and str(pendiente) in docs:
        default_index = docs.index(str(pendiente))

    st.markdown("## 👤 Expediente PAI")
    doc_sel = st.selectbox(
        "Seleccione la persona",
        docs,
        index=default_index,
        format_func=lambda d: (
            f"{personas.loc[personas['documento'].astype(str)==str(d), 'nombre_completo'].iloc[0]}"
            f" · CC {d}"
        ),
        key="v16_2_usuario_unico"
    )

    persona_sel = personas.loc[
        personas["documento"].astype(str) == str(doc_sel)
    ].iloc[0]
    nombre_usuario = str(persona_sel["nombre_completo"]).strip()
    modalidad_usuario = str(persona_sel.get("modalidad") or "").strip()

    # Cabecera persistente de contexto
    st.success(
        f"📌 Está trabajando el PAI de: **{nombre_usuario}** · "
        f"CC **{doc_sel}**"
        + (f" · Modalidad **{modalidad_usuario}**" if modalidad_usuario else "")
    )

    semaforo_integral, razones_integrales = _semaforo_integral_usuario_v16(doc_sel)

    # ------------------------------------------------------------
    # Cargar objetivos SOLO de la persona seleccionada
    # ------------------------------------------------------------
    objetivos = pd.read_sql(
        text("""
            SELECT
                p.id,
                p.documento_usuario,
                p.objetivo_tipo,
                p.objetivo_descripcion,
                p.actividades,
                p.avance_hitos,
                p.porcentaje_avance,
                p.estado,
                p.fecha_apertura,
                p.fecha_meta,
                p.fecha_cumplimiento_real,
                p.fecha_ultimo_seguimiento,
                p.linea_politica,
                p.ods_principal
            FROM pai_objetivos p
            WHERE TRIM(CAST(p.documento_usuario AS TEXT))=:doc
              AND p.profesional_referente=:prof
            ORDER BY
                CASE WHEN UPPER(COALESCE(p.estado,''))='CUMPLIDO' THEN 1 ELSE 0 END,
                p.fecha_meta NULLS LAST,
                p.id DESC
        """),
        engine,
        params={"doc": str(doc_sel), "prof": prof_id}
    )

    # ------------------------------------------------------------
    # KPIs del expediente
    # ------------------------------------------------------------
    if objetivos.empty:
        total_obj = vencidos = proximos = sin_seg = cumplidos = 0
    else:
        tmp = objetivos.copy()
        tmp["porcentaje_avance"] = pd.to_numeric(
            tmp["porcentaje_avance"], errors="coerce"
        ).fillna(0)
        tmp["fecha_meta"] = pd.to_datetime(tmp["fecha_meta"], errors="coerce")
        tmp["fecha_ultimo_seguimiento"] = pd.to_datetime(
            tmp["fecha_ultimo_seguimiento"], errors="coerce"
        )
        hoy = pd.Timestamp(date.today())
        cumplido_mask = (
            tmp["porcentaje_avance"].ge(100)
            | tmp["estado"].fillna("").astype(str).str.upper().eq("CUMPLIDO")
        )
        dias_meta = (tmp["fecha_meta"].dt.normalize() - hoy).dt.days
        total_obj = len(tmp)
        vencidos = int((~cumplido_mask & dias_meta.lt(0)).sum())
        proximos = int(
            (~cumplido_mask & dias_meta.between(0, 7, inclusive="both")).sum()
        )
        sin_seg = int(
            (
                ~cumplido_mask
                & (
                    tmp["fecha_ultimo_seguimiento"].isna()
                    | (
                        hoy - tmp["fecha_ultimo_seguimiento"].dt.normalize()
                    ).dt.days.gt(15)
                )
            ).sum()
        )
        cumplidos = int(cumplido_mask.sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Objetivos", total_obj)
    c2.metric("Vencidos", vencidos)
    c3.metric("Próximos 7 días", proximos)
    c4.metric("Sin seguimiento", sin_seg)
    c5.metric("Cumplidos", cumplidos)

    st.markdown(f"### {semaforo_integral}")
    if razones_integrales:
        st.caption(" · ".join(razones_integrales))
    else:
        st.caption("Sin alertas relevantes en este momento.")

    # ------------------------------------------------------------
    # Tabs del expediente único
    # ------------------------------------------------------------
    tab_resumen, tab_obj, tab_seg, tab_cierre = st.tabs(
        ["📋 Resumen PAI", "🎯 Objetivos", "📝 Seguimientos", "✅ Cierre"]
    )

    # ============================================================
    # RESUMEN
    # ============================================================
    with tab_resumen:
        st.markdown(f"### Resumen de {nombre_usuario}")

        if objetivos.empty:
            st.info("Esta persona todavía no tiene objetivos PAI asignados.")
        else:
            resumen_cols = [
                "objetivo_tipo",
                "linea_politica",
                "ods_principal",
                "porcentaje_avance",
                "estado",
                "fecha_meta",
                "fecha_ultimo_seguimiento"
            ]
            st.dataframe(
                objetivos[resumen_cols],
                use_container_width=True,
                hide_index=True
            )

            ult_seg = pd.to_datetime(
                objetivos["fecha_ultimo_seguimiento"],
                errors="coerce"
            ).max()
            prox_meta = pd.to_datetime(
                objetivos.loc[
                    ~objetivos["estado"].fillna("").astype(str).str.upper().eq(
                        "CUMPLIDO"
                    ),
                    "fecha_meta"
                ],
                errors="coerce"
            ).min()

            cc1, cc2 = st.columns(2)
            cc1.info(
                "Último seguimiento: "
                + (
                    ult_seg.strftime("%d/%m/%Y")
                    if pd.notna(ult_seg)
                    else "Sin seguimiento registrado"
                )
            )
            cc2.info(
                "Próxima fecha meta: "
                + (
                    prox_meta.strftime("%d/%m/%Y")
                    if pd.notna(prox_meta)
                    else "Sin fecha próxima"
                )
            )

    # ============================================================
    # OBJETIVOS
    # ============================================================
    with tab_obj:
        st.markdown(f"### 🎯 Objetivos PAI de {nombre_usuario}")
        st.warning(
            f"Todo lo que guarde en esta pestaña se registrará para "
            f"**{nombre_usuario} · CC {doc_sel}**."
        )

        tipos_objetivo = [
            "Documentación y ciudadanía",
            "Cedulación",
            "Aseguramiento en salud",
            "Salud mental",
            "Tratamiento consumo SPA",
            "Reducción de riesgos y daños",
            "Vinculación familiar",
            "Inclusión social",
            "Empleabilidad",
            "Generación de ingresos",
            "Educación",
            "Vivienda",
            "Proyecto de vida",
            "Participación comunitaria",
            "Justicia y acceso a derechos",
            "Otro"
        ]

        linea_por_tipo = {
            "Documentación y ciudadanía": "Derechos e inclusión social",
            "Cedulación": "Derechos e inclusión social",
            "Aseguramiento en salud": "Salud",
            "Salud mental": "Salud",
            "Tratamiento consumo SPA": "Salud",
            "Reducción de riesgos y daños": "Salud",
            "Vinculación familiar": "Inclusión social y familiar",
            "Inclusión social": "Inclusión social y familiar",
            "Empleabilidad": "Inclusión económica",
            "Generación de ingresos": "Inclusión económica",
            "Educación": "Educación",
            "Vivienda": "Hábitat y vivienda",
            "Proyecto de vida": "Desarrollo humano",
            "Participación comunitaria": "Participación",
            "Justicia y acceso a derechos": "Derechos e inclusión social",
            "Otro": "Intervención integral"
        }

        ods_por_tipo = {
            "Documentación y ciudadanía": "ODS 16",
            "Cedulación": "ODS 16",
            "Aseguramiento en salud": "ODS 3",
            "Salud mental": "ODS 3",
            "Tratamiento consumo SPA": "ODS 3",
            "Reducción de riesgos y daños": "ODS 3",
            "Vinculación familiar": "ODS 10",
            "Inclusión social": "ODS 10",
            "Empleabilidad": "ODS 8",
            "Generación de ingresos": "ODS 8",
            "Educación": "ODS 4",
            "Vivienda": "ODS 11",
            "Proyecto de vida": "ODS 3",
            "Participación comunitaria": "ODS 16",
            "Justicia y acceso a derechos": "ODS 16",
            "Otro": "ODS 10"
        }

        hitos_sugeridos = {
            "Documentación y ciudadanía": [
                "Verificar estado documental",
                "Gestionar documento requerido",
                "Confirmar entrega o trámite"
            ],
            "Cedulación": [
                "Verificar necesidad de cédula",
                "Gestionar cita o trámite",
                "Confirmar obtención del documento"
            ],
            "Aseguramiento en salud": [
                "Verificar afiliación",
                "Gestionar afiliación o traslado",
                "Confirmar aseguramiento activo"
            ],
            "Salud mental": [
                "Valoración inicial",
                "Remisión o vinculación",
                "Seguimiento a adherencia"
            ],
            "Tratamiento consumo SPA": [
                "Valoración",
                "Vinculación a tratamiento",
                "Seguimiento a adherencia"
            ],
            "Reducción de riesgos y daños": [
                "Identificar riesgos",
                "Definir acciones de reducción",
                "Verificar cambios"
            ],
            "Vinculación familiar": [
                "Identificar red",
                "Realizar contacto",
                "Verificar resultado del acercamiento"
            ],
            "Inclusión social": [
                "Identificar barreras",
                "Gestionar oferta institucional",
                "Verificar vinculación"
            ],
            "Empleabilidad": [
                "Perfil ocupacional",
                "Remisión o postulación",
                "Seguimiento a vinculación"
            ],
            "Generación de ingresos": [
                "Identificar alternativa",
                "Gestionar apoyo",
                "Seguimiento a resultado"
            ],
            "Educación": [
                "Identificar necesidad educativa",
                "Gestionar vinculación",
                "Seguimiento a permanencia"
            ],
            "Vivienda": [
                "Caracterizar necesidad",
                "Gestionar alternativa",
                "Verificar solución"
            ],
            "Proyecto de vida": [
                "Definir meta personal",
                "Establecer acciones",
                "Evaluar avances"
            ],
            "Participación comunitaria": [
                "Identificar espacio",
                "Vincular",
                "Verificar participación"
            ],
            "Justicia y acceso a derechos": [
                "Identificar necesidad jurídica",
                "Gestionar remisión",
                "Verificar respuesta"
            ],
            "Otro": [
                "Definir actividad 1",
                "Definir actividad 2",
                "Definir actividad 3"
            ]
        }

        with st.form(f"v16_2_objetivo_{doc_sel}"):
            tipo_obj = st.selectbox("Tipo de objetivo", tipos_objetivo)
            linea = linea_por_tipo.get(tipo_obj, "Intervención integral")
            ods = ods_por_tipo.get(tipo_obj, "ODS 10")

            cpol1, cpol2 = st.columns(2)
            cpol1.info(f"Línea de política: {linea}")
            cpol2.info(f"ODS: {ods}")

            descripcion = st.text_area(
                "Descripción del objetivo *",
                placeholder="Redacte el resultado que se espera lograr."
            )

            sugeridos = hitos_sugeridos.get(tipo_obj, [])
            actividades = st.multiselect(
                "Actividades / hitos",
                sugeridos,
                default=sugeridos
            )

            actividad_extra = st.text_input(
                "Actividad adicional (opcional)"
            )
            if actividad_extra.strip():
                actividades = actividades + [actividad_extra.strip()]

            fecha_meta = st.date_input(
                "Fecha meta",
                value=date.today() + timedelta(days=30)
            )

            guardar_obj = st.form_submit_button(
                f"➕ Crear objetivo para {nombre_usuario}",
                use_container_width=True,
                type="primary"
            )

        if guardar_obj:
            if not descripcion.strip():
                st.error("Debe escribir la descripción del objetivo.")
            elif not actividades:
                st.error("Debe registrar al menos una actividad o hito.")
            else:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO pai_objetivos(
                                documento_usuario,
                                objetivo_tipo,
                                objetivo_descripcion,
                                actividades,
                                avance_hitos,
                                porcentaje_avance,
                                estado,
                                linea_politica,
                                ods_principal,
                                profesional_referente,
                                fecha_apertura,
                                fecha_meta
                            )
                            VALUES(
                                :doc,
                                :tipo,
                                :descripcion,
                                CAST(:actividades AS JSON),
                                CAST(:avance AS JSON),
                                0,
                                'Activo',
                                :linea,
                                :ods,
                                :prof,
                                NOW(),
                                :fecha_meta
                            )
                        """),
                        {
                            "doc": str(doc_sel),
                            "tipo": tipo_obj,
                            "descripcion": descripcion.strip(),
                            "actividades": json.dumps(
                                actividades, ensure_ascii=False
                            ),
                            "avance": json.dumps(
                                [], ensure_ascii=False
                            ),
                            "linea": linea,
                            "ods": ods,
                            "prof": prof_id,
                            "fecha_meta": fecha_meta
                        }
                    )
                try:
                    registrar_auditoria(
                        "CREAR_OBJETIVO_PAI",
                        str(doc_sel),
                        f"{tipo_obj} - {descripcion.strip()[:120]}"
                    )
                except Exception:
                    pass

                st.success(
                    f"✅ Objetivo creado para {nombre_usuario} · CC {doc_sel}."
                )
                st.rerun()

        if not objetivos.empty:
            st.markdown("#### Objetivos registrados")
            st.dataframe(
                objetivos[
                    [
                        "id",
                        "objetivo_tipo",
                        "objetivo_descripcion",
                        "linea_politica",
                        "ods_principal",
                        "porcentaje_avance",
                        "estado",
                        "fecha_meta"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

            opciones_obj = objetivos["id"].tolist()
            obj_id = st.selectbox(
                "Objetivo a actualizar",
                opciones_obj,
                format_func=lambda oid: (
                    f"#{oid} · "
                    + str(
                        objetivos.loc[
                            objetivos["id"] == oid,
                            "objetivo_tipo"
                        ].iloc[0]
                    )
                ),
                key=f"v16_2_obj_update_{doc_sel}"
            )

            obj_row = objetivos.loc[objetivos["id"] == obj_id].iloc[0]

            try:
                acts = obj_row.get("actividades") or []
                if isinstance(acts, str):
                    acts = json.loads(acts)
                if not isinstance(acts, list):
                    acts = []
            except Exception:
                acts = []

            try:
                avance = obj_row.get("avance_hitos") or []
                if isinstance(avance, str):
                    avance = json.loads(avance)
                if not isinstance(avance, list):
                    avance = []
            except Exception:
                avance = []

            completos = st.multiselect(
                "Hitos completados",
                acts,
                default=[x for x in avance if x in acts],
                key=f"v16_2_hitos_{doc_sel}_{obj_id}"
            )

            pct = round((len(completos) / len(acts)) * 100) if acts else 0
            st.progress(pct / 100 if pct else 0)
            st.caption(f"Avance calculado: {pct}%")

            if st.button(
                f"💾 Guardar avance de {nombre_usuario}",
                use_container_width=True,
                key=f"v16_2_guardar_avance_{doc_sel}_{obj_id}"
            ):
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            UPDATE pai_objetivos
                            SET
                                avance_hitos=CAST(:avance AS JSON),
                                porcentaje_avance=:pct,
                                estado=CASE
                                    WHEN :pct >= 100 THEN 'CUMPLIDO'
                                    ELSE 'Activo'
                                END,
                                fecha_cumplimiento_real=CASE
                                    WHEN :pct >= 100 THEN NOW()
                                    ELSE NULL
                                END
                            WHERE id=:id
                              AND TRIM(CAST(documento_usuario AS TEXT))=:doc
                              AND profesional_referente=:prof
                        """),
                        {
                            "avance": json.dumps(
                                completos, ensure_ascii=False
                            ),
                            "pct": pct,
                            "id": int(obj_id),
                            "doc": str(doc_sel),
                            "prof": prof_id
                        }
                    )
                st.success(
                    f"✅ Avance actualizado para {nombre_usuario}."
                )
                st.rerun()

    # ============================================================
    # SEGUIMIENTOS
    # ============================================================
    with tab_seg:
        st.markdown(f"### 📝 Seguimientos de {nombre_usuario}")
        st.warning(
            f"El seguimiento que registre se guardará exclusivamente para "
            f"**{nombre_usuario} · CC {doc_sel}**."
        )

        if objetivos.empty:
            st.info(
                "Primero debe crear al menos un objetivo PAI para esta persona."
            )
        else:
            objetivo_seg = st.selectbox(
                "Objetivo relacionado",
                objetivos["id"].tolist(),
                format_func=lambda oid: (
                    f"#{oid} · "
                    + str(
                        objetivos.loc[
                            objetivos["id"] == oid,
                            "objetivo_tipo"
                        ].iloc[0]
                    )
                ),
                key=f"v16_2_obj_seg_{doc_sel}"
            )

            with st.form(f"v16_2_seg_form_{doc_sel}_{objetivo_seg}"):
                actividad = st.text_input(
                    "Actividad realizada *",
                    placeholder="Ej.: Acompañamiento, remisión, contacto familiar..."
                )
                descripcion_seg = st.text_area(
                    "Descripción del seguimiento *",
                    placeholder=(
                        "Registre la intervención realizada, resultado y compromisos."
                    )
                )
                evidencia = st.text_input(
                    "Evidencia / referencia (opcional)"
                )

                guardar_seg = st.form_submit_button(
                    f"📝 Registrar seguimiento para {nombre_usuario}",
                    use_container_width=True,
                    type="primary"
                )

            if guardar_seg:
                if not actividad.strip() or not descripcion_seg.strip():
                    st.error(
                        "Actividad y descripción del seguimiento son obligatorias."
                    )
                else:
                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                INSERT INTO pai_novedades(
                                    id_objetivo,
                                    fecha,
                                    profesional,
                                    tipo_novedad,
                                    descripcion,
                                    avance_generado,
                                    evidencia
                                )
                                VALUES(
                                    :id_obj,
                                    NOW(),
                                    :profesional,
                                    :tipo,
                                    :descripcion,
                                    :avance,
                                    :evidencia
                                )
                            """),
                            {
                                "id_obj": int(objetivo_seg),
                                "profesional": prof_nombre,
                                "tipo": actividad.strip(),
                                "descripcion": descripcion_seg.strip(),
                                "avance": 0,
                                "evidencia": evidencia.strip()
                            }
                        )
                        conn.execute(
                            text("""
                                UPDATE pai_objetivos
                                SET fecha_ultimo_seguimiento=NOW()
                                WHERE id=:id_obj
                                  AND TRIM(CAST(documento_usuario AS TEXT))=:doc
                                  AND profesional_referente=:prof
                            """),
                            {
                                "id_obj": int(objetivo_seg),
                                "doc": str(doc_sel),
                                "prof": prof_id
                            }
                        )

                    try:
                        registrar_auditoria(
                            "REGISTRAR_NOVEDAD_PROFESIONAL",
                            str(doc_sel),
                            descripcion_seg.strip()[:150]
                        )
                    except Exception:
                        pass

                    st.success(
                        f"✅ Seguimiento registrado para "
                        f"{nombre_usuario} · CC {doc_sel}."
                    )
                    st.rerun()

            hist = pd.read_sql(
                text("""
                    SELECT
                        n.fecha,
                        n.profesional,
                        n.tipo_novedad,
                        n.descripcion,
                        n.evidencia,
                        o.objetivo_tipo
                    FROM pai_novedades n
                    JOIN pai_objetivos o
                      ON o.id=n.id_objetivo
                    WHERE TRIM(CAST(o.documento_usuario AS TEXT))=:doc
                      AND o.profesional_referente=:prof
                    ORDER BY n.fecha DESC
                    LIMIT 20
                """),
                engine,
                params={"doc": str(doc_sel), "prof": prof_id}
            )

            st.markdown("#### Últimos seguimientos")
            if hist.empty:
                st.info("Aún no hay seguimientos registrados.")
            else:
                st.dataframe(
                    hist,
                    use_container_width=True,
                    hide_index=True
                )

    # ============================================================
    # CIERRE
    # ============================================================
    with tab_cierre:
        st.markdown(f"### ✅ Cierre del PAI de {nombre_usuario}")
        st.warning(
            f"Está a punto de trabajar el cierre del PAI de "
            f"**{nombre_usuario} · CC {doc_sel}**."
        )
        cierre_pai_usuario_v16(
            doc_sel,
            profesional_id=prof_id,
            profesional_nombre=prof_nombre
        )

def supervision_pai_v15():
    rol = str(st.session_state.get("rol_actual", "")).upper()
    if rol not in ["COORDINACION", "MANAGER"]:
        st.error("Acceso exclusivo para Coordinación y Manager.")
        return

    st.title("🎛️ Supervisión PAI por Profesional")
    st.caption(
        "Asignación de accesos y control comparativo de cumplimiento."
    )

    # --------------------------------------------------------
    # Vincular login de funcionario con registro profesional
    # --------------------------------------------------------
    with st.expander("🔗 Vincular profesional con su acceso al sistema"):
        funcionarios = pd.read_sql(
            text("""
                SELECT cedula, nombre
                FROM funcionarios_sistema
                WHERE rol='PROFESIONAL'
                  AND activo=TRUE
                  AND COALESCE(acceso_pai, FALSE)=TRUE
                ORDER BY nombre
            """),
            engine
        )
        profesionales = pd.read_sql(
            text("""
                SELECT id, nombre, rol
                FROM profesionales
                ORDER BY nombre
            """),
            engine
        )

        if funcionarios.empty or profesionales.empty:
            st.info(
                "Se requieren funcionarios con rol PROFESIONAL "
                "y registros en la tabla profesionales."
            )
        else:
            cedula = st.selectbox(
                "Acceso del profesional",
                funcionarios["cedula"].tolist(),
                format_func=lambda x: (
                    funcionarios.loc[
                        funcionarios["cedula"] == x,
                        "nombre"
                    ].iloc[0]
                    + f" · CC {x}"
                ),
                key="v15_func_map"
            )
            profesional_id = st.selectbox(
                "Registro profesional correspondiente",
                profesionales["id"].tolist(),
                format_func=lambda x: (
                    profesionales.loc[
                        profesionales["id"] == x,
                        "nombre"
                    ].iloc[0]
                    + " · "
                    + str(
                        profesionales.loc[
                            profesionales["id"] == x,
                            "rol"
                        ].iloc[0]
                    )
                ),
                key="v15_prof_map"
            )

            if st.button(
                "🔗 Guardar vinculación",
                use_container_width=True,
                key="v15_guardar_map"
            ):
                cedula_sel = str(cedula)
                profesional_sel_id = int(profesional_id)

                # Validar si ese registro profesional ya está vinculado
                existente_prof = pd.read_sql(
                    text("""
                        SELECT
                            m.cedula_funcionario,
                            f.nombre AS funcionario
                        FROM pai_profesional_funcionario m
                        LEFT JOIN funcionarios_sistema f
                            ON f.cedula=m.cedula_funcionario
                        WHERE m.profesional_id=:profesional_id
                          AND m.activo=TRUE
                          AND m.cedula_funcionario<>:cedula
                        LIMIT 1
                    """),
                    engine,
                    params={
                        "profesional_id": profesional_sel_id,
                        "cedula": cedula_sel
                    }
                )

                if not existente_prof.empty:
                    vinculado_a = existente_prof.iloc[0]
                    st.error(
                        "Ese registro profesional ya está vinculado a "
                        f"{vinculado_a.get('funcionario') or vinculado_a.get('cedula_funcionario')} "
                        f"(CC {vinculado_a.get('cedula_funcionario')}). "
                        "Revise la selección antes de continuar."
                    )
                else:
                    try:
                        with engine.begin() as conn:
                            conn.execute(
                                text("""
                                    INSERT INTO pai_profesional_funcionario(
                                        cedula_funcionario,
                                        profesional_id,
                                        activo,
                                        actualizado_por
                                    )
                                    VALUES(
                                        :cedula,
                                        :profesional_id,
                                        TRUE,
                                        :usuario
                                    )
                                    ON CONFLICT (cedula_funcionario)
                                    DO UPDATE SET
                                        profesional_id=EXCLUDED.profesional_id,
                                        activo=TRUE,
                                        actualizado_por=EXCLUDED.actualizado_por,
                                        actualizado_en=NOW()
                                """),
                                {
                                    "cedula": cedula_sel,
                                    "profesional_id": profesional_sel_id,
                                    "usuario": st.session_state.get(
                                        "usuario_actual",
                                        "coordinacion"
                                    )
                                }
                            )
                        st.success("✅ Profesional vinculado con su acceso.")
                        st.rerun()
                    except Exception as e:
                        st.error(
                            "No fue posible guardar la vinculación. "
                            "Revise si el registro profesional ya está asignado "
                            "a otra persona."
                        )

        try:
            vinculaciones = pd.read_sql(
                text("""
                    SELECT
                        m.cedula_funcionario,
                        f.nombre AS funcionario,
                        p.nombre AS profesional,
                        p.rol,
                        m.activo
                    FROM pai_profesional_funcionario m
                    LEFT JOIN funcionarios_sistema f
                        ON f.cedula=m.cedula_funcionario
                    LEFT JOIN profesionales p
                        ON p.id=m.profesional_id
                    ORDER BY f.nombre
                """),
                engine
            )
            if not vinculaciones.empty:
                st.dataframe(
                    vinculaciones,
                    use_container_width=True,
                    hide_index=True
                )
        except Exception:
            pass

    control = pd.read_sql(
        text("""
            SELECT
                p.id,
                p.documento_usuario,
                p.porcentaje_avance,
                p.estado,
                p.fecha_meta,
                p.fecha_ultimo_seguimiento,
                p.profesional_referente,
                pr.nombre AS profesional,
                pr.rol
            FROM pai_objetivos p
            LEFT JOIN profesionales pr
                ON pr.id=p.profesional_referente
        """),
        engine
    )

    if control.empty:
        st.info("No existen objetivos PAI para supervisar.")
        return

    hoy = pd.Timestamp(date.today())
    control["fecha_meta"] = pd.to_datetime(
        control["fecha_meta"], errors="coerce"
    )
    control["fecha_ultimo_seguimiento"] = pd.to_datetime(
        control["fecha_ultimo_seguimiento"], errors="coerce"
    )
    control["porcentaje_avance"] = pd.to_numeric(
        control["porcentaje_avance"], errors="coerce"
    ).fillna(0)
    control["dias_meta"] = (
        control["fecha_meta"].dt.normalize() - hoy
    ).dt.days
    control["dias_sin_seg"] = (
        hoy - control["fecha_ultimo_seguimiento"].dt.normalize()
    ).dt.days

    control["cumplido"] = (
        control["porcentaje_avance"].ge(100)
        | control["estado"].fillna("").astype(str).str.upper().eq("CUMPLIDO")
    )
    control["vencido"] = (
        ~control["cumplido"] & control["dias_meta"].lt(0)
    )
    control["proximo"] = (
        ~control["cumplido"]
        & control["dias_meta"].between(0, 7, inclusive="both")
    )
    control["sin_seguimiento"] = (
        ~control["cumplido"]
        & (
            control["fecha_ultimo_seguimiento"].isna()
            | control["dias_sin_seg"].gt(15)
        )
    )
    control["profesional"] = control["profesional"].fillna("Sin asignar")

    resumen = (
        control.groupby("profesional", dropna=False)
        .agg(
            usuarios=("documento_usuario", "nunique"),
            objetivos=("id", "count"),
            cumplidos=("cumplido", "sum"),
            vencidos=("vencido", "sum"),
            proximos=("proximo", "sum"),
            sin_seguimiento=("sin_seguimiento", "sum"),
            avance_promedio=("porcentaje_avance", "mean")
        )
        .reset_index()
    )
    resumen["cumplimiento_%"] = (
        resumen["cumplidos"] / resumen["objetivos"] * 100
    ).round(1)
    resumen["avance_promedio"] = resumen["avance_promedio"].round(1)

    st.markdown("### 📊 Comparativo por profesional")
    st.dataframe(
        resumen.sort_values(
            ["vencidos", "sin_seguimiento"],
            ascending=False
        ),
        use_container_width=True,
        hide_index=True
    )

    csv = resumen.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Descargar resumen PAI",
        data=csv,
        file_name=(
            "supervision_pai_"
            + datetime.now().strftime("%Y%m%d_%H%M")
            + ".csv"
        ),
        mime="text/csv",
        use_container_width=True
    )


def dashboard_ejecutivo():

    st.title("🎛️ Dashboard de Coordinación")
    st.caption(
        "Vista gerencial de ocupación, PAI, seguimiento profesional, egresos y alertas."
    )

    # ========================================================
    # POBLACIÓN GENERAL
    # ========================================================
    df_coord = pd.read_sql(
        text("""
            SELECT *
            FROM habitante_de_calle
        """),
        engine
    )

    if df_coord.empty:
        st.info("No hay información disponible.")
        return

    estado_coord = (
        df_coord["estado_caso"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
        if "estado_caso" in df_coord.columns
        else pd.Series("", index=df_coord.index)
    )

    modalidad_coord = (
        df_coord["modalidad"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
        if "modalidad" in df_coord.columns
        else pd.Series("", index=df_coord.index)
    )

    total_coord = len(df_coord)
    activos_coord = int(estado_coord.eq("ACTIVO").sum())
    urbano_coord = int(
        (estado_coord.eq("ACTIVO") & modalidad_coord.eq("URBANO")).sum()
    )
    granja_coord = int(
        (estado_coord.eq("ACTIVO") & modalidad_coord.eq("GRANJA")).sum()
    )

    # ========================================================
    # EGRESOS / MOVIMIENTOS
    # ========================================================
    try:
        egresos_coord = int(
            pd.read_sql(
                text("""
                    SELECT COUNT(*) AS total
                    FROM personas_caracterizacion
                    WHERE UPPER(TRIM(COALESCE(estado_caso,''))) = 'EGRESADO'
                """),
                engine
            ).iloc[0]["total"] or 0
        )
    except Exception:
        egresos_coord = 0

    try:
        mov_30 = pd.read_sql(
            text("""
                SELECT
                    tipo_movimiento,
                    COUNT(*) AS total
                FROM movimientos_habitante
                WHERE fecha_movimiento >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY tipo_movimiento
            """),
            engine
        )
    except Exception:
        mov_30 = pd.DataFrame(columns=["tipo_movimiento", "total"])

    reingresos_30 = 0
    if not mov_30.empty:
        reingresos_30 = int(
            mov_30.loc[
                mov_30["tipo_movimiento"]
                .astype(str)
                .str.upper()
                .str.contains("REINGRESO", na=False),
                "total"
            ].sum()
        )

    # ========================================================
    # CONTROL PAI GLOBAL
    # ========================================================
    try:
        df_pai_coord = pd.read_sql(
            text("""
                SELECT
                    p.id,
                    p.documento_usuario,
                    p.objetivo_tipo,
                    p.porcentaje_avance,
                    p.estado,
                    p.fecha_meta,
                    p.fecha_ultimo_seguimiento,
                    p.profesional_referente,
                    pr.nombre AS profesional,
                    pr.rol
                FROM pai_objetivos p
                LEFT JOIN profesionales pr
                    ON pr.id = p.profesional_referente
            """),
            engine
        )
    except Exception:
        df_pai_coord = pd.DataFrame()

    pai_total = pai_cumplidos = pai_vencidos = pai_proximos = 0
    pai_sin_seg = 0
    resumen_coord_prof = pd.DataFrame()
    alertas_pai_coord = pd.DataFrame()

    if not df_pai_coord.empty:

        hoy_coord = pd.Timestamp(date.today())

        df_pai_coord["fecha_meta"] = pd.to_datetime(
            df_pai_coord["fecha_meta"], errors="coerce"
        )
        df_pai_coord["fecha_ultimo_seguimiento"] = pd.to_datetime(
            df_pai_coord["fecha_ultimo_seguimiento"], errors="coerce"
        )
        df_pai_coord["porcentaje_avance"] = pd.to_numeric(
            df_pai_coord["porcentaje_avance"], errors="coerce"
        ).fillna(0)

        df_pai_coord["dias_meta"] = (
            df_pai_coord["fecha_meta"].dt.normalize() - hoy_coord
        ).dt.days

        df_pai_coord["dias_sin_seguimiento"] = (
            hoy_coord
            - df_pai_coord["fecha_ultimo_seguimiento"].dt.normalize()
        ).dt.days

        es_cumplido = (
            df_pai_coord["porcentaje_avance"].ge(100)
            |
            df_pai_coord["estado"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
            .eq("CUMPLIDO")
        )

        es_vencido = (
            ~es_cumplido
            & df_pai_coord["dias_meta"].lt(0)
        )

        es_proximo = (
            ~es_cumplido
            & df_pai_coord["dias_meta"].between(0, 7, inclusive="both")
        )

        sin_seguimiento = (
            ~es_cumplido
            & (
                df_pai_coord["fecha_ultimo_seguimiento"].isna()
                | df_pai_coord["dias_sin_seguimiento"].gt(15)
            )
        )

        pai_total = len(df_pai_coord)
        pai_cumplidos = int(es_cumplido.sum())
        pai_vencidos = int(es_vencido.sum())
        pai_proximos = int(es_proximo.sum())
        pai_sin_seg = int(sin_seguimiento.sum())

        df_pai_coord["cumplido"] = es_cumplido
        df_pai_coord["vencido"] = es_vencido
        df_pai_coord["proximo"] = es_proximo
        df_pai_coord["sin_seguimiento"] = sin_seguimiento

        df_pai_coord["profesional"] = (
            df_pai_coord["profesional"]
            .fillna("Sin asignar")
        )
        df_pai_coord["rol"] = (
            df_pai_coord["rol"]
            .fillna("Sin rol")
        )

        resumen_coord_prof = (
            df_pai_coord
            .groupby(["profesional", "rol"], dropna=False)
            .agg(
                objetivos=("id", "count"),
                cumplidos=("cumplido", "sum"),
                vencidos=("vencido", "sum"),
                proximos=("proximo", "sum"),
                sin_seguimiento=("sin_seguimiento", "sum")
            )
            .reset_index()
        )

        resumen_coord_prof["cumplimiento_%"] = (
            resumen_coord_prof["cumplidos"]
            / resumen_coord_prof["objetivos"]
            * 100
        ).round(1)

        alertas_pai_coord = df_pai_coord[
            df_pai_coord["vencido"]
            | df_pai_coord["proximo"]
            | df_pai_coord["sin_seguimiento"]
        ].copy()

    # ========================================================
    # FILA 1 - INDICADORES OPERATIVOS
    # ========================================================
    st.markdown("### 🏠 Operación actual")

    try:
        medidas_coord = pd.read_sql(
            text("""
                SELECT
                    tipo_medida,
                    COUNT(*) AS total
                FROM sanciones_usuarios
                WHERE UPPER(TRIM(COALESCE(estado_medida,''))) = 'ACTIVA'
                GROUP BY tipo_medida
            """),
            engine
        )
        medidas_activas_coord = int(medidas_coord["total"].sum()) if not medidas_coord.empty else 0
    except Exception:
        medidas_coord = pd.DataFrame()
        medidas_activas_coord = 0

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("👥 Población", total_coord)
    c2.metric("🟢 Activos", activos_coord)
    c3.metric("🏙️ Urbano", f"{urbano_coord}/100")
    c4.metric("🌱 Granja", granja_coord)
    c5.metric("🏆 Egresos", egresos_coord)
    c6.metric("🔁 Reingresos 30d", reingresos_30)
    c7.metric("⛔ Medidas activas", medidas_activas_coord)

    if urbano_coord >= 100:
        st.error("🚨 Urbano alcanzó o superó la capacidad de 100 cupos.")
    elif urbano_coord >= 90:
        st.warning(
            f"⚠️ Urbano está en {urbano_coord}% de su capacidad."
        )

    st.divider()

    # ========================================================
    # FILA 2 - PAI
    # ========================================================
    st.markdown("### 🎯 Control PAI")

    p1, p2, p3, p4, p5 = st.columns(5)
    p1.metric("🎯 Objetivos", pai_total)
    p2.metric("🟢 Cumplidos", pai_cumplidos)
    p3.metric("🔴 Vencidos", pai_vencidos)
    p4.metric("🟡 Vencen ≤7 días", pai_proximos)
    p5.metric("⚠️ Sin seguimiento", pai_sin_seg)

    # ========================================================
    # SEMÁFORO EJECUTIVO
    # ========================================================
    alertas_coord = []

    if pai_vencidos:
        alertas_coord.append(
            ("error", f"{pai_vencidos} objetivos PAI están vencidos.")
        )

    if pai_sin_seg:
        alertas_coord.append(
            (
                "warning",
                f"{pai_sin_seg} objetivos no tienen seguimiento "
                "o llevan más de 15 días sin actualización."
            )
        )

    if pai_proximos:
        alertas_coord.append(
            (
                "warning",
                f"{pai_proximos} objetivos vencen en los próximos 7 días."
            )
        )

    sin_estado_coord = int(
        estado_coord.isin(["", "NAN", "NONE"]).sum()
    )
    if sin_estado_coord:
        alertas_coord.append(
            ("warning", f"{sin_estado_coord} registros están sin estado del caso.")
        )

    st.markdown("### 🚨 Alertas de coordinación")

    if alertas_coord:
        for nivel, mensaje in alertas_coord:
            if nivel == "error":
                st.error(mensaje)
            else:
                st.warning(mensaje)
    else:
        st.success("✅ No se identifican alertas críticas en este momento.")

    st.divider()

    # ========================================================
    # CUMPLIMIENTO POR PROFESIONAL
    # ========================================================
    st.markdown("### 👨‍⚕️ Cumplimiento por profesional")

    if resumen_coord_prof.empty:
        st.info("No hay objetivos PAI disponibles para analizar.")
    else:
        resumen_mostrar = resumen_coord_prof.sort_values(
            ["vencidos", "sin_seguimiento", "cumplimiento_%"],
            ascending=[False, False, True]
        )

        st.dataframe(
            resumen_mostrar.rename(columns={
                "profesional": "Profesional",
                "rol": "Rol",
                "objetivos": "Objetivos",
                "cumplidos": "Cumplidos",
                "vencidos": "Vencidos",
                "proximos": "Próximos",
                "sin_seguimiento": "Sin seguimiento",
                "cumplimiento_%": "% cumplimiento"
            }),
            use_container_width=True,
            hide_index=True
        )

        graf_prof = (
            resumen_coord_prof[
                ["profesional", "cumplimiento_%"]
            ]
            .sort_values("cumplimiento_%")
            .set_index("profesional")
        )

        st.bar_chart(graf_prof)

    # ========================================================
    # ALERTAS PAI DETALLADAS
    # ========================================================
    if not alertas_pai_coord.empty:

        with st.expander(
            f"🔎 Ver detalle de {len(alertas_pai_coord)} alertas PAI"
        ):
            detalle_alertas = alertas_pai_coord[
                [
                    "documento_usuario",
                    "objetivo_tipo",
                    "profesional",
                    "rol",
                    "porcentaje_avance",
                    "fecha_meta",
                    "dias_meta",
                    "fecha_ultimo_seguimiento",
                    "dias_sin_seguimiento",
                    "vencido",
                    "proximo",
                    "sin_seguimiento"
                ]
            ].copy()

            st.dataframe(
                detalle_alertas.rename(columns={
                    "documento_usuario": "Documento",
                    "objetivo_tipo": "Objetivo",
                    "profesional": "Profesional",
                    "rol": "Rol",
                    "porcentaje_avance": "Avance %",
                    "fecha_meta": "Fecha meta",
                    "dias_meta": "Días para meta",
                    "fecha_ultimo_seguimiento": "Último seguimiento",
                    "dias_sin_seguimiento": "Días sin seguimiento",
                    "vencido": "Vencido",
                    "proximo": "Próximo",
                    "sin_seguimiento": "Sin seguimiento"
                }),
                use_container_width=True,
                hide_index=True
            )

    st.divider()

    # ========================================================
    # PERFIL DE POBLACIÓN
    # ========================================================
    st.markdown("### 📊 Lectura rápida de población")

    g1, g2 = st.columns(2)

    with g1:
        if "edad" in df_coord.columns:
            edades_coord = pd.to_numeric(
                df_coord["edad"], errors="coerce"
            )
            if edades_coord.notna().any():
                fig_edad_coord = px.histogram(
                    pd.DataFrame(
                        {"edad": edades_coord.dropna()}
                    ),
                    x="edad",
                    nbins=18,
                    title="Distribución por edad"
                )
                st.plotly_chart(
                    fig_edad_coord,
                    use_container_width=True
                )

    with g2:
        if "sexo_al_nacer" in df_coord.columns:
            sexo_coord = (
                df_coord["sexo_al_nacer"]
                .fillna("Sin dato")
                .astype(str)
                .str.strip()
                .replace({"": "Sin dato"})
                .value_counts()
                .rename_axis("sexo")
                .reset_index(name="cantidad")
            )

            if not sexo_coord.empty:
                fig_sexo_coord = px.pie(
                    sexo_coord,
                    names="sexo",
                    values="cantidad",
                    title="Sexo al nacer",
                    hole=0.45
                )
                st.plotly_chart(
                    fig_sexo_coord,
                    use_container_width=True
                )

    # ========================================================
    # DESCARGA PARA COORDINACIÓN
    # ========================================================
    if not resumen_coord_prof.empty:
        csv_coord = resumen_coord_prof.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "⬇️ Descargar seguimiento por profesional",
            data=csv_coord,
            file_name=(
                "dashboard_coordinacion_"
                + datetime.now().strftime("%Y%m%d_%H%M")
                + ".csv"
            ),
            mime="text/csv",
            use_container_width=True,
            key="descargar_dashboard_coordinacion_v8"
        )


# =========================
# ESTILO INSTITUCIONAL
# =========================
st.markdown("""
<style>

/* =========================
   STREAMLIT BASICO
========================= */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

/* ⚠️ IMPORTANTE: NO romper header */
header {visibility: visible !important;}

/* =========================
   APP DARK MODE
========================= */
.stApp {
    background-color: #0B1220;
    color: #E5E7EB;
}

/* =========================
   SIDEBAR (FIJO Y VISIBLE)
========================= */
section[data-testid="stSidebar"] {
    background-color: #0F172A !important;
    width: 21rem !important;
}

/* texto sidebar */
section[data-testid="stSidebar"] * {
    color: #E5E7EB !important;
}

/* =========================
   BOTÓN COLAPSE (OCULTAR)
========================= */
[data-testid="collapsedControl"] {
    display: none !important;
}

/* =========================
   CONTAINER PRINCIPAL
========================= */
.main .block-container {
    max-width: 1500px;
    padding-top: 1rem;
}

/* =========================
   METRICAS
========================= */
div[data-testid="stMetric"] {
    background: #111827;
    border-radius: 14px;
    padding: 16px;
    border-left: 4px solid #3B82F6;
}

div[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-weight: 800;
}

div[data-testid="stMetricLabel"] {
    color: #9CA3AF !important;
}

/* =========================
   TABS
========================= */
button[data-baseweb="tab"] {
    font-weight: 600;
    color: #E5E7EB !important;
}

/* =========================
   TABLAS
========================= */
[data-testid="stDataFrame"] {
    background: #111827;
    border-radius: 12px;
    padding: 8px;
    color: white;
}

/* =========================
   GRAFICOS
========================= */
[data-testid="stPlotlyChart"] {
    background: #111827;
    border-radius: 12px;
    padding: 10px;
}

/* =========================
   TITULOS
========================= */
h1, h2, h3 {
    color: #F9FAFB !important;
}

/* =========================
   TEXTO
========================= */
p, label, span {
    color: #D1D5DB;
}

/* =========================
   BANNER
========================= */
.banner {
    background: linear-gradient(90deg,#0F172A,#1E3A8A,#2563EB);
    padding: 35px;
    border-radius: 0 0 20px 20px;
    margin-bottom: 25px;
}

.banner-title {
    color: white;
    font-size: 42px;
    font-weight: 700;
}

.banner-subtitle {
    color: #CBD5E1;
    font-size: 18px;
    margin-top: 10px;
}

</style>
""", unsafe_allow_html=True)

exigir_login_v12()

# =====================================
# SIDEBAR
# =====================================

with st.sidebar:

    st.image("logo_acf.png", width=220)

    st.markdown("---")
    st.markdown("### Asociación Ciudad Futuro")
    st.caption(
        "Sistema Integral de Atención, "
        "Seguimiento y Observatorio Social"
    )

    st.markdown("---")
    st.markdown(
        f"**{st.session_state.get('nombre_funcionario','')}**"
    )
    st.caption(
        f"{st.session_state.get('rol_actual','')} · "
        f"CC {st.session_state.get('documento_funcionario','')}"
    )
    if st.session_state.get("rol_actual") == "MANAGER":
        st.success("🛡️ Acceso total de Manager")
    st.markdown("---")

    rol_menu = st.session_state.get(
        "rol_actual", ""
    )

    if rol_menu == "INSPIRADOR":

        if st.button(
            "📱 Gestión Móvil",
            use_container_width=True,
            type="primary"
        ):
            st.session_state.page = "gestion_movil"
            st.rerun()

        st.caption(
            "Ingresos · reingresos · permisos · sanciones · "
            "caracterización · novedades"
        )

    elif rol_menu == "PROFESIONAL":

        acceso_pai_menu = False
        try:
            _cedula_menu = str(
                st.session_state.get("documento_funcionario", "")
            ).strip()
            _permiso_menu = pd.read_sql(
                text("""
                    SELECT COALESCE(acceso_pai, FALSE) AS acceso_pai
                    FROM funcionarios_sistema
                    WHERE cedula=:cedula
                      AND activo=TRUE
                    LIMIT 1
                """),
                engine,
                params={"cedula": _cedula_menu}
            )
            acceso_pai_menu = (
                not _permiso_menu.empty
                and bool(_permiso_menu.iloc[0]["acceso_pai"])
            )
        except Exception:
            acceso_pai_menu = False

        if acceso_pai_menu:
            if st.button(
                "🩺 Mi Panel Profesional",
                use_container_width=True,
                type="primary"
            ):
                st.session_state.page = "panel_profesional_v15"
                st.rerun()

        if st.button(
            "👤 Gestión Profesional",
            use_container_width=True
        ):
            st.session_state.page = "gestion_movil"
            st.rerun()

        if st.button(
            "📚 Historia Integral",
            use_container_width=True
        ):
            st.session_state.page = "historia_integral_v12"
            st.rerun()

    elif rol_menu in ["COORDINACION", "MANAGER"]:

        if st.button(
            "🏠 Inicio",
            use_container_width=True
        ):
            st.session_state.page = "home"
            st.rerun()

        if st.button(
            "🎛️ Dashboard Coordinación",
            use_container_width=True
        ):
            st.session_state.page = "dashboard_ejecutivo"
            st.rerun()

        if st.button(
            "🎯 Supervisión PAI",
            use_container_width=True
        ):
            st.session_state.page = "supervision_pai_v15"
            st.rerun()

        if st.button(
            "🧠 Comité de Casos",
            use_container_width=True
        ):
            st.session_state.page = "comite_casos_v16"
            st.rerun()

        if st.button(
            "📱 Gestión Móvil",
            use_container_width=True
        ):
            st.session_state.page = "gestion_movil"
            st.rerun()

        if st.button(
            "🕐 Control de Turno",
            use_container_width=True
        ):
            st.session_state.page = "control_turno_v13"
            st.rerun()

        if st.button(
            "⚙️ Gestión usuarios",
            use_container_width=True
        ):
            st.session_state.page = "gestion_usuarios"
            st.rerun()

        if st.button(
            "📚 Historia Integral",
            use_container_width=True
        ):
            st.session_state.page = "historia_integral_v12"
            st.rerun()

        if st.button(
            "👥 Personal autorizado",
            use_container_width=True
        ):
            st.session_state.page = "funcionarios_sistema_v12"
            st.rerun()

        if st.button(
            "♀️ Género y Diversidad",
            use_container_width=True
        ):
            st.session_state.page = "genero_diversidad"
            st.rerun()

    st.markdown("---")

    if st.button(
        "🚪 Cerrar sesión",
        use_container_width=True
    ):
        cerrar_sesion_v12()

# =====================================
# FUNCIÓN GÉNERO Y DIVERSIDAD (ACTUALIZADA)
# =====================================

def formulario_genero_diversidad():

    st.header("♀️ Equidad de Género y Diversidad")

    with st.form("form_genero_diversidad"):

        numero_identificacion = st.text_input(
            "Número de identificación"
        )

        nombre_identitario = st.text_input(
            "Nombre identitario"
        )

        sexo_al_nacer = st.selectbox(
            "Sexo al nacer",
            ["Masculino", "Femenino", "Intersex", "Prefiere no responder"]
        )

        identidad_genero = st.selectbox(
            "Identidad de género",
            [
                "Mujer cisgénero",
                "Mujer trans",
                "Hombre cisgénero",
                "Hombre trans",
                "Persona no binaria",
                "Género fluido",
                "Queer",
                "Otra",
                "Prefiere no responder"
            ]
        )

        orientacion_sexual = st.selectbox(
            "Orientación sexual",
            [
                "Heterosexual",
                "Homosexual",
                "Lesbiana",
                "Bisexual",
                "Pansexual",
                "Asexual",
                "Otra",
                "Prefiere no responder"
            ]
        )

        expresion_genero = st.selectbox(
            "Expresión de género",
            [
                "Masculina",
                "Femenina",
                "Andrógina",
                "Variable",
                "Otra"
            ]
        )

        discriminacion = st.checkbox(
            "¿Ha sufrido discriminación?"
        )

        tipo_discriminacion = st.text_area(
            "Tipo de discriminación"
        )

        violencia_genero = st.checkbox(
            "Violencia basada en género"
        )

        violencia_fisica = st.checkbox(
            "Violencia física"
        )

        violencia_sexual = st.checkbox(
            "Violencia sexual"
        )

        violencia_institucional = st.checkbox(
            "Violencia institucional"
        )

        trabajo_sexual = st.selectbox(
            "Trabajo sexual",
            [
                "Nunca",
                "Anteriormente",
                "Actualmente"
            ]
        )

        estado_vih = st.selectbox(
            "Estado VIH",
            [
                "Negativo",
                "Positivo",
                "No conoce"
            ]
        )

        tratamiento_vih = st.selectbox(
            "Tratamiento VIH",
            [
                "Sí",
                "No",
                "No aplica"
            ]
        )

        acceso_salud = st.selectbox(
            "Acceso a salud",
            [
                "Sí",
                "No",
                "Parcial"
            ]
        )

        regimen_salud = st.selectbox(
            "Régimen de salud",
            [
                "Subsidiado",
                "Contributivo",
                "Especial",
                "No afiliado"
            ]
        )

        red_apoyo = st.selectbox(
            "Red de apoyo",
            [
                "Sí",
                "No",
                "Parcial"
            ]
        )

        amenazas = st.checkbox(
            "¿Ha recibido amenazas?"
        )

        custodia_hijos = st.text_input(
            "Situación de hijos"
        )

        fuente_ingresos = st.text_input(
            "Fuente principal de ingresos"
        )

        necesidades_prioritarias = st.text_area(
            "Necesidades prioritarias"
        )

        # 🔹 NUEVOS CAMPOS SPA Y PROGRAMAS
        uso_sustancias = st.checkbox(
            "¿Consumo de sustancias psicoactivas?"
        )

        sustancias_consumidas = st.multiselect(
            "Sustancias consumidas",
            [
                "Marihuana",
                "Tusi",
                "Heroína",
                "Bazuco",
                "Alcohol",
                "Cocaína",
                "Otra"
            ]
        )

        acceso_otros_programas = st.checkbox(
            "¿Ha accedido a otros programas?"
        )

        activacion_ruta_vbg = st.checkbox(
            "¿Ha activado ruta de atención en VBG?"
        )

        guardar_genero = st.form_submit_button(
            "💾 Guardar Caracterización"
        )

    # ==========================
    # GUARDAR EN BASE DE DATOS
    # ==========================

    if guardar_genero:

        with engine.begin() as conn:

            conn.execute(
                text("""
                    INSERT INTO caracterizacion_genero_diversidad (
                        numero_identificacion,
                        identidad_genero,
                        orientacion_sexual,
                        expresion_genero,
                        nombre_identitario,
                        sexo_al_nacer,
                        discriminacion,
                        tipo_discriminacion,
                        violencia_genero,
                        violencia_fisica,
                        violencia_sexual,
                        violencia_institucional,
                        trabajo_sexual,
                        estado_vih,
                        tratamiento_vih,
                        acceso_salud,
                        regimen_salud,
                        red_apoyo,
                        amenazas,
                        custodia_hijos,
                        fuente_ingresos,
                        necesidades_prioritarias,
                        uso_sustancias,
                        sustancias_consumidas,
                        acceso_otros_programas,
                        activacion_ruta_vbg,
                        fecha_registro
                    )
                    VALUES (
                        :numero_identificacion,
                        :identidad_genero,
                        :orientacion_sexual,
                        :expresion_genero,
                        :nombre_identitario,
                        :sexo_al_nacer,
                        :discriminacion,
                        :tipo_discriminacion,
                        :violencia_genero,
                        :violencia_fisica,
                        :violencia_sexual,
                        :violencia_institucional,
                        :trabajo_sexual,
                        :estado_vih,
                        :tratamiento_vih,
                        :acceso_salud,
                        :regimen_salud,
                        :red_apoyo,
                        :amenazas,
                        :custodia_hijos,
                        :fuente_ingresos,
                        :necesidades_prioritarias,
                        :uso_sustancias,
                        :sustancias_consumidas,
                        :acceso_otros_programas,
                        :activacion_ruta_vbg,
                        NOW()
                    )
                """),
                {
                    "numero_identificacion": numero_identificacion,
                    "identidad_genero": identidad_genero,
                    "orientacion_sexual": orientacion_sexual,
                    "expresion_genero": expresion_genero,
                    "nombre_identitario": nombre_identitario,
                    "sexo_al_nacer": sexo_al_nacer,
                    "discriminacion": discriminacion,
                    "tipo_discriminacion": tipo_discriminacion,
                    "violencia_genero": violencia_genero,
                    "violencia_fisica": violencia_fisica,
                    "violencia_sexual": violencia_sexual,
                    "violencia_institucional": violencia_institucional,
                    "trabajo_sexual": trabajo_sexual,
                    "estado_vih": estado_vih,
                    "tratamiento_vih": tratamiento_vih,
                    "acceso_salud": acceso_salud,
                    "regimen_salud": regimen_salud,
                    "red_apoyo": red_apoyo,
                    "amenazas": amenazas,
                    "custodia_hijos": custodia_hijos,
                    "fuente_ingresos": fuente_ingresos,
                    "necesidades_prioritarias": necesidades_prioritarias,
                    "uso_sustancias": uso_sustancias,
                    "sustancias_consumidas": sustancias_consumidas,
                    "acceso_otros_programas": acceso_otros_programas,
                    "activacion_ruta_vbg": activacion_ruta_vbg
                }
            )

        st.success("✅ Caracterización guardada correctamente")

# =====================================
# INDICADORES
# =====================================

if st.session_state.page == "genero_diversidad":

    st.markdown("---")
    st.subheader("📊 Indicadores de Género, Diversidad y Salud")

    try:

        df_genero = pd.read_sql(
            """
            SELECT *
            FROM caracterizacion_genero_diversidad
            """,
            engine
        )

        if df_genero.empty:
            st.warning("No hay registros aún en la base de datos.")

        else:

            total = len(df_genero)

            discriminacion = df_genero["discriminacion"].sum()
            violencia_genero = df_genero["violencia_genero"].sum()
            violencia_fisica = df_genero["violencia_fisica"].sum()
            violencia_sexual = df_genero["violencia_sexual"].sum()
            violencia_institucional = df_genero["violencia_institucional"].sum()
            activacion_vbg = df_genero["activacion_ruta_vbg"].sum()

            vih_positivo = len(
                df_genero[df_genero["estado_vih"] == "Positivo"]
            )

            uso_sustancias = df_genero["uso_sustancias"].sum()
            acceso_programas = df_genero["acceso_otros_programas"].sum()

            c1, c2, c3, c4 = st.columns(4)

            c1.metric("👥 Total caracterizaciones", total)
            c2.metric("⚠️ Discriminación", int(discriminacion))
            c3.metric("🚨 Violencia de género", int(violencia_genero))
            c4.metric("🧬 VIH positivo", vih_positivo)

            st.markdown("### 🚨 Violencias")

            c5, c6, c7, c8 = st.columns(4)

            c5.metric("💥 Violencia física", int(violencia_fisica))
            c6.metric("🔥 Violencia sexual", int(violencia_sexual))
            c7.metric("🏛️ Violencia institucional", int(violencia_institucional))
            c8.metric("🛑 Ruta VBG activada", int(activacion_vbg))

            st.markdown("### 🏥 Salud y programas")

            c9, c10 = st.columns(2)

            c9.metric("💊 Consumo de sustancias", int(uso_sustancias))
            c10.metric("📌 Acceso a otros programas", int(acceso_programas))

    except Exception as e:

        st.warning("Error cargando indicadores")
        st.caption(str(e))
# =====================================
# ROUTER V12
# =====================================

rol_router = st.session_state.get(
    "rol_actual", ""
)

# V14: Inspiradores operan únicamente desde Gestión Móvil.
if (
    rol_router == "INSPIRADOR"
    and st.session_state.page != "gestion_movil"
):
    st.session_state.page = "gestion_movil"
    st.rerun()

# V15.1: solo profesionales habilitados para PAI entran a su tablero.
if (
    rol_router == "PROFESIONAL"
    and st.session_state.page == "home"
):
    try:
        _cedula_router = str(
            st.session_state.get("documento_funcionario", "")
        ).strip()
        _pai_router = pd.read_sql(
            text("""
                SELECT COALESCE(acceso_pai, FALSE) AS acceso_pai
                FROM funcionarios_sistema
                WHERE cedula=:cedula
                  AND activo=TRUE
                LIMIT 1
            """),
            engine,
            params={"cedula": _cedula_router}
        )
        if (
            not _pai_router.empty
            and bool(_pai_router.iloc[0]["acceso_pai"])
        ):
            st.session_state.page = "panel_profesional_v15"
            st.rerun()
    except Exception:
        pass

if st.session_state.page == "gestion_movil":

    if rol_router not in [
        "INSPIRADOR",
        "PROFESIONAL",
        "COORDINACION",
        "MANAGER"
    ]:
        st.error("No tiene permisos para este módulo.")
    else:
        gestion_usuarios_movil()

    st.stop()

elif st.session_state.page == "control_turno_v13":

    if rol_router not in [
        "INSPIRADOR",
        "COORDINACION",
        "MANAGER"
    ]:
        st.error(
            "Control de Turno está habilitado para "
            "Inspiradores, Coordinación y Manager."
        )
    else:
        control_turno_v13()

    st.stop()

elif st.session_state.page == "historia_integral_v12":

    historia_integral_v12()
    st.stop()

elif st.session_state.page == "funcionarios_sistema_v12":

    if rol_router not in ["COORDINACION", "MANAGER"]:
        st.error(
            "Acceso exclusivo para Coordinación o Manager."
        )
    else:
        gestion_personal_v12_1()

    st.stop()

elif st.session_state.page == "panel_profesional_v15":

    if rol_router not in [
        "PROFESIONAL",
        "COORDINACION",
        "MANAGER"
    ]:
        st.error("No tiene permisos para Mi Panel Profesional.")
    else:
        panel_profesional_v15()

    st.stop()

elif st.session_state.page == "comite_casos_v16":

    if rol_router not in ["COORDINACION", "MANAGER"]:
        st.error("Acceso exclusivo para Coordinación o Manager.")
    else:
        comite_casos_v16()

    st.stop()

elif st.session_state.page == "supervision_pai_v15":

    if rol_router not in ["COORDINACION", "MANAGER"]:
        st.error("Acceso exclusivo para Coordinación o Manager.")
    else:
        supervision_pai_v15()

    st.stop()

elif st.session_state.page == "dashboard_ejecutivo":

    if rol_router not in ["COORDINACION", "MANAGER"]:
        st.error(
            "Acceso exclusivo para Coordinación o Manager."
        )
    else:
        dashboard_ejecutivo()

    st.stop()

elif st.session_state.page == "gestion_usuarios":

    if rol_router not in ["COORDINACION", "MANAGER"]:
        st.error(
            "Acceso exclusivo para Coordinación o Manager."
        )
    else:
        gestion_usuarios()

    st.stop()

elif st.session_state.page == "genero_diversidad":

    if rol_router not in ["COORDINACION", "MANAGER"]:
        st.error(
            "Acceso exclusivo para Coordinación o Manager."
        )
    else:
        formulario_genero_diversidad()

    st.stop()

# Inspiradores y profesionales no entran al escritorio general.
if (
    st.session_state.page == "home"
    and rol_router in [
        "INSPIRADOR",
        "PROFESIONAL"
    ]
):
    st.session_state.page = "gestion_movil"
    st.rerun()


def gestion_usuarios_legacy():
    
    st.title("⚙️ Gestión de usuarios")

    # =========================
    # CARGA DE DATOS
    # =========================
    df = pd.read_sql("""
        SELECT *
        FROM habitante_de_calle
    """, engine)

    df["modalidad"] = df["modalidad"].astype(str).str.upper().str.strip()
    df["estado_caso"] = df["estado_caso"].astype(str).str.upper().str.strip()

    df_activos = df[df["estado_caso"] == "ACTIVO"]

    # =========================
    # CUPOS EN TIEMPO REAL
    # =========================
    urbano, granja = cupos_actuales(df)

    col1, col2, col3 = st.columns(3)

    col1.metric("🏙️ Urbanos activos", urbano)
    col2.metric("🌱 Granja activos", granja)
    col3.metric("📊 Total activos", urbano + granja)

    st.divider()

    # =========================
    # BUSCADOR
    # =========================
    df["nombre"] = df["nombres"].astype(str) + " " + df["apellidos"].astype(str)

    usuario_sel = st.selectbox(
        "🔎 Buscar usuario",
        df.index,
        format_func=lambda x: f"{df.loc[x,'nombre']} - {df.loc[x,'numero_identificacion']}"
    )

    persona = df.loc[usuario_sel]

    st.info(f"""
    👤 {persona['nombre']}
    🪪 {persona['numero_identificacion']}
    📌 Estado: {persona['estado_caso']}
    🏷️ Modalidad: {persona['modalidad']}
    """)
        
    colA, colB = st.columns(2)
        
    # =========================
    # EGRESO
    # =========================
    with colA:

        if persona["estado_caso"] == "ACTIVO":

            if st.button("📤 Registrar egreso"):

                with engine.begin() as conn:

                    conn.execute(text("""
                        UPDATE habitante_de_calle
                        SET estado_caso = 'EGRESADO',
                            fecha_ultimo_egreso = CURRENT_DATE
                        WHERE numero_identificacion = :doc
                    """), {"doc": persona["numero_identificacion"]})

                    conn.execute(text("""
                        INSERT INTO movimientos_habitante (
                            numero_identificacion,
                            tipo_movimiento,
                            modalidad,
                            usuario_registra,
                            observacion
                        )
                        VALUES (
                            :doc,
                            'EGRESO',
                            :modalidad,
                            'sistema',
                            'Egreso desde gestión usuarios'
                        )
                    """), {
                        "doc": persona["numero_identificacion"],
                        "modalidad": persona["modalidad"]
                    })

                registrar_auditoria("REGISTRAR_EGRESO", persona["numero_identificacion"], "gestion_usuarios", "ACTIVO", "EGRESADO")
                invalidar_cache_datos()
                st.success("✔ Egreso registrado")
                st.rerun()

    # =========================
    # REINGRESO
    # =========================
    with colB:

        if persona["estado_caso"] == "EGRESADO":

            if st.button("📥 Registrar reingreso"):

                with engine.begin() as conn:

                    conn.execute(text("""
                        UPDATE habitante_de_calle
                        SET estado_caso = 'ACTIVO',
                            fecha_ultimo_ingreso = CURRENT_DATE,
                            numero_reingresos = COALESCE(numero_reingresos,0) + 1
                        WHERE numero_identificacion = :doc
                    """), {"doc": persona["numero_identificacion"]})

                    conn.execute(text("""
                        INSERT INTO movimientos_habitante (
                            numero_identificacion,
                            tipo_movimiento,
                            modalidad,
                            usuario_registra,
                            observacion
                        )
                        VALUES (
                            :doc,
                            'REINGRESO',
                            :modalidad,
                            'sistema',
                            'Reingreso desde gestión usuarios'
                        )
                    """), {
                        "doc": persona["numero_identificacion"],
                        "modalidad": persona["modalidad"]
                    })

                registrar_auditoria("REGISTRAR_REINGRESO", persona["numero_identificacion"], "gestion_usuarios", "EGRESADO", "ACTIVO")
                invalidar_cache_datos()
                st.success("✔ Reingreso registrado")
                st.rerun()

    st.divider()

    # =========================
    # CAMBIO MANUAL DE ESTADO
    # =========================
    st.subheader("🚫 Cambiar estado")

    usuario_estado = st.selectbox(
        "Selecciona usuario",
        df["numero_identificacion"].tolist()
    )

    nuevo_estado = st.selectbox("Nuevo estado", ["ACTIVO", "EGRESADO"])

    if st.button("Actualizar estado"):

        estado_anterior_df = pd.read_sql(
            text("""
                SELECT estado_caso, modalidad
                FROM habitante_de_calle
                WHERE TRIM(CAST(numero_identificacion AS TEXT)) = :id
                LIMIT 1
            """),
            engine,
            params={"id": str(usuario_estado).strip()}
        )

        estado_anterior = (
            str(estado_anterior_df.iloc[0]["estado_caso"])
            if not estado_anterior_df.empty else ""
        )
        modalidad_actual = (
            estado_anterior_df.iloc[0]["modalidad"]
            if not estado_anterior_df.empty else None
        )

        with engine.begin() as conn:

            conn.execute(text("""
                UPDATE habitante_de_calle
                SET estado_caso = :estado
                WHERE TRIM(CAST(numero_identificacion AS TEXT)) = :id
            """), {
                "estado": nuevo_estado,
                "id": str(usuario_estado).strip()
            })

            if estado_anterior.strip().upper() != nuevo_estado.strip().upper():
                conn.execute(text("""
                    INSERT INTO movimientos_habitante (
                        numero_identificacion,
                        tipo_movimiento,
                        modalidad,
                        usuario_registra,
                        observacion
                    )
                    VALUES (
                        :doc,
                        'CAMBIO_ESTADO_MANUAL',
                        :modalidad,
                        :usuario,
                        :observacion
                    )
                """), {
                    "doc": str(usuario_estado).strip(),
                    "modalidad": modalidad_actual,
                    "usuario": st.session_state.get("usuario_actual", "sistema"),
                    "observacion": (
                        f"Cambio manual de estado: "
                        f"{estado_anterior or 'SIN ESTADO'} -> {nuevo_estado}"
                    )
                })

        registrar_auditoria(
            "ACTUALIZAR_ESTADO",
            documento=usuario_estado,
            modulo="Gestión Usuarios",
            valor_anterior=estado_anterior,
            valor_nuevo=nuevo_estado
        )
        invalidar_cache_datos()
        st.success("Estado actualizado")
        st.rerun()
   
# =====================================
# BANNER PRINCIPAL
# =====================================
st.markdown("""
<div class="banner">

<div class="banner-title">
Sistema Integral de Atención y Seguimiento
</div>

<div class="banner-subtitle">
Gestión integral de usuarios • Seguimiento profesional •
Plan de Atención Individual (PAI) • Reducción de riesgos y daños •
Adherencia al tratamiento • Indicadores de impacto social
</div>

</div>
""", unsafe_allow_html=True)

# =====================================
# OLLAMA
# =====================================
# client = Client(host="http://localhost:11434")

# =====================================
# POSTGRESQL / SUPABASE
# =====================================
# engine reutiliza la conexión definida al inicio


# =========================
# OLLAMA
# =========================
#client = Client(host="http://localhost:11434")

# =========================
# POSTGRESQL / SUPABASE
# =========================
# engine reutiliza la conexión definida al inicio

# =========================
# TÍTULO
# =========================
st.title("🧠 Observatorio Social Habitante de Calle Pereira 2026")

# =========================
# CARGAR DATOS
# =========================
df = pd.read_sql("SELECT * FROM habitante_de_calle", engine)
df = df.drop_duplicates()

# =========================
# LIMPIEZA COLUMNAS
# =========================
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace("\n", " ")
    .str.replace("  ", " ")
    .str.replace(" ", "_")
)

# =========================
# CUPOS EN TIEMPO REAL
# =========================
def cupos_actuales(df):

    df["modalidad"] = df["modalidad"].astype(str).str.upper().str.strip()
    df["estado_caso"] = df["estado_caso"].astype(str).str.upper().str.strip()

    urbano_activos = len(
        df[(df["modalidad"] == "URBANO") & (df["estado_caso"] == "ACTIVO")]
    )

    granja_activos = len(
        df[(df["modalidad"] == "GRANJA") & (df["estado_caso"] == "ACTIVO")]
    )

    return urbano_activos, granja_activos
def validar_cupos(df, modalidad):
    
    urbano, granja = cupos_actuales(df)

    if modalidad == "URBANO" and urbano >= 100:
        return False, "🚨 Urbano está en capacidad máxima"

    return True, "OK"

# =========================
# FUNCIONES AUXILIARES
# =========================

def generar_resumen(df):

    total = len(df)

    consumo_top = (
        df["tipo_consumo"].value_counts().idxmax()
        if "tipo_consumo" in df.columns and len(df) > 0
        else None
    )

    etnia_top = (
        df["grupos_etnicos_afro_indigena"].value_counts().idxmax()
        if "grupos_etnicos_afro_indigena" in df.columns and len(df) > 0
        else None
    )

    return {
        "total": total,
        "consumo_top": consumo_top,
        "etnia_top": etnia_top
    }


def cargar_datos():
    df = pd.read_sql("SELECT * FROM habitante_de_calle", engine)

    df["estado_caso"] = (
        df["estado_caso"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Limpieza de sexo (bien ubicada aquí)
    if "sexo_al_nacer" in df.columns:
        df["sexo_al_nacer"] = (
            df["sexo_al_nacer"]
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({
                "M": "Masculino",
                "F": "Femenino",
                "MASCULINO": "Masculino",
                "FEMENINO": "Femenino",
            })
        )

    return df

# =========================
# SIDEBAR
# =========================

with st.sidebar:

    st.header("🏛️ Sistema de Atención")

    # =========================
    # CARGA DE DATOS
    # =========================
    df = cargar_datos()

    # =========================
    # CUPOS
    # =========================
    urbano, granja = cupos_actuales(df)

    st.subheader("📊 Cupos en tiempo real")

    st.metric("🏙️ Urbano (máx 100)", f"{urbano}/100")
    st.metric("🌱 Granja", granja)

    if urbano >= 100:
        st.error("🚨 URBANO EN CAPACIDAD MÁXIMA")

    st.divider()

    # =========================
    # USUARIOS URBANO
    # =========================
    with st.expander("🏙️ Usuarios URBANO activos"):

        df_urbano = df[
            (df["modalidad"] == "URBANO") &
            (df["estado_caso"] == "ACTIVO")
        ][["nombres", "apellidos", "numero_identificacion"]].copy()

        df_urbano["nombre"] = (
            df_urbano["nombres"].astype(str) + " " +
            df_urbano["apellidos"].astype(str)
        )

        st.dataframe(
            df_urbano[["nombre", "numero_identificacion"]],
            use_container_width=True
        )

    # =========================
    # USUARIOS GRANJA
    # =========================
    with st.expander("🌱 Usuarios GRANJA activos"):

        df_granja = df[
            (df["modalidad"] == "GRANJA") &
            (df["estado_caso"] == "ACTIVO")
        ][["nombres", "apellidos", "numero_identificacion"]].copy()

        df_granja["nombre"] = (
            df_granja["nombres"].astype(str) + " " +
            df_granja["apellidos"].astype(str)
        )

        st.dataframe(
            df_granja[["nombre", "numero_identificacion"]],
            use_container_width=True
        )

    st.divider()

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9= st.tabs([

    "📊 General",

    "🩺 Enfermería",

    "🏆 Egresos e Impacto",

    "📄 Reportes",

    "➕ Nuevo Registro",

    "📋 Seguimiento Profesional",

    "📈 Seguimiento e Impacto",

    "📥 Carga Activos",
    
    "📄 Historia Integral"
])

# =========================
# TAB GENERAL
# =========================
with tab1:

    st.subheader("📊 Caracterización General")

    st.caption(
        "Descripción sociodemográfica de la población atendida."
    )

    # =====================================
    # SEXO Y EDAD
    # =====================================

    col1, col2 = st.columns(2)

    with col1:

        if "sexo_al_nacer" in df.columns:

            sexo_df = (
                df["sexo_al_nacer"]
                .value_counts()
                .reset_index()
            )

            sexo_df.columns = [
                "sexo",
                "cantidad"
            ]

            fig1 = px.pie(
                sexo_df,
                names="sexo",
                values="cantidad",
                title="Sexo al nacer"
            )

            st.plotly_chart(
                fig1,
                use_container_width=True
            )

            sexo_top = sexo_df.iloc[0]

            st.info(
                f"Predomina el sexo {sexo_top['sexo']} con {sexo_top['cantidad']} registros."
            )

    with col2:

        if "edad" in df.columns:

            df["edad"] = pd.to_numeric(
                df["edad"],
                errors="coerce"
            )

            fig2 = px.histogram(
                df,
                x="edad",
                nbins=20,
                title="Distribución de edades"
            )

            st.plotly_chart(
                fig2,
                use_container_width=True
            )

            edad_promedio = round(
                df["edad"].mean(),
                1
            )

            st.info(
                f"Edad promedio de la población: {edad_promedio} años."
            )

    st.markdown("---")

    # =====================================
    # GRUPO ETARIO
    # =====================================

    if "edad" in df.columns:

        df["grupo_etario"] = pd.cut(
            df["edad"],
            bins=[18, 28, 59, 120],
            labels=[
                "Joven",
                "Adulto",
                "Adulto Mayor"
            ]
        )

        etario_df = (
            df["grupo_etario"]
            .value_counts()
            .reset_index()
        )

        etario_df.columns = [
            "grupo",
            "cantidad"
        ]

        fig_etario = px.bar(
            etario_df,
            x="grupo",
            y="cantidad",
            text="cantidad",
            title="Distribución por grupo etario"
        )

        st.plotly_chart(
            fig_etario,
            use_container_width=True
        )

        grupo_top = etario_df.iloc[0]

        st.success(
            f"Grupo predominante: {grupo_top['grupo']} ({grupo_top['cantidad']} personas)"
        )

        total_personas = len(df)

        porcentaje_grupo = round(
            (grupo_top["cantidad"] / total_personas) * 100,
            1
        )

        with st.expander(
            "📘 Interpretación de la distribución por grupo etario"
        ):

            st.markdown(f"""
### Resultado principal

El grupo etario predominante corresponde a **{grupo_top['grupo']}**, con **{grupo_top['cantidad']} personas**, equivalente al **{porcentaje_grupo}%** de la población registrada.

### Interpretación

- **Joven (18-28 años):** requiere estrategias de inclusión social, formación para el trabajo y prevención de riesgos.

- **Adulto (29-59 años):** demanda procesos de estabilización social, fortalecimiento de redes de apoyo y generación de ingresos.

- **Adulto Mayor (60 años o más):** requiere atención integral en salud, protección social y acompañamiento permanente.

            """)

    st.markdown("---")

    # =====================================
    # RIESGOS POBLACIONALES
    # =====================================

    if (
        "grupo_etario" in df.columns
        and
        "nivel_riesgo" in df.columns
    ):

        adultos_criticos = len(
            df[
                (df["grupo_etario"] == "Adulto Mayor")
                &
                (
                    df["nivel_riesgo"]
                    .isin(["Alto", "Crítico"])
                )
            ]
        )

        jovenes_criticos = len(
            df[
                (df["grupo_etario"] == "Joven")
                &
                (
                    df["nivel_riesgo"]
                    .isin(["Alto", "Crítico"])
                )
            ]
        )

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "👴 Adultos mayores en riesgo",
                adultos_criticos
            )

        with col2:

            st.metric(
                "🧑 Jóvenes en riesgo",
                jovenes_criticos
            )

    st.markdown("---")

    # =====================================
    # DISTRIBUCIÓN TERRITORIAL
    # =====================================

    st.subheader("📍 Distribución Territorial")

    if "departamento_procedencia" in df.columns:

        territorio = (
            df["departamento_procedencia"]
            .fillna("Sin dato")
            .value_counts()
            .head(10)
            .reset_index()
        )

        territorio.columns = [
            "territorio",
            "cantidad"
        ]

        fig_territorio = px.bar(
            territorio,
            x="cantidad",
            y="territorio",
            orientation="h",
            title="Distribución por departamento de procedencia"
        )

        st.plotly_chart(
            fig_territorio,
            use_container_width=True
        )

        territorio_top = territorio.iloc[0]

        st.info(
            f"La mayor concentración de usuarios se encuentra en {territorio_top['territorio']} ({territorio_top['cantidad']} registros)."
        )

    else:

        st.warning(
            "No existe la columna departamento_procedencia."
        )
    st.subheader("💊 Tipos de consumo")

    consumo_df = (

        df["tipo_consumo"]

        .value_counts()

        .reset_index()

    )

    consumo_df.columns = [

        "consumo",

        "cantidad"

    ]

    fig = px.bar(

        consumo_df,

        x="consumo",

        y="cantidad",

        color="cantidad"

    )

    st.plotly_chart(

        fig,

        use_container_width=True

    )

    # INTERPRETACIÓN

    principal_consumo = consumo_df.iloc[0]

    st.warning(

        f"La principal sustancia reportada es {principal_consumo['consumo']}."

    )

    st.info(

        "Los patrones de consumo permiten identificar niveles de complejidad social y sanitaria."

    )

    # ==========================
    # SALUD MENTAL
    # ==========================

    st.subheader("🧠 Salud mental")

    mental_df = (

        df["enfermedad_mental"]

        .value_counts()

        .reset_index()

    )

    mental_df.columns = [

        "condicion",

        "cantidad"

    ]

    fig = px.bar(

        mental_df,

        x="condicion",

        y="cantidad",

        color="cantidad"

    )

    st.plotly_chart(

        fig,

        use_container_width=True

    )

    # INTERPRETACIÓN

    mental_top = mental_df.iloc[0]

    st.info(

        f"La condición más frecuente registrada es: {mental_top['condicion']}."

    )

    st.warning(

        "La presencia de problemas de salud mental puede aumentar la permanencia en calle y la vulnerabilidad social."

    )
    st.subheader("📚 Nivel educativo")

    df_local = df.copy()

    if "nivel_educativo" in df_local.columns:

        # =========================
        # LIMPIEZA Y AGRUPACIÓN
        # =========================

        edu = (

            df_local["nivel_educativo"]

            .fillna("Sin dato")

            .astype(str)

            .str.strip()

            .value_counts()

            .reset_index()

        )

        edu.columns = [

            "nivel",

            "conteo"

        ]

        # =========================
        # GRÁFICA DE BARRAS
        # =========================

        fig_edu = px.bar(

            edu,

            x="nivel",

            y="conteo",

            color="conteo",

            text="conteo",

            title="📚 Distribución del nivel educativo"

        )

        fig_edu.update_traces(

            textposition="outside"

        )

        fig_edu.update_layout(

            xaxis_tickangle=-45

        )

        st.plotly_chart(

            fig_edu,

            use_container_width=True

        )

        # =========================
        # HALLAZGO AUTOMÁTICO
        # =========================

        edu_top = edu.iloc[0]

        st.info(

            f"El nivel educativo predominante es: **{edu_top['nivel']}** "

            f"con {edu_top['conteo']} registros."

        )

        # =========================
        # TABLA OPCIONAL
        # =========================

        with st.expander(

            "📋 Ver tabla detallada"

        ):

            st.dataframe(

                edu

            )

    else:

        st.warning(

            "No existe la columna 'nivel_educativo' en el dataset"

        )

# =========================
# TAB ENFERMERÍA
# =========================
with tab2:

    st.subheader("🏥 Enfermería")

    df_catalogo = pd.read_sql("""
        SELECT *
        FROM catalogo_enfermeria
        ORDER BY categoria, actividad
    """, engine)

    st.subheader("🔎 Buscar usuario")

    busqueda = st.text_input(
        "Buscar por nombre o documento",
        key="enfermeria_busqueda"
    )

    df_pai_personas = pd.read_sql(
        text("""
            SELECT *
            FROM habitante_de_calle
            ORDER BY nombres, apellidos
        """),
        engine
    )

    df_busqueda = df_pai_personas.copy()

    if busqueda:

        df_busqueda = df[
            df["nombres"].astype(str).str.contains(
                busqueda,
                case=False,
                na=False
            )
            |
            df["apellidos"].astype(str).str.contains(
                busqueda,
                case=False,
                na=False
            )
            |
            df["numero_identificacion"].astype(str).str.contains(
                busqueda,
                na=False
            )
        ]

    usuario_sel = None

    if not df_busqueda.empty:

        # Etiqueta amigable
        df_busqueda["usuario_label"] = (
            df_busqueda["nombres"].fillna("")
            + " "
            + df_busqueda["apellidos"].fillna("")
            + " - CC: "
            + df_busqueda["numero_identificacion"].astype(str)
        )

        usuario_label = st.selectbox(
            "Seleccione usuario",
            df_busqueda["usuario_label"].tolist()
        )

        usuario_sel = df_busqueda.loc[
            df_busqueda["usuario_label"] == usuario_label,
            "numero_identificacion"
        ].values[0]

        st.success(f"Usuario seleccionado: {usuario_label}")

    else:

        st.warning("No se encontraron usuarios")
    # =====================================
    # REGISTRO DIARIO DE ENFERMERÍA
    # =====================================

    if usuario_sel:

        st.divider()
        st.markdown("### 🏥 Registro Diario de Enfermería")

        categoria = st.selectbox(
            "Categoría",
            sorted(df_catalogo["categoria"].dropna().unique()),
            key="tab8_categoria"
        )

        actividades_categoria = df_catalogo[
            df_catalogo["categoria"] == categoria
        ]["actividad"].tolist()

        actividad = st.selectbox(
            "Actividad",
            actividades_categoria,
            key="tab8_actividad"
        )

        resultado = st.selectbox(
            "Resultado",
            ["Realizado", "Pendiente", "Rechazado", "Remitido", "En seguimiento"],
            key="tab8_resultado"
        )

        estado_usuario = st.selectbox(
            "Estado del usuario",
            ["Estable", "Mejorando", "Deterioro", "Hospitalizado", "Ausente"],
            key="tab8_estado"
        )

        cantidad = st.number_input(
            "Cantidad",
            min_value=1,
            value=1,
            key="tab8_cantidad"
        )

        # =========================
        # 🧠 NUEVOS CAMPOS CLÍNICOS
        # =========================

        st.markdown("#### ❤️ Signos vitales")

        presion_arterial = st.text_input("Presión arterial", key="tab8_pa")
        frecuencia_cardiaca = st.number_input("Frecuencia cardíaca", min_value=0, key="tab8_fc")
        temperatura = st.number_input("Temperatura °C", min_value=30.0, max_value=45.0, step=0.1, key="tab8_temp")
        saturacion = st.number_input("Saturación O2 %", min_value=0, max_value=100, key="tab8_sat")

        st.markdown("#### 🍽 Estado nutricional")

        peso = st.number_input("Peso (kg)", min_value=0.0, key="tab8_peso")
        talla = st.number_input("Talla (m)", min_value=0.0, step=0.01, key="tab8_talla")
        apetito = st.selectbox("Apetito", ["Adecuado", "Disminuido", "Aumentado"], key="tab8_apetito")

        st.markdown("#### 🚬 Consumo de sustancias")

        consumo_actual = st.selectbox("Consumo actual", ["Sí", "No"], key="tab8_consume")
        sustancia = st.text_input("Sustancia consumida", key="tab8_sustancia")
        ultima_vez = st.text_input("Último consumo", key="tab8_ultima")

        st.markdown("#### 💊 Tratamiento")

        tratamiento = st.selectbox("Tiene tratamiento", ["Sí", "No"], key="tab8_tratamiento")
        adherencia = st.selectbox("Adherencia", ["Completa", "Parcial", "Nula"], key="tab8_adherencia")
        medicamentos = st.text_area("Medicamentos formulados", key="tab8_meds")

        st.markdown("#### 🩹 Curaciones")

        heridas = st.selectbox("Presenta heridas", ["Sí", "No"], key="tab8_heridas")
        ubicacion_herida = st.text_area("Ubicación y descripción", key="tab8_ubi_herida")
        curacion_realizada = st.selectbox("Curación realizada", ["Sí", "No"], key="tab8_curacion")

        st.markdown("#### 🧠 Estado mental")

        estado_animo = st.selectbox(
            "Estado de ánimo",
            ["Adecuado", "Ansioso", "Triste", "Irritable", "Desorientado"],
            key="tab8_animo"
        )

        riesgo = st.selectbox(
            "Nivel de riesgo",
            ["Bajo", "Medio", "Alto"],
            key="tab8_riesgo"
        )

        st.markdown("#### 🚑 Remisiones")

        remision = st.selectbox("Requiere remisión", ["Sí", "No"], key="tab8_remision")

        tipo_remision = st.selectbox(
            "Tipo de remisión",
            ["Urgencias", "Hospital", "Psiquiatría", "Medicina General", "Trabajo Social", "Otro"],
            key="tab8_tipo_remision"
        )

        observacion = st.text_area(
            "Observaciones",
            key="tab8_observacion"
        )

        ods_principal = st.selectbox(
            "ODS relacionado",
            [
                "ODS 3 - Salud y Bienestar",
                "ODS 1 - Fin de la pobreza",
                "ODS 5 - Igualdad de género",
                "ODS 10 - Reducción de desigualdades",
                "ODS 16 - Paz, justicia e instituciones sólidas"
            ],
            key="tab8_ods"
        )

        guardar_enfermeria = st.button(
            "💾 Guardar actividad de enfermería",
            key="tab8_guardar"
        )

        if guardar_enfermeria:

            with engine.begin() as conn:

                conn.execute(text("""
                    INSERT INTO enfermeria_actividades (

                        fecha,
                        documento_usuario,
                        nombre_usuario,
                        actividad,
                        categoria,
                        observacion,
                        resultado,
                        ods_principal,
                        estado_usuario,
                        cantidad,

                        presion_arterial,
                        frecuencia_cardiaca,
                        temperatura,
                        saturacion,

                        peso,
                        talla,
                        apetito,

                        consumo_actual,
                        sustancia,
                        ultima_vez,

                        tratamiento,
                        adherencia,
                        medicamentos,

                        heridas,
                        ubicacion_herida,
                        curacion_realizada,

                        estado_animo,
                        riesgo,

                        remision,
                        tipo_remision

                    )

                    VALUES (

                        NOW(),
                        :documento_usuario,
                        :nombre_usuario,
                        :actividad,
                        :categoria,
                        :observacion,
                        :resultado,
                        :ods_principal,
                        :estado_usuario,
                        :cantidad,

                        :presion_arterial,
                        :frecuencia_cardiaca,
                        :temperatura,
                        :saturacion,

                        :peso,
                        :talla,
                        :apetito,

                        :consumo_actual,
                        :sustancia,
                        :ultima_vez,

                        :tratamiento,
                        :adherencia,
                        :medicamentos,

                        :heridas,
                        :ubicacion_herida,
                        :curacion_realizada,

                        :estado_animo,
                        :riesgo,

                        :remision,
                        :tipo_remision

                    )
                """), {

                    "documento_usuario": str(usuario_sel),
                    "nombre_usuario": usuario_label,

                    "actividad": actividad,
                    "categoria": categoria,
                    "observacion": observacion,
                    "resultado": resultado,
                    "ods_principal": ods_principal,
                    "estado_usuario": estado_usuario,
                    "cantidad": int(cantidad),

                    "presion_arterial": presion_arterial,
                    "frecuencia_cardiaca": frecuencia_cardiaca,
                    "temperatura": temperatura,
                    "saturacion": saturacion,

                    "peso": peso,
                    "talla": talla,
                    "apetito": apetito,

                    "consumo_actual": consumo_actual,
                    "sustancia": sustancia,
                    "ultima_vez": ultima_vez,

                    "tratamiento": tratamiento,
                    "adherencia": adherencia,
                    "medicamentos": medicamentos,

                    "heridas": heridas,
                    "ubicacion_herida": ubicacion_herida,
                    "curacion_realizada": curacion_realizada,

                    "estado_animo": estado_animo,
                    "riesgo": riesgo,

                    "remision": remision,
                    "tipo_remision": tipo_remision
                })

            st.success("✅ Actividad de enfermería registrada correctamente")

        else:

            st.info(
                "Seleccione un usuario para registrar actividades de enfermería"
            )
with tab3:

    st.title("🏆 Egresos e Impacto")

    df_egresados = pd.read_sql("""
        SELECT *
        FROM personas_caracterizacion
        WHERE estado_caso = 'EGRESADO'
    """, engine)

    # ==========================
    # INDICADORES
    # ==========================

    st.subheader("📊 Indicadores de Egreso")

    df_impacto = pd.read_sql_query("""
        SELECT *
        FROM personas_caracterizacion
        WHERE estado_caso = 'EGRESADO'
    """, engine)

    total_egresados = len(df_impacto)
    total_personas = len(df)

    tasa_egreso = round((total_egresados / total_personas) * 100, 2) if total_personas > 0 else 0

    col1, col2, col3 = st.columns(3)

    col1.metric("🎓 Total Egresados", total_egresados)
    col2.metric("📈 Tasa de Egreso", f"{tasa_egreso}%")
    col3.metric("👤 Edad Promedio", round(df_impacto["edad"].mean(), 1) if len(df_impacto) > 0 else 0)

    st.markdown("---")

    # ==========================
    # OBSERVACIONES DE EGRESO 
    # ==========================

    st.subheader("📌 Observaciones de Egreso")

    obs_df = (
        df_egresados["observaciones_egreso"]
        .fillna("Sin observación")
        .value_counts()
        .reset_index()
    )

    obs_df.columns = ["observacion", "cantidad"]

    fig_obs = px.bar(
        obs_df,
        x="observacion",
        y="cantidad",
        color="cantidad",
        title="📌 Observaciones de egreso"
    )

    st.plotly_chart(fig_obs, use_container_width=True)

    st.markdown("---")

    # ==========================
    # DEMOGRAFÍA EGRESADOS
    # ==========================

    if "sexo_nacer" in df_impacto.columns:
        st.plotly_chart(px.pie(df_impacto, names="sexo_nacer", title="Sexo"))

    if "orientacion_lgbti" in df_impacto.columns:
        st.plotly_chart(px.histogram(df_impacto, x="orientacion_lgbti", title="Orientación sexual"))

    if "grupos_etnicos_afro_indigena" in df_impacto.columns:
        st.plotly_chart(px.histogram(df_impacto, x="grupos_etnicos_afro_indigena", title="Grupos étnicos"))

    st.plotly_chart(px.histogram(df_impacto, x="edad", nbins=10, title="Edad"))

    st.info(f"Total egresados: {total_egresados} | Tasa: {tasa_egreso}%")
with tab4:

    # ============================================================
    # REPORTES INSTITUCIONALES - OBSERVATORIO SOCIAL
    # ============================================================
    import tempfile
    from datetime import datetime
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle

    st.title("📄 Reportes Institucionales")
    st.caption(
        "Análisis institucional dinámico de la población registrada. "
        "Los indicadores, gráficas y exportaciones responden a los filtros seleccionados."
    )

    # ------------------------------------------------------------
    # FUNCIONES LOCALES DEL MÓDULO
    # ------------------------------------------------------------
    def _columna(*nombres):
        """Devuelve el primer nombre de columna disponible."""
        for nombre in nombres:
            if nombre in df.columns:
                return nombre
        return None

    def _serie_limpia(dataframe, columna):
        if not columna or columna not in dataframe.columns:
            return pd.Series(dtype="object")
        serie = dataframe[columna].copy()
        serie = serie.where(serie.notna(), "")
        serie = serie.astype(str).str.strip()
        return serie[
            (serie != "") &
            (~serie.str.upper().isin(["NAN", "NONE", "NULL"]))
        ]

    def _tabla_categoria(dataframe, columna, top_n=15):
        serie = _serie_limpia(dataframe, columna)
        if serie.empty:
            return pd.DataFrame(columns=["categoria", "cantidad", "porcentaje"])

        conteo = serie.value_counts().head(top_n)
        salida = conteo.rename_axis("categoria").reset_index(name="cantidad")
        salida["porcentaje"] = (
            salida["cantidad"] / len(serie) * 100
        ).round(1)
        return salida

    def _grafica_png(fig):
        """Genera temporalmente una gráfica para el PDF."""
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.close()
            fig.write_image(tmp.name, width=1100, height=650, scale=1.3)
            return tmp.name
        except Exception:
            return None

    def _texto_pdf(valor):
        texto = "" if valor is None else str(valor)
        return (
            texto.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
        )

    # ------------------------------------------------------------
    # IDENTIFICAR COLUMNAS EXISTENTES
    # ------------------------------------------------------------
    col_doc = _columna("numero_identificacion", "numero_de_identificacion")
    col_sexo = _columna("sexo_al_nacer")
    col_edad = _columna("edad")
    col_estado = _columna("estado_caso")
    col_modalidad = _columna("modalidad")
    col_salud = _columna("tipo_seguridad_salud", "tipo_de_seguridad_social_en_salud")
    col_educacion = _columna(
        "nivel_educativo",
        "nivel_educativo_que_tiene_o_cursa"
    )
    col_ocupacion = _columna(
        "condicion_ocupacional",
        "perfil_ocupacional_su_principal_fuente_de_ingreso_es"
    )
    col_procedencia = _columna("departamento_procedencia", "departamento_de_procedencia")
    col_poblacion = _columna("poblacion")
    col_orientacion = _columna(
        "orientacion_sexual_lgtbi",
        "orientacion_lgbti",
        "orientacion_sexual"
    )
    col_etnia = _columna(
        "grupos_etnicos_afro_indigena",
        "grupos_etnicos"
    )
    col_consumo = _columna("tipo_consumo", "tipo_de_consumo")
    col_enfermedad = _columna("enfermedad_mental")

    df_reporte = df.copy()

    if col_edad:
        df_reporte[col_edad] = pd.to_numeric(
            df_reporte[col_edad],
            errors="coerce"
        )

    # ------------------------------------------------------------
    # FILTROS
    # ------------------------------------------------------------
    st.markdown("---")
    st.subheader("🔎 Filtros del reporte")

    f1, f2, f3, f4 = st.columns(4)

    def _opciones(columna):
        if not columna:
            return []
        return sorted(_serie_limpia(df_reporte, columna).unique().tolist())

    with f1:
        sexo_sel = st.multiselect(
            "Sexo al nacer",
            _opciones(col_sexo),
            key="rep_sexo"
        )

    with f2:
        estado_sel = st.multiselect(
            "Estado del caso",
            _opciones(col_estado),
            key="rep_estado"
        )

    with f3:
        modalidad_sel = st.multiselect(
            "Modalidad",
            _opciones(col_modalidad),
            key="rep_modalidad"
        )

    with f4:
        salud_sel = st.multiselect(
            "Seguridad en salud",
            _opciones(col_salud),
            key="rep_salud"
        )

    f5, f6, f7 = st.columns([1.2, 1, 2])

    if col_edad and df_reporte[col_edad].notna().any():
        edad_min = int(df_reporte[col_edad].min())
        edad_max = int(df_reporte[col_edad].max())
        if edad_min == edad_max:
            edad_max = edad_min + 1
    else:
        edad_min, edad_max = 0, 120

    with f5:
        rango_edad = st.slider(
            "Rango de edad",
            min_value=edad_min,
            max_value=edad_max,
            value=(edad_min, edad_max),
            key="rep_rango_edad"
        )

    with f6:
        incluir_sin_edad = st.checkbox(
            "Incluir sin edad",
            value=True,
            key="rep_incluir_sin_edad"
        )

    with f7:
        busqueda = st.text_input(
            "Buscar persona",
            placeholder="Nombre, apellido o identificación",
            key="rep_busqueda"
        ).strip()

    # ------------------------------------------------------------
    # APLICAR FILTROS
    # ------------------------------------------------------------
    df_f = df_reporte.copy()
    filtros_texto = []

    def _aplicar_lista(dataframe, columna, seleccion):
        if columna and seleccion:
            valores = dataframe[columna].astype(str).str.strip()
            return dataframe[valores.isin(seleccion)]
        return dataframe

    if sexo_sel:
        df_f = _aplicar_lista(df_f, col_sexo, sexo_sel)
        filtros_texto.append("Sexo: " + ", ".join(sexo_sel))

    if estado_sel:
        df_f = _aplicar_lista(df_f, col_estado, estado_sel)
        filtros_texto.append("Estado: " + ", ".join(estado_sel))

    if modalidad_sel:
        df_f = _aplicar_lista(df_f, col_modalidad, modalidad_sel)
        filtros_texto.append("Modalidad: " + ", ".join(modalidad_sel))

    if salud_sel:
        df_f = _aplicar_lista(df_f, col_salud, salud_sel)
        filtros_texto.append("Salud: " + ", ".join(salud_sel))

    if col_edad:
        mascara_edad = df_f[col_edad].between(
            rango_edad[0], rango_edad[1], inclusive="both"
        )
        if incluir_sin_edad:
            mascara_edad = mascara_edad | df_f[col_edad].isna()
        df_f = df_f[mascara_edad]

    if busqueda:
        columnas_busqueda = [
            c for c in ["nombres", "apellidos", col_doc]
            if c and c in df_f.columns
        ]
        if columnas_busqueda:
            mascara = pd.Series(False, index=df_f.index)
            for c in columnas_busqueda:
                mascara = mascara | df_f[c].astype(str).str.contains(
                    busqueda,
                    case=False,
                    na=False,
                    regex=False
                )
            df_f = df_f[mascara]
            filtros_texto.append("Búsqueda: " + busqueda)

    if df_f.empty:
        st.warning("Los filtros seleccionados no arrojan registros.")
    else:

        # --------------------------------------------------------
        # INDICADORES
        # --------------------------------------------------------
        total = len(df_f)

        if col_edad and df_f[col_edad].notna().any():
            edad_promedio = round(float(df_f[col_edad].mean()), 1)
            edad_mediana = round(float(df_f[col_edad].median()), 1)
        else:
            edad_promedio = 0.0
            edad_mediana = 0.0

        # --------------------------------------------------------
        # ACTIVOS: se calculan desde la base general habitante_de_calle
        # EGRESOS: se calculan desde la base personas_caracterizacion
        # --------------------------------------------------------
        if col_estado:
            estado_norm = (
                df_f[col_estado]
                .astype(str)
                .str.strip()
                .str.upper()
            )
            total_activos = int((estado_norm == "ACTIVO").sum())
        else:
            total_activos = 0

        try:
            df_egresados = pd.read_sql(
                """
                SELECT *
                FROM personas_caracterizacion
                WHERE UPPER(TRIM(estado_caso)) = 'EGRESADO'
                """,
                engine
            )
            total_egresados = len(df_egresados)
        except Exception:
            df_egresados = pd.DataFrame()
            total_egresados = 0

        # Tasa institucional de referencia:
        # egresos registrados / población total de la base general.
        total_base_general = len(df_reporte)

        tasa_egreso = round(
            total_egresados / total_base_general * 100, 1
        ) if total_base_general else 0.0

        urbano_activos = 0
        granja_activos = 0

        if col_estado and col_modalidad:
            est = df_f[col_estado].astype(str).str.strip().str.upper()
            mod = df_f[col_modalidad].astype(str).str.strip().str.upper()

            urbano_activos = int(
                ((est == "ACTIVO") & (mod == "URBANO")).sum()
            )
            granja_activos = int(
                ((est == "ACTIVO") & (mod == "GRANJA")).sum()
            )

        cobertura_salud = (
            round(len(_serie_limpia(df_f, col_salud)) / total * 100, 1)
            if col_salud and total else 0.0
        )

        cobertura_educacion = (
            round(len(_serie_limpia(df_f, col_educacion)) / total * 100, 1)
            if col_educacion and total else 0.0
        )

        st.markdown("---")
        st.subheader("📊 Indicadores estratégicos")

        k1, k2, k3, k4, k5 = st.columns(5)

        k1.metric(
            "👥 Población caracterizada",
            f"{total_base_general:,}".replace(",", ".")
        )
        k2.metric(
            "🔎 Personas según filtros",
            f"{total:,}".replace(",", ".")
        )
        k3.metric("🟢 Activos", total_activos)
        k4.metric("🏆 Egresos registrados", total_egresados)
        k5.metric("📈 Tasa de egreso", f"{tasa_egreso:.1f}%")

        k6, k7, k8 = st.columns(3)
        k6.metric(
            "🎂 Edad promedio",
            f"{edad_promedio:.1f}" if edad_promedio else "S/D"
        )
        k7.metric("🏙️ Urbano activos", urbano_activos)
        k8.metric("🌱 Granja activos", granja_activos)

        # --------------------------------------------------------
        # PERFIL SOCIODEMOGRÁFICO
        # --------------------------------------------------------
        st.markdown("---")
        st.subheader("👤 Perfil sociodemográfico")

        p1, p2 = st.columns(2)

        with p1:
            sexo_tabla = _tabla_categoria(df_f, col_sexo, 10)
            if not sexo_tabla.empty:
                fig_sexo = px.pie(
                    sexo_tabla,
                    names="categoria",
                    values="cantidad",
                    hole=0.42,
                    title="Sexo al nacer"
                )
                fig_sexo.update_traces(
                    textposition="inside",
                    textinfo="percent+label"
                )
                st.plotly_chart(fig_sexo, use_container_width=True)
            else:
                st.info("Sin información suficiente de sexo al nacer.")

        with p2:
            if col_edad and df_f[col_edad].notna().any():
                fig_edad = px.histogram(
                    df_f.dropna(subset=[col_edad]),
                    x=col_edad,
                    nbins=18,
                    title="Distribución por edad",
                    labels={col_edad: "Edad"}
                )
                st.plotly_chart(fig_edad, use_container_width=True)
                st.caption(
                    f"Edad promedio: {edad_promedio:.1f} años · "
                    f"Mediana: {edad_mediana:.1f} años"
                )
            else:
                st.info("Sin información suficiente de edad.")

        # --------------------------------------------------------
        # CARACTERIZACIÓN TEMÁTICA
        # --------------------------------------------------------
        st.markdown("---")
        st.subheader("🧭 Caracterización social")

        analisis_tabs = st.tabs([
            "🎓 Educación",
            "🏥 Salud",
            "💼 Ocupación",
            "🌎 Procedencia",
            "💊 Consumo",
            "🏳️ Diversidad"
        ])

        configuracion = [
            (col_educacion, "Nivel educativo"),
            (col_salud, "Seguridad social en salud"),
            (col_ocupacion, "Condición ocupacional"),
            (col_procedencia, "Departamento de procedencia"),
            (col_consumo, "Tipo de consumo"),
            (col_orientacion, "Orientación sexual / variable registrada")
        ]

        for pesta, (columna, titulo) in zip(analisis_tabs, configuracion):
            with pesta:
                tabla_cat = _tabla_categoria(df_f, columna, 15)

                if tabla_cat.empty:
                    st.info(f"No hay información disponible para {titulo.lower()}.")
                else:
                    fig_cat = px.bar(
                        tabla_cat.sort_values("cantidad"),
                        x="cantidad",
                        y="categoria",
                        orientation="h",
                        text="cantidad",
                        title=titulo
                    )
                    fig_cat.update_layout(
                        xaxis_title="Personas",
                        yaxis_title=""
                    )
                    st.plotly_chart(
                        fig_cat,
                        use_container_width=True
                    )

                    tabla_mostrar = tabla_cat.rename(columns={
                        "categoria": titulo,
                        "cantidad": "Cantidad",
                        "porcentaje": "Porcentaje %"
                    })
                    st.dataframe(
                        tabla_mostrar,
                        use_container_width=True,
                        hide_index=True
                    )

        # --------------------------------------------------------
        # OTROS ENFOQUES
        # --------------------------------------------------------
        st.markdown("---")
        st.subheader("🎯 Enfoques diferenciales y condiciones")

        e1, e2 = st.columns(2)

        with e1:
            etnia_tabla = _tabla_categoria(df_f, col_etnia, 12)
            if not etnia_tabla.empty:
                fig_etnia = px.bar(
                    etnia_tabla,
                    x="categoria",
                    y="cantidad",
                    text="cantidad",
                    title="Grupos étnicos"
                )
                st.plotly_chart(fig_etnia, use_container_width=True)

        with e2:
            enfermedad_tabla = _tabla_categoria(
                df_f, col_enfermedad, 10
            )
            if not enfermedad_tabla.empty:
                fig_enf = px.pie(
                    enfermedad_tabla,
                    names="categoria",
                    values="cantidad",
                    hole=0.35,
                    title="Enfermedad mental - variable registrada"
                )
                st.plotly_chart(fig_enf, use_container_width=True)

        # --------------------------------------------------------
        # CALIDAD DEL DATO - VISTA COMPACTA
        # --------------------------------------------------------
        st.markdown("---")

        campos_calidad = [
            (col_doc, "Identificación"),
            (col_edad, "Edad"),
            (col_sexo, "Sexo al nacer"),
            (col_salud, "Seguridad en salud"),
            (col_educacion, "Nivel educativo"),
            (col_ocupacion, "Condición ocupacional"),
            (col_procedencia, "Procedencia"),
            (col_estado, "Estado del caso"),
            (col_modalidad, "Modalidad")
        ]

        calidad = []

        for columna, etiqueta in campos_calidad:
            if columna and columna in df_f.columns:
                if columna == col_edad:
                    completos = int(
                        pd.to_numeric(
                            df_f[columna], errors="coerce"
                        ).notna().sum()
                    )
                else:
                    completos = len(_serie_limpia(df_f, columna))

                calidad.append({
                    "Campo": etiqueta,
                    "Completos": completos,
                    "Faltantes": total - completos,
                    "Completitud %": round(
                        completos / total * 100, 1
                    ) if total else 0
                })

        df_calidad = pd.DataFrame(calidad)

        with st.expander("🔍 Ver calidad y completitud de la base"):
            st.caption(
                "Control técnico de diligenciamiento. "
                "No corresponde a un indicador de impacto social."
            )

            if not df_calidad.empty:
                st.dataframe(
                    df_calidad,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No hay variables disponibles para evaluar completitud.")

        # --------------------------------------------------------
        # HALLAZGOS AUTOMÁTICOS
        # --------------------------------------------------------
        st.markdown("---")
        st.subheader("📋 Hallazgos automáticos")

        hallazgos = []

        if edad_promedio >= 50:
            hallazgos.append(
                f"La edad promedio es de {edad_promedio:.1f} años, "
                "lo que evidencia una presencia importante de población de mayor edad."
            )

        if total_egresados > 0 and tasa_egreso < 10:
            hallazgos.append(
                f"La tasa de egreso es de {tasa_egreso:.1f}%."
            )

        if col_salud and cobertura_salud < 80:
            hallazgos.append(
                f"La variable de seguridad social en salud tiene "
                f"{cobertura_salud:.1f}% de completitud."
            )

        if col_educacion and cobertura_educacion < 80:
            hallazgos.append(
                f"La variable de nivel educativo tiene "
                f"{cobertura_educacion:.1f}% de completitud."
            )

        if not hallazgos:
            st.success(
                "No se identifican alertas automáticas con los criterios configurados."
            )
        else:
            for hallazgo in hallazgos:
                st.warning(hallazgo)

        # --------------------------------------------------------
        # CONCLUSIONES
        # --------------------------------------------------------
        st.subheader("📝 Síntesis institucional")

        conclusiones = [
            f"La base general contiene {total_base_general} personas caracterizadas y el análisis filtrado incluye {total} registros.",
            (
                f"La edad promedio es {edad_promedio:.1f} años."
                if edad_promedio
                else "No existe información suficiente para calcular la edad promedio."
            ),
            (
                f"Se identifican {total_egresados} egresos registrados en personas_caracterizacion, "
                f"equivalentes al {tasa_egreso:.1f}% de la población total registrada en habitante_de_calle."
            )
        ]

        for columna, nombre_variable in [
            (col_educacion, "nivel educativo"),
            (col_salud, "seguridad social en salud"),
            (col_ocupacion, "condición ocupacional"),
            (col_consumo, "tipo de consumo")
        ]:
            serie = _serie_limpia(df_f, columna)
            if not serie.empty:
                conteo = serie.value_counts()
                principal = conteo.index[0]
                porcentaje = round(
                    conteo.iloc[0] / len(serie) * 100, 1
                )
                conclusiones.append(
                    f"En {nombre_variable}, la categoría predominante es "
                    f"“{principal}”, con {porcentaje}% de los registros con información."
                )

        st.info("\n\n".join([f"• {c}" for c in conclusiones]))

        # --------------------------------------------------------
        # EXPORTACIONES
        # --------------------------------------------------------
        st.markdown("---")
        st.subheader("📥 Exportar resultados")

        ex1, ex2 = st.columns(2)

        with ex1:
            csv_bytes = df_f.to_csv(
                index=False
            ).encode("utf-8-sig")

            st.download_button(
                "⬇️ Descargar base filtrada (CSV)",
                data=csv_bytes,
                file_name=(
                    "reporte_observatorio_"
                    + datetime.now().strftime("%Y%m%d")
                    + ".csv"
                ),
                mime="text/csv",
                use_container_width=True
            )

        with ex2:
            if st.button(
                "📄 Generar informe institucional completo",
                use_container_width=True,
                key="generar_pdf_reportes"
            ):
                try:
                    import textwrap
                    from reportlab.lib.enums import TA_LEFT, TA_CENTER
                    from reportlab.platypus import KeepTogether

                    buffer_pdf = BytesIO()

                    doc_pdf = SimpleDocTemplate(
                        buffer_pdf,
                        pagesize=letter,
                        rightMargin=1.35 * cm,
                        leftMargin=1.35 * cm,
                        topMargin=1.25 * cm,
                        bottomMargin=1.25 * cm,
                        title="Informe Institucional - Observatorio Social",
                        author="Asociación Ciudad Futuro"
                    )

                    estilos = getSampleStyleSheet()

                    estilo_portada = ParagraphStyle(
                        "Portada",
                        parent=estilos["Title"],
                        alignment=TA_CENTER,
                        fontName="Helvetica-Bold",
                        fontSize=22,
                        leading=27,
                        textColor=colors.HexColor("#17365D"),
                        spaceAfter=12
                    )

                    estilo_subportada = ParagraphStyle(
                        "SubPortada",
                        parent=estilos["Heading2"],
                        alignment=TA_CENTER,
                        fontName="Helvetica-Bold",
                        fontSize=13,
                        leading=17,
                        textColor=colors.HexColor("#44546A"),
                        spaceAfter=8
                    )

                    estilo_h1 = ParagraphStyle(
                        "H1Reporte",
                        parent=estilos["Heading1"],
                        fontName="Helvetica-Bold",
                        fontSize=15,
                        leading=18,
                        textColor=colors.HexColor("#17365D"),
                        spaceBefore=8,
                        spaceAfter=8
                    )

                    estilo_h2 = ParagraphStyle(
                        "H2Reporte",
                        parent=estilos["Heading2"],
                        fontName="Helvetica-Bold",
                        fontSize=11.5,
                        leading=14,
                        textColor=colors.HexColor("#1F4E78"),
                        spaceBefore=8,
                        spaceAfter=6
                    )

                    estilo_cuerpo = ParagraphStyle(
                        "CuerpoReporte",
                        parent=estilos["BodyText"],
                        fontName="Helvetica",
                        fontSize=9,
                        leading=12.5,
                        textColor=colors.HexColor("#333333"),
                        spaceAfter=6
                    )

                    estilo_nota = ParagraphStyle(
                        "NotaReporte",
                        parent=estilos["BodyText"],
                        fontName="Helvetica-Oblique",
                        fontSize=8,
                        leading=10.5,
                        textColor=colors.HexColor("#666666"),
                        spaceAfter=5
                    )

                    estilo_destacado = ParagraphStyle(
                        "DestacadoReporte",
                        parent=estilos["BodyText"],
                        fontName="Helvetica-Bold",
                        fontSize=9.5,
                        leading=12.5,
                        textColor=colors.HexColor("#17365D"),
                        spaceAfter=6
                    )

                    contenido = []
                    temporales = []

                    # ------------------------------------------------
                    # FUNCIONES PARA EL PDF
                    # ------------------------------------------------
                    def _fmt_num(valor):
                        try:
                            return f"{int(valor):,}".replace(",", ".")
                        except Exception:
                            return str(valor)

                    def _guardar_fig_mpl(fig):
                        tmp = tempfile.NamedTemporaryFile(
                            delete=False,
                            suffix=".png"
                        )
                        tmp.close()
                        fig.savefig(
                            tmp.name,
                            dpi=170,
                            bbox_inches="tight"
                        )
                        plt.close(fig)
                        temporales.append(tmp.name)
                        return tmp.name

                    def _tabla_pdf(datos, anchos=None, fontsize=8.5):
                        tabla = Table(
                            datos,
                            colWidths=anchos,
                            repeatRows=1
                        )
                        tabla.setStyle(TableStyle([
                            (
                                "BACKGROUND", (0, 0), (-1, 0),
                                colors.HexColor("#17365D")
                            ),
                            (
                                "TEXTCOLOR", (0, 0), (-1, 0),
                                colors.white
                            ),
                            (
                                "FONTNAME", (0, 0), (-1, 0),
                                "Helvetica-Bold"
                            ),
                            (
                                "GRID", (0, 0), (-1, -1),
                                0.35, colors.HexColor("#B7C9DD")
                            ),
                            (
                                "ROWBACKGROUNDS", (0, 1), (-1, -1),
                                [
                                    colors.white,
                                    colors.HexColor("#F5F7FA")
                                ]
                            ),
                            (
                                "VALIGN", (0, 0), (-1, -1),
                                "MIDDLE"
                            ),
                            (
                                "FONTSIZE", (0, 0), (-1, -1),
                                fontsize
                            ),
                            (
                                "TOPPADDING", (0, 0), (-1, -1),
                                5
                            ),
                            (
                                "BOTTOMPADDING", (0, 0), (-1, -1),
                                5
                            )
                        ]))
                        return tabla

                    def _interpretacion_categoria(
                        dataframe,
                        columna,
                        nombre_variable
                    ):
                        serie = _serie_limpia(dataframe, columna)
                        if serie.empty:
                            return (
                                f"No se dispone de información suficiente "
                                f"para analizar {nombre_variable.lower()}."
                            )

                        conteo = serie.value_counts()
                        categoria = str(conteo.index[0])
                        cantidad = int(conteo.iloc[0])
                        porcentaje = round(
                            cantidad / len(serie) * 100,
                            1
                        )

                        return (
                            f"La categoría con mayor frecuencia en "
                            f"{nombre_variable.lower()} es "
                            f"<b>{_texto_pdf(categoria)}</b>, con "
                            f"<b>{cantidad}</b> registros "
                            f"({porcentaje}% de los registros con dato)."
                        )

                    def _agregar_barras_categoria(
                        titulo_seccion,
                        dataframe,
                        columna,
                        numero_seccion,
                        top_n=10
                    ):
                        tabla_cat = _tabla_categoria(
                            dataframe,
                            columna,
                            top_n
                        )

                        if tabla_cat.empty:
                            return False

                        contenido.append(PageBreak())
                        contenido.append(
                            Paragraph(
                                f"{numero_seccion}. {_texto_pdf(titulo_seccion)}",
                                estilo_h1
                            )
                        )

                        graf = tabla_cat.sort_values("cantidad").copy()
                        graf["categoria_corta"] = graf["categoria"].astype(
                            str
                        ).apply(
                            lambda x: "\n".join(
                                textwrap.wrap(x, width=30)
                            )
                        )

                        fig, ax = plt.subplots(figsize=(8.2, 4.8))
                        ax.barh(
                            graf["categoria_corta"],
                            graf["cantidad"]
                        )
                        ax.set_title(titulo_seccion)
                        ax.set_xlabel("Número de personas")
                        ax.set_ylabel("")
                        ax.grid(
                            axis="x",
                            alpha=0.18
                        )

                        for i, valor in enumerate(graf["cantidad"]):
                            ax.text(
                                valor,
                                i,
                                f" {int(valor)}",
                                va="center",
                                fontsize=8
                            )

                        ruta = _guardar_fig_mpl(fig)
                        contenido.append(
                            Image(
                                ruta,
                                width=17 * cm,
                                height=9.5 * cm
                            )
                        )
                        contenido.append(Spacer(1, 5))

                        contenido.append(
                            Paragraph(
                                _interpretacion_categoria(
                                    dataframe,
                                    columna,
                                    titulo_seccion
                                ),
                                estilo_cuerpo
                            )
                        )

                        datos = [[
                            "Categoría",
                            "Cantidad",
                            "%"
                        ]]

                        for _, fila in tabla_cat.head(8).iterrows():
                            datos.append([
                                Paragraph(
                                    _texto_pdf(fila["categoria"]),
                                    estilo_cuerpo
                                ),
                                str(int(fila["cantidad"])),
                                f'{float(fila["porcentaje"]):.1f}%'
                            ])

                        contenido.append(
                            _tabla_pdf(
                                datos,
                                anchos=[
                                    11.3 * cm,
                                    2.7 * cm,
                                    2.5 * cm
                                ],
                                fontsize=8
                            )
                        )
                        return True

                    # ------------------------------------------------
                    # PORTADA
                    # ------------------------------------------------
                    contenido.append(Spacer(1, 1.6 * cm))
                    contenido.append(
                        Paragraph(
                            "OBSERVATORIO SOCIAL",
                            estilo_portada
                        )
                    )
                    contenido.append(
                        Paragraph(
                            "Habitante de Calle - Pereira 2026",
                            estilo_subportada
                        )
                    )
                    contenido.append(Spacer(1, 0.45 * cm))
                    contenido.append(
                        Paragraph(
                            "INFORME INSTITUCIONAL DE CARACTERIZACIÓN, "
                            "SEGUIMIENTO E IMPACTO",
                            estilo_portada
                        )
                    )
                    contenido.append(Spacer(1, 0.8 * cm))

                    portada_datos = [
                        ["Entidad / Operador", "Asociación Ciudad Futuro"],
                        [
                            "Fecha de generación",
                            datetime.now().strftime("%d/%m/%Y %H:%M")
                        ],
                        [
                            "Base general",
                            "habitante_de_calle"
                        ],
                        [
                            "Base de egresos",
                            "personas_caracterizacion"
                        ],
                        [
                            "Población caracterizada",
                            _fmt_num(total_base_general)
                        ],
                        [
                            "Registros incluidos en el análisis",
                            _fmt_num(total)
                        ]
                    ]

                    contenido.append(
                        _tabla_pdf(
                            portada_datos,
                            anchos=[6.3 * cm, 10.2 * cm],
                            fontsize=9
                        )
                    )

                    if filtros_texto:
                        contenido.append(Spacer(1, 0.5 * cm))
                        contenido.append(
                            Paragraph(
                                "<b>Filtros aplicados:</b> "
                                + _texto_pdf(
                                    " | ".join(filtros_texto)
                                ),
                                estilo_cuerpo
                            )
                        )
                    else:
                        contenido.append(Spacer(1, 0.5 * cm))
                        contenido.append(
                            Paragraph(
                                "<b>Alcance:</b> informe generado sin "
                                "filtros adicionales sobre la base general.",
                                estilo_cuerpo
                            )
                        )

                    contenido.append(Spacer(1, 0.8 * cm))
                    contenido.append(
                        Paragraph(
                            "Documento generado automáticamente a partir "
                            "de la información disponible en el sistema. "
                            "Los resultados deben interpretarse conforme "
                            "a la calidad y actualización de los registros.",
                            estilo_nota
                        )
                    )

                    # ------------------------------------------------
                    # 1. RESUMEN EJECUTIVO
                    # ------------------------------------------------
                    contenido.append(PageBreak())
                    contenido.append(
                        Paragraph(
                            "1. Resumen ejecutivo",
                            estilo_h1
                        )
                    )

                    contenido.append(
                        Paragraph(
                            (
                                f"El Observatorio Social registra "
                                f"<b>{_fmt_num(total_base_general)}</b> "
                                f"personas en la base general "
                                f"<b>habitante_de_calle</b>. "
                                f"El presente análisis incluye "
                                f"<b>{_fmt_num(total)}</b> registros "
                                f"de acuerdo con los filtros seleccionados."
                            ),
                            estilo_cuerpo
                        )
                    )

                    contenido.append(
                        Paragraph(
                            (
                                f"De manera complementaria, la base "
                                f"<b>personas_caracterizacion</b> registra "
                                f"<b>{_fmt_num(total_egresados)}</b> egresos. "
                                f"Como indicador institucional de referencia, "
                                f"estos egresos equivalen al "
                                f"<b>{tasa_egreso:.1f}%</b> de la población "
                                f"registrada en la base general."
                            ),
                            estilo_cuerpo
                        )
                    )

                    if edad_promedio:
                        contenido.append(
                            Paragraph(
                                (
                                    f"La edad promedio del universo analizado "
                                    f"es de <b>{edad_promedio:.1f} años</b> "
                                    f"y la mediana es de "
                                    f"<b>{edad_mediana:.1f} años</b>."
                                ),
                                estilo_cuerpo
                            )
                        )

                    resumen_kpis = [
                        ["Indicador", "Resultado"],
                        [
                            "Población caracterizada",
                            _fmt_num(total_base_general)
                        ],
                        [
                            "Registros según filtros",
                            _fmt_num(total)
                        ],
                        [
                            "Activos en universo filtrado",
                            _fmt_num(total_activos)
                        ],
                        [
                            "Egresos registrados",
                            _fmt_num(total_egresados)
                        ],
                        [
                            "Tasa institucional de egreso",
                            f"{tasa_egreso:.1f}%"
                        ],
                        [
                            "Edad promedio",
                            (
                                f"{edad_promedio:.1f} años"
                                if edad_promedio else "Sin dato"
                            )
                        ],
                        [
                            "Urbano activos",
                            _fmt_num(urbano_activos)
                        ],
                        [
                            "Granja activos",
                            _fmt_num(granja_activos)
                        ]
                    ]

                    contenido.append(Spacer(1, 8))
                    contenido.append(
                        _tabla_pdf(
                            resumen_kpis,
                            anchos=[10.5 * cm, 6 * cm],
                            fontsize=9
                        )
                    )

                    # ------------------------------------------------
                    # 2. PERFIL POR EDAD Y SEXO
                    # ------------------------------------------------
                    contenido.append(PageBreak())
                    contenido.append(
                        Paragraph(
                            "2. Perfil sociodemográfico",
                            estilo_h1
                        )
                    )

                    # EDAD
                    if col_edad and df_f[col_edad].notna().any():
                        edades = df_f[col_edad].dropna()

                        fig, ax = plt.subplots(figsize=(8.2, 4.4))
                        ax.hist(
                            edades,
                            bins=18
                        )
                        ax.axvline(
                            edad_promedio,
                            linestyle="--",
                            linewidth=1.5,
                            label=f"Promedio: {edad_promedio:.1f}"
                        )
                        ax.set_title("Distribución de edad")
                        ax.set_xlabel("Edad")
                        ax.set_ylabel("Personas")
                        ax.legend()
                        ax.grid(
                            axis="y",
                            alpha=0.18
                        )

                        ruta = _guardar_fig_mpl(fig)

                        contenido.append(
                            Paragraph(
                                "2.1 Distribución por edad",
                                estilo_h2
                            )
                        )
                        contenido.append(
                            Image(
                                ruta,
                                width=17 * cm,
                                height=9.2 * cm
                            )
                        )

                        menores_29 = int((edades <= 28).sum())
                        adultos = int(
                            ((edades >= 29) & (edades <= 59)).sum()
                        )
                        mayores = int((edades >= 60).sum())

                        contenido.append(
                            Paragraph(
                                (
                                    f"En el universo analizado se identifican "
                                    f"<b>{menores_29}</b> personas de 28 años "
                                    f"o menos, <b>{adultos}</b> entre 29 y 59 "
                                    f"años y <b>{mayores}</b> de 60 años o más. "
                                    f"La edad promedio es "
                                    f"<b>{edad_promedio:.1f} años</b>."
                                ),
                                estilo_cuerpo
                            )
                        )

                    # SEXO
                    if not sexo_tabla.empty:
                        contenido.append(
                            Paragraph(
                                "2.2 Sexo al nacer",
                                estilo_h2
                            )
                        )

                        fig, ax = plt.subplots(figsize=(7.2, 4.4))
                        ax.pie(
                            sexo_tabla["cantidad"],
                            labels=sexo_tabla["categoria"],
                            autopct="%1.1f%%",
                            startangle=90
                        )
                        ax.set_title("Distribución por sexo al nacer")
                        ax.axis("equal")

                        ruta = _guardar_fig_mpl(fig)
                        contenido.append(
                            Image(
                                ruta,
                                width=14.5 * cm,
                                height=8.8 * cm
                            )
                        )
                        contenido.append(
                            Paragraph(
                                _interpretacion_categoria(
                                    df_f,
                                    col_sexo,
                                    "Sexo al nacer"
                                ),
                                estilo_cuerpo
                            )
                        )

                    # ------------------------------------------------
                    # 3-8. CARACTERIZACIÓN SOCIAL
                    # ------------------------------------------------
                    seccion = 3

                    bloques = [
                        (
                            "Nivel educativo",
                            col_educacion,
                            12
                        ),
                        (
                            "Seguridad social en salud",
                            col_salud,
                            12
                        ),
                        (
                            "Condición ocupacional",
                            col_ocupacion,
                            12
                        ),
                        (
                            "Departamento de procedencia",
                            col_procedencia,
                            10
                        ),
                        (
                            "Tipo de consumo",
                            col_consumo,
                            12
                        ),
                        (
                            "Orientación sexual / diversidad",
                            col_orientacion,
                            10
                        ),
                        (
                            "Grupos étnicos",
                            col_etnia,
                            10
                        ),
                        (
                            "Enfermedad mental - variable registrada",
                            col_enfermedad,
                            8
                        )
                    ]

                    for titulo_bloque, columna_bloque, top_bloque in bloques:
                        if columna_bloque:
                            agregado = _agregar_barras_categoria(
                                titulo_bloque,
                                df_f,
                                columna_bloque,
                                seccion,
                                top_bloque
                            )
                            if agregado:
                                seccion += 1

                    # ------------------------------------------------
                    # ESTADO Y MODALIDAD
                    # ------------------------------------------------
                    if col_estado or col_modalidad:
                        contenido.append(PageBreak())
                        contenido.append(
                            Paragraph(
                                f"{seccion}. Seguimiento institucional",
                                estilo_h1
                            )
                        )

                        if col_estado:
                            tabla_estado = _tabla_categoria(
                                df_f,
                                col_estado,
                                10
                            )
                            if not tabla_estado.empty:
                                contenido.append(
                                    Paragraph(
                                        "Estado del caso",
                                        estilo_h2
                                    )
                                )
                                fig, ax = plt.subplots(
                                    figsize=(7.8, 4.1)
                                )
                                ax.bar(
                                    tabla_estado["categoria"],
                                    tabla_estado["cantidad"]
                                )
                                ax.set_title("Estado del caso")
                                ax.set_ylabel("Personas")
                                ax.tick_params(
                                    axis="x",
                                    rotation=25
                                )
                                ax.grid(
                                    axis="y",
                                    alpha=0.18
                                )
                                ruta = _guardar_fig_mpl(fig)
                                contenido.append(
                                    Image(
                                        ruta,
                                        width=16.5 * cm,
                                        height=8.5 * cm
                                    )
                                )

                        if col_modalidad:
                            tabla_modalidad = _tabla_categoria(
                                df_f,
                                col_modalidad,
                                10
                            )
                            if not tabla_modalidad.empty:
                                contenido.append(
                                    Paragraph(
                                        "Modalidad de atención",
                                        estilo_h2
                                    )
                                )
                                fig, ax = plt.subplots(
                                    figsize=(7.8, 4.1)
                                )
                                ax.bar(
                                    tabla_modalidad["categoria"],
                                    tabla_modalidad["cantidad"]
                                )
                                ax.set_title("Modalidad de atención")
                                ax.set_ylabel("Personas")
                                ax.grid(
                                    axis="y",
                                    alpha=0.18
                                )
                                ruta = _guardar_fig_mpl(fig)
                                contenido.append(
                                    Image(
                                        ruta,
                                        width=16.5 * cm,
                                        height=8.5 * cm
                                    )
                                )

                        contenido.append(
                            Paragraph(
                                (
                                    f"En el universo filtrado se encuentran "
                                    f"<b>{total_activos}</b> registros con "
                                    f"estado ACTIVO. Dentro de las modalidades "
                                    f"registradas se contabilizan "
                                    f"<b>{urbano_activos}</b> activos en Urbano "
                                    f"y <b>{granja_activos}</b> activos en Granja."
                                ),
                                estilo_cuerpo
                            )
                        )

                        seccion += 1

                    # ------------------------------------------------
                    # CALIDAD DE LA INFORMACIÓN
                    # ------------------------------------------------
                    if not df_calidad.empty:
                        contenido.append(PageBreak())
                        contenido.append(
                            Paragraph(
                                f"{seccion}. Calidad y completitud de la información",
                                estilo_h1
                            )
                        )

                        calidad_plot = df_calidad.sort_values(
                            "Completitud %"
                        ).copy()

                        fig, ax = plt.subplots(figsize=(8.2, 4.8))
                        ax.barh(
                            calidad_plot["Campo"],
                            calidad_plot["Completitud %"]
                        )
                        ax.set_xlim(0, 100)
                        ax.set_xlabel("Completitud (%)")
                        ax.set_title(
                            "Completitud de variables clave"
                        )
                        ax.grid(
                            axis="x",
                            alpha=0.18
                        )

                        for i, valor in enumerate(
                            calidad_plot["Completitud %"]
                        ):
                            ax.text(
                                valor,
                                i,
                                f" {valor:.1f}%",
                                va="center",
                                fontsize=8
                            )

                        ruta = _guardar_fig_mpl(fig)
                        contenido.append(
                            Image(
                                ruta,
                                width=17 * cm,
                                height=9.5 * cm
                            )
                        )

                        datos_calidad_pdf = [[
                            "Variable",
                            "Completos",
                            "Faltantes",
                            "%"
                        ]]

                        for _, r in df_calidad.iterrows():
                            datos_calidad_pdf.append([
                                r["Campo"],
                                str(int(r["Completos"])),
                                str(int(r["Faltantes"])),
                                f'{float(r["Completitud %"]):.1f}%'
                            ])

                        contenido.append(
                            _tabla_pdf(
                                datos_calidad_pdf,
                                anchos=[
                                    8 * cm,
                                    3 * cm,
                                    3 * cm,
                                    2.5 * cm
                                ],
                                fontsize=7.8
                            )
                        )

                        incompletas = df_calidad[
                            df_calidad["Completitud %"] < 80
                        ]

                        if not incompletas.empty:
                            lista_incompletas = ", ".join(
                                [
                                    f"{r['Campo']} "
                                    f"({float(r['Completitud %']):.1f}%)"
                                    for _, r in incompletas.iterrows()
                                ]
                            )
                            contenido.append(
                                Paragraph(
                                    (
                                        "Las variables con completitud inferior "
                                        "al 80% son: "
                                        f"<b>{_texto_pdf(lista_incompletas)}</b>. "
                                        "Se recomienda priorizar su actualización "
                                        "para fortalecer la lectura de resultados."
                                    ),
                                    estilo_cuerpo
                                )
                            )

                        seccion += 1

                    # ------------------------------------------------
                    # HALLAZGOS Y CONCLUSIONES
                    # ------------------------------------------------
                    contenido.append(PageBreak())
                    contenido.append(
                        Paragraph(
                            f"{seccion}. Hallazgos principales",
                            estilo_h1
                        )
                    )

                    hallazgos_pdf = []

                    if edad_promedio:
                        hallazgos_pdf.append(
                            f"La población analizada presenta una edad "
                            f"promedio de {edad_promedio:.1f} años."
                        )

                    for columna, nombre_variable in [
                        (col_sexo, "sexo al nacer"),
                        (col_educacion, "nivel educativo"),
                        (col_salud, "seguridad social en salud"),
                        (col_ocupacion, "condición ocupacional"),
                        (col_procedencia, "procedencia"),
                        (col_consumo, "tipo de consumo"),
                        (col_etnia, "grupo étnico")
                    ]:
                        serie = _serie_limpia(df_f, columna)
                        if not serie.empty:
                            conteo = serie.value_counts()
                            cat = str(conteo.index[0])
                            cant = int(conteo.iloc[0])
                            pct = round(
                                cant / len(serie) * 100,
                                1
                            )
                            hallazgos_pdf.append(
                                f"En {nombre_variable}, la categoría "
                                f"predominante es {cat}, con {cant} registros "
                                f"({pct}% de los registros con información)."
                            )

                    hallazgos_pdf.append(
                        f"La base de egresos registra {total_egresados} "
                        f"egresos, equivalentes al {tasa_egreso:.1f}% "
                        f"de la población total registrada en la base general."
                    )

                    if not df_calidad.empty:
                        promedio_calidad = round(
                            float(
                                df_calidad["Completitud %"].mean()
                            ),
                            1
                        )
                        hallazgos_pdf.append(
                            f"La completitud promedio de las variables "
                            f"clave evaluadas es de {promedio_calidad}%."
                        )

                    for h in hallazgos_pdf:
                        contenido.append(
                            Paragraph(
                                "• " + _texto_pdf(h),
                                estilo_cuerpo
                            )
                        )

                    contenido.append(
                        Paragraph(
                            f"{seccion + 1}. Conclusiones institucionales",
                            estilo_h1
                        )
                    )

                    conclusiones_pdf = [
                        (
                            f"El sistema consolida una base general de "
                            f"{_fmt_num(total_base_general)} personas, "
                            "permitiendo analizar características "
                            "sociodemográficas, sociales y de seguimiento."
                        ),
                        (
                            f"El análisis actual comprende "
                            f"{_fmt_num(total)} registros según los filtros "
                            "seleccionados, por lo que los resultados de "
                            "caracterización deben leerse sobre ese universo."
                        ),
                        (
                            f"La información de egresos se administra en una "
                            f"base diferenciada, personas_caracterizacion, "
                            f"en la cual se identifican "
                            f"{_fmt_num(total_egresados)} egresos."
                        ),
                        (
                            "Las distribuciones presentadas permiten orientar "
                            "la planeación de acciones de salud, inclusión "
                            "social, educación, reducción de riesgos, "
                            "acompañamiento psicosocial y seguimiento a "
                            "trayectorias de superación de vida en calle."
                        ),
                        (
                            "La calidad del dato debe mantenerse como un "
                            "componente transversal del Observatorio, dado "
                            "que las variables incompletas limitan la "
                            "interpretación de los indicadores."
                        )
                    ]

                    for c in conclusiones_pdf:
                        contenido.append(
                            Paragraph(
                                "• " + _texto_pdf(c),
                                estilo_cuerpo
                            )
                        )

                    # ------------------------------------------------
                    # METODOLOGÍA Y FUENTES
                    # ------------------------------------------------
                    contenido.append(PageBreak())
                    contenido.append(
                        Paragraph(
                            f"{seccion + 2}. Nota metodológica y fuentes",
                            estilo_h1
                        )
                    )

                    metodologia = [
                        (
                            "<b>Fuente principal:</b> tabla "
                            "<i>habitante_de_calle</i>, utilizada para "
                            "caracterización general, filtros, estado, "
                            "modalidad y variables sociodemográficas."
                        ),
                        (
                            "<b>Fuente de egresos:</b> tabla "
                            "<i>personas_caracterizacion</i>, utilizada "
                            "para contabilizar los egresos registrados."
                        ),
                        (
                            "<b>Universo:</b> la población caracterizada "
                            "corresponde al total de registros disponibles "
                            "en la base general al momento de generar el "
                            "informe."
                        ),
                        (
                            "<b>Filtros:</b> cuando el usuario selecciona "
                            "sexo, estado, modalidad, salud, rango de edad "
                            "o búsqueda individual, las gráficas de "
                            "caracterización se recalculan sobre el "
                            "subconjunto resultante."
                        ),
                        (
                            "<b>Tasa institucional de egreso:</b> se presenta "
                            "como relación de referencia entre los egresos "
                            "registrados en personas_caracterizacion y la "
                            "población total de habitante_de_calle."
                        ),
                        (
                            "<b>Limitación:</b> este indicador no debe "
                            "interpretarse como una tasa longitudinal de "
                            "cohorte mientras las dos bases no estén "
                            "relacionadas mediante una metodología única de "
                            "seguimiento temporal y personas únicas."
                        )
                    ]

                    for m in metodologia:
                        contenido.append(
                            Paragraph(
                                m,
                                estilo_cuerpo
                            )
                        )

                    contenido.append(Spacer(1, 0.6 * cm))
                    contenido.append(
                        Paragraph(
                            "Fin del informe.",
                            estilo_destacado
                        )
                    )

                    # ------------------------------------------------
                    # CREAR DOCUMENTO
                    # ------------------------------------------------
                    doc_pdf.build(contenido)
                    buffer_pdf.seek(0)

                    st.session_state[
                        "pdf_reporte_institucional"
                    ] = buffer_pdf.getvalue()

                    for archivo_tmp in temporales:
                        try:
                            os.remove(archivo_tmp)
                        except Exception:
                            pass

                    st.success(
                        "✅ Informe institucional completo generado."
                    )

                except Exception as e:
                    st.error(
                        f"Error generando el informe: {e}"
                    )

            if st.session_state.get(
                "pdf_reporte_institucional"
            ):
                st.download_button(
                    "⬇️ Descargar informe institucional PDF",
                    data=st.session_state[
                        "pdf_reporte_institucional"
                    ],
                    file_name=(
                        "Informe_Institucional_Observatorio_Social_"
                        + datetime.now().strftime("%Y%m%d_%H%M")
                        + ".pdf"
                    ),
                    mime="application/pdf",
                    use_container_width=True,
                    key="descargar_pdf_reportes"
                )

        # --------------------------------------------------------
        # VISTA DE REGISTROS
        # --------------------------------------------------------
        with st.expander("👁️ Ver registros incluidos en el reporte"):
            columnas_vista = [
                c for c in [
                    col_doc,
                    "nombres",
                    "apellidos",
                    col_edad,
                    col_sexo,
                    col_estado,
                    col_modalidad,
                    col_salud,
                    col_educacion,
                    col_ocupacion
                ]
                if c and c in df_f.columns
            ]

            st.dataframe(
                df_f[columnas_vista] if columnas_vista else df_f,
                use_container_width=True,
                hide_index=True
            )

with tab5:

        st.subheader("🔐 Acceso al formulario")

        clave = st.text_input(
            "Ingrese la contraseña",
            type="password",
            key="clave_registro"
        )

        clave_formulario = st.secrets.get("FORM_PASSWORD", "Pereira2026")

        if clave == clave_formulario:

            st.success("✅ Acceso autorizado")

            with st.form("registro_social"):

                st.markdown("### Datos personales")

                nombres = st.text_input("Nombres")
                apellidos = st.text_input("Apellidos")

                sexo = st.selectbox(
                    "Sexo al nacer",
                    ["Masculino", "Femenino"]
                )

                edad = st.number_input(
                    "Edad",
                    min_value=0,
                    max_value=120,
                    value=18
                )

                tipo_id = st.selectbox(
                    "Tipo ID",
                    ["CC", "TI", "CE", "PEP", "Otro"]
                )

                numero_id = st.text_input("Número de identificación")

                etnia = st.selectbox(
                    "Grupo étnico",
                    ["Ninguno", "Afrodescendiente", "Indígena", "Mestizo"]
                )

                discapacidad = st.selectbox(
                    "Discapacidad",
                    ["No", "Sí"]
                )

                migracion_txt = st.selectbox(
                    "Migración",
                    ["NO", "SI"]
                )

                migracion = 1 if migracion_txt == "SI" else 0

                educacion = st.selectbox(
                    "Nivel educativo",
                    ["Ninguno", "Primaria", "Secundaria", "Técnico", "Tecnólogo", "Universitario"]
                )

                barrio = st.text_input("Barrio")
                comuna = st.text_input("Comuna")
                telefono = st.text_input("Teléfono")

                consumo = st.selectbox(
                    "Consumo",
                    ["No", "Marihuana", "Cocaína", "Bazuco", "Alcohol", "Heroína", "Policonsumo"]
                )

                enfermedad_mental = st.selectbox(
                    "Enfermedad mental",
                    ["No", "Sí"]
                )

                modalidad = st.selectbox(
                    "Modalidad",
                    ["GRANJA", "URBANO"]
                )

                estado_caso = "ACTIVO"

                guardar = st.form_submit_button("💾 Guardar registro")

            # =========================
            # 🔥 INSERT CORREGIDO
            # =========================
            if guardar:

                sql = text("""
                    INSERT INTO habitante_de_calle
                    (
                        nombres,
                        apellidos,
                        sexo_al_nacer,
                        edad,
                        tipo_de_identificacion,
                        numero_identificacion,
                        grupos_etnicos_afro_indigena,
                        personas_con_discapacidad,
                        indicador_migracion,
                        nivel_educativo_que_tiene_o_cursa,
                        barrio_o_vereda_de_residencia,
                        comuna_o_corregimiento_de_residencia,
                        telefono_y_o_celular,
                        tipo_de_consumo,
                        enfermedad_mental,
                        estado_caso,
                        modalidad
                    )
                    VALUES
                    (
                        :nombres,
                        :apellidos,
                        :sexo,
                        :edad,
                        :tipo_id,
                        :numero_id,
                        :etnia,
                        :discapacidad,
                        :migracion,
                        :educacion,
                        :barrio,
                        :comuna,
                        :telefono,
                        :consumo,
                        :enfermedad_mental,
                        :estado_caso,
                        :modalidad
                    )
                """)

                try:
                    with engine.begin() as conn:
                        conn.execute(sql, {
                            "nombres": nombres,
                            "apellidos": apellidos,
                            "sexo": sexo,
                            "edad": edad,
                            "tipo_id": tipo_id,
                            "numero_id": numero_id,
                            "etnia": etnia,
                            "discapacidad": discapacidad,
                            "migracion": migracion,
                            "educacion": educacion,
                            "barrio": barrio,
                            "comuna": comuna,
                            "telefono": telefono,
                            "consumo": consumo,
                            "enfermedad_mental": enfermedad_mental,
                            "estado_caso": estado_caso,
                            "modalidad": modalidad
                        })

                    st.success("✅ Registro guardado correctamente")

                except Exception as e:
                    st.error(f"Error al guardar: {e}")

        else:
            st.info("Ingrese la contraseña para habilitar el formulario.")

# =====================================
# 🌍 MOTOR DE SCORING ODS - PAI
# =====================================

# 🏥 ODS 3 - SALUD
def score_salud(consumo, vih, salud_mental):

    score = 0

    # Consumo de sustancias
    if consumo == "Abstinencia":
        score += 2
    elif consumo == "Reducido":
        score += 1
    else:
        score += 0

    # VIH
    if vih == "Indetectable":
        score += 2
    elif vih == "Positivo":
        score += 1
    else:
        score += 0

    # Salud mental
    if salud_mental == "Estable":
        score += 2
    elif salud_mental == "En tratamiento":
        score += 1
    else:
        score += 0

    return round(score / 6, 2)


# 💼 ODS 8 - EMPLEO E INGRESOS
def score_empleo(empleo):

    if empleo == "Formal":
        return 1.0
    elif empleo == "Informal":
        return 0.5
    else:
        return 0.0


# 🤝 ODS 10 - INCLUSIÓN SOCIAL
def score_inclusion(red_apoyo):

    if red_apoyo == "Fuerte":
        return 1.0
    elif red_apoyo == "Débil":
        return 0.5
    else:
        return 0.0


# 📄 ODS 16 - DERECHOS BÁSICOS
def score_derechos(documento, agua):

    score = 0

    # Documento de identidad
    if documento == "Tiene":
        score += 1

    # Agua potable
    if agua == "Sí":
        score += 1

    return round(score / 2, 2)


# 🌍 ÍNDICE GLOBAL ODS (0 - 100)
def calcular_indice_ods(salud, empleo, inclusion, derechos):

    total = salud + empleo + inclusion + derechos

    indice = (total / 4) * 100



mapa_politica = {
    "Documentación y ciudadanía":"Restablecimiento de derechos",
    "Cedulación":"Restablecimiento de derechos",
    "Aseguramiento en salud":"Atención integral en salud",
    "Salud mental":"Atención integral en salud",
    "Tratamiento consumo SPA":"Reducción de riesgos y daños",
    "Reducción de riesgos y daños":"Reducción de riesgos y daños",
    "Vinculación familiar":"Fortalecimiento familiar",
    "Inclusión social":"Inclusión social",
    "Empleabilidad":"Inclusión laboral y generación de ingresos",
    "Generación de ingresos":"Inclusión laboral y generación de ingresos",
    "Educación":"Educación",
    "Vivienda":"Habitabilidad y vivienda",
    "Proyecto de vida":"Inclusión social",
    "Participación comunitaria":"Participación ciudadana",
    "Justicia y acceso a derechos":"Restablecimiento de derechos",
    "Otro":"Restablecimiento de derechos"
}

mapa_ods = {
    "Documentación y ciudadanía":["ODS 16"],
    "Cedulación":["ODS 16"],
    "Aseguramiento en salud":["ODS 3","ODS 10"],
    "Salud mental":["ODS 3"],
    "Tratamiento consumo SPA":["ODS 3"],
    "Reducción de riesgos y daños":["ODS 3"],
    "Vinculación familiar":["ODS 10","ODS 16"],
    "Inclusión social":["ODS 10","ODS 16"],
    "Empleabilidad":["ODS 8","ODS 10"],
    "Generación de ingresos":["ODS 8","ODS 10"],
    "Educación":["ODS 4"],
    "Vivienda":["ODS 11"],
    "Proyecto de vida":["ODS 3","ODS 10"],
    "Participación comunitaria":["ODS 16"],
    "Justicia y acceso a derechos":["ODS 16"],
    "Otro":["ODS 10"]
}

mapa_hitos = {
    "Documentación y ciudadanía": [
        "Identificación de documentos",
        "Inicio de trámite",
        "Gestión institucional",
        "Documento entregado"
    ],

    "Salud mental": [
        "Valoración inicial",
        "Intervención psicológica",
        "Seguimiento clínico",
        "Estabilización"
    ],

    "Tratamiento consumo SPA": [
        "Motivación al cambio",
        "Ingreso a tratamiento",
        "Adherencia",
        "Prevención de recaídas"
    ],

    "Empleabilidad": [
        "Perfilamiento laboral",
        "Capacitación",
        "Búsqueda de empleo",
        "Vinculación laboral"
    ],

    "Vivienda": [
        "Diagnóstico habitacional",
        "Gestión de subsidio",
        "Asignación",
        "Seguimiento",
        "Estabilización"
    ],

    "Red de apoyo": [
        "Identificación de familiares",
        "Primer contacto",
        "Fortalecimiento de vínculos",
        "Seguimiento",
        "Red consolidada"
    ],

    "Educación": [
        "Diagnóstico educativo",
        "Gestión de matrícula",
        "Inicio de formación",
        "Seguimiento académico",
        "Permanencia"
    ],

    "Proyecto de vida": [
        "Identificación de intereses",
        "Definición de metas",
        "Construcción del plan",
        "Seguimiento",
        "Consolidación"
    ]
}
with tab6:

    st.title("📋 PAI y Seguimiento Profesional")
    st.caption("Gestión de objetivos, avances e intervenciones profesionales por usuario.")

    import json
    from sqlalchemy import text

    # =========================
    # PROFESIONALES (UNA VEZ)
    # =========================
    df_profesionales = pd.read_sql("""
        SELECT id, nombre, rol
        FROM profesionales
        ORDER BY nombre
    """, engine)

    df_profesionales["label"] = (
        df_profesionales["nombre"] + " (" + df_profesionales["rol"] + ")"
    )

    # ========================================================
    # TABLERO DE SUPERVISIÓN PAI
    # ========================================================
    st.subheader("🧭 Supervisión de cumplimiento PAI")
    st.caption(
        "Control automático de objetivos, vencimientos y seguimiento por profesional."
    )

    df_control_pai = pd.read_sql(
        text("""
            SELECT
                p.id,
                p.documento_usuario,
                p.objetivo_tipo,
                p.objetivo_descripcion,
                p.porcentaje_avance,
                p.estado,
                p.fecha_apertura,
                p.fecha_meta,
                p.fecha_cumplimiento_real,
                p.fecha_ultimo_seguimiento,
                p.profesional_referente,
                pr.nombre AS profesional,
                pr.rol
            FROM pai_objetivos p
            LEFT JOIN profesionales pr
                ON pr.id = p.profesional_referente
            ORDER BY p.fecha_meta NULLS LAST, p.fecha_apertura DESC
        """),
        engine
    )

    if not df_control_pai.empty:
        hoy_control = pd.Timestamp(date.today())

        df_control_pai["fecha_meta"] = pd.to_datetime(
            df_control_pai["fecha_meta"], errors="coerce"
        )
        df_control_pai["fecha_apertura"] = pd.to_datetime(
            df_control_pai["fecha_apertura"], errors="coerce"
        )
        df_control_pai["fecha_cumplimiento_real"] = pd.to_datetime(
            df_control_pai["fecha_cumplimiento_real"], errors="coerce"
        )
        df_control_pai["fecha_ultimo_seguimiento"] = pd.to_datetime(
            df_control_pai["fecha_ultimo_seguimiento"], errors="coerce"
        )
        df_control_pai["porcentaje_avance"] = pd.to_numeric(
            df_control_pai["porcentaje_avance"], errors="coerce"
        ).fillna(0)

        def _estado_control_pai(row):
            avance = float(row.get("porcentaje_avance", 0) or 0)
            fecha_meta = row.get("fecha_meta")
            ultimo = row.get("fecha_ultimo_seguimiento")

            if avance >= 100 or str(row.get("estado", "")).strip().upper() == "CUMPLIDO":
                return "🟢 CUMPLIDO"

            if pd.isna(fecha_meta):
                return "⚪ SIN FECHA META"

            dias = (fecha_meta.normalize() - hoy_control).days

            if dias < 0:
                return "🔴 VENCIDO"

            if dias <= 7:
                return "🟡 PRÓXIMO A VENCER"

            if pd.isna(ultimo):
                return "⚫ SIN SEGUIMIENTO"

            dias_sin_seg = (hoy_control - ultimo.normalize()).days
            if dias_sin_seg > 15:
                return "🟠 SEGUIMIENTO ATRASADO"

            return "🔵 EN TÉRMINO"

        df_control_pai["semaforo"] = df_control_pai.apply(
            _estado_control_pai, axis=1
        )

        df_control_pai["dias_para_meta"] = (
            df_control_pai["fecha_meta"].dt.normalize() - hoy_control
        ).dt.days

        df_control_pai["dias_sin_seguimiento"] = (
            hoy_control - df_control_pai["fecha_ultimo_seguimiento"].dt.normalize()
        ).dt.days

        total_obj_control = len(df_control_pai)
        cumplidos_control = int(
            df_control_pai["semaforo"].eq("🟢 CUMPLIDO").sum()
        )
        vencidos_control = int(
            df_control_pai["semaforo"].eq("🔴 VENCIDO").sum()
        )
        proximos_control = int(
            df_control_pai["semaforo"].eq("🟡 PRÓXIMO A VENCER").sum()
        )
        sin_seg_control = int(
            df_control_pai["semaforo"].isin([
                "⚫ SIN SEGUIMIENTO",
                "🟠 SEGUIMIENTO ATRASADO"
            ]).sum()
        )

        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("🎯 Objetivos", total_obj_control)
        s2.metric("🟢 Cumplidos", cumplidos_control)
        s3.metric("🔴 Vencidos", vencidos_control)
        s4.metric("🟡 Vencen ≤ 7 días", proximos_control)
        s5.metric("⚠️ Sin seguimiento", sin_seg_control)

        st.markdown("#### 👨‍⚕️ Cumplimiento por profesional")

        resumen_prof = (
            df_control_pai.assign(
                cumplido=df_control_pai["semaforo"].eq("🟢 CUMPLIDO"),
                vencido=df_control_pai["semaforo"].eq("🔴 VENCIDO"),
                proximo=df_control_pai["semaforo"].eq("🟡 PRÓXIMO A VENCER"),
                sin_seguimiento=df_control_pai["semaforo"].isin([
                    "⚫ SIN SEGUIMIENTO",
                    "🟠 SEGUIMIENTO ATRASADO"
                ])
            )
            .groupby(["profesional", "rol"], dropna=False)
            .agg(
                objetivos=("id", "count"),
                cumplidos=("cumplido", "sum"),
                vencidos=("vencido", "sum"),
                proximos=("proximo", "sum"),
                sin_seguimiento=("sin_seguimiento", "sum")
            )
            .reset_index()
        )

        resumen_prof["profesional"] = resumen_prof["profesional"].fillna("Sin asignar")
        resumen_prof["rol"] = resumen_prof["rol"].fillna("Sin rol")
        resumen_prof["cumplimiento_%"] = (
            resumen_prof["cumplidos"] / resumen_prof["objetivos"] * 100
        ).round(1)

        st.dataframe(
            resumen_prof.rename(columns={
                "profesional": "Profesional",
                "rol": "Rol",
                "objetivos": "Objetivos",
                "cumplidos": "Cumplidos",
                "vencidos": "Vencidos",
                "proximos": "Próximos",
                "sin_seguimiento": "Sin seguimiento",
                "cumplimiento_%": "% cumplimiento"
            }),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("#### 🚨 Alertas de seguimiento")

        f1, f2 = st.columns(2)

        opciones_estado_control = [
            "Todos",
            "🔴 VENCIDO",
            "🟡 PRÓXIMO A VENCER",
            "🟠 SEGUIMIENTO ATRASADO",
            "⚫ SIN SEGUIMIENTO",
            "🔵 EN TÉRMINO",
            "🟢 CUMPLIDO",
            "⚪ SIN FECHA META"
        ]

        filtro_estado_control = f1.selectbox(
            "Estado de control",
            opciones_estado_control,
            key="pai_filtro_estado_control"
        )

        profesionales_control = (
            ["Todos"]
            + sorted(
                df_control_pai["profesional"]
                .fillna("Sin asignar")
                .astype(str)
                .unique()
                .tolist()
            )
        )

        filtro_prof_control = f2.selectbox(
            "Profesional",
            profesionales_control,
            key="pai_filtro_profesional_control"
        )

        df_alertas_pai = df_control_pai.copy()
        df_alertas_pai["profesional"] = (
            df_alertas_pai["profesional"].fillna("Sin asignar")
        )

        if filtro_estado_control != "Todos":
            df_alertas_pai = df_alertas_pai[
                df_alertas_pai["semaforo"] == filtro_estado_control
            ]

        if filtro_prof_control != "Todos":
            df_alertas_pai = df_alertas_pai[
                df_alertas_pai["profesional"] == filtro_prof_control
            ]

        columnas_alerta = [
            "semaforo",
            "documento_usuario",
            "objetivo_tipo",
            "profesional",
            "rol",
            "fecha_meta",
            "porcentaje_avance",
            "dias_para_meta",
            "fecha_ultimo_seguimiento",
            "dias_sin_seguimiento"
        ]

        st.dataframe(
            df_alertas_pai[columnas_alerta].rename(columns={
                "semaforo": "Estado",
                "documento_usuario": "Documento",
                "objetivo_tipo": "Objetivo",
                "profesional": "Profesional",
                "rol": "Rol",
                "fecha_meta": "Fecha meta",
                "porcentaje_avance": "Avance %",
                "dias_para_meta": "Días para meta",
                "fecha_ultimo_seguimiento": "Último seguimiento",
                "dias_sin_seguimiento": "Días sin seguimiento"
            }),
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "🔴 Vencido: fecha meta superada sin cumplimiento. "
            "🟡 Próximo: vence en 7 días o menos. "
            "🟠 Seguimiento atrasado: más de 15 días desde la última novedad. "
            "⚫ Sin seguimiento: no registra novedad profesional."
        )

        csv_control_pai = df_alertas_pai[columnas_alerta].to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "⬇️ Descargar control PAI en CSV",
            data=csv_control_pai,
            file_name=(
                "control_pai_"
                + datetime.now().strftime("%Y%m%d_%H%M")
                + ".csv"
            ),
            mime="text/csv",
            use_container_width=True,
            key="descargar_control_pai_v7"
        )
    else:
        st.info("Aún no existen objetivos PAI para supervisar.")

    st.divider()

    # =========================
    # BUSCAR USUARIO
    # =========================
    st.subheader("🔎 Buscar usuario")

    busqueda = st.text_input("Nombre, apellido o documento")

    df_pai_personas = pd.read_sql(
        text("""
            SELECT *
            FROM habitante_de_calle
            ORDER BY nombres, apellidos
        """),
        engine
    )

    df_busqueda = df_pai_personas.copy()

    if busqueda:
        df_busqueda = df_busqueda[
            df_busqueda["nombres"].astype(str).str.contains(busqueda, case=False, na=False)
            |
            df_busqueda["apellidos"].astype(str).str.contains(busqueda, case=False, na=False)
            |
            df_busqueda["numero_identificacion"].astype(str).str.contains(busqueda, na=False)
        ]

    usuario_sel = None

    if not df_busqueda.empty:

        usuario_sel = st.selectbox(
            "Seleccione usuario",
            df_busqueda["numero_identificacion"],
            format_func=lambda x:
                df_busqueda[df_busqueda["numero_identificacion"] == x][
                    ["nombres", "apellidos"]
                ]
                .astype(str)
                .agg(" ".join, axis=1)
                .values[0]
        )

    # =========================
    # CARGA USUARIO
    # =========================
    if usuario_sel:

        usuario = pd.read_sql(
            text("""
                SELECT *
                FROM habitante_de_calle
                WHERE numero_identificacion = :id
            """),
            engine,
            params={"id": usuario_sel}
        )

        datos = usuario.iloc[0]

        st.divider()

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Nombre", f"{datos['nombres']} {datos['apellidos']}")
        c2.metric("Documento", usuario_sel)
        c3.metric("Edad", datos.get("edad", "N/A"))

        count_obj = pd.read_sql(
            text("""
                SELECT COUNT(*) AS total
                FROM pai_objetivos
                WHERE documento_usuario = :id
            """),
            engine,
            params={"id": usuario_sel}
        ).iloc[0]["total"]

        c4.metric("Objetivos", count_obj)

        # =========================
        # OBJETIVOS
        # =========================
        objetivos = pd.read_sql(
            text("""
                SELECT p.*, pr.nombre AS nombre_profesional
                FROM pai_objetivos p
                LEFT JOIN profesionales pr
                    ON pr.id = p.profesional_referente
                WHERE p.documento_usuario = :id
                ORDER BY p.fecha_apertura DESC
            """),
            engine,
            params={"id": usuario_sel}
        )

        
        novedades_all = pd.read_sql("""
            SELECT *
            FROM pai_novedades
            ORDER BY fecha DESC
        """, engine)
        # =========================
        # CREAR OBJETIVO
        # =========================
        st.subheader("➕ Crear objetivo")

        objetivo_tipo = st.selectbox(
            "Tipo de objetivo",
            list(mapa_politica.keys()),
            key="nuevo_objetivo"
        )

        linea_politica = mapa_politica[objetivo_tipo]
        ods = mapa_ods.get(objetivo_tipo, [])
        actividades = mapa_hitos.get(objetivo_tipo, [])

        st.write(f"**Línea de política:** {linea_politica}")
        st.write(f"**ODS:** {', '.join(ods)}")

        st.write("**Actividades que tendrá este objetivo:**")

        for act in actividades:
            st.checkbox(
                act,
                value=True,
                disabled=True,
                key=f"preview_{act}"
            )

        descripcion_objetivo = st.text_area(
            "Descripción del objetivo",
            key="descripcion_objetivo"
        )
        fecha_cumplimiento = st.date_input(
        "📅 Fecha estimada de cumplimiento",
        value=date.today() + timedelta(days=90)
    )
        profesional_referente = st.selectbox(
            "Profesional referente",
            df_profesionales["id"],
            format_func=lambda x:
                df_profesionales.loc[
                    df_profesionales["id"] == x,
                    "label"
                ].values[0],
            key="prof_objetivo"
        )
        crear_objetivo = st.button("💾 Crear objetivo")
        if crear_objetivo:
    
            with engine.begin() as conn:

                conn.execute(text("""
                    INSERT INTO pai_objetivos(
                        documento_usuario,
                        objetivo_tipo,
                        objetivo_descripcion,
                        actividades,
                        avance_hitos,
                        porcentaje_avance,
                        estado,
                        linea_politica,
                        ods_principal,
                        profesional_referente,
                        fecha_apertura,
                        fecha_meta
                    )
                    VALUES(
                        :documento_usuario,
                        :objetivo_tipo,
                        :objetivo_descripcion,
                        :actividades,
                        :avance_hitos,
                        :porcentaje_avance,
                        :estado,
                        :linea_politica,
                        :ods_principal,
                        :profesional_referente,
                        NOW(),
                        :fecha_meta
                    )
                """), {

                    "documento_usuario": usuario_sel,
                    "objetivo_tipo": objetivo_tipo,
                    "objetivo_descripcion": descripcion_objetivo,
                    "actividades": json.dumps(actividades),
                    "avance_hitos": json.dumps([]),
                    "porcentaje_avance": 0,
                    "estado": "Activo",
                    "linea_politica": linea_politica,
                    "ods_principal": ", ".join(ods),
                    "profesional_referente": profesional_referente,
                    "fecha_meta": fecha_cumplimiento

                })

            registrar_auditoria(
                "CREAR_OBJETIVO_PAI",
                documento=usuario_sel,
                modulo="PAI",
                valor_nuevo=objetivo_tipo,
                observacion=(
                    f"Profesional ID {profesional_referente}; "
                    f"fecha meta {fecha_cumplimiento}"
                )
            )
            invalidar_cache_datos()
            st.success("✅ Objetivo creado correctamente.")
            st.rerun()
        st.divider()
        st.markdown("## 🎯 Objetivos activos")

        if objetivos.empty:
            st.info("Este usuario aún no tiene objetivos.")

        # =========================
        # LOOP OBJETIVOS
        # =========================
        for _, obj in objetivos.iterrows():

            obj_id = obj["id"]

            # =========================
            # ESTADO LOCAL (NO BD)
            # =========================
            if f"hitos_{obj_id}" not in st.session_state:
                try:
                    st.session_state[f"hitos_{obj_id}"] = json.loads(obj["avance_hitos"] or "[]")
                except:
                    st.session_state[f"hitos_{obj_id}"] = []

            actividades = json.loads(obj["actividades"] or "[]")
            hitos_temp = st.session_state[f"hitos_{obj_id}"]

            st.markdown(f"### 🎯 {obj['objetivo_tipo']}")

            avance = round((len(hitos_temp) / len(actividades)) * 100, 1) if actividades else 0

            fecha_meta_obj = pd.to_datetime(
                obj.get("fecha_meta"), errors="coerce"
            )

            if avance >= 100:
                semaforo_obj = "🟢 CUMPLIDO"
            elif pd.isna(fecha_meta_obj):
                semaforo_obj = "⚪ SIN FECHA META"
            else:
                dias_obj = (
                    fecha_meta_obj.normalize()
                    - pd.Timestamp(date.today())
                ).days
                if dias_obj < 0:
                    semaforo_obj = f"🔴 VENCIDO ({abs(dias_obj)} días)"
                elif dias_obj <= 7:
                    semaforo_obj = f"🟡 VENCE EN {dias_obj} días"
                else:
                    semaforo_obj = f"🔵 EN TÉRMINO ({dias_obj} días)"

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Avance", f"{avance}%")
            c2.metric("Estado", obj["estado"])
            c3.metric("Control", semaforo_obj)
            c4.metric(
                "Fecha meta",
                fecha_meta_obj.strftime("%d/%m/%Y")
                if not pd.isna(fecha_meta_obj)
                else "Sin fecha"
            )

            st.progress(min(max(avance / 100, 0), 1))

            st.caption(f"👨‍⚕️ {obj['nombre_profesional'] or 'Sin asignar'}")
            st.caption(f"🏛️ {obj['linea_politica']}")
            st.write(obj["objetivo_descripcion"])

            # =========================
            # CHECKLIST (SIN BD)
            # =========================
            nuevo_estado = []

            for actividad in actividades:

                marcado = st.checkbox(
                    actividad,
                    value=actividad in hitos_temp,
                    key=f"{obj_id}_{actividad}"
                )

                if marcado:
                    nuevo_estado.append(actividad)

            st.session_state[f"hitos_{obj_id}"] = nuevo_estado

            # =========================
            # GUARDAR SOLO AL FINAL
            # =========================
            if st.button("💾 Guardar avances", key=f"save_{obj_id}"):

                query = text("""
                    UPDATE pai_objetivos
                    SET avance_hitos = :hitos,
                        porcentaje_avance = :avance,
                        estado = CASE
                            WHEN :avance >= 100 THEN 'CUMPLIDO'
                            ELSE 'Activo'
                        END,
                        fecha_cumplimiento_real = CASE
                            WHEN :avance >= 100
                                THEN COALESCE(fecha_cumplimiento_real, NOW())
                            ELSE NULL
                        END
                    WHERE id = :id
                """)

                with engine.begin() as conn:
                    conn.execute(query, {
                        "hitos": json.dumps(nuevo_estado),
                        "avance": avance,
                        "id": obj_id
                    })

                registrar_auditoria(
                    "ACTUALIZAR_AVANCE_PAI",
                    documento=usuario_sel,
                    modulo="PAI",
                    valor_nuevo=f"{avance}%",
                    observacion=f"Objetivo PAI ID {obj_id}"
                )
                invalidar_cache_datos()
                if avance >= 100:
                    st.success(
                        "✅ Objetivo completado al 100% y marcado como CUMPLIDO."
                    )
                else:
                    st.success("Avance guardado")
                st.rerun()

            # =========================
            # NOVEDAD (SIN RERUN)
            # =========================
            st.markdown("### 📝 Registrar novedad")

            tipo_novedad = st.selectbox(
                "Actividad realizada",
                actividades,
                key=f"tipo_{obj_id}"
            )

            descripcion = st.text_area(
                "Descripción",
                key=f"desc_{obj_id}"
            )

            evidencia = st.text_input(
                "Evidencia",
                key=f"evid_{obj_id}"
            )

            if st.button("💾 Guardar novedad", key=f"nov_{obj_id}"):

                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO pai_novedades(
                            id_objetivo,
                            fecha,
                            profesional,
                            tipo_novedad,
                            descripcion,
                            avance_generado,
                            evidencia
                        )
                        VALUES (
                            :id_objetivo,
                            NOW(),
                            :profesional,
                            :tipo_novedad,
                            :descripcion,
                            :avance_generado,
                            :evidencia
                        )
                    """), {
                        "id_objetivo": obj_id,
                        "profesional": obj["nombre_profesional"] or "Sin asignar",
                        "tipo_novedad": tipo_novedad,
                        "descripcion": descripcion,
                        "avance_generado": avance,
                        "evidencia": evidencia
                    })

                    conn.execute(
                        text("""
                            UPDATE pai_objetivos
                            SET fecha_ultimo_seguimiento = NOW()
                            WHERE id = :id
                        """),
                        {"id": obj_id}
                    )

                registrar_auditoria(
                    "REGISTRAR_NOVEDAD_PROFESIONAL",
                    documento=usuario_sel,
                    modulo="Seguimiento Profesional",
                    valor_nuevo=tipo_novedad,
                    observacion=descripcion[:500] if descripcion else None
                )
                invalidar_cache_datos()
                st.success(
                    "✅ Novedad registrada y fecha de último seguimiento actualizada."
                )
                st.rerun()

            # =========================
            # HISTORIAL (FILTRADO EN MEMORIA)
            # =========================
            with st.expander("🕒 Ver historial"):

                nov_obj = novedades_all[novedades_all["id_objetivo"] == obj_id]

                if nov_obj.empty:
                    st.caption("Sin novedades registradas")
                else:
                    for _, nov in nov_obj.iterrows():

                        st.markdown(f"""
                        **📌 {nov['tipo_novedad']}**

                        📅 {nov['fecha']}

                        👨‍⚕️ {nov['profesional']}

                        📝 {nov['descripcion']}
                        """)

                        if pd.notna(nov.get("evidencia")) and nov["evidencia"]:
                            st.caption(f"📂 {nov['evidencia']}")

                        st.divider()

            st.divider()

with tab7:

    st.title("📈 Seguimiento e Impacto")
    st.caption(
        "Módulo analítico. Consulta las intervenciones profesionales sin modificar "
        "la base general de habitantes."
    )

    # ========================================================
    # PROFESIONALES
    # ========================================================
    try:
        df_prof_seguimiento = pd.read_sql(
            text("""
                SELECT id, nombre, rol
                FROM profesionales
                ORDER BY nombre
            """),
            engine
        )
    except Exception:
        df_prof_seguimiento = pd.DataFrame(
            columns=["id", "nombre", "rol"]
        )

    if not df_prof_seguimiento.empty:
        df_prof_seguimiento["label"] = (
            df_prof_seguimiento["nombre"].astype(str)
            + " ("
            + df_prof_seguimiento["rol"].astype(str)
            + ")"
        )

    # ========================================================
    # FILTROS
    # ========================================================
    c1, c2, c3 = st.columns(3)

    opciones_prof = ["Todos"]
    if not df_prof_seguimiento.empty:
        opciones_prof += df_prof_seguimiento["id"].tolist()

    profesional_sel_impacto = c1.selectbox(
        "👨‍⚕️ Profesional",
        opciones_prof,
        key="seguimiento_profesional_filtro",
        format_func=lambda x: (
            "Todos"
            if x == "Todos"
            else df_prof_seguimiento.loc[
                df_prof_seguimiento["id"] == x,
                "label"
            ].iloc[0]
        )
    )

    hoy = date.today()
    fecha_inicio_impacto = c2.date_input(
        "📅 Fecha inicio",
        value=hoy.replace(day=1),
        key="seguimiento_fecha_inicio"
    )
    fecha_fin_impacto = c3.date_input(
        "📅 Fecha fin",
        value=hoy,
        key="seguimiento_fecha_fin"
    )

    if fecha_inicio_impacto > fecha_fin_impacto:
        st.warning("La fecha inicial no puede ser posterior a la fecha final.")
        df_seguimiento = pd.DataFrame()
    else:
        query_seguimiento = """
            SELECT
                n.id,
                n.id_objetivo,
                n.fecha,
                n.profesional,
                n.tipo_novedad,
                n.descripcion,
                n.avance_generado,
                n.evidencia,
                o.documento_usuario,
                o.objetivo_tipo,
                o.estado AS estado_objetivo
            FROM pai_novedades n
            LEFT JOIN pai_objetivos o
                ON o.id = n.id_objetivo
            WHERE DATE(n.fecha) BETWEEN :inicio AND :fin
        """

        params_seguimiento = {
            "inicio": fecha_inicio_impacto.strftime("%Y-%m-%d"),
            "fin": fecha_fin_impacto.strftime("%Y-%m-%d")
        }

        if profesional_sel_impacto != "Todos":
            nombre_profesional = df_prof_seguimiento.loc[
                df_prof_seguimiento["id"] == profesional_sel_impacto,
                "nombre"
            ].iloc[0]

            query_seguimiento += " AND n.profesional = :profesional"
            params_seguimiento["profesional"] = nombre_profesional

        query_seguimiento += " ORDER BY n.fecha DESC"

        df_seguimiento = pd.read_sql(
            text(query_seguimiento),
            engine,
            params=params_seguimiento
        )

    st.divider()

    # ========================================================
    # NO DETENER EL RESTO DE LA APLICACIÓN
    # ========================================================
    if df_seguimiento.empty:
        st.info(
            "No hay intervenciones registradas para los filtros seleccionados. "
            "Los demás módulos continúan disponibles normalmente."
        )
    else:
        df_seguimiento["fecha"] = pd.to_datetime(
            df_seguimiento["fecha"],
            errors="coerce"
        )
        df_seguimiento["avance_generado"] = pd.to_numeric(
            df_seguimiento["avance_generado"],
            errors="coerce"
        )

        total_intervenciones = len(df_seguimiento)
        personas_atendidas = (
            df_seguimiento["documento_usuario"]
            .dropna()
            .astype(str)
            .nunique()
        )
        profesionales_activos = (
            df_seguimiento["profesional"]
            .dropna()
            .nunique()
        )
        avance_promedio_impacto = (
            df_seguimiento["avance_generado"].mean()
            if df_seguimiento["avance_generado"].notna().any()
            else 0
        )

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("📌 Intervenciones", total_intervenciones)
        k2.metric("👥 Personas atendidas", personas_atendidas)
        k3.metric("👨‍⚕️ Profesionales", profesionales_activos)
        k4.metric(
            "📈 Avance promedio",
            f"{avance_promedio_impacto:.1f}%"
        )

        st.divider()

        g1, g2 = st.columns(2)

        with g1:
            st.subheader("📈 Evolución de intervenciones")
            evolucion_intervenciones = (
                df_seguimiento.dropna(subset=["fecha"])
                .groupby(df_seguimiento["fecha"].dt.date)
                .size()
                .rename("intervenciones")
            )
            if not evolucion_intervenciones.empty:
                st.line_chart(evolucion_intervenciones)

        with g2:
            st.subheader("👨‍⚕️ Intervenciones por profesional")
            productividad = (
                df_seguimiento["profesional"]
                .fillna("Sin profesional")
                .value_counts()
            )
            if not productividad.empty:
                st.bar_chart(productividad)

        st.subheader("🎯 Intervenciones por objetivo PAI")
        objetivos_impacto = (
            df_seguimiento["objetivo_tipo"]
            .fillna("Sin objetivo asociado")
            .value_counts()
        )
        if not objetivos_impacto.empty:
            st.bar_chart(objetivos_impacto)

        st.divider()
        st.subheader("📋 Detalle de intervenciones")

        columnas_detalle = [
            "fecha",
            "documento_usuario",
            "profesional",
            "objetivo_tipo",
            "tipo_novedad",
            "descripcion",
            "avance_generado",
            "evidencia"
        ]

        columnas_existentes = [
            c for c in columnas_detalle
            if c in df_seguimiento.columns
        ]

        st.dataframe(
            df_seguimiento[columnas_existentes],
            use_container_width=True,
            hide_index=True
        )

        # ====================================================
        # APORTE A ODS - SOLO COMO LECTURA ANALÍTICA
        # ====================================================
        st.divider()
        st.subheader("🌎 Contribución indicativa a los ODS")

        ods3 = (
            df_seguimiento["tipo_novedad"]
            .fillna("")
            .str.contains(
                "motivación|salud|acompañamiento|orientación",
                case=False,
                regex=True
            )
            .sum()
        )

        ods10 = total_intervenciones

        ods16 = (
            df_seguimiento["evidencia"]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
            .sum()
        )

        o1, o2, o3 = st.columns(3)
        o1.metric(
            "🩺 ODS 3 Salud y bienestar",
            f"{(ods3 / total_intervenciones) * 100:.1f}%"
        )
        o2.metric(
            "⚖️ ODS 10 Reducción desigualdades",
            f"{(ods10 / total_intervenciones) * 100:.1f}%"
        )
        o3.metric(
            "🏛️ ODS 16 Trazabilidad",
            f"{(ods16 / total_intervenciones) * 100:.1f}%"
        )

        st.caption(
            "Los porcentajes ODS son una lectura operativa de las intervenciones "
            "registradas; no sustituyen una medición formal de cumplimiento ODS."
        )


with tab8:

    st.title("📥 Conciliación y Carga de Activos")
    st.caption(
        "Valida el archivo antes de modificar estados. La carga conserva los "
        "EGRESADOS, registra trazabilidad y reporta documentos no encontrados."
    )

    archivo_activos = st.file_uploader(
        "Sube archivo Excel",
        type=["xlsx"],
        key="upload_activos_tab8_v6"
    )

    if archivo_activos:

        try:
            df_carga = pd.read_excel(archivo_activos)

            df_carga.columns = (
                df_carga.columns
                .astype(str)
                .str.strip()
                .str.lower()
                .str.replace("\n", " ", regex=False)
                .str.replace("  ", " ", regex=False)
                .str.replace(" ", "_", regex=False)
            )

            requeridas = [
                "numero_identificacion",
                "modalidad"
            ]

            faltantes_columnas = [
                c for c in requeridas
                if c not in df_carga.columns
            ]

            if faltantes_columnas:
                st.error(
                    "❌ El archivo no puede procesarse porque faltan estas "
                    f"columnas: {faltantes_columnas}"
                )
            else:
                df_carga = df_carga.dropna(
                    subset=["numero_identificacion"]
                ).copy()

                df_carga["numero_identificacion"] = (
                    df_carga["numero_identificacion"]
                    .astype(str)
                    .str.strip()
                    .str.replace(r"\.0$", "", regex=True)
                )

                df_carga["modalidad"] = (
                    df_carga["modalidad"]
                    .fillna("")
                    .astype(str)
                    .str.upper()
                    .str.strip()
                )

                df_carga = df_carga[
                    df_carga["numero_identificacion"].ne("")
                ].copy()

                duplicados_archivo = int(
                    df_carga["numero_identificacion"].duplicated(
                        keep=False
                    ).sum()
                )

                df_carga = df_carga.drop_duplicates(
                    subset=["numero_identificacion"],
                    keep="last"
                ).copy()

                # Base actual independiente del df general de la app
                df_base_activos = pd.read_sql(
                    text("""
                        SELECT
                            numero_identificacion,
                            nombres,
                            apellidos,
                            estado_caso,
                            modalidad
                        FROM habitante_de_calle
                    """),
                    engine
                )

                df_base_activos["doc_normalizado"] = (
                    df_base_activos["numero_identificacion"]
                    .astype(str)
                    .str.strip()
                    .str.replace(r"\.0$", "", regex=True)
                )

                df_base_activos["estado_normalizado"] = (
                    df_base_activos["estado_caso"]
                    .fillna("")
                    .astype(str)
                    .str.upper()
                    .str.strip()
                )

                df_base_activos["modalidad_normalizada"] = (
                    df_base_activos["modalidad"]
                    .fillna("")
                    .astype(str)
                    .str.upper()
                    .str.strip()
                )

                docs_base = set(
                    df_base_activos["doc_normalizado"].tolist()
                )
                docs_archivo = set(
                    df_carga["numero_identificacion"].tolist()
                )

                docs_encontrados = docs_archivo & docs_base
                docs_no_encontrados = docs_archivo - docs_base

                activos_actuales_df = df_base_activos[
                    df_base_activos["estado_normalizado"] == "ACTIVO"
                ].copy()
                docs_activos_actuales = set(
                    activos_actuales_df["doc_normalizado"].tolist()
                )

                # Solo quienes están ACTIVOS y ya no vienen en el archivo
                # pasarán a INACTIVO. Los EGRESADOS no se modifican.
                docs_a_inactivar = (
                    docs_activos_actuales - docs_encontrados
                )

                # Encontrados que no estaban activos -> activar
                base_por_doc = (
                    df_base_activos
                    .drop_duplicates("doc_normalizado", keep="last")
                    .set_index("doc_normalizado")
                )

                docs_a_activar = set()
                docs_cambio_modalidad = set()

                modalidad_archivo = dict(
                    zip(
                        df_carga["numero_identificacion"],
                        df_carga["modalidad"]
                    )
                )

                for doc in docs_encontrados:
                    estado_prev = str(
                        base_por_doc.loc[doc, "estado_normalizado"]
                    )
                    modalidad_prev = str(
                        base_por_doc.loc[doc, "modalidad_normalizada"]
                    )
                    modalidad_nueva = modalidad_archivo.get(doc, "")

                    if estado_prev != "ACTIVO":
                        docs_a_activar.add(doc)
                    elif modalidad_prev != modalidad_nueva:
                        docs_cambio_modalidad.add(doc)

                # ------------------------------------------------
                # PREVISUALIZACIÓN
                # ------------------------------------------------
                st.subheader("🔎 Validación previa")

                p1, p2, p3, p4, p5 = st.columns(5)
                p1.metric("Archivo", len(df_carga))
                p2.metric("Encontrados", len(docs_encontrados))
                p3.metric(
                    "No encontrados",
                    len(docs_no_encontrados)
                )
                p4.metric("A activar", len(docs_a_activar))
                p5.metric("A inactivar", len(docs_a_inactivar))

                if duplicados_archivo:
                    st.warning(
                        f"Se detectaron {duplicados_archivo} filas asociadas "
                        "a identificaciones duplicadas en el archivo. "
                        "Se conservará la última aparición de cada persona."
                    )

                resumen_modalidad = (
                    df_carga["modalidad"]
                    .replace("", "SIN MODALIDAD")
                    .value_counts()
                    .rename_axis("modalidad")
                    .reset_index(name="cantidad")
                )

                st.subheader("📊 Distribución del archivo por modalidad")
                st.dataframe(
                    resumen_modalidad,
                    use_container_width=True,
                    hide_index=True
                )
                st.bar_chart(
                    resumen_modalidad.set_index("modalidad")
                )

                if docs_no_encontrados:
                    st.warning(
                        "Hay personas del Excel que no existen en "
                        "habitante_de_calle. No serán creadas automáticamente."
                    )

                    no_encontrados_df = (
                        df_carga[
                            df_carga["numero_identificacion"]
                            .isin(docs_no_encontrados)
                        ][["numero_identificacion", "modalidad"]]
                        .sort_values("numero_identificacion")
                    )

                    with st.expander(
                        f"⚠️ Ver {len(no_encontrados_df)} documentos no encontrados"
                    ):
                        st.dataframe(
                            no_encontrados_df,
                            use_container_width=True,
                            hide_index=True
                        )

                if docs_a_inactivar:
                    detalle_inactivar = df_base_activos[
                        df_base_activos["doc_normalizado"]
                        .isin(docs_a_inactivar)
                    ][
                        [
                            "numero_identificacion",
                            "nombres",
                            "apellidos",
                            "modalidad"
                        ]
                    ]

                    with st.expander(
                        f"🟠 Ver {len(detalle_inactivar)} personas que pasarán a INACTIVO"
                    ):
                        st.dataframe(
                            detalle_inactivar,
                            use_container_width=True,
                            hide_index=True
                        )

                if docs_a_activar:
                    detalle_activar = df_base_activos[
                        df_base_activos["doc_normalizado"]
                        .isin(docs_a_activar)
                    ][
                        [
                            "numero_identificacion",
                            "nombres",
                            "apellidos",
                            "estado_caso",
                            "modalidad"
                        ]
                    ]

                    with st.expander(
                        f"🟢 Ver {len(detalle_activar)} personas que pasarán a ACTIVO"
                    ):
                        st.dataframe(
                            detalle_activar,
                            use_container_width=True,
                            hide_index=True
                        )

                if docs_cambio_modalidad:
                    st.info(
                        f"{len(docs_cambio_modalidad)} personas ya activas "
                        "cambiarán de modalidad."
                    )

                st.divider()

                confirmar_carga = st.checkbox(
                    "Confirmo que revisé la conciliación y deseo aplicar estos cambios",
                    key="confirmar_actualizacion_activos_v6"
                )

                if confirmar_carga and st.button(
                    "✅ Aplicar conciliación",
                    key="btn_actualizar_activos_v6",
                    type="primary",
                    use_container_width=True
                ):
                    usuario_accion = st.session_state.get(
                        "usuario_actual",
                        "sistema"
                    )

                    with engine.begin() as conn:

                        # 1. INACTIVAR solo activos ausentes del archivo
                        for doc in sorted(docs_a_inactivar):
                            fila_prev = base_por_doc.loc[doc]
                            modalidad_prev = str(
                                fila_prev["modalidad_normalizada"]
                            )

                            conn.execute(
                                text("""
                                    UPDATE habitante_de_calle
                                    SET estado_caso = 'INACTIVO',
                                        modalidad = NULL
                                    WHERE TRIM(
                                        CAST(numero_identificacion AS TEXT)
                                    ) = :doc
                                      AND UPPER(
                                        TRIM(COALESCE(estado_caso, ''))
                                      ) = 'ACTIVO'
                                """),
                                {"doc": doc}
                            )

                            conn.execute(
                                text("""
                                    INSERT INTO movimientos_habitante (
                                        numero_identificacion,
                                        tipo_movimiento,
                                        modalidad,
                                        usuario_registra,
                                        observacion
                                    )
                                    VALUES (
                                        :doc,
                                        'INACTIVACION_CARGA',
                                        :modalidad,
                                        :usuario,
                                        'Inactivación por conciliación de archivo de activos'
                                    )
                                """),
                                {
                                    "doc": doc,
                                    "modalidad": modalidad_prev or None,
                                    "usuario": usuario_accion
                                }
                            )

                        # 2. ACTIVAR / ACTUALIZAR encontrados
                        for doc in sorted(docs_encontrados):
                            modalidad_nueva = modalidad_archivo.get(
                                doc,
                                ""
                            ) or None

                            estado_prev = str(
                                base_por_doc.loc[
                                    doc,
                                    "estado_normalizado"
                                ]
                            )
                            modalidad_prev = str(
                                base_por_doc.loc[
                                    doc,
                                    "modalidad_normalizada"
                                ]
                            )

                            conn.execute(
                                text("""
                                    UPDATE habitante_de_calle
                                    SET estado_caso = 'ACTIVO',
                                        modalidad = :modalidad
                                    WHERE TRIM(
                                        CAST(numero_identificacion AS TEXT)
                                    ) = :doc
                                """),
                                {
                                    "doc": doc,
                                    "modalidad": modalidad_nueva
                                }
                            )

                            if estado_prev != "ACTIVO":
                                tipo_mov = "ACTIVACION_CARGA"
                                obs = (
                                    "Activación por conciliación de archivo de activos"
                                )
                            elif modalidad_prev != (modalidad_nueva or ""):
                                tipo_mov = "CAMBIO_MODALIDAD_CARGA"
                                obs = (
                                    f"Cambio de modalidad por conciliación: "
                                    f"{modalidad_prev or 'SIN MODALIDAD'} -> "
                                    f"{modalidad_nueva or 'SIN MODALIDAD'}"
                                )
                            else:
                                tipo_mov = None
                                obs = None

                            if tipo_mov:
                                conn.execute(
                                    text("""
                                        INSERT INTO movimientos_habitante (
                                            numero_identificacion,
                                            tipo_movimiento,
                                            modalidad,
                                            usuario_registra,
                                            observacion
                                        )
                                        VALUES (
                                            :doc,
                                            :tipo_movimiento,
                                            :modalidad,
                                            :usuario,
                                            :observacion
                                        )
                                    """),
                                    {
                                        "doc": doc,
                                        "tipo_movimiento": tipo_mov,
                                        "modalidad": modalidad_nueva,
                                        "usuario": usuario_accion,
                                        "observacion": obs
                                    }
                                )

                        total_activos_final = conn.execute(
                            text("""
                                SELECT COUNT(*)
                                FROM habitante_de_calle
                                WHERE UPPER(
                                    TRIM(COALESCE(estado_caso, ''))
                                ) = 'ACTIVO'
                            """)
                        ).scalar()

                    # Auditoría resumida, fuera de la transacción principal
                    registrar_auditoria(
                        "CONCILIACION_MASIVA_ACTIVOS",
                        modulo="Carga Activos",
                        valor_anterior=(
                            f"Activos previos: {len(docs_activos_actuales)}"
                        ),
                        valor_nuevo=(
                            f"Activos finales: {total_activos_final}"
                        ),
                        observacion=(
                            f"Encontrados: {len(docs_encontrados)}; "
                            f"No encontrados: {len(docs_no_encontrados)}; "
                            f"Activados: {len(docs_a_activar)}; "
                            f"Inactivados: {len(docs_a_inactivar)}; "
                            f"Cambios modalidad: {len(docs_cambio_modalidad)}"
                        )
                    )

                    invalidar_cache_datos()

                    st.success(
                        "✅ Conciliación aplicada correctamente."
                    )
                    st.info(
                        f"Activos finales: {total_activos_final} | "
                        f"Activados: {len(docs_a_activar)} | "
                        f"Inactivados: {len(docs_a_inactivar)} | "
                        f"Cambios de modalidad: {len(docs_cambio_modalidad)} | "
                        f"No encontrados: {len(docs_no_encontrados)}"
                    )

        except Exception as e:
            st.error(
                f"❌ Error al procesar la carga de activos: {e}"
            )


with tab9:

    st.title("📄 Historia Integral de Atención")
    st.caption(
        "Consulta consolidada del usuario: estado actual, movimientos, PAI, "
        "intervenciones profesionales y trazabilidad."
    )

    usuarios_historia = pd.read_sql(
        text("""
            SELECT
                numero_identificacion,
                nombres,
                apellidos,
                edad,
                sexo_al_nacer,
                estado_caso,
                modalidad
            FROM habitante_de_calle
            ORDER BY nombres, apellidos
        """),
        engine
    )

    if usuarios_historia.empty:
        st.info("No hay personas disponibles para consultar.")
    else:
        usuarios_historia["doc_normalizado"] = (
            usuarios_historia["numero_identificacion"]
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
        )

        usuarios_historia["nombre_completo"] = (
            usuarios_historia["nombres"].fillna("").astype(str).str.strip()
            + " "
            + usuarios_historia["apellidos"].fillna("").astype(str).str.strip()
        ).str.strip()

        opciones_historia = usuarios_historia.index.tolist()

        indice_historia = st.selectbox(
            "👤 Seleccione usuario",
            opciones_historia,
            key="historia_usuario_v6",
            format_func=lambda i: (
                f"{usuarios_historia.loc[i, 'nombre_completo']} - "
                f"{usuarios_historia.loc[i, 'doc_normalizado']}"
            )
        )

        persona_historia = usuarios_historia.loc[indice_historia]
        documento_historia = persona_historia["doc_normalizado"]

        h1, h2, h3, h4 = st.columns(4)
        h1.metric(
            "📌 Estado",
            str(persona_historia.get("estado_caso", "") or "Sin dato")
        )
        h2.metric(
            "🏷️ Modalidad",
            str(persona_historia.get("modalidad", "") or "Sin dato")
        )
        h3.metric(
            "🎂 Edad",
            str(persona_historia.get("edad", "") or "Sin dato")
        )
        h4.metric(
            "⚧ Sexo",
            str(persona_historia.get("sexo_al_nacer", "") or "Sin dato")
        )

        st.divider()

        # ====================================================
        # RESUMEN DE HISTORIA
        # ====================================================
        movimientos_hist = pd.read_sql(
            text("""
                SELECT
                    fecha_movimiento,
                    tipo_movimiento,
                    modalidad,
                    usuario_registra,
                    observacion
                FROM movimientos_habitante
                WHERE TRIM(
                    CAST(numero_identificacion AS TEXT)
                ) = :doc
                ORDER BY fecha_movimiento DESC
            """),
            engine,
            params={"doc": documento_historia}
        )

        objetivos_hist = pd.read_sql(
            text("""
                SELECT
                    id,
                    fecha_apertura,
                    objetivo_tipo,
                    objetivo_descripcion,
                    estado,
                    porcentaje_avance,
                    fecha_meta,
                    fecha_cumplimiento_real,
                    fecha_ultimo_seguimiento,
                    profesional_referente
                FROM pai_objetivos
                WHERE TRIM(
                    CAST(documento_usuario AS TEXT)
                ) = :doc
                ORDER BY fecha_apertura DESC
            """),
            engine,
            params={"doc": documento_historia}
        )

        novedades_hist = pd.read_sql(
            text("""
                SELECT
                    n.fecha,
                    n.profesional,
                    n.tipo_novedad,
                    n.descripcion,
                    n.avance_generado,
                    o.objetivo_tipo
                FROM pai_novedades n
                INNER JOIN pai_objetivos o
                    ON o.id = n.id_objetivo
                WHERE TRIM(
                    CAST(o.documento_usuario AS TEXT)
                ) = :doc
                ORDER BY n.fecha DESC
            """),
            engine,
            params={"doc": documento_historia}
        )

        try:
            auditoria_hist = pd.read_sql(
                text("""
                    SELECT
                        fecha_hora,
                        usuario,
                        modulo,
                        accion,
                        valor_anterior,
                        valor_nuevo,
                        observacion
                    FROM auditoria_sistema
                    WHERE TRIM(
                        COALESCE(numero_identificacion, '')
                    ) = :doc
                    ORDER BY fecha_hora DESC
                    LIMIT 100
                """),
                engine,
                params={"doc": documento_historia}
            )
        except Exception:
            auditoria_hist = pd.DataFrame()

        avance_pai_hist = 0.0
        if (
            not objetivos_hist.empty
            and "porcentaje_avance" in objetivos_hist.columns
        ):
            avance_serie = pd.to_numeric(
                objetivos_hist["porcentaje_avance"],
                errors="coerce"
            )
            if avance_serie.notna().any():
                avance_pai_hist = float(avance_serie.mean())

        vencidos_hist = 0
        proximos_hist = 0

        if not objetivos_hist.empty and "fecha_meta" in objetivos_hist.columns:
            fechas_meta_hist = pd.to_datetime(
                objetivos_hist["fecha_meta"], errors="coerce"
            )
            avances_hist = pd.to_numeric(
                objetivos_hist["porcentaje_avance"], errors="coerce"
            ).fillna(0)
            dias_hist = (
                fechas_meta_hist.dt.normalize()
                - pd.Timestamp(date.today())
            ).dt.days

            vencidos_hist = int(
                ((dias_hist < 0) & (avances_hist < 100)).sum()
            )
            proximos_hist = int(
                (
                    (dias_hist >= 0)
                    & (dias_hist <= 7)
                    & (avances_hist < 100)
                ).sum()
            )

        r1, r2, r3, r4, r5, r6 = st.columns(6)
        r1.metric("🔄 Movimientos", len(movimientos_hist))
        r2.metric("🎯 Objetivos PAI", len(objetivos_hist))
        r3.metric("📝 Intervenciones", len(novedades_hist))
        r4.metric("📈 Avance PAI", f"{avance_pai_hist:.1f}%")
        r5.metric("🔴 Vencidos", vencidos_hist)
        r6.metric("🟡 Próximos", proximos_hist)

        st.markdown("### 🧭 Historia en pantalla")

        hist_tab1, hist_tab2, hist_tab3, hist_tab4 = st.tabs([
            "🔄 Movimientos",
            "🎯 PAI",
            "📝 Seguimiento profesional",
            "🛡️ Auditoría"
        ])

        with hist_tab1:
            if movimientos_hist.empty:
                st.info("Sin movimientos registrados.")
            else:
                st.dataframe(
                    movimientos_hist,
                    use_container_width=True,
                    hide_index=True
                )

        with hist_tab2:
            if objetivos_hist.empty:
                st.info("Sin objetivos PAI registrados.")
            else:
                st.dataframe(
                    objetivos_hist,
                    use_container_width=True,
                    hide_index=True
                )

        with hist_tab3:
            if novedades_hist.empty:
                st.info("Sin intervenciones profesionales registradas.")
            else:
                st.dataframe(
                    novedades_hist,
                    use_container_width=True,
                    hide_index=True
                )

        with hist_tab4:
            if auditoria_hist.empty:
                st.info(
                    "Aún no hay eventos de auditoría para esta persona."
                )
            else:
                st.dataframe(
                    auditoria_hist,
                    use_container_width=True,
                    hide_index=True
                )

        st.divider()

        if st.button(
            "📄 Generar Historia Integral PDF",
            key="generar_historia_integral_v6",
            use_container_width=True
        ):
            try:
                pdf_historia = generar_historia_integral(
                    documento_historia,
                    engine
                )
                st.session_state[
                    "historia_integral_pdf_v6"
                ] = pdf_historia.getvalue()
                st.session_state[
                    "historia_integral_doc_v6"
                ] = documento_historia

                registrar_auditoria(
                    "GENERAR_HISTORIA_INTEGRAL",
                    documento=documento_historia,
                    modulo="Historia Integral"
                )

                st.success("✅ Historia integral generada.")
            except Exception as e:
                st.error(
                    f"❌ No fue posible generar la historia: {e}"
                )

        if (
            st.session_state.get("historia_integral_pdf_v6")
            and st.session_state.get(
                "historia_integral_doc_v6"
            ) == documento_historia
        ):
            st.download_button(
                "⬇️ Descargar Historia Integral",
                data=st.session_state[
                    "historia_integral_pdf_v6"
                ],
                file_name=f"historia_{documento_historia}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="descargar_historia_integral_v6"
            )
