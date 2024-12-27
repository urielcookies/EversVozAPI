import os
from flask import Flask, request, jsonify, send_file
import json
import openai
from services.detect_language import detect_language
from services.translate import translate_to_english
from services.grammar_check import grammar_check
# from services.phonetic_transcription import phonetic_transcription
from services.phonetic_explanation import phonetic_explanation
from utils.auth import require_transcribe_api_key 
from google.cloud import texttospeech
from io import BytesIO

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./eversvoz-a6e9e2b3bfe7.json"

MAX_LENGTH = 250

@app.route('/transcribe', methods=['POST'])
@require_transcribe_api_key
def transcribe():
  data = request.json

  if not data or 'text' not in data or 'lang' not in data:
    return jsonify({"error": "Please provide 'text' and 'lang' in the request body"}), 400

  client_lang = data["lang"]
  input_text = data["text"]

  if not input_text or len(input_text) > MAX_LENGTH:
    return jsonify({"error": f"Text length exceeds {MAX_LENGTH} characters or is empty"}), 400

  if client_lang not in ['es', 'en']:
    return jsonify({"error": "Invalid value for 'lang'. Allowed values are 'es' or 'en'"}), 400

  detected_lang_response = detect_language(input_text)
  detected_lang_data = json.loads(detected_lang_response.get_data(as_text=True))
  detected_lang = detected_lang_data.get("detected_lang", "")

  if detected_lang == 'unsupported':
    return jsonify({"error": "Language Needs to be in English or Spanish"}), 400

  english_phrase = ''
  if detected_lang == 'english':
    grammar_check_response = grammar_check(input_text)
    grammar_check_data = json.loads(grammar_check_response.get_data(as_text=True))
    english_phrase = grammar_check_data.get("grammar_check", "")
  elif detected_lang == 'spanish':
    translate_response = translate_to_english(input_text)
    translate_data = json.loads(translate_response.get_data(as_text=True))
    english_phrase = translate_data.get("translation", "")

  # phonetic_response = phonetic_transcription(english_phrase)
  # phonetic_data = json.loads(phonetic_response.get_data(as_text=True))

  phonetic_explanation_response = phonetic_explanation(english_phrase)
  phonetic_explanation_data = json.loads(phonetic_explanation_response.get_data(as_text=True))

  response_data = {
    "detected_lang": detected_lang,
    "english_phrase": english_phrase,
    # "phonetic_transcription": phonetic_data.get("phonetic_transcription", ""),
    "phonetic_explanation": phonetic_explanation_data.get("phonetic_explanation", "")
  }

  return app.response_class(
    json.dumps(response_data, ensure_ascii=False),
    mimetype='application/json'
  )

@app.route('/synthesize', methods=['POST'])
def synthesize_speech():
  # Get the text and settings from the request body
  data = request.json
  text = data.get('text', 'Hello, world!')
  language_code = data.get('language_code', 'en-US')  # Default to US English
  gender = data.get('gender', 'NEUTRAL')  # Default to neutral voice
  speaking_rate = data.get('speaking_rate', 1.0)  # Default to normal speed
  pitch = data.get('pitch', 0.0)  # Default to normal pitch
  volume_gain_db = data.get('volume_gain_db', 0.0)  # Default to normal volume

  # Initialize the Text-to-Speech client
  client = texttospeech.TextToSpeechClient()

  # Set the text input
  synthesis_input = texttospeech.SynthesisInput(text=text)

  # Set voice parameters
  ssml_gender = getattr(texttospeech.SsmlVoiceGender, gender.upper(), texttospeech.SsmlVoiceGender.NEUTRAL)
  voice = texttospeech.VoiceSelectionParams(
    language_code=language_code,
    ssml_gender=ssml_gender
  )

  # Set audio configuration
  audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3,
    speaking_rate=speaking_rate,
    pitch=pitch,
    volume_gain_db=volume_gain_db
  )

  # Generate the audio
  response = client.synthesize_speech(
    input=synthesis_input, voice=voice, audio_config=audio_config
  )

  # Use BytesIO to handle audio content in memory
  audio_file = BytesIO(response.audio_content)

  # Send the audio file to the client
  return send_file(audio_file, as_attachment=False, mimetype='audio/mpeg')

if __name__ == '__main__':
  app.run(debug=True, host='0.0.0.0', port=5001)
