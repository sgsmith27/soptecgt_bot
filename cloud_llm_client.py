
import os
import requests

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4.1-nano" 


def _call_openai_chat(prompt: str, max_tokens: int = 200) -> str:
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un asistente técnico de soporte de TI. "
                    "Da respuestas claras, estructuradas en pasos, "
                    "sin inventar información de la empresa."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }

    try:
        resp = requests.post(OPENAI_CHAT_URL, headers=headers, json=data, timeout=40)

        if resp.status_code == 429:
            
            print("[CLOUD LLM] 429 Too Many Requests. Cuerpo del error:")
            print(resp.text)
           
            return ""

        resp.raise_for_status()
        payload = resp.json()

        
        content = payload["choices"][0]["message"]["content"]
        return content.strip()

    except Exception as e:
        print(f"[CLOUD LLM] Error llamando al modelo: {e}")
        return ""


def responder_incidente_otro(descripcion: str) -> str:
    
    prompt = (
        "El usuario tiene el siguiente problema (categoría 'Otros'): "
        f"'{descripcion}'.\n\n"
        "Da una respuesta breve en español, con un máximo de 4 pasos numerados, "
        "enfocada en cosas que el usuario pueda probar directamente. "
        "No menciones políticas internas ni datos de la empresa."
    )

    return _call_openai_chat(prompt, max_tokens=220)
