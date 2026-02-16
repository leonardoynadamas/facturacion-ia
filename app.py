import streamlit as st
import requests

st.set_page_config(page_title="Escáner Facturas", page_icon="📸")

st.title("📸 Escáner de Facturas IA")
st.write("Sube tu factura y el sistema contable la procesará.")

# URL inteligente: Si estamos en la nube usa la interna, sino la local
url_api = "http://127.0.0.1:8000/procesar_factura/"

qr_input = st.text_input("Dato del QR (Opcional)", "QR-Manual-001")
uploaded_file = st.file_uploader("Sube tu factura", type=["jpg", "png", "jpeg", "pdf"])

if uploaded_file is not None:
    st.success("Imagen cargada. Lista para procesar.")
    
    if st.button("🚀 PROCESAR FACTURA"):
        with st.spinner("Analizando con Inteligencia Artificial..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                data = {"qr_data": qr_input}
                
                # Intentamos conectar con el cerebro
                response = requests.post(url_api, files=files, data=data)
                
                if response.status_code == 200:
                    resultado = response.json()
                    if resultado.get("status") == "ok":
                        st.balloons()
                        st.success("✅ ¡Guardado en Excel exitosamente!")
                    else:
                        st.error(f"Error del sistema: {resultado.get('detalle')}")
                else:
                    st.error("No se pudo conectar con el Cerebro.")
            except Exception as e:
                st.error(f"Error de conexión: {e}")
                st.info("Asegúrate de que la terminal negra 'uvicorn' esté encendida.")