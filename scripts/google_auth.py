"""Flujo OAuth de Google Calendar. Correr UNA vez en tu PC (no en la Raspberry):

    pip install google-auth-oauthlib
    python scripts/google_auth.py [ruta/a/credentials.json]

Abre el navegador para loguearte y genera token.json (con refresh token permanente,
siempre que la app esté publicada "En producción" en Google Cloud — ver README).
Después copiá credentials.json y token.json a la carpeta data/ del proyecto en la Pi.
"""

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def main() -> None:
    credenciales = Path(sys.argv[1] if len(sys.argv) > 1 else "credentials.json")
    if not credenciales.exists():
        print(
            f"No encuentro {credenciales}.\n"
            "Descargalo desde Google Cloud Console → Credenciales → "
            "ID de cliente OAuth (tipo 'Aplicación de escritorio')."
        )
        raise SystemExit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(credenciales), SCOPES)
    creds = flow.run_local_server(port=0)

    salida = credenciales.parent / "token.json"
    salida.write_text(creds.to_json())
    print(f"\n✅ Listo: {salida}")
    if not creds.refresh_token:
        print(
            "⚠️ OJO: el token NO tiene refresh_token. Revocá el acceso en "
            "https://myaccount.google.com/permissions y volvé a correr este script."
        )
    print("Copiá credentials.json y token.json a data/ en la Raspberry.")


if __name__ == "__main__":
    main()
