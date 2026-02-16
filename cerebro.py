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
    # Por si acaso fallara la variable, ponemos una verificación
    print("¡ADVERTENCIA! No detecto la API Key en el entorno.")

genai.configure(api_key=api_key)

FILE_EXCEL = "mis_facturas.xlsx"

@app.post("/procesar_factura/")
async def procesar(file: UploadFile = File(...), qr_data: str = Form(...)):
    temp_filename = f"temp_{file.filename}"
    try:
        content = await file.read()
        with open(temp_filename, "wb") as buffer:
            buffer.write(content)

        myfile = genai.upload_file(temp_filename)

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

        # --- ESTRATEGIA TRIPLE INTENTO ---
        response = None
        errores = []
        
        # Opción 1: El más moderno y rápido
        try:
            print("Intento 1: gemini-1.5-flash")
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content([myfile, prompt])
        except Exception as e:
            errores.append(f"Flash falló: {e}")
            
            # Opción 2: La versión específica estable
            try:
                print("Intento 2: gemini-1.5-flash-latest")
                model = genai.GenerativeModel('gemini-1.5-flash-latest')
                response = model.generate_content([myfile, prompt])
            except Exception as e:
                errores.append(f"Flash-Latest falló: {e}")

                # Opción 3: El clásico (Vieja confiable)
                try:
                    print("Intento 3: gemini-1.0-pro")
                    model = genai.GenerativeModel('gemini-1.0-pro')
                    response = model.generate_content([myfile, prompt])
                except Exception as e:
                    errores.append(f"Pro falló: {e}")
                    raise Exception(f"Fallaron los 3 modelos. Detalles: {errores}")

        # ---------------------------------

        texto = response.text.replace("```json", "").replace("```", "").strip()
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio != -1 and fin != -1:
            datos = json.loads(texto[inicio:fin])
        else:
            raise Exception("La IA no devolvió datos válidos")

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
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
