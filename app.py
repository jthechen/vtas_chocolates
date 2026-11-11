import streamlit as st
import requests
import pandas as pd
import io
import plotly.express as px

# 1. Configuración de la página
st.set_page_config(
    page_title="🍫 Dashboard Integral - Chocolatería",
    page_icon="🍫",
    layout="wide"
)

# 2. Inyección de CSS Personalizado (Estilo Chocolates & Ventas)
st.markdown("""
    <style>
    /* Fondo principal de la app */
    .stApp {
        background-color: #FDFBF7;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Encabezado Principal */
    .main-title {
        color: #2B1B17;
        text-align: center;
        font-weight: 800;
        font-size: 2.3rem;
        margin-bottom: 5px;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }
    
    .sub-title {
        color: #5D4037;
        text-align: center;
        font-size: 1.05rem;
        margin-bottom: 25px;
    }
    
    /* Contenedores y Tarjetas */
    .css-card {
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 20px;
        border-left: 6px solid #4E342E;
        box-shadow: 0 4px 12px rgba(43, 27, 23, 0.08);
        margin-bottom: 20px;
    }
    
    /* Personalización de Botones */
    .stButton>button {
        background-color: #4E342E !important;
        color: #FFFFFF !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 10px 24px !important;
        width: 100%;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0,0,0,0.12);
    }
    
    .stButton>button:hover {
        background-color: #2B1B17 !important;
        box-shadow: 0 6px 10px rgba(0,0,0,0.2);
        transform: translateY(-1px);
    }

    /* Caja de carga de archivos */
    [data-testid="stFileUploader"] {
        background-color: #FFF8F0;
        border: 2px dashed #8D6E63;
        border-radius: 10px;
        padding: 15px;
    }
    
    /* Separador elegante */
    hr {
        border-top: 1px solid #D7CCC8;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Encabezados visuales globales
st.markdown('<div class="main-title">🍫 Ingesta Dinámica & Dashboard Predictivo</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Plataforma de Abastecimiento & Modelo Predictivo de Demandas de Chocolates</div>', unsafe_allow_html=True)

# Estado de la sesión para mantener los datos al cambiar de pestaña
if "resultado_n8n" not in st.session_state:
    st.session_state["resultado_n8n"] = None
if "df_transaccional" not in st.session_state:
    st.session_state["df_transaccional"] = None

# URL de Producción de n8n
N8N_WEBHOOK_URL = "https://jthechen.app.n8n.cloud/webhook/192e7443-2079-4375-9c11-de9fdf6865c4"

# ---------------------------------------------------------
# NAVEGACIÓN POR PESTAÑAS (Pestaña 3 eliminada)
# ---------------------------------------------------------
tab_ingesta, tab_analisis = st.tabs([
    "📥 1. Ingesta Dinámica", 
    "📈 2. Análisis Histórico & Predicción"
])

# =========================================================
# PESTAÑA 1: INGESTA DINÁMICA DE VENTAS
# =========================================================
with tab_ingesta:
    with st.container():
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.subheader("📥 Cargar Transacciones Diarias")
        st.write("Sube el archivo CSV o Excel con los registros recientes para actualizar automáticamente la base histórica y ejecutar la predicción de demanda.")
        
        archivo_ventas = st.file_uploader("Arrastra y suelta tu archivo CSV o Excel aquí", type=["csv", "xlsx"])
        st.markdown('</div>', unsafe_allow_html=True)

    if archivo_ventas:
        try:
            if archivo_ventas.name.endswith(".csv"):
                df = pd.read_csv(archivo_ventas)
            else:
                df = pd.read_excel(archivo_ventas)
                
            st.session_state["df_transaccional"] = df.copy()
            
            with st.expander("👀 Ver vista previa de las transacciones originales", expanded=False):
                st.dataframe(df.head(5), use_container_width=True)
        except Exception as e:
            st.warning("⚠️ No se pudo previsualizar el archivo.")

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🚀 Procesar Ventas y Ejecutar Modelo Predictivo"):
            with st.spinner("☕ Transformando datos a serie diaria y procesando en n8n..."):
                
                # Agrupación a TOTAL_RED
                if 'order_date' in df.columns and 'quantity' in df.columns:
                    df_diario = df.groupby('order_date', as_index=False)['quantity'].sum()
                    df_diario = df_diario.rename(columns={'order_date': 'date'})
                    df_diario['scope'] = 'TOTAL_RED'
                elif 'date' in df.columns and 'quantity' in df.columns:
                    df_diario = df[['date', 'quantity']].copy()
                    if 'scope' not in df_diario.columns:
                        df_diario['scope'] = 'TOTAL_RED'
                else:
                    st.error("El archivo no tiene las columnas necesarias.")
                    df_diario = None

                if df_diario is not None:
                    st.markdown("### 📊 Datos consolidados (TOTAL_RED)")
                    st.dataframe(df_diario.head(5), use_container_width=True)

                    csv_buffer = io.BytesIO()
                    df_diario.to_csv(csv_buffer, index=False)
                    csv_buffer.seek(0)

                    files = {"file": ("ventas_agrupadas.csv", csv_buffer, "text/csv")}

                    try:
                        respuesta = requests.post(N8N_WEBHOOK_URL, files=files, timeout=150)

                        if respuesta.status_code == 200:
                            st.success("✅ ¡Flujo ejecutado con éxito!")
                            st.info("El modelo procesó el historial, Gemini generó la recomendación estratégica y las notificaciones fueron enviadas.")
                            
                            try:
                                respuesta_json = respuesta.json()
                                st.session_state["resultado_n8n"] = respuesta_json
                                with st.expander("📄 Diagnóstico y Respuesta Detallada (JSON)"):
                                    st.json(respuesta_json)
                            except:
                                pass
                        else:
                            st.error(f"❌ Error en la ejecución del pipeline n8n. Código de estado: {respuesta.status_code}")
                            st.code(respuesta.text)
                    except requests.exceptions.RequestException as e:
                        st.error(f"❌ Error de conexión con el flujo automatizado: {e}")

# =========================================================
# PESTAÑA 2: ANÁLISIS & PREDICCIÓN
# =========================================================
with tab_analisis:
    st.header("📈 Centro de Control & Resultados")
    
    res = st.session_state["resultado_n8n"]
    df_trans = st.session_state["df_transaccional"]

    if res is not None:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        fecha_corte = res.get("fecha_corte", "N/A")
        modelo_sel = res.get("modelo_seleccionado", "N/A")
        pronostico_7dias = float(res.get("demanda_total_7_dias", 0.0))
        
        metricas = res.get("metricas_modelo_seleccionado", {})
        mae = metricas.get("MAE", 0.0)
        rmse = metricas.get("RMSE", 0.0)
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Última Fecha de Corte", str(fecha_corte))
        k2.metric("Demanda (7 días)", f"{pronostico_7dias:,.2f} unds")
        k3.metric("Modelo", str(modelo_sel))
        k4.metric("MAE / RMSE", f"{mae} / {rmse}")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.subheader("🤖 Diagnóstico de IA (Gemini)")
        st.info(f"**Prioridad:** {str(res.get('prioridad', 'media')).upper()}\n\n"
                f"**Diagnóstico:** {res.get('diagnostico', '')}\n\n"
                f"**Recomendación:** {res.get('recomendacion', '')}")
    else:
        st.info("💡 Ejecuta el modelo en la pestaña de Ingesta Dinámica para ver los resultados predictivos.")

    st.markdown("---")
    
    # Validar que sea un archivo transaccional antes de procesar gráficos de revenue
    if df_trans is not None:
        columnas_esperadas = ['order_date', 'revenue', 'profit', 'quantity']
        if all(col in df_trans.columns for col in columnas_esperadas):
            st.subheader("📊 Análisis Histórico por Períodos")
            df_trans['order_date'] = pd.to_datetime(df_trans['order_date'])
            
            frecuencia = st.radio("Agrupar Evolución Temporal por:", ["Día", "Semana"], horizontal=True)
            freq_code = 'D' if frecuencia == "Día" else 'W-MON'
            
            df_grouped = df_trans.groupby(pd.Grouper(key='order_date', freq=freq_code)).agg({
                'revenue': 'sum',
                'profit': 'sum'
            }).reset_index()
            
            fig = px.line(df_grouped, x='order_date', y=['revenue', 'profit'], title=f"Ingresos y Ganancias ({frecuencia})", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Carga un archivo transaccional completo (con ingresos y márgenes) para habilitar gráficos detallados de ventas.")
