import os
import requests
import json
import base64
from fastapi import FastAPI, UploadFile, File, Form
import pandas as pd
from datetime import datetime

app = FastAPI()

FILE_EXCEL = "mis_facturas.xlsx"

@app.post("/procesar_factura/")
async def procesar(file: UploadFile = File(...), qr_data: str = Form(...)):
    try:
        # 1. Obtener y limpiar API KEY
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return {"status": "error", "detalle": "Falta la API Key en Render"}
        
        api_key = api_key.strip() # Quitamos espacios fantasma por si acaso

        # 2. Preparar imagen (Codificación manual para envío directo)
        content = await file.read()
        imagen_b64 = base64.b64encode(content).decode("utf-8")
        
        # 3. URL DIRECTA (Sin librería, directo a la vena de Google)
        # Usamos la versión v1beta que es la más estable para Flash
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        headers = {"Content-Type": "application/json"}
        
        prompt_text = f"""
        Actúa como contador experto. Analiza la imagen de esta factura.
        Datos extra del QR: {qr_data}
        Extrae los datos y responde ÚNICAMENTE con este JSON exacto:
        {{
            "ruc": "solo numeros",
            "empresa": "nombre razon social",
            "fecha": "YYYY-MM-DD",
            "descripcion": "resumen del item principal",
            "base": 0.00,
            "igv": 0.00,
            "total": 0.00
        }}
        """
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt_text},
                    {"inline_data": {
                        "mime_type": file.content_type,
                        "data": imagen_b64
                    }}
                ]
            }]
        }

        print("📡 Enviando petición directa a Google (Sin intermediarios)...")
        response = requests.post(url, headers=headers, json=payload)
        
        # 4. Verificar si Google respondió bien
        if response.status_code != 200:
            print(f"⚠️ Flash falló ({response.status_code}), intentando con Pro...")
            # Plan B: Intentar con Gemini Pro si Flash falla
            url_pro = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}"
            response = requests.post(url_pro, headers=headers, json=payload)
            
            if response.status_code != 200:
                raise Exception(f"Google rechazó la conexión: {response.text}")

        # 5. Procesar la respuesta
        resultado = response.json()
        try:
            # Navegamos por el JSON crudo de Google
            texto_respuesta = resultado["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            raise Exception(f"Google respondió algo raro: {resultado}")

        # Limpiar JSON (quitar comillas de código si las hay)
        texto = texto_respuesta.replace("```json", "").replace("```", "").strip()
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio != -1 and fin != -1:
            datos = json.loads(texto[inicio:fin])
        else:
            raise Exception("No encontré JSON en la respuesta")

        # 6. Guardar en Excel
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
        print(f"❌ ERROR FINAL: {e}")
        return {"status": "error", "detalle": str(e)}
