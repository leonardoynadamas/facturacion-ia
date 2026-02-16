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
api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("¡No se encontró la API Key! Asegúrate de ponerla en Render.")

genai.configure(api_key=api_key)

FILE_EXCEL = "mis_facturas.xlsx"

@app.post("/procesar_factura/")
async def procesar(file: UploadFile = File(...), qr_data: str = Form(...)):
    temp_filename = f"temp_{file.filename}"
    try:
        # 1. Guardar imagen temporal
        content = await file.read()
        with open(temp_filename, "wb") as buffer:
            buffer.write(content)

        # 2. Subir a Google
        myfile = genai.upload_file(temp_filename)

        # 3. Instrucciones
        prompt = f"""
        Actúa como experto contable. Analiza esta factura.
        Info QR: {qr_data}
        Responde SOLO con este JSON:
        {{
            "ruc": "solo numeros",
            "empresa": "nombre empresa",
            "fecha": "YYYY-MM-DD",
            "descripcion": "resumen item",
            "base": 0.00,
            "igv": 0.00,
            "total": 0.00
        }}
        """

        # --- AQUÍ ESTÁ EL TRUCO (DOBLE MOTOR) ---
        try:
            # Intento 1: Usar el modelo Flash (Rápido)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content([myfile, prompt])
        except Exception:
            # Intento 2: Si falla, usar el modelo Clásico (Seguro)
            print("Cambiando a modelo de respaldo...")
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content([myfile, prompt])
        # ----------------------------------------

        # 4. Limpieza de respuesta
        texto = response.text.replace("```json", "").replace("```", "").strip()
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio != -1 and fin != -1:
            datos = json.loads(texto[inicio:fin])
        else:
            raise Exception("La IA no devolvió datos válidos")

        # 5. Guardar en Excel
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
        return {"status": "error", "detalle": str(e)}
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
