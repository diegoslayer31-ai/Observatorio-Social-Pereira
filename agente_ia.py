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
from datetime import date, timedelta

st.set_page_config(
    page_title="Observatorio Social Asociación Ciudad Futuro",
    page_icon="📊",
    layout="wide"
)

engine = create_engine(st.secrets["DATABASE_URL"])

if "page" not in st.session_state:
    st.session_state.page = "home"


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
    
    st.title("⚙️ Gestión de usuarios")

    # ==================================
    # CARGAR BASE
    # ==================================

    df = pd.read_sql(
        """
        SELECT *
        FROM habitante_de_calle
        """,
        engine
    )

    if df.empty:

        st.warning("No hay usuarios registrados")

        return

    # ==================================
    # NORMALIZAR
    # ==================================

    df["modalidad"] = (
        df["modalidad"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df["estado_caso"] = (
        df["estado_caso"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df["numero_identificacion"] = (
        df["numero_identificacion"]
        .astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
    )

    df["nombre"] = (
        df["nombres"].astype(str)
        + " "
        + df["apellidos"].astype(str)
    )

    # ==================================
    # INDICADORES
    # ==================================

    urbano = len(
        df[
            (df["modalidad"] == "URBANO")
            &
            (df["estado_caso"] == "ACTIVO")
        ]
    )

    granja = len(
        df[
            (df["modalidad"] == "GRANJA")
            &
            (df["estado_caso"] == "ACTIVO")
        ]
    )

    egresados = len(
        df[
            df["estado_caso"] == "EGRESADO"
        ]
    )

    total = len(df)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("🏙️ Urbano", urbano)

    c2.metric("🌱 Granja", granja)

    c3.metric("📤 Egresados", egresados)

    c4.metric("👥 Total", total)

    st.divider()

    # ==================================
    # LISTADO
    # ==================================

    st.subheader("📋 Usuarios")

    columnas = [

        "nombres",

        "apellidos",

        "numero_identificacion",

        "modalidad",

        "estado_caso"

    ]

    columnas = [

        c for c in columnas

        if c in df.columns

    ]

    st.dataframe(

        df[columnas],

        use_container_width=True

    )

    st.divider()
        # ==================================
    # BUSCADOR
    # ==================================

    st.subheader("🔎 Buscar usuario")

    usuario = st.selectbox(

        "Seleccione usuario",

        df.index,

        format_func=lambda x:

        f"{df.loc[x,'nombre']} - {df.loc[x,'numero_identificacion']}"

    )

    persona = df.loc[usuario]

    st.info(f"""

    👤 {persona['nombre']}

    🪪 {persona['numero_identificacion']}

    📌 Estado: {persona['estado_caso']}

    🏷️ Modalidad: {persona['modalidad']}

    """)

    st.divider()

    # ==================================
    # 📝 ÚLTIMAS 10 NOVEDADES
    # ==================================

    st.subheader("📝 Últimas 10 novedades")

    try:

        documento = str(
            persona["numero_identificacion"]
        ).strip()

        df_novedades = pd.read_sql(f"""

            SELECT

                n.fecha,

                n.profesional,

                o.objetivo_tipo,

                n.descripcion

            FROM pai_novedades n

            INNER JOIN pai_objetivos o

            ON n.id_objetivo = o.id

            WHERE o.documento_usuario = '{documento}'

            ORDER BY n.fecha DESC

            LIMIT 10

        """, engine)

        if df_novedades.empty:

            st.warning(
                "⚠️ No existen novedades registradas."
            )

        else:

            st.success(
                f"Se encontraron {len(df_novedades)} novedades."
            )

            st.dataframe(

                df_novedades,

                use_container_width=True

            )

    except Exception as e:

        st.warning(
            "Error cargando novedades"
        )

        st.caption(str(e))

    st.divider()
    # ==================================
    # ACTUALIZAR ESTADO Y MODALIDAD
    # ==================================

    c5, c6 = st.columns(2)

    with c5:

        st.subheader("📌 Estado")

        nuevo_estado = st.selectbox(

            "Cambiar estado",

            [

                "ACTIVO",

                "EGRESADO"

            ]

        )

        if st.button("💾 Actualizar estado"):

            with engine.begin() as conn:

                conn.execute(text("""

                    UPDATE habitante_de_calle

                    SET estado_caso=:estado

                    WHERE numero_identificacion=:doc

                """), {

                    "estado": nuevo_estado,

                    "doc": persona["numero_identificacion"]

                })

            st.success("Estado actualizado")

            st.rerun()

    with c6:

        st.subheader("🏠 Modalidad")

        nueva_modalidad = st.selectbox(

            "Cambiar modalidad",

            [

                "URBANO",

                "GRANJA"

            ]

        )

        if st.button("💾 Actualizar modalidad"):

            with engine.begin() as conn:

                conn.execute(text("""

                    UPDATE habitante_de_calle

                    SET modalidad=:modalidad

                    WHERE numero_identificacion=:doc

                """), {

                    "modalidad": nueva_modalidad,

                    "doc": persona["numero_identificacion"]

                })

            st.success("Modalidad actualizada")

            st.rerun()

    st.divider()

    # ==================================
    # NUEVO USUARIO
    # ==================================

    st.subheader("➕ Registrar nuevo usuario")

    with st.form("nuevo_usuario"):

        st.markdown("### 👤 Datos personales")

        nombres = st.text_input("Nombres")

        apellidos = st.text_input("Apellidos")

        sexo = st.selectbox(

            "Sexo al nacer",

            [

                "Masculino",

                "Femenino"

            ]

        )

        fecha_nacimiento = st.date_input(

            "Fecha nacimiento"

        )

        edad = st.number_input(

            "Edad",

            0,

            120,

            18

        )

        tipo_id = st.selectbox(

            "Tipo identificación",

            [

                "CC",

                "TI",

                "CE",

                "PEP",

                "Otro"

            ]

        )

        numero_id = st.text_input(

            "Número identificación"

        )

        st.markdown("### 🌎 Enfoque diferencial")

        discapacidad = st.selectbox(

            "Discapacidad",

            [

                "No",

                "Sí"

            ]

        )

        migracion = st.selectbox(

            "Migración",

            [

                "NO",

                "SI"

            ]

        )

        etnia = st.selectbox(

            "Grupo étnico",

            [

                "Ninguno",

                "Afrodescendiente",

                "Indígena",

                "Mestizo"

            ]

        )

        st.markdown("### 🏥 Salud")

        seguridad_salud = st.selectbox(

            "Seguridad social",

            [

                "Subsidiado",

                "Contributivo",

                "Especial",

                "No afiliado"

            ]

        )

        st.markdown("### 🎓 Educación")

        educacion = st.selectbox(

            "Nivel educativo",

            [

                "Ninguno",

                "Primaria",

                "Secundaria",

                "Técnico",

                "Tecnólogo",

                "Universitario"

            ]

        )

        st.markdown("### 📍 Ubicación")

        barrio = st.text_input(

            "Barrio"

        )

        comuna = st.text_input(

            "Comuna"

        )

        direccion = st.text_input(

            "Dirección"

        )

        telefono = st.text_input(

            "Teléfono"

        )

        correo = st.text_input(

            "Correo"

        )

        st.markdown("### 💊 Programa")

        consumo = st.selectbox(

            "Tipo consumo",

            [

                "No",

                "Marihuana",

                "Cocaína",

                "Bazuco",

                "Alcohol",

                "Heroína",

                "Policonsumo"

            ]

        )

        enfermedad = st.selectbox(

            "Enfermedad mental",

            [

                "No",

                "Sí"

            ]

        )

        modalidad = st.selectbox(

            "Modalidad",

            [

                "URBANO",

                "GRANJA"

            ]

        )

        guardar = st.form_submit_button(

            "💾 Guardar usuario"

        )

    if guardar:

        with engine.begin() as conn:

            conn.execute(text("""

            INSERT INTO habitante_de_calle(

                nombres,

                apellidos,

                sexo_al_nacer,

                fecha_nacimiento,

                edad,

                tipo_identificacion,

                numero_identificacion,

                personas_con_discapacidad,

                indicador_migracion,

                grupos_etnicos,

                tipo_seguridad_salud,

                nivel_educativo,

                barrio_vereda,

                comuna_corregimiento,

                direccion,

                telefono,

                correo,

                tipo_consumo,

                enfermedad_mental,

                estado_caso,

                modalidad,

                fecha_ingreso_albergue,

                numero_atenciones

            )

            VALUES(

                :nombres,

                :apellidos,

                :sexo,

                :fecha_nacimiento,

                :edad,

                :tipo_id,

                :numero_id,

                :discapacidad,

                :migracion,

                :etnia,

                :seguridad_salud,

                :educacion,

                :barrio,

                :comuna,

                :direccion,

                :telefono,

                :correo,

                :consumo,

                :enfermedad,

                'ACTIVO',

                :modalidad,

                CURRENT_DATE,

                0

            )

            """), {

                "nombres": nombres,

                "apellidos": apellidos,

                "sexo": sexo,

                "fecha_nacimiento": fecha_nacimiento,

                "edad": edad,

                "tipo_id": tipo_id,

                "numero_id": numero_id,

                "discapacidad": discapacidad,

                "migracion": migracion,

                "etnia": etnia,

                "seguridad_salud": seguridad_salud,

                "educacion": educacion,

                "barrio": barrio,

                "comuna": comuna,

                "direccion": direccion,

                "telefono": telefono,

                "correo": correo,

                "consumo": consumo,

                "enfermedad": enfermedad,

                "modalidad": modalidad

            })

        st.success("✅ Usuario registrado")

        st.rerun()
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

# =====================================
# SIDEBAR
# =====================================

with st.sidebar:

    st.image("logo_acf.png", width=220)

    st.markdown("---")
    st.markdown("### Asociación Ciudad Futuro")

    st.caption("""
    Sistema Integral de Atención,
    Seguimiento y Observatorio Social
    """)

    st.markdown("---")


    if st.button("🏠 Inicio"):
        st.session_state.page = "home"
        st.rerun()

    if st.button("⚙️ Gestión usuarios"):
        st.session_state.page = "gestion_usuarios"
        st.rerun()
    if st.button("♀️ Género y Diversidad"):
        st.session_state.page = "genero_diversidad"
        st.rerun()
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
# ROUTER
# =====================================

if st.session_state.page == "gestion_usuarios":
    
    gestion_usuarios()
    st.stop()
elif st.session_state.page == "genero_diversidad":

    formulario_genero_diversidad()
    st.stop()
   
def gestion_usuarios():
    
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

        with engine.begin() as conn:

            conn.execute(text("""
                UPDATE habitante_de_calle
                SET estado_caso = :estado
                WHERE numero_identificacion = :id
            """), {
                "estado": nuevo_estado,
                "id": usuario_estado
            })

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
engine = create_engine(
    st.secrets["DATABASE_URL"]
)

# =========================
# OLLAMA
# =========================
#client = Client(host="http://localhost:11434")

# =========================
# POSTGRESQL / SUPABASE
# =========================
engine = create_engine(
    st.secrets["DATABASE_URL"]
)
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

    df_busqueda = df.copy()

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

        if clave == "Pereira2026":

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

    st.title("📋 PAI")

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

    # =========================
    # BUSCAR USUARIO
    # =========================
    st.subheader("🔎 Buscar usuario")

    busqueda = st.text_input("Nombre, apellido o documento")

    df_busqueda = df.copy()

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
                        fecha_apertura
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
                        NOW()
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
                    "profesional_referente": profesional_referente

                })

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

            c1, c2, c3 = st.columns(3)
            c1.metric("Avance", f"{avance}%")
            c2.metric("Estado", obj["estado"])
            c3.metric("ODS", obj["ods_principal"])

            st.progress(avance / 100)

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
                        porcentaje_avance = :avance
                    WHERE id = :id
                """)

                with engine.begin() as conn:
                    conn.execute(query, {
                        "hitos": json.dumps(nuevo_estado),
                        "avance": avance,
                        "id": obj_id
                    })

                st.success("Avance guardado")

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

                st.success("Novedad registrada")

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

    st.title("📈 Seguimiento e Impacto - Reducción de Riesgos y Daños")


    # =========================
    # PROFESIONALES
    # =========================
    df_profesionales = pd.read_sql("""
        SELECT id, nombre, rol
        FROM profesionales
        ORDER BY nombre
    """, engine)

    df_profesionales["label"] = (
        df_profesionales["nombre"] + " (" + df_profesionales["rol"] + ")"
    )

    # =========================
    # FILTROS
    # =========================
    col1, col2, col3 = st.columns(3)

    profesional_sel = col1.selectbox(
        "👨‍⚕️ Profesional",
        ["Todos"] + df_profesionales["id"].tolist(),
        format_func=lambda x: (
            "Todos"
            if x == "Todos"
            else df_profesionales[df_profesionales["id"] == x]["label"].values[0]
        )
    )

    fecha_inicio = col2.date_input("📅 Fecha inicio")
    fecha_fin = col3.date_input("📅 Fecha fin")

    # =========================
    # QUERY
    # =========================
    query = """
        SELECT *
        FROM pai_novedades
        WHERE DATE(fecha) BETWEEN :inicio AND :fin
    """

    params = {
        "inicio": fecha_inicio.strftime("%Y-%m-%d"),
        "fin": fecha_fin.strftime("%Y-%m-%d")
    }

    # filtro profesional (por nombre real en tu tabla)
    if profesional_sel != "Todos":

        nombre_profesional = df_profesionales.loc[
            df_profesionales["id"] == profesional_sel,
            "nombre"
        ].values[0]

        query += " AND profesional = :profesional"
        params["profesional"] = nombre_profesional

    # =========================
    # DATA
    # =========================
    df = pd.read_sql(text(query), engine, params=params)

    st.divider()

    # =========================
    # VALIDACIÓN
    # =========================
    if df.empty:
        st.info("No hay registros en este rango.")
        st.stop()

    # =========================
    # KPIs
    # =========================
    col1, col2, col3 = st.columns(3)

    col1.metric("📌 Registros", len(df))
    col2.metric("📈 Avance promedio", f"{df['avance_generado'].mean():.1f}%")
    col3.metric("👨‍⚕️ Profesionales activos", df["profesional"].nunique())

    st.divider()

    # =========================
    # GRÁFICAS
    # =========================

    # 📈 evolución del avance
    df["fecha"] = pd.to_datetime(df["fecha"])
    evol = df.groupby(df["fecha"].dt.date)["avance_generado"].mean()

    st.subheader("📈 Evolución del avance")
    st.line_chart(evol)

    # 👨‍⚕️ productividad
    st.subheader("👨‍⚕️ Intervenciones por profesional")
    prod = df.groupby("profesional")["id"].count().sort_values(ascending=False)
    st.bar_chart(prod)

    st.divider()

    # =========================
    # TABLA DETALLADA
    # =========================
    st.subheader("📋 Detalle de registros")

    st.dataframe(
        df[[
            "fecha",
            "profesional",
            "tipo_novedad",
            "descripcion",
            "avance_generado",
            "evidencia"
        ]],
        use_container_width=True
    )
        # =========================
    # ODS
    # =========================

    st.divider()

    st.subheader("🌎 Contribución a los Objetivos de Desarrollo Sostenible (ODS)")

    total_intervenciones = len(df)

    # ODS 3
    ods3 = (
        df["tipo_novedad"]
        .str.contains(
            "motivación|salud|acompañamiento|orientación",
            case=False,
            na=False
        )
        .sum()
    )

    # ODS 10
    ods10 = total_intervenciones

    # ODS 16
    ods16 = (
        df["evidencia"]
        .fillna("")
        .str.strip()
        .ne("")
        .sum()
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "🩺 ODS 3 Salud y bienestar",
        f"{(ods3/total_intervenciones)*100:.1f}%"
    )

    col2.metric(
        "⚖️ ODS 10 Reducción desigualdades",
        f"{(ods10/total_intervenciones)*100:.1f}%"
    )

    col3.metric(
        "🏛️ ODS 16 Fortalecimiento institucional",
        f"{(ods16/total_intervenciones)*100:.1f}%"
    )
    st.subheader("📋 Aporte institucional a los ODS")

    ods_df = pd.DataFrame({
        "ODS": [
            "ODS 3",
            "ODS 10",
            "ODS 16"
        ],

        "Objetivo": [
            "Salud y bienestar",
            "Reducción de desigualdades",
            "Paz, justicia e instituciones sólidas"
        ],

        "Contribución": [
            "Intervenciones de reducción de riesgos y daños.",
            "Inclusión social y disminución de vulnerabilidades.",
            "Seguimiento, trazabilidad y fortalecimiento institucional."
        ]
    })

    st.dataframe(
        ods_df,
        use_container_width=True,
        hide_index=True
    )
with tab8:

    st.title("📥 Carga Masiva de Activos")

    archivo = st.file_uploader(
        "Sube archivo Excel",
        type=["xlsx"],
        key="upload_activos_tab11"
    )

    if archivo:

        try:
            df_activos = pd.read_excel(archivo)

            df_activos.columns = (
                df_activos.columns
                .astype(str)
                .str.strip()
                .str.lower()
                .str.replace(" ", "_", regex=False)
            )

            st.write(
                "📌 Columnas detectadas:",
                df_activos.columns.tolist()
            )

            required = [
                "numero_identificacion",
                "modalidad"
            ]

            missing = [
                columna
                for columna in required
                if columna not in df_activos.columns
            ]

            if missing:
                st.error(f"❌ Faltan columnas: {missing}")
                st.stop()

            # Eliminar filas sin identificación
            df_activos = df_activos.dropna(
                subset=["numero_identificacion"]
            )

            # Limpiar identificación
            df_activos["numero_identificacion"] = (
                df_activos["numero_identificacion"]
                .astype(str)
                .str.strip()
                .str.replace(r"\.0$", "", regex=True)
            )

            # Limpiar modalidad
            df_activos["modalidad"] = (
                df_activos["modalidad"]
                .fillna("SIN MODALIDAD")
                .astype(str)
                .str.upper()
                .str.strip()
            )

            # Eliminar identificaciones vacías
            df_activos = df_activos[
                df_activos["numero_identificacion"] != ""
            ]

            # Una persona solamente puede aparecer una vez
            df_activos = df_activos.drop_duplicates(
                subset=["numero_identificacion"],
                keep="last"
            )

            st.subheader("📊 Resumen del archivo")

            resumen = (
                df_activos["modalidad"]
                .value_counts()
                .reset_index()
            )

            resumen.columns = [
                "modalidad",
                "cantidad"
            ]

            st.dataframe(
                resumen,
                use_container_width=True,
                hide_index=True
            )

            st.bar_chart(
                resumen.set_index("modalidad")
            )

            st.metric(
                "Total de personas activas en el archivo",
                len(df_activos)
            )

            confirmar = st.checkbox(
                "Confirmo que este archivo reemplazará la lista actual de activos",
                key="confirmar_actualizacion_activos"
            )

            if confirmar and st.button(
                "Actualizar base",
                key="btn_actualizar_activos",
                type="primary"
            ):

                datos_actualizacion = [
                    {
                        "id": str(row["numero_identificacion"]).strip(),
                        "modalidad": str(row["modalidad"]).strip().upper()
                    }
                    for _, row in df_activos.iterrows()
                ]

                with engine.begin() as conn:

                    # Desactivar la lista anterior
                    conn.execute(text("""
                        UPDATE habitante_de_calle
                        SET estado_caso = 'INACTIVO',
                            modalidad = NULL
                        WHERE estado_caso = 'ACTIVO'
                    """))

                    # Activar la nueva lista
                    conn.execute(
                        text("""
                            UPDATE habitante_de_calle
                            SET estado_caso = 'ACTIVO',
                                modalidad = :modalidad
                            WHERE TRIM(
                                CAST(numero_identificacion AS TEXT)
                            ) = :id
                        """),
                        datos_actualizacion
                    )

                    # Verificar cuántos quedaron activos
                    total_activos = conn.execute(text("""
                        SELECT COUNT(*)
                        FROM habitante_de_calle
                        WHERE estado_caso = 'ACTIVO'
                    """)).scalar()

                st.success(
                    f"✅ Base actualizada correctamente. "
                    f"Actualmente hay {total_activos} registros activos."
                )

        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {e}")
    
    with tab9:

        st.title("📄 Historia Integral de Atención")

        usuarios = pd.read_sql("""
            SELECT numero_identificacion, nombres, apellidos
            FROM habitante_de_calle
        """, engine)

        documento = st.selectbox(
            "👤 Seleccione usuario",
            usuarios["numero_identificacion"],
            format_func=lambda x:
                usuarios.loc[usuarios["numero_identificacion"]==x, "nombres"].values[0]
                + " " +
                usuarios.loc[usuarios["numero_identificacion"]==x, "apellidos"].values[0]
        )

        if st.button("📄 Generar PDF"):

            pdf = generar_historia_integral(documento, engine)

            st.download_button(
                "⬇️ Descargar Historia Integral",
                data=pdf,
                file_name=f"historia_{documento}.pdf",
                mime="application/pdf"
            )