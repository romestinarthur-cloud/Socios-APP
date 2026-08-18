"""
Récupère la liste des clubs/équipes disponibles sur Socios.com avec leur logo.
Scrape la page https://www.socios.com/sports-teams/ à chaque appel (avec cache TTL côté app.py).
Si le scraping échoue (page indisponible, structure changée...), on retombe sur une
liste de secours (SEED_TEAMS) récupérée le 17/08/2026, pour que l'appli reste utilisable.
"""

import re
import requests
from bs4 import BeautifulSoup

SOCIOS_TEAMS_URL = "https://www.socios.com/sports-teams/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_teams_live(timeout: int = 15) -> list[dict]:
    """Scrape en direct la page socios.com/sports-teams/.
    Retourne une liste de dicts {"name": str, "logo": str}.
    Lève une exception si ça échoue (réseau, structure de page changée, etc.)."""
    resp = requests.get(SOCIOS_TEAMS_URL, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    teams = []
    seen = set()
    for img in soup.find_all("img"):
        alt = (img.get("alt") or "").strip()
        src = img.get("src") or img.get("data-src") or ""
        # Les logos de clubs sont hébergés sur assets.chiliz.com/partner/...
        if "assets.chiliz.com/partner" not in src:
            continue
        if not alt or alt in seen:
            continue
        seen.add(alt)
        teams.append({"name": alt, "logo": src})

    if not teams:
        raise ValueError("Aucune équipe trouvée : la structure de la page a probablement changé.")
    return sorted(teams, key=lambda t: t["name"].lower())


# Liste de secours (snapshot du 17/08/2026) utilisée si le scraping live échoue.
SEED_TEAMS = [
    {"name": "AC Milan", "logo": "https://assets.chiliz.com/partner/403d8e06-fbf2-4a5e-a379-09edf90cb2a0/partner_logo/7a7a2a32-7bd2-407a-a2d4-7ad63ceeda11.png"},
    {"name": "Alanyaspor", "logo": "https://assets.chiliz.com/partner/453dd0a3-45e9-46f4-87cb-9f6bb78d6558/partner_logo/30bf8919-d689-4c2e-af6f-1bf49e4aac78.png"},
    {"name": "Apollon Limassol FC", "logo": "https://assets.chiliz.com/partner/fa398d45-0bb3-4666-87bc-d35f43f1e863/partner_logo/34fe17b8-07d9-499d-ad98-09c8679e0dec.png"},
    {"name": "Arsenal FC", "logo": "https://assets.chiliz.com/partner/dbe044d5-25f8-4a05-b9f9-9fc44b5ab165/partner_logo/3b493d31-ebd8-4f0e-ac18-fb0052f81ae3.png"},
    {"name": "AS Monaco", "logo": "https://assets.chiliz.com/partner/6d189e7d-1af6-47ae-9c82-545b774bcb96/partner_logo/6d598cba-5fce-4be7-8ec4-3680e0ff8d27.png"},
    {"name": "AS Roma", "logo": "https://assets.chiliz.com/partner/710057ae-50a1-4a90-9c81-2a5875d7b298/partner_logo/80cb3a04-5e52-4df8-9a93-a9098b326601.png"},
    {"name": "Aston Villa", "logo": "https://assets.chiliz.com/partner/6dba8bf0-0610-4ef9-905b-fe5c62bb1bd4/partner_logo/918ef30a-1b8a-4c2e-88a8-305efbafc6b8.png"},
    {"name": "Atlético de Madrid", "logo": "https://assets.chiliz.com/partner/3c79d471-a7ef-4616-983e-b1a61d4eb6e0/partner_logo/3e7be134-ea9e-4124-8d3f-68535eae663c.png"},
    {"name": "Belgium - RBFA", "logo": "https://assets.chiliz.com/partner/72646029-e6a4-41eb-88ad-e6a52e3a8721/partner_logo/c47482bc-007c-4dfc-85ef-b8662b04a430.png"},
    {"name": "Bologna FC", "logo": "https://assets.chiliz.com/partner/2a8844ca-deb6-4712-b4d5-3135b30ae936/partner_logo/8fe3dbb5-cbb8-41eb-9041-249323509894.png"},
    {"name": "BSC Young Boys", "logo": "https://assets.chiliz.com/partner/5796d2d6-da2a-4914-82fe-3eeaba3c1bca/partner_logo/9248c1ee-cdae-4b92-b7dc-6814fedfdcec.png"},
    {"name": "Clube Atlético Mineiro", "logo": "https://assets.chiliz.com/partner/3e3d0c93-9f6f-4a10-a103-527ea8e9da12/partner_logo/d15ffb67-64c6-4908-bf1a-b8fc76c3f56e.png"},
    {"name": "Corinthians", "logo": "https://assets.chiliz.com/partner/759e82b6-46c3-4891-bfb1-f239a42d0669/partner_logo/be7cf147-89e3-40bb-bdd3-5698f3c8987a.png"},
    {"name": "Crystal Palace", "logo": "https://assets.chiliz.com/partner/c479a4d2-5fe4-4721-8823-10ee5cc59980/partner_logo/b439acb3-1dca-45eb-bef2-c876dd5f960b.png"},
    {"name": "EC Bahia", "logo": "https://assets.chiliz.com/partner/4b56e5e2-33f9-42bf-aa90-b9c261fd5c21/partner_logo/cbe800bc-a65a-4778-a249-7aa79588bd3f.png"},
    {"name": "Everton Football Club", "logo": "https://assets.chiliz.com/partner/8944b4a9-2a1a-451a-a360-678168c13d61/partner_logo/d2c8e49f-51e8-4471-abb6-4e58569246c1.png"},
    {"name": "FC Barcelona", "logo": "https://assets.chiliz.com/partner/4f9e8350-e68c-4874-91b0-3c30a0be3866/partner_logo/36a90588-2cf6-40e6-860f-e133bd78c358.png"},
    {"name": "FC Internazionale Milano", "logo": "https://assets.chiliz.com/partner/99dd7cc7-80a6-4728-84ea-fd96203fc223/partner_logo/204821af-8292-4d30-ab69-9c8426e8b25a.png"},
    {"name": "Flamengo", "logo": "https://assets.chiliz.com/partner/3392534e-774f-4cc0-b085-db27aef3aff4/partner_logo/93cacaa3-52d7-49c2-80a7-b96269f3c82d.png"},
    {"name": "Fluminense FC", "logo": "https://assets.chiliz.com/partner/7e5164a6-08c0-4e56-996c-4c986b3e9acb/partner_logo/a134afc9-cee5-434c-a617-8242817468f6.png"},
    {"name": "Fortuna Sittard", "logo": "https://assets.chiliz.com/partner/0f96aa5c-9db8-4544-95c7-5b47ab7ec3a8/partner_logo/ce58a488-2a46-48f7-96b5-59385f8754af.png"},
    {"name": "Galatasaray S.K.", "logo": "https://assets.chiliz.com/partner/fc00f3c8-1f85-4bb6-bf73-c6a5c51c0131/partner_logo/ccf45904-3c41-4731-a6f8-a490babd6657.png"},
    {"name": "GNK Dinamo Zagreb", "logo": "https://assets.chiliz.com/partner/cbe4d995-b48f-48eb-9b87-5552c4bb0fb3/partner_logo/1b096fb7-0e99-4d2f-ad2b-f396b3e7c108.png"},
    {"name": "Göztepe S.K.", "logo": "https://assets.chiliz.com/partner/44ecfe07-029a-4599-9b02-c961b4c9e9d6/partner_logo/df9688cd-279a-4c78-b859-7d582bebb868.png"},
    {"name": "İstanbul Başakşehir FK", "logo": "https://assets.chiliz.com/partner/64cd633a-17b7-436f-bfa1-760726e80fad/partner_logo/5ed36d8e-db1f-4e39-9f6e-6b366ecc15d7.png"},
    {"name": "Italy - FIGC", "logo": "https://assets.chiliz.com/partner/dd1402d0-205a-4208-b6fb-40d71514cb3e/partner_logo/dc62206e-af8a-4344-959b-dc1a85557bb2.png"},
    {"name": "Johor Darul Ta'zim F.C", "logo": "https://assets.chiliz.com/partner/39da2113-a5c1-4bb3-8e52-c7da6b8c802f/partner_logo/3fe87b53-83dd-443e-809b-0d837d7be932.png"},
    {"name": "Juventus", "logo": "https://assets.chiliz.com/partner/a0ad0a62-728b-4634-bf69-b3cf23435527/partner_logo/f84e5f39-27a9-4ddf-8263-2cc875ceb133.png"},
    {"name": "Leeds United FC", "logo": "https://assets.chiliz.com/partner/267325a9-e722-4278-a5ec-c50a942c8402/partner_logo/52f2f0a8-95d1-46b4-a575-1feecab520ef.png"},
    {"name": "Legia Warsaw", "logo": "https://assets.chiliz.com/partner/cc99945d-bac7-4391-84da-0eb48d06644e/partner_logo/ac73c387-5f9a-425b-b870-89920958d414.png"},
    {"name": "Levante U.D.", "logo": "https://assets.chiliz.com/partner/46d746df-ffb1-4a4b-b591-78e59f22023d/partner_logo/609ea2e6-9d7c-4ff6-b0eb-ca8bb6fbfb0c.png"},
    {"name": "Manchester City FC", "logo": "https://assets.chiliz.com/partner/a981c966-c2c2-4e6a-ac50-397e2eb3029a/partner_logo/ae2ed1fc-6f66-4fe7-889b-b43adcb08da6.png"},
    {"name": "Millonarios", "logo": "https://assets.chiliz.com/partner/1743c392-3cbe-480b-8137-e9999cc40aa5/partner_logo/6e5245da-24e0-4025-a9aa-2734a79c13d7.png"},
    {"name": "Napoli", "logo": "https://assets.chiliz.com/partner/69f65fe8-2863-478c-896a-26f84b4a2b21/partner_logo/fbada47a-4429-4332-a84c-2fad7db945ce.png"},
    {"name": "Paris Saint-Germain", "logo": "https://assets.chiliz.com/partner/c2d54ced-43c2-43e2-9d58-66684f02afb2/partner_logo/54adc1b8-bd96-4a86-9ed2-e5a149d940f8.png"},
    {"name": "Persija", "logo": "https://assets.chiliz.com/partner/6a2bf594-eb8c-4073-9608-a90aa9292ece/partner_logo/dc9c6f87-cdc2-4f78-a9dd-347aac99ea33.png"},
    {"name": "Portugal - FPF", "logo": "https://assets.chiliz.com/partner/8d51e1ad-9dc4-4a72-a652-4c5a1f80663c/partner_logo/08b23704-a315-49c4-8fb4-8ce8fa2f3fa6.png"},
    {"name": "Real Sociedad", "logo": "https://assets.chiliz.com/partner/b3f9fb0f-4ce9-4bd8-806f-948c3194d276/partner_logo/4bf52bd6-8ef9-4ff2-b97d-71bc511baea4.png"},
    {"name": "S.C. Internacional", "logo": "https://assets.chiliz.com/partner/141bf2f1-2a45-42af-9216-40d8adfc3552/partner_logo/2558be46-eb5b-4063-902e-754d816bdc07.png"},
    {"name": "Samsunspor", "logo": "https://assets.chiliz.com/partner/81bb56f5-2f8a-4cf9-ab87-f259681a15df/partner_logo/05f1931b-b41f-4036-843c-315e6d08e709.png"},
    {"name": "São Paulo FC", "logo": "https://assets.chiliz.com/partner/bc90f3ff-e9f8-4a51-892d-837494683506/partner_logo/b296d19d-66f3-4cf7-ba22-c17cfe9a1e9f.png"},
    {"name": "Scotland - SFA", "logo": "https://assets.chiliz.com/partner/36838ebd-5f29-4b26-85f7-7eca503069ae/partner_logo/a33536e3-dc3f-4119-a24e-8be3d1280309.png"},
    {"name": "SE Palmeiras", "logo": "https://assets.chiliz.com/partner/398d9ed2-5b11-474e-bd74-95f92f07e6c4/partner_logo/24b4ebc5-5c71-40d0-a4c1-00623ca3404b.png"},
    {"name": "Sevilla FC", "logo": "https://assets.chiliz.com/partner/a83e1852-9db9-4b31-852f-8132e0a88c73/partner_logo/3d25e224-7297-4fe7-8045-55b6b6a43293.png"},
    {"name": "SL Benfica", "logo": "https://assets.chiliz.com/partner/bcab2074-91bf-4938-865a-6d3d69bb8c06/partner_logo/1169b439-3e93-4ade-85b0-dd303d40bcc3.png"},
    {"name": "South Africa - SAFA", "logo": "https://assets.chiliz.com/partner/724cad87-34f1-496b-bd46-fa0a75661ea3/partner_logo/a75c3d88-52ba-49b8-b82a-6c82ef0e3510.png"},
    {"name": "Spain - RFEF", "logo": "https://assets.chiliz.com/partner/f2f99e66-f4e0-4683-bcc4-f288eac5869b/partner_logo/19fdbb6d-433a-41e7-8918-d848d43ecdaf.png"},
    {"name": "Tottenham Hotspur", "logo": "https://assets.chiliz.com/partner/e28dfba1-10dd-42d6-8d50-1b5260fc296c/partner_logo/f0827d9a-9d49-47cb-a902-e760acecb10f.png"},
    {"name": "Trabzonspor", "logo": "https://assets.chiliz.com/partner/cf93c282-b1cd-41a1-8c31-6d8b0de17f0a/partner_logo/bc9eaa7c-ba43-4965-a9bd-1ac09428035e.png"},
    {"name": "Valencia CF", "logo": "https://assets.chiliz.com/partner/61888b59-a44f-4808-b899-7afc8f04c4ea/partner_logo/4a7bcf01-794a-494c-8f9e-d9f26abbdac4.png"},
    {"name": "Vasco da Gama", "logo": "https://assets.chiliz.com/partner/9d6e0466-2564-49b7-ac11-ed727b513cb0/partner_logo/f2d42490-f4be-455d-aaf9-fbf57c11d2b2.png"},
    {"name": "MIBR", "logo": "https://assets.chiliz.com/partner/2a7c4de5-a179-4a3f-9bc7-a764f8e29d12/partner_logo/49861590-bd9c-4a9f-85f0-121be8952456.png"},
    {"name": "Ninjas in Pyjamas", "logo": "https://assets.chiliz.com/partner/8caa044f-7093-45a6-8a89-54610f74bba7/partner_logo/29e0af02-ea34-4295-b450-c15cda9e6c30.png"},
    {"name": "OG", "logo": "https://assets.chiliz.com/partner/f5230b16-f87f-4c26-b4d5-438db4371e7b/partner_logo/cad0259e-d6e0-4261-96ca-82dcf7664ff1.png"},
    {"name": "Team Heretics", "logo": "https://assets.chiliz.com/partner/baccb297-04a7-4d83-a88d-0a033be863a9/partner_logo/6a7e37a2-a87d-4ae1-8853-0d36595f02d6.png"},
    {"name": "RFK Racing", "logo": "https://assets.chiliz.com/partner/ed7d5d9e-ed2c-45c1-8d17-09fa4ffb9359/partner_logo/3b9bcc7a-210e-4748-a4c0-2ee7f53c80cc.png"},
    {"name": "UFC", "logo": "https://assets.chiliz.com/partner/60e658f8-b5e6-48b2-ba1c-e4d1fb2ea7bb/partner_logo/8fbeb64f-cedd-43fd-aa67-a62c79decf15.png"},
    {"name": "The Sharks", "logo": "https://assets.chiliz.com/partner/a5aa4dde-9eef-4240-a60c-cea1bcaf4a78/partner_logo/f947be9b-80d5-4ee4-957c-ed9d18367e46.png"},
]


def get_teams() -> tuple[list[dict], bool]:
    """Retourne (liste_equipes, live_ok). live_ok=False si on a dû retomber sur la liste de secours."""
    try:
        return fetch_teams_live(), True
    except Exception:
        return SEED_TEAMS, False
