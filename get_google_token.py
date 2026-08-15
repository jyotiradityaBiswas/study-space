from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive"
]

flow = InstalledAppFlow.from_client_secrets_file(
    "credentials.json",
    SCOPES
)

credentials = flow.run_local_server(
    port=8080,
    access_type="offline",
    prompt="consent"
)

with open("token.json", "w") as token_file:
    token_file.write(credentials.to_json())

print("Google OAuth token created.")