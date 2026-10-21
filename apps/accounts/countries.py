"""Countries for the profile, by ISO 3166-1 alpha-2 code, with their Uzbek names. Uzbekistan and its
neighbours come first in the picker (most users are from there), then every country by name."""
from django.utils.translation import gettext_lazy as _tl

COUNTRIES = {
    "UZ": _tl("O‘zbekiston"), "KZ": _tl("Qozog‘iston"), "KG": _tl("Qirg‘iziston"), "TJ": _tl("Tojikiston"), "TM": _tl("Turkmaniston"),
    "AF": _tl("Afg‘oniston"), "RU": _tl("Rossiya"), "TR": _tl("Turkiya"),
    "AL": _tl("Albaniya"), "DZ": _tl("Jazoir"), "AD": _tl("Andorra"), "AO": _tl("Angola"), "AG": _tl("Antigua va Barbuda"),
    "AR": _tl("Argentina"), "AM": _tl("Armaniston"), "AU": _tl("Avstraliya"), "AT": _tl("Avstriya"), "AZ": _tl("Ozarbayjon"),
    "BS": _tl("Bagama orollari"), "BH": _tl("Bahrayn"), "BD": _tl("Bangladesh"), "BB": _tl("Barbados"), "BY": _tl("Belarus"),
    "BE": _tl("Belgiya"), "BZ": _tl("Beliz"), "BJ": _tl("Benin"), "BT": _tl("Butan"), "BO": _tl("Boliviya"),
    "BA": _tl("Bosniya va Gersegovina"), "BW": _tl("Botsvana"), "BR": _tl("Braziliya"), "BN": _tl("Bruney"), "BG": _tl("Bolgariya"),
    "BF": _tl("Burkina-Faso"), "BI": _tl("Burundi"), "CV": _tl("Kabo-Verde"), "KH": _tl("Kambodja"), "CM": _tl("Kamerun"),
    "CA": _tl("Kanada"), "CF": _tl("Markaziy Afrika Respublikasi"), "TD": _tl("Chad"), "CL": _tl("Chili"), "CN": _tl("Xitoy"),
    "CO": _tl("Kolumbiya"), "KM": _tl("Komor orollari"), "CG": _tl("Kongo"), "CD": _tl("Kongo Demokratik Respublikasi"),
    "CR": _tl("Kosta-Rika"), "CI": _tl("Kot-d’Ivuar"), "HR": _tl("Xorvatiya"), "CU": _tl("Kuba"), "CY": _tl("Kipr"), "CZ": _tl("Chexiya"),
    "DK": _tl("Daniya"), "DJ": _tl("Jibuti"), "DM": _tl("Dominika"), "DO": _tl("Dominikan Respublikasi"), "EC": _tl("Ekvador"),
    "EG": _tl("Misr"), "SV": _tl("Salvador"), "GQ": _tl("Ekvatorial Gvineya"), "ER": _tl("Eritreya"), "EE": _tl("Estoniya"),
    "SZ": _tl("Esvatini"), "ET": _tl("Efiopiya"), "FJ": _tl("Fiji"), "FI": _tl("Finlandiya"), "FR": _tl("Fransiya"), "GA": _tl("Gabon"),
    "GM": _tl("Gambiya"), "GE": _tl("Gruziya"), "DE": _tl("Germaniya"), "GH": _tl("Gana"), "GR": _tl("Gretsiya"), "GD": _tl("Grenada"),
    "GT": _tl("Gvatemala"), "GN": _tl("Gvineya"), "GW": _tl("Gvineya-Bisau"), "GY": _tl("Gayana"), "HT": _tl("Gaiti"),
    "HN": _tl("Gonduras"), "HU": _tl("Vengriya"), "IS": _tl("Islandiya"), "IN": _tl("Hindiston"), "ID": _tl("Indoneziya"),
    "IR": _tl("Eron"), "IQ": _tl("Iroq"), "IE": _tl("Irlandiya"), "IL": _tl("Isroil"), "IT": _tl("Italiya"), "JM": _tl("Yamayka"),
    "JP": _tl("Yaponiya"), "JO": _tl("Iordaniya"), "KE": _tl("Keniya"), "KI": _tl("Kiribati"), "KW": _tl("Quvayt"), "LA": _tl("Laos"),
    "LV": _tl("Latviya"), "LB": _tl("Livan"), "LS": _tl("Lesoto"), "LR": _tl("Liberiya"), "LY": _tl("Liviya"), "LI": _tl("Lixtenshteyn"),
    "LT": _tl("Litva"), "LU": _tl("Lyuksemburg"), "MG": _tl("Madagaskar"), "MW": _tl("Malavi"), "MY": _tl("Malayziya"),
    "MV": _tl("Maldiv orollari"), "ML": _tl("Mali"), "MT": _tl("Malta"), "MH": _tl("Marshall orollari"), "MR": _tl("Mavritaniya"),
    "MU": _tl("Mavrikiy"), "MX": _tl("Meksika"), "FM": _tl("Mikroneziya"), "MD": _tl("Moldova"), "MC": _tl("Monako"),
    "MN": _tl("Mo‘g‘uliston"), "ME": _tl("Chernogoriya"), "MA": _tl("Marokash"), "MZ": _tl("Mozambik"), "MM": _tl("Myanma"),
    "NA": _tl("Namibiya"), "NR": _tl("Nauru"), "NP": _tl("Nepal"), "NL": _tl("Niderlandiya"), "NZ": _tl("Yangi Zelandiya"),
    "NI": _tl("Nikaragua"), "NE": _tl("Niger"), "NG": _tl("Nigeriya"), "KP": _tl("Shimoliy Koreya"), "MK": _tl("Shimoliy Makedoniya"),
    "NO": _tl("Norvegiya"), "OM": _tl("Ummon"), "PK": _tl("Pokiston"), "PW": _tl("Palau"), "PS": _tl("Falastin"), "PA": _tl("Panama"),
    "PG": _tl("Papua – Yangi Gvineya"), "PY": _tl("Paragvay"), "PE": _tl("Peru"), "PH": _tl("Filippin"), "PL": _tl("Polsha"),
    "PT": _tl("Portugaliya"), "QA": _tl("Qatar"), "RO": _tl("Ruminiya"), "RW": _tl("Ruanda"), "KN": _tl("Sent-Kits va Nevis"),
    "LC": _tl("Sent-Lyusiya"), "VC": _tl("Sent-Vinsent va Grenadin"), "WS": _tl("Samoa"), "SM": _tl("San-Marino"),
    "ST": _tl("San-Tome va Prinsipi"), "SA": _tl("Saudiya Arabistoni"), "SN": _tl("Senegal"), "RS": _tl("Serbiya"),
    "SC": _tl("Seyshel orollari"), "SL": _tl("Syerra-Leone"), "SG": _tl("Singapur"), "SK": _tl("Slovakiya"), "SI": _tl("Sloveniya"),
    "SB": _tl("Solomon orollari"), "SO": _tl("Somali"), "ZA": _tl("Janubiy Afrika"), "KR": _tl("Janubiy Koreya"),
    "SS": _tl("Janubiy Sudan"), "ES": _tl("Ispaniya"), "LK": _tl("Shri-Lanka"), "SD": _tl("Sudan"), "SR": _tl("Surinam"),
    "SE": _tl("Shvetsiya"), "CH": _tl("Shveytsariya"), "SY": _tl("Suriya"), "TW": _tl("Tayvan"), "TZ": _tl("Tanzaniya"),
    "TH": _tl("Tailand"), "TL": _tl("Sharqiy Timor"), "TG": _tl("Togo"), "TO": _tl("Tonga"), "TT": _tl("Trinidad va Tobago"),
    "TN": _tl("Tunis"), "TV": _tl("Tuvalu"), "UG": _tl("Uganda"), "UA": _tl("Ukraina"), "AE": _tl("Birlashgan Arab Amirliklari"),
    "GB": _tl("Buyuk Britaniya"), "US": _tl("AQSH"), "UY": _tl("Urugvay"), "VU": _tl("Vanuatu"), "VA": _tl("Vatikan"),
    "VE": _tl("Venesuela"), "VN": _tl("Vyetnam"), "YE": _tl("Yaman"), "ZM": _tl("Zambiya"), "ZW": _tl("Zimbabve"),
}

_FIRST = 8  # Uzbekistan and the region lead the list; the rest follow by name

COUNTRY_CHOICES = list(COUNTRIES.items())[:_FIRST] + sorted(list(COUNTRIES.items())[_FIRST:], key=lambda kv: kv[1])


def country_name(code: str) -> str:
    return str(COUNTRIES.get(code, ""))
