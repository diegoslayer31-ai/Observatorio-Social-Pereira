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

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([

    "📊 General",

    "🩺 Enfermería",

    "🏆 Egresos e Impacto",

    "📄 Reportes",

    "➕ Nuevo Registro",

    "📋 Seguimiento Profesional",

    "📈 Seguimiento e Impacto",

    "📄 Informes",

    "📥 Carga Activos"

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

    st.title("📄 Reportes Institucionales")
    st.write("Consolidado analítico del Observatorio Social")

    # =========================
    # KPIs BASE
    # =========================

    total = len(df)

    edad_promedio = round(df["edad"].mean(), 1) if "edad" in df.columns else 0

    # =========================
    # EGRESADOS
    # =========================
    df_egresados = pd.read_sql("""
        SELECT *
        FROM personas_caracterizacion
        WHERE estado_caso = 'EGRESADO'
    """, engine)

    total_egresados = len(df_egresados)
    tasa_egreso = round((total_egresados / total) * 100, 2) if total > 0 else 0

    # =========================
    # INDICADORES
    # =========================
    st.subheader("📊 Indicadores Estratégicos")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("👥 Personas", total)
    col2.metric("📊 Edad promedio", edad_promedio)
    col3.metric("🏆 Egresados", total_egresados)
    col4.metric("📈 Tasa egreso", f"{tasa_egreso}%")

    st.markdown("---")

    # =========================
    # PERFIL
    # =========================
    st.subheader("👤 Perfil Sociodemográfico")

    c1, c2 = st.columns(2)

    with c1:
        if "sexo_al_nacer" in df.columns:
            st.plotly_chart(
                px.pie(df, names="sexo_al_nacer", title="Sexo al nacer"),
                use_container_width=True
            )

    with c2:
        if "edad" in df.columns:
            st.plotly_chart(
                px.histogram(df, x="edad", nbins=15, title="Edad"),
                use_container_width=True
            )

        st.markdown("---")

        # =========================
        # DIVERSIDAD
        # =========================
        st.subheader("🏳️ Diversidad")

        st.plotly_chart(
            px.histogram(
                df,
                x="orientacion_sexual_lgtbi",
                color="orientacion_sexual_lgtbi",
                title="Orientación sexual"
            ),
            use_container_width=True
        )

        if "grupos_etnicos_afro_indigena" in df.columns:
            st.plotly_chart(
                px.histogram(
                    df,
                    x="grupos_etnicos_afro_indigena",
                    color="grupos_etnicos_afro_indigena",
                    title="Grupos étnicos"
                ),
                use_container_width=True
            )

        st.markdown("---")

        # =========================
        # IMPACTO
        # =========================
        st.subheader("🏆 Impacto Institucional")

        col1, col2 = st.columns(2)
        col1.metric("Egresados", total_egresados)
        col2.metric("Tasa Egreso", f"{tasa_egreso}%")

            # =========================
        # HALLAZGOS
        # =========================

        st.subheader("📋 Hallazgos")

        hallazgos = []

        if edad_promedio > 50:
            hallazgos.append("Envejecimiento poblacional.")

        if tasa_egreso < 10:
            hallazgos.append("Baja tasa de egreso.")

        if len(hallazgos) == 0:
            st.success("Sin alertas relevantes.")
        else:
            for h in hallazgos:
                st.warning(h)

        st.markdown("---")

        # =========================
        # CONCLUSIÓN
        # =========================
        st.subheader("📝 Conclusión")

        st.info(f"""
        Total: {total}
        Egresados: {total_egresados}
        Tasa: {tasa_egreso}%
        Edad promedio: {edad_promedio}
        """)

        st.markdown("---")

    # ==================================
    # PDF EJECUTIVO OBSERVATORIO SOCIAL
    # ==================================

    st.markdown("---")

    st.subheader("📄 Informe Ejecutivo Institucional")

    if st.button("📥 Generar Informe Ejecutivo"):

        try:

            archivo = "Informe_Observatorio_Social.pdf"

            doc = SimpleDocTemplate(
                archivo,
                pagesize=letter
            )

            styles = getSampleStyleSheet()

            styles["Title"].textColor = colors.darkblue

            styles["Heading2"].textColor = colors.darkred

            contenido = []

            # ======================
            # PORTADA
            # ======================

            contenido.append(
                Paragraph(
                    "OBSERVATORIO SOCIAL DE PEREIRA",
                    styles["Title"]
                )
            )

            contenido.append(
                Paragraph(
                    "Informe Ejecutivo Institucional",
                    styles["Heading2"]
                )
            )

            contenido.append(
                Spacer(1,15)
            )

            # ======================
            # RESUMEN
            # ======================

            contenido.append(
                Paragraph(
                    f"Total personas caracterizadas: {total}",
                    styles["BodyText"]
                )
            )

            contenido.append(
                Paragraph(
                    f"Edad promedio: {edad_promedio}",
                    styles["BodyText"]
                )
            )

            contenido.append(
                Paragraph(
                    f"Egresados: {total_egresados}",
                    styles["BodyText"]
                )
            )

            contenido.append(
                Paragraph(
                    f"Tasa de egreso: {tasa_egreso}%",
                    styles["BodyText"]
                )
            )

            contenido.append(
                Spacer(1,20)
            )

            # ======================
            # TABLA
            # ======================

            datos = [

                ["Indicador","Valor"],

                ["Personas",total],

                ["Edad promedio",edad_promedio],

                ["Egresados",total_egresados],

                ["Tasa egreso",f"{tasa_egreso}%"]

            ]

            tabla = Table(datos)

            tabla.setStyle(

                TableStyle([

                    ("BACKGROUND",(0,0),(-1,0),colors.darkblue),

                    ("TEXTCOLOR",(0,0),(-1,0),colors.white),

                    ("GRID",(0,0),(-1,-1),1,colors.black),

                    ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold")

                ])

            )

            contenido.append(tabla)

            contenido.append(
                Spacer(1,20)
            )

            # =====================================
            # EDAD
            # =====================================

            if "edad" in df.columns:

                fig = px.histogram(
                    df,
                    x="edad",
                    title="Distribución de edad"
                )

                fig.write_image(
                    "edad.png",
                    engine="kaleido"
                )

                contenido.append(

                    Paragraph(
                        "Distribución por edad",
                        styles["Heading2"]
                    )

                )

                contenido.append(

                    Image(
                        "edad.png",
                        width=450,
                        height=250
                    )

                )

                edad_media = round(
                    df["edad"].mean(),
                    1
                )

                if edad_media >= 50:

                    conclusion = (

                        f"La población presenta una edad promedio de {edad_media} años, evidenciando un proceso de envejecimiento poblacional."

                    )

                elif edad_media >= 30:

                    conclusion = (

                        f"La población presenta una edad promedio de {edad_media} años, predominando la población adulta."

                    )

                else:

                    conclusion = (

                        f"La población presenta una edad promedio de {edad_media} años, con predominio de población joven."

                    )

                contenido.append(

                    Paragraph(
                        conclusion,
                        styles["BodyText"]
                    )

                )

                contenido.append(
                    Spacer(1,15)
                )

            # =====================================
            # SEXO
            # =====================================

            if "sexo_al_nacer" in df.columns:

                fig = px.pie(
                    df,
                    names="sexo_al_nacer",
                    title="Sexo al nacer"
                )

                fig.write_image(
                    "sexo.png",
                    engine="kaleido"
                )

                contenido.append(

                    Paragraph(
                        "Sexo al nacer",
                        styles["Heading2"]
                    )

                )

                contenido.append(

                    Image(
                        "sexo.png",
                        width=350,
                        height=250
                    )

                )

                principal = (
                    df["sexo_al_nacer"]
                    .value_counts()
                    .idxmax()
                )

                porcentaje = round(

                    (
                        df["sexo_al_nacer"]
                        .value_counts(normalize=True)
                        .max()

                    ) * 100,

                    1

                )

                contenido.append(

                    Paragraph(

                        f"Predomina la población {principal.lower()} con una representación del {porcentaje}% del total.",

                        styles["BodyText"]

                    )

                )

                contenido.append(
                    Spacer(1,15)
                )

            # =====================================
            # NIVEL EDUCATIVO
            # =====================================

            if "nivel_educativo" in df.columns:

                fig = px.histogram(

                    df,

                    x="nivel_educativo",

                    title="Nivel educativo"

                )

                fig.write_image(

                    "educacion.png",

                    engine="kaleido"

                )

                contenido.append(

                    Paragraph(

                        "Nivel educativo",

                        styles["Heading2"]

                    )

                )

                contenido.append(

                    Image(

                        "educacion.png",

                        width=450,

                        height=250

                    )

                )

                principal = (

                    df["nivel_educativo"]

                    .value_counts()

                    .idxmax()

                )

                contenido.append(

                    Paragraph(

                        f"El nivel educativo predominante corresponde a {principal.lower()}, lo que orienta las estrategias de inclusión social y laboral.",

                        styles["BodyText"]

                    )

                )

                contenido.append(
                    Spacer(1,15)
                )

            # =====================================
            # SEGURIDAD EN SALUD
            # =====================================

            if "tipo_seguridad_salud" in df.columns:

                fig = px.histogram(

                    df,

                    x="tipo_seguridad_salud",

                    title="Seguridad en salud"

                )

                fig.write_image(

                    "salud.png",

                    engine="kaleido"

                )

                contenido.append(

                    Paragraph(

                        "Seguridad en salud",

                        styles["Heading2"]

                    )

                )

                contenido.append(

                    Image(

                        "salud.png",

                        width=450,

                        height=250

                    )

                )

                principal = (

                    df["tipo_seguridad_salud"]

                    .value_counts()

                    .idxmax()

                )

                contenido.append(

                    Paragraph(

                        f"El régimen predominante es {principal.lower()}, aspecto relevante para orientar la gestión institucional en salud.",

                        styles["BodyText"]

                    )

                )

            # =====================================
            # CONCLUSIONES GENERALES
            # =====================================

            contenido.append(
                PageBreak()
            )

            contenido.append(

                Paragraph(

                    "CONCLUSIONES GENERALES",

                    styles["Heading2"]

                )

            )

            contenido.append(

                Paragraph(

                    "La información consolidada permite orientar la toma de decisiones basadas en evidencia para fortalecer las estrategias de intervención social.",

                    styles["BodyText"]

                )

            )

            # =====================================
            # CREAR PDF
            # =====================================

            doc.build(contenido)

            with open(

                archivo,

                "rb"

            ) as f:

                st.download_button(

                    "⬇️ Descargar PDF",

                    data=f,

                    file_name=archivo,

                    mime="application/pdf"

                )

            st.success(

                "✅ Informe generado correctamente"

            )

        except Exception as e:

            st.error(

                f"Error: {e}"

            )
            # =========================
            # NUEVO REGISTRO
            # =========================

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
    "Documentación y ciudadanía":[
        "Identificación de documentos",
        "Inicio de trámite",
        "Gestión institucional",
        "Documento entregado"
    ],
    "Salud mental":[
        "Valoración inicial",
        "Intervención psicológica",
        "Seguimiento clínico",
        "Estabilización"
    ],
    "Tratamiento consumo SPA":[
        "Motivación al cambio",
        "Ingreso a tratamiento",
        "Adherencia",
        "Prevención de recaídas"
    ],
    "Empleabilidad":[
        "Perfilamiento laboral",
        "Capacitación",
        "Búsqueda de empleo",
        "Vinculación laboral"
    ],
    "Vivienda":[
        "Diagnóstico habitacional",
        "Gestión de subsidio",
        "Asignación",
        "Estabilización habitacional"
    ],
    "Red de apoyo":[
    "Identificación de familiares",
    "Primer contacto",
    "Fortalecimiento de vínculos",
    "Seguimiento",
    "Red consolidada"
    ],

    "Educación":[
        "Diagnóstico educativo",
        "Gestión de matrícula",
        "Inicio de formación",
        "Seguimiento académico",
        "Permanencia"
    ],

    "Vivienda":[
        "Diagnóstico habitacional",
        "Gestión institucional",
        "Asignación",
        "Seguimiento",
        "Estabilización"
    ],

    "Proyecto de vida":[
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
    df_profesionales = pd.read_sql("""

        SELECT id,nombre,rol

        FROM profesionales

        ORDER BY nombre

    """, engine)

    df_profesionales["label"]=(

        df_profesionales["nombre"]

        +" ("

        +df_profesionales["rol"]

        +")"

    )
    st.subheader("🔎 Buscar usuario")

    busqueda = st.text_input(

        "Nombre, apellido o documento"

    )

    df_busqueda = df.copy()

    if busqueda:

        df_busqueda = df_busqueda[

            df_busqueda["nombres"]

            .astype(str)

            .str.contains(

                busqueda,

                case=False,

                na=False

            )

            |

            df_busqueda["apellidos"]

            .astype(str)

            .str.contains(

                busqueda,

                case=False,

                na=False

            )

            |

            df_busqueda["numero_identificacion"]

            .astype(str)

            .str.contains(

                busqueda,

                na=False

            )

        ]

    usuario_sel=None

    if not df_busqueda.empty:

        usuario_sel=st.selectbox(

            "Seleccione usuario",

            df_busqueda[

                "numero_identificacion"

            ],

            format_func=lambda x:

            (

                df_busqueda[

                    df_busqueda[

                        "numero_identificacion"

                    ]==x

                ]

                [["nombres","apellidos"]]

                .astype(str)

                .agg(

                    " ".join,

                    axis=1

                )

                .values[0]

            )

        )
    if usuario_sel:
    
        usuario = pd.read_sql(f"""

            SELECT *

            FROM habitante_de_calle

            WHERE numero_identificacion='{usuario_sel}'

        """, engine)

        datos=usuario.iloc[0]

        st.divider()
        
        c1,c2,c3,c4=st.columns(4)

        c1.metric(

            "Nombre",

            f"{datos['nombres']} {datos['apellidos']}"

        )

        c2.metric(

            "Documento",

            usuario_sel

        )

        c3.metric(

            "Edad",

            datos.get(

                "edad",

                "N/A"

            )

        )

        c4.metric(

            "Objetivos",

            len(

                pd.read_sql(

                    f"""

                    SELECT *

                    FROM pai_objetivos

                    WHERE documento_usuario='{usuario_sel}'

                    """,

                    engine

                )

            )

        )
                # =========================
        # CREAR OBJETIVO PAI
        # =========================

        st.markdown("## ➕ Crear objetivo PAI")

        # =========================
        # OBJETIVO (FUERA DEL FORMULARIO)
        # =========================

        objetivo_tipo = st.selectbox(

            "Objetivo",

            list(mapa_politica.keys()),

            key="objetivo_pai"

        )

        st.info(

            f"🏛️ Política pública: {mapa_politica.get(objetivo_tipo,'')}"

        )

        st.info(

            f"🌍 ODS: {', '.join(mapa_ods.get(objetivo_tipo,[]))}"

        )

        # =========================
        # FORMULARIO
        # =========================

        with st.form("crear_objetivo_pai"):

            subactividades = st.multiselect(

                "🧭 Subactividades sugeridas",

                options=mapa_hitos.get(

                    objetivo_tipo,

                    []

                ),

                default=mapa_hitos.get(

                    objetivo_tipo,

                    []

                )

            )

            objetivo_descripcion = st.text_area(

                "Descripción del objetivo"

            )

            fecha_meta = st.date_input(

                "Fecha meta"

            )

            profesional_id = st.selectbox(

                "Profesional responsable",

                df_profesionales["id"],

                format_func=lambda x:

                df_profesionales[

                    df_profesionales["id"] == x

                ]["label"].values[0]

            )

            prioridad = st.selectbox(

                "Prioridad",

                [

                    "Alta",

                    "Media",

                    "Baja"

                ]

            )

            submit = st.form_submit_button(

                "💾 Guardar objetivo"

            )

        # =========================
        # GUARDAR OBJETIVO
        # =========================

        if submit:

            import json

            from sqlalchemy import text

            politica = mapa_politica.get(

                objetivo_tipo,

                "Restablecimiento de derechos"

            )

            ods = mapa_ods.get(

                objetivo_tipo,

                ["ODS 10"]

            )

            query = text("""

                INSERT INTO pai_objetivos (

                    documento_usuario,

                    objetivo_tipo,

                    objetivo_descripcion,

                    fecha_apertura,

                    fecha_meta,

                    estado,

                    porcentaje_avance,

                    profesional_referente,

                    ods_principal,

                    observaciones,

                    linea_politica,

                    actividades

                )

                VALUES (

                    :documento_usuario,

                    :objetivo_tipo,

                    :objetivo_descripcion,

                    NOW(),

                    :fecha_meta,

                    'Activo',

                    0,

                    :profesional_referente,

                    :ods_principal,

                    '',

                    :linea_politica,

                    :actividades

                )

            """)

            with engine.begin() as conn:

                conn.execute(

                    query,

                    {

                        "documento_usuario": str(usuario_sel),

                        "objetivo_tipo": objetivo_tipo,

                        "objetivo_descripcion": objetivo_descripcion,

                        "fecha_meta": fecha_meta,

                        "profesional_referente": int(profesional_id),

                        "ods_principal": ", ".join(ods),

                        "linea_politica": politica,

                        "actividades": json.dumps(

                            subactividades

                        )

                    }

                )

            st.success(

                "✅ Objetivo PAI creado"

            )

            st.rerun()
            # =========================
        # OBJETIVOS ACTIVOS
        # =========================

        st.divider()

        st.markdown("## 🎯 Objetivos activos")

        objetivos = pd.read_sql(f"""

            SELECT *

            FROM pai_objetivos

            WHERE documento_usuario='{usuario_sel}'

            ORDER BY fecha_apertura DESC

        """, engine)

        import json

        if objetivos.empty:

            st.info(
                "Este usuario aún no tiene objetivos."
            )

        else:

            for _, obj in objetivos.iterrows():
                
                # =========================
                # ACTIVIDADES
                # =========================

                actividades = []

                if obj["actividades"]:

                    try:

                        actividades = json.loads(
                            obj["actividades"]
                        )

                    except:

                        actividades = []

                # =========================
                # AVANCE HITOS
                # =========================

                avance_hitos = []

                if obj["avance_hitos"]:

                    try:

                        avance_hitos = json.loads(
                            obj["avance_hitos"]
                        )

                    except:

                        avance_hitos = []

                # =========================
                # CALCULAR AVANCE
                # =========================

                total = len(actividades)

                if total == 0:

                    avance = 0

                else:

                    avance = round(

                        (

                            len(avance_hitos)

                            / total

                        ) * 100,

                        1

                    )

                # =========================
                # PROFESIONAL
                # =========================

                nombre_profesional = "Sin asignar"

                if obj["profesional_referente"]:

                    profesional = pd.read_sql(

                        f"""

                        SELECT nombre

                        FROM profesionales

                        WHERE id={obj['profesional_referente']}

                        """,

                        engine

                    )

                    if not profesional.empty:

                        nombre_profesional = profesional.iloc[0]["nombre"]

                # =========================
                # MOSTRAR OBJETIVO
                # =========================

                st.markdown(

                    f"### 🎯 {obj['objetivo_tipo']}"

                )

                c1,c2,c3 = st.columns(3)

                c1.metric(

                    "Avance",

                    f"{avance}%"

                )

                c2.metric(

                    "Estado",

                    obj["estado"]

                )

                c3.metric(

                    "ODS",

                    obj["ods_principal"]

                )

                st.caption(

                    f"👨‍⚕️ {nombre_profesional}"

                )

                st.caption(

                    f"🏛️ {obj['linea_politica']}"

                )

                st.write(

                    obj["objetivo_descripcion"]

                )

                st.progress(

                    avance/100

                )
                objetivos = pd.read_sql(

            f"""

            SELECT *

            FROM pai_objetivos

            WHERE documento_usuario='{usuario_sel}'

            """,

            engine

        )

            if not objetivos.empty:

                objetivos_activos = len(

                    objetivos[
                        objetivos["estado"]=="Activo"
                    ]

                )

                objetivos_cumplidos = len(

                    objetivos[
                        objetivos["porcentaje_avance"]>=100
                    ]

                )

                avance_promedio = round(

                    objetivos["porcentaje_avance"]

                    .fillna(0)

                    .mean(),

                    1

                )

                ods_impactados = len(

                    set(

                        ",".join(

                            objetivos["ods_principal"]

                            .fillna("")

                        )

                        .split(",")

                    )

                )

                c1,c2,c3,c4 = st.columns(4)

                c1.metric(

                    "🎯 Activos",

                    objetivos_activos

                )

                c2.metric(

                    "✅ Cumplidos",

                    objetivos_cumplidos

                )

                c3.metric(

                    "📈 Avance promedio",

                    f"{avance_promedio}%"

                )

                c4.metric(

                    "🌍 ODS impactados",

                    ods_impactados

                )

            
                st.divider()
            for actividad in actividades:

                hecho = actividad in avance_hitos

                col1,col2 = st.columns(
                    [0.1,0.9]
                )

                with col1:

                    marcado = st.checkbox(

                        "",

                        value=hecho,

                        key=f"{obj['id']}_{actividad}"

                    )

                with col2:

                    st.write(
                        actividad
                    )

                if marcado:

                    if actividad not in avance_hitos:

                        avance_hitos.append(
                            actividad
                        )

                else:

                    if actividad in avance_hitos:

                        avance_hitos.remove(
                            actividad
                        )
            st.markdown("### 📝 Registrar novedad")

            tipo_novedad = st.selectbox(

                "Actividad realizada",

                actividades,

                key=f"tipo_{obj['id']}"

            )

            descripcion_novedad = st.text_area(

                "Descripción",

                key=f"desc_{obj['id']}"

            )

            evidencia = st.text_input(

                "Evidencia",

                key=f"evid_{obj['id']}"

            )

            guardar_novedad = st.button(

                "💾 Guardar novedad",

                key=f"guardar_{obj['id']}"

            )
            if guardar_novedad:
        
                from sqlalchemy import text

                query_nov = text("""

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

                        :id_objetivo,

                        NOW(),

                        :profesional,

                        :tipo_novedad,

                        :descripcion,

                        :avance_generado,

                        :evidencia

                    )

                """)

                with engine.begin() as conn:

                    conn.execute(

                        query_nov,

                        {

                            "id_objetivo": int(obj["id"]),

                            "profesional": nombre_profesional,

                            "tipo_novedad": tipo_novedad,

                            "descripcion": descripcion_novedad,

                            "avance_generado": avance,

                            "evidencia": evidencia

                        }

                    )

                st.success("Novedad registrada")

                st.rerun()
            from sqlalchemy import text

            query = text("""

            UPDATE pai_objetivos

            SET

            avance_hitos=:avance_hitos,

            porcentaje_avance=:porcentaje_avance

            WHERE id=:id

            """)

        with engine.begin() as conn:

            conn.execute(

                query,

                {

                    "avance_hitos":

                    json.dumps(

                        avance_hitos

                    ),

                    "porcentaje_avance":

                    avance,

                    "id":

                    int(

                        obj["id"]

                    )

                }

            )

            st.divider()
        # =========================
# HISTORIAL NOVEDADES
# =========================

st.markdown("### 🕒 Historial")

novedades = pd.read_sql(

    f"""

    SELECT *

    FROM pai_novedades

    WHERE id_objetivo={obj['id']}

    ORDER BY fecha DESC

    """,

    engine

)

if novedades.empty:

    st.info(

        "Sin novedades registradas"

    )

else:

    for _, nov in novedades.iterrows():

        st.info(

            f"""

            📅 {nov['fecha']}

            👨‍⚕️ {nov['profesional']}

            📌 {nov['tipo_novedad']}

            📝 {nov['descripcion']}

            📂 {nov['evidencia']}

            """

        )
with tab7:

    st.title("📈 Seguimiento e Impacto - Reducción de Riesgos y Daños")

    
with tab8:

    st.header("📄 Informes Gerenciales")

    st.markdown(
        "Seguimiento institucional del Plan de Atención Individual (PAI)"
    )

    st.divider()

    # ==========================
    # FILTROS
    # ==========================

    st.subheader("⚙️ Filtros")

    c1, c2, c3 = st.columns(3)

    with c1:

        fecha_inicio = st.date_input(

            "Fecha inicial"

        )

    with c2:

        fecha_fin = st.date_input(

            "Fecha final"

        )

    with c3:

        profesionales = pd.read_sql("""

            SELECT DISTINCT

            profesional_referente

            FROM pai_objetivos

            WHERE profesional_referente IS NOT NULL

            ORDER BY profesional_referente

        """, engine)

        lista_profesionales = (

            ["Todos"]

            +

            profesionales[
                "profesional_referente"
            ].tolist()

        )

        profesional = st.selectbox(

            "Profesional",

            lista_profesionales

        )
        # ==========================
    # CONSULTA PRINCIPAL
    # ==========================

    if profesional == "Todos":

        consulta = pd.read_sql(f"""

            SELECT

                o.id,

                o.documento_usuario,

                o.objetivo_tipo,

                o.estado,

                o.porcentaje_avance,

                o.linea_politica,

                o.ods_principal,

                o.profesional_referente,

                n.profesional,

                n.fecha,

                n.descripcion

            FROM pai_objetivos o

            LEFT JOIN pai_novedades n

            ON o.id = n.id_objetivo

            WHERE n.fecha

            BETWEEN

            '{fecha_inicio}'

            AND

            '{fecha_fin}'

        """, engine)

    else:

        consulta = pd.read_sql(f"""

            SELECT

                o.id,

                o.documento_usuario,

                o.objetivo_tipo,

                o.estado,

                o.porcentaje_avance,

                o.linea_politica,

                o.ods_principal,

                o.profesional_referente,

                n.profesional,

                n.fecha,

                n.descripcion

            FROM pai_objetivos o

            LEFT JOIN pai_novedades n

            ON o.id = n.id_objetivo

            WHERE o.profesional_referente = '{profesional}'

            AND n.fecha

            BETWEEN

            '{fecha_inicio}'

            AND

            '{fecha_fin}'

        """, engine)
        # ==========================
    # INDICADORES GENERALES
    # ==========================

    if consulta.empty:

        st.warning(

            "No hay información disponible."

        )

    else:

        st.subheader(

            "📊 Indicadores generales"

        )

        usuarios = consulta[

            "documento_usuario"

        ].nunique()

        objetivos = consulta[

            "id"

        ].nunique()

        cumplidos = (

            consulta[
                consulta["estado"]

                == "Cumplido"

            ]["id"]

            .nunique()

        )

        avance = round(

            consulta[

                "porcentaje_avance"

            ].mean(),

            1

        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(

            "Usuarios",

            usuarios

        )

        c2.metric(

            "Objetivos",

            objetivos

        )

        c3.metric(

            "Cumplidos",

            cumplidos

        )

        c4.metric(

            "Avance promedio",

            f"{avance}%"

        )

        st.divider()
        st.divider()

        # ==========================
        # GESTIÓN POR PROFESIONAL
        # ==========================

        st.subheader(
            "👨‍⚕️ Gestión por profesional"
        )

        profesional_df = (

            consulta["profesional_referente"]

            .fillna("Sin asignar")

            .value_counts()

            .reset_index()

        )

        profesional_df.columns = [

            "profesional",

            "cantidad"

        ]

        fig = px.bar(

            profesional_df,

            x="profesional",

            y="cantidad",

            color="cantidad",

            text="cantidad",

            title="Objetivos asignados por profesional"

        )

        fig.update_traces(

            textposition="outside"

        )

        st.plotly_chart(

            fig,

            use_container_width=True

        )

        if not profesional_df.empty:

            top_profesional = profesional_df.iloc[0]

            st.info(

                f"El profesional con mayor carga es "

                f"**{top_profesional['profesional']}** "

                f"con **{top_profesional['cantidad']} objetivos**."

            )

        st.divider()

        # ==========================
        # OBJETIVOS PAI
        # ==========================

        st.subheader(

            "🎯 Objetivos PAI"

        )

        objetivos_df = (

            consulta["objetivo_tipo"]

            .value_counts()

            .reset_index()

        )

        objetivos_df.columns = [

            "objetivo",

            "cantidad"

        ]

        fig = px.bar(

            objetivos_df,

            x="objetivo",

            y="cantidad",

            color="cantidad",

            text="cantidad",

            title="Distribución de objetivos PAI"

        )

        fig.update_traces(

            textposition="outside"

        )

        st.plotly_chart(

            fig,

            use_container_width=True

        )

        if not objetivos_df.empty:

            top_objetivo = objetivos_df.iloc[0]

            st.success(

                f"El objetivo más frecuente es "

                f"**{top_objetivo['objetivo']}**."

            )
            st.divider()

        # ==========================
        # GESTIÓN POR PROFESIONAL
        # ==========================

        st.subheader(
            "👨‍⚕️ Gestión por profesional"
        )

        profesional_df = (

            consulta["profesional_referente"]

            .fillna("Sin asignar")

            .value_counts()

            .reset_index()

        )

        profesional_df.columns = [

            "profesional",

            "cantidad"

        ]

        fig = px.bar(

            profesional_df,

            x="profesional",

            y="cantidad",

            color="cantidad",

            text="cantidad",

            title="Objetivos asignados por profesional"

        )

        fig.update_traces(

            textposition="outside"

        )

        st.plotly_chart(

            fig,

            use_container_width=True

        )
        st.divider()

        # ==========================
        # OBJETIVOS PAI
        # ==========================

        st.subheader(
            "🎯 Objetivos PAI"
        )

        objetivos_df = (

            consulta["objetivo_tipo"]

            .value_counts()

            .reset_index()

        )

        objetivos_df.columns = [

            "objetivo",

            "cantidad"

        ]

        fig = px.bar(

            objetivos_df,

            x="objetivo",

            y="cantidad",

            color="cantidad",

            text="cantidad",

            title="Distribución de objetivos PAI"

        )

        fig.update_traces(

            textposition="outside"

        )

        st.plotly_chart(

            fig,

            use_container_width=True

        )
        st.divider()

        # ==========================
        # POLÍTICA PÚBLICA
        # ==========================

        st.subheader(
            "🏛️ Política pública"
        )

        politica_df = (

            consulta["linea_politica"]

            .fillna("Sin asignar")

            .value_counts()

            .reset_index()

        )

        politica_df.columns = [

            "linea",

            "cantidad"

        ]

        fig = px.pie(

            politica_df,

            names="linea",

            values="cantidad",

            title="Distribución por línea de política pública"

        )

        st.plotly_chart(

            fig,

            use_container_width=True

        )
        st.divider()

        # ==========================
        # ODS
        # ==========================

        st.subheader(
            "🌍 Objetivos de Desarrollo Sostenible"
        )

        ods_principal_df = (

            consulta["ods_principal"]

            .fillna("Sin asignar")

            .value_counts()

            .reset_index()

        )

        ods_principal_df.columns = [

            "ods",

            "cantidad"

        ]

        fig = px.bar(

            ods_principal_df,

            x="ods",

            y="cantidad",

            color="cantidad",

            text="cantidad",

            title="Distribución por ODS"

        )

        fig.update_traces(

            textposition="outside"

        )

        st.plotly_chart(

            fig,

            use_container_width=True

        )
        st.divider()

        # ==========================
        # TENDENCIA MENSUAL
        # ==========================

        st.subheader(
            "📅 Tendencia mensual"
        )

        tendencia = pd.read_sql("""

            SELECT

                DATE_TRUNC(

                    'month',

                    fecha

                ) AS mes,

                COUNT(*) AS cantidad

            FROM pai_novedades

            GROUP BY mes

            ORDER BY mes

        """, engine)

        if not tendencia.empty:

            fig = px.line(

                tendencia,

                x="mes",

                y="cantidad",

                markers=True,

                title="Novedades registradas por mes"

            )

            st.plotly_chart(

                fig,

                use_container_width=True

            )

        else:

            st.info(

                "La tendencia mensual aparecerá cuando existan novedades."

            )
        st.divider()

        # ==========================
        # DETALLE OPERATIVO
        # ==========================

        st.subheader(
            "📋 Detalle operativo"
        )

        st.dataframe(

            consulta,

            use_container_width=True

        )
        st.divider()

        st.subheader(
            "📥 Exportación"
        )

        st.info(
            """
            Próximamente este módulo permitirá exportar:

            • Informe mensual

            • Informe por profesional

            • Informe institucional

            • Informe por línea de política pública

            • Informe por ODS

            """
        )
# =====================================
# TAB 9 - CARGA MASIVA ACTUALIZADA
# =====================================

with tab9:

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
                .str.replace(" ", "_")
            )

            st.write("📌 Columnas detectadas:", df_activos.columns.tolist())

            required = ["numero_identificacion", "modalidad"]

            missing = [c for c in required if c not in df_activos.columns]

            if missing:
                st.error(f"❌ Faltan columnas: {missing}")
                st.stop()

            df_activos["numero_identificacion"] = (
                df_activos["numero_identificacion"].astype(str).str.strip()
            )

            df_activos["modalidad"] = (
                df_activos["modalidad"].astype(str).str.upper().str.strip()
            )

            df_activos = df_activos.drop_duplicates(subset=["numero_identificacion"])

            # resumen
            st.subheader("📊 Modalidad")
            resumen = df_activos["modalidad"].value_counts().reset_index()
            resumen.columns = ["modalidad", "cantidad"]

            st.dataframe(resumen)
            st.bar_chart(resumen.set_index("modalidad"))

            confirmar = st.checkbox("Confirmo actualización")

            if confirmar and st.button("Actualizar base"):

                with engine.begin() as conn:

                    for _, row in df_activos.iterrows():

                        doc = str(row["numero_identificacion"]).strip()
                        modalidad = str(row["modalidad"]).strip().upper()

                        conn.execute(text("""
                            UPDATE habitante_de_calle
                            SET estado_caso = 'ACTIVO',
                                modalidad = :modalidad
                            WHERE TRIM(CAST(numero_identificacion AS TEXT)) = :id
                        """), {
                            "modalidad": modalidad,
                            "id": doc
                        })

                st.success("✅ Base actualizada correctamente")

        except Exception as e:
            st.error(f"❌ Error: {e}")
