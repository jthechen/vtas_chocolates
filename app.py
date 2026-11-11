import streamlit as st
import requests
import pandas as pd
import io

st.set_page_config(page_title="🍫 Ingesta Dinámica de Ventas", layout="centered")

st.title("🍫 Ingesta Dinámica de Ventas - Chocolates")
st.write("Sube el archivo CSV con las ventas recientes para actualizar el modelo predictivo.")

# 1. Carga de archivo
archivo_ventas = st.file_uploader("Arrastra aquí el archivo de ventas diario (CSV)", type=["csv"])

if archivo_ventas:
    # Vista previa opcional de los datos originales
    try:
        df = pd.read_csv(archivo_ventas)
        st.write("Vista previa de los datos originales:")
        st.dataframe(df.head(3))
    except Exception as e:
        st.warning("No se pudo previsualizar el archivo CSV.")

    # 2. Botón de procesamiento
    if st.button("Procesar Ventas y Ejecutar Modelo"):
        with st.spinner("Agrupando datos y enviando a n8n..."):

            # --- TRANSFORMACIÓN DE DATOS (De Transaccional a Serie Diaria) ---
            # 1. Agrupar por fecha y sumar la cantidad total vendida en el día
            df_diario = df.groupby('order_date', as_index=False)['quantity'].sum()
            
            # 2. Renombrar la columna de fecha a 'date'
            df_diario = df_diario.rename(columns={'order_date': 'date'})
            
            # 3. Añadir la columna 'scope' estricta para el modelo
            df_diario['scope'] = 'TOTAL_RED'
            
            # Mostrar al usuario cómo quedó el dato resumido
            st.write("Datos agrupados enviados a n8n:")
            st.dataframe(df_diario.head(3))

            # --- AQUÍ DEBES PEGAR TU TEST URL DE N8N ---
            n8n_webhook_url = "https://jthechen.app.n8n.cloud/webhook-test/192e7443-2079-4375-9c11-de9fdf6865c4"

            # Preparar el archivo transformado para el envío creando un CSV en memoria
            csv_buffer = io.BytesIO()
            df_diario.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)

            # Formato multipart para enviar archivos a n8n
            files = {
                "file": ("ventas_agrupadas.csv", csv_buffer, "text/csv")
            }

            try:
                # Enviar solicitud POST al Webhook
                respuesta = requests.post(n8n_webhook_url, files=files, timeout=60)

                # Manejar la respuesta
                if respuesta.status_code == 200:
                    st.success("✅ ¡Flujo ejecutado con éxito!")
                    st.write("El modelo de media móvil ha procesado los datos, Gemini generó el JSON y se han enviado las notificaciones por Gmail y Telegram.")

                    # Mostrar la respuesta de n8n si la devuelve en formato JSON
                    try:
                        respuesta_json = respuesta.json()
                        with st.expander("Ver respuesta detallada de n8n"):
                            st.json(respuesta_json)
                    except:
                        pass # La respuesta no era JSON
                else:
                    st.error(f"❌ Error en la ejecución de n8n. Código de estado: {respuesta.status_code}")
                    st.write(respuesta.text)

            except requests.exceptions.RequestException as e:
                 st.error(f"❌ Error de conexión: No se pudo contactar con n8n. Verifica la URL o si el flujo está activo. Detalle: {e}")
