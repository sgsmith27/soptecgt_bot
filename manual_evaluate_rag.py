"""

Evaluación manual del RAG usando GPT-4.1-nano
Produce métricas por caso:
- Answer Relevancy
- Contextual Relevancy
- Faithfulness

"""

import os
import json
from typing import List, Dict, Optional
from rag_engine import buscar_soluciones
from openai import OpenAI


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


TEST_CASES = [
    {
        "name": "Computadora no enciende",
        "categoria": "computadora",
        "subcategoria": None,
        "query": "Mi computadora no enciende, no muestra luces ni sonido.",
        "expected": (
            "1. **Verificar toma de corriente y regleta**"
            "- Conecta la computadora **directamente a la pared**, si es posible"
            "- Si usas regleta, verifica que esté **encendida** y funcionando (prueba otro dispositivo)." 
        ),
    },
    {
        "name": "Monitor pantalla negra",
        "categoria": "monitor",
        "subcategoria": None,
        "query": "El CPU parece encender pero el monitor se queda en negro.",
        "expected": (
            "1. **Verificar que el monitor esté encendido**"
            "- Confirmar que el LED esté iluminado (verde o ámbar)."
            "- Si está parpadeando, puede estar entrando en modo de reposo."
        ),
    },
    {
        "name": "Impresora térmica no imprime",
        "categoria": "impresora_termica",
        "subcategoria": None,
        "query": "La impresora térmica de caja no imprime tickets",
        "expected": (
            "1. **Verificar estado de la impresora**"
            "- Confirmar que el LED de **POWER** esté encendido."
            "- Si la luz de **ERROR** está fija o parpadeando, revisar tapa y papel."
        ),
    },
    {
        "name": "Scanner no jala hojas",
        "categoria": "scannersfin",
        "subcategoria": None,
        "query": "El escaner no jala las hojas, al parecer se quedan trabadas",
        "expected": (
            "1. **Alinear correctamente el papel**"
            "- Verifica que las hojas estén **rectas y sin dobleces**."
            "- Asegúrate de que no haya grapas, clips o papeles pegados."
            "- Coloca el papel con el lado correcto hacia abajo (según modelo)."
        ),
    },
]



def run_rag(query: str, categoria: Optional[str], subcategoria: Optional[str]) -> str:
    resultados = buscar_soluciones(
        descripcion=query,
        categoria=categoria,
        subcategoria=subcategoria,
        top_k=1,
    )
    if not resultados:
        return ""
    doc = resultados[0]
    return f"{doc['title']}\n{doc['content']}"



def gpt_score(prompt: str) -> float:
    """Devuelve un score 0–1 generado con GPT."""
    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    
    text = response.choices[0].message.content

    
    if isinstance(text, list):
        text = "".join(part for part in text if isinstance(part, str))

    text = str(text).strip()

    try:
        score = float(text)
        return max(0.0, min(score, 1.0))
    except Exception:
        
        return 0.0



def score_answer_relevancy(expected: str, rag_output: str) -> float:
    prompt = f"""
Evalúa qué TAN RELEVANTE es esta salida del RAG comparada con la respuesta ESPERADA.

Respuesta esperada:
{expected}

Salida RAG:
{rag_output}

Da un SOLO número entre 0 y 1 sin explicación:
0 = nada relevante
1 = totalmente relevante
"""
    return gpt_score(prompt)


def score_context_relevancy(query: str, rag_output: str) -> float:
    prompt = f"""
Evalúa qué tan relevante es el CONTEXTO recuperado respecto a la consulta original.

Consulta:
{query}

Salida RAG:
{rag_output}

Da un SOLO número entre 0 y 1.
"""
    return gpt_score(prompt)


def score_faithfulness(rag_output: str) -> float:
    prompt = f"""
Evalúa la veracidad y exactitud del contenido devuelto por RAG.

Texto RAG:
{rag_output}

Da un SOLO número entre 0 y 1:
0 = inventado / alucinado
1 = completamente factual y coherente
"""
    return gpt_score(prompt)


def main():
    results = []

    for case in TEST_CASES:
        name = case["name"]
        query = case["query"]
        expected = case["expected"]

        rag_output = run_rag(query, case["categoria"], case["subcategoria"])

        answer_rel = score_answer_relevancy(expected, rag_output)
        context_rel = score_context_relevancy(query, rag_output)
        faithfulness = score_faithfulness(rag_output)

        results.append({
            "name": name,
            "answer_relevancy": answer_rel,
            "contextual_relevancy": context_rel,
            "faithfulness": faithfulness,
        })

        print(f"\nCaso: {name}")
        print(f"  Answer Relevancy:      {answer_rel:.3f}")
        print(f"  Contextual Relevancy:  {context_rel:.3f}")
        print(f"  Faithfulness:          {faithfulness:.3f}")
        print("-" * 50)
    
    with open("rag_manual_eval.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\nResultados guardados en rag_manual_eval.json")


if __name__ == "__main__":
    main()
