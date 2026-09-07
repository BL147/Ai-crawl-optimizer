from google import genai

client = genai.Client()

response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents="Say hello. You are helping test an AI crawler project."
)

print(response.text)