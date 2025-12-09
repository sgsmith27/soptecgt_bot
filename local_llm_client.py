import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2:1b" 


def _fallback_generico(descripcion: str) -> str:
    
    return (
        "Aquí tienes algunos pasos generales que puedes seguir:\n\n"
        "1. Verifica si el problema ocurre siempre o solo en ciertas aplicaciones.\n"
        "2. Reinicia la computadora y vuelve a probar.\n"
        "3. Si es un equipo corporativo, evita cambiar configuraciones avanzadas sin autorización.\n"
        "4. Anota cualquier mensaje de error y, si el problema persiste, repórtalo a soporte adjuntando esa información.\n"
    )


def responder_incidente_otro(descripcion: str) -> str:
    
    prompt = f"""
Eres un técnico de TI de soporte en español.

Problema del usuario: \"\"\"{descripcion}\"\"\"

**Instrucciones:**
1. Responde SIEMPRE con 3 a 5 pasos numerados.
2. Cada paso debe ser corto (1 línea).
3. Sé práctico y da soluciones simples.
4. Si menciona 'antivirus' o 'seguridad':
   - Recomienda verificar actualizaciones.
   - No sugerir desinstalarlo.
5. Si el problema es vago, en el último paso pide detalles específicos (ej: "¿Qué mensaje de error ves?").
6. Solo habla de internet/red si el usuario usa palabras como 'internet', 'wifi' o 'red'.

**Formato de respuesta (ejemplo):**
1. Paso uno concreto.
2. Paso dos concreto.
3. Paso tres concreto.
"""

    payload = {
        "model": DEFAULT_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,   
            "num_predict": 100,   
        },
    }

    try:
        print("[Ollama] Llamando a modelo para categoria 'Otros'...")
        resp = requests.post(OLLAMA_URL, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        texto = data.get("response", "").strip()

        if not texto:
            return _fallback_generico(descripcion)

        
        lower = texto.lower()
        patrones_refuso = [
            "no puedo proporcionar asistencia",
            "no puedo ayudarte",
            "no puedo ayudar",
            "no puedo proporcionar ayuda",
        ]
        if any(p in lower for p in patrones_refuso):
            return _fallback_generico(descripcion)

        return texto

    except Exception as e:
        print(f"[Ollama] Error al responder incidente 'Otros': {e}")
        return _fallback_generico(descripcion)
