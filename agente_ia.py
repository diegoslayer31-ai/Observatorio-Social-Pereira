import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text

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
def formulario_registro():
    
    st.subheader("🔐 Registro de usuarios")

    clave = st.text_input("Ingrese la contraseña", type="password")

    if clave == "Pereira2026":

        st.success("Acceso autorizado")

        with st.form("registro"):

            nombres = st.text_input("Nombres")
            apellidos = st.text_input("Apellidos")
            sexo = st.selectbox("Sexo", ["Masculino", "Femenino"])
            edad = st.number_input("Edad", 0, 120, 18)

            tipo_id = st.selectbox("Tipo ID", ["CC", "TI", "CE", "PEP", "Otro"])
            numero_id = st.text_input("Número de identificación")

            etnia = st.selectbox("Etnia", ["Ninguno", "Afrodescendiente", "Indígena", "Mestizo"])
            discapacidad = st.selectbox("Discapacidad", ["No", "Sí"])

            migracion = 1 if st.selectbox("Migración", ["NO", "SI"]) == "SI" else 0

            educacion = st.selectbox(
                "Educación",
                ["Ninguno", "Primaria", "Secundaria", "Técnico", "Tecnólogo", "Universitario"]
            )

            barrio = st.text_input("Barrio")
            comuna = st.text_input("Comuna")
            telefono = st.text_input("Teléfono")

            consumo = st.selectbox(
                "Consumo",
                ["No", "Marihuana", "Cocaína", "Bazuco", "Alcohol", "Heroína", "Policonsumo"]
            )

            enfermedad = st.selectbox("Enfermedad mental", ["No", "Sí"])
            modalidad = st.selectbox("Modalidad", ["GRANJA", "URBANO"])

            guardar = st.form_submit_button("Guardar")

        if guardar:

            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO habitante_de_calle (
                        nombres, apellidos, sexo_al_nacer, edad,
                        tipo_de_identificacion, numero_de_identificacion,
                        grupos_etnicos_afro_indigena, personas_con_discapacidad,
                        indicador_migracion, nivel_educativo_que_tiene_o_cursa,
                        barrio_o_vereda_de_residencia, comuna_o_corregimiento_de_residencia,
                        telefono_y_o_celular, tipo_de_consumo, enfermedad_mental,
                        estado_caso, modalidad
                    )
                    VALUES (
                        :nombres, :apellidos, :sexo, :edad,
                        :tipo_id, :numero_id,
                        :etnia, :discapacidad,
                        :migracion, :educacion,
                        :barrio, :comuna,
                        :telefono, :consumo, :enfermedad,
                        'ACTIVO', :modalidad
                    )
                """), locals())

            st.success("Usuario registrado correctamente")
if st.session_state.page == "registro":
    formulario_registro()

    if st.button("⬅️ Volver"):
        st.session_state.page = "home"
        st.rerun()

    st.stop()
# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Observatorio Social Asociación Ciudad Futuro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
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
# =====================================
# SIDEBAR (VA ARRIBA DEL ROUTER)
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

    # BOTONES DE NAVEGACIÓN (IMPORTANTE)
    if st.button("🏠 Inicio"):
        st.session_state.page = "home"
        st.rerun()

    if st.button("⚙️ Gestión usuarios"):
        st.session_state.page = "gestion_usuarios"
        st.rerun()

if st.session_state.page == "home":
    
    st.title("🏠 Dashboard principal")
    # TODO observatorio completo

elif st.session_state.page == "gestion_usuarios":
    
    st.title("⚙️ Gestión de usuarios")

    # =========================
    # 1. FORMULARIO REGISTRO
    # =========================
    st.subheader("➕ Registrar usuario")

    with st.form("form_usuario"):

        nombres = st.text_input("Nombres")
        apellidos = st.text_input("Apellidos")

        numero_id = st.text_input("Número de identificación")

        estado = st.selectbox(
            "Estado del usuario",
            ["ACTIVO", "INACTIVO"]
        )

        guardar = st.form_submit_button("Guardar usuario")

    if guardar:

        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO usuarios (
                        nombres,
                        apellidos,
                        numero_de_identificacion,
                        estado
                    )
                    VALUES (
                        :nombres,
                        :apellidos,
                        :numero_id,
                        :estado
                    )
                """), {
                    "nombres": nombres,
                    "apellidos": apellidos,
                    "numero_id": numero_id,
                    "estado": estado
                })

            st.success("Usuario guardado correctamente")

        except Exception as e:
            st.error(f"Error guardando usuario: {e}")

    st.divider()

    # =========================
    # 2. LISTADO DE USUARIOS (SEGURO)
    # =========================
    st.subheader("📋 Usuarios registrados")

    try:
        df_usuarios = pd.read_sql("""
            SELECT
                nombres,
                apellidos,
                numero_de_identificacion,
                estado
            FROM usuarios
            ORDER BY nombres ASC
        """, engine)

        st.dataframe(df_usuarios, use_container_width=True)

    except Exception as e:
        st.error("No se pudo cargar la tabla de usuarios")
        st.caption(str(e))

    st.divider()

    # =========================
    # 3. INACTIVAR USUARIO
    # =========================
    st.subheader("🚫 Inactivar usuario")

    try:
        df_lista = pd.read_sql("""
            SELECT numero_de_identificacion, nombres, apellidos, estado
            FROM usuarios
            WHERE estado = 'ACTIVO'
        """, engine)

        usuario_sel = st.selectbox(
            "Selecciona usuario",
            df_lista["numero_de_identificacion"].tolist()
        )

        if st.button("Inactivar"):

            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE usuarios
                    SET estado = 'INACTIVO'
                    WHERE numero_de_identificacion = :id
                """), {"id": usuario_sel})

            st.success("Usuario inactivado")
            st.rerun()

    except Exception as e:
        st.warning("No hay usuarios o la tabla no existe aún")
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
# FUNCIÓN CONSOLIDADA 
# =========================

def peso_consumo(x):
    x = str(x).lower().strip()

    if x in ["no", "ninguno", "nan", ""]:
        return 0

    if "heroina" in x or "heroína" in x:
        return 5
    elif "policonsumo" in x:
        return 4
    elif "bazuco" in x:
        return 4
    elif "alcohol" in x:
        return 4
    elif "coca" in x:
        return 3
    elif "marihuana" in x:
        return 1
    else:
        return 1
# =========================
# LIMPIEZA / FEATURES
# =========================
df["score_vulnerabilidad"] = ...
df["nivel_riesgo"] = ...

# =========================
# FUNCIONES AUXILIARES 
# =========================
def generar_resumen(df):

    total = len(df)
    score = round(df["score_vulnerabilidad"].mean(), 2)
    criticos = len(df[df["nivel_riesgo"] == "Crítico"])
    alto = len(df[df["nivel_riesgo"] == "Alto"])
    medio = len(df[df["nivel_riesgo"] == "Medio"])

    consumo_top = df["tipo_consumo"].value_counts().idxmax()
    etnia_top = df["grupos_etnicos_afro_indigena"].value_counts().idxmax()

    return {
        "total": total,
        "score": score,
        "criticos": criticos,
        "alto": alto,
        "medio": medio,
        "consumo_top": consumo_top,
        "etnia_top": etnia_top
    }

# =========================
# APLICAR PESO
# =========================

df["v_consumo"] = df["tipo_consumo"].fillna("no").astype(str).apply(peso_consumo)
# =========================
# LIMPIAR SEXO
# =========================
if "sexo_al_nacer" in df.columns:
    df["sexo_al_nacer"] = (
        df["sexo_al_nacer"]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace(
            {
                "M": "Masculino",
                "F": "Femenino",
                "MASCULINO": "Masculino",
                "FEMENINO": "Femenino",
            }
        )
    )
with st.sidebar:

    st.header("🏛️ Sistema de Atención")

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
            df_urbano["nombres"].astype(str) + " " + df_urbano["apellidos"].astype(str)
        )

        st.dataframe(df_urbano[["nombre", "numero_identificacion"]], use_container_width=True)

    # =========================
    # USUARIOS GRANJA
    # =========================
    with st.expander("🌱 Usuarios GRANJA activos"):

        df_granja = df[
            (df["modalidad"] == "GRANJA") &
            (df["estado_caso"] == "ACTIVO")
        ][["nombres", "apellidos", "numero_identificacion"]].copy()

        df_granja["nombre"] = (
            df_granja["nombres"].astype(str) + " " + df_granja["apellidos"].astype(str)
        )

        st.dataframe(df_granja[["nombre", "numero_identificacion"]], use_container_width=True)

    st.divider()
# =========================
# ÍNDICE DE VULNERABILIDAD
# =========================

df["v_consumo"] = df["tipo_consumo"].notna().astype(int)
df["v_salud"] = (df["enfermedad_mental"] != "No").astype(int)
df["v_discapacidad"] = (
    df["personas_con_discapacidad"].isin(["SI", "Sí", "Si"]).astype(int)
)
df["v_migracion"] = df["indicador_migracion"].notna().astype(int)

df["indice_vulnerabilidad"] = (
    df["v_consumo"] + df["v_salud"] + df["v_discapacidad"] + df["v_migracion"]
)

df["score_vulnerabilidad"] = (df["indice_vulnerabilidad"] / 4) * 100

df["nivel_riesgo"] = pd.cut(
    df["score_vulnerabilidad"],
    bins=[0, 25, 50, 75, 100],
    labels=["Bajo", "Medio", "Alto", "Crítico"],
)


def color_riesgo(r):
    if r == "Crítico":
        return "🔴 Crítico"
    elif r == "Alto":
        return "🟠 Alto"
    elif r == "Medio":
        return "🟡 Medio"
    else:
        return "🟢 Bajo"


df["semáforo"] = df["nivel_riesgo"].apply(color_riesgo)


# =========================
# KPIs
# =========================
st.header("📊 Indicadores Clave")

# Asegúrate de usar SOLO un dataframe base
df_kpi = df.copy()

col1, col2, col3 = st.columns(3)
col4, col5, col6 = st.columns(3)

col1.metric(
    "Score promedio",
    round(df_kpi["score_vulnerabilidad"].mean(), 2)
)

col2.metric(
    "Índice promedio",
    round(df_kpi["indice_vulnerabilidad"].mean(), 2)
)

col3.metric(
    "Casos críticos",
    len(df_kpi[df_kpi["nivel_riesgo"] == "Crítico"])
)

col4.metric(
    "Total registros",
    len(df_kpi)
)
# KPIs
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12, tab13, tab14 = st.tabs([
    "📊 General",
    "⚠️ Vulnerabilidad",
    "🚬 Consumo",
    "🧠 Salud Mental",
    "🌎 Territorio",
    "🎓 Educación",
    "🚦 Semáforo",
    "🤖 IA",
    "🏆 Egresos e Impacto",
    "📄 Reportes",
    "➕ Nuevo Registro",
    "📋 Seguimiento Profesional",
    "📈 Seguimiento e Impacto",
    "📥 Carga Activos"   # 👈 NUEVO
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
    # ETNIA VS CONSUMO
    # =====================================

    st.subheader("💊 Etnia vs Consumo")

    if (
        "grupos_etnicos" in df.columns
        and
        "tipo_consumo" in df.columns
    ):

        tabla = pd.crosstab(
            df["grupos_etnicos"],
            df["tipo_consumo"]
        )

        st.dataframe(
            tabla,
            use_container_width=True
        )

    else:

        st.warning(
            "No existen columnas para etnia vs consumo."
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
# =========================
# TAB VULNERABILIDAD
# =========================
with tab2:

    st.subheader("🚦 Distribución de Vulnerabilidad Social")

    fig = px.histogram(
        df,
        x="score_vulnerabilidad",
        nbins=20,
        color="nivel_riesgo"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    # =========================
    # RESUMEN EJECUTIVO
    # =========================
    criticos = len(
        df[df["nivel_riesgo"] == "Crítico"]
    )

    st.error(
        f"⚠️ Se identifican {criticos} personas en nivel crítico de vulnerabilidad social."
    )

    # =========================
    # METODOLOGÍA
    # =========================
    with st.expander("📘 Metodología del Score de Vulnerabilidad"):

        st.markdown("""
        ### ¿Qué mide este indicador?

        El **Score de Vulnerabilidad Social** estima el nivel de acumulación de factores de riesgo presentes en cada persona atendida.

        ### Variables consideradas

        - Consumo de sustancias psicoactivas
        - Enfermedad mental reportada
        - Situación de discapacidad
        - Condición migratoria

        ### Escala de clasificación

        | Puntaje | Nivel |
        |----------|----------|
        | 0 - 25 | 🟢 Bajo |
        | 26 - 50 | 🟡 Medio |
        | 51 - 75 | 🟠 Alto |
        | 76 - 100 | 🔴 Crítico |

        ### Interpretación

        Un puntaje más alto indica una mayor acumulación de vulnerabilidades sociales y sanitarias, por lo que la persona requiere una prioridad superior en los procesos de intervención, seguimiento y acompañamiento institucional.

        **Este indicador no constituye un diagnóstico clínico**, sino una herramienta de focalización para la toma de decisiones.
        """)

    # =========================
    # TABLA RESUMEN
    # =========================
    st.subheader("📊 Distribución por nivel de riesgo")

    resumen = (
        df["nivel_riesgo"]
        .value_counts()
        .reset_index()
    )

    resumen.columns = ["Nivel", "Cantidad"]

    st.dataframe(
        resumen,
        use_container_width=True
    )
    # =========================
    # TOP 20 CASOS CRÍTICOS
    # =========================
    st.subheader("🚨 Casos Prioritarios")

    top_criticos = df.sort_values(
        "score_vulnerabilidad",
        ascending=False
    )

    columnas_mostrar = [
        "nombres",
        "apellidos",
        "score_vulnerabilidad",
        "nivel_riesgo"
    ]

    columnas_existentes = [
        c for c in columnas_mostrar
        if c in top_criticos.columns
    ]

    st.dataframe(
        top_criticos[columnas_existentes].head(20),
        use_container_width=True
    )
# =========================
# TAB CONSUMO
# =========================
with tab3:

    st.subheader("💊 Tipos de consumo")

    consumo_df = (
        df["tipo_consumo"]
        .value_counts()
        .reset_index()
    )

    consumo_df.columns = ["consumo", "cantidad"]

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
# =========================
# TAB SALUD MENTAL
# =========================
with tab4:

    st.subheader("🧠 Salud mental")

    mental_df = (
        df["enfermedad_mental"]
        .value_counts()
        .reset_index()
    )

    mental_df.columns = ["condicion", "cantidad"]

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
        "La presencia de salud mental puede aumentar la permanencia en calle y la vulnerabilidad social."
    )
# =========================
# TAB TERRITORIO
# =========================
with tab5:

    st.subheader("📍 Departamento de procedencia")

    if "departamento_procedencia" in df.columns:

        # =========================
        # LIMPIEZA BÁSICA
        # =========================
        dep_df = (
            df["departamento_procedencia"]
            .fillna("Sin dato")
            .astype(str)
            .str.strip()
            .value_counts()
            .reset_index()
        )

        dep_df.columns = ["departamento", "cantidad"]

        # =========================
        # GRÁFICA (BARRAS)
        # =========================
        fig_dep = px.bar(
            dep_df,
            x="departamento",
            y="cantidad",
            color="cantidad",
            text="cantidad",
            title="🌍 Personas por departamento de procedencia"
        )

        fig_dep.update_traces(textposition="outside")
        fig_dep.update_layout(xaxis_tickangle=-45)

        st.plotly_chart(fig_dep, use_container_width=True)

        # =========================
        # TABLA OPCIONAL
        # =========================
        with st.expander("📋 Ver tabla detallada"):
            st.dataframe(dep_df)

    else:
        st.warning("No existe la columna 'departamento_procedencia' en el dataset")
# =========================
# TAB EDUCACIÓN
# =========================
with tab6:

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

        edu.columns = ["nivel", "conteo"]

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

        fig_edu.update_traces(textposition="outside")
        fig_edu.update_layout(xaxis_tickangle=-45)

        st.plotly_chart(fig_edu, use_container_width=True)

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
        with st.expander("📋 Ver tabla detallada"):
            st.dataframe(edu)

    else:
        st.warning("No existe la columna 'nivel_educativo' en el dataset")
# =========================
# TAB SEMÁFORO SOCIAL
# =========================
with tab7:

    st.subheader("👥 Semáforo social")

    # =========================
    # NOMBRE COMPLETO
    # =========================
    df["nombre_completo"] = (
        df["nombres"].astype(str).str.strip()
        + " "
        + df["apellidos"].astype(str).str.strip()
    )

    # =========================
    # NORMALIZAR SEMÁFORO
    # =========================
    if "semáforo" not in df.columns and "semaforo" in df.columns:
        df["semáforo"] = df["semaforo"]

    # =========================
    # MAPEO REAL DE COLUMNAS 
    # =========================
    columnas = [
        "semáforo",
        "score_vulnerabilidad",
        "nombre_completo",
        "sexo_al_nacer",
        "edad",
        "tipo_consumo",
        "nivel_educativo",
        "barrio_vereda"
    ]

    # =========================
    # FILTRO
    # =========================
    columnas_existentes = [c for c in columnas if c in df.columns]

    # =========================
    # VALIDACIÓN SEGURA
    # =========================
    if columnas_existentes:

        st.dataframe(
            df[columnas_existentes]
            .sort_values(
                by="score_vulnerabilidad",
                ascending=False
            ),
            use_container_width=True
        )

    else:
        st.warning("No se encontraron columnas para el semáforo social")
        st.write("Columnas disponibles:", df.columns.tolist())

    # =========================
    # INTERPRETACIÓN
    # =========================
    st.info(
        "El semáforo social prioriza personas con mayor acumulación de riesgos."
    )

    st.error(
        "🔴 Crítico = atención inmediata | 🟠 Alto = intervención prioritaria"
    )
# =========================
# TAB IA
# =========================
with tab8:

    st.subheader("🤖 Agente IA")

    st.warning("""
    El módulo de Inteligencia Artificial se encuentra
    temporalmente deshabilitado en la versión web.

    Esta funcionalidad requiere un servidor Ollama local.
    """)
with tab9:

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
with tab10:

    st.title("📄 Reportes Institucionales")
    st.write("Consolidado analítico del Observatorio Social")

    # =========================
    # KPIs BASE
    # =========================
    total = len(df)
    score = round(df["score_vulnerabilidad"].mean(), 2)
    criticos = len(df[df["nivel_riesgo"] == "Crítico"])
    edad_promedio = round(df["edad"].mean(), 1)

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

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("👥 Personas", total)
    col2.metric("⚠️ Críticos", criticos)
    col3.metric("📈 Score", score)
    col4.metric("🏆 Egresados", total_egresados)
    col5.metric("📊 Tasa", f"{tasa_egreso}%")

    st.markdown("---")

    # =========================
    # PERFIL
    # =========================
    st.subheader("👤 Perfil Sociodemográfico")

    c1, c2 = st.columns(2)

    with c1:
        st.plotly_chart(
            px.pie(df, names="sexo_al_nacer", title="Sexo al nacer"),
            use_container_width=True
        )

    with c2:
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

    if criticos > total * 0.25:
        hallazgos.append("Alta concentración de riesgo crítico.")

    if score > 7:
        hallazgos.append("Vulnerabilidad elevada.")

    if tasa_egreso < 10:
        hallazgos.append("Baja tasa de egreso.")

    if edad_promedio > 50:
        hallazgos.append("Envejecimiento poblacional.")

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
    Score: {score}
    Críticos: {criticos}
    Egresados: {total_egresados}
    Tasa: {tasa_egreso}%
    """)

    st.markdown("---")

    # =========================
    # PDF AVANZADO
    # =========================
    st.subheader("📄 Informe PDF Avanzado")

    if st.button("📥 Generar PDF completo"):

        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.pagesizes import letter
        import matplotlib.pyplot as plt

        styles = getSampleStyleSheet()
        contenido = []
        archivo = "informe_observatorio.pdf"
        doc = SimpleDocTemplate(archivo, pagesize=letter)

        # =========================
        # GRAFICO 1 (EDAD)
        # =========================
        fig1 = px.histogram(df, x="edad", title="Distribución de edad")
        fig1.write_image("edad.png")

        # =========================
        # GRAFICO 2 (SEXO)
        # =========================
        fig2 = px.pie(df, names="sexo_al_nacer", title="Sexo")
        fig2.write_image("sexo.png")

        # =========================
        # CONTENIDO PDF
        # =========================
        contenido.append(Paragraph("INFORME EJECUTIVO - OBSERVATORIO SOCIAL", styles["Title"]))
        contenido.append(Spacer(1, 12))

        contenido.append(Paragraph(f"Personas: {total}", styles["BodyText"]))
        contenido.append(Paragraph(f"Score: {score}", styles["BodyText"]))
        contenido.append(Paragraph(f"Críticos: {criticos}", styles["BodyText"]))
        contenido.append(Paragraph(f"Egresados: {total_egresados}", styles["BodyText"]))
        contenido.append(Paragraph(f"Tasa: {tasa_egreso}%", styles["BodyText"]))

        contenido.append(Spacer(1, 12))

        contenido.append(Paragraph("ANÁLISIS GENERAL", styles["Heading2"]))
        contenido.append(Paragraph(
            "El análisis muestra la distribución poblacional y niveles de riesgo asociados.",
            styles["BodyText"]
        ))

        contenido.append(Spacer(1, 12))

        # =========================
        # INSERTAR GRAFICOS
        # =========================
        contenido.append(Image("edad.png", width=400, height=200))
        contenido.append(Spacer(1, 12))
        contenido.append(Image("sexo.png", width=400, height=200))

        contenido.append(Spacer(1, 12))

        contenido.append(Paragraph("CONCLUSIÓN", styles["Heading2"]))
        contenido.append(Paragraph(
            "Se recomienda fortalecer intervención social y seguimiento de casos críticos.",
            styles["BodyText"]
        ))

        doc.build(contenido)

        with open(archivo, "rb") as f:
            st.download_button(
                "⬇️ Descargar PDF",
                f,
                file_name=archivo,
                mime="application/pdf"
            )

        st.success("PDF generado correctamente")
# =========================
# NUEVO REGISTRO
# =========================

with tab11:

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
                    numero_de_identificacion,
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
# TAB 12 - SEGUIMIENTO PROFESIONAL + PAI
# =====================================

with tab12:

    st.title("📋 Seguimiento Profesional - PAI (Plan de Atención Individual)")

    # =========================
    # PROFESIONALES
    # =========================
    try:
        df_profesionales = pd.read_sql("""
            SELECT nombre, rol
            FROM profesionales
            ORDER BY nombre
        """, engine)

        df_profesionales["label"] = (
            df_profesionales["nombre"].astype(str)
            + " (" + df_profesionales["rol"].astype(str) + ")"
        )

    except:
        df_profesionales = pd.DataFrame({
            "label": ["Psicología", "Enfermería", "Trabajo Social", "Pedagogía"]
        })

    # =========================
    # USUARIO
    # =========================
    cedula = st.text_input("Documento del usuario (PAI)", key="pai_user")

    if cedula:
        usuario = pd.read_sql(f"""
            SELECT * FROM habitante_de_calle
            WHERE numero_identificacion = '{cedula}'
        """, engine)

        if not usuario.empty:
            datos = usuario.iloc[0]
            st.success("Usuario encontrado")

            c1, c2, c3 = st.columns(3)
            c1.metric("Nombre", f"{datos['nombres']} {datos['apellidos']}")
            c2.metric("Edad", datos.get("edad", "N/A"))
            c3.metric("Documento", cedula)
        else:
            st.warning("Usuario no encontrado")

    st.divider()

    # =========================
    # PAI FORM
    # =========================
    st.subheader("🧠 PAI - Plan de Atención Individual")

    if cedula:

        with st.form("pai_form"):

            tipo_intervencion = st.selectbox(
                "Tipo de intervención",
                [
                    "Reducción de riesgos y daños",
                    "Adherencia tratamiento",
                    "Valoración enfermería",
                    "Valoración psicología",
                    "Seguimiento social"
                ]
            )

            patologia = st.selectbox(
                "Patología / condición",
                [
                    "Consumo de sustancias",
                    "Ansiedad",
                    "Depresión",
                    "Trastorno mental severo",
                    "VIH",
                    "Tuberculosis",
                    "Enfermedad infectocontagiosa",
                    "Hipertensión",
                    "Otra"
                ]
            )

            profesional = st.selectbox(
                "Profesional",
                df_profesionales["label"].tolist()
            )

            descripcion = st.text_area("Descripción")

            adherencia = st.selectbox(
                "Nivel de adherencia",
                ["Alta", "Media", "Baja"]
            )

            guardar = st.form_submit_button("Guardar PAI")

        if guardar:

            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO pai_intervenciones
                    (documento_usuario, tipo_intervencion, patologia, profesional, descripcion, adherencia)
                    VALUES (:doc, :tipo, :patologia, :prof, :desc, :adh)
                """), {
                    "doc": cedula,
                    "tipo": tipo_intervencion,
                    "patologia": patologia,
                    "prof": profesional,
                    "desc": descripcion,
                    "adh": adherencia
                })

            st.success("PAI registrado correctamente")

    st.divider()

    # =========================
    # ASISTENCIA
    # =========================
    st.subheader("📅 Asistencia a talleres")

    df_activos = pd.read_sql("""
        SELECT numero_identificacion, nombres, apellidos
        FROM habitante_de_calle
        WHERE estado_caso = 'ACTIVO'
    """, engine)

    df_activos["nombre"] = df_activos["nombres"] + " " + df_activos["apellidos"]

    with st.form("asistencia"):

        actividad = st.text_input("Actividad")

        profesional_a = st.selectbox(
            "Profesional",
            df_profesionales["label"].tolist()
        )

        fecha = st.date_input("Fecha")

        participantes = st.multiselect(
            "Participantes",
            df_activos["numero_identificacion"].tolist(),
            format_func=lambda x: df_activos.loc[
                df_activos["numero_identificacion"] == x, "nombre"
            ].values[0]
        )

        estado = st.selectbox("Asistencia", ["Asistió", "No asistió"])
        obs = st.text_area("Observaciones")

        guardar2 = st.form_submit_button("Guardar")

    if guardar2:

        with engine.begin() as conn:
            for doc in participantes:
                conn.execute(text("""
                    INSERT INTO asistencias
                    (documento_usuario, fecha, asistencia, observaciones, profesional, actividad)
                    VALUES (:doc, :fecha, :estado, :obs, :prof, :act)
                """), {
                    "doc": doc,
                    "fecha": fecha,
                    "estado": estado,
                    "obs": obs,
                    "prof": profesional_a,
                    "act": actividad
                })

        st.success("Asistencia registrada")
# =====================================
# TAB 13 - SEGUIMIENTO E IMPACTO (PAI + REDUCCIÓN DE RIESGOS)
# =====================================
with tab13:

    st.title("📈 Seguimiento e Impacto - Reducción de Riesgos y Daños")

    # =========================
    # 🔎 BASE ACTIVA NORMALIZADA (ESTO ARREGLA LOS 167 vs 124)
    # =========================
    df_base = pd.read_sql("""
        SELECT *
        FROM habitante_de_calle
        WHERE LOWER(TRIM(estado_caso)) = 'activo'
    """, engine)

    df_base["numero_identificacion"] = (
        df_base["numero_identificacion"]
        .astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
    )

    df_base["nombre"] = (
        df_base["nombres"].astype(str) + " " + df_base["apellidos"].astype(str)
    )

    total_activos = len(df_base)

    # =========================
    # 🧠 PAI INTERVENCIONES
    # =========================
    try:
        df_pai = pd.read_sql("""
            SELECT *
            FROM pai_intervenciones
        """, engine)
    except:
        df_pai = pd.DataFrame(columns=[
            "documento_usuario",
            "adherencia",
            "patologia"
        ])

    df_pai["documento_usuario"] = df_pai["documento_usuario"].astype(str).str.strip()

    # =========================
    # 🔗 CRUCE PAI VS ACTIVOS
    # =========================
    activos_ids = set(df_base["numero_identificacion"])
    pai_ids = set(df_pai["documento_usuario"])

    con_pai = activos_ids.intersection(pai_ids)
    sin_pai = activos_ids.difference(pai_ids)

    df_con_pai = df_base[df_base["numero_identificacion"].isin(con_pai)]
    df_sin_pai = df_base[df_base["numero_identificacion"].isin(sin_pai)]

    # =========================
    # 📊 INDICADORES GENERALES
    # =========================
    st.subheader("📊 Indicadores generales")

    c1, c2, c3 = st.columns(3)

    c1.metric("Activos", total_activos)
    c2.metric("Con PAI", len(df_con_pai))
    c3.metric("Sin PAI", len(df_sin_pai))

    st.divider()

    # =========================
    # 🚨 SIN PAI
    # =========================
    st.subheader("🚨 Personas sin PAI")

    st.dataframe(
        df_sin_pai[[
            "nombre",
            "numero_identificacion",
            "modalidad"
        ]] if len(df_sin_pai) > 0 else pd.DataFrame()
    )

    st.divider()

    # =========================
    # ✅ CON PAI
    # =========================
    st.subheader("✅ Personas con PAI")

    st.dataframe(
        df_con_pai[[
            "nombre",
            "numero_identificacion",
            "modalidad"
        ]] if len(df_con_pai) > 0 else pd.DataFrame()
    )

    st.divider()

    # =========================
    # 💊 ADHERENCIA POR PATOLOGÍA
    # =========================
    st.subheader("💊 Adherencia por patología")

    if len(df_pai) > 0 and "patologia" in df_pai.columns:

        tabla = pd.crosstab(
            df_pai["patologia"],
            df_pai["adherencia"]
        )

        st.dataframe(tabla)
        st.bar_chart(tabla)

    else:
        st.warning("No hay datos suficientes de PAI")

    st.divider()

    # =========================
    # 🧠 ÍNDICE DE ÉXITO
    # =========================
    st.subheader("🧠 Índice de éxito en reducción de riesgos")

    if len(df_pai) > 0 and "adherencia" in df_pai.columns:

        mapa = {"Alta": 2, "Media": 1, "Baja": 0}

        df_pai["score"] = df_pai["adherencia"].map(mapa)

        df_indice = df_pai.groupby("documento_usuario").agg(
            score=("score", "mean")
        ).reset_index()

        df_indice["indice_exito"] = (df_indice["score"] / 2) * 100

        def clasificar(x):
            if x >= 75:
                return "🟢 Estabilizado"
            elif x >= 50:
                return "🟡 En proceso"
            elif x >= 25:
                return "🟠 Riesgo"
            else:
                return "🔴 Crítico"

        df_indice["estado"] = df_indice["indice_exito"].apply(clasificar)

        df_final = df_indice.merge(
            df_base[["numero_identificacion", "nombre", "modalidad"]],
            left_on="documento_usuario",
            right_on="numero_identificacion",
            how="left"
        )

        st.dataframe(
            df_final[[
                "nombre",
                "modalidad",
                "indice_exito",
                "estado"
            ]]
        )

        st.bar_chart(df_final["estado"].value_counts())

    else:
        st.warning("No hay datos para calcular índice de éxito")

    st.divider()

    # =========================
    # 🚦 ALERTAS
    # =========================
    st.subheader("🚨 Alertas")

    if len(df_pai) > 0 and "adherencia" in df_pai.columns:

        criticos = len(df_indice[df_indice["indice_exito"] < 25])
        porcentaje = round((criticos / len(df_indice)) * 100, 2)

        if porcentaje > 30:
            st.error(f"⚠️ Alta población en riesgo crítico: {porcentaje}%")
        elif porcentaje > 15:
            st.warning(f"⚠️ Riesgo medio: {porcentaje}%")
        else:
            st.success(f"✔️ Situación controlada: {porcentaje}%")

    st.divider()

    # =========================
    # 📋 HISTORIA INDIVIDUAL
    # =========================
    st.subheader("📋 Historia individual PAI")

    cedula = st.text_input("Documento")

    if cedula:

        historia = pd.read_sql(f"""
            SELECT *
            FROM pai_intervenciones
            WHERE documento_usuario = '{cedula}'
        """, engine)

        st.dataframe(historia)

# =====================================
# TAB 14 - CARGA MASIVA ACTUALIZADA
# =====================================

with tab14:

    st.title("📥 Carga Masiva de Activos")

    archivo = st.file_uploader(
        "Sube archivo Excel",
        type=["xlsx"],
        key="upload_activos_tab14"
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
