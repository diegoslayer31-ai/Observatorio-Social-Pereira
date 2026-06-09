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
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12, tab13 = st.tabs([
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
    "➕ Nuevo Registro",
    "📋 Seguimiento Profesional",
    "📈 Seguimiento e Impacto"
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

        sexo_df = df["sexo_al_nacer"].value_counts().reset_index()
        sexo_df.columns = ["sexo", "cantidad"]

        fig1 = px.pie(
            sexo_df,
            names="sexo",
            values="cantidad",
            title="Sexo al nacer"
        )

        st.plotly_chart(fig1, use_container_width=True)

        sexo_top = sexo_df.iloc[0]

        st.info(
            f"Predomina el sexo {sexo_top['sexo']} con {sexo_top['cantidad']} registros."
        )

    else:
        st.warning("No existe la columna 'sexo_al_nacer'")

    st.markdown("---")

    # =========================
    # EDAD
    # =========================
    if "edad" in df.columns:

        df["edad"] = pd.to_numeric(df["edad"], errors="coerce")

        fig2 = px.histogram(
            df,
            x="edad",
            nbins=20,
            title="Distribución de edades"
        )

        st.plotly_chart(fig2, use_container_width=True)

    else:
        st.warning("No existe la columna 'edad'")

    st.markdown("---")

    # =========================
    # GRUPO ETARIO
    # =========================
    if "edad" in df.columns:

        df["grupo_etario"] = pd.cut(
            df["edad"],
            bins=[0, 17, 28, 59, 120],
            labels=["Adolescencia", "Joven", "Adulto", "Adulto mayor"]
        )

        etario_df = df["grupo_etario"].value_counts().reset_index()
        etario_df.columns = ["grupo", "cantidad"]

        grupo_top = etario_df.iloc[0]

        st.info(
            f"Grupo etario predominante: {grupo_top['grupo']} con {grupo_top['cantidad']} registros."
        )

    else:
        st.warning("No se puede calcular grupo etario sin la columna edad")

    st.markdown("---")

    # =========================
    # ADULTOS MAYORES EN RIESGO
    # =========================
    if "grupo_etario" in df.columns and "nivel_riesgo" in df.columns:

        adultos_criticos = len(
            df[
                (df["grupo_etario"] == "Adulto mayor") &
                (df["nivel_riesgo"].isin(["Alto", "Crítico"]))
            ]
        )

        adultos_total = len(df[df["grupo_etario"] == "Adulto mayor"])

        st.error(
            f"👴 Adultos mayores en alto/crítico riesgo: {adultos_criticos}"
        )

        st.warning(
            f"Total adultos mayores: {adultos_total}"
        )

    else:
        st.info("No se puede calcular riesgo en adultos mayores")

    st.markdown("---")

    # =========================
    # JÓVENES EN RIESGO
    # =========================
    if "grupo_etario" in df.columns and "nivel_riesgo" in df.columns:

        jovenes_criticos = len(
            df[
                (df["grupo_etario"] == "Joven") &
                (df["nivel_riesgo"].isin(["Alto", "Crítico"]))
            ]
        )

        jovenes_total = len(df[df["grupo_etario"] == "Joven"])

        if jovenes_total > 0:
            porcentaje_jovenes_criticos = round(
                (jovenes_criticos / jovenes_total) * 100,
                2
            )
        else:
            porcentaje_jovenes_criticos = 0

        st.warning(
            f"🧑 Jóvenes en alta vulnerabilidad: {jovenes_criticos} "
            f"({porcentaje_jovenes_criticos}%)"
        )

    else:
        st.info("No se puede calcular jóvenes en riesgo")

    st.markdown("---")

    # =========================
    # ETNIA VS CONSUMO
    # =========================
    st.subheader("💊 Etnia vs Consumo")

    if "grupos_etnicos" in df.columns and "tipo_consumo" in df.columns:

        tabla = pd.crosstab(
            df["grupos_etnicos"],
            df["tipo_consumo"]
        )

        st.dataframe(tabla)

    else:
        st.warning("No existen columnas para etnia vs consumo")
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
# NUEVO REGISTRO
# =========================

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

            numero_id = st.text_input(
                "Número de identificación"
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
                [
                    "Ninguno",
                    "Primaria",
                    "Secundaria",
                    "Técnico",
                    "Tecnólogo",
                    "Universitario"
                ]
            )

            barrio = st.text_input("Barrio")

            comuna = st.text_input("Comuna")

            telefono = st.text_input("Teléfono")

            consumo = st.selectbox(
                "Consumo",
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
                ["No", "Sí"]
            )

            guardar = st.form_submit_button(
                "💾 Guardar registro"
            )

        if guardar:

            sql = text("""
                INSERT INTO habitante_de_calle
                (
                    nombres,
                    apellidos,
                    sexo_al_nacer,
                    edad,
                    tipo_de_identificacion,
                    numero_de_identidadficacion_____sin_puntos,_ni_rayas,el_registr,
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

                st.error(f"Error al guardar: {e}")

    else:

        st.info(
            "Ingrese la contraseña para habilitar el formulario."
        )
            

# =====================================
# SEGUIMIENTO PROFESIONAL
# =====================================

with tab12:

    st.title("📋 Seguimiento Profesional")

    cedula = st.text_input(
        "Número de identificación",
        key="cedula_seguimiento"
    )

    if cedula:

        try:

            usuario = pd.read_sql(
                f"""
                SELECT *
                FROM habitante_de_calle
                WHERE numero_identificacion = '{cedula}'
                """,
                engine
            )

            if usuario.empty:

                st.warning("Usuario no encontrado")

            else:

                datos = usuario.iloc[0]

                st.success("Usuario encontrado")

                col1, col2, col3 = st.columns(3)

                col1.metric(
                    "Nombre",
                    f"{datos['nombres']} {datos['apellidos']}"
                )

                col2.metric(
                    "Edad",
                    datos["edad"]
                )

                col3.metric(
                    "Documento",
                    cedula
                )

                st.divider()

                modulo = st.selectbox(
                    "Seleccione módulo",
                    [
                        "Acciones Profesionales",
                        "Asistencia",
                        "Adherencia al Tratamiento",
                        "Valoración Integral",
                        "Plan de Intervención"
                    ]
                )

                # =====================================
                # ACCIONES PROFESIONALES
                # =====================================

                if modulo == "Acciones Profesionales":

                    with st.form("acciones"):

                        profesional = st.selectbox(
                            "Profesional",
                            [
                                "Psicología",
                                "Trabajo Social",
                                "Pedagogía",
                                "Enfermería",
                                "Coordinación",
                                "Dirección"
                            ]
                        )

                        tipo_accion = st.text_input(
                            "Tipo de acción"
                        )

                        observaciones = st.text_area(
                            "Observaciones"
                        )

                        guardar = st.form_submit_button(
                            "Guardar Acción"
                        )

                    if guardar:

                        sql = text("""
                        INSERT INTO acciones_profesionales
                        (
                            documento_usuario,
                            profesional,
                            tipo_accion,
                            observaciones
                        )
                        VALUES
                        (
                            :documento,
                            :profesional,
                            :accion,
                            :obs
                        )
                        """)

                        with engine.begin() as conn:

                            conn.execute(
                                sql,
                                {
                                    "documento": cedula,
                                    "profesional": profesional,
                                    "accion": tipo_accion,
                                    "obs": observaciones
                                }
                            )

                        st.success(
                            "Acción registrada"
                        )

                # =====================================
                # ASISTENCIA
                # =====================================

                elif modulo == "Asistencia":

                    with st.form("asistencia"):

                        fecha = st.date_input(
                            "Fecha"
                        )

                        asistencia = st.selectbox(
                            "Asistencia",
                            [
                                "Asistió",
                                "No asistió"
                            ]
                        )

                        observaciones = st.text_area(
                            "Observaciones"
                        )

                        guardar = st.form_submit_button(
                            "Guardar Asistencia"
                        )

                    if guardar:

                        sql = text("""
                        INSERT INTO asistencias
                        (
                            documento_usuario,
                            fecha,
                            asistencia,
                            observaciones
                        )
                        VALUES
                        (
                            :documento,
                            :fecha,
                            :asistencia,
                            :obs
                        )
                        """)

                        with engine.begin() as conn:

                            conn.execute(
                                sql,
                                {
                                    "documento": cedula,
                                    "fecha": fecha,
                                    "asistencia": asistencia,
                                    "obs": observaciones
                                }
                            )

                        st.success(
                            "Asistencia registrada"
                        )

                # =====================================
                # ADHERENCIA
                # =====================================

                elif modulo == "Adherencia al Tratamiento":

                    with st.form("adherencia"):

                        tratamiento = st.text_input(
                            "Tratamiento"
                        )

                        adherencia = st.selectbox(
                            "Nivel de adherencia",
                            [
                                "Alta",
                                "Media",
                                "Baja"
                            ]
                        )

                        observaciones = st.text_area(
                            "Observaciones"
                        )

                        guardar = st.form_submit_button(
                            "Guardar Adherencia"
                        )

                    if guardar:

                        sql = text("""
                        INSERT INTO adherencia_tratamiento
                        (
                            documento_usuario,
                            tratamiento,
                            adherencia,
                            observaciones
                        )
                        VALUES
                        (
                            :documento,
                            :tratamiento,
                            :adherencia,
                            :obs
                        )
                        """)

                        with engine.begin() as conn:

                            conn.execute(
                                sql,
                                {
                                    "documento": cedula,
                                    "tratamiento": tratamiento,
                                    "adherencia": adherencia,
                                    "obs": observaciones
                                }
                            )

                        st.success(
                            "Adherencia registrada"
                        )

                # =====================================
                # VALORACIÓN
                # =====================================

                elif modulo == "Valoración Integral":

                    with st.form("valoracion"):

                        riesgo = st.selectbox(
                            "Nivel de riesgo",
                            [
                                "Bajo",
                                "Medio",
                                "Alto",
                                "Crítico"
                            ]
                        )

                        observaciones = st.text_area(
                            "Valoración"
                        )

                        guardar = st.form_submit_button(
                            "Guardar Valoración"
                        )

                    if guardar:

                        sql = text("""
                        INSERT INTO valoraciones_integrales
                        (
                            documento_usuario,
                            nivel_riesgo,
                            observaciones
                        )
                        VALUES
                        (
                            :documento,
                            :riesgo,
                            :obs
                        )
                        """)

                        with engine.begin() as conn:

                            conn.execute(
                                sql,
                                {
                                    "documento": cedula,
                                    "riesgo": riesgo,
                                    "obs": observaciones
                                }
                            )

                        st.success(
                            "Valoración registrada"
                        )

                # =====================================
                # PLAN INTERVENCIÓN
                # =====================================

                elif modulo == "Plan de Intervención":

                    with st.form("plan"):

                        objetivo = st.text_input(
                            "Objetivo"
                        )

                        responsable = st.selectbox(
                            "Responsable",
                            [
                                "Psicología",
                                "Trabajo Social",
                                "Pedagogía",
                                "Enfermería"
                            ]
                        )

                        fecha_meta = st.date_input(
                            "Fecha meta"
                        )

                        guardar = st.form_submit_button(
                            "Guardar Plan"
                        )

                    if guardar:

                        sql = text("""
                        INSERT INTO plan_intervencion
                        (
                            documento_usuario,
                            objetivo,
                            responsable,
                            fecha_meta
                        )
                        VALUES
                        (
                            :documento,
                            :objetivo,
                            :responsable,
                            :fecha_meta
                        )
                        """)

                        with engine.begin() as conn:

                            conn.execute(
                                sql,
                                {
                                    "documento": cedula,
                                    "objetivo": objetivo,
                                    "responsable": responsable,
                                    "fecha_meta": fecha_meta
                                }
                            )

                        st.success(
                            "Plan registrado"
                        )

        except Exception as e:

            st.error(f"Error: {e}")

    else:

        st.info(
            "Ingrese un número de identificación para iniciar el seguimiento."
        )
    # =====================================
# SEGUIMIENTO E IMPACTO
# =====================================

with tab13:

    st.title("📈 Seguimiento e Impacto")

    try:

        df_acciones = pd.read_sql(
            "SELECT * FROM acciones_profesionales",
            engine
        )

        df_asistencia = pd.read_sql(
            "SELECT * FROM asistencias",
            engine
        )

        df_adherencia = pd.read_sql(
            "SELECT * FROM adherencia_tratamiento",
            engine
        )

        df_valoracion = pd.read_sql(
            "SELECT * FROM valoraciones_integrales",
            engine
        )

        # =========================
        # KPIs
        # =========================

        st.subheader("📊 Indicadores Generales")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Acciones",
            len(df_acciones)
        )

        c2.metric(
            "Asistencias",
            len(df_asistencia)
        )

        c3.metric(
            "Adherencias",
            len(df_adherencia)
        )

        c4.metric(
            "Valoraciones",
            len(df_valoracion)
        )

        st.divider()

        # =========================
        # ACCIONES POR PROFESIONAL
        # =========================

        if len(df_acciones) > 0:

            st.subheader("👨‍⚕️ Productividad por profesional")

            acciones_prof = (
                df_acciones
                .groupby("profesional")
                .size()
                .reset_index(name="acciones")
            )

            fig = px.bar(
                acciones_prof,
                x="profesional",
                y="acciones",
                title="Acciones realizadas"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        # =========================
        # ASISTENCIAS
        # =========================

        if len(df_asistencia) > 0:

            st.subheader("📅 Asistencia")

            fig = px.pie(
                df_asistencia,
                names="asistencia",
                title="Distribución asistencia"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        # =========================
        # ADHERENCIA
        # =========================

        if len(df_adherencia) > 0:

            st.subheader("💊 Adherencia al tratamiento")

            fig = px.pie(
                df_adherencia,
                names="adherencia",
                title="Nivel de adherencia"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        # =========================
        # RIESGO
        # =========================

        if len(df_valoracion) > 0:

            st.subheader("⚠️ Valoraciones")

            fig = px.histogram(
                df_valoracion,
                x="nivel_riesgo",
                color="nivel_riesgo",
                title="Nivel de riesgo"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        st.divider()

        # =========================
        # HISTORIA SOCIAL
        # =========================

        st.subheader("📋 Historia Social del Usuario")

        cedula_historia = st.text_input(
            "Número de identificación",
            key="historia_social"
        )

        if cedula_historia:

            acciones = pd.read_sql(
                f"""
                SELECT *
                FROM acciones_profesionales
                WHERE documento_usuario = '{cedula_historia}'
                """,
                engine
            )

            adherencia = pd.read_sql(
                f"""
                SELECT *
                FROM adherencia_tratamiento
                WHERE documento_usuario = '{cedula_historia}'
                """,
                engine
            )

            valoraciones = pd.read_sql(
                f"""
                SELECT *
                FROM valoraciones_integrales
                WHERE documento_usuario = '{cedula_historia}'
                """,
                engine
            )

            planes = pd.read_sql(
                f"""
                SELECT *
                FROM plan_intervencion
                WHERE documento_usuario = '{cedula_historia}'
                """,
                engine
            )

            st.markdown("### 👨‍⚕️ Acciones Profesionales")
            st.dataframe(
                acciones,
                use_container_width=True
            )

            st.markdown("### 💊 Adherencia")
            st.dataframe(
                adherencia,
                use_container_width=True
            )

            st.markdown("### ⚠️ Valoraciones")
            st.dataframe(
                valoraciones,
                use_container_width=True
            )

            st.markdown("### 🎯 Plan de Intervención")
            st.dataframe(
                planes,
                use_container_width=True
            )

    except Exception as e:

        st.error(
            f"Error cargando indicadores: {e}"
        )