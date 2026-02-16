import os
from fastapi import FastAPI, UploadFile, File, Form
import google.generativeai as genai
import pandas as pd
import json
from datetime import datetime

app = FastAPI()

# --- CONFIGURACIÓN DE LA LLAVE ---
# 1. Primero intenta buscar la llave en la configuración de la Nube (Render)
api_key = os.environ.get("GOOGLE_API_KEY")

# 2. Si no la encuentra (porque estás en tu laptop), usa esta fija:
if not api_key:
    api_key = "AIzaSyD-6ebGMxt-T9KMCoi8l-t5tmOPR2BTrNg" 

genai.configure(api_key=api_key)
# ---------------------------------

FILE_EXCEL = "mis_facturas.xlsx"

@app.post("/procesar_factura/")
async def procesar(file: UploadFile = File(...), qr_data: str = Form(...)):
    temp_filename = f"temp_{file.filename}"
    try:
        content = await file.read()
        with open(temp_filename, "wb") as buffer:
            buffer.write(content)

        # Usamos el modelo Flash que es rápido y barato
        model = genai.GenerativeModel('gemini-1.5-flash')
        myfile = genai.upload_file(temp_filename)

        prompt = f"""
        Actúa como asistente contable. Analiza esta factura.
        Dato extra: {qr_data}
        
        Responde SOLO con este JSON exacto:
        {{
            "ruc": "solo numeros",
            "empresa": "nombre razon social",
            "fecha": "YYYY-MM-DD",
            "descripcion": "breve resumen",
            "base": 0.00,
            "igv": 0.00,
            "total": 0.00
        }}
        """

        response = model.generate_content([myfile, prompt])
        texto = response.text.replace("```json", "").replace("```", "").strip()
        
        # Limpieza extra por si la IA habla de más
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        json_str = texto[inicio:fin]
        
        datos = json.loads(json_str)

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

        # Guardado en Excel
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
        return {"status": "ok", "mensaje": "Factura guardada correctamente"}

    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "detalle": str(e)}
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)