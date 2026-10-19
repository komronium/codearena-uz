"""Cities and schools the profile offers as choices, by country. A country without a list falls back to a text
box (the form accepts any text, these lists only drive the pickers and tidy up spellings).

CITIES[code] is a list of (group, [city, ...]); the group is a region shown as the picker's heading.
SCHOOLS[code][city] is the list of institutions in that city. Add to these when a student cannot find theirs;
"Boshqa…" in the picker lets them write it meanwhile."""

import re

OTHER = "__other__"  # the picker value that means "I'll write it myself"

CITIES = {
    "UZ": [
        ("Toshkent shahri", ["Toshkent"]),
        ("Toshkent viloyati", ["Nurafshon", "Chirchiq", "Angren", "Olmaliq", "Bekobod", "Ohangaron", "Yangiyo‘l",
                               "Piskent", "Parkent"]),
        ("Andijon viloyati", ["Andijon", "Asaka", "Xonobod", "Shahrixon", "Marhamat", "Xo‘jaobod", "Qo‘rg‘ontepa",
                              "Paxtaobod"]),
        ("Buxoro viloyati", ["Buxoro", "Kogon", "G‘ijduvon", "Vobkent", "Qorako‘l", "Romitan", "Shofirkon", "Jondor",
                             "Olot", "Peshku"]),
        ("Farg‘ona viloyati", ["Farg‘ona", "Marg‘ilon", "Qo‘qon", "Quvasoy", "Rishton", "Oltiariq", "Beshariq", "Quva",
                               "Bag‘dod", "Uchko‘prik", "Toshloq"]),
        ("Jizzax viloyati", ["Jizzax", "Zomin", "Forish", "G‘allaorol", "Do‘stlik", "Paxtakor"]),
        ("Xorazm viloyati", ["Urganch", "Xiva", "Xonqa", "Shovot", "Pitnak", "Hazorasp", "Bog‘ot", "Gurlan",
                             "Yangiariq", "Yangibozor"]),
        ("Namangan viloyati", ["Namangan", "Chust", "Pop", "Kosonsoy", "Uychi", "Chortoq", "Mingbuloq",
                               "To‘raqo‘rg‘on", "Davlatobod", "Uchqo‘rg‘on"]),
        ("Navoiy viloyati", ["Navoiy", "Zarafshon", "Uchquduq", "Nurota", "Konimex", "Karmana", "Xatirchi", "Tomdi",
                             "Qiziltepa"]),
        ("Qashqadaryo viloyati", ["Qarshi", "Shahrisabz", "Kitob", "G‘uzor", "Koson", "Muborak", "Yakkabog‘",
                                  "Chiroqchi", "Dehqonobod", "Qamashi"]),
        ("Qoraqalpog‘iston", ["Nukus", "Xo‘jayli", "Qo‘ng‘irot", "To‘rtko‘l", "Beruniy", "Mo‘ynoq", "Chimboy",
                              "Qorao‘zak", "Kegeyli", "Taxtako‘pir", "Amudaryo"]),
        ("Samarqand viloyati", ["Samarqand", "Kattaqo‘rg‘on", "Urgut", "Bulung‘ur", "Jomboy", "Ishtixon", "Nurobod",
                                "Oqdaryo", "Pastdarg‘om", "Payariq", "Narpay"]),
        ("Sirdaryo viloyati", ["Guliston", "Sirdaryo", "Yangiyer", "Shirin", "Boyovut", "Sardoba", "Xovos", "Oqoltin",
                               "Mirzaobod"]),
        ("Surxondaryo viloyati", ["Termiz", "Denov", "Sherobod", "Boysun", "Sho‘rchi", "Qumqo‘rg‘on", "Angor",
                                  "Jarqo‘rg‘on", "Uzun", "Oltinsoy"]),
    ],
    "KZ": [(None, ["Ostona", "Almati", "Shimkent", "Qorag‘anda", "Aqtobe", "Toraz", "Pavlodar", "Ust-Kamenogorsk",
                   "Semey", "Atyrau", "Qostanay", "Qizilo‘rda", "Oral", "Petropavl", "Aqtau", "Turkiston"])],
    "KG": [(None, ["Bishkek", "Osh", "Jalolobod", "Tokmok", "Qorako‘l", "Norin", "Talas", "Batken"])],
    "TJ": [(None, ["Dushanbe", "Xo‘jand", "Kulob", "Bokhtar", "Istaravshan", "Panjakent", "Xorog‘"])],
    "TM": [(None, ["Ashxobod", "Turkmenobod", "Dashog‘uz", "Mari", "Balkanobod", "Turkmanboshi"])],
    "AF": [(None, ["Kobul", "Qandahor", "Hirot", "Mozori Sharif"])],
    "RU": [(None, ["Moskva", "Sankt-Peterburg", "Novosibirsk", "Yekaterinburg", "Qozon", "Nijniy Novgorod",
                   "Chelyabinsk", "Samara", "Omsk", "Rostov-na-Donu", "Ufa", "Krasnoyarsk", "Voronej", "Perm",
                   "Volgograd", "Krasnodar"])],
    "TR": [(None, ["Istanbul", "Ankara", "Izmir", "Bursa", "Antalya", "Konya", "Adana", "Gaziantep", "Kayseri"])],
    "AZ": [(None, ["Boku", "Gyanja", "Sumqayit", "Mingachevir", "Shaki", "Lankaran"])],
    "KR": [(None, ["Seul", "Busan", "Incheon", "Daegu", "Daejeon", "Gwangju", "Suwon"])],
    "DE": [(None, ["Berlin", "Gamburg", "Myunxen", "Kyoln", "Frankfurt", "Shtutgart", "Dyusseldorf", "Drezden"])],
    "GB": [(None, ["London", "Birmingem", "Manchester", "Liverpul", "Edinburg", "Glazgo", "Bristol", "Lids"])],
    "US": [(None, ["Nyu-York", "Los-Anjeles", "Chikago", "Xyuston", "San-Fransisko", "Boston", "Vashington",
                   "Sietl", "Mayami"])],
    "AE": [(None, ["Dubay", "Abu-Dabi", "Sharja", "Ajman"])],
}

# English and Russian-style spellings people typed, to the list's spelling
ALIASES = {
    "UZ": {
        "tashkent": "Toshkent", "ташкент": "Toshkent", "bukhara": "Buxoro", "бухара": "Buxoro",
        "samarkand": "Samarqand", "самарканд": "Samarqand", "andijan": "Andijon", "fergana": "Farg‘ona",
        "ferghana": "Farg‘ona", "kokand": "Qo‘qon", "margilan": "Marg‘ilon", "urgench": "Urganch",
        "khiva": "Xiva", "karshi": "Qarshi", "termez": "Termiz", "jizzakh": "Jizzax", "navoi": "Navoiy",
        "gulistan": "Guliston", "kagan": "Kogon", "gijduvan": "G‘ijduvon", "chirchik": "Chirchiq",
        "angren": "Angren", "almalyk": "Olmaliq", "denau": "Denov", "shahrisabz": "Shahrisabz",
    },
}

SCHOOLS = {
    "UZ": {
        "Toshkent": [
            "O‘zbekiston Milliy universiteti", "Toshkent axborot texnologiyalari universiteti (TATU)",
            "Toshkent davlat texnika universiteti", "Inha universiteti (Toshkent)",
            "Westminster xalqaro universiteti (Toshkent)", "Turin politexnika universiteti (Toshkent)",
            "Toshkent davlat iqtisodiyot universiteti", "Toshkent davlat yuridik universiteti",
            "Toshkent moliya instituti", "Toshkent tibbiyot akademiyasi", "Toshkent arxitektura-qurilish universiteti",
            "Toshkent davlat pedagogika universiteti", "O‘zbekiston davlat jahon tillari universiteti",
            "Toshkent davlat sharqshunoslik universiteti", "Toshkent kimyo-texnologiya instituti",
            "Toshkent to‘qimachilik va yengil sanoat instituti", "Amity University Tashkent",
            "Webster University Tashkent", "Prezident maktabi",
        ],
        "Buxoro": [
            "Osiyo xalqaro universiteti", "Buxoro davlat universiteti", "Buxoro muhandislik-texnologiya instituti",
            "Abu Ali ibn Sino nomidagi Buxoro davlat tibbiyot instituti", "Buxoro davlat pedagogika instituti",
            "Buxoro xalqaro universiteti", "Prezident maktabi",
        ],
        "Samarqand": [
            "Samarqand davlat universiteti", "Samarqand davlat tibbiyot universiteti",
            "Samarqand davlat arxitektura-qurilish universiteti", "Samarqand davlat chet tillar instituti",
            "Samarqand iqtisodiyot va servis instituti", "Samarqand veterinariya meditsinasi instituti",
            "TATU Samarqand filiali",
        ],
        "Andijon": [
            "Andijon davlat universiteti", "Andijon davlat tibbiyot instituti", "Andijon mashinasozlik instituti",
            "Andijon davlat pedagogika instituti", "Andijon qishloq xo‘jaligi va agrotexnologiyalar instituti",
        ],
        "Farg‘ona": ["Farg‘ona davlat universiteti", "Farg‘ona politexnika instituti", "TATU Farg‘ona filiali"],
        "Namangan": ["Namangan davlat universiteti", "Namangan muhandislik-qurilish instituti",
                     "Namangan muhandislik-texnologiya instituti"],
        "Qarshi": ["Qarshi davlat universiteti", "Qarshi muhandislik-iqtisodiyot instituti", "TATU Qarshi filiali"],
        "Termiz": ["Termiz davlat universiteti", "Termiz muhandislik-texnologiya instituti"],
        "Urganch": ["Urganch davlat universiteti", "TATU Urganch filiali"],
        "Navoiy": ["Navoiy davlat universiteti", "Navoiy davlat konchilik va texnologiyalar universiteti"],
        "Jizzax": ["Jizzax politexnika instituti", "Jizzax davlat pedagogika universiteti"],
        "Guliston": ["Guliston davlat universiteti"],
        "Nukus": ["Qoraqalpoq davlat universiteti", "Nukus davlat pedagogika instituti", "TATU Nukus filiali"],
    },
}

# old free-text spellings of an institution, by a distinctive word, to its list name (first match wins)
_SCHOOL_HINTS = {
    # "OXU", "osiyo ...", or the group code "ATT" (also "OXU_2-ATT-25", "att 2- kurs", "ATT25"): letters, not
    # digits or underscores, bound the word
    "UZ": [(r"(?<![a-z])(oxu|att)(?![a-z])|osiyo", "Osiyo xalqaro universiteti")],
}


def _key(text: str) -> str:
    """Lower-case, apostrophes and spaces dropped, so "Qo‘qon", "Qo'qon" and "qoqon" meet."""
    return re.sub(r"[\s‘’ʻʼ'`´.\-]+", "", (text or "").lower())


def _city_index(country: str) -> dict:
    index = {_key(c): c for _, cities in CITIES.get(country, []) for c in cities}
    index.update({_key(a): c for a, c in ALIASES.get(country, {}).items()})
    return index


def canon_city(country: str, text: str) -> str:
    """The list's spelling of a typed city, else the text as given (trimmed)."""
    text = (text or "").strip()
    return _city_index(country).get(_key(text), text)


def canon_school(country: str, text: str) -> str:
    """The list's name for an institution typed as free text ("oxu 2-ATT-25" -> Osiyo xalqaro universiteti);
    what cannot be recognised stays as typed."""
    text = (text or "").strip()
    names = {_key(s): s for by_city in SCHOOLS.get(country, {}).values() for s in by_city}
    if _key(text) in names:
        return names[_key(text)]
    for pattern, name in _SCHOOL_HINTS.get(country, []):
        if re.search(pattern, text.lower()):
            return name
    return text


def payload() -> dict:
    """What the pickers' script needs: {"cities": {code: [[group, [city, ...]], ...]}, "schools": {code: {city: [...]}}}."""
    return {"cities": CITIES, "schools": SCHOOLS, "other": OTHER}
