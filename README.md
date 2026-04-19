# Chess Academy 3D (Python)

3D šachová aplikace v Pythonu s profesionálním UI stylem a JSON databází.

## Co aplikace umí
- 3D šachovnici a 3D figurky.
- Přihlášení uživatele při startu aplikace.
- Až 5 uživatelů na jednom zařízení.
- Vytvoření uživatele + přihlášení tlačítkem „Přihlásit se“.
- Odemknutí sekcí po přihlášení:
  - 100 lekcí
  - 100 puzzle
  - 20 exhibicí s roboty
- Ukládání progresu do `data/database.json`.
- Efekt šachmatu: pod poraženým králem vyroste věž z červeného skla a následně exploduje.

## Instalace
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Spuštění
```bash
python main.py
```

## Databáze
Při prvním spuštění se automaticky vytvoří soubor:
- `data/database.json`

Obsahuje:
- uživatele
- 100 lekcí
- 100 puzzle
- 20 exhibicí
