import json

from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = [
    "https://www.googleapis.com/auth/drive"
]


with open(
    "credentials.json",
    "r"
) as file:

    client_config = json.load(
        file
    )


flow = InstalledAppFlow.from_client_config(
    client_config,
    SCOPES
)


credentials = flow.run_local_server(
    port=8080,
    access_type="offline",
    prompt="consent"
)


print()
print("REFRESH TOKEN:")
print(credentials.refresh_token)
print()