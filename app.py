import streamlit as st
import requests
import pandas as pd
import io

# 1. Configuración de la página
st.set_page_config(
    page_title="🍫 Ingesta Dinámica de Ventas - Chocolatería",
    page_icon="🍫",
    layout="centered"
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

# 3. Encabezados visuales
st.markdown('<div class="main-title">🍫 Ingesta Dinámica de Ventas</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Plataforma de Abastecimiento & Modelo Predictivo de Demandas de Chocolates</div>', unsafe_allow_html=True)

# 4. Sección principal de carga
with st.container():
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    st.subheader("📥 Cargar Transacciones Diarias")
    st.write("Sube el archivo CSV con los registros recientes para actualizar automáticamente la base histórica y ejecutar la predicción de demanda.")
    
    archivo_ventas = st.file_uploader("Arrastra y suelta tu archivo CSV aquí", type=["csv"])
    st.markdown('</div>', unsafe_allow_html=True)

if archivo_ventas:
    # Vista previa de datos cargados
    try:
        df = pd.read_csv(archivo_ventas)
        with st.expander("👀 Ver vista previa de las transacciones originales", expanded=False):
            st.dataframe(df.head(5), use_container_width=True)
    except Exception as e:
        st.warning("⚠️ No se pudo previsualizar el archivo CSV.")

    st.markdown("<br>", unsafe_allow_html=True)

    # 5. Ejecución del procesamiento y envío
    if st.button("🚀 Procesar Ventas y Ejecutar Modelo Predictivo"):
        with st.spinner("☕ Transformando datos a serie diaria y procesando en n8n..."):

            # --- TRANSFORMACIÓN DE DATOS (De Transaccional a Serie Diaria) ---
            # 1. Agrupar por fecha y sumar la cantidad total vendida en el día
            df_diario = df.groupby('order_date', as_index=False)['quantity'].sum()
            
            # 2. Renombrar la columna de fecha a 'date'
            df_diario = df_diario.rename(columns={'order_date': 'date'})
            
            # 3. Añadir la columna 'scope' estricta para el modelo
            df_diario['scope'] = 'TOTAL_RED'
            
            # Mostrar resumen visual del envío
            st.markdown("### 📊 Datos consolidados (TOTAL_RED)")
            st.dataframe(df_diario.head(5), use_container_width=True)

            # Webhook de n8n
            n8n_webhook_url = "https://jthechen.app.n8n.cloud/webhook/192e7443-2079-4375-9c11-de9fdf6865c4"

            # Preparar el archivo transformado para el envío en memoria
            csv_buffer = io.BytesIO()
            df_diario.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)

            files = {
                "file": ("ventas_agrupadas.csv", csv_buffer, "text/csv")
            }

            try:
                # Enviar solicitud POST al Webhook
                respuesta = requests.post(n8n_webhook_url, files=files, timeout=150)

                if respuesta.status_code == 200:
                    st.success("✅ ¡Flujo ejecutado con éxito!")
                    st.info("El modelo de media móvil procesó el historial, Gemini generó la recomendación estratégica y las notificaciones fueron enviadas.")

                    # Respuesta detallada de n8n en formato JSON
                    try:
                        respuesta_json = respuesta.json()
                        with st.expander("📄 Diagnóstico y Respuesta Detallada (JSON)"):
                            st.json(respuesta_json)
                    except:
                        pass
                else:
                    st.error(f"❌ Error en la ejecución del pipeline n8n. Código de estado: {respuesta.status_code}")
                    st.code(respuesta.text)

            except requests.exceptions.RequestException as e:
                st.error(f"❌ Error de conexión con el flujo automatizado: {e}")
