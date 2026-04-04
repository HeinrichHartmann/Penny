from penny.classify import contains, is_, rule


def payee_is(tx, *values):
    return any(is_(tx.payee, value) for value in values)


def payee_contains(tx, *needles):
    return any(contains(tx.payee, needle) for needle in needles)


def memo_contains(tx, *needles):
    return any(contains(tx.memo, needle) for needle in needles)


def raw_contains(tx, *needles):
    return any(contains(tx.raw_buchungstext, needle) for needle in needles)


def text_contains(tx, *needles):
    return payee_contains(tx, *needles) or memo_contains(tx, *needles) or raw_contains(tx, *needles)


@rule("salary")
def zalando_salary(tx):
    return payee_is(tx, "Zalando SE") and memo_contains(tx, "lohn / gehalt")


@rule("salary/zalando_equity")
def zalando_equity(tx):
    return payee_is(tx, "EQUATEX AG") or text_contains(tx, "equateplus")


@rule("family/child_benefit")
def child_benefit(tx):
    return text_contains(tx, "familienkasse")


@rule("family/allowance")
def family_card_allowance(tx):
    return (
        (payee_is(tx, "Lena Hartmann") and memo_contains(tx, "family card"))
        or payee_is(tx, "Elisa Sophie Hartmann", "Viola Hartmann", "Mathilda Hartmann")
    )


@rule("household/mortgage")
def mortgage_transfer(tx):
    return payee_is(tx, "Lena Hegerfeld und Heinrich Hartmann") or memo_contains(tx, "hauskredit")


@rule("transfer/shared")
def shared_account_transfer(tx):
    return payee_is(tx, "Lena Hartmann und Heinrich Hartmann")


@rule("transfer/lena_personal")
def lena_personal_transfer(tx):
    return payee_is(tx, "Lena Hartmann") and (
        raw_contains(tx, "DE29200411110837291400") or memo_contains(tx, "erstattung")
    )


@rule("transfer/private")
def private_family_transfer(tx):
    return (
        payee_is(tx, "Dr. Heinrich Hartmann", "Lena Hartmann", "Lena Hartmann, Dr. Heinrich Hartmann")
        and memo_contains(tx, "gemeinschaftskonto", "uebertrag", "umbuchung", "sonderzahlung")
    )


@rule("family/support")
def family_support(tx):
    return payee_is(tx, "Ulrich Hartmann", "Hans-Wilhelm Hartmann")


@rule("transfer/card_settlement")
def card_settlement(tx):
    return (
        payee_is(tx, "Comdirect", "Visa-Kartenabrechnung", "SUMME MONATSABRECHNUNG VISA")
        or payee_contains(tx, "Visa-Monatsabrechnung")
        or memo_contains(tx, "monatsabrechnung visa", "visa-kartenabrechnung")
    )


@rule("financial/bank_fees")
def bank_fees(tx):
    return (
        payee_is(tx, "Kontoführungsentgelt")
        or payee_contains(tx, "AUSLANDSENTGELT")
        or (payee_is(tx, "Kontoabschluss") and tx.amount_cents < 0)
        or (payee_is(tx, "Comdirect") and memo_contains(tx, "entgelt"))
    )


@rule("financial/interest")
def interest_income(tx):
    return (
        (payee_is(tx, "Kontoabschluss") and tx.amount_cents > 0)
        or (payee_is(tx, "HARTMANN IT GMBH") and memo_contains(tx, "zinszahlung"))
    )


@rule("professional/tax_accounting")
def tax_accounting(tx):
    return payee_is(tx, "Commerzbank AG") or text_contains(tx, "fieseler")


@rule("tax/refund")
def tax_refund(tx):
    return payee_is(tx, "STEUERVERWALTUNG NRW") and tx.amount_cents > 0


@rule("financial/fees/government")
def government_fees(tx):
    return payee_contains(tx, "bundeskasse")


@rule("transfer/investment_asset")
def depot_asset_transfer(tx):
    return tx.subaccount_type == "depot"


@rule("investment/stocks")
def stock_investments(tx):
    return payee_is(tx, "Wertpapiere", "Kupon") or tx.transaction_type in {"Wertpapiere", "Kupon"}


@rule("investment/bitcoin")
def bitcoin(tx):
    return text_contains(tx, "bitpanda")


@rule("family/kindergarten")
def kindergarten(tx):
    return text_contains(tx, "parität für kinder", "paritaet fuer kinder", "wiesenpiraten", "ogs haldem")


@rule("family/music_education")
def music_education(tx):
    return text_contains(tx, "sabrina dresa", "sabrina hassebrock", "musikschulverband")


@rule("family/dance")
def dance(tx):
    return text_contains(tx, "anna nasirov-kotow", "artistic dance academy")


@rule("family/sports")
def kids_sports(tx):
    return text_contains(
        tx,
        "reit- und fahrverein",
        "sport club",
        "blasheimer sport-club",
        "tv frisch auf levern",
        "tus lemfoerde",
    )


@rule("family/swimming")
def swimming(tx):
    return text_contains(
        tx,
        "aquaparkt",
        "interspa",
        "marita lorenz-ruthenberg",
        "freizeitbad atoll",
        "minimare",
    )


@rule("personal/recreation/kids_park")
def kids_park(tx):
    return text_contains(tx, "marissa aktivitaetenha", "marissa kinderpark", "kletterpark")


@rule("family/children_programs")
def children_programs(tx):
    return text_contains(tx, "jugend,freizeit", "jugend freizeit", "ogs gebuehren")


@rule("personal/donations")
def donations(tx):
    return text_contains(
        tx,
        "deutsches rotes kreuz",
        "johanniter",
        "fdp stemwede",
        "f.d.p. ortsverb",
        "heimatverein levern",
    )


@rule("insurance/legal")
def legal_insurance(tx):
    return text_contains(tx, "arag")


@rule("insurance")
def insurance(tx):
    return text_contains(
        tx,
        "alte leipziger",
        "debeka",
        "hannoversche lebensversicherung",
        "docura",
        "lvm",
        "allianz",
        "adac versicherung",
        "nordhemmer versicherungsverein",
        "verti versicherung",
    )


@rule("utilities/electricity")
def electricity(tx):
    return text_contains(tx, "e.on energie", "elektrizitatsgesellschaft levern", "elektrizitätsgesellschaft levern")


@rule("utilities/internet")
def internet(tx):
    return text_contains(tx, "greenfiber")


@rule("household/municipal_fees")
def municipal_fees(tx):
    return text_contains(tx, "servicehaus stemwede", "gemeinde stemwede", "buergerbuero stemwede")


@rule("subscriptions/storage")
def storage_subscription(tx):
    return text_contains(tx, "backblaze")


@rule("subscriptions/media/newspapers")
def newspapers(tx):
    return text_contains(tx, "kreiszeitung", "frankfurter allgemeine")


@rule("subscriptions/media/public_broadcast")
def public_broadcast(tx):
    return text_contains(tx, "rundfunk ard", "dradio", "rundfunkbeitrag")


@rule("subscriptions/software")
def software_subscriptions(tx):
    return text_contains(
        tx,
        "amazon web services",
        "aws emea",
        "telekom deutschland",
        "host europe",
        "openai",
        "chatgpt",
        "claude.ai",
        "anthropic",
        "github",
        "riverside",
        "cursor",
        "x corp",
        "otter.ai",
        "midjourney",
        "apple.com/bill",
        "apple.com bill",
        "apple.com/de",
        "google one",
        "google one ai premium",
        "twitter paid features",
        "bitwarden",
        "dash0",
        "calendly",
        "docusign",
        "audible",
    )


@rule("travel/booking")
def travel_booking(tx):
    return text_contains(tx, "booking.com", "expedia", "airbnb")


@rule("travel/hotel")
def travel_hotel(tx):
    return text_contains(tx, "hotel", "schulz hotel", "dorint")


@rule("travel/shopping")
def travel_shopping(tx):
    return text_contains(tx, "lagardere")


@rule("travel/food")
def travel_food(tx):
    return text_contains(tx, "backwerk", "ditsch", "serways", "aramark", "le crobag", "haferkater", "autogrill")


@rule("transport/rideshare")
def rideshare(tx):
    return text_contains(tx, "uber")


@rule("transport/public_transit")
def public_transit(tx):
    return text_contains(tx, "db vertrieb", "db fernverkehr", "deutsche bahn", "bahncard", "contipark")


@rule("transport/fuel")
def fuel(tx):
    return text_contains(
        tx,
        "classic tankstelle",
        "tankstelle levern",
        "unicredit w/classic",
        "tankstelle",
        "avia",
        "westfalen tankstelle",
        "hem tankstelle",
        "aral",
        "esso",
        "shell",
        "eni",
        "total service station",
    )


@rule("health/pharmacy")
def pharmacy(tx):
    return text_contains(tx, "apotheke", "vital apotheke")


@rule("health/glasses")
def glasses(tx):
    return text_contains(tx, "apollo optik", "augenoptik")


@rule("health/therapy")
def therapy(tx):
    return text_contains(tx, "therapiezentrum")


@rule("personal/fitness")
def fitness(tx):
    return text_contains(tx, "finion capital", "era gym", "nyx gym")


@rule("personal/haircut")
def haircut(tx):
    return text_contains(tx, "nh stylisten")


@rule("household/garden")
def garden(tx):
    return text_contains(tx, "raiffeisen owl", "concept g", "gaertnerei")


@rule("household/home_improvement")
def home_improvement(tx):
    return text_contains(tx, "hagebau", "westerkamp", "toom", "holz hassfeld", "kramer haustechnik", "tischlerei becker")


@rule("household/cleaning")
def cleaning(tx):
    return text_contains(tx, "gebaeudereinigung", "helpling")


@rule("household/groceries")
def groceries(tx):
    return text_contains(
        tx,
        "e center hartmann",
        "e-center hartmann",
        "e-center",
        "posten boerse",
        "combi verbrauchermarkt",
        "k+k klaas+kock",
        "edeka hartmann",
        "edeka",
        "aktiv markt",
        "aldi",
        "lidl",
        "rewe",
        "getraenke kettler",
        "muller handels",
        "dorfladen",
        "hofladen medewege",
        "hofladen medewegen",
        "moin moin naturkost",
        "e-aktiv steiner",
    )


@rule("shopping/drugstore")
def drugstore(tx):
    return text_contains(tx, "rossmann", "mueller", "müller drogerie", "boots retail", "boots the chemist")


@rule("shopping/discount_store")
def discount_store(tx):
    return text_contains(tx, "tedi", "action germany", "kik")


@rule("family/clothing")
def family_clothing(tx):
    return text_contains(tx, "ernstings")


@rule("shopping/clothing")
def clothing(tx):
    return (
        (payee_is(tx, "Zalando SE") and tx.amount_cents < 0)
        or text_contains(tx, "h&m", "c+a", "only stores germany", "marks spencer", "brormann")
    )


@rule("personal/shoes")
def shoes(tx):
    return text_contains(tx, "deichmann", "schuhhaus")


@rule("food/bakery")
def bakery(tx):
    return text_contains(
        tx,
        "baeckerei k schmidt",
        "baeckerei k. schmidt",
        "baeckerei",
        "backerei",
        "backhaus",
        "landbaeckerei",
        "brot broetchen",
        "karlchens backstube",
        "bertermann",
        "overmeyer",
        "nexi germany",
        "gabler back und snack",
        "steinecke",
    )


@rule("food/fast_food")
def fast_food(tx):
    return text_contains(tx, "mcdonalds")


@rule("food/coffee")
def coffee(tx):
    return text_contains(tx, "espresso house", "starbucks")


@rule("food/restaurants")
def restaurants(tx):
    return text_contains(
        tx,
        "restaurant rhodos",
        "shibuya",
        "hasenstall",
        "burgerbox",
        "burgerliebling",
        "eiscafe alte kantorei",
        "dean + david",
        "losteria",
        "extrablatt",
    )


@rule("food/wine")
def wine(tx):
    return text_contains(tx, "dietrich spreen-ledebur", "sankt urban")


@rule("shopping/amazon")
def amazon(tx):
    return text_contains(
        tx,
        "amazon payments europe",
        "amazon eu s.a r.l.",
        "amazon media",
        "amzn mktp",
        "amazon.de",
        "amazon*",
        "amazon digital germany",
        "www.amazon.",
    )


@rule("household/furniture")
def furniture(tx):
    return text_contains(tx, "ikea")


@rule("shopping/books")
def books(tx):
    return text_contains(tx, "buecher edele")


@rule("shopping/stationery")
def stationery(tx):
    return text_contains(tx, "mcpaper")


@rule("shopping/paypal")
def paypal(tx):
    return text_contains(tx, "paypal europe", "paypal (europe)", "paypal-zahlung", "instant transfer")


@rule("cash/withdrawal")
def cash_withdrawal(tx):
    return payee_is(tx, "Auszahlung GAA") or payee_contains(tx, "volksbank plus", "berliner volksbank")


@rule("household/chimney_sweep")
def chimney_sweep(tx):
    return text_contains(tx, "florian martlage")


# ── New rules for unmatched transactions ──────────────────────────────────────

@rule("professional/coaching")
def coaching(tx):
    return payee_contains(tx, "johannes metzler", "ankush jain")


@rule("investment/currency")
def currency_exchange(tx):
    return payee_is(tx, "Devisen")


@rule("transfer/family")
def family_account_transfer(tx):
    return payee_is(tx, "Lena Hartmann Heinrich Hartmann")


@rule("personal/whiskey")
def whiskey_purchase(tx):
    # Specific whiskey purchases from Richelle Dangremond
    return payee_contains(tx, "richelle dangremond")


@rule("shopping/electronics")
def electronics(tx):
    return text_contains(tx, "media markt", "saturn", "mediamarkt")


@rule("travel/refund")
def travel_refund(tx):
    return payee_contains(tx, "service-now") and tx.amount_cents > 0


@rule("transport/car")
def car_expenses(tx):
    return payee_contains(tx, "fred wehrmann")


@rule("travel/vacation")
def vacation(tx):
    return text_contains(tx, "hof-ferien", "medewege ug")


@rule("family/childcare")
def childcare(tx):
    return text_contains(tx, "diakoniewerk")


@rule("shopping/bicycle")
def bicycle(tx):
    return text_contains(tx, "fahrrad lohmeier", "fahrradlohmeier")


@rule("shopping/jewelry")
def jewelry(tx):
    return text_contains(tx, "juwelier")


@rule("transport/fuel")
def autohof(tx):
    return text_contains(tx, "autohof")
