import io
import unicodedata

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# =========================================================
# 1. CONFIGURACIÓN
# =========================================================
st.set_page_config(
    page_title="🍫 Dashboard Integral - Chocolatería",
    page_icon="🍫",
    layout="wide",
)

# Pega aquí las Production URLs que muestra cada nodo Webhook de n8n.
# 1) Webhook POST que guarda transacciones originales en Ventas_Detalle.
N8N_DETAIL_WEBHOOK_URL = "https://jthechen.app.n8n.cloud/webhook/ventas-detalle"
# 2) Webhook POST actual que recibe la serie diaria y ejecuta el pronóstico.
N8N_FORECAST_WEBHOOK_URL = "https://jthechen.app.n8n.cloud/webhook/192e7443-2079-4375-9c11-de9fdf6865c4"
# 3) (Recomendado) Webhook GET que devuelve el historial guardado en Sheets.
#    Debe responder JSON con esta forma: {"ventas": [{...}, {...}]}
N8N_DASHBOARD_WEBHOOK_URL = "https://jthechen.app.n8n.cloud/webhook/456e80f2-09d7-420a-b58a-d703ab69f64c"

# Déjalo vacío si no configuraste Header Auth en los Webhooks.
# Si sí configuraste Header Auth, pega aquí el valor compartido con n8n.
N8N_WEBHOOK_TOKEN = ""

REQUEST_TIMEOUT = 180

# =========================================================
# 2. ESTILO
# =========================================================
st.markdown(
    """
    <style>
    .stApp {
        background-color: #FDFBF7;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .main-title {
        color: #2B1B17;
        text-align: center;
        font-weight: 800;
        font-size: 2.3rem;
        margin-bottom: 5px;
    }
    .sub-title {
        color: #5D4037;
        text-align: center;
        font-size: 1.05rem;
        margin-bottom: 25px;
    }
    [data-testid="stFileUploader"] {
        background-color: #FFF8F0;
        border: 2px dashed #8D6E63;
        border-radius: 10px;
        padding: 15px;
    }
    hr { border-top: 1px solid #D7CCC8; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-title">🍫 Ingesta Dinámica & Dashboard Predictivo</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-title">Plataforma de Abastecimiento & Modelo Predictivo de Demanda de Chocolates</div>',
    unsafe_allow_html=True,
)

# =========================================================
# 3. ESTADO DE LA SESIÓN
# =========================================================
if "resultado_n8n" not in st.session_state:
    st.session_state["resultado_n8n"] = None
if "df_transaccional" not in st.session_state:
    st.session_state["df_transaccional"] = None
if "mensaje_ingesta" not in st.session_state:
    st.session_state["mensaje_ingesta"] = None
if "error_detalle" not in st.session_state:
    st.session_state["error_detalle"] = None

# =========================================================
# 4. FUNCIONES AUXILIARES
# =========================================================
def headers_n8n():
    """Devuelve el encabezado de autenticación solo si se configuró un token."""
    if N8N_WEBHOOK_TOKEN.strip():
        return {"X-Webhook-Token": N8N_WEBHOOK_TOKEN.strip()}
    return {}


def normalizar_nombre_columna(nombre):
    nombre = str(nombre).strip().lower()
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = "".join(c for c in nombre if not unicodedata.combining(c))
    return "_".join(nombre.replace("-", " ").split())


def preparar_transacciones(df_original):
    """Normaliza encabezados y nombres clave sin eliminar columnas originales."""
    df = df_original.copy()
    df.columns = [normalizar_nombre_columna(c) for c in df.columns]

    alias = {
        "fecha": ["order_date", "date", "fecha", "transaction_date"],
        "cantidad": ["quantity", "qty", "cantidad", "unidades", "boxes_shipped"],
        "producto": ["product", "producto", "item", "sku"],
        "ingreso": ["revenue", "amount", "sales", "ingreso", "ventas", "monto"],
        "precio_unitario": ["unit_price", "price", "precio_unitario", "precio"],
        "ganancia": ["profit", "ganancia", "margin"],
    }

    renombrar = {}
    for nombre_estandar, alternativas in alias.items():
        if nombre_estandar in df.columns:
            continue
        encontrada = next((c for c in alternativas if c in df.columns), None)
        if encontrada:
            renombrar[encontrada] = nombre_estandar
    df = df.rename(columns=renombrar)

    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(
            df["fecha"],
            errors="coerce",
            dayfirst=False
        )
    if "cantidad" in df.columns:
        df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")
    for col in ["ingreso", "precio_unitario", "ganancia"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def construir_serie_diaria(df):
    """Prepara la serie date/quantity/scope que espera el flujo predictivo."""
    if "fecha" not in df.columns or "cantidad" not in df.columns:
        raise ValueError(
            "El archivo debe incluir una columna de fecha y otra de cantidad. "
            "Encabezados aceptados incluyen order_date/date/fecha y quantity/qty/cantidad."
        )

    validas = df.dropna(subset=["fecha", "cantidad"]).copy()
    if validas.empty:
        raise ValueError("No encontré filas válidas con fecha y cantidad.")

    diario = (
        validas.groupby(validas["fecha"].dt.date, as_index=False)["cantidad"]
        .sum()
        .rename(columns={"fecha": "date", "cantidad": "quantity"})
    )
    diario["date"] = pd.to_datetime(diario["date"]).dt.strftime("%Y-%m-%d")
    diario["scope"] = "TOTAL_RED"
    return diario[["date", "quantity", "scope"]]


def enviar_csv_a_webhook(url, nombre_archivo, dataframe):
    buffer = io.BytesIO()
    dataframe.to_csv(buffer, index=False, encoding="utf-8")
    buffer.seek(0)
    respuesta = requests.post(
        url,
        files={"file": (nombre_archivo, buffer, "text/csv")},
        headers=headers_n8n(),
        timeout=REQUEST_TIMEOUT,
    )
    if not respuesta.ok:
        cuerpo = respuesta.text[:1500]
        raise requests.HTTPError(
            f"HTTP {respuesta.status_code} del Webhook: {cuerpo}",
            response=respuesta,
        )
    return respuesta


def extraer_json_respuesta(respuesta):
    try:
        datos = respuesta.json()
    except ValueError as exc:
        raise ValueError(
            "n8n respondió, pero el cuerpo no es JSON. Revisa la configuración "
            "Respond to Webhook del flujo de pronóstico."
        ) from exc

    # Algunas configuraciones de n8n envuelven la respuesta como lista.
    if isinstance(datos, list):
        datos = datos[0] if datos else {}
    if not isinstance(datos, dict):
        raise ValueError("La respuesta de n8n no tiene el formato JSON esperado.")
    return datos


@st.cache_data(ttl=60, show_spinner=False)
def cargar_ventas_historicas(url, token):
    if not url.strip():
        return None
    headers = {"X-Webhook-Token": token} if token.strip() else {}
    respuesta = requests.get(url.strip(), headers=headers, timeout=60)
    respuesta.raise_for_status()
    datos = respuesta.json()
    if isinstance(datos, dict):
        ventas = datos.get("ventas", [])
    elif isinstance(datos, list):
        ventas = datos
    else:
        ventas = []
    return pd.DataFrame(ventas)

# =========================================================
# 5. PESTAÑAS
# =========================================================
tab_ingesta, tab_analisis = st.tabs(
    ["📥 1. Ingesta Dinámica", "📈 2. Análisis Histórico & Predicción"]
)

# =========================================================
# PESTAÑA 1: CARGA Y EJECUCIÓN DE LOS DOS WEBHOOKS POST
# =========================================================
with tab_ingesta:
    st.subheader("📥 Cargar transacciones")
    st.write(
        "Sube un archivo CSV o Excel. La app enviará las transacciones originales "
        "al Webhook de detalle y la serie diaria al Webhook del pronóstico."
    )

    archivo_ventas = st.file_uploader(
        "Arrastra y suelta el archivo de ventas", type=["csv", "xlsx"]
    )

    if archivo_ventas is not None:
        try:
            if archivo_ventas.name.lower().endswith(".csv"):
                df_original = pd.read_csv(archivo_ventas)
            else:
                df_original = pd.read_excel(archivo_ventas)

            df_normalizado = preparar_transacciones(df_original)
            st.session_state["df_transaccional"] = df_normalizado.copy()

            with st.expander("👀 Vista previa de las transacciones", expanded=False):
                st.dataframe(df_original.head(10), use_container_width=True)

            st.caption(f"Filas leídas: {len(df_original):,}")

            if st.button("🚀 Guardar ventas y ejecutar pronóstico", type="primary"):
                if not N8N_DETAIL_WEBHOOK_URL.strip():
                    st.error("Pega la Production URL del Webhook de detalle en N8N_DETAIL_WEBHOOK_URL.")
                elif not N8N_FORECAST_WEBHOOK_URL.strip():
                    st.error("Pega la Production URL del Webhook de pronóstico en N8N_FORECAST_WEBHOOK_URL.")
                else:
                    try:
                        df_diario = construir_serie_diaria(df_normalizado)
                        st.markdown("#### Serie diaria enviada al modelo")
                        st.dataframe(df_diario.head(10), use_container_width=True)

                        error_detalle = None
                        with st.spinner("Guardando transacciones detalladas en n8n..."):
                            # Llamada 1: envía el detalle original para Ventas_Detalle.
                            # Si falla, guardamos el error pero igual intentamos el pronóstico.
                            try:
                                enviar_csv_a_webhook(
                                    N8N_DETAIL_WEBHOOK_URL.strip(),
                                    "ventas_detalle.csv",
                                    df_original,
                                )
                            except requests.exceptions.RequestException as exc:
                                error_detalle = str(exc)

                        try:
                            with st.spinner("Ejecutando el pronóstico en n8n..."):
                                # Llamada 2: webhook actual con la serie diaria agrupada.
                                respuesta_pronostico = enviar_csv_a_webhook(
                                    N8N_FORECAST_WEBHOOK_URL.strip(),
                                    "ventas_agrupadas.csv",
                                    df_diario,
                                )
                                resultado = extraer_json_respuesta(respuesta_pronostico)

                            st.session_state["resultado_n8n"] = resultado
                            st.session_state["error_detalle"] = error_detalle
                            st.session_state["mensaje_ingesta"] = (
                                "Pronóstico ejecutado. "
                                "El Dashboard se actualizará con la respuesta de n8n."
                            )
                            st.cache_data.clear()
                            st.rerun()

                        except (requests.exceptions.RequestException, ValueError, KeyError) as exc:
                            st.error(f"Falló el Webhook de pronóstico: {exc}")
                            if error_detalle:
                                st.warning(
                                    "También falló el guardado del detalle. "
                                    f"Error del Webhook de detalle: {error_detalle}"
                                )
                    except (ValueError, KeyError) as exc:
                        st.error(f"No pude preparar la serie diaria: {exc}")
        except Exception as exc:
            st.error(f"No pude leer el archivo. Revisa su formato y encabezados. Detalle: {exc}")

    if st.session_state["mensaje_ingesta"]:
        if st.session_state["error_detalle"]:
            st.warning(
                st.session_state["mensaje_ingesta"]
                + " Sin embargo, no se pudo guardar el detalle en Ventas_Detalle: "
                + st.session_state["error_detalle"]
            )
        else:
            st.success(st.session_state["mensaje_ingesta"])

# =========================================================
# PESTAÑA 2: DASHBOARD HISTÓRICO Y PRONÓSTICO
# =========================================================
with tab_analisis:
    st.subheader("📊 Ventas históricas")

    df_historial = None
    if N8N_DASHBOARD_WEBHOOK_URL.strip():
        try:
            df_historial = cargar_ventas_historicas(
                N8N_DASHBOARD_WEBHOOK_URL,
                N8N_WEBHOOK_TOKEN,
            )
        except requests.exceptions.RequestException as exc:
            st.warning(f"No pude leer el historial desde n8n: {exc}")
        except (ValueError, KeyError) as exc:
            st.warning(f"La respuesta del Webhook de Dashboard no es válida: {exc}")
    else:
        st.caption(
            "Para ver ventas de cargas anteriores, configura N8N_DASHBOARD_WEBHOOK_URL "
            "con un Webhook GET que devuelva {\"ventas\": [...]}. Mientras tanto, "
            "se mostrarán solo los datos de esta sesión."
        )

    if df_historial is None or df_historial.empty:
        df_historial = st.session_state["df_transaccional"]
        if df_historial is not None:
            st.info("Mostrando el archivo cargado en esta sesión; todavía no es el historial acumulado.")

    if df_historial is None or df_historial.empty:
        st.info("Carga un archivo de ventas o configura el Webhook GET del Dashboard.")
    else:
        df_historial = preparar_transacciones(df_historial)
        requeridas = {"fecha", "cantidad"}
        if not requeridas.issubset(df_historial.columns):
            st.error("El historial debe incluir columnas de fecha y cantidad.")
        else:
            df_historial = df_historial.dropna(subset=["fecha", "cantidad"]).copy()

            inicio = df_historial["fecha"].min().date()
            fin = df_historial["fecha"].max().date()
            periodo = st.date_input(
                "Período del Dashboard",
                value=(inicio, fin),
                min_value=inicio,
                max_value=fin,
            )
            if isinstance(periodo, tuple) and len(periodo) == 2:
                desde, hasta = periodo
                mascara = df_historial["fecha"].dt.date.between(desde, hasta)
                df_periodo = df_historial.loc[mascara].copy()
            else:
                df_periodo = df_historial.copy()

            unidades = float(df_periodo["cantidad"].sum())
            k1, k2, k3 = st.columns(3)
            k1.metric("Unidades vendidas", f"{unidades:,.0f}")

            if "ingreso" in df_periodo.columns:
                ingresos = float(df_periodo["ingreso"].fillna(0).sum())
                k2.metric("Ingresos", f"${ingresos:,.0f}")
            elif "precio_unitario" in df_periodo.columns:
                ingresos = float(
                    (df_periodo["cantidad"] * df_periodo["precio_unitario"]).sum()
                )
                k2.metric("Ingresos estimados", f"${ingresos:,.0f}")
            else:
                k2.metric("Ingresos", "Sin columna de monto/precio")

            frecuencia = st.radio(
                "Agrupar evolución temporal por:",
                ["Día", "Semana", "Mes"],
                horizontal=True,
            )
            freq_code = {"Día": "D", "Semana": "W-MON", "Mes": "MS"}[frecuencia]
            serie = (
                df_periodo.set_index("fecha")
                .resample(freq_code)
                .agg(unidades=("cantidad", "sum"))
                .reset_index()
            )
            fig_unidades = px.line(
                serie,
                x="fecha",
                y="unidades",
                markers=True,
                title=f"Unidades vendidas por {frecuencia.lower()}",
            )
            st.plotly_chart(fig_unidades, use_container_width=True)

            columna_monto = "ingreso" if "ingreso" in df_periodo.columns else None
            if columna_monto:
                serie_ingresos = (
                    df_periodo.set_index("fecha")
                    .resample(freq_code)
                    .agg(ingresos=(columna_monto, "sum"))
                    .reset_index()
                )
                fig_ingresos = px.line(
                    serie_ingresos,
                    x="fecha",
                    y="ingresos",
                    markers=True,
                    title=f"Ingresos por {frecuencia.lower()}",
                )
                st.plotly_chart(fig_ingresos, use_container_width=True)
            elif "precio_unitario" in df_periodo.columns:
                df_periodo["ingreso_calculado"] = (
                    df_periodo["cantidad"] * df_periodo["precio_unitario"]
                )
                serie_ingresos = (
                    df_periodo.set_index("fecha")
                    .resample(freq_code)
                    .agg(ingresos=("ingreso_calculado", "sum"))
                    .reset_index()
                )
                fig_ingresos = px.line(
                    serie_ingresos,
                    x="fecha",
                    y="ingresos",
                    markers=True,
                    title=f"Ingresos estimados por {frecuencia.lower()}",
                )
                st.plotly_chart(fig_ingresos, use_container_width=True)
