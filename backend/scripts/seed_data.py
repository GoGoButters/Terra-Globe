"""Seed database from existing static data files.

Reads countries_data.csv, capitals.csv, countries.geojson, layers.json,
alliances.json, trade_data.json, diplomacy.json and populates the database.
"""

import asyncio
import csv
import json
from pathlib import Path
from typing import Any

from geoalchemy2.shape import from_shape
from shapely.geometry import shape, mapping
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models import (
    Country, IndicatorDefinition, IndicatorValue,
    Alliance, AllianceMember, TradeFlow, DiplomaticRelation,
    User,
)
from app.services.auth_service import get_password_hash

# ── Русские названия стран ──
COUNTRY_NAMES_RU = {
    "AFG": "Афганистан", "ALB": "Албания", "DZA": "Алжир", "AND": "Андорра",
    "AGO": "Ангола", "ATG": "Антигуа и Барбуда", "ARG": "Аргентина", "ARM": "Армения",
    "AUS": "Австралия", "AUT": "Австрия", "AZE": "Азербайджан", "BHS": "Багамские Острова",
    "BHR": "Бахрейн", "BGD": "Бангладеш", "BRB": "Барбадос", "BLR": "Беларусь",
    "BEL": "Бельгия", "BLZ": "Белиз", "BEN": "Бенин", "BTN": "Бутан",
    "BOL": "Боливия", "BIH": "Босния и Герцеговина", "BWA": "Ботсвана", "BRA": "Бразилия",
    "BRN": "Бруней", "BGR": "Болгария", "BFA": "Буркина-Фасо", "BDI": "Бурунди",
    "CPV": "Кабо-Верде", "KHM": "Камбоджа", "CMR": "Камерун", "CAN": "Канада",
    "CAF": "ЦАР", "TCD": "Чад", "CHL": "Чили", "CHN": "Китай",
    "COL": "Колумбия", "COM": "Коморы", "COG": "Республика Конго", "COD": "ДР Конго",
    "CRI": "Коста-Рика", "CIV": "Кот-д'Ивуар", "HRV": "Хорватия", "CUB": "Куба",
    "CYP": "Кипр", "CZE": "Чехия", "DNK": "Дания", "DJI": "Джибути",
    "DMA": "Доминика", "DOM": "Доминиканская Республика", "ECU": "Эквадор", "EGY": "Египет",
    "SLV": "Сальвадор", "GNQ": "Экваториальная Гвинея", "ERI": "Эритрея", "EST": "Эстония",
    "SWZ": "Эсватини", "ETH": "Эфиопия", "FJI": "Фиджи", "FIN": "Финляндия",
    "FRA": "Франция", "GAB": "Габон", "GMB": "Гамбия", "GEO": "Грузия",
    "DEU": "Германия", "GHA": "Гана", "GRC": "Греция", "GRD": "Гренада",
    "GTM": "Гватемала", "GIN": "Гвинея", "GNB": "Гвинея-Бисау", "GUY": "Гайана",
    "HTI": "Гаити", "HND": "Гондурас", "HUN": "Венгрия", "ISL": "Исландия",
    "IND": "Индия", "IDN": "Индонезия", "IRN": "Иран", "IRQ": "Ирак",
    "IRL": "Ирландия", "ISR": "Израиль", "ITA": "Италия", "JAM": "Ямайка",
    "JPN": "Япония", "JOR": "Иордания", "KAZ": "Казахстан", "KEN": "Кения",
    "KIR": "Кирибати", "PRK": "КНДР", "KOR": "Южная Корея", "KWT": "Кувейт",
    "KGZ": "Кыргызстан", "LAO": "Лаос", "LVA": "Латвия", "LBN": "Ливан",
    "LSO": "Лесото", "LBR": "Либерия", "LBY": "Ливия", "LIE": "Лихтенштейн",
    "LTU": "Литва", "LUX": "Люксембург", "MDG": "Мадагаскар", "MWI": "Малави",
    "MYS": "Малайзия", "MDV": "Мальдивы", "MLI": "Мали", "MLT": "Мальта",
    "MHL": "Маршалловы Острова", "MRT": "Мавритания", "MUS": "Маврикий", "MEX": "Мексика",
    "FSM": "Микронезия", "MDA": "Молдова", "MCO": "Монако", "MNG": "Монголия",
    "MNE": "Черногория", "MAR": "Марокко", "MOZ": "Мозамбик", "MMR": "Мьянма",
    "NAM": "Намибия", "NRU": "Науру", "NPL": "Непал", "NLD": "Нидерланды",
    "NZL": "Новая Зеландия", "NIC": "Никарагуа", "NER": "Нигер", "NGA": "Нигерия",
    "MKD": "Северная Македония", "NOR": "Норвегия", "OMN": "Оман", "PAK": "Пакистан",
    "PLW": "Палау", "PSE": "Палестина", "PAN": "Панама", "PNG": "Папуа — Новая Гвинея",
    "PRY": "Парагвай", "PER": "Перу", "PHL": "Филиппины", "POL": "Польша",
    "PRT": "Португалия", "QAT": "Катар", "ROU": "Румыния", "RUS": "Россия",
    "RWA": "Руанда", "KNA": "Сент-Китс и Невис", "LCA": "Сент-Люсия", "VCT": "Сент-Винсент и Гренадины",
    "WSM": "Самоа", "SMR": "Сан-Марино", "STP": "Сан-Томе и Принсипи", "SAU": "Саудовская Аравия",
    "SEN": "Сенегал", "SRB": "Сербия", "SYC": "Сейшелы", "SLE": "Сьерра-Леоне",
    "SGP": "Сингапур", "SVK": "Словакия", "SVN": "Словения", "SLB": "Соломоновы Острова",
    "SOM": "Сомали", "ZAF": "ЮАР", "SSD": "Южный Судан", "ESP": "Испания",
    "LKA": "Шри-Ланка", "SDN": "Судан", "SUR": "Суринам", "SWE": "Швеция",
    "CHE": "Швейцария", "SYR": "Сирия", "TJK": "Таджикистан", "TZA": "Танзания",
    "THA": "Таиланд", "TLS": "Восточный Тимор", "TGO": "Того", "TON": "Тонга",
    "TTO": "Тринидад и Тобаго", "TUN": "Тунис", "TUR": "Турция", "TKM": "Туркменистан",
    "TUV": "Тувалу", "UGA": "Уганда", "UKR": "Украина", "ARE": "ОАЭ",
    "GBR": "Великобритания", "USA": "США", "URY": "Уругвай", "UZB": "Узбекистан",
    "VUT": "Вануату", "VAT": "Ватикан", "VEN": "Венесуэла", "VNM": "Вьетнам",
    "YEM": "Йемен", "ZMB": "Замбия", "ZWE": "Зимбабве",
}

CAPITAL_NAMES_RU = {
    "AFG": "Кабул", "ALB": "Тирана", "DZA": "Алжир", "AND": "Андорра-ла-Велья",
    "AGO": "Луанда", "ATG": "Сент-Джонс", "ARG": "Буэнос-Айрес", "ARM": "Ереван",
    "AUS": "Канберра", "AUT": "Вена", "AZE": "Баку", "BHS": "Нассау",
    "BHR": "Манама", "BGD": "Дакка", "BRB": "Бриджтаун", "BLR": "Минск",
    "BEL": "Брюссель", "BLZ": "Бельмопан", "BEN": "Порто-Ново", "BTN": "Тхимпху",
    "BOL": "Сукре", "BIH": "Сараево", "BWA": "Габороне", "BRA": "Бразилиа",
    "BRN": "Бандар-Сери-Бегаван", "BGR": "София", "BFA": "Уагадугу", "BDI": "Гитега",
    "CPV": "Прая", "KHM": "Пномпень", "CMR": "Яунде", "CAN": "Оттава",
    "CAF": "Банги", "TCD": "Нджамена", "CHL": "Сантьяго", "CHN": "Пекин",
    "COL": "Богота", "COM": "Морони", "COG": "Браззавиль", "COD": "Киншаса",
    "CRI": "Сан-Хосе", "CIV": "Ямусукро", "HRV": "Загреб", "CUB": "Гавана",
    "CYP": "Никосия", "CZE": "Прага", "DNK": "Копенгаген", "DJI": "Джибути",
    "DMA": "Розо", "DOM": "Санто-Доминго", "ECU": "Кито", "EGY": "Каир",
    "SLV": "Сан-Сальвадор", "GNQ": "Малабо", "ERI": "Асмэра", "EST": "Таллин",
    "SWZ": "Мбабане", "ETH": "Аддис-Абеба", "FJI": "Сува", "FIN": "Хельсинки",
    "FRA": "Париж", "GAB": "Либревиль", "GMB": "Банжул", "GEO": "Тбилиси",
    "DEU": "Берлин", "GHA": "Аккра", "GRC": "Афины", "GRD": "Сент-Джорджес",
    "GTM": "Гватемала", "GIN": "Конакри", "GNB": "Бисау", "GUY": "Джорджтаун",
    "HTI": "Порт-о-Пренс", "HND": "Тегусигальпа", "HUN": "Будапешт", "ISL": "Рейкьявик",
    "IND": "Нью-Дели", "IDN": "Джакарта", "IRN": "Тегеран", "IRQ": "Багдад",
    "IRL": "Дублин", "ISR": "Иерусалим", "ITA": "Рим", "JAM": "Кингстон",
    "JPN": "Токио", "JOR": "Амман", "KAZ": "Астана", "KEN": "Найроби",
    "KIR": "Южная Тарава", "PRK": "Пхеньян", "KOR": "Сеул", "KWT": "Эль-Кувейт",
    "KGZ": "Бишкек", "LAO": "Вьентьян", "LVA": "Рига", "LBN": "Бейрут",
    "LSO": "Масеру", "LBR": "Монровия", "LBY": "Триполи", "LIE": "Вадуц",
    "LTU": "Вильнюс", "LUX": "Люксембург", "MDG": "Антананариву", "MWI": "Лилонгве",
    "MYS": "Куала-Лумпур", "MDV": "Мале", "MLI": "Бамако", "MLT": "Валлетта",
    "MHL": "Маджуро", "MRT": "Нуакшот", "MUS": "Порт-Луи", "MEX": "Мехико",
    "FSM": "Паликир", "MDA": "Кишинёв", "MCO": "Монако", "MNG": "Улан-Батор",
    "MNE": "Подгорица", "MAR": "Рабат", "MOZ": "Мапуту", "MMR": "Нейпьидо",
    "NAM": "Виндхук", "NRU": "Ярен", "NPL": "Катманду", "NLD": "Амстердам",
    "NZL": "Веллингтон", "NIC": "Манагуа", "NER": "Ниамей", "NGA": "Абуджа",
    "MKD": "Скопье", "NOR": "Осло", "OMN": "Маскат", "PAK": "Исламабад",
    "PLW": "Нгерулмуд", "PSE": "Рамалла", "PAN": "Панама", "PNG": "Порт-Морсби",
    "PRY": "Асунсьон", "PER": "Лима", "PHL": "Манила", "POL": "Варшава",
    "PRT": "Лиссабон", "QAT": "Доха", "ROU": "Бухарест", "RUS": "Москва",
    "RWA": "Кигали", "KNA": "Бастер", "LCA": "Кастри", "VCT": "Кингстаун",
    "WSM": "Апиа", "SMR": "Сан-Марино", "STP": "Сан-Томе", "SAU": "Эр-Рияд",
    "SEN": "Дакар", "SRB": "Белград", "SYC": "Виктория", "SLE": "Фритаун",
    "SGP": "Сингапур", "SVK": "Братислава", "SVN": "Любляна", "SLB": "Хониара",
    "SOM": "Могадишо", "ZAF": "Претория", "SSD": "Джуба", "ESP": "Мадрид",
    "LKA": "Шри-Джаяварденепура-Котте", "SDN": "Хартум", "SUR": "Парамарибо", "SWE": "Стокгольм",
    "CHE": "Берн", "SYR": "Дамаск", "TJK": "Душанбе", "TZA": "Додома",
    "THA": "Бангкок", "TLS": "Дили", "TGO": "Ломе", "TON": "Нукуалофа",
    "TTO": "Порт-оф-Спейн", "TUN": "Тунис", "TUR": "Анкара", "TKM": "Ашхабад",
    "TUV": "Фунафути", "UGA": "Кампала", "UKR": "Киев", "ARE": "Абу-Даби",
    "GBR": "Лондон", "USA": "Вашингтон", "URY": "Монтевидео", "UZB": "Ташкент",
    "VUT": "Порт-Вила", "VAT": "Ватикан", "VEN": "Каракас", "VNM": "Ханой",
    "YEM": "Сана", "ZMB": "Лусака", "ZWE": "Хараре",
}

# Path to static data files
# Host:   terra-globe/frontend/data  (script at backend/scripts/)
# Docker: /app/frontend/data         (script at /app/scripts/)
_SCRIPT_DIR = Path(__file__).resolve().parent.parent  # backend/ or /app
DATA_DIR = _SCRIPT_DIR.parent / "frontend" / "data"    # host fallback
if not DATA_DIR.exists():
    DATA_DIR = _SCRIPT_DIR / "frontend" / "data"       # docker fallback


def _parse_csv(filepath: Path) -> list[dict[str, str]]:
    """Parse a CSV file into a list of dicts."""
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _parse_json(filepath: Path) -> dict[str, Any] | list[dict]:
    """Parse a JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


async def seed_countries(session: AsyncSession) -> None:
    """Load countries from GeoJSON + CSV data."""
    geojson = _parse_json(DATA_DIR / "countries.geojson")
    csv_data = _parse_csv(DATA_DIR / "countries_data.csv")
    capitals = _parse_csv(DATA_DIR / "capitals.csv")

    # Index CSV data by iso3
    csv_by_iso3 = {row["iso3"]: row for row in csv_data}
    capitals_by_iso3 = {row["iso3"]: row for row in capitals}

    countries_to_insert = []

    for feature in geojson["features"]:
        props = feature["properties"]
        iso3 = props.get("ISO3166-1-Alpha-3", "")
        name = props.get("name") or props.get("NAME", "")

        # Skip invalid entries
        if not iso3 or iso3 == "-99":
            continue

        csv_row = csv_by_iso3.get(iso3, {})
        capital_row = capitals_by_iso3.get(iso3, {})

        # Build geometry
        geom = None
        centroid = None
        try:
            geom_obj = shape(feature["geometry"])
            if geom_obj.is_valid:
                geom = from_shape(geom_obj, srid=4326)
                centroid = from_shape(geom_obj.centroid, srid=4326)
        except Exception:
            pass

        country = Country(
            iso3=iso3,
            name=name or csv_row.get("name", ""),
            name_ru=COUNTRY_NAMES_RU.get(iso3),
            official_name=csv_row.get("name", ""),
            region=csv_row.get("region", ""),
            subregion=csv_row.get("subregion", ""),
            income_group=csv_row.get("income", ""),
            geometry=geom,
            centroid=centroid,
            capital_name=capital_row.get("capital", ""),
            capital_name_ru=CAPITAL_NAMES_RU.get(iso3),
            capital_lat=float(capital_row["lat"]) if capital_row.get("lat") else None,
            capital_lon=float(capital_row["lon"]) if capital_row.get("lon") else None,
            population=int(csv_row["pop"]) if csv_row.get("pop") and csv_row["pop"].isdigit() else None,
        )
        countries_to_insert.append(country)

    # Clear existing and insert
    await session.execute(delete(Country))
    session.add_all(countries_to_insert)
    await session.flush()
    print(f"  Seeded {len(countries_to_insert)} countries")


async def seed_indicators(session: AsyncSession) -> None:
    """Load indicator definitions and values from CSV + layers.json."""
    csv_data = _parse_csv(DATA_DIR / "countries_data.csv")
    layers = _parse_json(DATA_DIR / "layers.json")

    # Indicator columns from CSV
    indicator_columns = [
        "income", "gdp", "pop", "hdi", "freedom", "gdp_per_capita",
        "inflation", "gini", "unemployment", "life_expectancy", "literacy",
        "population_density", "urbanization", "democracy_index",
        "corruption", "press_freedom", "political_stability",
        "military_power", "military_budget", "nuclear_weapons",
    ]

    # Layer metadata
    layer_meta = {k: v for k, v in layers.items()}

    # Clear existing
    await session.execute(delete(IndicatorValue))
    await session.execute(delete(IndicatorDefinition))

    # Insert definitions
    definitions = []
    for col in indicator_columns:
        meta = layer_meta.get(col, {})
        defn = IndicatorDefinition(
            code=col,
            name=meta.get("name", col.replace("_", " ").title()),
            description=meta.get("description", ""),
            category=meta.get("category", ""),
            unit=meta.get("unit", ""),
            source=meta.get("source", "static"),
            source_url=meta.get("sourceUrl", ""),
            methodology=meta.get("methodology", ""),
            display_type=meta.get("type", "gradient"),
            categories=meta.get("categories"),
            gradient_stops=meta.get("stops"),
            sort_order=0,
        )
        definitions.append(defn)

    session.add_all(definitions)
    await session.flush()

    # Insert values (using 2024 as the year for static data)
    # Only insert values for countries that exist in the seeded set
    existing = (await session.execute(select(Country.iso3))).scalars().all()
    existing_set = set(existing)
    values = []
    for row in csv_data:
        iso3 = row.get("iso3", "")
        if not iso3 or iso3 not in existing_set:
            continue
        for col in indicator_columns:
            val_str = row.get(col, "").strip()
            if not val_str:
                continue
            try:
                val = float(val_str)
            except ValueError:
                continue
            iv = IndicatorValue(
                country_iso3=iso3,
                indicator_code=col,
                year=2024,
                value=val,
            )
            values.append(iv)

    session.add_all(values)
    await session.flush()
    print(f"  Seeded {len(definitions)} indicator definitions, {len(values)} values")


async def seed_alliances(session: AsyncSession) -> None:
    """Load alliances from JSON."""
    alliances_data = _parse_json(DATA_DIR / "alliances.json")

    existing = (await session.execute(select(Country.iso3))).scalars().all()
    existing_set = set(existing)

    await session.execute(delete(AllianceMember))
    await session.execute(delete(Alliance))

    alliances = []
    members = []

    for code, data in alliances_data.items():
        alliance = Alliance(
            code=code,
            name=data.get("name", ""),
            color=data.get("color", ""),
            founded=int(data["founded"]) if data.get("founded") else None,
            headquarters=data.get("headquarters", ""),
            info=data.get("info", ""),
            features=data.get("features", []),
        )
        alliances.append(alliance)
        session.add(alliance)

    await session.flush()

    for code, data in alliances_data.items():
        alliance = await session.execute(
            select(Alliance).where(Alliance.code == code)
        )
        alliance_obj = alliance.scalar_one()
        for member_iso3 in data.get("members", []):
            if member_iso3 not in existing_set:
                continue
            member = AllianceMember(
                alliance_id=alliance_obj.id,
                country_iso3=member_iso3,
            )
            members.append(member)

    session.add_all(members)
    await session.flush()
    print(f"  Seeded {len(alliances)} alliances, {len(members)} members")


async def seed_trade(session: AsyncSession) -> None:
    """Load trade data from JSON."""
    trade_data = _parse_json(DATA_DIR / "trade_data.json")

    existing = (await session.execute(select(Country.iso3))).scalars().all()
    existing_set = set(existing)

    await session.execute(delete(TradeFlow))

    flows = []
    for reporter_iso3, data in trade_data.items():
        if reporter_iso3 not in existing_set:
            continue
        partners = data.get("partners", [])
        for partner in partners:
            partner_iso3 = partner.get("iso3", "")
            if partner_iso3 not in existing_set:
                continue
            flow = TradeFlow(
                reporter_iso3=reporter_iso3,
                partner_iso3=partner_iso3,
                year=2024,
                export_value_usd=float(partner.get("export", 0) or 0),
                import_value_usd=float(partner.get("import", 0) or 0),
                export_categories=data.get("top_exports", []),
                import_categories=data.get("top_imports", []),
            )
            flows.append(flow)

    session.add_all(flows)
    await session.flush()
    print(f"  Seeded {len(flows)} trade flows")


async def seed_diplomacy(session: AsyncSession) -> None:
    """Load diplomatic relations from JSON."""
    diplomacy_data = _parse_json(DATA_DIR / "diplomacy.json")

    existing = (await session.execute(select(Country.iso3))).scalars().all()
    existing_set = set(existing)

    await session.execute(delete(DiplomaticRelation))

    relations = []
    for key, data in diplomacy_data.items():
        parts = key.split("_")
        if len(parts) != 2:
            continue
        iso3_a, iso3_b = parts
        if iso3_a not in existing_set or iso3_b not in existing_set:
            continue

        relation = DiplomaticRelation(
            country_iso3_a=iso3_a,
            country_iso3_b=iso3_b,
            summary=data.get("summary", ""),
            documents=data.get("relations", []),
        )
        relations.append(relation)

    session.add_all(relations)
    await session.flush()
    print(f"  Seeded {len(relations)} diplomatic relations")


async def run_seed(session: AsyncSession | None = None) -> None:
    """Run all seed operations.

    If session is provided, uses it (caller manages transaction).
    If session is None, creates its own session and transaction.
    """
    own_session = session is None
    if own_session:
        session = async_session_factory()

    try:
        if own_session:
            async with session.begin():
                await _do_seed(session)
        else:
            await _do_seed(session)
    finally:
        if own_session:
            await session.close()

    print("Database seed complete!")


async def seed_user(session: AsyncSession) -> None:
    """Create admin user if not exists."""
    result = await session.execute(
        select(User).where(User.email == "admin@example.com")
    )
    if result.scalar_one_or_none():
        print("  Admin user already exists")
        return

    admin = User(
        email="admin@example.com",
        username="admin",
        hashed_password=get_password_hash("admin123"),
        is_active=True,
        is_superuser=True,
        full_name="Administrator",
    )
    session.add(admin)
    await session.flush()
    print("  Created admin user: admin@example.com / admin123")


async def _do_seed(session: AsyncSession) -> None:
    """Internal seed logic — runs within an existing transaction."""
    print("Starting database seed...")
    # Delete dependent tables first (before countries), then re-seed in order
    await session.execute(delete(IndicatorValue))
    await session.execute(delete(IndicatorDefinition))
    await session.execute(delete(AllianceMember))
    await session.execute(delete(Alliance))
    await session.execute(delete(TradeFlow))
    await session.execute(delete(DiplomaticRelation))
    await session.flush()

    await seed_user(session)
    await seed_countries(session)
    await seed_indicators(session)
    await seed_alliances(session)
    await seed_trade(session)
    await seed_diplomacy(session)


if __name__ == "__main__":
    asyncio.run(run_seed())
