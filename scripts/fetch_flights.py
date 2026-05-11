"""
fetch_flights.py
Busca chegadas e partidas na AviationStack API (gratuita).
Salva cada aeroporto em data/{ICAO}.json para o GitHub Pages.

Variaveis de ambiente:
  AIRPORTS           -> ICAOs separados por virgula (ex: SBCA,SBGR)
                        Padrao: SBCA
  AVIATIONSTACK_KEY  -> API Key da AviationStack (GitHub Secret)

Plano gratuito: 100 chamadas/mes.
  1 aeroporto (chegadas + partidas = 2 chamadas) x 1x/dia = 60/mes  OK
  2 aeroportos x 1x/dia = 120/mes  (leve ultrapassagem)
"""

import json
import os
from datetime import datetime, timezone

import requests

# ── Configuracoes ─────────────────────────────────────────────────────────────

API_KEY      = os.environ.get("AVIATIONSTACK_KEY", "").strip()
airports_env = os.environ.get("AIRPORTS", "SBCA")
AIRPORTS     = [a.strip().upper() for a in airports_env.split(",") if a.strip()]
API_BASE     = "http://api.aviationstack.com/v1"   # HTTP no plano gratuito

if not API_KEY:
    print("[ERRO] AVIATIONSTACK_KEY nao configurado. Adicione o Secret no repositorio.")
    raise SystemExit(1)

print(f"AviationStack API configurada.")
print(f"Aeroportos: {', '.join(AIRPORTS)}")

# Mapa ICAO -> nome
AIRPORT_NAMES = {
    "SBRB":"Rio Branco","SBMO":"Maceio","SBMQ":"Macapa","SBEG":"Manaus",
    "SBSV":"Salvador","SBIL":"Ilheus","SBPS":"Porto Seguro",
    "SBFZ":"Fortaleza","SBJU":"Juazeiro do Norte","SBBR":"Brasilia",
    "SBVT":"Vitoria","SBGO":"Goiania","SBSL":"Sao Luis","SBCY":"Cuiaba",
    "SBCG":"Campo Grande","SBCF":"Belo Horizonte / Confins",
    "SBBH":"Belo Horizonte / Pampulha","SBUL":"Uberlandia",
    "SBBE":"Belem","SBSN":"Santarem","SBJP":"Joao Pessoa",
    "SBCT":"Curitiba","SBFI":"Foz do Iguacu","SBCA":"Cascavel",
    "SBLO":"Londrina","SBMG":"Maringa","SBRF":"Recife","SBTE":"Teresina",
    "SBGL":"Rio de Janeiro / Galeao","SBRJ":"Rio / Santos Dumont",
    "SBSG":"Natal","SBPA":"Porto Alegre","SBCX":"Caxias do Sul",
    "SBPV":"Porto Velho","SBBV":"Boa Vista","SBFL":"Florianopolis",
    "SBJV":"Joinville","SBNF":"Navegantes","SBGR":"Sao Paulo / Guarulhos",
    "SBSP":"Sao Paulo / Congonhas","SBKP":"Campinas / Viracopos",
    "SBRP":"Ribeirao Preto","SBSE":"Aracaju","SBPJ":"Palmas",
}


def fetch_flights(icao: str, kind: str) -> list:
    """
    kind: 'arrival' ou 'departure'
    Retorna lista de voos normalizados.
    """
    param_key = "arr_icao" if kind == "arrival" else "dep_icao"
    try:
        r = requests.get(
            f"{API_BASE}/flights",
            params={
                "access_key": API_KEY,
                param_key:    icao,
                "limit":      100,
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        if "error" in data:
            msg = data["error"].get("message", str(data["error"]))
            print(f"  [AVISO] API retornou erro para {icao} ({kind}): {msg}")
            return []

        flights = data.get("data", [])
        result  = []

        for f in flights:
            airline_info  = f.get("airline") or {}
            dep_info      = f.get("departure") or {}
            arr_info      = f.get("arrival")   or {}
            flight_info   = f.get("flight")    or {}

            if kind == "arrival":
                route_icao = dep_info.get("icao", "")
                scheduled  = arr_info.get("scheduled", "")
                estimated  = arr_info.get("estimated", "")
                actual     = arr_info.get("actual", "")
            else:
                route_icao = arr_info.get("icao", "")
                scheduled  = dep_info.get("scheduled", "")
                estimated  = dep_info.get("estimated", "")
                actual     = dep_info.get("actual", "")

            # Determina o melhor horario disponivel
            time_iso = actual or estimated or scheduled or ""

            # Determina situacao
            raw_status = (f.get("flight_status") or "").lower()
            status_map = {
                "landed":    "pousado",
                "active":    "em voo",
                "scheduled": "programado",
                "cancelled": "cancelado",
                "diverted":  "desviado",
                "incident":  "incidente",
            }
            status = status_map.get(raw_status, raw_status or "programado")

            result.append({
                "callsign":     flight_info.get("iata") or flight_info.get("icao") or "?",
                "airline":      airline_info.get("name") or airline_info.get("iata") or "?",
                "airport":      route_icao,
                "airport_name": AIRPORT_NAMES.get(route_icao, route_icao or "?"),
                "scheduled":    scheduled,
                "time_iso":     time_iso,
                "status":       status,
            })

        return result

    except Exception as e:
        print(f"  [AVISO] Falha ao buscar {kind} de {icao}: {e}")
        return []


# ── Execucao ──────────────────────────────────────────────────────────────────

os.makedirs("data", exist_ok=True)

for icao in AIRPORTS:
    name = AIRPORT_NAMES.get(icao, icao)
    print(f"\nBuscando {icao} - {name}...")

    arrivals   = fetch_flights(icao, "arrival")
    departures = fetch_flights(icao, "departure")

    output = {
        "updated_at":   datetime.now(timezone.utc).isoformat(),
        "airport_icao": icao,
        "airport_name": name,
        "source":       "AviationStack",
        "arrivals":     arrivals,
        "departures":   departures,
    }

    with open(f"data/{icao}.json", "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)

    print(f"  OK: {len(arrivals)} chegadas, {len(departures)} partidas.")

print("\nConcluido.")
