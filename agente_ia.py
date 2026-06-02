import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
#from ollama import Client

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak
)

from reportlab.lib.styles import getSampleStyleSheet

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Observatorio Social IA",
    layout="wide"
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
# =========================
# CARGAR DATOS
# =========================
df = pd.read_sql("SELECT * FROM habitante_de_calle", engine)
df = df.drop_duplicates()
# 🔥 LIMPIEZA DE COLUMNAS (OBLIGATORIO)
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace("\n", " ")
    .str.replace("  ", " ")
    .str.replace(" ", "_")
)
# =========================
# LIMPIEZA / FEATURES
# =========================
df["score_vulnerabilidad"] = ...
df["nivel_riesgo"] = ...

# =========================
# FUNCIONES AUXILIARES (AQUÍ VA)
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
# FUNCIÓN PESO CONSUMO
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

    return 1


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

def peso_consumo(x):
    x = str(x).lower()

    # 🔴 CRÍTICO
    if "heroina" in x or "heroína" in x:
        return 5

    # 🔴 MUY ALTO
    elif "policonsumo" in x or ("," in x and len(x.split(",")) >= 2):
        return 4

    elif "bazuco" in x:
        return 4

    elif "alcohol" in x:
        return 4

    # 🟠 MEDIO
    elif "coca" in x:
        return 3

    # 🟡 BAJO
    elif "marihuana" in x:
        return 1

    # SIN CONSUMO
    elif x in ["no", "ninguno", "nan", ""]:
        return 0

    else:
        return 1


# =========================
# SIDEBAR
# =========================
st.sidebar.header("Filtros")

if "sexo_al_nacer" in df.columns:
    sexo = st.sidebar.multiselect(
        "Sexo",
        options=df["sexo_al_nacer"].dropna().unique(),
        default=df["sexo_al_nacer"].dropna().unique(),
    )
    df = df[df["sexo_al_nacer"].isin(sexo)]
if "comuna_o_corregimiento_de_residencia" in df.columns:
    comuna = st.sidebar.multiselect(
        "Comuna",
        options=df["comuna_o_corregimiento_de_residencia"].dropna().unique(),
        default=df["comuna_o_corregimiento_de_residencia"].dropna().unique(),
    )
    df = df[df["comuna_o_corregimiento_de_residencia"].isin(comuna)]
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
st.subheader("🧠 ¿Cómo interpretar el Score de Vulnerabilidad?")

st.info("""
El Score de Vulnerabilidad mide el nivel de acumulación de factores de riesgo social.

Se construye a partir de:
- Consumo de sustancias
- Salud mental
- Discapacidad
- Migración

Escala:
- 0–25 → Bajo riesgo
- 26–50 → Riesgo medio
- 51–75 → Alto riesgo
- 76–100 → Riesgo crítico

👉 A mayor score, mayor prioridad de intervención.
""")
df["v_consumo"] = df["tipo_consumo"].apply(peso_consumo)
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

col5.metric(
    "Consumo SPA",
    f"{round(df_kpi['consumo_spa'].mean() * 100, 1)}%"
    if "consumo_spa" in df_kpi.columns else "N/A"
)

col6.metric(
    "Salud mental",
    f"{round(df_kpi['salud_mental'].mean() * 100, 1)}%"
    if "salud_mental" in df_kpi.columns else "N/A"
)
# KPIs
# =========================
# TABS PRINCIPALES
# =========================
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs([
    "📊 General",
    "⚠️ Vulnerabilidad",
    "🚬 Consumo",
    "🧠 Salud Mental",
    "🌎 Territorio",
    "🎓 Educación",
    "🚦 Semáforo",
    "🤖 IA",
    "🏆 Egresos e Impacto",
    "📄 Reportes Institucionales",
    "➕ Nuevo Registro"
])
# =========================
# TAB GENERAL
# =========================
with tab1:

    st.subheader("📊 Caracterización general")

    # =========================
    # SEXO AL NACER
    # =========================
    if "sexo_al_nacer" in df.columns:

        sexo_df = (
            df["sexo_al_nacer"]
            .value_counts()
            .reset_index()
        )

        sexo_df.columns = ["sexo", "cantidad"]

        fig1 = px.pie(
            sexo_df,
            names="sexo",
            values="cantidad",
            title="Sexo al nacer"
        )

        st.plotly_chart(fig1, use_container_width=True)

        sexo_mayor = sexo_df.iloc[0]

        st.info(
            f"La mayoría de la población corresponde a personas de sexo {sexo_mayor['sexo']}, "
            f"con {sexo_mayor['cantidad']} registros."
        )

    # =========================
    # EDADES
    # =========================
    if "edad" in df.columns:

        df["edad"] = pd.to_numeric(df["edad"], errors="coerce")

        fig3 = px.histogram(
            df,
            x="edad",
            nbins=20,
            title="Distribución de edades"
        )

        st.plotly_chart(fig3, use_container_width=True)

    # =========================
    # GRUPOS ETARIOS
    # =========================
    df["grupo_etario"] = pd.cut(
        df["edad"],
        bins=[0, 17, 28, 59, 120],
        labels=["Adolescencia", "Joven", "Adulto", "Adulto mayor"]
    )

    etario_df = (
        df["grupo_etario"]
        .value_counts()
        .reset_index()
    )

    etario_df.columns = ["grupo", "cantidad"]

    grupo_top = etario_df.iloc[0]

    st.info(
        f"El grupo etario predominante es {grupo_top['grupo']} "
        f"con {grupo_top['cantidad']} registros."
    )

    # =========================
    # ADULTOS MAYORES CRÍTICOS
    # =========================
    adultos_criticos = len(
        df[
            (df["grupo_etario"] == "Adulto mayor") &
            (df["nivel_riesgo"].isin(["Alto", "Crítico"]))
        ]
    )

    st.error(
        f"👴 Se identifican {adultos_criticos} adultos mayores en condición crítica o de alta vulnerabilidad."
    )

    adultos_mayores = len(
        df[df["grupo_etario"] == "Adulto mayor"]
    )

    st.warning(
        f"Se identifican {adultos_mayores} personas adultas mayores en situación de calle."
    )

    # =========================
    # JÓVENES CRÍTICOS
    # =========================
    jovenes_criticos = len(
        df[
            (df["grupo_etario"] == "Joven") &
            (df["nivel_riesgo"].isin(["Alto", "Crítico"]))
        ]
    )

    st.warning(
        f"🧑 Se identifican {jovenes_criticos} jóvenes con niveles altos de vulnerabilidad social."
    )

    # =========================
    # ETNIA VS CONSUMO
    # =========================
    st.subheader("💊 Etnia vs Consumo")

# Validación básica para evitar KeyError
if "grupos_etnicos" in df.columns and "tipo_consumo" in df.columns:

    tabla = pd.crosstab(
        df["grupos_etnicos"],
        df["tipo_consumo"]
    )

    st.dataframe(tabla)

else:
    st.warning("No se encontraron las columnas 'grupos_etnicos' o 'tipo_consumo' en el dataset.")
    # =========================
    # EDUCACIÓN VS VULNERABILIDAD
    # =========================
    st.subheader("📚 Educación vs Vulnerabilidad")

    edu = df.groupby(
        "nivel_educativo_que_tiene_o_cursa"
    )["score_vulnerabilidad"].mean().reset_index()

    fig = px.bar(
        edu,
        x="nivel_educativo_que_tiene_o_cursa",
        y="score_vulnerabilidad",
        color="score_vulnerabilidad",
        color_continuous_scale="Reds"
    )

    st.plotly_chart(fig, use_container_width=True)

    # =========================
    # GRUPOS ÉTNICOS
    # =========================
    if "grupos_etnicos_afro_indigena" in df.columns:

        etnia_df = (
            df["grupos_etnicos_afro_indigena"]
            .value_counts()
            .reset_index()
        )

        etnia_df.columns = ["etnia", "cantidad"]

        fig2 = px.bar(
            etnia_df,
            x="etnia",
            y="cantidad",
            color="cantidad",
            title="Grupos étnicos"
        )

        st.plotly_chart(fig2, use_container_width=True)
# =========================
# TAB VULNERABILIDAD
# =========================
with tab2:

    st.subheader("🚦 Distribución de vulnerabilidad")

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

    # INTERPRETACIÓN
    criticos = len(
        df[df["nivel_riesgo"] == "Crítico"]
    )

    st.error(
        f"Se identifican {criticos} personas en nivel crítico de vulnerabilidad social."
    )

    st.info(
        "El score de vulnerabilidad refleja acumulación de riesgos sociales, sanitarios y territoriales."
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

    st.subheader("📍 Barrio o vereda")

if "barrio_vereda" in df.columns:

    barrio_df = df["barrio_vereda"].value_counts().reset_index()
    barrio_df.columns = ["barrio", "cantidad"]

    st.dataframe(barrio_df)

else:
    st.warning("No existe la columna 'barrio_vereda' en la base de datos")
# =========================
# TAB EDUCACIÓN
# =========================
with tab6:

    st.subheader("📚 Nivel educativo")

    edu = (
        df["nivel_educativo_que_tiene_o_cursa"]
        .value_counts()
        .reset_index()
    )

    edu.columns = ["nivel", "cantidad"]

    fig = px.bar(
        edu,
        x="nivel",
        y="cantidad",
        color="cantidad"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    # INTERPRETACIÓN
    edu_top = edu.iloc[0]

    st.info(
        f"El nivel educativo predominante es: {edu_top['nivel']}."
    )

    st.warning(
        "Los bajos niveles educativos pueden aumentar la exclusión social y laboral."
    )
# =========================
# TAB SEMÁFORO SOCIAL
# =========================
with tab7:

    st.subheader("👥 Semáforo social")

    df["nombre_completo"] = (
        df["nombres"].astype(str)
        + " "
        + df["apellidos"].astype(str)
    )

    st.dataframe(

        df[[
            "semáforo",
            "score_vulnerabilidad",
            "nombre_completo",
            "sexo_al_nacer",
            "edad",
            "tipo_de_consumo",
            "nivel_educativo_que_tiene_o_cursa",
            "barrio_o_vereda_de_residencia"
        ]]

        .sort_values(
            by="score_vulnerabilidad",
            ascending=False
        ),

        use_container_width=True
    )

    # INTERPRETACIÓN
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
    # IMPORTAR EGRESOS
    # ==========================

    st.subheader("📥 Cargar egresos desde Excel")

    archivo_egresos = st.file_uploader(
        "Subir Excel de egresos",
        type=["xlsx"],
        key="egresos"
    )

    if archivo_egresos is not None:

        df_egresos = pd.read_excel(archivo_egresos)

        # Limpiar columnas vacías
        df_egresos = df_egresos.loc[
            :, ~df_egresos.columns.str.contains("^Unnamed")
        ]

        # Renombrar documento
        df_egresos = df_egresos.rename(
            columns={
                "NÚMERO DE IDENTIDAD": "documento"
            }
        )

        st.success("Archivo cargado correctamente")
        st.dataframe(df_egresos)

        if st.button(
            "📥 Importar egresos a PostgreSQL",
            key="importar_egresos"
        ):

            actualizados = 0

            with engine.begin() as conn:

                for _, fila in df_egresos.iterrows():

                    conn.execute(
                        text("""
                            UPDATE personas_caracterizacion
                            SET
                                estado_caso = 'EGRESADO',
                                observaciones_egreso = :obs,
                                funcionario_egreso = :funcionario
                            WHERE numero_identidad = :doc
                        """),
                        {
                            "doc": str(fila["documento"]),
                            "obs": str(fila["OBSERVACIONES"]),
                            "funcionario": str(
                                fila["FUNCIONARIO /CONTRATISTA  RESPONSABLE"]
                            )
                        }
                    )

                    actualizados += 1

            st.success(
                f"✅ {actualizados} egresos importados correctamente"
            )

    st.markdown("---")

    # ==========================
    # INDICADORES DE IMPACTO
    # ==========================

    st.subheader("📊 Indicadores de Egreso")

    query = """
        SELECT *
        FROM personas_caracterizacion
        WHERE estado_caso = 'EGRESADO'
    """

    df_impacto = pd.read_sql_query(query, engine)

    total_egresados = len(df_impacto)

    total_personas = len(df)

    tasa_egreso = round(
        (total_egresados / total_personas) * 100,
        2
    ) if total_personas > 0 else 0

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "🎓 Total Egresados",
        total_egresados
    )

    col2.metric(
        "📈 Tasa de Egreso",
        f"{tasa_egreso}%"
    )

    col3.metric(
        "👤 Edad Promedio",
        round(df_impacto["edad"].mean(), 1)
        if len(df_impacto) > 0 else 0
    )
# ==========================
# OBSERVACIONES DE EGRESO
# ==========================

st.subheader("📌 Análisis de Observaciones de Egreso")

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


# ==========================
# SEXO (EGRESADOS)
# ==========================

if "sexo_nacer" in df_impacto.columns:

    fig_sexo = px.pie(
        df_impacto,
        names="sexo_nacer",
        title="Egresados por sexo"
    )

    st.plotly_chart(
        fig_sexo,
        use_container_width=True,
        key="sexo_egresados"
    )
    # ==========================
    # ORIENTACIÓN SEXUAL
    # ==========================

    if "orientacion_lgbti" in df_impacto.columns:

        fig_lgbti = px.histogram(
            df_impacto,
            x="orientacion_lgbti",
            color="orientacion_lgbti",
            title="Orientación sexual"
        )

        st.plotly_chart(
            fig_lgbti,
            use_container_width=True,
            key="lgbti_egresados"
        )

    # ==========================
    # GRUPO ÉTNICO
    # ==========================

    if "grupo_etnico" in df_impacto.columns:

        fig_etnia = px.histogram(
            df_impacto,
            x="grupo_etnico",
            color="grupo_etnico",
            title="Grupo étnico"
        )

        st.plotly_chart(
            fig_etnia,
            use_container_width=True,
            key="etnia_egresados"
        )

    # ==========================
    # EDAD
    # ==========================

    fig_edad = px.histogram(
        df_impacto,
        x="edad",
        nbins=10,
        title="Distribución de edades"
    )

    st.plotly_chart(
        fig_edad,
        use_container_width=True,
        key="edad_egresados"
    )

    # ==========================
    # CONCLUSIÓN AUTOMÁTICA
    # ==========================

    st.info(
        f"""
        El programa registra actualmente {total_egresados} personas egresadas,
        equivalentes al {tasa_egreso}% del total de personas caracterizadas.
        """
    )
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
    # EGRESADOS (FUENTE CORRECTA)
    # =========================

    df_egresados = pd.read_sql("""
    SELECT
        numero_identidad,
        estado_caso,
        edad,
        sexo_nacer,
        grupo_etnico,
        orientacion_lgbti,
        observaciones_egreso,
        funcionario_egreso
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
    col2.metric("⚠️ Riesgo crítico", criticos)
    col3.metric("📈 Vulnerabilidad", score)
    col4.metric("🏆 Egresados", total_egresados)
    col5.metric("📊 Tasa Egreso", f"{tasa_egreso}%")

    st.markdown("---")

    # =========================
    # PERFIL SOCIODEMOGRÁFICO
    # =========================

    st.subheader("👤 Perfil Sociodemográfico")

    c1, c2 = st.columns(2)

    with c1:
        fig_sexo = px.pie(df, names="sexo_al_nacer", title="Sexo al nacer")
        st.plotly_chart(fig_sexo, use_container_width=True)

    with c2:
        fig_edad = px.histogram(df, x="edad", nbins=15, title="Distribución de edades")
        st.plotly_chart(fig_edad, use_container_width=True)

    st.markdown("---")

    # =========================
    # DIVERSIDAD
    # =========================

    st.subheader("🏳️ Diversidad e Inclusión")

    fig_orientacion = px.histogram(
        df,
        x="orientacion_sexual_comunidad_lgtbi",
        color="orientacion_sexual_comunidad_lgtbi",
        title="Orientación sexual"
    )
    st.plotly_chart(fig_orientacion, use_container_width=True)

    if "grupos_etnicos_afro_indigena" in df.columns:
        fig_etnia = px.histogram(
            df,
            x="grupos_etnicos_afro_indigena",
            color="grupos_etnicos_afro_indigena",
            title="Grupos étnicos"
        )
        st.plotly_chart(fig_etnia, use_container_width=True)

    st.markdown("---")

    # =========================
    # CONSUMO
    # =========================

    st.subheader("🚬 Consumo de Sustancias")

    fig_consumo = px.histogram(
        df,
        x="tipo_de_consumo",
        color="tipo_de_consumo",
        title="Tipo de consumo"
    )
    st.plotly_chart(fig_consumo, use_container_width=True)

    consumo_promedio = df.groupby("tipo_de_consumo")["score_vulnerabilidad"].mean().reset_index()

    fig_relacion = px.bar(
        consumo_promedio,
        x="tipo_de_consumo",
        y="score_vulnerabilidad",
        color="tipo_de_consumo",
        title="Vulnerabilidad promedio según consumo"
    )
    st.plotly_chart(fig_relacion, use_container_width=True)

    st.markdown("---")

    # =========================
    # VULNERABILIDAD
    # =========================

    st.subheader("⚠️ Vulnerabilidad Social")

    fig_riesgo = px.histogram(df, x="nivel_riesgo", color="nivel_riesgo")
    st.plotly_chart(fig_riesgo, use_container_width=True)

    if "semáforo" in df.columns:
        fig_semaforo = px.pie(df, names="semáforo", title="Clasificación por semáforo")
        st.plotly_chart(fig_semaforo, use_container_width=True)

    st.markdown("---")

    # =========================
    # TERRITORIO
    # =========================

    st.subheader("🌎 Análisis Territorial")

    fig_territorio = px.histogram(
        df,
        x="comuna_o_corregimiento_de_residencia",
        color="comuna_o_corregimiento_de_residencia",
        title="Distribución territorial"
    )
    st.plotly_chart(fig_territorio, use_container_width=True)

    st.markdown("---")

    # =========================
    # IMPACTO
    # =========================

    st.subheader("🏆 Impacto Institucional")

    col1, col2 = st.columns(2)

    col1.metric("Egresados", total_egresados)
    col2.metric("Tasa de Egreso", f"{tasa_egreso}%")

    st.markdown("---")

    # =========================
    # HALLAZGOS
    # =========================

    st.subheader("📋 Hallazgos Institucionales")

    hallazgos = []

    if criticos > total * 0.25:
        hallazgos.append("Alta concentración de riesgo crítico.")

    if score > 7:
        hallazgos.append("Vulnerabilidad promedio elevada.")

    if tasa_egreso < 10:
        hallazgos.append("Baja tasa de egreso institucional.")

    if edad_promedio > 50:
        hallazgos.append("Envejecimiento progresivo de la población.")

    if len(hallazgos) == 0:
        st.success("No se identifican alertas relevantes.")
    else:
        for h in hallazgos:
            st.warning(h)

    st.markdown("---")

    # =========================
    # CONCLUSIÓN
    # =========================

    st.subheader("📝 Conclusión Ejecutiva")

    st.info(f"""
    El Observatorio Social registra actualmente {total} personas.

    Edad promedio: {edad_promedio} años.

    Vulnerabilidad promedio: {score}.

    Casos críticos: {criticos}.

    Egresados: {total_egresados} ({tasa_egreso}%).

    Se recomienda fortalecer intervención social,
    salud mental y seguimiento post-egreso.
    """)
    st.markdown("---")

st.subheader("📄 Informe Ejecutivo")

if st.button("📥 Generar Informe Ejecutivo PDF", key="pdf_ejecutivo"):

    # =========================
    # IMPORTS BASE PDF
    # =========================
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import letter
    import os

    styles = getSampleStyleSheet()
    contenido = []

    archivo = "informe_observatorio_social.pdf"

    doc = SimpleDocTemplate(archivo, pagesize=letter)

    # =========================
    # KPIs BASE (df = habitante_calle)
    # =========================

    total = len(df)

    score = round(df["score_vulnerabilidad"].mean(), 2)
    criticos = len(df[df["nivel_riesgo"] == "Crítico"])
    edad_promedio = round(df["edad"].mean(), 1)

    # =========================
    # EGRESADOS (FUENTE CORRECTA)
    # =========================

    df_egresados = pd.read_sql("""
        SELECT *
        FROM personas_caracterizacion
        WHERE estado_caso = 'EGRESADO'
    """, engine)

    total_egresados = len(df_egresados)

    tasa_egreso = round((total_egresados / total) * 100, 2) if total > 0 else 0

    # =========================
    # ENCABEZADO
    # =========================

    contenido.append(Paragraph("INFORME EJECUTIVO - OBSERVATORIO SOCIAL", styles["Title"]))
    contenido.append(Spacer(1, 12))

    # =========================
    # KPIs
    # =========================

    contenido.append(Paragraph(f"Personas caracterizadas: {total}", styles["BodyText"]))
    contenido.append(Paragraph(f"Edad promedio: {edad_promedio}", styles["BodyText"]))
    contenido.append(Paragraph(f"Score de vulnerabilidad: {score}", styles["BodyText"]))
    contenido.append(Paragraph(f"Casos críticos: {criticos}", styles["BodyText"]))
    contenido.append(Paragraph(f"Egresados: {total_egresados}", styles["BodyText"]))
    contenido.append(Paragraph(f"Tasa de egreso: {tasa_egreso}%", styles["BodyText"]))

    contenido.append(Spacer(1, 12))

    # =========================
    # ANÁLISIS ESTADÍSTICO
    # =========================

    contenido.append(Paragraph("ANÁLISIS ESTADÍSTICO", styles["Heading2"]))

    contenido.append(Paragraph(
        f"""
        La población analizada presenta una edad promedio de {edad_promedio} años.
        El índice promedio de vulnerabilidad es de {score} puntos.

        Los casos clasificados como críticos representan
        aproximadamente {round((criticos/total)*100,2) if total > 0 else 0}% de la población.
        """,
        styles["BodyText"]
    ))

    contenido.append(Spacer(1, 12))

    # =========================
    # HALLAZGOS
    # =========================

    contenido.append(Paragraph("HALLAZGOS INSTITUCIONALES", styles["Heading2"]))

    hallazgos = []

    if criticos > total * 0.25:
        hallazgos.append("Alta concentración de población en riesgo crítico.")

    if score > 7:
        hallazgos.append("Nivel promedio de vulnerabilidad elevado.")

    if tasa_egreso < 10:
        hallazgos.append("Baja tasa de egreso institucional.")

    if edad_promedio > 50:
        hallazgos.append("Tendencia de envejecimiento en la población atendida.")

    if len(hallazgos) == 0:
        hallazgos.append("No se identifican alertas relevantes en el análisis.")

    for h in hallazgos:
        contenido.append(Paragraph(f"• {h}", styles["BodyText"]))

    contenido.append(Spacer(1, 12))

    # =========================
    # RECOMENDACIONES
    # =========================

    contenido.append(Paragraph("RECOMENDACIONES", styles["Heading2"]))

    recomendaciones = [
        "Fortalecer seguimiento a casos de alta vulnerabilidad.",
        "Incrementar estrategias de inclusión social.",
        "Reforzar atención en salud mental.",
        "Ampliar programas de reducción de daños.",
        "Fortalecer procesos de egreso sostenible."
    ]

    for r in recomendaciones:
        contenido.append(Paragraph(f"• {r}", styles["BodyText"]))

    contenido.append(Spacer(1, 12))

    # =========================
    # CONCLUSIÓN
    # =========================

    contenido.append(Paragraph("CONCLUSIÓN INSTITUCIONAL", styles["Heading2"]))

    contenido.append(Paragraph(
        f"""
        El Observatorio Social registra {total} personas caracterizadas.
        La tasa de egreso es del {tasa_egreso}%.

        Los resultados evidencian la necesidad de fortalecer
        estrategias integrales de intervención social,
        salud mental, reducción de riesgos y acompañamiento
        post-egreso para garantizar procesos sostenibles de inclusión.
        """,
        styles["BodyText"]
    ))

    # =========================
    # GENERAR PDF
    # =========================

    doc.build(contenido)

    with open(archivo, "rb") as pdf:
        st.download_button(
            "⬇️ Descargar Informe PDF",
            pdf,
            file_name=archivo,
            mime="application/pdf"
        )

    st.success("✅ Informe generado correctamente")
# NUEVO REGISTRO
# =========================

with tab11:
    st.subheader("🔐 Acceso al formulario")

    clave = st.text_input(
        "Ingrese la contraseña",
        type="password"
    )

    if clave != "Pereira2026":
        st.warning("Contraseña incorrecta")
        st.stop()

    st.success("Acceso autorizado")
    st.subheader("➕ Nuevo Registro Social")

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
            "Tipo de identificación",
            ["CC", "TI", "CE", "PEP", "Otro"]
        )

        numero_id = st.text_input(
            " numero_de_identidadficacion_____sin_puntos,_ni_rayas,el_registr"
        )

        st.markdown("### Caracterización")

        etnia = st.selectbox(
            "Grupo étnico",
            [
                "Ninguno",
                "Afrodescendiente",
                "Indígena",
                "Mestizo"
            ]
        )
        discapacidad_txt = st.selectbox(
            "¿Presenta discapacidad?",
            ["NO", "SI"]
        )
        categoria_discapacidad = st.selectbox(
            "Tipo de discapacidad",
            [
                "Física",
                "Visual",
                "Auditiva",
                "Intelectual",
                "Psicosocial",
                "Múltiple",
                "Otra"
            ],
            key="categoria_discapacidad_form"
        )
        migracion_txt = st.selectbox(
            "Migración",
            ["NO", "SI"]
        )
        migracion = 1 if migracion_txt == "SI" else 0
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

        st.markdown("### Territorio")

        barrio = st.text_input("Barrio o vereda")
        comuna = st.text_input("Comuna o corregimiento")
        telefono = st.text_input("Teléfono")

        st.markdown("### Vulnerabilidad")

        consumo = st.selectbox(
            "Tipo de consumo",
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

        enfermedad_mental = st.selectbox(
            "Enfermedad mental",
            [
                "No",
                "Sí"
            ]
        )

        guardar = st.form_submit_button(
        "💾 Guardar registro"
    )

if guardar:

    st.success("Formulario enviado correctamente")


    sql = text("""
        INSERT INTO habitante_calle
        (
            nombres,
            apellidos,
            sexo_al_nacer,
            edad,
            tipo_de_identificacion,
            "numero_de_identidadficacion_____sin_puntos,_ni_rayas,el_registr",
            grupos_etnicos_afro_indigena,
            personas_con_discapacidad,
            indicador_migracion,
            nivel_educativo_que_tiene_o_cursa,
            barrio_o_vereda_de_residencia,
            comuna_o_corregimiento_de_residencia,
            telefono_y_o_celular,
            tipo_de_consumo,
            enfermedad_mental
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
            :enfermedad_mental
        )
        """)

    try:

            with engine.begin() as conn:

                conn.execute(
                    sql,
                    {
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
                        "enfermedad_mental": enfermedad_mental
                    }
                )

            st.success("✅ Registro guardado correctamente")

    except Exception as e:

            st.error(str(e))
            