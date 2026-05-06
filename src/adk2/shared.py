"""Shared resources for the adk2 package."""

import os

from google import genai
from google.adk.models.google_llm import Gemini

client_global = genai.Client(
    vertexai=True,
    location=os.environ.get("GOOGLE_CLOUD_LOCATION", "europe-west4"),
)

global_model = Gemini(
    model="gemini-2.5-flash",
)
global_model.api_client = client_global
