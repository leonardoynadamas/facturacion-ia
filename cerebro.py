import os
from fastapi import FastAPI, UploadFile, File, Form
import google.generativeai as genai
import pandas as pd
import json
from datetime import datetime

app = FastAPI()

# --- CONFIGURACIÓN ---
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("¡ADVERTENCIA! No detecto la API Key.")

genai.configure(api_key=api_key)

FILE_EXCEL = "mis_facturas.xlsx"

@app.post("/procesar_factura/")
async def procesar(file: UploadFile = File(...), qr_data: str = Form(...)):
    try:
        # 1. Leer la imagen directamente en memoria (Sin guardar en disco)
        content = await file.read()
        
        # 2. Preparar el paquete para la IA (Envío Directo)
        imagen_blob = {
            "mime_type": file.content_type,
            "data": content
        }

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

        # 3. Intentar con el modelo Flash (Ahora con envío directo)
        try:
            print(f"Versión de librería: {genai.__version__}") # Para verificar en los logs
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content([prompt, imagen_blob])
        except Exception as e:
            print(f"Flash falló ({e}), intentando con Pro...")
            model = genai.GenerativeModel('gemini-pro')
            # Gemini Pro (versión vieja) a veces pide la imagen distinto, pero intentamos igual
            response = model.generate_content([prompt, imagen_blob])

        # 4. Procesar respuesta
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
        print(f"ERROR FATAL: {e}")
        return {"status": "error", "detalle": str(e)}
