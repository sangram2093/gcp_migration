from google.cloud import texttospeech

# Initialize client
client = texttospeech.TextToSpeechClient()

# Text to convert (8-second target)
input_text = texttospeech.SynthesisInput(
    text="Our developers spend a disproportionate amount of time on Jira updates, worklogs, and rituals, instead of creating business value."
)

# Use an Indian English male voice
voice = texttospeech.VoiceSelectionParams(
    language_code="en-IN",          # Indian English
    name="en-IN-Neural2-C",         # Natural male neural voice
    ssml_gender=texttospeech.SsmlVoiceGender.MALE
)

# Configure audio output
audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3,
    speaking_rate=0.95,             # Adjust pace to hit ~8 seconds
    pitch=0.0
)

# Synthesize speech
response = client.synthesize_speech(
    input=input_text,
    voice=voice,
    audio_config=audio_config
)

# Save as MP3
with open("output_indian.mp3", "wb") as out:
    out.write(response.audio_content)
    print("✅ Indian-accent voice saved as output_indian.mp3")
