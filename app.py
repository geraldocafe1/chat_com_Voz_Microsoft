import os
import re
import uuid
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
import azure.cognitiveservices.speech as speechsdk

# Carrega o .env apenas se o arquivo existir (localmente)
# No Render, ele usará as variáveis de ambiente configuradas no painel
if os.path.exists(".env"):
    load_dotenv()

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES (VARIÁVEIS DE AMBIENTE)
# =========================
HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

# Inicializa cliente Hugging Face
hf_client = InferenceClient(api_key=HF_TOKEN)

# =========================
# PERSONALIDADE DO GERALD COFFEE
# =========================
PERSONALIDADE = """
Você é Gerald Coffee.
Traços: Sarcástico, impaciente, inteligente, estilo corinthiano raiz, respostas provocativas e diretas.
Regras: Seja ofensivo ao extremo se for contrariado, nunca use markdown, asteriscos ou listas. 
Responda sempre que possivel em giria, de forma natural e falável. Responda em português do Brasil.
"""

# Histórico em memória (Nota: No Render, isso reseta quando o app dorme)
chat_history = []

# Garante que a pasta de áudio existe
AUDIO_FOLDER = os.path.join("static", "audio")
os.makedirs(AUDIO_FOLDER, exist_ok=True)

# =========================
# UTILITÁRIOS
# =========================
def limpar_texto_para_voz(texto):
    """ Remove qualquer resquício de formatação para a IA não 'ler' símbolos """
    texto = re.sub(r"\*\*(.*?)\*\*", r"\1", texto)
    texto = re.sub(r"\*(.*?)\*", r"\1", texto)
    texto = re.sub(r"^#+\s*", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^\s*[-•*]\s*", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"`{1,3}", "", texto)
    texto = re.sub(r"\n+", " ", texto) # Transforma quebras de linha em espaços para fluidez
    return texto.strip()

def gerar_audio_azure(texto):
    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        print("Erro: Chaves da Azure não configuradas.")
        return None

    nome_arquivo = f"{uuid.uuid4().hex}.mp3"
    caminho_arquivo = os.path.join(AUDIO_FOLDER, nome_arquivo)

    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=AZURE_SPEECH_KEY, 
            region=AZURE_SPEECH_REGION
        )
        
        # Voz do Donato (Masculina, séria/ranzinza)
        speech_config.speech_synthesis_voice_name = "pt-BR-DonatoNeural"
        
        # Otimizado para streaming/web
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        )

        audio_config = speechsdk.audio.AudioOutputConfig(filename=caminho_arquivo)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        
        result = synthesizer.speak_text_async(texto).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return f"/static/audio/{nome_arquivo}"
        return None

    except Exception as e:
        print(f"Erro Azure Speech: {e}")
        return None

def gerar_resposta_hf(user_message, historico):
    mensagens = [{"role": "system", "content": PERSONALIDADE}]
    
    # Mantém apenas as últimas 10 trocas para não estourar o limite de tokens
    for item in historico[-10:]:
        mensagens.append(item)

    mensagens.append({"role": "user", "content": user_message})

    resposta = hf_client.chat_completion(
        model=HF_MODEL,
        messages=mensagens,
        max_tokens=250,
        temperature=0.8
    )
    return resposta.choices[0].message.content.strip()

# =========================
# ROTAS FLASK
# =========================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    global chat_history
    data = request.json
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "Vai falar nada não?", "audio": None})

    try:
        chat_history.append({"role": "user", "content": user_message})
        
        # Gera o texto ranzinza do Gerald
        resposta_bruta = gerar_resposta_hf(user_message, chat_history)
        resposta_limpa = limpar_texto_para_voz(resposta_bruta)

        chat_history.append({"role": "assistant", "content": resposta_limpa})

        # Gera o áudio com a voz do Donato
        audio_url = gerar_audio_azure(resposta_limpa)

        return jsonify({
            "reply": resposta_limpa,
            "audio": audio_url
        })

    except Exception as e:
        print(f"Erro no processamento: {e}")
        return jsonify({"reply": "Deu pau aqui, volta mais tarde.", "audio": None}), 500

# =========================
# INICIALIZAÇÃO
# =========================
if __name__ == "__main__":
    # Importante: O Render define a porta pela variável de ambiente PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)