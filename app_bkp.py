import os
import re
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai

load_dotenv()

app = Flask(__name__)

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

PERSONALIDADE = """
Você é Chat Coffee.

- Simpatica
- Paciente
- Super inteligente
- Estilo professora de ensino médio, mas sem ser chata
- Respostas meigas, mas sem ser melosa
- Respostas diretas, mas sem ser grosseira

Nunca seja ofensivo extremo.

REGRAS IMPORTANTES:
- Nunca use markdown
- Nunca use asteriscos
- Nunca use listas com símbolos tipo *, -, #
- Responda sempre em texto puro
- Seja natural e falável em voz
"""

chat_history = []


def limpar_texto_para_voz(texto):
    texto = re.sub(r"\*\*(.*?)\*\*", r"\1", texto)
    texto = re.sub(r"\*(.*?)\*", r"\1", texto)
    texto = re.sub(r"^#+\s*", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^\s*[-•]\s*", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"`{1,3}", "", texto)
    texto = re.sub(r"\n\s*\n+", "\n\n", texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    return texto.strip()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    global chat_history

    data = request.json
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "Manda alguma coisa decente aí."})

    chat_history.append(f"Usuário: {user_message}")

    historico_limitado = chat_history[-12:]
    contexto = PERSONALIDADE + "\n\n" + "\n".join(historico_limitado)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contexto
        )

        resposta = response.text if response.text else "Hoje eu tô sem paciência até pra responder."
        resposta = limpar_texto_para_voz(resposta)

        chat_history.append(f"Aetherius: {resposta}")

        return jsonify({"reply": resposta})

    except Exception as e:
        return jsonify({"reply": f"Deu ruim no servidor: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)