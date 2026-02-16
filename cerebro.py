import os
from fastapi import FastAPI, UploadFile, File, Form
import google.generativeai as genai
import pandas as pd
import json
from datetime import datetime

app = FastAPI()

# --- CONFIGURACIÓN SEGURA ---
import os
# Solo busca la llave en las variables de entorno (Render o tu PC)
api_key = os.environ.get("AIzaSyDZLht4yFrhTZyLY_9K28GADIe_pIQfzbU")

if not api_key:
    raise ValueError("¡No se encontró la API Key! Asegúrate de ponerla en Render.")

genai.configure(api_key=api_key)
# ---------------------------------

FILE_EXCEL = "mis_facturas.xlsx"

@app.post("/procesar_factura/")
async def procesar(file: UploadFile = File(...), qr_data: str = Form(...)):
    temp_filename = f"temp_{file.filename}"
    try:
        # 1. Guardar la imagen temporalmente
        content = await file.read()
        with open(temp_filename, "wb") as buffer:
            buffer.write(content)

        # 2. CONFIGURACIÓN DEL MODELO (La versión estándar y rápida)
        model = genai.GenerativeModel('gemini-1.5-flash')
        myfile = genai.upload_file(temp_filename)

        # 3. Instrucciones para la IA
        prompt = f"""
        Actúa como experto contable. Analiza esta factura.
        Información adicional del QR: {qr_data}
        
        Responde ÚNICAMENTE con este JSON válido (sin texto extra):
        {{
            "ruc": "solo el numero",
            "empresa": "nombre de la empresa",
            "fecha": "YYYY-MM-DD",
            "descripcion": "resumen de la compra",
            "base": 0.00,
            "igv": 0.00,
            "total": 0.00
        }}
        """

        # 4. Generar respuesta
        response = model.generate_content([myfile, prompt])
        texto = response.text.replace("```json", "").replace("```", "").strip()
        
        # Búsqueda inteligente del JSON (por si la IA habla mucho)
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio != -1 and fin != -1:
            json_str = texto[inicio:fin]
            datos = json.loads(json_str)
        else:
            raise Exception("No se encontró información válida en la factura")

        # 5. Preparar datos para Excel
        nueva_fila = {
            "Fecha_Registro": datetime.now().strftime("%d/%m/%Y"),
            "RUC": datos.get("ruc"),
            "Empresa": datos.get("empresa"),
            "Fecha_Emision": datos.get("fecha"),
            "Descripcion": datos.get("descripcion"),
            "Base_Imponible": datos.get("base"),
            "IGV": datos.get("igv"),
            "Total": datos.get("total")
        }

        # 6. Guardar en Excel
        df_nuevo = pd.DataFrame([nueva_fila])
        if os.path.exists(FILE_EXCEL):
            try:
                df_existente = pd.read_excel(FILE_EXCEL)
                df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
            except:
                df_final = df_nuevo
        else:
            df_final = df_nuevo
        
        df_final.to_excel(FILE_EXCEL, index=False)
        return {"status": "ok", "mensaje": "Factura procesada correctamente"}

    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "detalle": str(e)}
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


