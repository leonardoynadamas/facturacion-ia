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
    print("¡ALERTA! No hay API Key.")

genai.configure(api_key=api_key)

FILE_EXCEL = "mis_facturas.xlsx"

@app.post("/procesar_factura/")
async def procesar(file: UploadFile = File(...), qr_data: str = Form(...)):
    try:
        # 1. Leer imagen
        content = await file.read()
        imagen_blob = {"mime_type": file.content_type, "data": content}

        prompt = f"""
        Actúa como contador. Analiza la factura. Info QR: {qr_data}
        Responde SOLO JSON:
        {{
            "ruc": "solo numeros",
            "empresa": "nombre",
            "fecha": "YYYY-MM-DD",
            "descripcion": "item",
            "base": 0.00,
            "igv": 0.00,
            "total": 0.00
        }}
        """

        # --- DETECTOR DE MODELOS (La solución final) ---
        print(f"Librería versión: {genai.__version__}")
        model = None
        
        # Lista de candidatos a probar (del más rápido al más potente)
        candidatos = [
            'gemini-1.5-flash',
            'gemini-1.5-flash-latest',
            'models/gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-2.0-flash-exp'
        ]

        response = None
        error_last = ""

        # Intento 1: Probar lista de nombres conocidos
        for nombre in candidatos:
            try:
                print(f"Probando modelo: {nombre}...")
                model = genai.GenerativeModel(nombre)
                response = model.generate_content([prompt, imagen_blob])
                print(f"¡Éxito con {nombre}!")
                break # Si funciona, salimos del bucle
            except Exception as e:
                print(f"Falló {nombre}: {e}")
                error_last = str(e)

        # Intento 2 (Si todo falla): Preguntar a la API qué tiene
        if not response:
            print("--- Buscando en la lista oficial de Google ---")
            try:
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods and 'vision' in m.description.lower():
                        print(f"Intentando con el oficial: {m.name}")
                        model = genai.GenerativeModel(m.name)
                        response = model.generate_content([prompt, imagen_blob])
                        break
            except Exception as e:
                print(f"Error listando modelos: {e}")

        if not response:
            raise Exception(f"No se pudo conectar con ningún modelo. Último error: {error_last}")

        # ------------------------------------------------

        # Procesar respuesta
        texto = response.text.replace("```json", "").replace("```", "").strip()
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        datos = json.loads(texto[inicio:fin])

        # Guardar Excel
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
        print(f"ERROR FINAL: {e}")
        return {"status": "error", "detalle": str(e)}
