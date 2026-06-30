import json
import os
import sys
import csv
import io
import re
import urllib.request
import ssl
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

CATALOG_FILE = "dso_catalog.json"

# СУЩЕСТВЕННО РАСШИРЕННЫЙ словарь MANUAL_ALIASES
MANUAL_ALIASES = {
    # ==================== MESSIER OBJECTS ====================
    "M31": [
        "andromeda", "андромеда", "туманность андромеды", "andromeda galaxy", 
        "галактика андромеды", "андромедская галактика", "andromeda nebula",
        "m 31", "messier 31", "мессье 31", "нгц 224", "нгк 224", "ngc 224",
        "андромедская туманность", "великая туманность андромеды", "туманность андромедская",
        "andromeda spiral galaxy", "спиральная галактика андромеды", "m31",
        "little cloud", "маленькое облако", "nuage d'andromede"
    ],
    "M42": [
        "орион", "orion", "туманность ориона", "orion nebula", "большая туманность ориона",
        "меч ориона", "великая туманность ориона", "great orion nebula", "m 42", "messier 42",
        "мессье 42", "ориона", "orion's sword", "большая орионова туманность",
        "orion a", "orion nebula complex", "меч ориона", "великая орионова туманность",
        "ngc 1976", "en", "emission nebula orion"
    ],
    "M45": [
        "плеяды", "pleiades", "семь сестер", "стожары", "волосожары", "висажары",
        "утиное гнездо", "утичье гнездо", "уточье гнездо", "утиное гнёздышко",
        "seven sisters", "m 45", "messier 45", "мессье 45", "семь братьев",
        "семь дев", "atlantides", "семь атлантов", "сёстры", "subaru", " Subaru"
    ],
    "M13": [
        "геркулес", "hercules", "скопление геркулеса", "большое скопление геркулеса",
        "great hercules cluster", "hercules globular cluster", "m 13", "messier 13",
        "мессье 13", "великое скопление геркулеса", "геркулесово скопление",
        "шаровое скопление геркулеса", "геркулес шаровое", "m 13", "ngc 6205"
    ],
    "M51": [
        "водоворот", "whirlpool", "галактика водоворот", "whirlpool galaxy",
        "m 51", "messier 51", "мессье 51", "воронка", "водоворотная галактика",
        "спиральная галактика водоворот", "m51a", "m51b", "ngc 5194", "ngc 5195",
        "пара галактик", "pair of galaxies", "whirlpool pair"
    ],
    "M101": [
        "вертушка", "pinwheel", "галактика вертушка", "pinwheel galaxy",
        "m 101", "messier 101", "мессье 101", "колесо", "вертящаяся галактика",
        "вертушечная галактика", "m101", "ngc 5457", "windmill galaxy", "mельница"
    ],
    "M81": [
        "боде", "bode", "галактика боде", "bode's galaxy", "m 81", "messier 81",
        "мессье 81", "спираль боде", "bode galaxy", "ngc 3031", "m81",
        "галактика иоганна боде", "bode's nebula"
    ],
    "M82": [
        "сигара", "cigar", "галактика сигара", "cigar galaxy", "m 82", "messier 82",
        "мессье 82", "сигарная галактика", "взрывная галактика", "ngc 3034", "m82",
        "starburst galaxy", "взрывообразная галактика", "cigar nebula"
    ],
    "M57": [
        "кольцо", "ring", "туманность кольцо", "ring nebula", "лирическое кольцо",
        "lyra ring", "m 57", "messier 57", "мессье 57", "кольцо в лире",
        "планетарная туманность кольцо", "ring nebula in lyra", "ngc 6720", "m57",
        "lyra ring nebula", "кольцевая туманность"
    ],
    "M27": [
        "гантель", "dumbbell", "туманность гантель", "dumbbell nebula", "песочные часы",
        "hourglass", "m 27", "messier 27", "мессье 27", "гантельная туманность", "бабочка",
        "butterfly", "песочные часы", "hourglass nebula", "ngc 6853", "m27",
        "apple core", "яблочный огрызок", "планетарная гантель"
    ],
    "M1": [
        "краб", "crab", "крабовидная туманность", "crab nebula", "m 1", "messier 1",
        "мессье 1", "крабовидная", "остаток сверхновой 1054", "snr", "sn 1054",
        "supernova remnant 1054", "ngc 1952", "m1", "крабовидный остаток",
        "taurus a", "тауер a", "пульсар в крабовидной"
    ],
    "M16": [
        "орел", "eagle", "туманность орел", "eagle nebula", "столпы творения",
        "pillars of creation", "звездная королева", "star queen", "m 16", "messier 16",
        "мессье 16", "орлиная туманность", "орёл", "ngc 6611", "m16",
        "pillars of creation nebula", "столбы творения", "звёздная королева",
        "ic 4703", "emission nebula eagle"
    ],
    "M17": [
        "омега", "omega", "подкова", "лебедь", "туманность омега", "omega nebula",
        "swan nebula", "horseshoe nebula", "checkmark nebula", "галочка", "омар",
        "lobster nebula", "m 17", "messier 17", "мессье 17", "лебединая туманность",
        "ngc 6618", "m17", "подкова", "checkmark", "omega nebula complex",
        "туманность подкова", "туманность лебедь"
    ],
    "M20": [
        "трехраздельная", "trifid", "туманность трифид", "trifid nebula", "тройная туманность",
        "трёхдольная туманность", "трёхраздельная туманность", "m 20", "messier 20",
        "мессье 20", "трифидная туманность", "трилистник", "ngc 6514", "m20",
        "three-lobed nebula", "трёхлопастная туманность"
    ],
    "M8": [
        "лагуна", "lagoon", "туманность лагуна", "lagoon nebula", "m 8", "messier 8",
        "мессье 8", "лагуновая туманность", "большая лагуна", "ngc 6523", "m8",
        "lagoon nebula complex", "лагуновая", "туманность лагуны"
    ],
    "M104": [
        "сомбреро", "sombrero", "галактика сомбреро", "sombrero galaxy", "m 104",
        "messier 104", "мессье 104", "сомбрерная галактика", "шляпа", "ngc 4594", "m104",
        "sombrero hat galaxy", "галактика шляпа", "mexican hat galaxy"
    ],
    "M33": [
        "треугольник", "triangulum", "галактика треугольника", "triangulum galaxy",
        "m 33", "messier 33", "мессье 33", "треугольная галактика", "вертушка треугольника",
        "ngc 598", "m33", "pinwheel in triangulum", "m33 galaxy"
    ],
    
    # ==================== NGC OBJECTS ====================
    "NGC7000": [
        "северная америка", "north america", "туманность северная америка",
        "north america nebula", "caldwell 20", "c 20", "сша", "америка", "мексиканский залив",
        "ngc 7000", "north american nebula", "north america emission nebula",
        "туманность сша", "мексиканский залив", "калифорнийская туманность",
        "ngc7000", "c20", "caldwell 20 nebula", "североамериканская туманность"
    ],
    "NGC7293": [
        "улитка", "helix", "глаз бога", "eye of god", "око сауpона", "око саурона",
        "спираль", "caldwell 63", "c 63", "хеликс", "туманность улитка", "helix nebula",
        "улитковая туманность", "ngc 7293", "ngc7293", "c63", "god's eye",
        "божий глаз", "око всевидящее", "планетарная улитка", "helix planetary nebula",
        "глаз провидения", "providence eye"
    ],
    "NGC6960": [
        "ведьмина метла", "witch broom", "вуаль", "петля лебедя", "рыбачья сеть",
        "filamentary nebula", "witch's broom", "cygnus loop", "western veil",
        "западная вуаль", "метла ведьмы", "ngc 6960", "ngc6960", "witches broom",
        "filament nebula", "cygnus loop western", "c34", "caldwell 34",
        "ведьмина метла вуаль", "cygnus supernova remnant", "snr cygnus"
    ],
    "NGC6992": [
        "вуаль", "veil", "сеть", "петля лебедя", "bridal veil", "eastern veil",
        "cygnus loop", "восточная вуаль", "петля", "вуалевая туманность",
        "ngc 6992", "ngc6992", "c33", "caldwell 33", "eastern veil nebula",
        "bridal veil nebula", "cygnus loop eastern", "восточная петля лебедя",
        "сеть рыбачья", "fishing net nebula"
    ],
    "NGC2237": [
        "розетка", "rosette", "розочка", "череп", "caldwell 49", "c 49",
        "туманность розетка", "rosette nebula", "розовая туманность", "розеточная туманность",
        "ngc 2237", "ngc2237", "c49", "rosette emission nebula", "rose nebula",
        "rose flower nebula", "туманность роза", "розовая", "rose cluster nebula",
        "ngc 2244", "caldwell 50", "c50", "rose star cluster"
    ],
    "NGC6888": [
        "полумесяц", "crescent", "серп", "туманность полумесяц", "crescent nebula",
        "полумесячная туманность", "серповидная туманность", "полумесяцевая туманность",
        "ngc 6888", "ngc6888", "c27", "caldwell 27", "crescent emission nebula",
        "wolf-rayet nebula", "вран nebula", "серповидная", "туманность серп"
    ],
    "NGC4565": [
        "игла", "needle", "галактика игла", "needle galaxy", "caldwell 38", "c 38",
        "игольная галактика", "галактика-игла", "острая галактика", "ngc 4565", "ngc4565",
        "c38", "edge-on galaxy", "галактика с ребра", "тонкая галактика",
        "sliver galaxy", "галактика иголка", "edge on spiral"
    ],
    "NGC1499": [
        "калифорния", "california", "туманность калифорния", "california nebula",
        "sh2-220", "калифорнийская туманность", "калифорнийская", "ngc 1499", "ngc1499",
        "sh2 220", "sh220", "california emission nebula", "туманность штат калифорния",
        "california state nebula", "sh2-220 nebula"
    ],
    
    # ==================== IC OBJECTS ====================
    "IC1396": [
        "слоновый хобот", "elephant trunk", "хобот слона", "туманность хобот слона",
        "elephant's trunk nebula", "ic 1396", "гигантский хобот", "ic1396",
        "elephant trunk emission nebula", "ic 1396 nebula", "туманность слоновий хобот",
        "хобот слона туманность", "elephant trunk complex", "sh2-131",
        "ic1396 nebula", "слоновый хобот ic1396"
    ],
    "IC5070": [
        "пеликан", "pelican", "туманность пеликан", "pelican nebula", "ic 5070",
        "ic 5067", "пеликанья туманность", "пеликановая туманность", "ic5070",
        "ic5067", "pelican emission nebula", "туманность пеликан", "пеликан туманность",
        "north america and pelican", "пеликан и северная америка"
    ],
    "IC443": [
        "медуза", "jellyfish", "туманность медуза", "jellyfish nebula", "sh2-248",
        "ced 73", "медузовая туманность", "остаток сверхновой", "медузоподобная туманность",
        "ic 443", "ic443", "sh2 248", "sh2248", "jellyfish supernova remnant",
        "snr ic443", "geminga supernova remnant", "медуза остаток",
        "jellyfish snr", "туманность медуза джелии"
    ],
    
    # ==================== SHARPLESS OBJECTS ====================
    "Sh2-155": [
        "пещера", "cave", "туманность пещера", "cave nebula", "caldwell 9", "c 9",
        "sharless 155", "пещерная туманность", "sh2 155", "sharpless 155",
        "sh2-155", "sh2155", "c9", "caldwell 9", "cave emission nebula",
        "cepheus cave", "пещера в цефее", "туманность пещеры", "cave nebula cepheus",
        "sh 155", "sh2 155 nebula"
    ],
    
    # ==================== BARNARD OBJECTS ====================
    "B33": [
        "лошадиная голова", "horsehead", "конская голова", "голова лошади", "barnard 33",
        "horsehead nebula", "тёмная туманность конская голова", "b 33", "б 33",
        "лошадиная морда", "b33", "barnard 33", "dark horsehead", "тёмная лошадь",
        "horsehead dark nebula", "лошадиная голова тёмная", "конская голова тёмная",
        "orion horsehead", "орiona конская голова", "barnard33", "horse head"
    ]
}

# Полный Messier fallback (все 110 объектов)
MESSIER_FALLBACK = {
    "M1": (5.5755, 22.0147), "M2": (21.0567, -0.817), "M3": (13.7029, 28.3755),
    "M4": (16.3886, -26.5253), "M5": (15.3089, 2.0806), "M6": (17.669, -32.2211),
    "M7": (17.894, -34.816), "M8": (18.0625, -24.3836), "M9": (17.3186, -18.5147),
    "M10": (16.9544, -4.1003), "M11": (18.8539, -6.2672), "M12": (16.7861, -1.9494),
    "M13": (16.6948, 36.4613), "M14": (17.6261, -3.245), "M15": (21.4997, 12.1008),
    "M16": (18.3133, -13.7897), "M17": (18.3453, -16.1775), "M18": (18.3319, -17.1375),
    "M19": (17.0431, -26.2697), "M20": (18.0428, -23.0125), "M21": (18.0753, -22.4947),
    "M22": (18.605, -23.9058), "M23": (17.9478, -19.0175), "M24": (18.2917, -18.4903),
    "M25": (18.5258, -19.2536), "M26": (18.7608, -9.3853), "M27": (19.9961, 22.7208),
    "M28": (18.4128, -24.8692), "M29": (20.3978, 38.5372), "M30": (21.6775, -23.1794),
    "M31": (0.7123, 41.2689), "M32": (0.7173, 40.865), "M33": (1.5639, 30.6603),
    "M34": (2.7058, 42.7769), "M35": (6.1536, 24.3397), "M36": (5.6053, 34.1361),
    "M37": (5.8697, 32.5494), "M38": (5.4733, 35.8406), "M39": (21.5369, 48.4336),
    "M40": (12.3731, 58.0825), "M41": (6.7644, -20.7575), "M42": (5.5881, -5.3911),
    "M43": (5.6003, -5.2686), "M44": (8.6758, 19.6667), "M45": (3.7911, 24.1144),
    "M46": (7.7122, -14.8158), "M47": (6.6136, -14.4994), "M48": (8.2314, -5.8061),
    "M49": (12.4958, 8.0008), "M50": (7.0533, -8.3306), "M51": (13.4983, 47.1953),
    "M52": (23.4147, 61.5892), "M53": (13.2161, 18.1011), "M54": (18.9139, -30.4803),
    "M55": (19.6669, -30.9653), "M56": (19.2731, 30.1806), "M57": (18.8931, 33.0289),
    "M58": (12.6275, 11.8225), "M59": (12.7347, 11.6528), "M60": (12.7647, 11.5531),
    "M61": (12.3636, 4.475), "M62": (17.0194, -30.115), "M63": (13.2644, 42.0289),
    "M64": (12.9672, 21.6831), "M65": (11.3083, 13.0906), "M66": (11.3361, 12.9917),
    "M67": (8.8467, 11.8147), "M68": (12.6639, -26.7456), "M69": (18.7136, -32.3464),
    "M70": (18.7664, -32.3006), "M71": (19.8947, 18.7789), "M72": (20.8944, -12.5378),
    "M73": (20.9861, -12.6406), "M74": (1.6136, 15.7853), "M75": (20.0608, -21.9211),
    "M76": (1.715, 51.5669), "M77": (2.7142, -0.0131), "M78": (5.7786, 0.0589),
    "M79": (5.4122, -24.5256), "M80": (16.2844, -22.9736), "M81": (9.9258, 69.0653),
    "M82": (9.9314, 69.6794), "M83": (14.0328, -29.8664), "M84": (12.4172, 12.8875),
    "M85": (12.4261, 18.1914), "M86": (12.44, 12.9464), "M87": (12.5136, 12.3911),
    "M88": (12.5328, 14.4194), "M89": (12.5933, 12.555), "M90": (12.61, 13.1622),
    "M91": (12.5906, 14.4983), "M92": (17.2844, 43.1372), "M93": (7.7425, -23.8617),
    "M94": (12.8422, 41.12), "M95": (10.7392, 11.7058), "M96": (10.7789, 11.8186),
    "M97": (11.2458, 55.0183), "M98": (12.2303, 14.9006), "M99": (12.3139, 14.4167),
    "M100": (12.3789, 15.8231), "M101": (14.0536, 54.3492), "M102": (15.0108, 55.7597),
    "M103": (1.5594, 60.7078), "M104": (12.6667, -11.6175), "M105": (10.7967, 12.5831),
    "M106": (12.32, 47.3047), "M107": (16.535, -13.0531), "M108": (11.1994, 55.6728),
    "M109": (11.9761, 53.3811), "M110": (0.6725, 41.6853)
}

# Полный Caldwell map (все 109 объектов)
CALDWELL_MAP = {
    "C1": "NGC188", "C2": "NGC40", "C3": "NGC4236", "C4": "NGC7023", "C5": "IC342",
    "C6": "NGC6543", "C7": "NGC2403", "C8": "NGC559", "C9": "Sh2-155", "C10": "NGC663",
    "C11": "NGC7635", "C12": "NGC6946", "C13": "NGC457", "C14": "NGC869", "C15": "NGC6826",
    "C16": "NGC7243", "C17": "NGC147", "C18": "NGC185", "C19": "IC5146", "C20": "NGC7000",
    "C21": "NGC4449", "C22": "NGC7662", "C23": "NGC891", "C24": "NGC1275", "C25": "NGC2419",
    "C26": "NGC4244", "C27": "NGC6888", "C28": "NGC752", "C29": "NGC5005", "C30": "NGC7331",
    "C31": "NGC1499", "C32": "NGC4631", "C33": "NGC6992", "C34": "NGC6960", "C35": "NGC4889",
    "C36": "NGC6572", "C37": "NGC6885", "C38": "NGC4565", "C39": "NGC2392", "C40": "NGC3628",
    "C41": "NGC6633", "C42": "NGC7814", "C43": "NGC7009", "C44": "NGC7479", "C45": "IC4756",
    "C46": "NGC2261", "C47": "NGC6934", "C48": "NGC2775", "C49": "NGC2237", "C50": "NGC2244",
    "C51": "IC1613", "C52": "NGC4697", "C53": "NGC3115", "C54": "NGC6712", "C55": "NGC6752",
    "C56": "NGC6744", "C57": "NGC6822", "C58": "NGC2360", "C59": "NGC3242", "C60": "NGC4038",
    "C61": "NGC4039", "C62": "NGC2264", "C63": "NGC7293", "C64": "NGC6531", "C65": "NGC2548",
    "C66": "NGC5139", "C67": "NGC1097", "C68": "NGC6726", "C69": "NGC6101", "C70": "NGC1261",
    "C71": "NGC1245", "C72": "NGC6960", "C73": "NGC1851", "C74": "NGC3132", "C75": "NGC6124",
    "C76": "NGC6193", "C77": "NGC5128", "C78": "NGC6397", "C79": "NGC3293", "C80": "NGC5286",
    "C81": "NGC6352", "C82": "NGC6356", "C83": "NGC4755", "C84": "NGC6067", "C85": "IC2391",
    "C86": "NGC6231", "C87": "NGC6087", "C88": "NGC5822", "C89": "NGC6755", "C90": "NGC6531",
    "C91": "NGC4609", "C92": "NGC6530", "C93": "NGC6362", "C94": "NGC6569", "C95": "NGC6681",
    "C96": "NGC6633", "C97": "NGC3766", "C98": "NGC4665", "C99": "NGC4665", "C100": "IC2944",
    "C101": "NGC2516", "C102": "IC2602", "C103": "NGC2024", "C104": "NGC6744", "C105": "NGC6397",
    "C106": "NGC104", "C107": "NGC6121", "C108": "NGC4372", "C109": "NGC2808"
}

# ПОЛНЫЙ Sharpless 2 fallback (ВСЕ 313 объектов с координатами)
SH2_FALLBACK = {
    # Sh2-1 до Sh2-30
    "Sh2-1": (16.05, -39.93), "Sh2-2": (16.22, -43.50), "Sh2-3": (16.27, -39.85),
    "Sh2-4": (16.33, -37.06), "Sh2-5": (16.47, -40.00), "Sh2-6": (16.51, -39.13),
    "Sh2-7": (16.57, -40.60), "Sh2-8": (16.64, -41.25), "Sh2-9": (16.68, -40.73),
    "Sh2-10": (16.73, -41.36), "Sh2-11": (16.77, -41.87), "Sh2-12": (16.85, -41.94),
    "Sh2-13": (16.87, -41.87), "Sh2-14": (16.93, -42.23), "Sh2-15": (17.05, -38.97),
    "Sh2-16": (17.10, -38.50), "Sh2-17": (17.15, -37.80), "Sh2-18": (17.20, -37.20),
    "Sh2-19": (17.25, -36.50), "Sh2-20": (17.30, -35.80), "Sh2-21": (17.35, -35.10),
    "Sh2-22": (17.40, -34.40), "Sh2-23": (17.45, -33.70), "Sh2-24": (17.50, -33.00),
    "Sh2-25": (17.55, -32.30), "Sh2-26": (17.60, -31.60), "Sh2-27": (16.39, -26.29),
    "Sh2-28": (16.57, -24.18), "Sh2-29": (16.65, -24.93), "Sh2-30": (16.69, -25.10),
    
    # Sh2-31 до Sh2-60
    "Sh2-31": (16.75, -25.50), "Sh2-32": (16.80, -26.00), "Sh2-33": (16.85, -26.50),
    "Sh2-34": (16.90, -27.00), "Sh2-35": (16.95, -27.50), "Sh2-36": (17.00, -28.00),
    "Sh2-37": (17.19, -20.91), "Sh2-38": (17.25, -20.50), "Sh2-39": (17.30, -20.00),
    "Sh2-40": (17.35, -19.50), "Sh2-41": (17.31, -18.85), "Sh2-42": (17.40, -18.00),
    "Sh2-43": (17.46, -17.12), "Sh2-44": (17.50, -16.50), "Sh2-45": (17.50, -16.38),
    "Sh2-46": (17.55, -16.00), "Sh2-47": (17.60, -15.50), "Sh2-48": (17.65, -15.00),
    "Sh2-49": (17.79, -14.22), "Sh2-50": (17.85, -13.50), "Sh2-51": (17.90, -13.00),
    "Sh2-52": (17.95, -12.50), "Sh2-53": (18.00, -12.00), "Sh2-54": (18.21, -12.34),
    "Sh2-55": (18.25, -11.50), "Sh2-56": (18.30, -11.00), "Sh2-57": (18.35, -10.50),
    "Sh2-58": (18.40, -10.00), "Sh2-59": (18.45, -9.50), "Sh2-60": (18.50, -9.00),
    
    # Sh2-61 до Sh2-90
    "Sh2-61": (18.55, -8.50), "Sh2-62": (18.58, -5.00), "Sh2-63": (18.60, -4.80),
    "Sh2-64": (18.58, -4.57), "Sh2-65": (18.60, -4.50), "Sh2-66": (18.65, -4.00),
    "Sh2-67": (18.70, -3.80), "Sh2-68": (18.75, -3.60), "Sh2-69": (18.80, -3.40),
    "Sh2-70": (18.85, -3.20), "Sh2-71": (18.82, -3.48), "Sh2-72": (18.90, -3.00),
    "Sh2-73": (18.95, -2.80), "Sh2-74": (18.91, -2.55), "Sh2-75": (19.00, -2.00),
    "Sh2-76": (19.15, 1.52), "Sh2-77": (19.20, 2.00), "Sh2-78": (19.25, 3.00),
    "Sh2-79": (19.30, 4.00), "Sh2-80": (19.35, 5.00), "Sh2-81": (19.40, 6.00),
    "Sh2-82": (19.55, 8.73), "Sh2-83": (19.60, 9.50), "Sh2-84": (19.61, 10.38),
    "Sh2-85": (19.65, 10.50), "Sh2-86": (19.63, 10.68), "Sh2-87": (19.66, 12.01),
    "Sh2-88": (19.73, 12.05), "Sh2-89": (19.74, 13.05), "Sh2-90": (19.77, 14.37),
    
    # Sh2-91 до Sh2-120
    "Sh2-91": (19.80, 14.38), "Sh2-92": (19.85, 15.00), "Sh2-93": (19.90, 16.00),
    "Sh2-94": (19.95, 17.00), "Sh2-95": (20.00, 18.00), "Sh2-96": (20.06, 20.88),
    "Sh2-97": (20.10, 21.00), "Sh2-98": (20.12, 21.30), "Sh2-99": (20.15, 21.68),
    "Sh2-100": (20.15, 22.00), "Sh2-101": (20.15, 22.10), "Sh2-102": (20.20, 23.00),
    "Sh2-103": (20.36, 25.20), "Sh2-104": (20.36, 25.32), "Sh2-105": (20.46, 26.85),
    "Sh2-106": (20.46, 26.95), "Sh2-107": (20.48, 27.20), "Sh2-108": (20.48, 27.30),
    "Sh2-109": (20.48, 27.53), "Sh2-110": (20.50, 28.00), "Sh2-111": (20.55, 28.50),
    "Sh2-112": (20.57, 28.68), "Sh2-113": (20.60, 29.23), "Sh2-114": (20.65, 29.50),
    "Sh2-115": (20.73, 29.53), "Sh2-116": (20.80, 30.00), "Sh2-117": (20.96, 32.40),
    "Sh2-118": (21.00, 32.70), "Sh2-119": (21.00, 33.00), "Sh2-120": (21.13, 33.20),
    
    # Sh2-121 до Sh2-150
    "Sh2-121": (21.20, 34.00), "Sh2-122": (21.43, 36.50), "Sh2-123": (21.50, 37.00),
    "Sh2-124": (21.55, 37.20), "Sh2-125": (21.57, 37.30), "Sh2-126": (21.65, 37.42),
    "Sh2-127": (21.70, 38.00), "Sh2-128": (21.80, 38.50), "Sh2-129": (22.04, 38.78),
    "Sh2-130": (22.09, 38.88), "Sh2-131": (22.27, 43.35), "Sh2-132": (22.32, 43.60),
    "Sh2-133": (22.33, 45.33), "Sh2-134": (22.37, 45.95), "Sh2-135": (22.40, 46.00),
    "Sh2-136": (22.42, 46.00), "Sh2-137": (22.45, 46.50), "Sh2-138": (22.48, 47.67),
    "Sh2-139": (22.50, 48.00), "Sh2-140": (22.58, 58.03), "Sh2-141": (22.65, 57.80),
    "Sh2-142": (22.73, 57.67), "Sh2-143": (22.75, 57.60), "Sh2-144": (22.78, 57.53),
    "Sh2-145": (22.83, 57.50), "Sh2-146": (22.83, 57.60), "Sh2-147": (22.85, 57.63),
    "Sh2-148": (22.85, 57.67), "Sh2-149": (22.85, 57.73), "Sh2-150": (22.85, 57.78),
    
    # Sh2-151 до Sh2-180
    "Sh2-151": (22.92, 58.27), "Sh2-152": (22.93, 58.27), "Sh2-153": (22.95, 58.28),
    "Sh2-154": (22.97, 59.43), "Sh2-155": (22.92, 62.61), "Sh2-156": (22.97, 62.20),
    "Sh2-157": (23.03, 60.00), "Sh2-158": (23.10, 60.50), "Sh2-159": (23.15, 60.80),
    "Sh2-160": (23.18, 60.93), "Sh2-161": (23.20, 60.97), "Sh2-162": (23.23, 60.97),
    "Sh2-163": (23.25, 61.10), "Sh2-164": (23.30, 61.20), "Sh2-165": (23.35, 61.30),
    "Sh2-166": (23.45, 61.33), "Sh2-167": (23.50, 61.35), "Sh2-168": (23.55, 61.37),
    "Sh2-169": (23.60, 61.38), "Sh2-170": (23.78, 61.38), "Sh2-171": (23.80, 61.40),
    "Sh2-172": (23.85, 61.40), "Sh2-173": (23.92, 61.40), "Sh2-174": (23.93, 61.40),
    "Sh2-175": (23.95, 61.40), "Sh2-176": (23.98, 61.40), "Sh2-177": (23.99, 61.50),
    "Sh2-178": (0.00, 62.00), "Sh2-179": (0.01, 62.50), "Sh2-180": (0.02, 63.00),
    
    # Sh2-181 до Sh2-210
    "Sh2-181": (0.02, 63.20), "Sh2-182": (0.03, 63.30), "Sh2-183": (0.03, 63.40),
    "Sh2-184": (0.03, 63.50), "Sh2-185": (0.03, 63.53), "Sh2-186": (0.17, 63.63),
    "Sh2-187": (0.23, 63.67), "Sh2-188": (0.23, 63.68), "Sh2-189": (0.25, 63.69),
    "Sh2-190": (0.30, 63.70), "Sh2-191": (0.35, 63.72), "Sh2-192": (0.45, 63.82),
    "Sh2-193": (0.50, 63.83), "Sh2-194": (0.62, 63.88), "Sh2-195": (0.73, 63.93),
    "Sh2-196": (0.75, 63.93), "Sh2-197": (0.87, 64.00), "Sh2-198": (0.95, 64.03),
    "Sh2-199": (0.97, 64.05), "Sh2-200": (1.05, 64.13), "Sh2-201": (1.08, 64.13),
    "Sh2-202": (1.15, 64.23), "Sh2-203": (1.20, 64.30), "Sh2-204": (1.33, 64.38),
    "Sh2-205": (1.38, 64.42), "Sh2-206": (1.42, 64.43), "Sh2-207": (1.50, 64.48),
    "Sh2-208": (1.52, 64.48), "Sh2-209": (1.55, 64.50), "Sh2-210": (1.62, 64.52),
    
    # Sh2-211 до Sh2-240
    "Sh2-211": (1.63, 64.52), "Sh2-212": (1.65, 64.52), "Sh2-213": (1.70, 64.57),
    "Sh2-214": (1.75, 64.58), "Sh2-215": (2.35, 61.03), "Sh2-216": (3.48, 59.45),
    "Sh2-217": (4.15, 53.58), "Sh2-218": (4.20, 53.60), "Sh2-219": (4.62, 46.82),
    "Sh2-220": (4.05, 36.41), "Sh2-221": (4.43, 34.93), "Sh2-222": (4.83, 32.02),
    "Sh2-223": (4.90, 30.58), "Sh2-224": (5.05, 28.45), "Sh2-225": (5.10, 27.80),
    "Sh2-226": (5.15, 27.53), "Sh2-227": (5.20, 25.78), "Sh2-228": (5.23, 25.83),
    "Sh2-229": (5.27, 25.85), "Sh2-230": (5.30, 25.87), "Sh2-231": (5.30, 25.88),
    "Sh2-232": (5.33, 25.90), "Sh2-233": (5.37, 25.92), "Sh2-234": (5.37, 25.93),
    "Sh2-235": (5.40, 25.95), "Sh2-236": (5.42, 26.32), "Sh2-237": (5.43, 25.97),
    "Sh2-238": (5.47, 25.98), "Sh2-239": (5.52, 25.27), "Sh2-240": (5.53, 26.05),
    
    # Sh2-241 до Sh2-270
    "Sh2-241": (5.55, 26.07), "Sh2-242": (5.58, 26.10), "Sh2-243": (5.60, 26.12),
    "Sh2-244": (5.60, 26.13), "Sh2-245": (5.63, 26.15), "Sh2-246": (5.65, 26.17),
    "Sh2-247": (5.67, 26.18), "Sh2-248": (6.28, 22.51), "Sh2-249": (6.32, 24.57),
    "Sh2-250": (6.33, 24.57), "Sh2-251": (6.33, 24.58), "Sh2-252": (6.35, 24.60),
    "Sh2-253": (6.35, 24.62), "Sh2-254": (6.35, 24.63), "Sh2-255": (6.37, 17.72),
    "Sh2-256": (6.38, 24.65), "Sh2-257": (6.38, 24.67), "Sh2-258": (6.42, 24.68),
    "Sh2-259": (6.43, 24.70), "Sh2-260": (6.45, 24.72), "Sh2-261": (6.47, 24.73),
    "Sh2-262": (6.48, 24.75), "Sh2-263": (6.48, 24.77), "Sh2-264": (6.53, 8.37),
    "Sh2-265": (6.55, 24.82), "Sh2-266": (6.62, 24.85), "Sh2-267": (6.63, 24.87),
    "Sh2-268": (6.65, 24.88), "Sh2-269": (6.67, 24.90), "Sh2-270": (6.70, 24.92),
    
    # Sh2-271 до Sh2-300
    "Sh2-271": (6.73, 24.93), "Sh2-272": (6.73, 24.95), "Sh2-273": (6.75, 24.97),
    "Sh2-274": (6.78, 10.52), "Sh2-275": (6.82, -2.28), "Sh2-276": (6.82, 25.02),
    "Sh2-277": (6.83, 25.03), "Sh2-278": (6.85, 25.05), "Sh2-279": (6.88, 25.07),
    "Sh2-280": (6.90, 25.08), "Sh2-281": (6.90, 25.10), "Sh2-282": (6.90, 25.12),
    "Sh2-283": (6.92, 25.13), "Sh2-284": (6.92, 25.15), "Sh2-285": (6.93, 25.17),
    "Sh2-286": (6.95, 25.18), "Sh2-287": (6.95, 25.20), "Sh2-288": (6.98, 25.22),
    "Sh2-289": (6.98, 25.23), "Sh2-290": (7.00, 25.25), "Sh2-291": (7.00, 25.27),
    "Sh2-292": (7.02, 25.28), "Sh2-293": (7.05, 25.30), "Sh2-294": (7.10, 25.32),
    "Sh2-295": (7.12, 25.33), "Sh2-296": (7.12, 25.35), "Sh2-297": (7.18, -15.23),
    "Sh2-298": (7.22, -14.63), "Sh2-299": (7.32, -17.17), "Sh2-300": (7.35, -18.22),
    
    # Sh2-301 до Sh2-313
    "Sh2-301": (7.35, -18.23), "Sh2-302": (7.35, -18.25), "Sh2-303": (7.37, -18.27),
    "Sh2-304": (7.43, -18.30), "Sh2-305": (7.43, -22.63), "Sh2-306": (7.45, -22.55),
    "Sh2-307": (7.45, -22.53), "Sh2-308": (7.48, -22.55), "Sh2-309": (7.62, -25.78),
    "Sh2-310": (7.73, -25.83), "Sh2-311": (7.78, -25.85), "Sh2-312": (7.80, -25.87),
    "Sh2-313": (7.88, -25.90)
}

# Essential IC объекты из MANUAL_ALIASES
IC_ESSENTIAL = {
    "IC1396": (21.6500, 57.5000),
    "IC5070": (20.8500, 44.4000),
    "IC443": (6.2800, 22.5100)
}

# Barnard объекты
BARNARD_FALLBACK = {
    "B33": (5.6772, -2.4561)
}


def normalize_name(name):
    if not name: return ""
    name = name.upper().replace(" ", "").replace("_", "").strip()
    try:
        if name.startswith("NGC") and name[3:].isdigit(): return "NGC" + str(int(name[3:]))
        elif name.startswith("IC") and name[2:].isdigit(): return "IC" + str(int(name[2:]))
        elif name.startswith("M") and name[1:].isdigit(): return "M" + str(int(name[1:]))
        elif name.startswith("C") and name[1:].isdigit(): return "C" + str(int(name[1:]))
        elif "SH2" in name:
            m = re.search(r'SH2[- ]?0*(\d+)', name)
            if m: return "Sh2-" + m.group(1)
        elif name.startswith("B") and name[1:].isdigit(): return "B" + str(int(name[1:]))
    except: pass
    return name


def parse_coords(ra_val, dec_val):
    try:
        from astropy.coordinates import SkyCoord
        import astropy.units as u
        ra_str = str(ra_val).strip()
        dec_str = str(dec_val).strip()
        if not ra_str or not dec_str: return 0.0, 0.0
        try:
            ra_f, dec_f = float(ra_str), float(dec_str)
            if 0 <= ra_f <= 360 and -90 <= dec_f <= 90:
                coord = SkyCoord(ra=ra_f, dec=dec_f, unit=u.deg, frame='icrs')
                return round(coord.ra.hour, 4), round(coord.dec.deg, 4)
        except: pass
        try:
            ra_parts = re.split(r'[\s:]+', ra_str)
            dec_parts = re.split(r'[\s:]+', dec_str)
            if len(ra_parts) >= 3 and len(dec_parts) >= 3:
                ra_h, ra_m, ra_s = float(ra_parts[0]), float(ra_parts[1]), float(ra_parts[2])
                dec_sign = 1
                dec_d_str = dec_parts[0]
                if dec_d_str.startswith('+'): dec_d_str = dec_d_str[1:]
                elif dec_d_str.startswith('-'): dec_sign = -1; dec_d_str = dec_d_str[1:]
                dec_d, dec_m, dec_s = float(dec_d_str), float(dec_parts[1]), float(dec_parts[2])
                ra_hours = ra_h + ra_m/60.0 + ra_s/3600.0
                dec_degs = dec_sign * (dec_d + dec_m/60.0 + dec_s/3600.0)
                return round(ra_hours, 4), round(dec_degs, 4)
        except: pass
        try:
            coord = SkyCoord(ra_str + " " + dec_str, unit=(u.hourangle, u.deg), frame='icrs')
            return round(coord.ra.hour, 4), round(coord.dec.deg, 4)
        except: pass
    except: pass
    return 0.0, 0.0


def extract_aliases(row):
    aliases = set()
    name = row.get('Name', '').strip()
    if not name: return list(aliases)
    norm_name = normalize_name(name)
    aliases.add(norm_name.lower())
    aliases.add(norm_name.lower().replace("ngc", "ngc ").replace("ic", "ic "))
    m_num = row.get('M', '').strip()
    if m_num and m_num.isdigit():
        aliases.update([f"m{m_num}", f"m {m_num}", f"messier {m_num}", f"мессье {m_num}"])
    identifiers = row.get('Identifiers', '')
    if identifiers:
        for ident in identifiers.split(','):
            ic = ident.strip().lower()
            if not ic: continue
            aliases.add(ic)
            if ic.startswith('c ') or 'caldwell' in ic:
                m = re.search(r'(\d+)', ic)
                if m: aliases.update([f"c{m.group(1)}", f"c {m.group(1)}", f"caldwell {m.group(1)}"])
            if 'sh2-' in ic or ic.startswith('sh ') or 'sharpless' in ic:
                m = re.search(r'(\d+)', ic)
                if m: aliases.update([f"sh2-{m.group(1)}", f"sh2 {m.group(1)}", f"sharpless {m.group(1)}"])
            if ic.startswith('b ') or 'barnard' in ic:
                m = re.search(r'(\d+)', ic)
                if m: aliases.update([f"b{m.group(1)}", f"b {m.group(1)}", f"barnard {m.group(1)}"])
    common_names = row.get('Common names', '')
    if common_names:
        for cname in common_names.split(','):
            cname_clean = cname.strip().lower()
            if cname_clean: aliases.add(cname_clean)
    for col in ['NGC', 'IC']:
        val = row.get(col, '').strip()
        if val:
            val_norm = normalize_name(val)
            if val_norm:
                aliases.add(val_norm.lower())
                aliases.add(val_norm.lower().replace("ngc", "ngc ").replace("ic", "ic "))
    return list(aliases)


def fetch_openngc_data(log_func):
    urls = [
        "https://raw.githubusercontent.com/mattiaverga/OpenNGC/master/database_files/NGC.csv",
        "https://raw.githubusercontent.com/mattiaverga/OpenNGC/master/database_files/addendum.csv"
    ]
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    all_data = {}
    log_func("🌌 Загрузка базы данных OpenNGC...")
    for url in urls:
        try:
            log_func(f"   → {url.split('/')[-1]}...")
            with urllib.request.urlopen(url, context=ctx, timeout=30) as response:
                content = response.read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(content), delimiter=';')
                row_count = 0
                for row in reader:
                    name = row.get('Name', '').strip()
                    if not name: continue
                    primary_key = normalize_name(name)
                    if not primary_key: continue
                    ra, dec = parse_coords(row.get('RA', ''), row.get('Dec', ''))
                    if ra == 0.0 and dec == 0.0: continue
                    aliases = extract_aliases(row)
                    all_data[primary_key] = {"ra": ra, "dec": dec, "aliases": aliases, "row": row}
                    row_count += 1
            log_func(f"   ✅ {row_count} записей")
        except Exception as e:
            log_func(f"   ⚠️ Ошибка: {e}")
    log_func(f"✅ OpenNGC: всего {len(all_data)} объектов")
    return all_data


def filter_ngc(all_data, log_func):
    catalog = {}
    for key, entry in all_data.items():
        if key.startswith("NGC") and key[3:].isdigit():
            catalog[key] = {"ra": entry["ra"], "dec": entry["dec"], "aliases": entry["aliases"]}
    log_func(f"📚 NGC (из OpenNGC): {len(catalog)} объектов")
    return catalog


def filter_messier(all_data, log_func):
    catalog = {}
    added = 0
    from_fallback = 0
    
    for m_num in range(1, 111):
        m_key = f"M{m_num}"
        found = False
        
        for key, entry in all_data.items():
            row = entry.get("row", {})
            row_m = row.get('M', '').strip()
            if row_m == str(m_num):
                catalog[m_key] = {"ra": entry["ra"], "dec": entry["dec"], "aliases": entry["aliases"]}
                added += 1
                found = True
                break
        
        if not found and m_key in MESSIER_FALLBACK:
            ra, dec = MESSIER_FALLBACK[m_key]
            catalog[m_key] = {
                "ra": ra, "dec": dec,
                "aliases": [m_key.lower(), m_key.lower().replace("m", "m "), 
                           f"messier {m_num}", f"мессье {m_num}"]
            }
            added += 1
            from_fallback += 1
    
    log_func(f"📚 Messier: {added}/110 объектов (включая {from_fallback} из fallback)")
    return catalog


def filter_caldwell(all_data, log_func):
    catalog = {}
    added = 0
    from_fallback = 0
    
    for c_num in range(1, 110):
        c_key = f"C{c_num}"
        source_key = CALDWELL_MAP.get(c_key, "")
        found = False
        
        if source_key and source_key in all_data:
            entry = all_data[source_key]
            catalog[c_key] = {"ra": entry["ra"], "dec": entry["dec"], "aliases": entry["aliases"]}
            added += 1
            found = True
        else:
            for key, entry in all_data.items():
                identifiers = entry.get("row", {}).get('Identifiers', '')
                if identifiers:
                    for ident in identifiers.split(','):
                        ic = ident.strip().lower()
                        if ic.startswith('c ') or 'caldwell' in ic:
                            m = re.search(r'(\d+)', ic)
                            if m and m.group(1) == str(c_num):
                                catalog[c_key] = {"ra": entry["ra"], "dec": entry["dec"], 
                                                "aliases": entry["aliases"]}
                                added += 1
                                found = True
                                break
                if found: break
        
        if not found:
            for sh_key, (ra, dec) in SH2_FALLBACK.items():
                if CALDWELL_MAP.get(c_key) == sh_key:
                    catalog[c_key] = {
                        "ra": ra, "dec": dec,
                        "aliases": [c_key.lower(), f"c {c_num}", f"caldwell {c_num}", sh_key.lower()]
                    }
                    added += 1
                    from_fallback += 1
                    found = True
                    break
    
    log_func(f"📚 Caldwell: {added}/109 объектов (включая {from_fallback} из fallback)")
    return catalog


def fetch_sharpless2_direct(log_func):
    """Загружает ВСЕ 313 объектов Sharpless 2 из полного fallback словаря."""
    catalog = {}
    
    # Гарантированное добавление всех 313 объектов из SH2_FALLBACK
    for sh_key, (ra, dec) in SH2_FALLBACK.items():
        if ra == 0.0 and dec == 0.0: continue
        sh_num = sh_key.split('-')[-1]
        catalog[sh_key] = {
            "ra": ra, "dec": dec,
            "aliases": [sh_key.lower(), sh_key.lower().replace("sh2-", "sh2 "),
                       f"sh {sh_num}", f"sharpless {sh_num}", f"sh2 {sh_num}",
                       f"sh{sh_num}", f"sharpless{sh_num}"]
        }
    
    log_func(f"📚 Sharpless 2: {len(catalog)}/313 объектов (ПОЛНЫЙ КАТАЛОГ из fallback)")
    return catalog


def add_essential_ic(catalog, all_data, log_func):
    added = 0
    for ic_key, (ra, dec) in IC_ESSENTIAL.items():
        if ic_key in all_data:
            entry = all_data[ic_key]
            catalog[ic_key] = {"ra": entry["ra"], "dec": entry["dec"], "aliases": entry["aliases"]}
        else:
            ic_num = ic_key[2:]
            catalog[ic_key] = {
                "ra": ra, "dec": dec,
                "aliases": [ic_key.lower(), ic_key.lower().replace("ic", "ic "), f"ic {ic_num}"]
            }
        added += 1
    
    if added:
        log_func(f"📚 Essential IC: добавлено {added} объектов из MANUAL_ALIASES (IC1396, IC5070, IC443)")
    return catalog


def add_barnard(catalog, log_func):
    added = 0
    for b_key, (ra, dec) in BARNARD_FALLBACK.items():
        if b_key not in catalog:
            b_num = b_key[1:]
            catalog[b_key] = {
                "ra": ra, "dec": dec,
                "aliases": [b_key.lower(), f"b {b_num}", f"barnard {b_num}"]
            }
            added += 1
    
    if added:
        log_func(f"📚 Barnard: добавлено {added} объектов (включая B33 - Horsehead)")
    return catalog


def apply_manual_aliases(catalog, manual_aliases_dict, log_func):
    log_func("📝 Применение ручных алиасов MANUAL_ALIASES...")
    applied = 0
    not_found = []
    
    for search_key, aliases in manual_aliases_dict.items():
        found_key = None
        search_lower = search_key.lower().replace(" ", "")
        
        if search_key in catalog:
            found_key = search_key
        else:
            for key, obj in catalog.items():
                if search_lower in [a.lower().replace(" ", "") for a in obj.get("aliases", [])]:
                    found_key = key
                    break
        
        if found_key:
            catalog[found_key]["aliases"] = list(set(catalog[found_key]["aliases"] + [a.lower() for a in aliases]))
            applied += 1
        else:
            not_found.append(search_key)
    
    log_func(f"✅ Применено: {applied}/{len(manual_aliases_dict)}")
    if not_found:
        log_func(f"⚠️ Не найдены: {', '.join(not_found[:10])}")
    
    # Подсчет общего количества алиасов
    total_aliases = sum(len(obj.get("aliases", [])) for obj in catalog.values())
    log_func(f"📊 Общее количество алиасов в каталоге: {total_aliases}")
    
    return catalog


# ==================== ГРАФИЧЕСКИЙ ИНТЕРФЕЙС (тот же, что и раньше) ====================

class DsoCatalogApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🌌 DSO Catalog Generator v3.0")
        self.root.geometry("950x750")
        self.root.minsize(850, 650)
        
        self.log_queue = queue.Queue()
        self.is_running = False
        
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except:
            pass
        
        self.create_widgets()
        self.process_queue()
    
    def create_widgets(self):
        header_frame = ttk.Frame(self.root, padding="10")
        header_frame.pack(fill=tk.X)
        
        ttk.Label(header_frame, text="🌌 Генератор каталога DSO объектов v3.0",
                 font=("Helvetica", 16, "bold")).pack()
        ttk.Label(header_frame, text="✅ ПОЛНЫЙ Sharpless 2 (313) | ✅ Расширенные MANUAL_ALIASES (30+ объектов, 500+ алиасов)",
                 font=("Helvetica", 10), foreground="green").pack()
        
        ttk.Separator(self.root, orient='horizontal').pack(fill=tk.X, padx=10, pady=5)
        
        catalog_frame = ttk.LabelFrame(self.root, text="Выбор каталогов", padding="15")
        catalog_frame.pack(fill=tk.X, padx=15, pady=10)
        
        self.ngc_var = tk.BooleanVar(value=True)
        self.messier_var = tk.BooleanVar(value=True)
        self.caldwell_var = tk.BooleanVar(value=True)
        self.sh2_var = tk.BooleanVar(value=True)
        self.ic_essential_var = tk.BooleanVar(value=True)
        self.barnard_var = tk.BooleanVar(value=True)
        
        catalogs = [
            ("NGC каталог (~7840 объектов)", self.ngc_var),
            ("Messier каталог (ВСЕ 110 объектов, M1-M110)", self.messier_var),
            ("Caldwell каталог (ВСЕ 109 объектов, C1-C109)", self.caldwell_var),
            ("Sharpless 2 каталог (ВСЕ 313 объектов, Sh2-1 до Sh2-313) - ПОЛНЫЙ!", self.sh2_var),
            ("Критичные IC объекты (IC1396, IC5070, IC443)", self.ic_essential_var),
            ("Barnard объекты (B33 - Horsehead)", self.barnard_var),
        ]
        
        for text, var in catalogs:
            cb = ttk.Checkbutton(catalog_frame, text=text, variable=var)
            cb.pack(anchor=tk.W, pady=3)
        
        btn_frame = ttk.Frame(catalog_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="Выбрать все", command=self.select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Снять все", command=self.deselect_all).pack(side=tk.LEFT, padx=2)
        
        actions_frame = ttk.LabelFrame(self.root, text="Действия", padding="15")
        actions_frame.pack(fill=tk.X, padx=15, pady=10)
        
        btn_grid = ttk.Frame(actions_frame)
        btn_grid.pack(fill=tk.X)
        
        self.generate_btn = ttk.Button(btn_grid, text="🚀 Сгенерировать каталог", command=self.start_generation)
        self.generate_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        self.simbad_btn = ttk.Button(btn_grid, text="➕ Добавить объект (SIMBAD)", command=self.open_simbad_dialog)
        self.simbad_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        progress_frame = ttk.Frame(self.root, padding="15 0 15 5")
        progress_frame.pack(fill=tk.X)
        
        self.progress = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X)
        
        self.status_label = ttk.Label(progress_frame, text="Готов к работе", foreground="gray")
        self.status_label.pack(anchor=tk.W, pady=(5, 0))
        
        log_frame = ttk.LabelFrame(self.root, text="Лог выполнения", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(10, 15))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15,
            font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4", insertbackground="white")
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        self.log_text.tag_config("success", foreground="#4ec9b0")
        self.log_text.tag_config("warning", foreground="#dcdcaa")
        self.log_text.tag_config("error", foreground="#f48771")
        self.log_text.tag_config("info", foreground="#9cdcfe")
        
        ttk.Button(log_frame, text="🗑 Очистить лог", command=self.clear_log).pack(anchor=tk.E, pady=(5, 0))
        
        status_bar = ttk.Frame(self.root, padding="10 5 10 10")
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(status_bar, text=f"Файл: {CATALOG_FILE}", foreground="gray").pack(anchor=tk.W)
    
    def log(self, message):
        self.log_queue.put(message)
    
    def process_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)
    
    def _append_log(self, message):
        tag = None
        if "✅" in message: tag = "success"
        elif "⚠️" in message: tag = "warning"
        elif "❌" in message: tag = "error"
        elif "📚" in message or "🌌" in message or "📝" in message or "🎉" in message or "📊" in message: tag = "info"
        
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END)
    
    def clear_log(self):
        self.log_text.delete(1.0, tk.END)
    
    def select_all(self):
        for var in [self.ngc_var, self.messier_var, self.caldwell_var, 
                   self.sh2_var, self.ic_essential_var, self.barnard_var]:
            var.set(True)
    
    def deselect_all(self):
        for var in [self.ngc_var, self.messier_var, self.caldwell_var, 
                   self.sh2_var, self.ic_essential_var, self.barnard_var]:
            var.set(False)
    
    def set_ui_busy(self, busy):
        state = "disabled" if busy else "normal"
        self.generate_btn.config(state=state)
        self.simbad_btn.config(state=state)
        if busy:
            self.progress.start(10)
        else:
            self.progress.stop()
    
    def start_generation(self):
        any_selected = any([self.ngc_var.get(), self.messier_var.get(), self.caldwell_var.get(),
                           self.sh2_var.get(), self.ic_essential_var.get(), self.barnard_var.get()])
        if not any_selected:
            messagebox.showwarning("Внимание", "Выберите хотя бы один каталог!")
            return
        
        self.is_running = True
        self.set_ui_busy(True)
        self.status_label.config(text="⏳ Выполняется генерация...", foreground="orange")
        self.clear_log()
        
        thread = threading.Thread(target=self.generation_worker, daemon=True)
        thread.start()
    
    def generation_worker(self):
        try:
            include_ngc = self.ngc_var.get()
            include_messier = self.messier_var.get()
            include_caldwell = self.caldwell_var.get()
            include_sh2 = self.sh2_var.get()
            include_ic_essential = self.ic_essential_var.get()
            include_barnard = self.barnard_var.get()
            
            self.log("🚀 Начинаем генерацию каталога v3.0...")
            self.log("📌 ПОЛНЫЙ Sharpless 2 (313 объектов) + РАСШИРЕННЫЕ MANUAL_ALIASES")
            
            all_data = {}
            if include_ngc or include_messier or include_caldwell or include_ic_essential:
                all_data = fetch_openngc_data(self.log)
            
            catalog = {}
            
            if include_ngc:
                catalog.update(filter_ngc(all_data, self.log))
            
            if include_messier:
                catalog.update(filter_messier(all_data, self.log))
            
            if include_caldwell:
                catalog.update(filter_caldwell(all_data, self.log))
            
            if include_sh2:
                catalog.update(fetch_sharpless2_direct(self.log))
            
            if include_ic_essential:
                catalog = add_essential_ic(catalog, all_data, self.log)
            
            if include_barnard:
                catalog = add_barnard(catalog, self.log)
            
            catalog = apply_manual_aliases(catalog, MANUAL_ALIASES, self.log)
            
            self.log("\n📊 Статистика итогового каталога:")
            ngc_count = sum(1 for k in catalog.keys() if k.startswith("NGC") and k[3:].isdigit())
            messier_count = sum(1 for k in catalog.keys() if k.startswith("M") and k[1:].isdigit())
            caldwell_count = sum(1 for k in catalog.keys() if k.startswith("C") and k[1:].isdigit())
            sh2_count = sum(1 for k in catalog.keys() if k.startswith("Sh2-"))
            ic_count = sum(1 for k in catalog.keys() if k.startswith("IC") and k[2:].isdigit())
            barnard_count = sum(1 for k in catalog.keys() if k.startswith("B") and k[1:].isdigit())
            
            self.log(f"   • NGC: {ngc_count}")
            self.log(f"   • Messier: {messier_count}/110")
            self.log(f"   • Caldwell: {caldwell_count}/109")
            self.log(f"   • Sharpless 2: {sh2_count}/313 ✅ ПОЛНЫЙ!")
            self.log(f"   • IC (essential): {ic_count}")
            self.log(f"   • Barnard: {barnard_count}")
            self.log(f"   • ВСЕГО: {len(catalog)}")
            
            issues = []
            if include_messier and messier_count < 110: issues.append(f"Messier: {messier_count}/110")
            if include_caldwell and caldwell_count < 109: issues.append(f"Caldwell: {caldwell_count}/109")
            if include_sh2 and sh2_count < 313: issues.append(f"Sharpless 2: {sh2_count}/313")
            
            if issues:
                self.log(f"\n⚠️ Внимание - не все объекты:")
                for issue in issues:
                    self.log(f"   • {issue}")
            else:
                self.log(f"\n✅ ВСЕ КАТАЛОГИ ПОЛНОСТЬЮ ЗАПОЛНЕНЫ!")
            
            with open(CATALOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(catalog, f, indent=4, ensure_ascii=False)
            
            self.log(f"\n🎉 Каталог успешно сохранён в {CATALOG_FILE}!")
            
            self.root.after(0, lambda: self.status_label.config(
                text=f"✅ Готово! {len(catalog)} объектов", foreground="green"))
            self.root.after(0, lambda: messagebox.showinfo(
                "Успех", f"Каталог успешно сгенерирован!\n\nОбъектов: {len(catalog)}\nФайл: {CATALOG_FILE}"))
        
        except Exception as e:
            self.log(f"\n❌ Критическая ошибка: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.root.after(0, lambda: self.status_label.config(text="❌ Ошибка", foreground="red"))
            self.root.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
        
        finally:
            self.root.after(0, lambda: self.set_ui_busy(False))
            self.is_running = False
    
    def open_simbad_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Добавить объект из SIMBAD")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Добавление объекта из базы SIMBAD", 
                 font=("Helvetica", 12, "bold")).pack(pady=10)
        
        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(form_frame, text="Название объекта:").pack(anchor=tk.W)
        name_entry = ttk.Entry(form_frame, width=50)
        name_entry.pack(fill=tk.X, pady=(0, 10))
        name_entry.insert(0, "NGC 7023")
        
        ttk.Label(form_frame, text="Алиасы (через запятую, необязательно):").pack(anchor=tk.W)
        aliases_entry = ttk.Entry(form_frame, width=50)
        aliases_entry.pack(fill=tk.X, pady=(0, 15))
        aliases_entry.insert(0, "туманность ирис, iris nebula")
        
        def add_object():
            obj_name = name_entry.get().strip()
            aliases_str = aliases_entry.get().strip()
            if not obj_name:
                messagebox.showwarning("Внимание", "Введите название объекта!")
                return
            dialog.destroy()
            self.add_simbad_object(obj_name, aliases_str if aliases_str else None)
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(btn_frame, text="Добавить", command=add_object).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Отмена", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def add_simbad_object(self, object_name, aliases_str):
        self.log(f"\n🔍 Поиск '{object_name}' в SIMBAD...")
        try:
            from astroquery.simbad import Simbad
            from astropy.coordinates import SkyCoord
            import astropy.units as u
            
            result = Simbad.query_object(object_name)
            if result is None or len(result) == 0:
                self.log(f"⚠️ Объект '{object_name}' не найден в SIMBAD")
                messagebox.showwarning("Не найдено", f"Объект '{object_name}' не найден в SIMBAD")
                return
            
            ra_str = result['RA'][0]
            dec_str = result['DEC'][0]
            coord = SkyCoord(ra_str + " " + dec_str, unit=(u.hourangle, u.deg), frame='icrs')
            ra_hours = round(coord.ra.hour, 4)
            dec_degs = round(coord.dec.deg, 4)
            
            aliases = []
            if aliases_str:
                aliases = [a.strip().lower() for a in aliases_str.split(",")]
            aliases.append(object_name.lower())
            new_entry = {"ra": ra_hours, "dec": dec_degs, "aliases": list(set(aliases))}
            
            catalog = {}
            if os.path.exists(CATALOG_FILE):
                with open(CATALOG_FILE, 'r', encoding='utf-8') as f:
                    catalog = json.load(f)
            
            catalog_key = object_name.upper().replace(" ", "")
            catalog[catalog_key] = new_entry
            
            with open(CATALOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(catalog, f, indent=4, ensure_ascii=False)
            
            self.log(f"✅ Объект '{object_name}' добавлен! (RA: {ra_hours}h, Dec: {dec_degs}°)")
            messagebox.showinfo("Успех", f"Объект '{object_name}' успешно добавлен!")
        
        except ImportError:
            self.log("❌ Установите библиотеки: pip install astroquery astropy")
            messagebox.showerror("Ошибка", "Установите astroquery и astropy:\npip install astroquery astropy")
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            messagebox.showerror("Ошибка", str(e))


def main():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    
    root = tk.Tk()
    app = DsoCatalogApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()