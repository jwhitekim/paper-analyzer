from google import genai
from google.genai import types

client = genai.Client(api_key="AIzaSyD_nDxJqJvTtU68Fk_c3BIDhxQ4NfuIuzE")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="3D Medical image segmentation using parallel transformers 논문의 초록, 제안 방법, 주요 결론을 찾아서 한국어로 정리해줘",
    config=types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())]
    )
)
print(response.text)