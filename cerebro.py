import os
from fastapi import FastAPI, UploadFile, File, Form
import google.generativeai as genai
import pandas as pd
import json
from datetime import datetime

app = FastAPI()

# --- CONFIGURACIÓN DE LA LLAVE ---
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    api_key = "AIzaSyD-6ebGMxt-T9KMCoi8l-t5tmOPR2BTrNg" # Tu clave para local

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

        # 2. Subir archivo a Google
        myfile = genai.upload_file(temp_filename)

        # 3. Preparar las instrucciones
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

        # --- AQUÍ ESTÁ EL BLINDAJE ANTI-ERROR ---
        # Intentamos primero con el modelo rápido (Flash)
        try:
            print("Intentando con Gemini 1.5 Flash...")
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content([myfile, prompt])
        except Exception as e:
            # Si falla (Error 404), usamos el modelo clásico (Pro) que nunca falla
            print(f"Flash falló ({e}), cambiando a Gemini Pro...")
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content([myfile, prompt])
        # ----------------------------------------

        # 4. Limpieza y guardado
        texto = response.text.replace("```json", "").replace("```", "").strip()
        
        # Búsqueda inteligente del JSON
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio != -1 and fin != -1:
            json_str = texto[inicio:fin]
            datos = json.loads(json_str)
        else:
            raise Exception("La IA no devolvió un formato válido.")

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

        # Guardar en Excel
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
        print(f"Error fatal: {e}")
        return {"status": "error", "detalle": str(e)}
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
