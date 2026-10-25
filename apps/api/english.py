"""English spellings of the free-text city and school names profiles hold (Uzbek Latin, as typed or picked from
apps.accounts.places). A name nobody mapped is returned as stored: it is the person's own text, not ours to guess."""
from apps.accounts import places

# the Uzbek spelling the profile stores -> the English one
CITIES = {
    "Toshkent": "Tashkent", "Buxoro": "Bukhara", "Samarqand": "Samarkand", "Andijon": "Andijan",
    "Farg‘ona": "Fergana", "Qo‘qon": "Kokand", "Marg‘ilon": "Margilan", "Urganch": "Urgench", "Xiva": "Khiva",
    "Qarshi": "Karshi", "Termiz": "Termez", "Jizzax": "Jizzakh", "Navoiy": "Navoi", "Guliston": "Gulistan",
    "Kogon": "Kagan", "G‘ijduvon": "Gijduvan", "Chirchiq": "Chirchik", "Olmaliq": "Almalyk", "Denov": "Denau",
    "Nukus": "Nukus", "Namangan": "Namangan", "Angren": "Angren", "Qorako‘l": "Karakul", "Shahrixon": "Shahrikhan",
    "Kobul": "Kabul", "Olot": "Olot", "Jondor": "Jondor", "Qorovulbozor": "Karaulbazar", "Vobkent": "Vobkent",
    "Shofirkon": "Shafirkan", "Peshku": "Peshku", "Romitan": "Romitan", "Toshkent shahri": "Tashkent city",
    "Toshkent viloyati": "Tashkent region", "Nurafshon": "Nurafshon", "Bekobod": "Bekabad",
    "Yangiyo‘l": "Yangiyul", "Ohangaron": "Akhangaran", "Zarafshon": "Zarafshan", "Muborak": "Mubarek",
    "Xorazm": "Khorezm", "Qashqadaryo": "Kashkadarya", "Surxondaryo": "Surkhandarya", "Sirdaryo": "Syrdarya",
    "Dubay": "Dubai", "Nyu-York": "New York", "Los-Anjeles": "Los Angeles", "Chikago": "Chicago",
    "Vashington": "Washington", "Moskva": "Moscow", "Istanbul": "Istanbul", "Qohira": "Cairo",
}
# the inverse of places.ALIASES covers every spelling the pickers know that is not listed above
for _country, _aliases in places.ALIASES.items():
    for _english, _uzbek in _aliases.items():
        if _english.isascii():
            CITIES.setdefault(_uzbek, _english.title())

SCHOOLS = {
    "Osiyo xalqaro universiteti": "Asia International University",
    "Toshkent axborot texnologiyalari universiteti (TATU)": "Tashkent University of Information Technologies (TUIT)",
    "O‘zbekiston Milliy universiteti": "National University of Uzbekistan",
    "Buxoro davlat universiteti": "Bukhara State University",
    "Buxoro muhandislik-texnologiya instituti": "Bukhara Engineering and Technology Institute",
    "Abu Ali ibn Sino nomidagi Buxoro davlat tibbiyot instituti": "Abu Ali ibn Sino Bukhara State Medical Institute",
    "Buxoro davlat pedagogika instituti": "Bukhara State Pedagogical Institute",
    "Buxoro xalqaro universiteti": "Bukhara International University",
    "Prezident maktabi": "Presidential School",
}


def city(name: str, lang: str) -> str | None:
    """The city in the API's language; None for nothing or for junk with no letters in it."""
    name = (name or "").strip()
    if not any(ch.isalpha() for ch in name):
        return None
    return CITIES.get(name, name) if lang == "en" else name


def school(name: str, lang: str) -> str | None:
    name = (name or "").strip()
    if not name:
        return None
    return SCHOOLS.get(name, name) if lang == "en" else name
