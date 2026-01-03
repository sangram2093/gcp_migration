from gtts import gTTS

text = (
    "Our developers spend a disproportionate amount of time on Jira updates, "
    "worklogs, and rituals, instead of creating business value."
)

tts = gTTS(text=text, lang="en", tld="co.in")  # Indian English
tts.save("indian_free.mp3")
print("✅ Saved indian_free.mp3")
