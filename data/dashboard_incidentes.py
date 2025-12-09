import os
from datetime import datetime, date

import pandas as pd
import streamlit as st

# --- Rutas ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INCIDENTES_CSV = os.path.join(PROJECT_ROOT, "data", "incidentes_soptecgt.csv")


@st.cache_data
def cargar_incidentes():
    """Carga el CSV de incidentes en un DataFrame."""
    # 1) Si no existe el archivo, devolvemos un DataFrame vacío
    if not os.path.exists(INCIDENTES_CSV):
        st.warning("Aún no hay incidentes registrados en el archivo CSV.")
        return pd.DataFrame()

    # 2) Cargar el CSV
    df = pd.read_csv(INCIDENTES_CSV)

    # 3) Si está vacío, también devolvemos vacío
    if df.empty:
        st.warning("Aún no hay incidentes registrados en el archivo CSV.")
        return df

    # 4) Normalizar columnas esperadas
    columnas_esperadas = [
        "fecha",
        "hora",
        "sucursal",
        "nombre_sucursal",
        "empleado",
        "codigo_empleado",
        "categoria",
        "subcategoria",
        "descripcion",
        "ticket_id",
        "estado",
    ]
    for col in columnas_esperadas:
        if col not in df.columns:
            df[col] = ""

    # 5) Convertir fecha y crear columna combinada fecha_hora
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date
    df["fecha_hora"] = pd.to_datetime(
        df["fecha"].astype(str) + " " + df["hora"].astype(str),
        errors="coerce",
    )

    return df



def aplicar_filtros(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica filtros desde la barra lateral de Streamlit."""
    if df.empty:
        return df

    with st.sidebar:
        st.header("Filtros")

        # Rango de fechas
        min_date = df["fecha"].min()
        max_date = df["fecha"].max()
        if isinstance(min_date, date) and isinstance(max_date, date):
            rango_fechas = st.date_input(
                "Rango de fechas",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
            )
        else:
            rango_fechas = None

        # Sucursal
        sucursales = sorted(df["nombre_sucursal"].dropna().unique().tolist())
        sucursal_sel = st.multiselect(
            "Sucursal",
            options=sucursales,
            default=sucursales,
        )

        # Categoría
        categorias = sorted(df["categoria"].dropna().unique().tolist())
        categoria_sel = st.multiselect(
            "Categoría",
            options=categorias,
            default=categorias,
        )

        # Estado
        estados = sorted(df["estado"].dropna().unique().tolist())
        if estados:
            estado_sel = st.multiselect(
                "Estado",
                options=estados,
                default=estados,
            )
        else:
            estado_sel = []

    df_filtrado = df.copy()

    # Filtro por fechas
    if rango_fechas and isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
        inicio, fin = rango_fechas
        df_filtrado = df_filtrado[
            (df_filtrado["fecha"] >= inicio) & (df_filtrado["fecha"] <= fin)
        ]

    # Filtro por sucursal
    if sucursal_sel:
        df_filtrado = df_filtrado[df_filtrado["nombre_sucursal"].isin(sucursal_sel)]

    # Filtro por categoría
    if categoria_sel:
        df_filtrado = df_filtrado[df_filtrado["categoria"].isin(categoria_sel)]

    # Filtro por estado
    if estado_sel:
        df_filtrado = df_filtrado[df_filtrado["estado"].isin(estado_sel)]

    return df_filtrado


def main():
    st.set_page_config(
        page_title="Dashboard Incidentes - Soporte Técnico GT",
        layout="wide",
    )
    
    st.title("Dashboard de Incidentes Reportados por Chatbot de SopTec GT")

    df = cargar_incidentes()

    if df.empty:
        st.info("Aún no hay incidentes registrados en el archivo CSV.")
        return

    df_filtrado = aplicar_filtros(df)    
    # --- Últimos incidentes ---
    st.subheader("Últimos incidentes reportados")

    df_ordenado = df_filtrado.sort_values("fecha_hora", ascending=False)

    st.dataframe(
        df_ordenado[
            [
                "fecha",
                "hora",
                "ticket_id",
                "estado",
                "empleado",
                "codigo_empleado",
                "sucursal",
                "nombre_sucursal",
                "categoria",
                "subcategoria",
                "descripcion",
            ]
        ],
        use_container_width=True,
        height=400,
    )

    # --- Métricas principales ---
    col1, col2, col3, col4 = st.columns(4)

    total_incidentes = len(df_filtrado)
    abiertos = (df_filtrado["estado"] == "Abierto").sum()
    cerrados = (df_filtrado["estado"] == "Cerrado").sum()
    sucursales_distintas = df_filtrado["sucursal"].nunique()

    col1.metric("Incidentes filtrados", total_incidentes)
    col2.metric("Abiertos", abiertos)
    col3.metric("Cerrados", cerrados)
    col4.metric("Sucursales afectadas", sucursales_distintas)

    st.markdown("---")

    # --- Incidentes por sucursal ---
    st.subheader("Incidentes por sucursal")
    inc_por_sucursal = (
        df_filtrado.groupby(["sucursal", "nombre_sucursal"])["ticket_id"]
        .count()
        .reset_index(name="total_incidentes")
        .sort_values("total_incidentes", ascending=False)
    )

    st.dataframe(inc_por_sucursal, use_container_width=True)

    # --- Incidentes por categoría ---
    st.subheader("Incidentes por categoría")
    inc_por_categoria = (
        df_filtrado.groupby("categoria")["ticket_id"]
        .count()
        .reset_index(name="total_incidentes")
        .sort_values("total_incidentes", ascending=False)
    )

    st.dataframe(inc_por_categoria, use_container_width=True)
    html_code = """
    <div style="text-align: center;">
    <img src="https://storage.googleapis.com/multimedia_bot/sos.jpeg" alt="Imagen centrada" style="display: inline-block;" width="300"/>
    </div>"""

    st.markdown(html_code, unsafe_allow_html=True)
    


if __name__ == "__main__":
    main()
