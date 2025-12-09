from typing import Any, Text, Dict, List, Optional
import re
import json
import unicodedata
import os
import uuid
import csv
from datetime import datetime
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, AllSlotsReset, FollowupAction
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from rag_engine import buscar_soluciones
#from local_llm_client import responder_incidente_otro #cuando se use LLM local
from cloud_llm_client import responder_incidente_otro
from datetime import datetime
from pathlib import Path
from openai import OpenAI
client = OpenAI()

MAX_PASOS_POR_TANDA = 5
MAX_TANDAS_PASOS = 3 

LOG_DIR = "logs"
RAG_LOG_PATH = os.path.join(LOG_DIR, "rag_events.jsonl")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPLEADOS_CSV_PATH = os.path.join(BASE_DIR, "data", "empleados.csv")
INCIDENTES_CSV = os.path.join(BASE_DIR, "data", "incidentes_soptecgt.csv")


def cargar_empleados_desde_csv() -> Dict[str, Dict[str, str]]:
    empleados: Dict[str, Dict[str, str]] = {}
    try:
        with open(EMPLEADOS_CSV_PATH, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=",")
            for row in reader:
                raw_code = (row.get("CODIGO") or "").strip()
                if not raw_code:
                    continue

                # solo dígitos
                code_digits = re.sub(r"\D", "", raw_code)
                if not code_digits:
                    continue

                nombre = (row.get("NOMBRE EMPLEADO") or row.get("NOMBRE_EMPLEADO") or "").strip()
                sucursal = (row.get("SUCURSAL") or "").strip()
                nombre_sucursal = (row.get("NOMBRE_SUCURSAL") or "").strip()

                registro = {
                    "name": nombre or "Empleado sin nombre",
                    "branch": sucursal or "N/D",
                    "branch_name": nombre_sucursal or "",
                }                
                empleados[code_digits] = registro
                if len(code_digits) < 6:
                    empleados[code_digits.zfill(6)] = registro

        print(f"[EMPLEADOS] Cargados {len(empleados)} registros desde {EMPLEADOS_CSV_PATH}")
    except FileNotFoundError:
        print(f"[EMPLEADOS] CSV no encontrado en {EMPLEADOS_CSV_PATH}")
    except Exception as e:
        print(f"[EMPLEADOS] Error leyendo CSV: {e}")

    return empleados

EMPLEADOS = cargar_empleados_desde_csv()


def normalizar_categoria_para_rag(raw: Optional[str]) -> str:
        
    if not raw:
        return ""

    raw = raw.strip()

    #minúsculas y sin acentos
    ascii_txt = unicodedata.normalize("NFKD", raw)
    ascii_txt = "".join(ch for ch in ascii_txt if not unicodedata.combining(ch))
    ascii_txt = ascii_txt.lower()

    # MAPEOS POR CATEGORÍA    
    if "monitor" in ascii_txt or "pantalla" in ascii_txt:
        return "monitor"

    if "case" in ascii_txt or "cpu" in ascii_txt or "computadora" in ascii_txt or "pc" in ascii_txt:
        return "computadora"

    if "scanner" in ascii_txt and "financ" in ascii_txt:
        return "scannersfin"

    if "scanner" in ascii_txt and "caja" in ascii_txt:
        return "scannercaja"

    if "impresora" in ascii_txt and ("termica" in ascii_txt or "bixolon" in ascii_txt):
        return "impresora_termica"

    if "impresora" in ascii_txt and ("laser" in ascii_txt or "lexmark" in ascii_txt):
        return "impresora_laser"

    if "periferic" in ascii_txt or "dispositiv" in ascii_txt:
        return "periferico"

    if "internet" in ascii_txt or " red" in ascii_txt:
        return "internet"

    if "software" in ascii_txt or "sistema" in ascii_txt or "windows" in ascii_txt:
        return "software"

    if "otro" in ascii_txt:
        return "otro"

    return ascii_txt



def extract_employee_code_from_message(tracker: Tracker) -> Optional[str]:
   
    text = tracker.latest_message.get("text") or ""

    # patrones tipo E12345 o solo 5 dígitos
    m = re.search(r"\b(\d{5,6})\b", text)
    if m:
        return m.group(1)

    return None

def registrar_incidente_en_csv(
    fecha: str,
    hora: str,
    sucursal: str,
    nombre_sucursal: str,
    empleado: str,
    codigo_empleado: str,
    categoria: str,
    subcategoria: str,
    descripcion: str,
    ticket_id: str,
    estado: str = "Abierto",
) -> None:
    
    try:
        
        data_dir = os.path.dirname(INCIDENTES_CSV)
        os.makedirs(data_dir, exist_ok=True)

        file_exists = os.path.exists(INCIDENTES_CSV)

        with open(INCIDENTES_CSV, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(
                    [
                        "fecha",
                        "hora",
                        "sucursal",
                        "nombre_sucursal",
                        "empleado",
                        "codigo_empleado",
                        "categoria",
                        "subcategoria",
                        "descripcion",
                        "ticket_id",
                        "estado",
                    ]
                )

            writer.writerow(
                [
                    fecha,
                    hora,
                    sucursal,
                    nombre_sucursal,
                    empleado,
                    codigo_empleado,
                    categoria,
                    subcategoria,
                    descripcion,
                    ticket_id,
                    estado,
                ]
            )

        print(f"[INCIDENTES] Registrado incidente {ticket_id} en {INCIDENTES_CSV}")

    except Exception as e:
        print(f"[INCIDENTES] Error al escribir en CSV: {e}")

def generar_ticket_id() -> str:
    
    try:
        if not os.path.exists(INCIDENTES_CSV):
            return "INC000001"

        numeros = []

        with open(INCIDENTES_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tid = (row.get("ticket_id") or "").strip()
                m = re.match(r"INC(\d+)$", tid)
                if m:
                    numeros.append(int(m.group(1)))

        if not numeros:
            return "INC000001"

        siguiente = max(numeros) + 1
        return f"INC{siguiente:06d}"

    except Exception as e:
        print(f"[INCIDENTES] Error generando ticket_id, usando valor por defecto: {e}")
        return "INC000001"


class ActionVerificarIdentidad(Action):    

    def name(self) -> Text:
        return "action_verificar_identidad"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        
        if tracker.get_slot("authenticated"):
            dispatcher.utter_message(
                text="Ya he validado tu identidad previamente ✅. Podemos continuar."
            )
            return []

        employee_code = extract_employee_code_from_message(tracker)

        if not employee_code:
            dispatcher.utter_message(
                text=(
                    "No pude identificar tu código de empleado a partir del mensaje.\n"
                    "Por favor, envíame tu código de empleado en el formato 123456 "
                    "o 5 dígitos, por ejemplo: 12345."
                )
            )
            
            return []
        
        code_norm = re.sub(r"\D", "", employee_code or "")
        candidato = EMPLEADOS.get(code_norm) or EMPLEADOS.get(code_norm.zfill(6))        

        if not candidato:
            dispatcher.utter_message(
                text=(
                    f"No he podido validar tu código de empleado en el sistema ({employee_code}).\n"
                    "Por favor verifica que esté correcto o vuelve a enviar tu código."
                )
            )
            return [
                SlotSet("authenticated", False),
                SlotSet("employee_code", None),
                SlotSet("employee_name", None),
                SlotSet("branch_number", None),
                SlotSet("branch_name", None),
            ]

        employee_name = candidato.get("name", "Empleado no identificado")
        branch_number = candidato.get("branch", "N/D")
        branch_name = candidato.get("branch_name", "")

        dispatcher.utter_message(
            text=(
                "Perfecto, he validado tu identidad ✅.\n\n"
                f"👤 Empleado: {employee_name} (código {employee_code})\n"
                f"📍 Sucursal: {branch_number}-{branch_name}\n\n"
                "Ahora vamos a registrar tu incidente."
            )
        )

        return [
            SlotSet("authenticated", True),
            SlotSet("employee_code", employee_code),
            SlotSet("employee_name", employee_name),
            SlotSet("branch_number", branch_number),
            SlotSet("branch_name", branch_name),
        ]

class ActionConfirmarReporte(Action):
    def name(self) -> Text:
        return "action_confirmar_reporte"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        #cargar datos para generar el reporte
        sucursal = tracker.get_slot("branch_number") or tracker.get_slot("sucursal")
        nombre_sucursal = tracker.get_slot("branch_name")
        empleado = tracker.get_slot("employee_name")
        codigo_empleado = tracker.get_slot("employee_code")
        categoria = tracker.get_slot("categoria")
        subcategoria = tracker.get_slot("subcategoria")
        descripcion = tracker.get_slot("descripcion")        
        sucursal = sucursal or "no especificada"
        nombre_sucursal = nombre_sucursal or "N/D"
        empleado = empleado or "Empleado no identificado"
        codigo_empleado = codigo_empleado or "N/D"
        categoria = categoria or "no especificada"
        subcategoria = subcategoria or "No especificada"
        descripcion = descripcion or "sin descripción"        
        ticket_id = generar_ticket_id()
         
        ahora = datetime.now()
        fecha_str = ahora.strftime("%Y-%m-%d")
        hora_str = ahora.strftime("%H:%M:%S")
        estado = "Abierto"

        registrar_incidente_en_csv(
            fecha=fecha_str,
            hora=hora_str,
            sucursal=str(sucursal),
            nombre_sucursal=str(nombre_sucursal),
            empleado=str(empleado),
            codigo_empleado=str(codigo_empleado),
            categoria=str(categoria),
            subcategoria=str(subcategoria),
            descripcion=str(descripcion),
            ticket_id=str(ticket_id),
            estado=estado,
        )

        mensaje = (
            "He registrado tu incidente con la siguiente información:\n"
            f"📍 Sucursal: {sucursal}-{nombre_sucursal}\n"
            f"👤 Empleado: {empleado} (código {codigo_empleado})\n"
            f"📂 Categoría: {categoria}\n"
            f"📦 Subcategoría: {subcategoria}\n"
            f"📝 Descripción: {descripcion}\n"
            f"🎫 Número de ticket: {ticket_id}\n"
            "Un ingeniero de soporte técnico dará seguimiento lo antes posible."
        )

        dispatcher.utter_message(text=mensaje)
        session_id = tracker.get_slot("rag_session_id")

        if session_id:
            log_rag_event(
                {
                    "type": "rag_outcome",
                    "session_id": session_id,
                    "user_id": tracker.sender_id,
                    "outcome": "levantar_reporte",
                    "ticket_id": ticket_id,    
                    "categoria": tracker.get_slot("categoria"),
                    "subcategoria": tracker.get_slot("subcategoria"),
                    "descripcion": tracker.get_slot("descripcion"),
                }
            )

        return [SlotSet("authenticated", False),
            SlotSet("employee_code", None),
            SlotSet("employee_name", None),
            SlotSet("branch_number", None),
            SlotSet("branch_name", None),
            SlotSet("categoria", None),
            SlotSet("subcategoria", None),
            SlotSet("descripcion", None),
            SlotSet("ticket_id", None),
            SlotSet("flujo_otros_llm", False),]


class ValidateIncidenteForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_incidente_form"

    async def required_slots(
        self,
        slots_mapped_in_domain: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        
        categoria = tracker.get_slot("categoria")
        required = list(slots_mapped_in_domain)

        raw = categoria or ""
        cat_norm = raw.lower()
        cat_ascii = unicodedata.normalize("NFKD", raw)
        cat_ascii = "".join(ch for ch in cat_ascii if not unicodedata.combining(ch))
        cat_ascii = cat_ascii.lower()

        # se pide subcategoria si la categoría  es periférico
        es_periferico = "periferic" in cat_ascii or "perifer" in cat_ascii

        if not (es_periferico):
            if "subcategoria" in required:
                required.remove("subcategoria")

        return required

    
class ActionStartNuevoIncidente(Action):
    def name(self) -> Text:
        return "action_start_nuevo_incidente"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        
        events: List[Dict[Text, Any]] = [
            SlotSet("authenticated", False),
            SlotSet("employee_code", None),
            SlotSet("employee_name", None),
            SlotSet("branch_number", None),
            SlotSet("branch_name", None),
            SlotSet("categoria", None),
            SlotSet("subcategoria", None),
            SlotSet("descripcion", None),
            SlotSet("ticket_id", None),
            SlotSet("flujo_otros_llm", False),
        ]

        
        dispatcher.utter_message(
            text=(
                "Perfecto 👍. Vamos a iniciar un nuevo reporte.\n\n"
                "Primero necesito validar tu identidad nuevamente.\n"
                "Por favor, envíame una foto de tu carnet corporativo o tu código de empleado."
            )
        )

        return events

class ActionEndConversation(Action):
    def name(self) -> Text:
        return "action_end_conversation"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        
        dispatcher.utter_message(
            text="¡Perfecto! Si necesitas algo más, estaré aquí para ayudarte. 👋"
        )
        
        events: List[Dict[Text, Any]] = [
            SlotSet("authenticated", False),
            SlotSet("employee_code", None),
            SlotSet("employee_name", None),
            SlotSet("branch_number", None),
            SlotSet("branch_name", None),
            SlotSet("categoria", None),
            SlotSet("subcategoria", None),
            SlotSet("descripcion", None),
            SlotSet("ticket_id", None),
            SlotSet("flujo_otros_llm", False),
        ]

        return events

class ActionSugerirSolucionIncidente(Action):
    def name(self) -> Text:
        return "action_sugerir_solucion_incidente"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        categoria = tracker.get_slot("categoria")
        subcategoria = tracker.get_slot("subcategoria")
        descripcion = tracker.get_slot("descripcion")

        if not descripcion:
            dispatcher.utter_message(
                text=(
                    "No tengo una descripción del problema para poder buscar una solución. "
                    "Por favor dime brevemente qué está ocurriendo."
                )
            )
            return []

        desc_low = descripcion.lower()

        # Normalización de categoría para RAG 
        cat_for_rag = normalizar_categoria_para_rag(categoria)
        sub_for_rag = subcategoria
        cat_norm = (cat_for_rag or "").strip().lower()

        # Router para categoría "Otros" (si el caso esta en otra categorias tratar de redirigir)
        if cat_norm in ["otro", "otros"]:
            if "teclado" in desc_low:
                cat_for_rag = "periferico"
                sub_for_rag = "teclado"
                cat_norm = "periferico"

            elif "mouse" in desc_low:
                cat_for_rag = "periferico"
                sub_for_rag = "mouse"
                cat_norm = "periferico"

            elif "monitor" in desc_low or "pantalla" in desc_low:
                cat_for_rag = "monitor"
                sub_for_rag = None
                cat_norm = "monitor"

            elif "scanner" in desc_low and "financ" in desc_low:
                cat_for_rag = "scannersfin"
                sub_for_rag = None
                cat_norm = "scannersfin"

            elif "scanner" in desc_low or "digitalizadora" in desc_low:
                cat_for_rag = "scannercaja"
                sub_for_rag = None
                cat_norm = "scannercaja"

        #si despues del router el caso no se encuentra, se pasa al LLM Cloud o Local
        botones = [
            {"title": "Si, se solucionó", "payload": "/afirmacion"},
            {"title": "No, se solucionó", "payload": "/negacion"},
        ]

        if cat_norm in ["otro", "otros"]:
            respuesta_llm = responder_incidente_otro(descripcion)

            dispatcher.utter_message(
                text=(
                    "Este tipo de problema no está contemplado en las categorías estándar.\n\n"
                    "He consultado al asistente técnico inteligente y te sugiero lo siguiente:\n\n"
                    f"{respuesta_llm}\n"
                ),
                buttons=botones,
            )
            return [SlotSet("flujo_otros_llm", True)]

        #Consulta al RAG con categoría y subcategoría normalizadas
        try:
            resultados = buscar_soluciones(
                descripcion=descripcion,
                categoria=cat_for_rag,
                subcategoria=sub_for_rag,
                top_k=1,
            )
        except Exception as e:
            print(f"[RAG] Error buscando soluciones: {e}")
            dispatcher.utter_message(
                text=(
                    "No pude consultar la base de conocimiento en este momento. "
                    "Lo siento, continuaré con el registro del incidente."
                )
            )
            return []

        if not resultados:
            dispatcher.utter_message(
                text=(
                    "No encontré una solución directa en la base de conocimiento. "
                    "Continuaré con el registro del incidente."
                )
            )
            return []

        mejor = resultados[0]
        contenido = mejor["content"]
        titulo_doc = mejor.get("title", "Procedimiento técnico")
        path_doc = mejor.get("path")
        session_id = tracker.get_slot("rag_session_id") or str(uuid.uuid4())

        log_rag_event(
            {
                "type": "rag_suggestion",
                "session_id": session_id,
                "user_id": tracker.sender_id,
                "descripcion": descripcion,
                "categoria_raw": categoria,
                "categoria_norm": cat_for_rag,
                "subcategoria": sub_for_rag,
                "doc_title": titulo_doc,
                "doc_path": path_doc,
                "doc_category": mejor.get("category"),
                "doc_score": mejor.get("score"),
            }
        )
        
        #Intentar quedarse solo con la sección de pasos del markdown        
        texto_seccion = contenido
        lower = contenido.lower()

        idx = lower.find("## pasos de solución")
        if idx == -1:
            idx = lower.find("## pasos de solucion")

        if idx != -1:
            resto = contenido[idx:]
            lower_resto = resto.lower()
            idx_next = lower_resto.find("\n## ")
            if idx_next != -1:
                texto_seccion = resto[:idx_next].strip()
            else:
                texto_seccion = resto.strip()

        #Extraer solo líneas que parezcan pasos
        lineas = [l.strip() for l in texto_seccion.splitlines() if l.strip()]
        pasos: List[str] = []

        for l in lineas:
            # bullets tipo "- algo" o "* algo"
            if l.startswith("- ") or l.startswith("* "):
                pasos.append(l)
            else:
                # numerados tipo "1. algo" o "2) algo"
                if len(l) > 2 and l[0].isdigit() and l[1] in [".", ")"]:
                    pasos.append(l)

        # Fallback: si no se detecta pasos "formales", usamos las líneas de la sección
        if not pasos:
            pasos = lineas

        if not pasos:
            dispatcher.utter_message(
                text=(
                    "Encontré un procedimiento relacionado, pero no pude extraer pasos claros. "
                    "Continuaré con el registro del incidente."
                )
            )
            return []

        # guardar todos los pasos y solo se muestra la primera tanda
        # Guardar los pasos crudos (aún con bullets) en un slot como JSON
        pasos_json = json.dumps(pasos, ensure_ascii=False)

        # Primera tanda
        primeros_pasos = pasos[:MAX_PASOS_POR_TANDA]

        pasos_formateados: List[str] = []
        for i, p in enumerate(primeros_pasos, start=1):
            # limpiamos bullets iniciales
            if p.startswith("- ") or p.startswith("* "):
                p = p[2:].strip()
            pasos_formateados.append(f"{i}️⃣ {p}")

        texto_pasos = "\n".join(pasos_formateados)

        mensaje = (
            f"Según nuestra base de conocimiento (*{titulo_doc}*), te recomiendo probar lo siguiente:\n\n"
            f"{texto_pasos}\n"
        )

        dispatcher.utter_message(text=mensaje)

        
        #Imagenes y videos
        imagenes = re.findall(r"!\[[^\]]*]\(([^)]+)\)", contenido)
        for url in imagenes[:2]:
            dispatcher.utter_message(image=url)

        videos = re.findall(r"(https?://\S+\.(?:mp4|mov|webm))", contenido)
        if videos:
            video_url = videos[0]
            dispatcher.utter_message(
                text=f"🎥 Puedes ver un video de ejemplo aquí:\n{video_url}"
            )

        # preguntar si quiere ver más pasos o levantar reporte
        botones = [
            {"title": "Ya se solucionó", "payload": "/incidente_solucionado"},
            {"title": "Ver más pasos", "payload": "/ver_mas_pasos"},
            {"title": "Generar reporte", "payload": "/levantar_reporte"},
        ]
        dispatcher.utter_message(
            text="¿Quieres ver más pasos o prefieres que genere el reporte?",
            buttons=botones,
        )

        #Guardar contexto para tandas posteriores y trazabilidad
        return [
            SlotSet("kb_steps", pasos_json),
            SlotSet("kb_steps_index", float(len(primeros_pasos))),
            SlotSet("kb_steps_round", 1.0),
            SlotSet("rag_doc_path", path_doc),
            SlotSet("rag_doc_title", titulo_doc),
            SlotSet("rag_session_id", session_id),
        ]


class ActionMostrarMasPasosRAG(Action):
    def name(self) -> Text:
        return "action_mostrar_mas_pasos_rag"

    def run(self, dispatcher, tracker, domain):
        
        pasos_json = tracker.get_slot("kb_steps")
        idx = tracker.get_slot("kb_steps_index") or 0
        ronda = tracker.get_slot("kb_steps_round") or 0

        try:
            pasos_solucion = json.loads(pasos_json) if pasos_json else []
        except Exception:
            pasos_solucion = []

        idx = int(idx)
        ronda = int(ronda)

        if not pasos_solucion:
            dispatcher.utter_message(
                text=(
                    "Ya no tengo más pasos registrados en la base de conocimiento. "
                    "Procederé a levantar el reporte para que un técnico lo revise."
                )
            )
            return [FollowupAction("action_confirmar_reporte")]

        # Si se ha llegado al máximo de tandas, levantar reporte
        if ronda >= MAX_TANDAS_PASOS or idx >= len(pasos_solucion):
            dispatcher.utter_message(
                text=(
                    "Ya revisamos todas las alternativas disponibles. "
                    "Procederé a levantar el reporte para que lo vea soporte técnico."
                )
            )
            return [FollowupAction("action_confirmar_reporte")]

        # Mostrar siguiente tanda
        siguiente_idx = min(idx + MAX_PASOS_POR_TANDA, len(pasos_solucion))
        siguientes_pasos = pasos_solucion[idx:siguiente_idx]

        texto_pasos = "\n".join(
            [f"{i+1+idx}️⃣ {p}" for i, p in enumerate(siguientes_pasos)]
        )

        dispatcher.utter_message(
            text=f"Continuemos con más pasos de solución:\n\n{texto_pasos}"
        )

        botones = [
            {"title": "Ya se solucionó", "payload": "/incidente_solucionado"},
            {"title": "Ver más pasos", "payload": "/ver_mas_pasos"},
            {"title": "Generar reporte", "payload": "/levantar_reporte"},
        ]
        dispatcher.utter_message(
            text="¿Quieres intentar con más pasos o prefieres que levante el reporte?",
            buttons=botones,
        )

        session_id = tracker.get_slot("rag_session_id")
        if session_id:
            log_rag_event(
                {
                    "type": "rag_followup_choice",
                    "session_id": session_id,
                    "user_id": tracker.sender_id,
                    "choice": "ver_mas_pasos",
                    "kb_steps_index_before": int(idx),
                    "kb_steps_round_before": int(ronda),
                }
            )

        return [
            SlotSet("kb_steps_index", float(siguiente_idx)),
            SlotSet("kb_steps_round", float(ronda + 1)),
        ]

def log_rag_event(event: Dict[Text, Any]) -> None:
    
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        event = dict(event)
        event["timestamp"] = datetime.utcnow().isoformat()
        with open(RAG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[RAG-LOG] Error al escribir el log: {e}")


#Para efectos de pruebas y mejoras futuras
def generar_self_query(descripcion: str) -> dict:
    prompt = f"""
    Eres un sistema experto en soporte técnico.
    Dada la descripción del problema, produce una clasificación con:
    - semantic_query (texto reformulado)
    - categoria (computadora, monitor, impresora_termica, scannersfin, routers, otros)
    - subcategoria (si aplica)
    - keywords (lista de palabras clave)

    Descripción: "{descripcion}"

    Responde estrictamente en JSON.
    """

    resp = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[{"role": "user", "content": prompt}]
    )

    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except:
        return {
            "semantic_query": descripcion,
            "categoria": None,
            "subcategoria": None,
            "keywords": []
        }
