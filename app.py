import streamlit as st
import requests
import os

st.set_page_config(page_title="Escáner Facturas", page_icon="📸")

st.title("📸 Escáner de Facturas IA")
st.write("Sube tu factura y descárgala en Excel.")

# URL inteligente: Usa la local si estás en la compu, o la nube si estás en Render
url_api = "http://127.0.0.1:8000/procesar_factura/"

qr_input = st.text_input("Dato del QR (Opcional)", "QR-Manual-001")
uploaded_file = st.file_uploader("Sube tu factura", type=["jpg", "png", "jpeg", "pdf"])

if uploaded_file is not None:
    st.info("Imagen cargada. Lista para procesar.")
    
    if st.button("🚀 PROCESAR FACTURA"):
        with st.spinner("La IA está leyendo tu factura..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                data = {"qr_data": qr_input}
                
                # Enviamos al cerebro
                response = requests.post(url_api, files=files, data=data)
                
                if response.status_code == 200:
                    resultado = response.json()
                    if resultado.get("status") == "ok":
                        st.balloons()
                        st.success("✅ ¡Factura guardada en la Nube!")
                        
                        # --- MAGIA: BOTÓN DE DESCARGA ---
                        # Leemos el archivo que el cerebro acaba de guardar
                        if os.path.exists("mis_facturas.xlsx"):
                            with open("mis_facturas.xlsx", "rb") as f:
                                st.download_button(
                                    label="📥 DESCARGAR EXCEL ACTUALIZADO",
                                    data=f,
                                    file_name="mis_facturas.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                        else:
                            st.warning("Se guardó, pero no encuentro el archivo para descargar.")
                    else:
                        st.error(f"Error del sistema: {resultado.get('detalle')}")
                else:
                    st.error("Error de conexión con el Cerebro.")
            except Exception as e:
                st.error(f"Error: {e}")
