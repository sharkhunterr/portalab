# ruff: noqa: E501 — a data table of product texts
"""Demo shop catalog (027): every product of the demo Marketplace in one place — the universe themes and
their theme packs, profile cosmetics (banners, frames, name styles, animated backgrounds), ambient
animations, celebrations, notification looks, palettes, animated badges and titles, packs and features.

Prices follow the rarity (common about 100 to 200, rare 250 to 450, epic 500 to 900, legendary from 1000 Coins) and
the rarest need a level; a pack costs about 80 % of what it contains. Copies come from the rarity's supply
unless a product sets its own (interfaces and theme packs have a few more). Demo data only."""

from typing import Any

from portalab.app.demo_economy import LEVEL_REWARDS
from portalab.capabilities.visuals import SOCLE, builtin_interfaces, interface_document
from portalab.modules.marketplace.products.sync import definition as sync_definition

Product = dict[str, Any]
# 028: the interfaces are their packs' — the universes are those in a pack of their own (neither the socle
# nor the base collection), their definitions in their element (``theme.json``)
UNIVERSE_THEMES = tuple(k for k, pack in builtin_interfaces().items() if pack not in (SOCLE, "portalab-base"))


def theme_definition(theme: str) -> dict[str, Any]:
    """An interface's definition, from its built-in pack."""
    return interface_document(theme)


SHOP: list[Product] = []
# 027: products taken out of the shop — archived (no longer sold, their option no longer offered)
RETIRED: tuple[str, ...] = (
    "ambient_cometpass",  # #130: renamed « greatcomet » (a key holding « pass » reads as a secret)
    "banner_live_cometpass",
    "opt_style_upcoming_flip",
    "widget_server_playing",  # free again: it replaced « now playing »
    "widget_calendar",  # free: the calendar is part of every dashboard
)


def _p(
    key: str,
    kind: str,
    price: int | None,
    rarity: str,
    en: str,
    fr: str,
    about_en: str,
    about_fr: str,
    payload: dict[str, Any],
    *,
    collection: str,
    icon: str | None = None,
    featured: bool = False,
    level: int | None = None,
    supply: int | None = None,
    limit: tuple[int, int] | None = None,
    repeatable: bool = False,
    reward_only: bool = False,
    contribution: int | None = None,
    config_required: bool = False,
    season: str | None = None,
) -> None:
    SHOP.append(
        {
            "key": key,
            "type": kind,
            "price": price,
            "rarity": rarity,
            "names": {"en": en, "fr": fr},
            "descriptions": {"en": about_en, "fr": about_fr},
            "payload": payload,
            "collection": collection,
            "icon": icon,
            "featured": featured,
            "level": level,
            "supply": supply,
            "limit": limit,
            "repeatable": repeatable,
            # 027: given by an achievement only — out of sale (« unavailable »), the design stays exclusive
            "reward_only": reward_only,
            # 027: Contribution points needed (for those who take part), and a form to fill once bought
            "contribution": contribution,
            "config_required": config_required,
            # #81: the season it belongs to — its season's booster and pack draw from it
            "season": season,
        }
    )


# --------------------------------------------------------------------------------- badges and titles
for key, label, fr, icon, style, rarity, price, level, en_about, fr_about, supply in (
    ("badge_pioneer", "Pioneer", "Badge Pionnier", "compass", "none", "common", 120, None,
     "For the first members of the portal.", "Pour les premiers membres du portail.", None),
    ("badge_night_owl", "Night owl", "Badge Oiseau de nuit", "moon", "float", "rare", 300, None,
     "For those who watch until dawn.", "Pour celles et ceux qui regardent jusqu'à l'aube.", None),
    ("badge_ghost", "Ghost", "Badge Fantôme", "ghost", "pulse", "legendary", 1300, 8,
     "Only the bravest haunt the portal at night — a single copy exists.",
     "Seuls les plus braves hantent le portail la nuit — un seul exemplaire existe.", 1),
    ("badge_archmage", "Archmage", "Badge Archimage", "wand", "gold", "legendary", 1400, 15,
     "The highest rank of the wizarding school.", "Le plus haut rang de l'école de sorcellerie.", None),
    ("badge_ace_pilot", "Ace pilot", "Badge Pilote d'élite", "rocket", "neon", "epic", 650, 6,
     "Fastest ship of the fleet.", "Le vaisseau le plus rapide de la flotte.", None),
    ("badge_the_one", "The One", "Badge L'Élu", "binary", "glitch", "legendary", 1600, 20,
     "You see the code. One copy, ever.", "Vous voyez le code. Un seul exemplaire, à jamais.", 1),
    ("badge_spice_master", "Spice master", "Badge Maître de l'épice", "sun", "gold", "epic", 700, 6,
     "The spice must flow.", "L'épice doit couler.", None),
    ("badge_survivor", "Survivor", "Badge Survivant", "skull", "pulse", "rare", 350, None,
     "You made it through the night.", "Vous avez survécu à la nuit.", None),
    ("badge_pumpkin_king", "Pumpkin king", "Badge Roi citrouille", "cookie", "flame", "epic", 600, 4,
     "King of the spooky season.", "Le roi de la saison des frissons.", None),
    ("badge_elf", "Head elf", "Badge Lutin en chef", "gift", "shimmer", "rare", 300, None,
     "Wrapping gifts since forever.", "Emballe des cadeaux depuis toujours.", None),
    ("badge_vigilante", "Vigilante", "Badge Justicier", "shield", "shimmer", "epic", 650, 5,
     "Protector of the portal.", "Protecteur du portail.", None),
    ("badge_senpai", "Senpai", "Badge Senpai", "sword", "float", "rare", 350, None,
     "Finally noticed.", "Enfin remarqué.", None),
    ("badge_prankster", "Prankster", "Badge Farceur", "smile", "float", "common", 150, None,
     "Always up to something.", "Toujours un mauvais coup en tête.", None),
    ("badge_golden_blanket", "Golden blanket", "Badge Plaid d'or", "coffee", "pulse", "rare", 300, None,
     "Champion of cosy evenings.", "Champion des soirées douillettes.", None),
    ("badge_engineer", "Engineer", "Badge Ingénieur", "cpu", "neon", "rare", 350, None,
     "Builds the future, one widget at a time.", "Construit le futur, un widget à la fois.", None),
    ("badge_purist", "Purist", "Badge Épure", "diamond", "none", "common", 120, None,
     "Less is more.", "Moins, c'est mieux.", None),
    ("badge_xenobiologist", "Xenobiologist", "Badge Xénobiologiste", "dna", "pulse", "epic", 600, 5,
     "Studies what came from the stars.", "Étudie ce qui vient des étoiles.", None),
    ("badge_arcade_king", "Arcade king", "Badge Roi de l'arcade", "joystick", "rainbow", "epic", 650, 5,
     "High score on every machine.", "Record sur toutes les bornes.", None),
    ("badge_dancing_king", "Dancing king", "Badge Roi de la piste", "disc", "rainbow", "epic", 650, 5,
     "Owns the dance floor.", "Règne sur la piste de danse.", None),
    ("badge_netrunner", "Netrunner", "Badge Netrunner", "fingerprint", "glitch", "epic", 700, 7,
     "Jacked in, never caught.", "Branché, jamais repéré.", None),
    ("badge_sunday_hero", "Sunday hero", "Badge Héros du dimanche", "zap", "rainbow", "rare", 350, None,
     "Saves the day, then takes a nap.", "Sauve la journée, puis fait la sieste.", None),
    ("badge_golden_cinephile", "Golden cinephile", "Badge Cinéphile d'or", "clapperboard", "gold",
     "legendary", 1200, 10, "A life in the dark rooms.", "Une vie dans les salles obscures.", None),
    ("badge_binge_watcher", "Binge-watcher", "Badge Binge-watcher", "popcorn", "flame", "rare", 400, None,
     "One more episode. Then another.", "Encore un épisode. Puis un autre.", None),
    ("badge_dragon_tamer", "Dragon tamer", "Badge Dompteur de dragons", "flame", "flame", "legendary", 1800,
     18, "Few have ever done it — a single copy.", "Rares sont ceux qui y sont arrivés — exemplaire unique.",
     1),
    # 027: VHS, pixel art, terminal, the elements, a light blade
    ("badge_rewinder", "Be kind, rewind", "Badge Rembobineur", "tv", "vhs", "rare", 350, None,
     "You still remember the video club.", "Vous vous souvenez encore du vidéoclub.", None),
    ("badge_8bit_hero", "8-bit hero", "Badge Héros 8 bits", "joystick", "pixel", "rare", 300, None,
     "Three lives and a high score.", "Trois vies et un record.", None),
    ("badge_root", "Root access", "Badge Accès root", "terminal", "terminal", "epic", 600, 5,
     "sudo watch everything.", "sudo regarde tout.", None),
    ("badge_waterbender", "Waterbender", "Badge Maître de l'eau", "droplets", "water", "epic", 650, 6,
     "Flows around every obstacle.", "Contourne chaque obstacle comme l'eau.", None),
    ("badge_airbender", "Airbender", "Badge Maître de l'air", "wind", "wind", "epic", 650, 6,
     "Light as the wind, never in a hurry.", "Léger comme le vent, jamais pressé.", None),
    ("badge_jedi", "Light blade master", "Badge Maître de la lame de lumière", "sword", "saber", "legendary", 1500,
     14, "The force is strong with this one.", "La force est puissante chez celui-ci.", None),
    # 027: the Upside Down
    ("badge_demohunter", "Demogorgon hunter", "Badge Chasseur de Démogorgon", "skull", "veins", "epic", 700, 6,
     "Rolled a natural twenty when it mattered.", "A fait un vingt naturel au bon moment.", None),
    ("badge_upside_survivor", "Upside Down survivor", "Badge Survivant de l'envers", "flashlight", "mirror", "epic",
     650, 5, "Came back from the other side.", "Revenu de l'autre côté.", None),
    ("badge_party", "Party member", "Badge Membre de la bande", "dices", "pulse", "rare", 300, None,
     "Never splits the party.", "Ne sépare jamais la bande.", None),
    ("badge_walkie", "Over and out", "Badge Terminé", "radio", "vhs", "rare", 300, None,
     "Walkie-talkie always on channel six.", "Talkie-walkie toujours sur le canal six.", None),
    # 027: Middle-earth
    ("badge_ringbearer", "Ringbearer", "Badge Porteur de l'Anneau", "gem", "ring", "legendary", 1500, 15,
     "Carried it all the way — a single copy.", "L'a porté jusqu'au bout — exemplaire unique.", 1),
    ("badge_grey_wizard", "Grey wizard", "Badge Magicien gris", "wand", "elven", "epic", 700, 6,
     "Never late, nor early.", "Jamais en retard, ni en avance.", None),
    ("badge_balrog_slayer", "Balrog slayer", "Badge Tueur de Balrog", "flame", "flame", "legendary", 1400, 14,
     "Stood on the bridge and held.", "A tenu sur le pont.", None),
    ("badge_hobbit", "Hobbit of the Shire", "Badge Hobbit de la Comté", "sprout", "float", "common", 150, None,
     "Fond of good food and quiet.", "Amateur de bonne chère et de calme.", None),
    ("badge_pixel_quest", "Pixel quest", "Badge Quête pixel", "sword", "pixel", "rare", 300, None,
     "The fellowship in 8-bit.", "La communauté en 8 bits.", None),
    # 027: VHS and Nova
    # 027: Nostromo
    ("badge_interface_2037", "Interface 2037", "Badge Interface 2037", "terminal", "hazard", "rare", 400, None,
     "Talks to MU/TH/UR without raising its voice.", "Parle à MU/TH/UR sans hausser le ton.", None),
    ("badge_last_survivor", "Last survivor", "Badge Dernier survivant", "radiation", "hazard", "epic", 800, 7,
     "Final report of the commercial starship Nostromo.", "Rapport final du cargo commercial Nostromo.", None),
    ("badge_space_trucker", "Space trucker", "Badge Routier de l'espace", "package", "hazard", "common", 200, None,
     "Twenty million tons of ore, and a share of the bonus.", "Vingt millions de tonnes de minerai, et sa part de la prime.", None),
    ("badge_be_kind_rewind", "Be kind, rewind", "Badge Rembobinez, svp", "disc", "vhs", "common", 200, None,
     "Always brings the tape back rewound.", "Rend toujours la cassette rembobinée.", None),
    ("badge_video_club", "Video club member", "Badge Membre du vidéoclub", "store", "vhs", "rare", 400, None,
     "Card number 0042, valid for life.", "Carte n° 0042, valable à vie.", None),
    ("badge_early_adopter", "Early adopter", "Badge Early adopter", "rocket", "glass", "rare", 400, None,
     "Updates on day one.", "Fait les mises à jour dès le premier jour.", None),
    ("badge_power_user", "Power user", "Badge Utilisateur expert", "zap", "glass", "epic", 800, 6,
     "Knows every shortcut.", "Connaît tous les raccourcis.", None),
    # #78: drawn by the GPU
    ("badge_phoenix_feather", "Phoenix feather", "Badge Plume de phénix", "flame", "blaze", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_thunderbolt", "Thunderbolt", "Badge Éclair", "bolt", "voltage", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_trident", "Trident", "Badge Trident", "waves", "aqua", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_lava_stone", "Lava stone", "Badge Pierre de lave", "mountain", "magma", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_snowflake", "Snowflake", "Badge Flocon", "snowflake", "glacier", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_comet", "Comet", "Badge Comète", "orbit", "galaxy", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_golden_crown", "Golden crown", "Badge Couronne d'or", "crown", "aurum", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_radioactive", "Radioactive", "Badge Radioactif", "radiation", "toxic", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_chrome_chip", "Chrome chip", "Badge Puce chromée", "cpu", "holo", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_grimoire", "Grimoire", "Badge Grimoire", "book", "runes", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_backdoor", "Backdoor", "Badge Porte dérobée", "terminal", "matrix", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_blossom", "Blossom", "Badge Fleur de cerisier", "flower", "sakura", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_watcher", "The watcher", "Badge L'Observateur", "eye", "shadow", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_lollipop", "Lollipop", "Badge Sucette", "candy", "candy", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_north_star", "North star", "Badge Étoile du nord", "star", "aurora", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_atom", "Atom", "Badge Atome", "atom", "plasma", "rare", 800, 6,
     "A badge drawn by the graphics chip.", "Un badge dessiné par la puce graphique.", None),
    ("badge_hourglass", "Hourglass", "Badge Sablier", "hourglass", "chrono", "epic", 1000, 8,
     "A badge seen through a time portal.", "Un badge vu à travers un portail temporel.", None),
):  # fmt: skip
    _p(key, "badge", price, rarity, f"{label} badge", fr, en_about, fr_about,
       {"label": label, "icon": icon, **({"style": style} if style != "none" else {})},
       collection="badges", icon=icon, level=level, supply=supply)  # fmt: skip

for key, label, fr, style, rarity, price, level, en_about, fr_about in (
    ("title_legend", "Legend", "Titre : Légende", "gold", "legendary", 1200, 10,
     "A legendary title under your name.", "Un titre légendaire sous votre nom."),
    ("title_cinephile", "Cinephile", "Titre : Cinéphile", "shimmer", "rare", 350, None,
     "For lovers of the big screen.", "Pour les amoureux du grand écran."),
    ("title_archmage", "Archmage of the portal", "Titre : Archimage du portail", "gold", "legendary", 1300,
     14, "For the greatest wizards.", "Pour les plus grands sorciers."),
    ("title_star_keeper", "Keeper of the stars", "Titre : Gardien des étoiles", "neon", "epic", 650, 6,
     "Watches over the galaxy.", "Veille sur la galaxie."),
    ("title_awakened", "The Awakened", "Titre : L'Éveillé", "glitch", "epic", 700, 7,
     "Took the red pill.", "A pris la pilule rouge."),
    ("title_sand_lord", "Lord of the sands", "Titre : Seigneur des sables", "gold", "epic", 650, 6,
     "Rides the great worms.", "Chevauche les grands vers."),
    ("title_damned", "Damned soul", "Titre : Âme damnée", "flame", "rare", 350, None,
     "Wanders the manor at midnight.", "Erre dans le manoir à minuit."),
    ("title_head_elf", "Head elf", "Titre : Lutin en chef", "shimmer", "rare", 300, None,
     "Runs the toy workshop.", "Dirige l'atelier des jouets."),
    ("title_otaku", "Certified otaku", "Titre : Otaku certifié", "rainbow", "rare", 350, None,
     "Seen every episode, twice.", "A vu chaque épisode, deux fois."),
    ("title_toon_star", "Toon star", "Titre : Star du cartoon", "float", "common", 150, None,
     "Bounces back from anything.", "Rebondit après tout."),
    ("title_nap_champion", "Nap champion", "Titre : Champion·ne de la sieste", "pulse", "common", 150, None,
     "Undefeated on the sofa.", "Invaincu·e sur le canapé."),
    ("title_night_city", "Legend of Night City", "Titre : Légende de Night City", "glitch", "legendary",
     1300, 14, "Everyone in the city knows your name.", "Toute la ville connaît votre nom."),
    ("title_saturday_fever", "Saturday night fever", "Titre : Fièvre du samedi soir", "rainbow", "epic", 600,
     5, "Can't stop dancing.", "Impossible d'arrêter de danser."),
    ("title_neighbourhood_hero", "Neighbourhood hero", "Titre : Héros du quartier", "shimmer", "rare", 350,
     None, "Always there when it matters.", "Toujours là quand il le faut."),
    ("title_less_is_more", "Less is more", "Titre : Moins, c'est mieux", "none", "common", 120, None,
     "Simplicity as a way of life.", "La simplicité comme art de vivre."),
    ("title_mouth_breather", "Mouth breather", "Titre : Respire-par-la-bouche", "mirror", "common", 150, None,
     "Said with affection. Mostly.", "Dit avec affection. En général."),
    ("title_friends_dont_lie", "Friends don't lie", "Titre : Les amis ne mentent pas", "veins", "rare", 350, None,
     "A promise kept.", "Une promesse tenue."),
    ("title_hawkins_hero", "Hero of Hawkins", "Titre : Héros de Hawkins", "neon", "epic", 650, 6,
     "Closed the gate.", "A refermé le portail."),
    ("title_ringbearer", "Ringbearer", "Titre : Porteur de l'Anneau", "ring", "legendary", 1400, 14,
     "One title to rule them all.", "Un titre pour les gouverner tous."),
    ("title_shall_not_pass", "You shall not pass", "Titre : Vous ne passerez pas", "elven", "epic", 700, 6,
     "The bridge holds.", "Le pont tient."),
    ("title_second_breakfast", "Second breakfast champion", "Titre : Champion du second petit-déjeuner", "none",
     "common", 150, None, "What about elevenses?", "Et l'en-cas de onze heures ?"),
    ("title_crew_expendable", "Crew expendable", "Titre : Équipage sacrifiable", "hazard", "rare", 400, None,
     "Special order 937 — read it twice.", "Ordre spécial 937 — à relire deux fois."),
    ("title_perfect_organism", "Perfect organism", "Titre : Organisme parfait", "hazard", "epic", 750, 7,
     "Its structural perfection is matched only by its hostility.", "Sa perfection n'a d'égale que son hostilité."),
    ("title_be_kind_rewind", "Be kind, rewind", "Titre : Rembobinez, svp", "vhs", "common", 200, None,
     "The video store's golden rule.", "La règle d'or du vidéoclub."),
    ("title_late_fees", "Late fees collector", "Titre : Roi des pénalités de retard", "vhs", "rare", 350, None,
     "The tape always comes back… eventually.", "La cassette revient toujours… un jour."),
    ("title_one_more_thing", "One more thing", "Titre : Encore une chose", "glass", "rare", 400, None,
     "Always a last surprise.", "Toujours une dernière surprise."),
    ("title_beta_tester", "Beta tester", "Titre : Bêta-testeur", "glass", "common", 200, None,
     "Tries everything first.", "Essaie tout en premier."),
    # #78: drawn by the GPU
    ("title_firebrand", "Firebrand", "Titre : Boutefeu", "blaze", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_stormcaller", "Stormcaller", "Titre : Invocateur d'orages", "voltage", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_deep_diver", "Deep diver", "Titre : Plongeur des abysses", "aqua", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_volcano_heart", "Heart of the volcano", "Titre : Cœur du volcan", "magma", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_frostborn", "Frostborn", "Titre : Né du givre", "glacier", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_stargazer", "Stargazer", "Titre : Contemplateur d'étoiles", "galaxy", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_golden_one", "The Golden One", "Titre : L'Être doré", "aurum", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_mad_scientist", "Mad scientist", "Titre : Savant fou", "toxic", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_netrunner", "Netrunner", "Titre : Netrunner", "holo", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_runemaster", "Runemaster", "Titre : Maître des runes", "runes", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_root_access", "Root access", "Titre : Accès root", "matrix", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_spring_spirit", "Spring spirit", "Titre : Esprit du printemps", "sakura", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_shadow_walker", "Shadow walker", "Titre : Marcheur des ombres", "shadow", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_sugar_rush", "Sugar rush", "Titre : Overdose de sucre", "candy", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_northern_light", "Northern light", "Titre : Lumière du nord", "aurora", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_plasma_core", "Plasma core", "Titre : Cœur de plasma", "plasma", "rare", 900, 6,
     "A title drawn by the graphics chip.", "Un titre dessiné par la puce graphique."),
    ("title_time_traveller", "Time traveller", "Titre : Voyageur temporel", "chrono", "epic", 1100, 8,
     "A title seen through a time portal.", "Un titre vu à travers un portail temporel."),
):  # fmt: skip
    _p(key, "title", price, rarity, label if key == "title_cinephile" else f"Title: {label}", fr, en_about,
       fr_about, {"label": label, **({"style": style} if style != "none" else {})}, collection="titles",
       icon="trophy", level=level)  # fmt: skip

# --------------------------------------------------------------------------------- notification looks
for key, kind, field, value, en, fr, rarity, price, en_about, fr_about in (
    ("notif_glass", "notification_style", "style", "glass", "Frosted glass notifications",
     "Notifications verre dépoli", "rare", 300, "Translucent notifications that blur what is behind them.",
     "Des notifications translucides qui floutent ce qu'il y a derrière."),
    ("notif_neon", "notification_style", "style", "neon", "Neon notifications", "Notifications néon", "epic",
     550, "Glowing outlines in the colour of each notification.", "Des contours lumineux de la couleur de chaque notification."),
    ("notif_comic", "notification_style", "style", "comic", "Comic notifications", "Notifications BD", "rare",
     300, "Thick ink, a hard shadow and a comic title.", "Encre épaisse, ombre franche et titre de BD."),
    ("notif_terminal", "notification_style", "style", "terminal", "Terminal notifications",
     "Notifications terminal", "rare", 300, "Green on black, like a console.", "Vert sur noir, comme une console."),
    ("notif_parchment", "notification_style", "style", "parchment", "Parchment notifications",
     "Notifications parchemin", "epic", 550, "Old paper and a serif title.", "Vieux papier et titre à empattements."),
    ("notif_hologram", "notification_style", "style", "hologram", "Hologram notifications",
     "Notifications hologramme", "epic", 650, "A shifting iridescent border.", "Une bordure irisée qui ondule."),
    ("notif_pixel", "notification_style", "style", "pixel", "Pixel notifications", "Notifications pixel",
     "rare", 300, "8-bit borders and font.", "Bordures et police 8 bits."),
    ("notif_paper", "notification_style", "style", "paper", "Sticky note notifications",
     "Notifications post-it", "common", 150, "A paper note taped to the corner.", "Une note de papier scotchée dans le coin."),
    ("notif_bounce", "notification_animation", "animation", "bounce", "Bouncing notifications",
     "Notifs rebondissantes", "common", 150, "Notifications arrive with a little bounce.", "Les notifications arrivent avec un petit rebond."),
    ("notif_flip", "notification_animation", "animation", "flip", "Flipping notifications",
     "Notifications qui pivotent", "rare", 300, "Notifications flip into view like a card.", "Les notifications pivotent comme une carte."),
    ("notif_swing", "notification_animation", "animation", "swing", "Swinging notifications",
     "Notifications balancier", "rare", 250, "Notifications swing in like a hanging sign.", "Les notifications se balancent comme une enseigne."),
    ("notif_glitch", "notification_animation", "animation", "glitch", "Glitching notifications",
     "Notifications glitch", "rare", 300, "They arrive scrambled, then lock in.", "Elles arrivent brouillées, puis se figent."),
    ("notif_drop", "notification_animation", "animation", "drop", "Dropping notifications",
     "Notifications qui tombent", "common", 150, "They fall from above with a bounce.", "Elles tombent d'en haut avec un rebond."),
    ("notif_spiral", "notification_animation", "animation", "spiral", "Spiral notifications",
     "Notifications spirale", "rare", 300, "They spin in from nowhere.", "Elles arrivent en tournoyant."),
    ("notif_slam", "notification_animation", "animation", "slam", "Slamming notifications",
     "Notifications impact", "epic", 500, "They slam onto the screen.", "Elles s'abattent sur l'écran."),
    # 027: shapes
    ("notif_square", "notification_style", "style", "square", "Square tile notifications",
     "Notifications tuile carrée", "rare", 300, "A square tile: a big icon and the title under it.",
     "Une tuile carrée : une grande icône et le titre dessous."),
    ("notif_circle", "notification_style", "style", "circle", "Bubble notifications", "Notifications bulle",
     "epic", 550, "A round bubble with a glowing ring in the colour of the notification.",
     "Une bulle ronde cerclée de la couleur de la notification."),
    ("notif_cloud", "notification_style", "style", "cloud", "Cloud notifications", "Notifications nuage",
     "epic", 600, "A thought cloud with its little puffs.", "Un nuage de pensée avec ses petites bulles."),
    ("notif_ticket", "notification_style", "style", "ticket", "Ticket notifications", "Notifications ticket",
     "rare", 350, "A notched ticket with its tear line.", "Un ticket échancré avec sa ligne de découpe."),
    ("notif_tag", "notification_style", "style", "tag", "Label notifications", "Notifications étiquette",
     "rare", 300, "A luggage label with its eyelet.", "Une étiquette de bagage avec son œillet."),
    ("notif_split", "notification_style", "style", "split", "Two-tone notifications",
     "Notifications bicolores", "common", 180, "The icon on a coloured band, the text beside it.",
     "L'icône sur une bande colorée, le texte à côté."),
    ("notif_rise", "notification_animation", "animation", "rise", "Rising notifications",
     "Notifications qui s'envolent", "common", 150, "They float up from below, softly.",
     "Elles montent doucement depuis le bas."),
    ("notif_wipe", "notification_animation", "animation", "wipe", "Wiping notifications",
     "Notifications balayage", "rare", 250, "They are revealed from one side to the other.",
     "Elles se dévoilent d'un côté à l'autre."),
    ("notif_focus", "notification_animation", "animation", "focus", "Focusing notifications",
     "Notifications mise au point", "rare", 250, "Blurred at first, then sharp.", "Floues d'abord, puis nettes."),
    ("notif_jelly", "notification_animation", "animation", "jelly", "Jelly notifications",
     "Notifications gelée", "rare", 300, "They squash and stretch into place.", "Elles s'écrasent et s'étirent avant de se poser."),
    ("notif_shake", "notification_animation", "animation", "shake", "Shaking notifications",
     "Notifications secousse", "epic", 450, "They arrive with a shake — hard to miss.",
     "Elles arrivent en tremblant — impossible de les manquer."),
    # 027: universes
    ("notif_saga", "notification_style", "style", "saga", "Space saga notifications",
     "Notifications saga spatiale", "legendary", 1000, "Bold yellow capitals tilted over a starfield, like an opening crawl.",
     "Des capitales jaunes inclinées sur un champ d'étoiles, comme un générique d'ouverture."),
    ("notif_pirate", "notification_style", "style", "pirate", "Pirate notifications", "Notifications pirate",
     "epic", 650, "A weathered plank, brass rivets and a rope edge.", "Une planche patinée, des rivets de laiton et un bord en corde."),
    ("notif_manga", "notification_style", "style", "manga", "Manga panel notifications",
     "Notifications case de manga", "epic", 600, "Screentone, speed lines and a heavy ink frame cut on a slant.",
     "Trame, lignes de vitesse et un cadre à l'encre coupé en biais."),
    ("notif_noir", "notification_style", "style", "noir", "Film noir notifications", "Notifications film noir",
     "epic", 600, "Black and white, hard light — only its colour bleeds in.",
     "Noir et blanc, lumière crue — seule sa couleur transparaît."),
    ("notif_vhs", "notification_style", "style", "vhs", "VHS notifications", "Notifications VHS", "rare", 400,
     "A tape on pause: scanlines, a colour split and PLAY in the corner.",
     "Une cassette en pause : lignes de balayage, couleurs décalées et PLAY dans le coin."),
    ("notif_filmwipe", "notification_animation", "animation", "filmwipe", "Film wipe notifications",
     "Notifications volet de film", "epic", 550, "A hard-edged wipe from right to left, like a scene change.",
     "Un volet net de droite à gauche, comme un changement de plan."),
    ("notif_iris", "notification_animation", "animation", "iris", "Iris notifications", "Notifications iris",
     "rare", 300, "They open in a circle, like an old film.", "Elles s'ouvrent en cercle, comme un vieux film."),
    ("notif_air", "notification_animation", "animation", "air", "Air notifications", "Notifications air",
     "epic", 500, "A gust brings them in, still blurred by the wind.", "Une bourrasque les apporte, encore floues de vent."),
    ("notif_water", "notification_animation", "animation", "water", "Water notifications", "Notifications eau",
     "epic", 500, "They well up from below and settle with a ripple.", "Elles jaillissent d'en bas et se posent en ondulant."),
    ("notif_earth", "notification_animation", "animation", "earth", "Earth notifications", "Notifications terre",
     "epic", 500, "They rise like a slab of rock and land with a jolt.", "Elles surgissent comme une dalle de roche et retombent d'un coup."),
    ("notif_fire", "notification_animation", "animation", "fire", "Fire notifications", "Notifications feu",
     "epic", 500, "They flare up from embers, glowing, then cool down.", "Elles s'embrasent depuis les braises, rougeoient, puis refroidissent."),
    ("notif_blackhole", "notification_animation", "animation", "blackhole", "Black hole notifications",
     "Notifications trou noir", "legendary", 1100, "They spin out of a singularity — and are sucked back in when they go.",
     "Elles jaillissent d'une singularité en tournoyant — et y sont aspirées en partant."),
    ("notif_melt", "notification_animation", "animation", "melt", "Melting notifications", "Notifications fondantes",
     "epic", 550, "They drip into shape — and melt away when they go.", "Elles prennent forme en coulant — et fondent en partant."),
    ("notif_kapow", "notification_animation", "animation", "kapow", "KAPOW! notifications", "Notifications KAPOW !",
     "epic", 600, "A comic punch: they land with a « KAPOW! » burst — and a « POOF » when they go.",
     "Un coup de poing de BD : elles arrivent dans un « KAPOW ! » — et repartent dans un « POUF »."),
    ("notif_portal", "notification_animation", "animation", "portal", "Portal notifications", "Notifications portail",
     "legendary", 1000, "They step out of a swirling dimensional portal — and back into it.",
     "Elles sortent d'un portail dimensionnel tourbillonnant — et y retournent."),
    ("notif_upsidedown", "notification_style", "style", "upsidedown", "Upside Down notifications",
     "Notifications monde à l'envers", "epic", 700, "The title sequence: hollow red neon letters closing in between two growing bars, the message typed like a lab report.",
     "Le générique : des lettres de néon rouge creuses qui se resserrent entre deux barres, le message tapé comme un rapport de labo."),
    ("notif_flipup", "notification_animation", "animation", "flipup", "Flip-up notifications",
     "Notifications retournées", "epic", 600, "They rise from below and flip up, as if turned over from the other side.",
     "Elles montent d'en bas et se retournent, comme venues de l'autre côté."),
    ("notif_elven", "notification_style", "style", "elven", "Elven notifications", "Notifications elfiques",
     "rare", 400, "A silver-green leaf written in fine capitals.", "Une feuille vert argent écrite en fines capitales."),
    ("notif_onering", "notification_style", "style", "onering", "One Ring notifications",
     "Notifications de l'Anneau", "legendary", 1000, "Black, inside a turning golden ring.", "Noires, dans un anneau d'or qui tourne."),
    ("notif_balrog", "notification_animation", "animation", "balrog", "Balrog notifications", "Notifications Balrog",
     "epic", 650, "They rise from fire, wings of shadow opening.", "Elles surgissent du feu, des ailes d'ombre s'ouvrant."),
    ("notif_eye", "notification_animation", "animation", "eye", "Eye notifications", "Notifications de l'Œil",
     "epic", 600, "They open like a fiery slit eye.", "Elles s'ouvrent comme un œil de feu."),
    ("notif_tracking", "notification_animation", "animation", "tracking", "Bad tracking notifications",
     "Notifications mauvais tracking", "rare", 450, "They arrive torn by bad tracking and leave like a TV switched off.",
     "Elles arrivent déchirées par un mauvais tracking et repartent comme une télé qu'on éteint."),
    ("notif_nostromo", "notification_style", "style", "nostromo", "Onboard computer notifications",
     "Notifications ordinateur de bord", "epic", 650,
     "MU/TH/UR's transmissions: an amber strip, phosphor text, corner brackets and a blinking cursor.",
     "Les transmissions de MU/TH/UR : bandeau ambre, texte phosphore, coins de cadre et curseur qui clignote."),
    ("notif_uplink", "notification_animation", "animation", "uplink", "Uplink notifications",
     "Notifications liaison montante", "rare", 450, "Received line by line with a flicker; they cut out like a monitor.",
     "Reçues ligne par ligne avec un scintillement ; elles s'éteignent comme un moniteur."),
    ("notif_island", "notification_style", "style", "island", "Island notifications", "Notifications îlot",
     "epic", 650, "A black capsule at the top of the screen, like a phone's island.",
     "Une capsule noire en haut de l'écran, comme l'îlot d'un téléphone."),
    ("notif_morph", "notification_animation", "animation", "morph", "Morph notifications",
     "Notifications métamorphose", "rare", 450, "A small capsule swells into the message.",
     "Une petite capsule s'agrandit pour devenir le message."),
    # #78: drawn by the GPU
    ("notif_blaze", "notification_style", "style", "blaze", "Blazing notifications",
     "Notifications embrasées", "epic", 1100, "Flames lick round each notification. Drawn by the graphics chip.",
     "Des flammes lèchent chaque notification. Dessinées par la puce graphique."),
    ("notif_voltage", "notification_style", "style", "voltage", "Charged notifications",
     "Notifications chargées", "epic", 1100, "Arcs crawl round each notification and leap out. Drawn by the graphics chip.",
     "Des arcs électriques courent sur chaque notification et s'en échappent. Dessinées par la puce graphique."),
    ("notif_aqua", "notification_style", "style", "aqua", "Tidal notifications",
     "Notifications marée", "epic", 1100, "Water sloshing inside each notification. Drawn by the graphics chip.",
     "De l'eau qui tangue dans chaque notification. Dessinées par la puce graphique."),
    ("notif_magma", "notification_style", "style", "magma", "Molten notifications",
     "Notifications en fusion", "epic", 1100, "Lava flowing under a cracked crust. Drawn by the graphics chip.",
     "De la lave qui coule sous une croûte fissurée. Dessinées par la puce graphique."),
    ("notif_glacier", "notification_style", "style", "glacier", "Frozen notifications",
     "Notifications gelées", "epic", 1100, "Ice facets and growing frost. Drawn by the graphics chip.",
     "Des facettes de glace et du givre qui pousse. Dessinées par la puce graphique."),
    ("notif_galaxy", "notification_style", "style", "galaxy", "Cosmic notifications",
     "Notifications cosmiques", "epic", 1100, "A galaxy turning behind each notification. Drawn by the graphics chip.",
     "Une galaxie qui tourne derrière chaque notification. Dessinées par la puce graphique."),
    ("notif_aurum", "notification_style", "style", "aurum", "Gilded notifications",
     "Notifications dorées", "epic", 1100, "Liquid gold behind each notification. Drawn by the graphics chip.",
     "De l'or liquide derrière chaque notification. Dessinées par la puce graphique."),
    ("notif_toxic", "notification_style", "style", "toxic", "Toxic notifications",
     "Notifications toxiques", "epic", 1100, "Acid bubbling, drops dripping. Drawn by the graphics chip.",
     "De l'acide qui bouillonne, des gouttes qui tombent. Dessinées par la puce graphique."),
    ("notif_holo", "notification_style", "style", "holo", "Holographic notifications",
     "Notifications holographiques", "epic", 1100, "Rainbow foil and a neon edge. Drawn by the graphics chip.",
     "Un film arc-en-ciel et un bord néon. Dessinées par la puce graphique."),
    ("notif_runes", "notification_style", "style", "runes", "Arcane notifications",
     "Notifications arcaniques", "epic", 1100, "Runes orbiting each notification. Drawn by the graphics chip.",
     "Des runes qui orbitent autour de chaque notification. Dessinées par la puce graphique."),
    ("notif_matrix", "notification_style", "style", "matrix", "Hacked notifications",
     "Notifications piratées", "epic", 1100, "Digital rain behind each notification. Drawn by the graphics chip.",
     "De la pluie numérique derrière chaque notification. Dessinées par la puce graphique."),
    ("notif_sakura", "notification_style", "style", "sakura", "Sakura notifications",
     "Notifications sakura", "epic", 1100, "Petals drifting across each notification. Drawn by the graphics chip.",
     "Des pétales qui traversent chaque notification. Dessinées par la puce graphique."),
    ("notif_shadow", "notification_style", "style", "shadow", "Shadowy notifications",
     "Notifications ténébreuses", "epic", 1100, "Smoke and eyes in the dark. Drawn by the graphics chip.",
     "De la fumée et des yeux dans le noir. Dessinées par la puce graphique."),
    ("notif_candy", "notification_style", "style", "candy", "Candy notifications",
     "Notifications bonbon", "epic", 1100, "Swirling candy stripes and sprinkles. Drawn by the graphics chip.",
     "Des rayures de bonbon et des vermicelles. Dessinées par la puce graphique."),
    ("notif_aurora", "notification_style", "style", "aurora", "Aurora notifications",
     "Notifications aurore", "epic", 1100, "Northern lights behind each notification. Drawn by the graphics chip.",
     "Des aurores boréales derrière chaque notification. Dessinées par la puce graphique."),
    ("notif_plasma", "notification_style", "style", "plasma", "Plasma notifications",
     "Notifications plasma", "epic", 1100, "Plasma filaments behind each notification. Drawn by the graphics chip.",
     "Des filaments de plasma derrière chaque notification. Dessinées par la puce graphique."),
    ("notif_chrono", "notification_style", "style", "chrono", "Time portal notifications",
     "Notifications portail temporel", "legendary", 1500,
     "Each notification steps out of a triangular time portal that opens, then closes behind it as it leaves.",
     "Chaque notification sort d'un portail temporel triangulaire qui s'ouvre, puis se referme derrière elle quand elle part."),
    ("notif_ignite", "notification_animation", "animation", "ignite", "Ignite notifications",
     "Notifications embrasement", "epic", 1100, "They burst out of flames — and go up in flames. Drawn by the graphics chip.",
     "Elles jaillissent des flammes — et partent en fumée. Dessinées par la puce graphique."),
    ("notif_surge", "notification_animation", "animation", "surge", "Power surge notifications",
     "Notifications surtension", "epic", 1100, "Electricity crackles round them as they arrive and leave. Drawn by the graphics chip.",
     "L'électricité crépite autour d'elles à l'arrivée et au départ. Dessinées par la puce graphique."),
    ("notif_splash", "notification_animation", "animation", "splash", "Splash notifications",
     "Notifications éclaboussure", "epic", 1000, "They surface from a splash of water — and sink back. Drawn by the graphics chip.",
     "Elles surgissent d'une éclaboussure — et y replongent. Dessinées par la puce graphique."),
    ("notif_frostbite", "notification_animation", "animation", "frostbite", "Frostbite notifications",
     "Notifications morsure du givre", "epic", 1000, "Frost grows round them, then shatters as they go. Drawn by the graphics chip.",
     "Le givre les entoure, puis se brise quand elles partent. Dessinées par la puce graphique."),
    ("notif_stardust", "notification_animation", "animation", "stardust", "Stardust notifications",
     "Notifications poussière d'étoiles", "epic", 1100, "A galaxy swirls them in and out. Drawn by the graphics chip.",
     "Une galaxie les fait apparaître et disparaître en tourbillonnant. Dessinées par la puce graphique."),
    ("notif_hex", "notification_animation", "animation", "hex", "Hex notifications",
     "Notifications sortilège", "epic", 1100, "Runes flare round them as they are summoned and dismissed. Drawn by the graphics chip.",
     "Des runes s'embrasent quand elles sont invoquées puis renvoyées. Dessinées par la puce graphique."),
    ("notif_decrypt", "notification_animation", "animation", "decrypt", "Decrypt notifications",
     "Notifications décryptage", "epic", 1000, "Digital rain decrypts them — and encrypts them away. Drawn by the graphics chip.",
     "La pluie numérique les décrypte — puis les chiffre en partant. Dessinées par la puce graphique."),
    ("notif_petalfall", "notification_animation", "animation", "petalfall", "Petal fall notifications",
     "Notifications chute de pétales", "rare", 900, "A gust of petals brings them and takes them away. Drawn by the graphics chip.",
     "Une bourrasque de pétales les apporte et les emporte. Dessinées par la puce graphique."),
    ("notif_eclipse", "notification_animation", "animation", "eclipse", "Eclipse notifications",
     "Notifications éclipse", "epic", 1100, "Black smoke parts to let them out — and swallows them. Drawn by the graphics chip.",
     "Une fumée noire s'écarte pour les laisser sortir — et les avale. Dessinées par la puce graphique."),
    ("notif_warp", "notification_animation", "animation", "warp", "Time warp notifications",
     "Notifications distorsion temporelle", "legendary", 1500, "They step out of a triangular time portal that closes behind them. Drawn by the graphics chip.",
     "Elles sortent d'un portail temporel triangulaire qui se referme derrière elles. Dessinées par la puce graphique."),
):  # fmt: skip
    _p(key, kind, price, rarity, en, fr, en_about, fr_about, {field: value}, collection="looks",
       icon="bell" if kind == "notification_style" else "sparkles")  # fmt: skip

# --------------------------------------------------------------------------------- celebrations (rewards)
for key, value, en, fr, rarity, price, level in (
    ("effect_confetti", "confetti", "Confetti", "Confettis", "rare", 250, None),
    ("effect_aurora", "stars", "Shooting stars", "Étoiles filantes", "epic", 550, 4),
    ("effect_pumpkin", "bats", "Bat swarm", "Nuée de chauves-souris", "rare", 300, None),
    ("effect_snow", "snow", "Snowflakes", "Flocons", "rare", 300, None),
    ("effect_pixels", "pixels", "Pixel burst", "Explosion de pixels", "rare", 300, None),
    ("effect_hearts", "hearts", "Hearts", "Cœurs", "common", 180, None),
    ("effect_coins", "coins", "Coin shower", "Pluie de pièces", "epic", 650, 6),
    ("effect_lightning", "lightning", "Lightning", "Éclairs", "epic", 600, 5),
    ("effect_petals", "petals", "Petals", "Pétales", "rare", 300, None),
    ("effect_bubbles", "bubbles", "Bubbles", "Bulles", "common", 180, None),
    ("effect_assemble", "assemble", "Pixel rain", "Pluie de pixels", "epic", 700, 6),
    ("effect_burn", "burn", "Burning bubble", "Bulle en flammes", "epic", 750, 7),
    ("effect_shatter", "shatter", "Shatter", "Éclats", "rare", 400, None),
    ("effect_freeze", "freeze", "Freeze", "Gel", "rare", 400, None),
    ("effect_glitch", "glitch", "Glitch", "Glitch", "rare", 450, None),
    ("effect_portal", "portal", "Portal", "Portail", "legendary", 1200, 12),
    ("effect_flicker", "flicker", "Christmas lights", "Guirlande", "rare", 400, None),
    ("effect_fireworks", "fireworks", "Wizard's fireworks", "Feux d'artifice du magicien", "epic", 700, 6),
    ("effect_rewind", "rewind", "Rewind", "Rembobinage", "rare", 400, None),
    ("effect_bloom", "bloom", "Bloom", "Éclosion", "rare", 450, None),
    ("effect_tracker", "tracker", "Motion tracker", "Détecteur de mouvement", "epic", 650, 6),
    ("effect_nova", "nova", "Supernova", "Supernova", "legendary", 1600, 12),
    ("effect_goldshower", "goldshower", "Gold shower", "Pluie d'or", "epic", 1200, 8),
    ("effect_petalstorm", "petalstorm", "Petal storm", "Tempête de pétales", "epic", 1100, 8),
    ("effect_rebirth", "rebirth", "Phoenix rebirth", "Renaissance du phénix", "legendary", 1600, 12),
    ("effect_stormstrike", "stormstrike", "Storm strike", "Coup de tonnerre", "epic", 1200, 8),
    ("effect_skyveil", "skyveil", "Aurora veil", "Voile d'aurore", "epic", 1200, 8),
    ("effect_arcana", "arcana", "Arcana", "Arcanes", "epic", 1200, 8),
    ("effect_timerift", "timerift", "Time rift", "Faille temporelle", "legendary", 1800, 12),
):  # fmt: skip
    _p(key, "effect", price, rarity, f"{en} celebration", f"Célébration {fr.lower()}",
       f"{en} burst out when you earn a reward or level up.",
       f"{fr} jaillissent quand vous gagnez une récompense ou un niveau.", {"effect": value},
       collection="celebrations", icon="party", level=level)  # fmt: skip

# --------------------------------------------------------------------------------- ambient animations (portal)
AMBIENT_NAMES = {
    "snow": ("Snowfall", "Chute de neige", "rare", 400),
    "embers": ("Embers", "Braises", "rare", 400),
    "code-rain": ("Code rain", "Pluie de code", "epic", 750),
    "fireflies": ("Fireflies", "Lucioles", "common", 200),
    "starfield": ("Starry sky", "Ciel étoilé", "rare", 400),
    "warp": ("Hyperspace", "Hyperespace", "epic", 700),
    "petals": ("Sakura petals", "Pétales de sakura", "rare", 400),
    "bats": ("Bats", "Chauves-souris", "epic", 650),
    "bubbles": ("Bubbles", "Bulles", "common", 200),
    "rain": ("Neon rain", "Pluie néon", "rare", 450),
    "sparkles": ("Sparkles", "Étincelles", "common", 200),
    "disco": ("Disco lights", "Lumières disco", "epic", 750),
    "fog": ("Fog", "Brume", "rare", 400),
    "sand": ("Sandstorm", "Vent de sable", "rare", 400),
    "leaves": ("Autumn leaves", "Feuilles d'automne", "rare", 400),
    "hearts": ("Floating hearts", "Cœurs flottants", "rare", 350),
    "glitch": ("Glitch", "Glitch", "epic", 650),
    "lights": ("Fairy lights", "Guirlande lumineuse", "rare", 350),
    "spores": ("Glowing spores", "Spores lumineuses", "epic", 650),
    "aurora": ("Northern lights", "Aurore boréale", "legendary", 1100),
    "vhs": ("VHS tape", "Cassette VHS", "rare", 450),
    "wind": ("Wind", "Vent", "rare", 400),
    "tide": ("Tide", "Marée", "epic", 650),
    "lanterns": ("Sky lanterns", "Lanternes célestes", "epic", 700),
    "pixelsky": ("8-bit sky", "Ciel 8 bits", "rare", 450),
    "upsidedown": ("Upside Down spores", "Spores du monde à l'envers", "epic", 750),
    "veins": ("Red veins", "Veines rouges", "epic", 650),
    "meadow": ("Shire meadow", "Prairie de la Comté", "rare", 400),
    "ash": ("Ash of Mordor", "Cendres du Mordor", "rare", 450),
    "bokeh": ("Bokeh", "Bokeh", "rare", 450),
    "nostromo": ("Onboard computer", "Ordinateur de bord", "epic", 700),
    # #68: premium ambiences drawn by the GPU (shaders) or as particles
    "inferno": ("Inferno", "Brasier", "epic", 1300),
    "thunderstorm": ("Thunderstorm", "Orage", "legendary", 1700),
    "sandstorm": ("Desert storm", "Tempête du désert", "epic", 1200),
    "polar": ("Polar lights", "Lumières polaires", "epic", 1200),
    "cosmos": ("Deep space", "Espace profond", "epic", 1200),
    "abyss": ("Abyss", "Abysses", "epic", 1200),
    "matrix": ("Digital rain", "Pluie numérique", "epic", 1200),
    "downpour": ("Downpour", "Averse", "rare", 800),
    "blizzard": ("Blizzard", "Blizzard", "rare", 800),
    "fireworks": ("Fireworks", "Feu d'artifice", "rare", 900),
    "mesh": ("Constellation mesh", "Maillage constellation", "rare", 700),
    "meshwave": ("Moving mesh network", "Réseau maillé en mouvement", "epic", 1300),
    "volcano": ("Volcano", "Volcan", "legendary", 1700),
    "blackhole": ("Black hole", "Trou noir", "legendary", 1800),
    "reef": ("Under the surface", "Sous la surface", "legendary", 1600),
    "firestorm": ("Firestorm", "Tempête de feu", "epic", 1300),
    "whiteout": ("Night blizzard", "Blizzard nocturne", "epic", 1200),
    "liquidmetal": ("Liquid metal", "Métal liquide", "epic", 1300),
    "plasma": ("Plasma storm", "Tempête de plasma", "epic", 1300),
    "forest": ("Living forest", "Forêt vivante", "epic", 1200),
    "neoncity": ("Neon city", "Cité néon", "legendary", 1600),
    "weather": ("Live weather", "Météo en direct", "legendary", 1800),
    "haunted": ("Haunting", "Hantise", "epic", 1200),
    "darkness": ("Darkness", "Ténèbres", "epic", 1300),
    "lostsignal": ("Lost signal", "Signal perdu", "rare", 800),
    "garland": ("String lights", "Guirlandes", "rare", 800),
    "christmasnight": ("Christmas night", "Nuit de Noël", "epic", 1300),
    "hearth": ("By the fire", "Coin du feu", "epic", 1100),
    # #68: warm, cheerful and pixel-art ambiences
    "goldenhour": ("Golden hour", "Heure dorée", "epic", 1100),
    "windowrain": ("Rain on the window", "Pluie à la fenêtre", "epic", 1100),
    "summerfield": ("Summer field", "Champ d'été", "rare", 900),
    "soapbubbles": ("Soap bubbles", "Bulles de savon", "rare", 700),
    "skylanterns": ("Lanterns over the lake", "Lanternes sur le lac", "epic", 1200),
    "autumnlane": ("Autumn lane", "Allée d'automne", "rare", 900),
    "pixelcamp": ("Pixel campfire", "Feu de camp pixel", "epic", 1200),
    "pixelbeach": ("Pixel sunset beach", "Plage pixel au couchant", "epic", 1200),
    "pixelballoons": ("Pixel balloons", "Montgolfières pixel", "epic", 1200),
    # #68: cosy ambiences — only warmth, no scenery
    "amberglow": ("Amber glow", "Lueur ambrée", "rare", 700),
    "candlelight": ("Candlelight", "Lueur de bougies", "rare", 800),
    "steam": ("Warm steam", "Vapeur chaude", "common", 500),
    "fairybokeh": ("Soft fairy lights", "Lumières douces", "rare", 700),
    "warmsilk": ("Warm silk", "Soie chaude", "rare", 800),
    "honey": ("Honey", "Miel", "rare", 800),
    "knit": ("Cosy knit", "Tricot douillet", "rare", 900),
    "paintmix": ("Stirred paint", "Peinture mêlée", "rare", 800),
    "acrylicpour": ("Acrylic pour", "Coulée acrylique", "epic", 1100),
    "watercolor": ("Warm watercolour", "Aquarelle chaude", "rare", 800),
    "marbling": ("Marbled paper", "Papier marbré", "rare", 800),
    "poppaint": ("Pop paint", "Peinture pop", "rare", 800),
    "poppour": ("Pop pour", "Coulée pop", "epic", 1100),
    "popwatercolor": ("Pop watercolour", "Aquarelle pop", "rare", 800),
    "popmarbling": ("Pop marbling", "Marbré pop", "rare", 800),
    "lavalamp": ("Lava lamp", "Lampe à lave", "legendary", 1600),
    "impasto": ("Thick paint", "Peinture épaisse", "legendary", 1700),
    "paintribbon": ("Paint ribbons", "Rubans de peinture", "epic", 1200),
}
for value, (en, fr, rarity, price) in AMBIENT_NAMES.items():
    _p(f"ambient_{value.replace('-', '_')}", "ambient", price, rarity, f"{en} ambience", f"Ambiance {fr.lower()}",
       f"{en} drifting behind the whole portal. Chosen in Appearance; off with reduced motion.",
       f"{fr} derrière tout le portail. À choisir dans Apparence ; coupé si les animations sont réduites.",
       {"ambient": value}, collection="ambients", icon="snowflake",
       level=10 if rarity == "legendary" else 5 if rarity == "epic" else None)  # fmt: skip

# --------------------------------------------------------------------------------- animated banners (#79)
# the profile's banner can be animated — an ambience playing inside it, for every visitor to see (the
# animated background behind the portal stays each member's own choice, in Appearance)
LIVE_BANNERS = ("starfield", "code-rain", "snow", "embers", "petals", "aurora", "disco", "bats", "fireflies",
                "rain", "spores", "hearts", "upsidedown", "veins", "meadow", "ash", "vhs", "bokeh", "nostromo")  # fmt: skip
HD_LIVE_BANNERS = ("inferno", "thunderstorm", "reef", "volcano", "whiteout", "blackhole", "liquidmetal", "neoncity",
                   "matrix", "goldenhour", "darkness", "lavalamp", "polar", "plasma")  # fmt: skip
for value in LIVE_BANNERS:
    en, fr, rarity, price = AMBIENT_NAMES[value]
    rarity = "legendary" if value == "aurora" else "epic" if rarity in ("epic", "legendary") else "rare"
    _p(f"banner_live_{value.replace('-', '_')}", "profile_banner", {"rare": 450, "epic": 800, "legendary": 1300}[rarity],
       rarity, f"{en} animated banner", f"Bannière animée {fr.lower()}",
       f"{en} playing in your profile's banner, for every visitor to see.",
       f"{fr} dans la bannière de votre profil, pour tous vos visiteurs.", {"banner": f"live-{value}"},
       collection="profile", icon="image", level=12 if rarity == "legendary" else 6 if rarity == "epic" else None)  # fmt: skip
for value in HD_LIVE_BANNERS:  # #78: drawn by the graphics chip
    en, fr, rarity, price = AMBIENT_NAMES[value]
    _p(f"banner_live_{value}", "profile_banner", 1100, "epic", f"{en} animated banner", f"Bannière animée {fr.lower()}",
       f"{en} in your profile's banner, drawn by the graphics chip, for every visitor to see.",
       f"{fr} dans la bannière de votre profil, dessiné par la puce graphique, pour tous vos visiteurs.",
       {"banner": f"live-{value}"}, collection="profile", icon="image", level=8)  # fmt: skip

# --------------------------------------------------------------------------------- banners and frames
for key, value, en, fr, rarity, price, level, en_about, fr_about in (
    ("banner_synthwave", "synthwave", "Synthwave banner", "Bannière synthwave", "rare", 300, None,
     "A retro sunset grid.", "Une grille rétro au coucher du soleil."),
    ("banner_starfield", "starfield", "Starfield banner", "Bannière champ d'étoiles", "epic", 550, 4,
     "A slowly drifting field of stars.", "Un champ d'étoiles qui dérive lentement."),
    ("banner_sakura", "sakura", "Sakura banner", "Bannière sakura", "rare", 300, None,
     "Falling cherry blossom petals.", "Des pétales de cerisier qui tombent."),
    ("banner_halloween", "halloween", "Haunted banner", "Bannière hantée", "epic", 500, None,
     "Pumpkins and a full moon.", "Citrouilles et pleine lune."),
    ("banner_castle", "castle", "Enchanted castle banner", "Bannière château enchanté", "epic", 600, 5,
     "Towers under the stars of a wizarding night.", "Des tours sous les étoiles d'une nuit magique."),
    ("banner_hyperspace", "hyperspace", "Hyperspace banner", "Bannière hyperespace", "epic", 650, 5,
     "Stars stretching into light.", "Des étoiles qui s'étirent en lumière."),
    ("banner_code", "code", "Green code banner", "Bannière code vert", "epic", 650, 5,
     "Falling green code.", "Du code vert qui défile."),
    ("banner_dunes", "dunes", "Dunes banner", "Bannière dunes", "rare", 350, None,
     "Two suns over the dunes.", "Deux soleils sur les dunes."),
    ("banner_bloodmoon", "bloodmoon", "Blood moon banner", "Bannière lune de sang", "rare", 400, None,
     "A red moon over a dark sky.", "Une lune rouge dans un ciel noir."),
    ("banner_snowfall", "snowfall", "Snowy night banner", "Bannière nuit de neige", "epic", 550, None,
     "Snow falling on the village.", "La neige tombe sur le village."),
    ("banner_pow", "pow", "POW! banner", "Bannière POW !", "rare", 350, None,
     "A comic-book burst.", "Une explosion de BD."),
    ("banner_speedlines", "speedlines", "Speed lines banner", "Bannière lignes de vitesse", "rare", 350, None,
     "Manga speed lines.", "Les lignes de vitesse des mangas."),
    ("banner_toon", "toon", "Toon banner", "Bannière cartoon", "common", 180, None,
     "Clouds and green hills.", "Nuages et collines vertes."),
    ("banner_cabin", "cabin", "Cabin banner", "Bannière chalet", "rare", 300, None,
     "Warm plaid by the fire.", "Plaid chaud au coin du feu."),
    ("banner_neon_grid", "neon-grid", "Neon grid banner", "Bannière grille néon", "epic", 600, 5,
     "A grid racing towards the horizon.", "Une grille qui file vers l'horizon."),
    ("banner_mono", "mono", "Monochrome banner", "Bannière monochrome", "common", 120, None,
     "Soft greys, nothing else.", "Des gris doux, rien d'autre."),
    ("banner_nebula", "nebula", "Nebula banner", "Bannière nébuleuse", "legendary", 1100, 10,
     "A living nebula slowly shifting colours.", "Une nébuleuse vivante aux couleurs changeantes."),
    ("banner_skyline", "skyline", "Hero skyline banner", "Bannière ville héroïque", "rare", 400, None,
     "The city you protect.", "La ville que vous protégez."),
    ("banner_mirrorball", "mirrorball", "Mirror ball banner", "Bannière boule à facettes", "epic", 650, 5,
     "Spinning disco lights.", "Des lumières disco qui tournent."),
    ("banner_night_city", "night-city", "Night city banner", "Bannière Night City", "epic", 650, 6,
     "Neon towers in the rain.", "Des tours de néon sous la pluie."),
    ("banner_upsidedown", "upsidedown", "Upside Down banner", "Bannière Monde à l'envers", "epic", 700, 6,
     "A red sky, floating spores and lightning over the other side.", "Un ciel rouge, des spores et des éclairs sur l'autre côté."),
    ("banner_hawkins", "hawkins", "Hawkins lights banner", "Bannière guirlande de Hawkins", "rare", 400, None,
     "A string of Christmas lights blinking on a wallpapered wall.", "Une guirlande qui clignote sur un mur tapissé."),
    ("banner_shire", "shire", "Shire banner", "Bannière de la Comté", "rare", 400, None,
     "Green hills under a gentle sun.", "Des collines vertes sous un doux soleil."),
    ("banner_mordor", "mordor", "Mordor banner", "Bannière du Mordor", "epic", 750, 7,
     "A dark land, a burning eye on its tower.", "Une terre sombre, un œil de feu sur sa tour."),
    ("banner_pixelshire", "pixelshire", "Pixel Shire banner", "Bannière Comté pixel", "rare", 350, None,
     "The Shire in pixel art: hills, a round door, clouds.", "La Comté en pixel art : collines, porte ronde, nuages."),
    ("banner_vhs", "vhs", "VHS blue screen banner", "Bannière écran bleu VHS", "rare", 450, None,
     "PLAY ▶ on a blue screen, a tracking band and the tape's rainbow.",
     "PLAY ▶ sur écran bleu, une bande de tracking et l'arc-en-ciel de la cassette."),
    ("banner_nostromo", "nostromo", "Onboard computer banner", "Bannière ordinateur de bord", "epic", 650, 6,
     "A phosphor grid, a heartbeat running across and a bulkhead's hazard stripe.",
     "Une grille phosphore, un battement de cœur qui défile et la bande de danger d'une cloison."),
    ("banner_mesh", "mesh", "Colour mesh banner", "Bannière dégradé fluide", "epic", 650, 5,
     "Soft colours drifting like a phone's wallpaper.", "Des couleurs douces qui dérivent comme un fond d'écran de téléphone."),
):  # fmt: skip
    _p(key, "profile_banner", price, rarity, en, fr, en_about, fr_about, {"banner": value},
       collection="profile", icon="image", level=level)  # fmt: skip

for key, value, en, fr, rarity, price, level, en_about, fr_about in (
    ("frame_gold", "gold", "Golden frame", "Cadre doré", "legendary", 1300, 10,
     "A shining golden ring around your avatar.", "Un anneau doré brillant autour de votre avatar."),
    ("frame_neon", "neon", "Neon frame", "Cadre néon", "epic", 600, 4,
     "A glowing neon ring.", "Un anneau de néon lumineux."),
    ("frame_flames", "flames", "Flame frame", "Cadre de flammes", "epic", 650, 5,
     "Your avatar surrounded by flames.", "Votre avatar entouré de flammes."),
    ("frame_rainbow", "rainbow", "Rainbow frame", "Cadre arc-en-ciel", "rare", 350, None,
     "A turning rainbow ring.", "Un anneau arc-en-ciel qui tourne."),
    ("frame_runes", "runes", "Rune frame", "Cadre de runes", "epic", 650, 5,
     "Golden runes turning around you.", "Des runes dorées qui tournent autour de vous."),
    ("frame_orbit", "orbit", "Orbit frame", "Cadre orbite", "epic", 650, 5,
     "A tiny planet in orbit.", "Une petite planète en orbite."),
    ("frame_code", "code", "Code frame", "Cadre code", "epic", 600, 5,
     "Flickering green code.", "Du code vert qui scintille."),
    ("frame_sand", "sand", "Sand frame", "Cadre de sable", "rare", 350, None,
     "Warm desert tones.", "Les tons chauds du désert."),
    ("frame_blood", "blood", "Bloody frame", "Cadre sanglant", "rare", 400, None,
     "It drips.", "Ça goutte."),
    ("frame_pumpkin", "pumpkin", "Pumpkin frame", "Cadre citrouille", "rare", 350, None,
     "Carved orange ribs.", "Des côtes orange sculptées."),
    ("frame_holly", "holly", "Holly frame", "Cadre de houx", "rare", 350, None,
     "Holly leaves and red berries.", "Feuilles de houx et baies rouges."),
    ("frame_pow", "pow", "POW frame", "Cadre POW", "rare", 350, None,
     "A comic burst around your face.", "Une explosion de BD autour de votre visage."),
    ("frame_chrome", "chrome", "Chrome frame", "Cadre chrome", "rare", 400, None,
     "Polished metal.", "Du métal poli."),
    ("frame_hologram", "hologram", "Hologram frame", "Cadre hologramme", "legendary", 1200, 12,
     "Ever-shifting iridescent light.", "Une lumière irisée en perpétuel mouvement."),
    ("frame_cyber", "cyber", "Cyber frame", "Cadre cyber", "epic", 600, 6,
     "Notched yellow plating.", "Un blindage jaune biseauté."),
    ("frame_hero", "hero", "Hero frame", "Cadre héros", "rare", 400, None,
     "Red, white and blue.", "Rouge, blanc et bleu."),
    ("frame_disco", "disco", "Disco frame", "Cadre disco", "epic", 650, 5,
     "A spinning ring of colours.", "Un anneau de couleurs qui tourne."),
    ("frame_toxic", "toxic", "Toxic frame", "Cadre toxique", "epic", 600, 5,
     "Pulsing acid glow.", "Une lueur acide qui pulse."),
    ("frame_sakura", "sakura", "Sakura frame", "Cadre sakura", "rare", 350, None,
     "Cherry blossoms around you.", "Des fleurs de cerisier autour de vous."),
    ("frame_veins", "veins", "Red veins frame", "Cadre veines rouges", "epic", 650, 6,
     "Red veins pulsing around your face.", "Des veines rouges qui pulsent autour de vous."),
    ("frame_lights", "lights", "Christmas lights frame", "Cadre guirlande", "rare", 350, None,
     "A ring of blinking bulbs.", "Un cercle d'ampoules qui clignotent."),
    ("frame_onering", "onering", "One Ring frame", "Cadre de l'Anneau unique", "epic", 800, 8,
     "A golden ring turning around you.", "Un anneau d'or qui tourne autour de vous."),
    ("frame_elven", "elven", "Elven frame", "Cadre elfique", "rare", 400, None,
     "Silver and green, like Lothlórien.", "Argent et vert, comme la Lothlórien."),
    ("frame_vhs", "vhs", "VHS rainbow frame", "Cadre arc-en-ciel VHS", "rare", 400, None,
     "The tape's rainbow around you, slipping now and then.", "L'arc-en-ciel de la cassette autour de vous, qui décroche parfois."),
    ("frame_tracker", "tracker", "Motion tracker frame", "Cadre détecteur de mouvement", "epic", 650, 6,
     "Amber brackets and a tracker's sweep going round you.", "Des coins ambrés et le balayage d'un détecteur autour de vous."),
    ("frame_rings", "rings", "Activity rings frame", "Cadre anneaux d'activité", "epic", 700, 6,
     "Three rings filling up around your avatar.", "Trois anneaux qui se remplissent autour de votre avatar."),
    # #78: drawn by the GPU, in shapes of their own
    ("frame_pyre", "pyre", "Pyre frame", "Cadre bûcher", "epic", 1200, 8,
     "A hexagon of living flames around your avatar.", "Un hexagone de flammes vives autour de votre avatar."),
    ("frame_tesla", "tesla", "Tesla coil frame", "Cadre bobine Tesla", "epic", 1200, 8,
     "A diamond crackling with electricity.", "Un losange qui crépite d'électricité."),
    ("frame_abyssal", "abyssal", "Abyssal frame", "Cadre abyssal", "epic", 1200, 8,
     "A ring of glass full of moving water.", "Un anneau de verre rempli d'eau qui bouge."),
    ("frame_obsidian", "obsidian", "Obsidian frame", "Cadre obsidienne", "epic", 1200, 8,
     "A molten shield around your avatar.", "Un écusson en fusion autour de votre avatar."),
    ("frame_frostcrown", "frostcrown", "Frost crown frame", "Cadre couronne de givre", "epic", 1200, 8,
     "A star of ice around your avatar.", "Une étoile de glace autour de votre avatar."),
    ("frame_starlit", "starlit", "Starlit frame", "Cadre constellé", "legendary", 1600, 12,
     "A ring of turning stars and nebulae.", "Un anneau d'étoiles et de nébuleuses qui tourne."),
    ("frame_regalia", "regalia", "Regalia frame", "Cadre régalia", "legendary", 1600, 12,
     "A shield of liquid gold.", "Un écusson d'or liquide."),
    ("frame_biohazard", "biohazard", "Biohazard frame", "Cadre danger biologique", "epic", 1200, 8,
     "A hexagon of bubbling acid.", "Un hexagone d'acide bouillonnant."),
    ("frame_prism", "prism", "Prism frame", "Cadre prisme", "epic", 1200, 8,
     "A diamond of holographic foil.", "Un losange de film holographique."),
    ("frame_sigil", "sigil", "Sigil frame", "Cadre sceau", "epic", 1200, 8,
     "A circle of turning runes.", "Un cercle de runes qui tournent."),
    ("frame_mainframe", "mainframe", "Mainframe frame", "Cadre ordinateur central", "epic", 1200, 8,
     "A square of falling code.", "Un carré de code qui tombe."),
    ("frame_hanami", "hanami", "Hanami frame", "Cadre hanami", "epic", 1200, 8,
     "A ring of drifting cherry petals.", "Un anneau de pétales de cerisier qui dérivent."),
    ("frame_wraith", "wraith", "Wraith frame", "Cadre spectre", "epic", 1200, 8,
     "A star of black smoke.", "Une étoile de fumée noire."),
    ("frame_sweetie", "sweetie", "Sweetie frame", "Cadre friandise", "epic", 1200, 8,
     "A square of swirling candy.", "Un carré de bonbon qui tourbillonne."),
    ("frame_borealis", "borealis", "Borealis frame", "Cadre boréal", "epic", 1200, 8,
     "A hexagon of northern lights.", "Un hexagone d'aurores boréales."),
    ("frame_corona", "corona", "Corona frame", "Cadre couronne solaire", "epic", 1200, 8,
     "A ring of plasma filaments.", "Un anneau de filaments de plasma."),
    ("frame_chronogate", "chronogate", "Time gate frame", "Cadre porte du temps", "legendary", 1600, 12,
     "Your avatar framed in a triangular time portal.", "Votre avatar dans un portail temporel triangulaire."),
):  # fmt: skip
    _p(key, "avatar_frame", price, rarity, en, fr, en_about, fr_about, {"frame": value},
       collection="profile", icon="user", level=level)  # fmt: skip

_p("backdrop_banner", "profile_backdrop", 1500, "legendary", "Film backdrop banner", "Bannière de film",
   "Use the backdrop of any film or series of the library as your profile banner.",
   "Le backdrop de n'importe quel film ou série de la bibliothèque en bannière de profil.",
   {"feature": "backdrop"}, collection="profile", icon="film", featured=False, level=8, supply=5)  # fmt: skip

_p("release_search", "access", 5000, "legendary", "Release hunter", "Chasseur de versions",
   "Search the indexers yourself from a title's page and see every release found (advanced).",
   "Interroger soi-même les indexeurs depuis la fiche d'un titre et voir toutes les versions trouvées (avancé).",
   {"permission": "media.release_search"}, collection="essentials", icon="search", level=20, supply=3)  # fmt: skip

# --------------------------------------------------------------------------------- name styles
for value, en, fr, rarity, price, level in (
    ("wizard", "Golden spellbook", "Grimoire doré", "epic", 750, 6),
    ("upsidedown", "Upside Down", "Monde à l'envers", "epic", 700, 6),
    ("elvish", "Elvish gold", "Or elfique", "epic", 700, 6),
    ("mordor", "Fires of Mordor", "Feux du Mordor", "rare", 450, None),
    ("vhs", "VHS", "Magnétoscope", "rare", 400, None),
    ("nova", "Nova gradient", "Dégradé Nova", "epic", 650, 5),
    ("nostromo", "Phosphor", "Phosphore", "rare", 450, None),
    ("galaxy", "Galactic", "Galactique", "rare", 400, None),
    ("matrix", "Simulation", "Simulation", "epic", 700, 5),
    ("desert", "Dune sand", "Sable des dunes", "rare", 400, None),
    ("horror", "Horror", "Épouvante", "rare", 400, None),
    ("halloween", "Halloween", "Halloween", "rare", 350, None),
    ("christmas", "Candy cane", "Sucre d'orge", "rare", 350, None),
    ("comic", "Comic", "BD", "rare", 400, None),
    ("manga", "Manga", "Manga", "rare", 400, None),
    ("cartoon", "Cartoon", "Cartoon", "epic", 600, 4),
    ("cozy", "Cozy", "Douillet", "common", 200, None),
    ("futuristic", "Future chrome", "Chrome futur", "rare", 400, None),
    ("minimal", "Minimal", "Minimal", "common", 150, None),
    ("alien", "Xeno", "Xéno", "epic", 650, 5),
    ("hero", "Superhero", "Super-héros", "rare", 450, None),
    ("neowave", "Retro neon", "Néon rétro", "epic", 650, 5),
    ("disco", "Disco", "Disco", "epic", 700, 5),
    ("cyberpunk", "Cyberpunk", "Cyberpunk", "epic", 700, 6),
    ("pixel", "Pixel", "Pixel", "rare", 350, None),
    ("handwritten", "Handwritten", "Manuscrit", "common", 150, None),
    ("fire", "Fire", "Flammes", "epic", 750, 7),
    ("ice", "Ice", "Glace", "rare", 400, None),
    ("rainbow", "Rainbow", "Arc-en-ciel", "epic", 700, 5),
    ("royal", "Royal", "Royal", "legendary", 1300, 12),
    ("nameblaze", "Inferno", "Ardent", "epic", 1100, 8),
    ("namevolt", "Live wire", "Sous tension", "epic", 1100, 8),
    ("namefrost", "Frozen", "Givré", "epic", 1000, 8),
    ("namegalaxy", "Starborn", "Né des étoiles", "epic", 1100, 8),
    ("namegold", "Gilded", "Doré", "legendary", 1500, 12),
    ("nameshadow", "Shadowed", "Ombreux", "epic", 1100, 8),
    ("namesakura", "Blossom", "En fleurs", "rare", 900, 6),
    ("nameplasma", "Plasma", "Plasma", "epic", 1100, 8),
    ("nameaurora", "Aurora", "Aurore", "epic", 1100, 8),
    ("namechrono", "Out of time", "Hors du temps", "legendary", 1600, 12),
):  # fmt: skip
    _p(f"name_{value}", "name_style", price, rarity, f"{en} name style", f"Style de nom {fr.lower()}",
       "A font and an effect for your name on your profile.", "Une police et un effet pour votre nom sur votre profil.",
       {"style": value}, collection="names", icon="feather", level=level)  # fmt: skip

# --------------------------------------------------------------------------------- palettes
for value, en, fr, rarity, price, level in (
    ("sunset", "Sunset", "Coucher de soleil", "rare", 250, None),
    ("candy", "Candy", "Bonbon", "rare", 250, None),
    ("royal", "Royal", "Royale", "epic", 550, 4),
    ("ember", "Ember", "Braise", "epic", 550, 4),
    ("matrix", "Matrix", "Matrix", "legendary", 1100, 10),
    ("aurora", "Aurora", "Aurore", "epic", 550, 4),
    ("lagoon", "Lagoon", "Lagon", "rare", 250, None),
    ("lava", "Lava", "Lave", "epic", 550, 4),
    ("mint", "Mint", "Menthe", "common", 150, None),
    ("gold", "Gold", "Or", "legendary", 1100, 10),
    ("ice", "Ice", "Glace", "rare", 250, None),
    ("rose", "Rose", "Rose", "common", 150, None),
    ("toxic", "Toxic", "Toxique", "epic", 550, 5),
    ("midnight", "Midnight", "Minuit", "rare", 300, None),
    ("coffee", "Coffee", "Café", "common", 150, None),
    ("lavender", "Lavender", "Lavande", "rare", 250, None),
    ("bubblegum", "Bubblegum", "Chewing-gum", "rare", 300, None),
    ("polar", "Polar", "Polaire", "rare", 250, None),
    ("copper", "Copper", "Cuivre", "rare", 300, None),
    ("solar", "Solar", "Solaire", "rare", 250, None),
    ("berry", "Berry", "Baie", "epic", 500, 3),
    ("slate", "Slate", "Ardoise", "common", 150, None),
    ("peach", "Peach", "Pêche", "common", 150, None),
    ("crimson", "Crimson", "Carmin", "epic", 550, 4),
    ("hawkins", "Hawkins", "Hawkins", "rare", 300, None),
    ("gondor", "Gondor", "Gondor", "epic", 550, 4),
    ("vhs", "VHS", "Vidéoclub", "rare", 300, None),
    ("nova", "Nova", "Violet Nova", "epic", 550, 4),
    ("nostromo", "Nostromo", "Nostromo", "rare", 350, None),
):  # fmt: skip
    _p(f"palette_{value}", "palette", price, rarity, f"{en} palette", f"Palette {fr.lower()}",
       "Accent colours laid over any theme — try it before buying.",
       "Des couleurs d'accent posées sur n'importe quel thème — essayez-la avant d'acheter.",
       {"palette": value}, collection="palettes", icon="palette", level=level)  # fmt: skip

# --------------------------------------------------------------------------------- level badges (027)
for value, en, fr, rarity, price, level, about_en, about_fr in (
    ("pixel", "Pixel", "Pixel", "common", 200, None, "Your level in 8-bit, framed in square pixels.",
     "Votre niveau en 8 bits, encadré de pixels carrés."),
    ("neon", "Neon", "Néon", "rare", 350, None, "A glowing cyan tube around your level.",
     "Un tube cyan lumineux autour de votre niveau."),
    ("crest", "Crest", "Blason", "rare", 400, None, "A heraldic shield edged with gold.", "Un écu héraldique bordé d'or."),
    ("gem", "Gem", "Gemme", "epic", 650, 5, "A cut amethyst catching the light.", "Une améthyste taillée qui accroche la lumière."),
    ("hologram", "Hologram", "Hologramme", "epic", 700, 6, "Iridescent colours drifting across it.",
     "Des couleurs irisées qui glissent dessus."),
    ("vhs", "VHS", "VHS", "rare", 350, None, "Scanlines and a colour split, straight off the tape.",
     "Lignes de balayage et couleurs décalées, tout droit de la cassette."),
    ("saber", "Light blade", "Lame de lumière", "legendary", 1200, 12, "A humming blade of light in your accent colour.",
     "Une lame de lumière vibrante de votre couleur d'accent."),
    ("elements", "Four elements", "Quatre éléments", "legendary", 1300, 15,
     "Fire, water, earth and air turning around your level.", "Le feu, l'eau, la terre et l'air qui tournent autour de votre niveau."),
    ("blackhole", "Black hole", "Trou noir", "legendary", 1400, 16, "An accretion disc spinning around your level, the number pulled in now and then.",
     "Un disque d'accrétion qui tourne autour de votre niveau, le chiffre aspiré de temps en temps."),
    ("melt", "Melting", "Fondant", "epic", 600, 5, "Your level drips like hot wax.", "Votre niveau coule comme de la cire chaude."),
    ("kapow", "KAPOW!", "KAPOW !", "epic", 650, 5, "A comic starburst behind your level, punching now and then.",
     "Une explosion de BD derrière votre niveau, qui frappe de temps en temps."),
    ("portal", "Dimensional portal", "Portail dimensionnel", "legendary", 1300, 14, "A swirling portal opens behind your level.",
     "Un portail tourbillonnant s'ouvre derrière votre niveau."),
    ("inferno", "Inferno", "Brasier", "epic", 700, 6, "Your level burns with living flames.", "Votre niveau brûle de flammes vives."),
    ("cassette", "Cassette", "Cassette", "rare", 450, None, "Your level written on the label of a tape.",
     "Votre niveau écrit sur l'étiquette d'une cassette."),
    ("tracker", "Motion tracker", "Détecteur de mouvement", "epic", 650, 6,
     "A phosphor disc, the tracker's sweep going round your level.", "Un disque phosphore, le balayage du détecteur autour de votre niveau."),
    ("squircle", "App icon", "Icône d'app", "rare", 450, None, "Your level as a glossy app icon.",
     "Votre niveau en icône d'application brillante."),
    ("upsidedown", "Upside Down", "Monde à l'envers", "epic", 750, 6, "Red neon, a faint mirror, and now and then it turns over.",
     "Néon rouge, un reflet pâle, et de temps en temps il se retourne."),
    ("veins", "Red veins", "Veines rouges", "epic", 650, 6, "Red veins pulsing across your level.", "Des veines rouges qui pulsent sur votre niveau."),
    ("lights", "Christmas lights", "Guirlande", "rare", 400, None, "A string of bulbs blinking over your level.", "Une guirlande qui clignote au-dessus de votre niveau."),
    ("onering", "One Ring", "Anneau unique", "legendary", 1500, 15, "A golden ring turning around your level.", "Un anneau d'or qui tourne autour de votre niveau."),
    ("eye", "The Eye", "L'Œil", "legendary", 1400, 14, "A fiery slit eye that blinks now and then.", "Un œil de feu qui cligne de temps en temps."),
    ("mithril", "Mithril", "Mithril", "epic", 700, 6, "Light chainmail with a silver gleam.", "Une fine cotte de mailles à l'éclat d'argent."),
    ("balrog", "Balrog", "Balrog", "legendary", 1300, 13, "Shadow and flame rising behind your level.", "Ombre et flamme derrière votre niveau."),
    ("frost", "Frost", "Givre", "rare", 400, None, "Cold blue ice.", "Une glace d'un bleu froid."),
    ("nebula", "Nebula", "Nébuleuse", "epic", 650, 5, "A drifting nebula with a few stars.", "Une nébuleuse qui dérive, quelques étoiles."),
    ("circuit", "Circuit", "Circuit", "rare", 400, None, "Green traces on a circuit board.", "Des pistes vertes sur un circuit imprimé."),
    # #73: drawn by the graphics chip (HD)
    ("blaze", "Living flames", "Flammes vives", "legendary", 1600, 12, "Real flames wrapped around your level, rising above it, sparks flying.",
     "De vraies flammes qui enveloppent votre niveau et montent au-dessus, des étincelles qui s'envolent."),
    ("voltage", "High voltage", "Haute tension", "epic", 1200, 8, "A charged badge: arcs crawl round its edge and leap out, sparks crackle inside.",
     "Un badge chargé : des arcs courent sur son bord et s'en échappent, des étincelles crépitent dedans."),
    ("aqua", "Water glass", "Verre d'eau", "epic", 1100, 8, "A glass badge half full of water sloshing from side to side, caustics and rising bubbles.",
     "Un badge de verre à moitié rempli d'eau qui tangue, des reflets et des bulles qui montent."),
    ("magma", "Magma", "Magma", "epic", 1200, 8, "Molten rock flowing under a cracked crust, its heat glowing around it.",
     "De la roche en fusion qui coule sous une croûte fissurée, sa chaleur rougeoie autour."),
    # #77: more of them, each its own world
    ("glacier", "Glacier", "Glacier", "epic", 1200, 8, "A frozen badge of facets, frost spikes growing from it, glints.",
     "Un badge gelé à facettes, des pointes de givre qui poussent, des éclats."),
    ("galaxy", "Galaxy", "Galaxie", "epic", 1200, 8, "A spiral galaxy turning inside your level.",
     "Une galaxie spirale qui tourne dans votre niveau."),
    ("aurum", "Liquid gold", "Or liquide", "epic", 1200, 8, "Molten gold rippling, a shine sweeping across.",
     "De l'or en fusion qui ondule, un reflet qui passe."),
    ("toxic", "Toxic", "Toxique", "epic", 1200, 8, "Green acid bubbling, drops dripping below.",
     "De l'acide vert qui bouillonne, des gouttes qui tombent."),
    ("holo", "Holo foil", "Holographique", "epic", 1200, 8, "A rainbow foil sliding with the light.",
     "Un film arc-en-ciel qui glisse avec la lumière."),
    ("runes", "Arcane runes", "Runes arcaniques", "epic", 1200, 8, "A ring of glyphs orbiting a swirling mist.",
     "Un anneau de glyphes autour d'une brume qui tourbillonne."),
    ("matrix", "Digital rain", "Pluie numérique", "epic", 1200, 8, "Glyphs falling inside your level.",
     "Des glyphes qui tombent dans votre niveau."),
    ("sakura", "Sakura", "Sakura", "epic", 1200, 8, "Petals drifting round your level.",
     "Des pétales qui dérivent autour de votre niveau."),
    ("shadow", "Shadow", "Ombre", "epic", 1200, 8, "Black smoke reaching out, eyes opening in the dark.",
     "Une fumée noire qui s'étend, des yeux qui s'ouvrent dans le noir."),
    ("candy", "Candy", "Bonbon", "epic", 1200, 8, "Pastel stripes swirling, sprinkles and a glossy shine.",
     "Des rayures pastel qui tourbillonnent, des vermicelles, un reflet brillant."),
    ("aurora", "Aurora", "Aurore", "epic", 1200, 8, "Curtains of green and violet light waving.",
     "Des voiles de lumière verte et violette qui ondulent."),
    ("plasma", "Plasma ball", "Boule plasma", "epic", 1200, 8, "Filaments of light reaching from a bright core.",
     "Des filaments de lumière qui partent d'un cœur brillant."),
    ("chrono", "Time rift", "Faille temporelle", "legendary", 1600, 12,
     "A triangular time portal tearing open behind your level, the vortex of time seen through it.",
     "Un portail temporel triangulaire qui s'ouvre derrière votre niveau, le vortex du temps vu au travers."),
):  # fmt: skip
    _p(f"level_{value}", "level_badge", price, rarity, f"{en} level badge", f"Badge de niveau {fr.lower()}",
       about_en, about_fr, {"style": value}, collection="levels", icon="star", level=level)  # fmt: skip
_p("level_crown", "level_badge", None, "legendary", "Crowned level badge", "Badge de niveau couronné",
   "A golden crown over your level — only for living legends (achievement « Living legend »).",
   "Une couronne d'or sur votre niveau — réservée aux légendes vivantes (succès « Légende vivante »).",
   {"style": "crown"}, collection="rewards", icon="crown", reward_only=True)  # fmt: skip

# --------------------------------------------------------------------------------- level-up moments (027)
for value, en, fr, rarity, price, level, about_en, about_fr in (
    ("arcade", "Arcade", "Arcade", "rare", 350, None, "LEVEL UP! in 8-bit, blinking stars and a coin sound.",
     "LEVEL UP ! en 8 bits, étoiles clignotantes et bruit de pièce."),
    ("cosmic", "Cosmic", "Cosmique", "epic", 800, 8, "Your new level is born from a black hole, in a ring of stars.",
     "Votre nouveau niveau naît d'un trou noir, dans un anneau d'étoiles."),
    ("comic", "Comic book", "Bande dessinée", "epic", 650, 5, "A splash page: KAPOW!, halftone and speed lines.",
     "Une page de BD : KAPOW !, trame et lignes de vitesse."),
    ("elements", "Four elements", "Quatre éléments", "epic", 750, 7, "Fire, water, earth and air swirl together into your new level.",
     "Le feu, l'eau, la terre et l'air tourbillonnent pour former votre nouveau niveau."),
    # #78: full-stage, drawn by the GPU
    ("phoenix", "Phoenix", "Phénix", "legendary", 1700, 12, "Fire rises, a bird of flame spreads its wings, embers fly.",
     "Le feu monte, un oiseau de flammes déploie ses ailes, des braises s'envolent."),
    ("thunderstrike", "Lightning strike", "Coup de foudre", "epic", 1300, 8, "Storm clouds roll in, bolts strike one after another.",
     "L'orage gronde, la foudre frappe coup sur coup."),
    ("tidalwave", "Tidal wave", "Raz-de-marée", "epic", 1300, 8, "The water rises and a great wave rolls across.",
     "L'eau monte et une vague géante déferle."),
    ("supernova", "Supernova", "Supernova", "legendary", 1700, 12, "A star gathers, bursts, a shock wave rings out.",
     "Une étoile se contracte, explose, une onde de choc se propage."),
    ("goldrush", "Gold rush", "Ruée vers l'or", "epic", 1300, 8, "Coins rain down tumbling, golden light bursts.",
     "Une pluie de pièces qui tournoient, une lumière dorée qui jaillit."),
    ("arcanum", "Arcane circle", "Cercle arcanique", "epic", 1300, 8, "A magic circle draws itself and flares.",
     "Un cercle magique se trace et s'embrase."),
    ("sakurastorm", "Sakura storm", "Tempête de sakura", "epic", 1300, 8, "A gust carries hundreds of petals across.",
     "Une bourrasque emporte des centaines de pétales."),
    ("aurorasky", "Aurora sky", "Ciel d'aurore", "epic", 1300, 8, "The night opens on waving curtains of light.",
     "La nuit s'ouvre sur des voiles de lumière."),
    ("timeportal", "Time portal", "Portail temporel", "legendary", 1800, 12,
     "A triangular portal draws itself, tears open on the vortex of time, flashes and closes again.",
     "Un portail triangulaire se trace, s'ouvre sur le vortex du temps, éclate de lumière et se referme."),
    # #133: the Upside Down's gate
    ("rift", "The Gate", "La brèche", "legendary", 1800, 12,
     "The lights flicker, a red rift tears the wall open, its membrane pulsing — you step into it and come out in the Upside Down, ash drifting up, red lightning overhead, at your new level.",
     "Les lumières vacillent, une brèche rouge déchire le mur, sa membrane palpite — vous y entrez et ressortez dans le monde à l'envers, des cendres qui montent, des éclairs rouges au-dessus, à votre nouveau niveau."),
):  # fmt: skip
    _p(f"levelup_{value}", "level_up", price, rarity, f"{en} level-up", f"Passage de niveau {fr.lower()}",
       about_en, about_fr, {"animation": value}, collection="levels", icon="trophy", level=level)  # fmt: skip
# 027: each universe's own level-up — its theme's default, sold to wear with any theme (and in its pack)
for value, en, fr, about_en, about_fr in (
    ('crawl', 'Opening crawl', 'Générique spatial', "Your new level rises through the stars like a film's opening crawl.", 'Votre nouveau niveau défile dans les étoiles comme un générique de film.'),
    ('spell', 'Spell circle', 'Cercle magique', 'A turning magic circle and a parchment that unrolls.', 'Un cercle magique qui tourne et un parchemin qui se déroule.'),
    ('decode', 'Decode', 'Décodage', 'Green code falls, the terminal types ACCESS GRANTED.', 'Le code vert tombe, le terminal tape ACCESS GRANTED.'),
    ('sandstorm', 'Sandstorm', 'Tempête de sable', 'Sand blows across; your level emerges from the haze.', 'Le sable souffle ; votre niveau sort de la brume.'),
    ('bloodmoon', 'Blood moon', 'Lune de sang', 'A red moon, dripping blood, a flickering screen.', 'Une lune rouge, du sang qui coule, un écran qui vacille.'),
    ('pumpkin', 'Pumpkin night', 'Nuit des citrouilles', 'Bats fly off in an orange glow — BOO!', "Des chauves-souris s'envolent dans une lueur orange — BOU !"),
    ('gift', 'Christmas present', 'Cadeau de Noël', 'Your level springs out of a present under the snow.', "Votre niveau jaillit d'un cadeau sous la neige."),
    ('manga', 'Manga panel', 'Planche de manga', 'Speed lines and a big ドン! on a manga page.', 'Lignes de vitesse et un grand ドン ! sur une planche de manga.'),
    ('boing', 'Boing!', 'Boing !', 'Your level bounces in, stars spinning round.', 'Votre niveau arrive en rebondissant, des étoiles tout autour.'),
    ('hearth', 'By the hearth', 'Coin du feu', 'Warm light and embers floating up slowly.', 'Une lumière chaude et des braises qui montent doucement.'),
    ('hud', 'Holographic HUD', 'Interface holographique', 'A scanning line, corner brackets and a grid.', "Une ligne de balayage, des coins d'interface et une grille."),
    ('minimal', 'Minimal', 'Minimal', 'A thin line, and the facts.', "Un trait fin, et l'essentiel."),
    ('abduction', 'Abduction', 'Enlèvement', "A saucer's beam lifts your new level up.", "Le rayon d'une soucoupe soulève votre nouveau niveau."),
    ('hero', 'Hero shield', 'Bouclier de héros', 'A shield of rings slams down — BAM!', "Un bouclier d'anneaux s'abat — BAM !"),
    ('synthwave', 'Synthwave sunset', 'Coucher synthwave', 'A sunset over a moving neon grid.', 'Un coucher de soleil sur une grille néon en mouvement.'),
    ('disco', 'Mirror ball', 'Boule à facettes', "The mirror ball's spots sweep the room.", 'Les éclats de la boule à facettes balaient la pièce.'),
    ('glitch', 'Glitch', 'Glitch', 'The screen tears and the title glitches.', "L'écran se déchire et le titre bugue."),
    ('noir', 'Film noir', 'Film noir', 'Rain in black and white, your number in red.', 'La pluie en noir et blanc, votre niveau en rouge.'),
    ('spotlight', 'Spotlight', 'Projecteur', 'An amber spotlight finds you.', 'Un projecteur ambré vous trouve.'),
    ("upsidedown", "Upside Down", "Monde à l'envers", "The world turns over, spores drift up, red lightning flashes.",
     "Le monde se retourne, les spores remontent, des éclairs rouges."),
    ("onering", "The One Ring", "L'Anneau unique", "A golden ring turns in the dark; the scroll of your journey unrolls.",
     "Un anneau d'or tourne dans l'ombre ; le parchemin de votre voyage se déroule."),
    ("vhs", "VHS tape", "Magnétoscope", "The TV comes on: a blue screen, PLAY ▶ and your level in the VCR's letters.",
     "La télé s'allume : écran bleu, PLAY ▶ et votre niveau en lettres de magnétoscope."),
    ("nostromo", "Onboard computer", "Ordinateur de bord",
     "The CRT switches on, the motion tracker sweeps behind, MU/TH/UR types your crew file update.",
     "L'écran s'allume, le détecteur de mouvement balaie, MU/TH/UR tape la mise à jour de votre dossier."),
    ("nova", "Nova sheet", "Volet dépoli", "Soft colours breathe while a frosted sheet slides up with your new level.",
     "Des couleurs douces respirent pendant qu'un volet dépoli glisse avec votre nouveau niveau."),
):  # fmt: skip
    _p(f"levelup_{value}", "level_up", 450, "rare", f"{en} level-up", f"Passage de niveau {fr.lower()}",
       about_en, about_fr, {"animation": value}, collection="levels", icon="trophy")  # fmt: skip
_p("levelup_cinema", "level_up", None, "legendary", "Premiere level-up", "Passage de niveau avant-première",
   "A film countdown 3-2-1, then your new level on the big screen — for the ten-thousand-XP club.",
   "Un compte à rebours de film 3-2-1, puis votre nouveau niveau sur grand écran — pour le club des dix mille XP.",
   {"animation": "cinema"}, collection="rewards", icon="clapperboard", reward_only=True)  # fmt: skip

# --------------------------------------------------------------------------------- achievement rewards (027)
# out of sale: each one is given by an achievement (see the demo achievements' « unlocks »)
for key, kind, payload, en, fr, about_en, about_fr, icon in (
    ("badge_bug_hunter", "badge", {"label": "Bug hunter", "icon": "bug", "style": "glitch"}, "Bug hunter badge",
     "Badge Chasseur de bugs", "Given for three pieces of feedback.", "Offert pour trois retours.", "bug"),
    ("badge_achievement_hunter", "badge", {"label": "Achievement hunter", "icon": "trophy", "style": "shimmer"},
     "Achievement hunter badge", "Badge Chasseur de succès", "Given for ten achievements.", "Offert pour dix succès.", "trophy"),
    ("badge_patron", "badge", {"label": "Patron", "icon": "handshake", "style": "gold"}, "Patron badge",
     "Badge Mécène", "Given for funding three projects.", "Offert pour trois projets financés.", "handshake"),
    ("badge_completionist", "badge", {"label": "The Collector", "icon": "gem", "style": "rainbow"},
     "The Collector badge", "Badge Le Collectionneur", "Unique: for those who bought 150 things in the shop.",
     "Unique : pour qui a acheté 150 objets dans la boutique.", "gem"),
    ("title_golden_reel", "title", {"label": "Golden reel", "style": "gold"}, "Title: Golden reel",
     "Titre : Bobine d'or", "Given for 250 films and episodes.", "Offert pour 250 films et épisodes.", "trophy"),
    ("title_wish_master", "title", {"label": "Wish master", "style": "shimmer"}, "Title: Wish master",
     "Titre : Maître des souhaits", "Given for 25 requests.", "Offert pour 25 demandes.", "trophy"),
    ("title_patron", "title", {"label": "Patron of the arts", "style": "gold"}, "Title: Patron of the arts",
     "Titre : Mécène", "Given for funding three projects.", "Offert pour trois projets financés.", "trophy"),
    ("title_living_legend", "title", {"label": "Living legend", "style": "flame"}, "Title: Living legend",
     "Titre : Légende vivante", "Given at level 20.", "Offert au niveau 20.", "trophy"),
    ("title_big_spender", "title", {"label": "Big spender", "style": "gold"}, "Title: Big spender",
     "Titre : Flambeur", "Given for 25 purchases.", "Offert pour 25 achats.", "trophy"),
    ("title_completionist", "title", {"label": "The Collector", "style": "rainbow"}, "Title: The Collector",
     "Titre : Le Collectionneur", "Unique: for those who bought 150 things in the shop.",
     "Unique : pour qui a acheté 150 objets dans la boutique.", "trophy"),
    ("frame_loyal", "avatar_frame", {"frame": "gold"}, "Loyal golden frame", "Cadre doré de la fidélité",
     "Given for a hundred visits.", "Offert pour cent visites.", "user"),
    ("bg_night_owl", "profile_background", {"background": "starfield"}, "Night owl background",
     "Fond Oiseau de nuit", "A secret achievement's starry sky.", "Le ciel étoilé d'un succès secret.", "moon"),
    # #103: the portal's player, casting, books, music and boosters
    ("title_front_row", "title", {"label": "Front row", "style": "gold"}, "Title: Front row",
     "Titre : Premier rang", "Given for a film watched to the end in the portal.",
     "Offert pour un film vu jusqu'au bout dans le portail.", "film"),
    ("badge_big_screen", "badge", {"label": "Big screen", "icon": "cast", "style": "shimmer"}, "Big screen badge",
     "Badge Grand écran", "Given for a title cast to a TV.", "Offert pour un titre envoyé sur la télé.", "cast"),
    ("title_projectionist", "title", {"label": "Projectionist", "style": "flame"}, "Title: Projectionist",
     "Titre : Projectionniste", "Given for 25 titles cast to a TV.", "Offert pour 25 titres envoyés sur la télé.",
     "tv"),
    ("badge_bookworm", "badge", {"label": "Bookworm", "icon": "library", "style": "gold"}, "Bookworm badge",
     "Badge Rat de bibliothèque", "Given for ten books finished.", "Offert pour dix livres terminés.", "library"),
    ("title_music_lover", "title", {"label": "Music lover", "style": "shimmer"}, "Title: Music lover",
     "Titre : Mélomane", "Given for fifty songs.", "Offert pour cinquante chansons.", "music"),
    ("badge_lucky_hand", "badge", {"label": "Lucky hand", "icon": "dices", "style": "rainbow"}, "Lucky hand badge",
     "Badge Main heureuse", "Given for a legendary card drawn from a booster.",
     "Offert pour une carte légendaire tirée d'un booster.", "dices"),
    # #108: the long run — high levels, big totals, years of films
    ("title_seasoned", "title", {"label": "Seasoned", "style": "shimmer"}, "Title: Seasoned",
     "Titre : Chevronné", "Given at level 30.", "Offert au niveau 30.", "medal"),
    ("badge_elder", "badge", {"label": "Elder", "icon": "mountain", "style": "gold"}, "Elder badge",
     "Badge Ancien", "Given at level 40.", "Offert au niveau 40.", "mountain"),
    ("title_portal_legend", "title", {"label": "Legend of the portal", "style": "rainbow"},
     "Title: Legend of the portal", "Titre : Légende du portail", "Given at level 50, the highest.",
     "Offert au niveau 50, le plus haut.", "crown"),
    ("badge_portal_legend", "badge", {"label": "Legend", "icon": "crown", "style": "rainbow"}, "Legend badge",
     "Badge Légende", "Given at level 50, the highest.", "Offert au niveau 50, le plus haut.", "crown"),
    ("title_five_hundred", "title", {"label": "Five hundred screenings", "style": "gold"},
     "Title: Five hundred screenings", "Titre : Cinq cents séances", "Given for 500 films and episodes.", "Offert pour 500 films et épisodes.", "clapperboard"),
    ("badge_thousand_nights", "badge", {"label": "A thousand nights", "icon": "moon", "style": "shimmer"},
     "A thousand nights badge", "Badge Mille et une nuits", "Given for 1,000 films and episodes.",
     "Offert pour 1 000 films et épisodes.", "moon"),
    ("frame_faithful", "avatar_frame", {"frame": "orbit"}, "Faithful orbit frame", "Cadre orbital de la constance",
     "Given for 365 visits.", "Offert pour 365 visites.", "user"),
    ("title_hundred_thousand", "title", {"label": "Hundred thousand", "style": "flame"},
     "Title: Hundred thousand", "Titre : Cent mille", "Given for 100,000 XP.", "Offert pour 100 000 XP.", "zap"),
):  # fmt: skip
    _p(key, kind, None, "legendary", en, fr, about_en, about_fr, payload, collection="rewards", icon=icon,
       reward_only=True)  # fmt: skip


# --------------------------------------------------------------------------------- themes
THEME_TEXT = {
    "orbit": (
        "Orbit",
        "Orbite",
        "Navigation in an orbiting bubble, header at the bottom, playful motion.",
        "La navigation dans une bulle en orbite, l'en-tête en bas, des animations joueuses.",
    ),
    "studio": (
        "Studio",
        "Studio",
        "A calm studio: top bar, flat cards, narrow reading width.",
        "Un studio calme : barre du haut, cartes plates, largeur de lecture étroite.",
    ),
    "wizard": (
        "Grimoire",
        "Grimoire",
        "A wizarding school: bookmark navigation, gilded cards, parchment notifications, magic bells and a whole new vocabulary.",
        "Une école de sorcellerie : navigation en marque-pages, cartes dorées, notifications parchemin, clochettes magiques et tout un vocabulaire.",
    ),
    "galaxy": (
        "Space Opera",
        "Space Opera",
        "A starship bridge: dock navigation, holographic cards, a starry sky and sci-fi sounds.",
        "Le pont d'un vaisseau : navigation en dock, cartes holographiques, ciel étoilé et sons de science-fiction.",
    ),
    "matrix": (
        "Simulation",
        "Simulation",
        "Wake up: a command-line navigation, falling green code, terminal cards and glitches.",
        "Réveillez-vous : navigation en ligne de commande, pluie de code vert, cartes terminal et glitchs.",
    ),
    "desert": (
        "Dune",
        "Dune",
        "The spice desert: sand blowing over the dunes, header at the bottom, tribal words.",
        "Le désert de l'épice : vent de sable sur les dunes, en-tête en bas, vocabulaire des tribus.",
    ),
    "horror": (
        "Horror",
        "Horreur",
        "The manor at night: fog, cobwebs, dripping titles and spooky drones.",
        "Le manoir la nuit : brume, toiles d'araignée, titres dégoulinants et bourdonnements inquiétants.",
    ),
    "halloween": (
        "Halloween",
        "Halloween",
        "Trick or treat: bats flying by, a cauldron bubble for the menu, candy for Coins.",
        "Des bonbons ou un sort : chauves-souris, menu en bulle-chaudron, des bonbons comme monnaie.",
    ),
    "christmas": (
        "Noël",
        "Noël",
        "By the fireplace: falling snow, an advent-calendar launcher, sticky notes and bells.",
        "Au coin du feu : neige qui tombe, menu calendrier de l'Avent, post-it et clochettes.",
    ),
    "comic": (
        "Comic",
        "BD",
        "Ink and halftone: comic cards with hard shadows, BANG! titles and boing sounds.",
        "Encre et trame : cartes BD aux ombres franches, titres BANG ! et sons de cartoon.",
    ),
    "manga": (
        "Manga",
        "Manga",
        "Speed lines, sakura petals and chapter tabs, on white paper.",
        "Lignes de vitesse, pétales de sakura et onglets de chapitres, sur papier blanc.",
    ),
    "cartoon": (
        "Cartoon",
        "Dessin animé",
        "Bubbly and bouncy: a toy dock, outlined cards, bubbles and boings.",
        "Pétillant et rebondissant : un dock de jouets, cartes cernées, bulles et sons rigolos.",
    ),
    "cozy": (
        "Cozy",
        "Cosy",
        "A warm blanket: plaid, autumn leaves, handwritten titles and soft marimba.",
        "Un plaid tout chaud : tartan, feuilles d'automne, titres manuscrits et marimba douce.",
    ),
    "futuristic": (
        "Neo Future",
        "Néo-futur",
        "Chrome and light: a dock above a bottom header, hexagons and warp speed.",
        "Chrome et lumière : un dock au-dessus d'un en-tête en bas, hexagones et vitesse lumière.",
    ),
    "minimal": (
        "Minimal",
        "Minimal",
        "Nothing but the essential: top bar, flat cards, narrow page, one word per place.",
        "Rien que l'essentiel : barre du haut, cartes plates, page étroite, un mot par lieu.",
    ),
    "alien": (
        "Xeno",
        "Xéno",
        "The ship's computer: a command line, spores in the dark, motion tracker words.",
        "L'ordinateur de bord : ligne de commande, spores dans le noir, vocabulaire de l'équipage.",
    ),
    "heroes": (
        "Heroes",
        "Super-héros",
        "Hero select: a launcher screen, light rays, bold titles and power stats.",
        "Choix du héros : écran de lancement, rayons de lumière, titres puissants et stats de pouvoirs.",
    ),
    "neowave": (
        "Neowave",
        "Néo-wave",
        "Retro 80s: neon titles, a grid horizon, header at the bottom and chiptune.",
        "Rétro 80 : titres néon, horizon en grille, en-tête en bas et chiptune.",
    ),
    "disco": (
        "Disco",
        "Disco",
        "Mirror ball: a menu that orbits, disco lights, rainbow titles and funky sounds.",
        "Boule à facettes : menu en orbite, lumières disco, titres arc-en-ciel et sons funky.",
    ),
    "cyberpunk": (
        "Cyberpunk",
        "Cyberpunk",
        "Night city: neon rain, a command line on screens and a dock on phones, glitches everywhere.",
        "Night City : pluie de néon, ligne de commande sur écran et dock sur mobile, glitchs partout.",
    ),
    "sincity": (
        "Sin City",
        "Sin City",
        "Black and white with a splash of red: a film-reel navigation, ink-heavy cards, noir notifications that wipe in like a scene change.",
        "Noir et blanc avec une touche de rouge : navigation en pellicule, cartes à l'encre, notifications noires qui entrent comme un changement de plan.",
    ),
    "plex": (
        "Plex",
        "Plex",
        "The media server's look: charcoal and amber, a sidebar on screens and a bottom bar on phones, its own words for your libraries.",
        "Le style du serveur multimédia : anthracite et ambre, barre latérale sur écran et barre du bas sur mobile, ses mots pour vos bibliothèques.",
    ),
}
THEME_TEXT |= {
    "upsidedown": (
        "Upside Down",
        "Monde à l'envers",
        "The other side: red veins, spores drifting up, a string of lights to find your way and notifications that flip up from below.",
        "L'autre côté : veines rouges, spores qui remontent, une guirlande pour s'orienter et des notifications qui se retournent depuis le bas.",
    ),
    "middleearth": (
        "Middle-earth",
        "Terre du Milieu",
        "From the Shire to Mordor: parchment, a map screen to travel, elven notifications, the One Ring and fireworks.",
        "De la Comté au Mordor : parchemin, un écran de carte pour voyager, notifications elfiques, l'Anneau unique et des feux d'artifice.",
    ),
    "vhs": (
        "VHS",
        "VHS",
        "Back to the video store: a blue screen, PLAY ▶, a VCR to zap between sections like channels, bad tracking and tapes rewinding.",
        "Retour au vidéoclub : écran bleu, PLAY ▶, un magnétoscope pour zapper entre les rubriques comme des chaînes, du mauvais tracking et des cassettes qui rembobinent.",
    ),
    "nostromo": (
        "Nostromo",
        "Nostromo",
        "The onboard computer of a commercial starship: phosphor and amber on black, a console docked at the bottom with the ship's clock and a heartbeat, MU/TH/UR's transmissions and the motion tracker's pings.",
        "L'ordinateur de bord d'un cargo spatial : phosphore et ambre sur noir, une console à quai en bas avec l'horloge du vaisseau et un battement de cœur, les transmissions de MU/TH/UR et les bips du détecteur de mouvement.",
    ),
    "nova": (
        "Nova",
        "Nova",
        "Ultra-modern, like a phone: a round button at the bottom opens a sheet of app icons, frosted glass, soft colours and an island for notifications.",
        "Ultra moderne, comme un téléphone : un bouton rond en bas ouvre un volet d'icônes d'applications, du verre dépoli, des couleurs douces et un îlot pour les notifications.",
    ),
}
THEME_RARITY = {
    "orbit": ("epic", 900, 6), "studio": ("rare", 600, None), "wizard": ("legendary", 1500, 12),
    "galaxy": ("legendary", 1500, 12), "matrix": ("legendary", 1500, 12), "desert": ("epic", 900, 6),
    "horror": ("epic", 900, 6), "halloween": ("rare", 600, 3), "christmas": ("epic", 900, 5),
    "comic": ("rare", 600, 3), "manga": ("rare", 600, 3), "cartoon": ("rare", 600, 3), "cozy": ("rare", 600, None),
    "futuristic": ("epic", 900, 6), "minimal": ("common", 300, None), "alien": ("epic", 900, 6),
    "heroes": ("legendary", 1500, 12), "neowave": ("epic", 900, 6), "disco": ("epic", 900, 5),
    "cyberpunk": ("legendary", 1500, 14), "sincity": ("legendary", 1500, 12), "plex": ("epic", 900, 4),
    "upsidedown": ("legendary", 1500, 12), "middleearth": ("legendary", 1500, 12),
    "vhs": ("epic", 900, 5), "nova": ("legendary", 1500, 10), "nostromo": ("legendary", 1500, 12),
}  # fmt: skip
# #89: the universes' interfaces
THEME_TEXT |= {
    "academy": ("Academy", "Académie",
                "A school of magic: scarlet and gold, parchment scrolls, floating candles in the Great Hall, owls bringing your news.",
                "Une école de magie : écarlate et or, parchemins, bougies flottantes dans la Grande Salle, des hiboux qui apportent vos nouvelles."),
    "caribbean": ("Caribbean", "Caraïbes",
                  "Pirates of the islands: a harbour of charts and lanterns, messages in bottles, cannon smoke and doubloons.",
                  "Les pirates des îles : un port de cartes et de lanternes, des bouteilles à la mer, la fumée des canons et des doublons."),
    "mecha": ("Mecha", "Méca",
              "Robots in disguise: steel plates with cut corners, a console docked at the bottom, gears turning and panels that unfold.",
              "Des robots déguisés : des plaques d'acier aux coins coupés, une console à quai en bas, des engrenages qui tournent et des panneaux qui se déplient."),
}  # fmt: skip
THEME_RARITY |= {"academy": ("legendary", 1500, 12), "caribbean": ("epic", 900, 6), "mecha": ("epic", 900, 6)}
THEME_TEXT |= {
    "classicdesk": ("Desktop 2001", "Bureau 2001",
                    "The desktop of the early 2000s: a sky over a green hill, windows with a blue title bar, a taskbar with its Start button and its clock, balloon tips popping out of the tray.",
                    "Le bureau des années 2000 : un ciel au-dessus d'une colline verte, des fenêtres à barre de titre bleue, une barre des tâches avec son bouton Démarrer et son horloge, des info-bulles qui sortent de la zone de notification."),
    "cupertino": ("Cupertino", "Cupertino",
                  "Clean and bright like a fruit-branded laptop: frosted glass, a dock that swells under the pointer, window buttons in three colours, notifications that come out of a genie's lamp.",
                  "Épuré et lumineux comme un portable à la pomme : verre dépoli, un dock qui gonfle sous le pointeur, des boutons de fenêtre en trois couleurs, des notifications qui sortent d'une lampe de génie."),
    "social": ("Social", "Réseau social",
               "A social network's feed: tabs in the middle, your shortcuts on the left, notifications as chat heads, likes and reactions floating up.",
               "Le fil d'un réseau social : des onglets au milieu, vos raccourcis à gauche, des notifications en bulles de discussion, des j'aime et des réactions qui s'envolent."),
}  # fmt: skip
THEME_RARITY |= {"classicdesk": ("epic", 900, 6), "cupertino": ("epic", 900, 6), "social": ("rare", 600, 3)}
THEME_TEXT |= {
    "groove": ("Groove", "Groove",
               "A music app at night: green on black, your sections as playlists in a library, a « now playing » bar to skip from page to page, an equalizer pulsing behind.",
               "Une appli de musique la nuit : vert sur noir, vos rubriques en playlists dans une bibliothèque, une barre « en cours de lecture » pour passer de page en page, un égaliseur qui pulse derrière."),
    "binge": ("Binge", "Binge",
              "A night of series: red on black, a top bar over the posters, cinema glows, « next episode » notifications and a season finale for every level.",
              "Une soirée séries : rouge sur noir, une barre en haut au-dessus des affiches, des lueurs de cinéma, des notifications « épisode suivant » et un final de saison à chaque niveau."),
    "gazette": ("The Gazette", "La Gazette",
                "The portal as a newspaper: its masthead and date line, the sections as its columns, serif type on paper, telegrams and a spinning extra edition.",
                "Le portail en journal : son grand titre et sa date, les rubriques en colonnes, des caractères à empattements sur papier, des télégrammes et une édition spéciale qui tourne."),
}  # fmt: skip
THEME_RARITY |= {"groove": ("epic", 900, 6), "binge": ("epic", 900, 6), "gazette": ("rare", 600, 3)}
THEME_TEXT |= {
    "pocket": ("Pocket console", "Console de poche",
               "A pocket console's green screen: four shades of green, pixel type, a d-pad at the bottom to steer between the sections and their pages, A for the menu, B to go back.",
               "L'écran vert d'une console de poche : quatre nuances de vert, des caractères en pixels, une croix directionnelle en bas pour passer d'une rubrique et d'une page à l'autre, A pour le menu, B pour revenir."),
    "blockfall": ("Blocks", "Blocs",
                  "The falling-blocks puzzle: bright pieces on a night-blue playfield, the sections stacked like pieces on the edge, lines that flash and clear.",
                  "Le casse-tête des blocs qui tombent : des pièces vives sur un plateau bleu nuit, les rubriques empilées comme des pièces sur le bord, des lignes qui clignotent et s'effacent."),
    "invaders": ("Invaders", "Envahisseurs",
                 "The arcade shooter: phosphor green on black, a fleet marching overhead, the sections as your cannon's bunkers and notifications that march in.",
                 "Le jeu de tir d'arcade : vert phosphore sur noir, une flotte qui avance au-dessus, les rubriques en bunkers de votre canon et des notifications qui arrivent en marchant."),
}  # fmt: skip
THEME_RARITY |= {"pocket": ("epic", 900, 6), "blockfall": ("rare", 600, 3), "invaders": ("rare", 600, 3)}
THEME_TEXT |= {
    "mazechase": ("Maze", "Labyrinthe",
                  "The maze chase: blue corridors on black, the sections as a row of pellets with the eater on the current one, ghosts drifting, notifications chomped in.",
                  "La poursuite dans le labyrinthe : des couloirs bleus sur noir, les rubriques en rangée de gommes avec le glouton sur la rubrique courante, des fantômes qui flottent, des notifications croquées."),
    "platformer": ("Platformer", "Plateformes",
                   "The 8-bit platformer: a blue sky, bricks and mystery blocks, a world map to pick your level, coins spinning and a flagpole at the end of every level.",
                   "Le jeu de plateformes 8 bits : un ciel bleu, des briques et des blocs mystère, une carte du monde pour choisir son niveau, des pièces qui tournent et un drapeau au bout de chaque niveau."),
}  # fmt: skip
THEME_RARITY |= {"mazechase": ("rare", 600, 3), "platformer": ("epic", 900, 6)}
THEME_TEXT |= {
    "funky": ("Funky", "Funky",
              "The seventies at full groove: orange, mustard and brown, wavy stripes, a jukebox to choose your section, notifications that strut in.",
              "Les années 70 à plein groove : orange, moutarde et marron, des rayures ondulées, un juke-box pour choisir sa rubrique, des notifications qui arrivent en se déhanchant."),
    "beach": ("Beach", "Plage",
              "A day at the beach: sand and lagoon, a string of beach pennants to find your way, beach balls bouncing, notifications on a striped towel.",
              "Une journée à la plage : sable et lagon, une guirlande de fanions de plage pour s'orienter, des ballons qui rebondissent, des notifications sur une serviette rayée."),
    "blossom": ("Spring", "Printemps",
                "A spring garden: fresh greens and pink, a vine down the side with a leaf for each section, dandelion seeds floating, seed-packet notifications sprouting up.",
                "Un jardin au printemps : des verts frais et du rose, une liane sur le côté avec une feuille par rubrique, des aigrettes de pissenlit qui flottent, des notifications en sachets de graines qui poussent."),
}  # fmt: skip
THEME_RARITY |= {"funky": ("epic", 900, 6), "beach": ("rare", 600, 3), "blossom": ("rare", 600, 3)}
# #130: the cosmos' interfaces
THEME_TEXT |= {
    "observatory": ("Observatory", "Observatoire",
                    "A night at the observatory: navy and brass, a round star chart that turns to choose your section — each a constellation, each page a star — constellations drawing themselves behind, shooting-star notifications.",
                    "Une nuit à l'observatoire : bleu nuit et laiton, une carte du ciel ronde qui tourne pour choisir sa rubrique — chacune une constellation, chaque page une étoile —, des constellations qui se dessinent derrière, des notifications en étoiles filantes."),
    "spacestation": ("Space station", "Station spatiale",
                     "Aboard a space station: cyan readouts on black, your sections as planets on their orbit — open one and its pages go round it like moons — the solar system turning behind, a jump to hyperspace at every level.",
                     "À bord d'une station spatiale : des écrans cyan sur fond noir, vos rubriques en planètes sur leur orbite — ouvrez-en une et ses pages tournent autour comme des lunes —, le système solaire qui tourne derrière, un saut dans l'hyperespace à chaque niveau."),
}  # fmt: skip
THEME_RARITY |= {"observatory": ("legendary", 1500, 10), "spacestation": ("legendary", 1500, 10)}
THEME_TEXT |= {
    "starship": ("Starship", "Vaisseau spatial",
                 "In command of a starship: steel and amber, the ship seen from the side along the bottom of the screen — its engines burning, one compartment per section, the energy gauge and the comms light — asteroids drifting past, mission-control notifications that lift off.",
                 "Aux commandes d'un vaisseau spatial : acier et ambre, le vaisseau vu de profil en bas de l'écran — ses moteurs allumés, un compartiment par rubrique, la jauge d'énergie et le voyant des communications —, des astéroïdes qui défilent, des notifications du contrôle de mission qui décollent."),
}  # fmt: skip
THEME_RARITY |= {"starship": ("legendary", 1600, 20)}

# 027: an interface (the « theme » product) is its colours, fonts, layout, navigation and words; its sold
# looks (animated background, notifications, celebration, level-up) come with its theme pack
PACK_NOTE = (
    " The interface only: its animated background, notifications, celebration and level-up come with its theme pack.",
    " L'interface seule : son fond animé, ses notifications, sa célébration et son passage de niveau sont dans son pack de thème.",
)
for theme, (en, fr, about_en, about_fr) in THEME_TEXT.items():
    rarity, price, level = THEME_RARITY[theme]
    if theme in UNIVERSE_THEMES:
        about_en, about_fr = about_en + PACK_NOTE[0], about_fr + PACK_NOTE[1]
    _p(f"theme_{theme}", "theme", price, rarity, f"{en} interface", f"Interface {fr}", about_en, about_fr,
       {"theme": theme}, collection="themes", icon="palette", featured=False, level=level,
       supply={"legendary": 10, "epic": 25}.get(rarity))  # fmt: skip

# --------------------------------------------------------------------------------- features
_p("widget_poster_wall", "widget", 700, "epic", "Poster wall widget", "Widget mur d'affiches",
   "The 24 most watched titles of the month as a big poster wall on your dashboard.",
   "Les 24 titres les plus vus du mois en grand mur d'affiches sur votre tableau de bord.",
   {"widget": "media.poster_wall"}, collection="widgets", icon="image", featured=True, level=4)  # fmt: skip
_p("quota_requests", "quota", 150, "common", "+5 media requests", "+5 demandes de médias",
   "Five extra media requests this month — two packs a month at most.",
   "Cinq demandes de médias en plus ce mois-ci — deux par mois au plus.",
   {"kind": "media_requests", "units": 5}, collection="essentials", icon="inbox", limit=(2, 30),
   repeatable=True)  # fmt: skip

# #57: saving a title from the library's cleanup (Maintainerr) — spent on the title's page, for everyone
_p("rescue_1", "media_rescue", 600, "rare", "Rescue a title", "Sauvetage d'un titre",
   "A title the library's cleanup was about to delete stays: « Save this title » on its page takes it off the list, for everyone.",
   "Un titre que le nettoyage de la médiathèque allait supprimer reste : « Sauver ce titre » sur sa fiche le retire de la liste, pour tout le monde.",
   {"count": 1}, collection="essentials", icon="shield", level=3, limit=(3, 30), repeatable=True)  # fmt: skip
_p("rescue_3", "media_rescue", 1500, "epic", "Three rescues", "Trois sauvetages",
   "Three titles saved from the cleanup, whenever you need them — cheaper than one by one.",
   "Trois titres sauvés du nettoyage, quand vous en avez besoin — moins cher qu'un par un.",
   {"count": 3}, collection="essentials", icon="shield", level=8, limit=(1, 30), repeatable=True)  # fmt: skip

# #131: a pass for one item won early (a booster, a gift) and still waiting for its level — dear and rare
_p("early_unlock", "early_unlock", 2500, "epic", "Level pass", "Passe-droit",
   "Use it from your reserve on an item you hold but may not wear yet for want of a level: it is yours to wear at once. 25 copies, one a month per member.",
   "À utiliser depuis votre réserve sur un élément que vous possédez mais ne pouvez pas encore porter faute de niveau : il est à vous tout de suite. 25 exemplaires, un par mois et par membre.",
   {}, collection="essentials", icon="key", supply=25, limit=(1, 30), repeatable=True)  # fmt: skip

# #54/#55: perks for the play streak and the gains — consumed, bought again and again (within limits)
_p("streak_freeze_1", "streak_freeze", 120, "common", "Streak freeze", "Gel de série",
   "A missed day no longer breaks your play streak: it is covered automatically, the multiplier goes on.",
   "Un jour manqué ne casse plus votre série de jeu : il est couvert automatiquement, le multiplicateur continue.",
   {"count": 1}, collection="essentials", icon="snowflake", limit=(4, 30), repeatable=True)  # fmt: skip
_p("streak_freeze_3", "streak_freeze", 300, "rare", "Three streak freezes", "Trois gels de série",
   "Three missed days covered — for holidays or a busy week. Cheaper than one by one.",
   "Trois jours manqués couverts — pour les vacances ou une semaine chargée. Moins cher qu'un par un.",
   {"count": 3}, collection="essentials", icon="snowflake", level=3, limit=(2, 30), repeatable=True)  # fmt: skip
_p("boost_xp_15", "xp_boost", 200, "rare", "XP boost x1.5 — 24 h", "Boost d'XP x1,5 — 24 h",
   "All the XP you earn is multiplied by 1.5 for 24 hours, on top of your streak and the events.",
   "Toute l'XP gagnée est multipliée par 1,5 pendant 24 heures, en plus de votre série et des événements.",
   {"factor": 1.5, "hours": 24, "values": ["xp"]}, collection="essentials", icon="rocket", featured=True,
   limit=(3, 7), repeatable=True)  # fmt: skip
_p("boost_xp_2", "xp_boost", 600, "epic", "XP boost x2 — 48 h", "Boost d'XP x2 — 48 h",
   "Twice the XP for two days: the fastest way to the next level.",
   "Deux fois plus d'XP pendant deux jours : le plus court chemin vers le niveau suivant.",
   {"factor": 2, "hours": 48, "values": ["xp"]}, collection="essentials", icon="rocket", level=5,
   limit=(1, 7), repeatable=True)  # fmt: skip


# 027: requests the administrators handle — a film in 4K with one's wishes, a homelab service's access — kept
# for members who take part (a minimum Contribution) and limited in time
def _field(
    key: str, kind: str, en: str, fr: str, options: tuple[str, ...] = (), required: bool = False
) -> dict[str, Any]:
    return {
        "key": key,
        "type": kind,
        "labels": {"en": en, "fr": fr},
        "options": list(options),
        "required": required,
    }


_p("request_4k", "special_request", 1500, "epic", "A film in 4K", "Un film en 4K",
   "Ask for a film in 4K UHD with what matters to you — Dolby Atmos, HDR, languages, subtitles. An administrator finds it within a week; declined, your Coins come back.",
   "Demandez un film en 4K UHD avec ce qui compte pour vous — Dolby Atmos, HDR, langues, sous-titres. Un administrateur le trouve sous une semaine ; refusée, vos Coins vous sont rendus.",
   {"deadline_days": 7, "form": [
       _field("film", "text", "Which film (title and year)", "Quel film (titre et année)", required=True),
       _field("sound", "multi", "Sound", "Son", ("Dolby Atmos", "DTS:X", "Dolby TrueHD 7.1", "5.1")),
       _field("hdr", "choice", "Picture", "Image", ("Dolby Vision", "HDR10+", "HDR10", "No preference")),
       _field("languages", "multi", "Languages", "Langues", ("French (VFF)", "Quebec French (VFQ)", "Original (VO)")),
       _field("subtitles", "choice", "Subtitles", "Sous-titres", ("French", "English", "Forced only", "None")),
       _field("notes", "textarea", "Anything else", "Autre chose"),
   ]},
   collection="essentials", icon="clapperboard", featured=True, level=10, contribution=10, limit=(1, 30),
   repeatable=True)  # fmt: skip
# #59: a TV channel of one's own on the Live TV (Tunarr) — costly, for the members who take part; an
# administrator builds it by hand until Tunarr is automated
_p("request_tv_channel", "special_request", 5000, "legendary", "Your own TV channel", "Votre chaîne TV",
   "A Live TV channel built for you: its name, its theme and what it shows (films, series, a saga, a genre…), on a loop for everyone. An administrator sets it up within two weeks; declined, your Coins come back.",
   "Une chaîne de la TV en direct créée pour vous : son nom, son thème et ce qu'elle diffuse (films, séries, une saga, un genre…), en boucle pour tout le monde. Un administrateur la met en place sous deux semaines ; refusée, vos Coins vous sont rendus.",
   {"deadline_days": 14, "form": [
       _field("name", "text", "Channel name", "Nom de la chaîne", required=True),
       _field("theme", "choice", "Theme", "Thème", ("Films", "Series", "A saga", "A genre", "Cartoons", "Mixed")),
       _field("content", "textarea", "What it shows (titles, saga, genre…)", "Ce qu'elle diffuse (titres, saga, genre…)", required=True),
       _field("order", "choice", "Order", "Ordre", ("Shuffle", "In order", "By release date")),
       _field("notes", "textarea", "Anything else", "Autre chose"),
   ]},
   collection="essentials", icon="tv", featured=True, level=15, contribution=30, limit=(1, 60),
   repeatable=True)  # fmt: skip
for service, en, fr, group, about_en, about_fr in (
    (
        "romm",
        "RomM games",
        "Jeux RomM",
        "romm-users",
        "Your own account on RomM: thousands of retro games to play in the browser, your saves kept.",
        "Votre compte sur RomM : des milliers de jeux rétro à jouer dans le navigateur, vos sauvegardes gardées.",
    ),
    (
        "grimmory",
        "Grimmory library",
        "Bibliothèque Grimmory",
        "grimmory-users",
        "Your own account on Grimmory: the books and audiobooks to read and listen to, your progress kept.",
        "Votre compte sur Grimmory : les livres et livres audio à lire et écouter, votre progression gardée.",
    ),
):
    _p(f"access_{service}", "service_access", 800, "rare", f"{en} access", f"Accès {fr}",
       about_en + " An administrator approves it and your account is created.",
       about_fr + " Un administrateur la valide et votre compte est créé.",
       {"service": service, "group": group, "deadline_days": 3},
       collection="essentials", icon="server", level=5, contribution=30)  # fmt: skip

# --------------------------------------------------------------------------------- dashboard and statistics
for key, widget, en, fr, about_en, about_fr, rarity, price, level in (
    ("widget_media_top", "media.top", "Top of the week widget", "Widget Top de la semaine",
     "The most watched titles of the week with their posters.", "Les titres les plus vus de la semaine, avec leurs affiches.",
     "rare", 400, None),
    ("widget_media_upcoming", "media.upcoming", "Upcoming releases widget", "Widget Prochaines sorties",
     "The films and episodes coming to the library.", "Les films et épisodes qui arrivent dans la bibliothèque.",
     "rare", 350, None),
    ("widget_my_soon", "media.my_soon", "My requests coming soon widget", "Widget Mes demandes bientôt là",
     "Your requests about to arrive: downloading, importing, coming out.",
     "Vos demandes sur le point d'arriver : en téléchargement, en import, bientôt dans les salles.",
     "common", 200, None),
    # 027: small widgets to lay out a dashboard
    ("widget_progress", "dashboard.progress", "Progress bar widget", "Widget Barre de progression",
     "Your level, today's objectives, quests or achievements as a bar across.",
     "Votre niveau, vos objectifs du jour, vos quêtes ou vos succès en barre horizontale.",
     "common", 150, None),
    ("widget_progress_vertical", "dashboard.progress_vertical", "Progress column widget",
     "Widget Colonne de progression", "The same progress as an upright column that fills up.",
     "La même progression en colonne verticale qui se remplit.", "rare", 250, None),
    ("widget_separator", "dashboard.separator", "Separator widget", "Widget Séparateur",
     "A line, dots, a gradient or space — with a label — to group your widgets.",
     "Une ligne, des points, un dégradé ou de l'espace — avec un libellé — pour regrouper vos widgets.",
     "common", 100, None),
    ("widget_clock", "dashboard.clock", "Clock widget", "Widget Horloge",
     "The time and the date, big, on your dashboard.", "L'heure et la date, en grand, sur votre tableau de bord.",
     "common", 120, None),
    ("widget_note", "dashboard.note", "Sticky note widget", "Widget Post-it",
     "A coloured note for yourself on your dashboard.", "Un post-it coloré pour vous sur votre tableau de bord.",
     "common", 120, None),
    ("widget_countdown", "dashboard.countdown", "Countdown widget", "Widget Compte à rebours",
     "The days left until the date you choose: a holiday, a release, a birthday.",
     "Les jours restants jusqu'à la date de votre choix : des vacances, une sortie, un anniversaire.",
     "rare", 250, None),
):  # fmt: skip
    _p(key, "widget", price, rarity, en, fr, about_en, about_fr, {"widget": widget}, collection="widgets",
       icon="dashboard", level=level)  # fmt: skip

for key, option, en, fr, rarity, price in (
    ("opt_stats_area", "media.stats:chart=area", "Area chart for « My statistics »", "Graphique en aires pour « Mes statistiques »", "rare", 250),
    ("opt_stats_donut", "media.stats:chart=donut", "Donut chart for « My statistics »", "Graphique en anneau pour « Mes statistiques »", "rare", 300),
    ("opt_stats_top", "media.stats:chart=top", "Top list for « My statistics »", "Classement pour « Mes statistiques »", "epic", 450),
    ("opt_stats_year", "media.stats:period=365d", "One-year period for « My statistics »", "Période d'un an pour « Mes statistiques »", "rare", 250),
    ("opt_stats_all", "media.stats:period=all", "All-time period for « My statistics »", "Depuis toujours pour « Mes statistiques »", "epic", 500),
    ("opt_stats_server", "media.stats:scope=all", "Whole server for « My statistics »", "Tout le serveur pour « Mes statistiques »", "rare", 300),
    ("opt_requests_server", "media.recently_requested:scope=all", "Whole server for « Recently requested »", "Tout le serveur pour « Demandes récentes »", "rare", 250),
    # #52: « Chart » — CPU and memory are free; the other series and the week are sold
    ("opt_chart_storage", "health.chart:series=storage", "Storage over time for « Chart »", "Stockage dans le temps pour « Graphique »", "common", 200),
    ("opt_chart_temperature", "health.chart:series=temperature", "Temperatures for « Chart »", "Températures pour « Graphique »", "rare", 300),
    ("opt_chart_week", "health.chart:range=7d", "A week of history for « Chart »", "Une semaine d'historique pour « Graphique »", "epic", 450),
):  # fmt: skip
    _p(key, "widget_option", price, rarity, en, fr,
       "One more setting for this dashboard widget — chosen in its settings once bought.",
       "Une option de réglage en plus pour ce widget — à choisir dans ses réglages une fois achetée.",
       {"option": option}, collection="widgets", icon="settings")  # fmt: skip

# #53: what says much about the server — the administrators have it; members buy it, and only once they
# have given to the community (a contribution minimum)
_p("opt_chart_network", "widget_option", 600, "epic", "Network traffic for « Chart »", "Trafic réseau pour « Graphique »",
   "The server's network traffic over time in your « Chart » — for those who take part.",
   "Le trafic réseau du serveur dans le temps, dans votre « Graphique » — pour ceux qui s'investissent.",
   {"option": "health.chart:series=network"}, collection="widgets", icon="activity", contribution=30)  # fmt: skip
_p("widget_server", "widget", 1500, "legendary", "Server widget", "Widget Serveur",
   "The server at a glance: processor, memory, temperature, network, uptime and what needs attention.",
   "Le serveur d'un coup d'œil : processeur, mémoire, température, réseau, temps de fonctionnement et ce qui demande attention.",
   {"widget": "health.host"}, collection="widgets", icon="cpu", level=10, contribution=30)  # fmt: skip
_p("widget_containers", "widget", 2500, "legendary", "Containers widget", "Widget Conteneurs",
   "The server's containers: which run, which have an update, and what the server warns about.",
   "Les conteneurs du serveur : lesquels tournent, lesquels ont une mise à jour, et ce que le serveur signale.",
   {"widget": "health.containers"}, collection="widgets", icon="package", level=15, contribution=30)  # fmt: skip
_p("widget_downloads", "widget", 1500, "legendary", "Downloads widget", "Widget Téléchargements",
   "What is coming to the server: each title being downloaded, its progress, speed, peers and time left.",
   "Ce qui arrive sur le serveur : chaque titre en téléchargement, sa progression, sa vitesse, ses pairs et le temps restant.",
   {"widget": "media.downloads"}, collection="widgets", icon="download", level=10, contribution=30)  # fmt: skip

# 027 (#30, #31): the widgets' other looks — the original one stays free; these are picked in a widget's
# settings (« Visual ») once bought
for key, option, en, fr, rarity, price in (
    ("opt_style_continue_ambient", "media.continue:style=ambient", "Ambient light for « Continue »", "Lumière d'ambiance pour « Continuer »", "rare", 350),
    ("opt_style_services_pulse", "health.services_summary:style=pulse", "Heartbeat for « Services »", "Pouls pour « Services »", "rare", 300),
    ("opt_style_progress_odometer", "gamification.progress:style=odometer", "Odometer for « My progression »", "Compteur animé pour « Ma progression »", "epic", 450),
    ("opt_style_progress_chart", "gamification.progress:style=chart", "Curves for « My progression »", "Courbes pour « Ma progression »", "epic", 500),
    ("opt_style_daily_liquid", "gamification.daily_objectives:style=liquid", "Liquid gauges for « Daily objectives »", "Jauges liquides pour « Objectifs du jour »", "rare", 300),
    ("opt_style_added_deck", "media.recently_added:style=deck", "Card deck for « Recently added »", "Pile de cartes pour « Ajouts récents »", "common", 200),
    ("opt_style_releases_deck", "media.recent_releases:style=deck", "Card deck for « Recent releases »", "Pile de cartes pour « Sorties récentes »", "common", 200),
    ("opt_style_requested_deck", "media.recently_requested:style=deck", "Card deck for « Recently requested »", "Pile de cartes pour « Demandes récentes »", "common", 200),
    ("opt_style_stats_countup", "media.stats:style=countup", "Counting figures for « My statistics »", "Chiffres animés pour « Mes statistiques »", "common", 200),
    ("opt_style_wall_kenburns", "media.poster_wall:style=kenburns", "Travelling camera for the poster wall", "Travelling pour le mur d'affiches", "epic", 500),
    ("opt_style_news_ticker", "news.latest:style=carousel", "Carousel for « Latest news »", "Carrousel pour « Dernières actualités »", "common", 200),  # the key predates the carousel
    ("opt_style_clock_analog", "dashboard.clock:style=analog", "Analog face for the clock", "Cadran analogique pour l'horloge", "rare", 250),
    ("opt_style_countdown_flip", "dashboard.countdown:style=flip", "Flip digits for the countdown", "Chiffres à palettes pour le compte à rebours", "rare", 250),
    ("opt_style_activity_live", "community.activity:style=live", "Live feed for « Community activity »", "Fil en direct pour « Activité de la communauté »", "common", 200),
):  # fmt: skip
    _p(key, "widget_option", price, rarity, en, fr,
       "Another look for this dashboard widget — its original look stays yours. Chosen in its settings once bought.",
       "Un autre visuel pour ce widget — son visuel d'origine reste disponible. À choisir dans ses réglages une fois acheté.",
       {"option": option}, collection="widgets", icon="sparkles")  # fmt: skip

_p("widget_on_this_day", "widget", 450, "rare", "A year ago widget", "Widget Il y a un an",
   "Around this date, a year or more ago: what you watched, what came into the library.",
   "Autour de cette date, il y a un an ou plus : ce que vous regardiez, ce qui arrivait dans la bibliothèque.",
   {"widget": "media.on_this_day"}, collection="widgets", icon="dashboard")  # fmt: skip
_p("widget_next_releases", "widget", 500, "epic", "Next releases widget", "Widget Prochaines sorties",
   "What comes out next among what you asked for and the series you follow — with a live countdown.",
   "Ce qui sort bientôt parmi vos demandes et les séries que vous suivez — avec un décompte en direct.",
   {"widget": "media.next_releases"}, collection="widgets", icon="dashboard")  # fmt: skip
_p("widget_living_wall", "widget", 650, "epic", "Living wall widget", "Widget Mur vivant",
   "A wall of posters from the library that turn one by one to reveal others.",
   "Un mur d'affiches de la bibliothèque qui se retournent une à une pour en révéler d'autres.",
   {"widget": "media.living_wall"}, collection="widgets", icon="dashboard")  # fmt: skip

for name, en, fr, rarity, price, level in (
    ("when", "When you watch", "Vos moments de visionnage", "rare", 300, None),
    ("genres", "Your favourite genres", "Vos genres préférés", "rare", 300, None),
    ("people", "Actors and directors", "Acteurs et réalisateurs", "epic", 500, 4),
    ("decades", "By decade", "Par décennie", "common", 200, None),
    ("records", "Your records", "Vos records", "rare", 350, None),
    ("box_office", "Box office of your films", "Box-office de vos films", "epic", 600, 5),
    ("platforms", "Your platforms", "Vos plateformes", "common", 200, None),
):  # fmt: skip
    _p(f"stat_{name}", "statistic", price, rarity, f"Statistic: {en}", f"Statistique : {fr}",
       f"Unlocks « {en} » in the Media statistics.", f"Débloque « {fr} » dans les statistiques Médias.",
       {"statistic": f"media.insights.{name}"}, collection="statistics", icon="chart", level=level)  # fmt: skip

# 061: more of the statistics sold — the tabs in depth, the long history, the whole server, and the deeper
# statistics of « My requests »; the overview, the chart, the top titles and periods up to a year stay free
for key, statistic, en, fr, about_en, about_fr, rarity, price, level, contribution in (
    ("stat_tab_casting", "media.insights.tab.casting", "Casting in depth", "Le casting en détail",
     "The « Casting » tab: the actors and directors you watch most, with their portraits, compared with the period before.",
     "L'onglet « Casting » : les acteurs et réalisateurs que vous regardez le plus, avec leurs portraits, comparés à la période précédente.",
     "rare", 400, None, None),
    ("stat_tab_production", "media.insights.tab.production", "Production in depth", "La production en détail",
     "The « Production » tab: the years and countries of your films, their budgets and box office, successes and flops.",
     "L'onglet « Production » : les années et pays de vos films, leurs budgets et box-office, succès et flops.",
     "epic", 550, 4, None),
    ("stat_tab_playback", "media.insights.tab.playback", "Playback in depth", "La lecture en détail",
     "The « Playback » tab: direct play or transcoding, picture quality, platforms and devices.",
     "L'onglet « Lecture » : lecture directe ou transcodage, qualité d'image, plateformes et appareils.",
     "rare", 450, None, None),
    ("stat_tab_profile", "media.insights.tab.profile", "Your viewer profile", "Votre profil de spectateur",
     "The « Profile » tab: your viewer portrait — genres new, rising or gone, your hours and days, what you finish.",
     "L'onglet « Profil » : votre portrait de spectateur — genres nouveaux, en hausse ou délaissés, vos heures et jours, ce que vous terminez.",
     "epic", 600, 5, None),
    ("stat_history", "media.insights.history", "Full history", "Historique complet",
     "Go back further than a year: the year to date, any past year, all time — in Media statistics and My requests.",
     "Remontez au-delà d'un an : l'année en cours, n'importe quelle année passée, depuis toujours — dans les statistiques Médias et Mes demandes.",
     "epic", 700, 5, None),
    ("stat_server", "media.insights.server", "The whole server's statistics", "Les statistiques de tout le serveur",
     "What the whole community watches, listens to and reads — anonymous, for those who take part.",
     "Ce que toute la communauté regarde, écoute et lit — anonyme, pour celles et ceux qui participent.",
     "legendary", 1200, 10, 30),
    ("stat_req_watched", "media.requests.watched", "What became of my requests", "Ce que sont devenues mes demandes",
     "In My requests: how many of the titles you asked for you actually watched.",
     "Dans Mes demandes : combien des titres demandés vous avez vraiment regardés.",
     "common", 150, None, None),
    ("stat_req_ranking", "media.requests.ranking", "My rank among requesters", "Mon rang parmi les demandeurs",
     "In My requests: your position among the members who ask (anonymous) and how it moves.",
     "Dans Mes demandes : votre position parmi les membres qui demandent (anonyme) et son évolution.",
     "rare", 300, None, None),
    ("stat_req_top_watched", "media.requests.top_watched", "Community favourites", "Les favoris de la communauté",
     "In My requests: the titles you asked for that the community watches most.",
     "Dans Mes demandes : les titres que vous avez demandés et que la communauté regarde le plus.",
     "rare", 300, None, None),
    ("stat_req_genres", "media.requests.genres", "Requested vs watched genres", "Genres demandés vs regardés",
     "In My requests: the genres you ask for against the genres you watch.",
     "Dans Mes demandes : les genres que vous demandez face à ceux que vous regardez.",
     "common", 200, None, None),
    ("stat_req_acquisition", "media.requests.acquisition", "Arrival times", "Délais d'arrivée",
     "In My requests: how long your requests take to arrive, step by step.",
     "Dans Mes demandes : le temps que mettent vos demandes à arriver, étape par étape.",
     "rare", 350, 3, None),
):  # fmt: skip
    _p(key, "statistic", price, rarity, f"Statistic: {en}", f"Statistique : {fr}", about_en, about_fr,
       {"statistic": statistic}, collection="statistics", icon="chart", level=level,
       contribution=contribution)  # fmt: skip

_p("project_launch", "project_launch", 1500, "epic", "Launch a community project", "Lancer un projet communautaire",
   "Ask for a feature or a project: name it and pitch it, it opens as a proposal in the community projects for everyone to fund.",
   "Demandez une fonctionnalité ou un projet : donnez-lui un titre et un pitch, il s'ouvre en proposition dans les projets de la communauté pour que chacun le finance.",
   {"kind": "feature"}, collection="essentials", icon="lightbulb", featured=True, level=5, limit=(1, 30),
   repeatable=True)  # fmt: skip

# --------------------------------------------------------------------------------- packs
UNIVERSES = {  # theme: banner, frame, name, notification style or animation, celebration, ambient, badge, title
    "wizard": (
        "banner_castle",
        "frame_runes",
        "name_wizard",
        "notif_parchment",
        "effect_aurora",
        "ambient_sparkles",
        "badge_archmage",
        "title_archmage",
    ),
    "galaxy": (
        "banner_hyperspace",
        "frame_orbit",
        "name_galaxy",
        "notif_hologram",
        "effect_portal",
        "ambient_starfield",
        "badge_ace_pilot",
        "title_star_keeper",
    ),
    "matrix": (
        "banner_code",
        "frame_code",
        "name_matrix",
        "notif_terminal",
        "effect_assemble",
        "ambient_code_rain",
        "badge_the_one",
        "title_awakened",
    ),
    "desert": (
        "banner_dunes",
        "frame_sand",
        "name_desert",
        "notif_glass",
        "effect_coins",
        "ambient_sand",
        "badge_spice_master",
        "title_sand_lord",
    ),
    "horror": (
        "banner_bloodmoon",
        "frame_blood",
        "name_horror",
        "notif_glitch",
        "effect_burn",
        "ambient_fog",
        "badge_survivor",
        "title_damned",
    ),
    "halloween": (
        "banner_halloween",
        "frame_pumpkin",
        "name_halloween",
        "notif_bounce",
        "effect_pumpkin",
        "ambient_bats",
        "badge_pumpkin_king",
        None,
    ),
    "christmas": (
        "banner_snowfall",
        "frame_holly",
        "name_christmas",
        "notif_paper",
        "effect_snow",
        "ambient_snow",
        "badge_elf",
        "title_head_elf",
    ),
    "comic": (
        "banner_pow",
        "frame_pow",
        "name_comic",
        "notif_comic",
        "effect_lightning",
        None,
        "badge_sunday_hero",
        None,
    ),
    "manga": (
        "banner_speedlines",
        "frame_sakura",
        "name_manga",
        "notif_slam",
        "effect_petals",
        "ambient_petals",
        "badge_senpai",
        "title_otaku",
    ),
    "cartoon": (
        "banner_toon",
        "frame_rainbow",
        "name_cartoon",
        "notif_bounce",
        "effect_bubbles",
        "ambient_bubbles",
        "badge_prankster",
        "title_toon_star",
    ),
    "cozy": (
        "banner_cabin",
        "frame_sakura",
        "name_cozy",
        "notif_paper",
        "effect_hearts",
        "ambient_leaves",
        "badge_golden_blanket",
        "title_nap_champion",
    ),
    "futuristic": (
        "banner_neon_grid",
        "frame_chrome",
        "name_futuristic",
        "notif_hologram",
        "effect_shatter",
        "ambient_warp",
        "badge_engineer",
        None,
    ),
    "minimal": (
        "banner_mono",
        "frame_chrome",
        "name_minimal",
        "notif_drop",
        None,
        None,
        "badge_purist",
        "title_less_is_more",
    ),
    "alien": (
        "banner_nebula",
        "frame_toxic",
        "name_alien",
        "notif_terminal",
        "effect_freeze",
        "ambient_spores",
        "badge_xenobiologist",
        None,
    ),
    "heroes": (
        "banner_skyline",
        "frame_hero",
        "name_hero",
        "notif_slam",
        "effect_lightning",
        None,
        "badge_vigilante",
        "title_neighbourhood_hero",
    ),
    "neowave": (
        "banner_synthwave",
        "frame_neon",
        "name_neowave",
        "notif_neon",
        "effect_aurora",
        None,
        "badge_arcade_king",
        None,
    ),
    "disco": (
        "banner_mirrorball",
        "frame_disco",
        "name_disco",
        "notif_spiral",
        "effect_confetti",
        "ambient_disco",
        "badge_dancing_king",
        "title_saturday_fever",
    ),
    "cyberpunk": (
        "banner_night_city",
        "frame_cyber",
        "name_cyberpunk",
        "notif_glitch",
        "effect_glitch",
        "ambient_rain",
        "badge_netrunner",
        "title_night_city",
    ),
}
UNIVERSES |= {  # 027: the Upside Down and Middle-earth
    "upsidedown": ("banner_upsidedown", "frame_veins", "name_upsidedown", "notif_upsidedown", "effect_flicker",
                   "ambient_upsidedown", "badge_demohunter", "title_friends_dont_lie"),
    "middleearth": ("banner_shire", "frame_onering", "name_elvish", "notif_elven", "effect_fireworks",
                    "ambient_meadow", "badge_grey_wizard", "title_shall_not_pass"),
}  # fmt: skip
UNIVERSES |= {  # 027: the two new universes
    "sincity": ("banner_mono", "frame_blood", "name_minimal", "notif_noir", "effect_shatter", "ambient_fog",
                "badge_vigilante", "title_night_city"),
    "plex": ("banner_skyline", "frame_chrome", "name_futuristic", "notif_split", "effect_glitch", None,
             "badge_golden_cinephile", "title_cinephile"),
}  # fmt: skip
UNIVERSES |= {  # 027: the VHS tape and the phone-like Nova
    "vhs": ("banner_vhs", "frame_vhs", "name_vhs", "notif_vhs", "effect_rewind", "ambient_vhs", "badge_video_club",
            "title_be_kind_rewind"),
    "nova": ("banner_mesh", "frame_rings", "name_nova", "notif_island", "effect_bloom", "ambient_bokeh",
             "badge_early_adopter", "title_one_more_thing"),
    "nostromo": ("banner_nostromo", "frame_tracker", "name_nostromo", "notif_nostromo", "effect_tracker",
                 "ambient_nostromo", "badge_last_survivor", "title_crew_expendable"),
}  # fmt: skip
# 027: each universe's level badge, notification look and level-up moment
UNIVERSE_EXTRAS = {
    "wizard": ("level_crest", "notif_portal", "levelup_spell"), "galaxy": ("level_blackhole", "notif_saga", "notif_filmwipe",
    "levelup_cosmic", "levelup_crawl"), "matrix": ("level_vhs", "notif_vhs", "levelup_decode"), "desert": ("level_gem", "notif_earth", "levelup_sandstorm"),
    "horror": ("level_melt", "notif_melt", "levelup_bloodmoon"), "halloween": ("level_inferno", "notif_fire", "levelup_pumpkin"),
    "christmas": ("level_gem", "notif_air", "levelup_gift"), "comic": ("level_kapow", "notif_kapow", "levelup_comic"),
    "manga": ("level_kapow", "notif_manga", "levelup_comic", "levelup_manga"), "cartoon": ("level_pixel", "notif_jelly", "levelup_boing"),
    "cozy": ("level_crest", "ambient_lanterns", "levelup_hearth"), "futuristic": ("level_hologram", "notif_iris", "levelup_hud"),
    "minimal": ("level_neon", "notif_focus", "levelup_minimal"), "alien": ("level_portal", "notif_portal", "levelup_cosmic", "levelup_abduction"),
    "heroes": ("level_kapow", "notif_kapow", "levelup_comic", "levelup_hero"), "neowave": ("level_vhs", "ambient_vhs", "levelup_synthwave"),
    "disco": ("level_hologram", "notif_jelly", "levelup_disco"), "cyberpunk": ("level_neon", "notif_vhs", "levelup_arcade", "levelup_glitch"),
    "sincity": ("level_melt", "notif_filmwipe", "notif_noir", "levelup_noir"), "plex": ("level_neon", "notif_iris", "levelup_spotlight"),
    "upsidedown": ("level_upsidedown", "level_veins", "level_lights", "notif_flipup", "levelup_upsidedown", "levelup_rift",
                   "banner_hawkins", "frame_lights", "bg_upsidedown", "ambient_veins", "palette_hawkins",
                   "badge_upside_survivor", "badge_party", "badge_walkie", "title_mouth_breather", "title_hawkins_hero"),
    "middleearth": ("level_onering", "level_eye", "level_mithril", "notif_onering", "notif_balrog", "notif_eye",
                    "levelup_onering", "banner_mordor", "banner_pixelshire", "frame_elven", "name_mordor", "bg_meadow",
                    "bg_ash", "ambient_ash", "palette_gondor", "badge_hobbit", "badge_pixel_quest",
                    "title_second_breakfast"),
    "vhs": ("level_vhs", "level_cassette", "notif_tracking", "levelup_vhs", "bg_vhs", "palette_vhs", "badge_rewinder",
            "badge_be_kind_rewind", "title_late_fees"),
    "nova": ("level_squircle", "notif_morph", "levelup_nova", "bg_bokeh", "palette_nova", "badge_power_user",
             "title_beta_tester"),
    "nostromo": ("level_tracker", "notif_uplink", "levelup_nostromo", "bg_nostromo", "palette_nostromo",
                 "badge_interface_2037", "badge_space_trucker", "title_perfect_organism"),
}  # fmt: skip


def _looks(items: tuple[tuple[Any, ...], ...], *, season: str | None = None) -> tuple[list[str], list[str]]:
    """#81, #89: a season's or a universe's looks from short rows (kind, design, names, price, level, texts):
    the products made, and those drawn by the graphics chip among them."""
    made: list[str] = []
    _hd: list[str] = []
    _season = season
    for _item in items:
        _before = len(SHOP)
        _kind = _item[0]
        if _kind == "ambient":
            _, _v, _en, _fr, _price, _level, _aen, _afr = _item
            _p(
                f"ambient_{_v}",
                "ambient",
                _price,
                "common",
                f"{_en} ambience",
                f"Ambiance {_fr.lower()}",
                _aen,
                _afr,
                {"ambient": _v},
                collection="ambients",
                icon="sparkles",
                level=_level,
                season=_season,
            )
        elif _kind == "live":
            _, _v, _en, _fr, _price, _level, _aen, _afr = _item
            _p(
                f"banner_live_{_v}",
                "profile_banner",
                _price,
                "common",
                f"{_en} animated banner",
                f"Bannière animée {_fr}",
                f"{_en} playing in your profile's banner, for every visitor to see.",
                f"Des {_fr} dans la bannière de votre profil, pour tous vos visiteurs.",
                {"banner": f"live-{_v}"},
                collection="profile",
                icon="image",
                level=_level,
                season=_season,
            )
        elif _kind == "effect":
            _, _v, _en, _fr, _price, _level, _aen, _afr = _item
            _p(
                f"effect_{_v}",
                "effect",
                _price,
                "common",
                f"{_en} celebration",
                f"Célébration {_fr.lower()}",
                _aen,
                _afr,
                {"effect": _v},
                collection="celebrations",
                icon="party",
                level=_level,
                season=_season,
            )
        elif _kind == "palette":
            _, _v, _en, _fr, _price, _level, _aen, _afr = _item
            _p(
                f"palette_{_v}",
                "palette",
                _price,
                "common",
                f"{_en} palette",
                f"Palette {_fr.lower()}",
                _aen,
                _afr,
                {"palette": _v},
                collection="palettes",
                icon="palette",
                level=_level,
                season=_season,
            )
        elif _kind == "name":
            _, _v, _en, _fr, _price, _level, _aen, _afr = _item
            _p(
                f"name_{_v}",
                "name_style",
                _price,
                "common",
                f"{_en} name style",
                f"Style de nom {_fr}",
                _aen,
                _afr,
                {"style": _v},
                collection="names",
                icon="feather",
                level=_level,
                season=_season,
            )
        elif _kind == "banner":
            _, _v, _en, _fr, _price, _level, _aen, _afr = _item
            _p(
                f"banner_{_v}",
                "profile_banner",
                _price,
                "common",
                f"{_en} banner",
                f"Bannière {_fr.lower()}",
                _aen,
                _afr,
                {"banner": _v},
                collection="profile",
                icon="image",
                level=_level,
                season=_season,
            )
        elif _kind == "title":
            _, _label, _fr, _style, _price, _level, _, _ = _item
            _p(
                f"title_{_label.lower().replace(' ', '_').replace(chr(39), '')}",
                "title",
                _price,
                "common",
                f"Title: {_label}",
                _fr,
                f"« {_label} » under your name.",
                f"« {_label} » sous votre nom.",
                {"label": _label, "style": _style},
                collection="titles",
                icon="trophy",
                level=_level,
                season=_season,
            )
        elif _kind == "badge":
            _, _label, _fr, _icon, _style, _price, _level, _, _ = _item
            _p(
                f"badge_{_label.lower().replace(' ', '_').replace(chr(39), '')}",
                "badge",
                _price,
                "common",
                f"{_label} badge",
                _fr,
                f"A « {_label} » badge on your profile.",
                f"Un badge « {_label} » sur votre profil.",
                {"label": _label, "icon": _icon, "style": _style},
                collection="badges",
                icon="star",
                level=_level,
                season=_season,
            )
        elif _kind == "frame":
            _, _v, _en, _fr, _price, _level, _aen, _afr = _item
            _p(
                f"frame_{_v}",
                "avatar_frame",
                _price,
                "rare",
                f"{_en} frame",
                f"Cadre {_fr.lower()}",
                _aen,
                _afr,
                {"frame": _v},
                collection="profile",
                icon="user",
                level=_level,
                season=_season,
            )
        elif _kind == "level":
            _, _v, _en, _fr, _price, _level, _aen, _afr = _item
            _p(
                f"level_{_v}",
                "level_badge",
                _price,
                "rare",
                f"{_en} level badge",
                f"Badge de niveau {_fr.lower()}",
                _aen,
                _afr,
                {"style": _v},
                collection="levels",
                icon="trophy",
                level=_level,
                season=_season,
            )
        elif _kind == "notif":
            _, _v, _en, _fr, _price, _level, _aen, _afr = _item
            _p(
                f"notif_{_v}",
                "notification_style",
                _price,
                "rare",
                f"{_en} notifications",
                f"Notifications {_fr.lower()}",
                _aen,
                _afr,
                {"style": _v},
                collection="looks",
                icon="bell",
                level=_level,
                season=_season,
            )
        elif _kind == "hdframe":
            _, _v, _en, _fr, _price, _level, _aen, _afr = _item
            _key = f"frame_{_v}"
            _p(
                _key,
                "avatar_frame",
                _price,
                "legendary" if _key in SEASONAL_LEGENDARY else "epic",
                f"{_en} frame",
                f"Cadre {_fr.lower()}",
                _aen,
                _afr,
                {"frame": _v},
                collection="profile",
                icon="user",
                level=_level,
                season=_season,
            )
            _hd.append(_key)
        elif _kind == "hdname":
            _, _v, _en, _fr, _price, _level, _, _ = _item
            _key = f"name_name{_v}"
            _p(
                _key,
                "name_style",
                _price,
                "legendary" if _key in SEASONAL_LEGENDARY else "epic",
                f"{_en} name style",
                f"Style de nom {_fr}",
                f"An aura around your name. {HD_ABOUT[0]}",
                f"Une aura autour de votre nom. {HD_ABOUT[1]}",
                {"style": f"name{_v}"},
                collection="names",
                icon="feather",
                level=_level,
                season=_season,
            )
            _hd.append(_key)
        elif _kind == "hdlevel":
            _, _v, _en, _fr, _price, _level, _aen, _afr = _item
            _key = f"level_{_v}"
            _p(
                _key,
                "level_badge",
                _price,
                "legendary" if _key in SEASONAL_LEGENDARY else "epic",
                f"{_en} level badge",
                f"Badge de niveau {_fr.lower()}",
                _aen,
                _afr,
                {"style": _v},
                collection="levels",
                icon="trophy",
                level=_level,
                season=_season,
            )
            _hd.append(_key)
        elif _kind == "anim":
            _, _v, _en, _fr, _price, _level, _aen, _afr = _item
            _p(f"notif_{_v}", "notification_animation", _price, "rare", f"{_en} notification animation",
               f"Animation de notification {_fr.lower()}", _aen, _afr, {"animation": _v}, collection="looks",
               icon="bell-ring", level=_level, season=_season)  # fmt: skip
        elif _kind == "levelup":
            _, _v, _en, _fr, _price, _level, _aen, _afr = _item
            _p(f"levelup_{_v}", "level_up", _price, "epic", f"{_en} level-up", f"Passage de niveau {_fr.lower()}",
               _aen, _afr, {"animation": _v}, collection="levels", icon="trophy", level=_level, season=_season)  # fmt: skip
        made.extend(product["key"] for product in SHOP[_before:])
    return made, _hd


# #89: the universes' looks — every kind, most of them common; shapes of their own (a shield, a ship's wheel, a
# winged ball, a bottle…)
UNIVERSE_ROWS: dict[str, tuple[tuple[Any, ...], ...]] = {
    "academy": (
        ("ambient", "floatingcandles", "Floating candles", "Bougies flottantes", 300, None,
         "Candles hanging in the air, bobbing, their flames flickering.", "Des bougies suspendues dans les airs qui flottent, leurs flammes qui vacillent."),
        ("live", "floatingcandles", "Floating candles", "bougies flottantes", 350, None, "", ""),
        ("banner", "greathall", "Great Hall", "Grande Salle", 300, None,
         "Long tables under an enchanted night sky, candles floating.", "De longues tables sous un ciel nocturne enchanté, des bougies qui flottent."),
        ("effect", "wandsparks", "Wand sparks", "Étincelles de baguette", 250, None,
         "Gold and scarlet sparks shooting out of the reward.", "Des étincelles d'or et d'écarlate qui jaillissent de la récompense."),
        ("palette", "scarletgold", "Scarlet and gold", "Écarlate et or", 200, None,
         "A house's scarlet and gold over the theme.", "L'écarlate et l'or d'une maison sur le thème."),
        ("name", "spellbound", "Spellbound", "ensorcelé", 300, None,
         "A name in uncial letters of shimmering gold.", "Un nom en lettres onciales d'or chatoyant."),
        ("title", "Head prefect", "Titre : Préfet en chef", "shimmer", 150, None, "", ""),
        ("badge", "Seeker", "Badge Attrapeur", "sparkle", "gold", 200, None, "", ""),
        ("frame", "housecrest", "House crest", "Blason de maison", 650, 4,
         "Your avatar on a house's quartered shield.", "Votre avatar sur l'écu écartelé d'une maison."),
        ("level", "snitch", "Golden snitch", "Balle dorée ailée", 700, 4,
         "Your level on a golden ball beating its little wings.", "Votre niveau sur une balle dorée qui bat de ses petites ailes."),
        ("notif", "scroll", "Scroll", "Parchemin enroulé", 650, 4,
         "Notifications unrolled like a scroll between its two rolls.", "Des notifications déroulées comme un parchemin entre ses deux rouleaux."),
        ("anim", "swoop", "Owl swoop", "Piqué du hibou", 650, 4,
         "Notifications swooping in like an owl bringing the mail.", "Des notifications qui arrivent en piqué comme un hibou qui apporte le courrier."),
        ("levelup", "owlpost", "Owl post", "Hibou postal", 1100, 8,
         "An owl swoops in with a letter: your new level, under a sky of gold sparkles.",
         "Un hibou arrive en piqué avec une lettre : votre nouveau niveau, sous un ciel d'étincelles dorées."),
    ),
    "caribbean": (
        ("ambient", "cannonsmoke", "Cannon smoke", "Fumée de canon", 300, None,
         "Puffs of cannon smoke drifting across.", "Des bouffées de fumée de canon qui dérivent."),
        ("live", "cannonsmoke", "Cannon smoke", "fumée de canon", 350, None, "", ""),
        ("banner", "jollyship", "Ship at night", "Navire de nuit", 300, None,
         "A ship under full sail on a moonlit sea.", "Un navire toutes voiles dehors sur une mer sous la lune."),
        ("effect", "cannonball", "Cannonballs", "Boulets de canon", 250, None,
         "Cannonballs bursting out of the reward in a puff of smoke.", "Des boulets de canon qui jaillissent de la récompense dans un nuage de fumée."),
        ("palette", "rum", "Rum and lagoon", "Rhum et lagon", 200, None,
         "Amber rum and lagoon turquoise over the theme.", "Rhum ambré et turquoise du lagon sur le thème."),
        ("name", "pirata", "Pirate", "pirate", 300, None,
         "A name in a pirate's blackletter, old gold.", "Un nom en gothique de pirate, vieil or."),
        ("title", "Terror of the seven seas", "Titre : Terreur des sept mers", "flame", 150, None, "", ""),
        ("badge", "Captain", "Badge Capitaine", "anchor", "shimmer", 200, None, "", ""),
        ("frame", "shipwheel", "Ship's wheel", "Barre de navire", 650, 4,
         "Your avatar at the helm, the wheel turning slowly.", "Votre avatar à la barre, la roue qui tourne lentement."),
        ("level", "doubloon", "Doubloon", "Doublon", 700, 4,
         "Your level struck on a notched gold doubloon.", "Votre niveau frappé sur un doublon d'or cranté."),
        ("notif", "bottle", "Message in a bottle", "Bouteille à la mer", 650, 4,
         "Notifications arriving as messages in bottles.", "Des notifications qui arrivent en bouteilles à la mer."),
        ("anim", "anchor", "Anchor drop", "Ancre jetée", 650, 4,
         "Notifications dropping like an anchor and swaying.", "Des notifications qui tombent comme une ancre et se balancent."),
        ("levelup", "plunder", "Plunder", "Butin", 1100, 8,
         "A treasure chest bursts open, doubloons flying: YO HO HO!",
         "Un coffre au trésor qui s'ouvre, des doublons qui volent : YO HO HO !"),
    ),
    "mecha": (
        ("ambient", "gears", "Gears", "Engrenages", 300, None,
         "Steel gears turning one way and the other.", "Des engrenages d'acier qui tournent dans un sens et dans l'autre."),
        ("live", "gears", "Gears", "engrenages", 350, None, "", ""),
        ("banner", "assemblyline", "Assembly line", "Chaîne de montage", 300, None,
         "Robot arms over an assembly line, warning lights blinking.", "Des bras robotisés au-dessus d'une chaîne de montage, des voyants qui clignotent."),
        ("effect", "bolts", "Nuts and bolts", "Écrous et boulons", 250, None,
         "Nuts and bolts spinning out of the reward.", "Des écrous et des boulons qui jaillissent en tournant de la récompense."),
        ("palette", "gunmetal", "Gunmetal", "Acier canon", 200, None,
         "Steel grey and warning red over the theme.", "Gris acier et rouge d'alerte sur le thème."),
        ("name", "steelplate", "Steel plate", "plaque d'acier", 300, None,
         "A name stamped in chrome stencil.", "Un nom frappé au pochoir chromé."),
        ("title", "More than meets the eye", "Titre : Plus qu'il n'y paraît", "glitch", 150, None, "", ""),
        ("badge", "Mech pilot", "Badge Pilote de méca", "bot", "neon", 200, None, "", ""),
        ("frame", "visor", "Visor", "Visière", 650, 4,
         "Your avatar behind a bolted hexagonal visor.", "Votre avatar derrière une visière hexagonale boulonnée."),
        ("level", "chevron", "Chevron", "Chevron", 700, 4,
         "Your level on a steel chevron.", "Votre niveau sur un chevron d'acier."),
        ("notif", "chamfer", "Steel panel", "Panneau d'acier", 650, 4,
         "Notifications on steel panels with cut corners.", "Des notifications sur des panneaux d'acier aux coins coupés."),
        ("anim", "transform", "Transform", "Transformation", 650, 4,
         "Notifications unfolding panel by panel.", "Des notifications qui se déplient panneau par panneau."),
        ("levelup", "rollout", "Roll out", "En route", 1100, 8,
         "Steel plates fly in from every side and lock into place around your new level.",
         "Des plaques d'acier arrivent de partout et se verrouillent autour de votre nouveau niveau."),
    ),
    "classicdesk": (
        ("ambient", "skyclouds", "Clouds in the sky", "Nuages dans le ciel", 300, None,
         "Fluffy white clouds drifting across a blue sky.", "Des nuages blancs et cotonneux qui traversent un ciel bleu."),
        ("live", "skyclouds", "Clouds in the sky", "nuages dans le ciel", 350, None, "", ""),
        ("banner", "greenhill", "Green hill", "Colline verdoyante", 300, None,
         "A green hill rolling under a deep blue sky and its clouds.", "Une colline verte qui ondule sous un ciel bleu profond et ses nuages."),
        ("effect", "cardcascade", "Card cascade", "Cascade de cartes", 250, None,
         "Playing cards bouncing down the screen like a won game of patience.", "Des cartes à jouer qui rebondissent sur l'écran comme une réussite gagnée."),
        ("palette", "luna", "Desktop blue", "Bleu bureau", 200, None,
         "Title-bar blue and Start-button green over the theme.", "Le bleu des barres de titre et le vert du bouton Démarrer sur le thème."),
        ("name", "titlebar", "Title bar", "barre de titre", 300, None,
         "A name in bold italic white, outlined in blue like a window's title.", "Un nom en blanc gras italique, cerné de bleu comme le titre d'une fenêtre."),
        ("title", "Safe to turn off", "Titre : Vous pouvez éteindre", "shimmer", 150, None, "", ""),
        ("badge", "Defragmented", "Badge Défragmenté", "hard-drive", "pixel", 200, None, "", ""),
        ("frame", "window", "Window", "Fenêtre", 650, 4,
         "Your avatar in a little window, its blue title bar and red close button.", "Votre avatar dans une petite fenêtre, sa barre de titre bleue et son bouton fermer rouge."),
        ("level", "startbutton", "Start button", "Bouton démarrer", 700, 4,
         "Your level on a green rounded button, in white italics.", "Votre niveau sur un bouton vert arrondi, en italique blanc."),
        ("notif", "balloon", "Balloon tip", "Info-bulle", 650, 4,
         "Notifications in pale yellow balloon tips, their tail pointing down to the tray.", "Des notifications en info-bulles jaune pâle, leur pointe tournée vers la zone de notification."),
        ("anim", "trayrise", "Tray balloon", "Bulle de la zone de notification", 650, 4,
         "Notifications rising out of the corner of the screen and bobbing.", "Des notifications qui montent du coin de l'écran et se balancent."),
        ("levelup", "setupwizard", "Setup wizard", "Assistant d'installation", 1100, 8,
         "A setup wizard installs your new level: its progress bar fills block by block, then Finish.",
         "Un assistant d'installation installe votre nouveau niveau : sa barre de progression se remplit bloc par bloc, puis Terminer."),
    ),
    "cupertino": (
        ("ambient", "silkwaves", "Silk waves", "Vagues de soie", 300, None,
         "Soft coloured waves of light gliding slowly behind the page.", "De douces vagues de lumière colorée qui glissent lentement derrière la page."),
        ("live", "silkwaves", "Silk waves", "vagues de soie", 350, None, "", ""),
        ("banner", "coastline", "Coast at dusk", "Côte au crépuscule", 300, None,
         "Cliffs over the ocean at dusk, the sky turning pink and violet.", "Des falaises au-dessus de l'océan au crépuscule, le ciel qui vire au rose et au violet."),
        ("effect", "balloons", "Balloons", "Ballons", 250, None,
         "Glossy balloons floating up across the whole screen.", "Des ballons brillants qui s'envolent sur tout l'écran."),
        ("palette", "graphite", "Graphite", "Graphite", 200, None,
         "Graphite grey and a touch of blue over the theme.", "Gris graphite et une touche de bleu sur le thème."),
        ("name", "aluminium", "Aluminium", "aluminium", 300, None,
         "A name in brushed aluminium, a light sweeping across it.", "Un nom en aluminium brossé, une lumière qui le parcourt."),
        ("title", "Pixel perfect", "Titre : Au pixel près", "glass", 150, None, "", ""),
        ("badge", "Unboxer", "Badge Pro du déballage", "package", "glass", 200, None, "", ""),
        ("frame", "appicon", "App icon", "Icône d'app", 650, 4,
         "Your avatar as an app icon, its rounded square and its red bubble.", "Votre avatar en icône d'app, son carré arrondi et sa pastille rouge."),
        ("level", "aquagel", "Gel button", "Bouton gel", 700, 4,
         "Your level in a glossy blue gel drop.", "Votre niveau dans une goutte de gel bleu brillant."),
        ("notif", "trafficlights", "Traffic lights", "Feux tricolores", 650, 4,
         "Notifications in frosted windows with their three coloured buttons.", "Des notifications dans des fenêtres dépolies avec leurs trois boutons de couleur."),
        ("anim", "genie", "Genie", "Génie", 650, 4,
         "Notifications pouring out of the corner like a genie from its lamp.", "Des notifications qui sortent du coin comme un génie de sa lampe."),
        ("levelup", "unboxing", "Unboxing", "Déballage", 1100, 8,
         "A white box slides open and your new level rises out of it.",
         "Une boîte blanche s'ouvre en glissant et votre nouveau niveau en sort."),
    ),
    "social": (
        ("ambient", "reactions", "Live reactions", "Réactions en direct", 300, None,
         "Hearts and thumbs up floating up like reactions on a live video.", "Des cœurs et des pouces qui s'envolent comme les réactions d'une vidéo en direct."),
        ("live", "reactions", "Live reactions", "réactions en direct", 350, None, "", ""),
        ("banner", "friendswall", "Wall of friends", "Mur d'amis", 300, None,
         "Snapshots pinned edge to edge, like a cover photo of friends.", "Des photos épinglées bord à bord, comme une photo de couverture entre amis."),
        ("effect", "likes", "Thumbs-up shower", "Pluie de pouces", 250, None,
         "Thumbs up and hearts popping out of the reward.", "Des pouces levés et des cœurs qui jaillissent de la récompense."),
        ("palette", "chatgradient", "Chat gradient", "Dégradé discussion", 200, None,
         "The blue-to-pink gradient of a chat over the theme.", "Le dégradé bleu-rose d'une discussion sur le thème."),
        ("name", "verified", "Verified", "certifié", 300, None,
         "Your name in bold with a blue verified tick after it.", "Votre nom en gras suivi d'une coche bleue de compte certifié."),
        ("title", "Influencer", "Titre : Influenceur", "pulse", 150, None, "", ""),
        ("badge", "Top fan", "Badge Fan numéro un", "thumbs-up", "shimmer", 200, None, "", ""),
        ("frame", "storyring", "Story ring", "Anneau de story", 650, 4,
         "Your avatar inside a gradient ring broken into stories.", "Votre avatar dans un anneau dégradé découpé en stories."),
        ("level", "speechbubble", "Speech bubble", "Bulle de discussion", 700, 4,
         "Your level in a blue speech bubble with its little tail.", "Votre niveau dans une bulle de discussion bleue avec sa petite pointe."),
        ("notif", "chathead", "Chat head", "Bulle de discussion", 650, 4,
         "Notifications as chat bubbles hanging from a round head.", "Des notifications en bulles de discussion accrochées à une tête ronde."),
        ("anim", "chatpop", "Typing message", "Message qui s'écrit", 650, 4,
         "Three typing dots, then the notification pops open.", "Trois petits points qui s'écrivent, puis la notification s'ouvre d'un coup."),
        ("levelup", "viral", "Gone viral", "Publication virale", 1100, 8,
         "Your new level posted: likes and hearts pour in, the counter goes wild.",
         "Votre nouveau niveau publié : les j'aime et les cœurs affluent, le compteur s'affole."),
    ),
    "groove": (
        ("ambient", "equalizer", "Equalizer", "Égaliseur", 300, None,
         "Equalizer bars pulsing along the bottom of the page.", "Des barres d'égaliseur qui pulsent en bas de la page."),
        ("live", "equalizer", "Equalizer", "égaliseur", 350, None, "", ""),
        ("banner", "soundwave", "Sound wave", "Onde sonore", 300, None,
         "A green sound wave across a night-black banner.", "Une onde sonore verte en travers d'une bannière noire."),
        ("effect", "musicnotes", "Music notes", "Notes de musique", 250, None,
         "Music notes flying out of the reward.", "Des notes de musique qui s'envolent de la récompense."),
        ("palette", "groove", "Groove green", "Vert groove", 200, None,
         "A bright green and a pink over the theme.", "Un vert vif et un rose sur le thème."),
        ("name", "recap", "Year recap", "bilan de l'année", 300, None,
         "A name in big bold letters, a gradient of pink, orange and green running through.", "Un nom en grosses lettres grasses, parcouru d'un dégradé rose, orange et vert."),
        ("title", "On repeat", "Titre : En boucle", "pulse", 150, None, "", ""),
        ("badge", "Crate digger", "Badge Fouilleur de bacs", "music", "pulse", 200, None, "", ""),
        ("frame", "vinyl", "Vinyl", "Vinyle", 650, 4,
         "Your avatar as the label of a spinning record, its grooves shining.", "Votre avatar en étiquette d'un disque qui tourne, ses sillons qui brillent."),
        ("level", "eqbars", "Equalizer", "Égaliseur", 700, 4,
         "Your level on a green pill with three little bars dancing.", "Votre niveau sur une pastille verte où dansent trois petites barres."),
        ("notif", "nowplaying", "Now playing", "En cours de lecture", 650, 4,
         "Notifications like the track playing: a cover, its title, a green progress bar.", "Des notifications comme le titre en cours : une pochette, son nom, une barre de progression verte."),
        ("anim", "beatdrop", "Beat drop", "Drop de basse", 650, 4,
         "Notifications dropping in on the beat, thumping twice.", "Des notifications qui tombent sur le temps et cognent deux fois."),
        ("levelup", "encore", "Encore", "Rappel", 1100, 8,
         "The stage lights sweep, a record spins and the equalizer goes wild: your new level, once more.",
         "Les projecteurs balaient la scène, un disque tourne et l'égaliseur s'emballe : votre nouveau niveau, une fois de plus."),
    ),
    "binge": (
        ("ambient", "cinemaglow", "Cinema glow", "Lueurs de cinéma", 300, None,
         "Soft red glows sweeping slowly, like the light of a screen in the dark.", "De douces lueurs rouges qui balaient lentement, comme la lumière d'un écran dans le noir."),
        ("live", "cinemaglow", "Cinema glow", "lueurs de cinéma", 350, None, "", ""),
        ("banner", "postergrid", "Poster wall", "Mur d'affiches", 300, None,
         "Rows of posters fading into black, a red glow behind.", "Des rangées d'affiches qui se fondent dans le noir, une lueur rouge derrière."),
        ("effect", "ribbons", "Red ribbons", "Rubans rouges", 250, None,
         "Red ribbons of light streaking across the screen.", "Des rubans de lumière rouge qui traversent l'écran."),
        ("palette", "redcarpet", "Red carpet", "Tapis rouge", 200, None,
         "Screen red and a touch of gold over the theme.", "Le rouge de l'écran et une touche d'or sur le thème."),
        ("name", "marathon", "Marathon", "marathon", 300, None,
         "A name in tall condensed red capitals, like a show's title.", "Un nom en hautes capitales rouges condensées, comme le titre d'une série."),
        ("title", "Just one more episode", "Titre : Encore un épisode", "flame", 150, None, "", ""),
        ("badge", "Season finisher", "Badge Saison bouclée", "clapperboard", "flame", 200, None, "", ""),
        ("frame", "profiletile", "Viewing profile", "Profil de visionnage", 650, 4,
         "Your avatar as a viewing profile's rounded square, a red edge around it.", "Votre avatar en carré arrondi de profil de visionnage, bordé de rouge."),
        ("level", "toprank", "Top 10", "Top 10", 700, 4,
         "Your level as a huge outlined number, like a top-ten row.", "Votre niveau en énorme chiffre détouré, comme dans un classement."),
        ("notif", "nextepisode", "Next episode", "Épisode suivant", 650, 4,
         "Notifications like « next episode »: black, a red countdown filling.", "Des notifications comme « épisode suivant » : noires, un compte à rebours rouge qui se remplit."),
        ("anim", "curtainwipe", "Curtain rise", "Lever de rideau", 650, 4,
         "Notifications opening from the middle like a curtain.", "Des notifications qui s'ouvrent depuis le milieu comme un rideau."),
        ("levelup", "finale", "Season finale", "Final de saison", 1100, 8,
         "Red ribbons sweep the screen, then your new level appears like a new season's title.",
         "Des rubans rouges balaient l'écran, puis votre nouveau niveau apparaît comme le titre d'une nouvelle saison."),
    ),
    "gazette": (
        ("ambient", "pages", "Flying pages", "Pages qui s'envolent", 300, None,
         "Newspaper pages fluttering across, carried by the wind.", "Des pages de journal qui volettent, portées par le vent."),
        ("live", "pages", "Flying pages", "pages qui s'envolent", 350, None, "", ""),
        ("banner", "frontpage", "Front page", "Une du journal", 300, None,
         "A newspaper's front page: its title, its rules and its columns.", "La une d'un journal : son titre, ses filets et ses colonnes."),
        ("effect", "inkstamp", "Ink stamps", "Coups de tampon", 250, None,
         "Red ink stamps thumping onto the screen: EXTRA!", "Des coups de tampon à l'encre rouge sur l'écran : EXTRA !"),
        ("palette", "newsprint", "Ink and paper", "Encre et papier", 200, None,
         "Ink black and editorial red over the theme.", "Le noir de l'encre et le rouge de la rédaction sur le thème."),
        ("name", "typewriter", "Typewriter", "machine à écrire", 300, None,
         "A name typed on an old typewriter, the ink a little uneven.", "Un nom tapé à la machine à écrire, l'encre un peu inégale."),
        ("title", "Front page", "Titre : À la une", "shimmer", 150, None, "", ""),
        ("badge", "Scoop", "Badge Scoop", "newspaper", "pixel", 200, None, "", ""),
        ("frame", "postage", "Postage stamp", "Timbre-poste", 650, 4,
         "Your avatar on a postage stamp, its perforated edges and its postmark.", "Votre avatar sur un timbre-poste, ses bords dentelés et son cachet."),
        ("level", "presscard", "Press pass", "Carte de presse", 700, 4,
         "Your level on a press pass tucked in a hatband.", "Votre niveau sur une carte de presse glissée dans un ruban de chapeau."),
        ("notif", "telegram", "Telegram", "Télégramme", 650, 4,
         "Notifications as telegrams: a strip of paper glued on a form, STOP.", "Des notifications en télégrammes : une bande de papier collée sur un formulaire, STOP."),
        ("anim", "spinpaper", "Spinning paper", "Journal qui tourne", 650, 4,
         "Notifications spinning in like a headline in an old film.", "Des notifications qui arrivent en tournant comme une une dans un vieux film."),
        ("levelup", "extraedition", "Extra edition", "Édition spéciale", 1100, 8,
         "A newspaper spins up to the screen: EXTRA! EXTRA! your new level on the front page.",
         "Un journal arrive en tournant : EXTRA ! EXTRA ! votre nouveau niveau à la une."),
    ),
    "pocket": (
        ("ambient", "lcdstars", "8-bit stars", "Étoiles 8 bits", 300, None,
         "Little pixel stars twinkling in four shades of green.", "De petites étoiles en pixels qui scintillent en quatre nuances de vert."),
        ("live", "lcdstars", "8-bit stars", "étoiles 8 bits", 350, None, "", ""),
        ("banner", "lcdscreen", "Pocket screen", "Écran de poche", 300, None,
         "A green screen with pixel hills, a cloud and the sun.", "Un écran vert avec des collines en pixels, un nuage et le soleil."),
        ("effect", "pixelhearts", "8-bit hearts", "Cœurs 8 bits", 250, None,
         "Pixel hearts bursting out of the reward.", "Des cœurs en pixels qui jaillissent de la récompense."),
        ("palette", "dotmatrix", "Green screen", "Écran vert", 200, None,
         "The four greens of a pocket screen over the theme.", "Les quatre verts d'un écran de poche sur le thème."),
        ("name", "lcdtext", "LCD screen", "écran LCD", 300, None,
         "A name in pixel letters, dark green with the screen's faint ghost.", "Un nom en lettres de pixels, vert sombre avec la légère rémanence de l'écran."),
        ("title", "Insert cartridge", "Titre : Insérez la cartouche", "pixel", 150, None, "", ""),
        ("badge", "Link cable", "Badge Câble de liaison", "gamepad", "pixel", 200, None, "", ""),
        ("frame", "cartridge", "Cartridge", "Cartouche", 650, 4,
         "Your avatar on a grey cartridge's label, its corner cut.", "Votre avatar sur l'étiquette d'une cartouche grise, son coin coupé."),
        ("level", "batteryled", "Battery light", "Voyant de pile", 700, 4,
         "Your level beside a little red light glowing like the battery's.", "Votre niveau à côté d'un petit voyant rouge qui brille comme celui de la pile."),
        ("notif", "rpgbox", "Dialogue box", "Boîte de dialogue", 650, 4,
         "Notifications in a role-playing game's text box, its arrow blinking.", "Des notifications dans la boîte de texte d'un jeu de rôle, sa flèche qui clignote."),
        ("anim", "pixelreveal", "Text appearing", "Texte qui s'affiche", 650, 4,
         "Notifications appearing line by line, like a game's text.", "Des notifications qui s'affichent ligne par ligne, comme le texte d'un jeu."),
        ("levelup", "statsup", "Stats up", "Statistiques en hausse", 1100, 8,
         "A text box announces it: your new level, every stat going up in pixels.",
         "Une boîte de texte l'annonce : votre nouveau niveau, toutes les statistiques qui montent en pixels."),
    ),
    "blockfall": (
        ("ambient", "fallingblocks", "Falling blocks", "Blocs qui tombent", 300, None,
         "Bright pieces falling and turning behind the page.", "Des pièces vives qui tombent en tournant derrière la page."),
        ("live", "fallingblocks", "Falling blocks", "blocs qui tombent", 350, None, "", ""),
        ("banner", "linestack", "Stack of blocks", "Pile de blocs", 300, None,
         "A stack of bevelled blocks, one line about to clear.", "Une pile de blocs biseautés, une ligne sur le point de s'effacer."),
        ("effect", "lineclear", "Lines cleared", "Lignes effacées", 250, None,
         "Lines of blocks flashing across the screen and clearing.", "Des lignes de blocs qui clignotent sur l'écran et s'effacent."),
        ("palette", "blockcolors", "Block colours", "Couleurs des blocs", 200, None,
         "Cyan and yellow pieces over the theme.", "Des pièces cyan et jaunes sur le thème."),
        ("name", "bevelblocks", "Bevelled blocks", "blocs biseautés", 300, None,
         "A name in chunky pixel capitals, banded like a stack of pieces.", "Un nom en grosses capitales de pixels, rayé comme une pile de pièces."),
        ("title", "Line clearer", "Titre : Effaceur de lignes", "rainbow", 150, None, "", ""),
        ("badge", "Perfect clear", "Badge Plateau vide", "blocks", "rainbow", 200, None, "", ""),
        ("frame", "blockframe", "Frame of blocks", "Cadre de blocs", 650, 4,
         "Your avatar walled in bevelled blocks of every colour.", "Votre avatar entouré de blocs biseautés de toutes les couleurs."),
        ("level", "tpiece", "T piece", "Pièce en T", 700, 4,
         "Your level on a purple T-shaped piece.", "Votre niveau sur une pièce violette en forme de T."),
        ("notif", "blockrow", "Row of blocks", "Ligne de blocs", 650, 4,
         "Notifications framed in a row of bevelled blocks.", "Des notifications encadrées d'une ligne de blocs biseautés."),
        ("anim", "harddrop", "Hard drop", "Chute brutale", 650, 4,
         "Notifications dropping straight down and landing with a jolt.", "Des notifications qui tombent tout droit et se posent d'un coup sec."),
        ("levelup", "fourlines", "Four lines", "Quatre lignes", 1100, 8,
         "Four lines flash and clear at once: 4 LINES! and your new level drops in.",
         "Quatre lignes clignotent et s'effacent d'un coup : 4 LIGNES ! et votre nouveau niveau tombe à sa place."),
    ),
    "invaders": (
        ("ambient", "fleet", "Invader fleet", "Flotte d'envahisseurs", 300, None,
         "Rows of pixel invaders marching side to side, stepping down.", "Des rangées d'envahisseurs en pixels qui avancent de côté et descendent d'un cran."),
        ("live", "fleet", "Invader fleet", "flotte d'envahisseurs", 350, None, "", ""),
        ("banner", "bunkers", "Bunkers", "Bunkers", 300, None,
         "Green bunkers on the ground line, a fleet overhead.", "Des bunkers verts sur la ligne de sol, une flotte au-dessus."),
        ("effect", "lasers", "Laser shots", "Tirs laser", 250, None,
         "Laser bolts shooting out of the reward.", "Des tirs laser qui jaillissent de la récompense."),
        ("palette", "arcadegreen", "Arcade green", "Vert arcade", 200, None,
         "Phosphor green and a red alert over the theme.", "Vert phosphore et rouge d'alerte sur le thème."),
        ("name", "hiscore", "High score", "meilleur score", 300, None,
         "A name in white pixel letters glowing on the high-score table.", "Un nom en lettres de pixels blanches qui brillent dans le tableau des scores."),
        ("title", "Last defender", "Titre : Dernier défenseur", "neon", 150, None, "", ""),
        ("badge", "Sharpshooter", "Badge Tireur d'élite", "crosshair", "neon", 200, None, "", ""),
        ("frame", "crab", "Invader", "Envahisseur", 650, 4,
         "Your avatar in a stepped pixel frame, an invader perched on top.", "Votre avatar dans un cadre en pixels, un envahisseur perché dessus."),
        ("level", "saucer", "Saucer", "Soucoupe", 700, 4,
         "Your level on a mystery saucer, its lights blinking.", "Votre niveau sur une soucoupe mystère, ses feux qui clignotent."),
        ("notif", "invasion", "Invasion", "Invasion", 650, 4,
         "Notifications under a pixel invader, framed like a phosphor screen.", "Des notifications sous un envahisseur en pixels, encadrées comme un écran au phosphore."),
        ("anim", "march", "Invaders' march", "Marche des envahisseurs", 650, 4,
         "Notifications stepping in side to side, like the fleet.", "Des notifications qui arrivent pas à pas de côté, comme la flotte."),
        ("levelup", "wavecleared", "Wave cleared", "Vague repoussée", 1100, 8,
         "The fleet bursts into pixels: WAVE CLEARED, and your new level.",
         "La flotte éclate en pixels : VAGUE REPOUSSÉE, et votre nouveau niveau."),
    ),
    "mazechase": (
        ("ambient", "ghosts", "Ghosts", "Fantômes", 300, None,
         "Little ghosts drifting through the page, their eyes darting.", "De petits fantômes qui flottent à travers la page, les yeux qui roulent."),
        ("live", "ghosts", "Ghosts", "fantômes", 350, None, "", ""),
        ("banner", "mazewalls", "Maze", "Labyrinthe", 300, None,
         "Blue maze corridors lined with pellets, a power pellet glowing.", "Des couloirs de labyrinthe bleus bordés de gommes, une super gomme qui brille."),
        ("effect", "pellets", "Pellets", "Gommes", 250, None,
         "Pellets popping out of the reward, a big one blinking.", "Des gommes qui jaillissent de la récompense, une grosse qui clignote."),
        ("palette", "mazeblue", "Maze blue", "Bleu labyrinthe", 200, None,
         "Maze blue and eater yellow over the theme.", "Le bleu du labyrinthe et le jaune du glouton sur le thème."),
        ("name", "neonmaze", "Maze neon", "néon du labyrinthe", 300, None,
         "A name in yellow pixel letters outlined in maze blue.", "Un nom en lettres de pixels jaunes cernées du bleu du labyrinthe."),
        ("title", "Power pellet", "Titre : Super gomme", "neon", 150, None, "", ""),
        ("badge", "Ghost hunter", "Badge Chasseur de fantômes", "ghost", "neon", 200, None, "", ""),
        ("frame", "corridor", "Maze corridor", "Couloir du labyrinthe", 650, 4,
         "Your avatar inside a corridor of the maze, its double blue walls.", "Votre avatar dans un couloir du labyrinthe, ses doubles murs bleus."),
        ("level", "chomper", "Chomper", "Glouton", 700, 4,
         "Your level beside a yellow eater opening and closing its mouth.", "Votre niveau à côté d'un glouton jaune qui ouvre et ferme la bouche."),
        ("notif", "ghostly", "Ghost", "Fantôme", 650, 4,
         "Notifications shaped like a ghost, their wavy hem and their two eyes.", "Des notifications en forme de fantôme, leur bas ondulé et leurs deux yeux."),
        ("anim", "chomp", "Chomped", "Croqué", 650, 4,
         "Notifications opening like a mouth chomping its way in.", "Des notifications qui s'ouvrent comme une bouche qui croque."),
        ("levelup", "powerup", "Power pellet", "Super gomme", 1100, 8,
         "READY! The ghosts turn blue and flee, and your new level gobbles the screen.",
         "READY ! Les fantômes virent au bleu et s'enfuient, et votre nouveau niveau dévore l'écran."),
    ),
    "platformer": (
        ("ambient", "spincoins", "Spinning coins", "Pièces qui tournent", 300, None,
         "Gold coins spinning in the air across the page.", "Des pièces d'or qui tournent dans les airs sur la page."),
        ("live", "spincoins", "Spinning coins", "pièces qui tournent", 350, None, "", ""),
        ("banner", "brickworld", "Brick world", "Monde de briques", 300, None,
         "A blue sky, bricks, a mystery block, a green pipe and hills.", "Un ciel bleu, des briques, un bloc mystère, un tuyau vert et des collines."),
        ("effect", "coinpop", "Coins popping", "Pièces qui sautent", 250, None,
         "Coins jumping out of the reward and spinning.", "Des pièces qui sautent de la récompense en tournant."),
        ("palette", "brickred", "Brick red", "Rouge brique", 200, None,
         "Brick red and pipe green over the theme.", "Le rouge des briques et le vert des tuyaux sur le thème."),
        ("name", "gametitle", "Game title", "titre de jeu", 300, None,
         "A name in chunky white pixel letters with a hard black shadow, like a game's title.", "Un nom en grosses lettres de pixels blanches à l'ombre noire, comme le titre d'un jeu."),
        ("title", "Extra life", "Titre : Vie supplémentaire", "pixel", 150, None, "", ""),
        ("badge", "Speedrunner", "Badge Speedrunner", "zap", "flame", 200, None, "", ""),
        ("frame", "warppipe", "Warp pipe", "Tuyau", 650, 4,
         "Your avatar popping out of a green warp pipe.", "Votre avatar qui sort d'un tuyau vert."),
        ("level", "qblock", "Mystery block", "Bloc mystère", 700, 4,
         "Your level on a golden mystery block with its rivets.", "Votre niveau sur un bloc mystère doré et ses rivets."),
        ("notif", "bricks", "Bricks", "Briques", 650, 4,
         "Notifications framed in bricks, like a level's wall.", "Des notifications encadrées de briques, comme le mur d'un niveau."),
        ("anim", "jumpin", "Jump", "Saut", 650, 4,
         "Notifications jumping in from below, squashing as they land.", "Des notifications qui arrivent d'un saut, et s'écrasent un peu en atterrissant."),
        ("levelup", "flagpole", "Course clear", "Fin de niveau", 1100, 8,
         "The flag slides down the pole, fireworks over the castle: COURSE CLEAR!",
         "Le drapeau glisse le long du mât, un feu d'artifice au-dessus du château : COURSE CLEAR !"),
    ),
    "funky": (
        ("ambient", "groovywaves", "Groovy waves", "Vagues groovy", 300, None,
         "Wide orange, mustard and brown stripes waving slowly behind the page.", "De larges rayures orange, moutarde et marron qui ondulent lentement derrière la page."),
        ("live", "groovywaves", "Groovy waves", "vagues groovy", 350, None, "", ""),
        ("banner", "sunset70s", "Seventies sunset", "Coucher de soleil 70", 300, None,
         "A striped seventies sun setting over brown hills.", "Un soleil rayé des années 70 qui se couche sur des collines brunes."),
        ("effect", "flowerpower", "Flower power", "Flower power", 250, None,
         "Seventies daisies spinning out of the reward.", "Des marguerites des années 70 qui jaillissent en tournant de la récompense."),
        ("palette", "seventies", "Seventies", "Années 70", 200, None,
         "Orange and mustard over the theme.", "De l'orange et de la moutarde sur le thème."),
        ("name", "funkadelic", "Funkadelic", "funkadélique", 300, None,
         "A name in round seventies letters with stacked orange, mustard and brown shadows.", "Un nom en lettres rondes des années 70 aux ombres empilées orange, moutarde et marron."),
        ("title", "Get funky", "Titre : Funky", "rainbow", 150, None, "", ""),
        ("badge", "Bell bottoms", "Badge Pattes d'eph", "music", "rainbow", 200, None, "", ""),
        ("frame", "retroarc", "Seventies rainbow", "Arc-en-ciel 70", 650, 4,
         "Your avatar under a three-striped seventies rainbow.", "Votre avatar sous un arc-en-ciel des années 70 à trois bandes."),
        ("level", "eighttrack", "8-track cartridge", "Cartouche 8 pistes", 700, 4,
         "Your level on an 8-track cartridge's label.", "Votre niveau sur l'étiquette d'une cartouche 8 pistes."),
        ("notif", "jukebox", "Jukebox", "Juke-box", 650, 4,
         "Notifications under a jukebox's glowing chrome arch.", "Des notifications sous l'arche chromée et lumineuse d'un juke-box."),
        ("anim", "funkwalk", "Funky walk", "Démarche funky", 650, 4,
         "Notifications strutting in, swaying their hips.", "Des notifications qui arrivent en se déhanchant."),
        ("levelup", "jukeboxdrop", "Jukebox", "Juke-box", 1100, 8,
         "A record drops on the jukebox, the bubbles rise in its tubes: FUNKY!",
         "Un disque tombe sur le juke-box, les bulles montent dans ses tubes : FUNKY !"),
    ),
    "beach": (
        ("ambient", "beachballs", "Beach balls", "Ballons de plage", 300, None,
         "Striped beach balls bouncing across the page.", "Des ballons de plage rayés qui rebondissent sur la page."),
        ("live", "beachballs", "Beach balls", "ballons de plage", 350, None, "", ""),
        ("banner", "lifeguard", "Lifeguard tower", "Poste de secours", 300, None,
         "A lifeguard tower on the sand, its flag flying, the lagoon behind.", "Un poste de secours sur le sable, son drapeau au vent, le lagon derrière."),
        ("effect", "seashells", "Seashells", "Coquillages", 250, None,
         "Seashells and starfish scattering out of the reward.", "Des coquillages et des étoiles de mer qui s'éparpillent de la récompense."),
        ("palette", "sandbar", "Sandbar", "Banc de sable", 200, None,
         "Lagoon blue and coral over the theme.", "Le bleu du lagon et le corail sur le thème."),
        ("name", "surfwave", "Surf wave", "vague de surf", 300, None,
         "A name in lagoon blues, a little wave rolling under it.", "Un nom dans les bleus du lagon, une petite vague qui roule dessous."),
        ("title", "Beach bum", "Titre : Lézard de plage", "float", 150, None, "", ""),
        ("badge", "Lifeguard", "Badge Maître-nageur", "umbrella", "float", 200, None, "", ""),
        ("frame", "parasol", "Parasol", "Parasol", 650, 4,
         "Your avatar in the shade of a striped parasol.", "Votre avatar à l'ombre d'un parasol rayé."),
        ("level", "flipflop", "Flip-flop", "Tong", 700, 4,
         "Your level on a flip-flop and its strap.", "Votre niveau sur une tong et sa bride."),
        ("notif", "beachtowel", "Beach towel", "Serviette de plage", 650, 4,
         "Notifications laid out on a striped beach towel, fringes and all.", "Des notifications étendues sur une serviette de plage rayée, franges comprises."),
        ("anim", "surfin", "Riding the wave", "Sur la vague", 650, 4,
         "Notifications riding in on a wave.", "Des notifications qui arrivent sur une vague."),
        ("levelup", "sandcastle", "Sandcastle", "Château de sable", 1100, 8,
         "A sandcastle rises tower by tower, a flag with your new level on top.",
         "Un château de sable s'élève tour par tour, un drapeau à votre nouveau niveau au sommet."),
    ),
    "blossom": (
        ("ambient", "dandelion", "Dandelion seeds", "Aigrettes de pissenlit", 300, None,
         "Dandelion seeds floating up on the breeze.", "Des aigrettes de pissenlit qui s'envolent au gré de la brise."),
        ("live", "dandelion", "Dandelion seeds", "aigrettes de pissenlit", 350, None, "", ""),
        ("banner", "tulipfield", "Tulip field", "Champ de tulipes", 300, None,
         "Rows of tulips, red, yellow and pink, under a spring sky.", "Des rangées de tulipes, rouges, jaunes et roses, sous un ciel de printemps."),
        ("effect", "songbirds", "Songbirds", "Oiseaux chanteurs", 250, None,
         "Little birds flying up across the screen.", "De petits oiseaux qui s'envolent sur l'écran."),
        ("palette", "lilac", "Lilac", "Lilas", 200, None,
         "Lilac and leaf green over the theme.", "Du lilas et du vert tendre sur le thème."),
        ("name", "watercolour", "Watercolour", "aquarelle", 300, None,
         "A name painted in soft watercolour, pink running into green.", "Un nom peint à l'aquarelle, le rose qui coule dans le vert."),
        ("title", "Green thumb", "Titre : Main verte", "float", 150, None, "", ""),
        ("badge", "Gardener", "Badge Jardinier", "sprout", "float", 200, None, "", ""),
        ("frame", "flowerwreath", "Flower wreath", "Couronne de fleurs", 650, 4,
         "Your avatar crowned with a wreath of spring flowers.", "Votre avatar couronné de fleurs de printemps."),
        ("level", "ladybug", "Ladybird", "Coccinelle", 700, 4,
         "Your level on a ladybird's red, spotted shell.", "Votre niveau sur la carapace rouge et tachetée d'une coccinelle."),
        ("notif", "seedpacket", "Seed packet", "Sachet de graines", 650, 4,
         "Notifications like a seed packet, its torn top edge and its flowers.", "Des notifications comme un sachet de graines, son haut déchiré et ses fleurs."),
        ("anim", "sprout", "Sprout", "Pousse", 650, 4,
         "Notifications growing up from the ground like a shoot.", "Des notifications qui poussent depuis le sol comme une jeune pousse."),
        ("levelup", "fullbloom", "Full bloom", "Pleine floraison", 1100, 8,
         "A tree bursts into blossom, its petals swirling around your new level.",
         "Un arbre se couvre de fleurs, ses pétales tourbillonnent autour de votre nouveau niveau."),
    ),
}  # fmt: skip
# --------------------------------------------------------------------------------- the cosmos (#130)
# Nebulae (Orion, the Crab, the Helix, the Pillars of Creation, Carina's cliffs), planets, comets, shooting
# stars and constellations: ambiences and animated banners, frames, level badges, notifications, a
# celebration and level-ups drawn by the graphics chip; name styles in faces of their own (no aura), palettes,
# banners, titles and badges — the twelve constellations of the zodiac among them. Their packs, their
# booster, two interfaces (an observatory, a space station) and a few given by achievements and levels.
COSMOS_HD: list[str] = []
COSMOS_KEYS: list[str] = []


COSMOS_LEGENDARY = {
    "ambient_orion", "ambient_pillars", "frame_ringedworld", "levelup_hyperjump", "level_totality", "effect_bigbang",
    "frame_polaris", "badge_supernova", "title_night_watcher", "title_star_sailor",
}  # fmt: skip


def _cosmos(key: str, kind: str, price: int | None, rarity: str, en: str, fr: str, about_en: str, about_fr: str,
            payload: dict[str, Any], *, collection: str, icon: str, hd: bool = True, reward: bool = False) -> None:  # fmt: skip
    _p(key, kind, None if reward else price, "legendary" if key in COSMOS_LEGENDARY else rarity, en, fr, about_en,
       about_fr, payload, collection=collection, icon=icon, reward_only=reward)  # fmt: skip
    COSMOS_KEYS.append(key)
    if hd:
        COSMOS_HD.append(key)


COSMOS_AMBIENTS = {  # key: names, what it shows, rarity, price
    "orion": ("Orion Nebula", "Nébuleuse d'Orion", "legendary", 1700,
              "M42: billowing clouds of magenta and crimson round a white-hot heart where young stars blaze, violet and blue wings, dark bays of dust — folding slowly.",
              "M42 : des nuages magenta et cramoisis autour d'un cœur blanc où brillent de jeunes étoiles, des ailes violettes et bleues, des baies de poussière — qui se replient lentement."),
    "crab": ("Crab Nebula", "Nébuleuse du Crabe", "epic", 1400,
             "What a star left when it blew up: a web of orange and red filaments round a ghostly cyan glow, its pulsar flickering in the middle.",
             "Ce qu'a laissé une étoile en explosant : une toile de filaments orange et rouges autour d'une lueur cyan, son pulsar qui scintille au milieu."),
    "helix": ("Helix Nebula", "Nébuleuse de l'Hélice", "epic", 1400,
              "The « eye of God »: a ring of teal gas streaked with cometary knots round a red ring and a deep blue heart, turning slowly.",
              "L'« œil de Dieu » : un anneau de gaz turquoise strié de nœuds cométaires autour d'un anneau rouge et d'un cœur bleu profond, qui tourne lentement."),
    "pillars": ("Pillars of Creation", "Piliers de la création", "legendary", 1800,
                "Towering columns of golden-brown dust against a blue field of stars, their tops lit and evaporating, stars with six spikes.",
                "Des colonnes de poussière dorée dressées sur un champ d'étoiles bleu, leurs sommets éclairés qui s'évaporent, des étoiles à six aigrettes."),
    "cliffs": ("Cosmic Cliffs", "Falaises cosmiques", "epic", 1300,
               "Carina's ridge of orange dust like a mountain range, steam rising from its crest into a blue sky of glowing gas.",
               "La crête de poussière orangée de la Carène comme une chaîne de montagnes, de la vapeur qui s'élève de sa crête dans un ciel de gaz bleu."),
    "solarsystem": ("Solar system", "Système solaire", "epic", 1300,
                    "The sun glowing on the side, six planets on their tilted orbits, the asteroid belt and a ringed giant.",
                    "Le soleil qui rayonne sur le côté, six planètes sur leurs orbites inclinées, la ceinture d'astéroïdes et une géante à anneaux."),
    "saturnrise": ("Ringed giant", "Géante aux anneaux", "epic", 1200,
                   "A ringed giant rising in a corner: banded clouds turning, rings with their gap, little moons going round.",
                   "Une géante aux anneaux qui se lève dans un coin : des nuages en bandes qui tournent, des anneaux et leur division, de petites lunes qui tournent."),
    "perseids": ("Perseids", "Perséides", "rare", 950,
                 "A summer night over the hills, shooting stars streaking from their radiant, now and then a fireball.",
                 "Une nuit d'été au-dessus des collines, des étoiles filantes qui jaillissent de leur radiant, parfois un bolide."),
    "constellations": ("Constellations", "Constellations", "epic", 1100,
                       "Orion, Cassiopeia, the Plough, the Swan, the Lion and the Scorpion drawing themselves in turn, star after star.",
                       "Orion, Cassiopée, la Grande Ourse, le Cygne, le Lion et le Scorpion qui se dessinent tour à tour, étoile après étoile."),
    "milkyway": ("Milky Way", "Voie lactée", "epic", 1300,
                 "A band of countless stars across the sky, its glowing core and dark lanes of dust, over the mountains.",
                 "Une bande d'innombrables étoiles à travers le ciel, son cœur lumineux et ses traînées de poussière, au-dessus des montagnes."),
    "greatcomet": ("Great comet", "Grande comète", "rare", 900,
                  "A great comet crossing the sky, its curved golden dust tail and its straight blue ion tail.",
                  "Une grande comète qui traverse le ciel, sa queue de poussière dorée et courbe, sa queue d'ions bleue et droite."),
}  # fmt: skip
for _k, (_en, _fr, _rarity, _price, _aen, _afr) in COSMOS_AMBIENTS.items():
    _cosmos(f"ambient_{_k}", "ambient", _price, _rarity, f"{_en} ambience", f"Ambiance {_fr}", _aen, _afr,
            {"ambient": _k}, collection="ambients", icon="telescope")  # fmt: skip
    _banner = {"legendary": 1500, "epic": 1100}.get(_rarity, 850)  # the banner as rare as its ambience
    _cosmos(f"banner_live_{_k}", "profile_banner", _banner, "epic" if _banner >= 1000 else "rare", f"{_en} animated banner", f"Bannière animée {_fr}",
            f"{_en} in your profile's banner, drawn by the graphics chip, for every visitor to see.",
            f"{_fr} dans la bannière de votre profil, dessiné par la puce graphique, pour tous vos visiteurs.",
            {"banner": f"live-{_k}"}, collection="profile", icon="image")  # fmt: skip

COSMOS_EFFECTS = {  # GPU effect: names, then what the frame, the level badge and the notifications show
    "stellar": ("Nebula", "Nébuleuse", "nebulaveil", "Glowing gas, pink and teal, folding round", "Du gaz lumineux, rose et turquoise, qui se replie autour"),
    "orrery": ("Orrery", "Planétaire", "orrery", "Planets going round on their orbits, a little sun in the middle", "Des planètes qui tournent sur leurs orbites, un petit soleil au milieu"),
    "starmap": ("Star chart", "Carte du ciel", "starchart", "A constellation drawing itself on a star chart", "Une constellation qui se dessine sur une carte du ciel"),
    "comet": ("Comet", "Comète", "cometring", "A comet going round, its tails streaming behind", "Une comète qui fait le tour, ses queues derrière elle"),
    "ringworld": ("Ringed planet", "Planète à anneaux", "ringedworld", "A ringed planet, its banded clouds turning", "Une planète à anneaux, ses nuages en bandes qui tournent"),
    "pulsar": ("Pulsar", "Pulsar", "pulsar", "A pulsar's beams sweeping round like a lighthouse", "Les faisceaux d'un pulsar qui balaient comme un phare"),
    "totality": ("Total eclipse", "Éclipse totale", "eclipse", "The corona of a total eclipse, the diamond ring flashing", "La couronne d'une éclipse totale, l'anneau de diamant qui étincelle"),
    "meteor": ("Shooting stars", "Étoiles filantes", "meteorite", "Shooting stars streaking across a night sky", "Des étoiles filantes qui traversent un ciel nocturne"),
}  # fmt: skip
HD_TEXT = ("drawn by the graphics chip", "dessiné par la puce graphique")
# the price of each look (frame, level badge, notifications): its rarity follows (rare from 600, epic from 1000;
# the legendary ones are named below)
COSMOS_PRICES = {
    "stellar": (1300, 1600, 1200), "orrery": (1200, 1500, 1000), "starmap": (900, 1400, 850), "comet": (850, 1300, 800),
    "ringworld": (1600, 1700, 1100), "pulsar": (1100, 1500, 900), "totality": (1400, 1900, 1200), "meteor": (750, 1000, 700),
}  # fmt: skip


def _tier(price: int) -> str:
    return "epic" if price >= 1000 else "rare" if price >= 600 else "common"


for _fx, (_en, _fr, _frame, _aen, _afr) in COSMOS_EFFECTS.items():
    _fp, _lp, _np = COSMOS_PRICES[_fx]
    _cosmos(f"frame_{_frame}", "avatar_frame", _fp, _tier(_fp), f"{_en} frame", f"Cadre {_fr.lower()}",
            f"{_aen} your avatar, {HD_TEXT[0]}.", f"{_afr} de votre avatar, {HD_TEXT[1]}.", {"frame": _frame},
            collection="profile", icon="user")  # fmt: skip
    _cosmos(f"level_{_fx}", "level_badge", _lp, _tier(_lp), f"{_en} level badge", f"Badge de niveau {_fr.lower()}",
            f"Your level inside: {_aen.lower()}, {HD_TEXT[0]}.", f"Votre niveau au cœur : {_afr.lower()}, {HD_TEXT[1]}.",
            {"style": _fx}, collection="levels", icon="trophy")  # fmt: skip
    _cosmos(f"notif_{_fx}", "notification_style", _np, _tier(_np), f"{_en} notifications", f"Notifications {_fr.lower()}",
            f"Notifications in a shape of their own: {_aen.lower()}, {HD_TEXT[0]}.",
            f"Des notifications à la forme bien à elles : {_afr.lower()}, {HD_TEXT[1]}.", {"style": _fx},
            collection="looks", icon="bell")  # fmt: skip
for _k, _price, _en, _fr, _aen, _afr in (
    ("shootingstar", 750, "Shooting star", "Étoile filante", "Notifications streaking in like a shooting star.", "Des notifications qui arrivent comme une étoile filante."),
    ("nebulabloom", 1000, "Nebula bloom", "Éclosion de nébuleuse", "Notifications blooming out of a cloud of glowing gas.", "Des notifications qui éclosent d'un nuage de gaz lumineux."),
    ("eclipsed", 900, "Eclipse", "Éclipse", "Notifications appearing as the moon slides off the sun, the corona flaring.", "Des notifications qui apparaissent quand la lune quitte le soleil, la couronne qui flamboie."),
):  # fmt: skip
    _cosmos(f"notif_{_k}", "notification_animation", _price, _tier(_price), f"{_en} notification animation",
            f"Animation de notification {_fr.lower()}", _aen, _afr, {"animation": _k}, collection="looks", icon="bell-ring")  # fmt: skip
for _k, _price, _en, _fr, _aen, _afr in (
    ("starshower", 1100, "Meteor storm", "Pluie d'étoiles filantes", "Dozens of shooting stars streaking out of the reward, fireballs flaring green and gold.", "Des dizaines d'étoiles filantes qui jaillissent de la récompense, des bolides verts et dorés."),
    ("bigbang", 1600, "Big Bang", "Big Bang", "A point of light, a blinding flash, a ball of fire cooling into the cosmic web and its first galaxies.", "Un point de lumière, un éclair aveuglant, une boule de feu qui refroidit en toile cosmique et ses premières galaxies."),
):  # fmt: skip
    _cosmos(f"effect_{_k}", "effect", _price, _tier(_price), f"{_en} celebration", f"Célébration {_fr}", _aen, _afr,
            {"effect": _k}, collection="celebrations", icon="party")  # fmt: skip
for _k, _en, _fr, _price, _rarity, _aen, _afr in (
    ("hyperjump", "Hyperspace jump", "Saut dans l'hyperespace", 2000, "legendary",
     "The stars stretch into streaks, a tunnel of light rushes past — a flash — and you come out before a nebula in bloom, at your new level.",
     "Les étoiles s'étirent en traînées, un tunnel de lumière défile — un éclair — et vous arrivez devant une nébuleuse en fleur, à votre nouveau niveau."),
    ("constellate", "A constellation is born", "Naissance d'une constellation", 1500, "epic",
     "Stars light up one by one round your new level and join into a crown of stars.",
     "Des étoiles s'allument une à une autour de votre nouveau niveau et se relient en couronne d'étoiles."),
):  # fmt: skip
    _cosmos(f"levelup_{_k}", "level_up", _price, _rarity, f"{_en} level-up", f"Passage de niveau {_fr.lower()}", _aen,
            _afr, {"animation": _k}, collection="levels", icon="trophy")  # fmt: skip

# not drawn by the GPU: faces of their own, colours, banners, titles and badges
for _k, _en, _fr, _price, _aen, _afr in (
    ("spaceage", "Space age", "ère spatiale", 350, "A name in rounded space-age letters, silver turning to sky blue, glowing softly.",
     "Un nom en lettres arrondies de l'ère spatiale, l'argent qui vire au bleu ciel, d'un éclat doux."),
    ("starlines", "Star lines", "lignes d'étoiles", 650, "A name drawn in fine lines like a constellation's, a star twinkling at its end.",
     "Un nom tracé en traits fins comme ceux d'une constellation, une étoile qui scintille au bout."),
    ("staratlas", "Star atlas", "atlas céleste", 300, "A name engraved in gold like the title of an old star atlas.",
     "Un nom gravé à l'or comme le titre d'un vieil atlas céleste."),
):  # fmt: skip
    _cosmos(f"name_{_k}", "name_style", _price, "common", f"{_en} name style", f"Style de nom {_fr}", _aen, _afr,
            {"style": _k}, collection="names", icon="feather", hd=False)  # fmt: skip
    SHOP[-1]["rarity"] = _tier(_price)
for _k, _en, _fr, _aen, _afr in (
    ("orionpink", "Orion pink", "Rose d'Orion", "Orion's magenta and violet over the theme.", "Le magenta et le violet d'Orion sur le thème."),
    ("deepspace", "Deep space", "Espace lointain", "The blue and teal of deep space over the theme.", "Le bleu et le turquoise de l'espace lointain sur le thème."),
):  # fmt: skip
    _cosmos(f"palette_{_k}", "palette", 200, "common", f"{_en} palette", f"Palette {_fr.lower()}", _aen, _afr,
            {"palette": _k}, collection="palettes", icon="palette", hd=False)  # fmt: skip
for _k, _en, _fr, _aen, _afr in (
    ("starchart", "Star chart", "Carte du ciel", "A navy star chart, its grid and two constellations drawn.", "Une carte du ciel bleu nuit, sa grille et deux constellations tracées."),
    ("orbits", "Orbits", "Orbites", "A sun and its planets on their orbits.", "Un soleil et ses planètes sur leurs orbites."),
):  # fmt: skip
    _cosmos(f"banner_{_k}", "profile_banner", 300, "common", f"{_en} banner", f"Bannière {_fr.lower()}", _aen, _afr,
            {"banner": _k}, collection="profile", icon="image", hd=False)  # fmt: skip
for _label, _fr, _style, _price in (
    ("Astronomer", "Titre : Astronome", "starmap", 650), ("Comet chaser", "Titre : Chasseur de comètes", "comet", 450),
    ("Event horizon", "Titre : Horizon des événements", "totality", 1100), ("Cosmonaut", "Titre : Cosmonaute", "orrery", 700),
):  # fmt: skip
    _cosmos(f"title_{_label.lower().replace(' ', '_')}", "title", _price, _tier(_price), f"Title: {_label}", _fr,
            f"« {_label} » under your name, {HD_TEXT[0]}.", f"« {_label} » sous votre nom, {HD_TEXT[1]}.",
            {"label": _label, "style": _style}, collection="titles", icon="trophy")  # fmt: skip
for _label, _fr, _icon, _style, _price in (
    ("Telescope", "Badge Télescope", "telescope", "stellar", 650), ("Ringed planet", "Badge Planète à anneaux", "orbit", "ringworld", 700),
    ("Pulsar", "Badge Pulsar", "radio", "pulsar", 450), ("Meteorite", "Badge Météorite", "sparkle", "meteor", 350),
):  # fmt: skip
    _cosmos(f"badge_{_label.lower().replace(' ', '_')}", "badge", _price, _tier(_price), f"{_label} badge", _fr,
            f"A « {_label} » badge on your profile, {HD_TEXT[0]}.", f"Un badge « {_label} » sur votre profil, {HD_TEXT[1]}.",
            {"label": _label, "icon": _icon, "style": _style}, collection="badges", icon="star")  # fmt: skip
ZODIAC = (
    ("aries", "Aries", "Bélier"), ("taurus", "Taurus", "Taureau"), ("gemini", "Gemini", "Gémeaux"), ("cancer", "Cancer", "Cancer"),
    ("leo", "Leo", "Lion"), ("virgo", "Virgo", "Vierge"), ("libra", "Libra", "Balance"), ("scorpio", "Scorpio", "Scorpion"),
    ("sagittarius", "Sagittarius", "Sagittaire"), ("capricorn", "Capricorn", "Capricorne"), ("aquarius", "Aquarius", "Verseau"),
    ("pisces", "Pisces", "Poissons"),
)  # fmt: skip
for _sign, _en, _fr in ZODIAC:
    _cosmos(f"badge_zodiac_{_sign}", "badge", 300, "common", f"{_en} badge", f"Badge {_fr}",
            f"The constellation of {_en}, its stars joined, on your profile — {HD_TEXT[0]}.",
            f"La constellation du {_fr}, ses étoiles reliées, sur votre profil — {HD_TEXT[1]}.",
            {"label": _en, "icon": f"zodiac-{_sign}", "style": "starmap"}, collection="badges", icon="star")  # fmt: skip

# given, never sold: an achievement's or a level's (see the demo achievements and the level rewards)
for _key, _kind, _payload, _en, _fr, _aen, _afr, _icon in (
    ("frame_polaris", "avatar_frame", {"frame": "polaris"}, "Polaris frame", "Cadre étoile polaire",
     "A star chart in the shape of the North Star round your avatar. Given at level 40.", "Une carte du ciel en forme d'étoile polaire autour de votre avatar. Offert au niveau 40.", "user"),
    ("title_night_watcher", "title", {"label": "Night watcher", "style": "starmap"}, "Title: Night watcher", "Titre : Veilleur de nuit",
     "Given by a secret achievement of the night.", "Offert par un succès secret de la nuit.", "moon"),
    ("title_star_sailor", "title", {"label": "Star sailor", "style": "comet"}, "Title: Star sailor", "Titre : Navigateur des étoiles",
     "Given at level 26 (Or II).", "Offert au niveau 26 (Or II).", "rocket"),
    ("badge_supernova", "badge", {"label": "Supernova", "icon": "sparkles", "style": "stellar"}, "Supernova badge", "Badge Supernova",
     "Given at level 46 (Diamant II).", "Offert au niveau 46 (Diamant II).", "sparkles"),
):  # fmt: skip
    _cosmos(
        _key,
        _kind,
        None,
        "legendary",
        _en,
        _fr,
        _aen,
        _afr,
        _payload,
        collection="rewards",
        icon=_icon,
        reward=True,
    )

# the packs: everything that is not drawn by the GPU, then three HD packs (the Prestige HD booster draws from
# them too), the zodiac — and a booster drawing only from these
_ZODIAC_KEYS = [f"badge_zodiac_{sign}" for sign, _, _ in ZODIAC]
_SOLD = [
    key
    for key in COSMOS_KEYS
    if key not in ("frame_polaris", "title_night_watcher", "title_star_sailor", "badge_supernova")
]
_NEBULAE = ("orion", "crab", "helix", "pillars", "cliffs")
_PLANETS = ("solarsystem", "saturnrise")
COSMOS_PACKS: tuple[tuple[str, str, str, str, str, str, list[str]], ...] = (
    ("pack_astro", "Astronomy pack", "Pack Astronomie", "telescope",
     "The cosmos' name styles, palettes and banners together.",
     "Les styles de nom, palettes et bannières du cosmos réunis.",
     [k for k in _SOLD if k not in COSMOS_HD]),
    ("pack_hd_nebulae", "Nebulae HD pack", "Pack Nébuleuses HD", "sparkles",
     "Orion, the Crab, the Helix, the Pillars of Creation and Carina's cliffs — behind the portal and in your banner — with the nebula frame, level badge and notifications.",
     "Orion, le Crabe, l'Hélice, les Piliers de la création et les falaises de la Carène — derrière le portail et dans votre bannière — avec le cadre, le badge de niveau et les notifications nébuleuse.",
     [*(f"ambient_{k}" for k in _NEBULAE), *(f"banner_live_{k}" for k in _NEBULAE), "frame_nebulaveil", "level_stellar",
      "notif_stellar", "notif_nebulabloom", "badge_telescope"]),
    ("pack_hd_planets", "Planets HD pack", "Pack Planètes HD", "orbit",
     "The solar system and the ringed giant, their animated banners, the orrery and ringed-world frames, level badges and notifications.",
     "Le système solaire et la géante aux anneaux, leurs bannières animées, les cadres planétaire et monde aux anneaux, leurs badges de niveau et notifications.",
     [*(f"ambient_{k}" for k in _PLANETS), *(f"banner_live_{k}" for k in _PLANETS), "frame_orrery", "frame_ringedworld",
      "level_orrery", "level_ringworld", "notif_orrery", "notif_ringworld", "badge_ringed_planet", "title_cosmonaut"]),
    ("pack_hd_stars", "Stars HD pack", "Pack Étoiles HD", "star",
     "Shooting stars, constellations and the Milky Way: ambiences, banners, frames, level badges, notifications, the meteor storm and a constellation's birth.",
     "Étoiles filantes, constellations et Voie lactée : ambiances, bannières, cadres, badges de niveau, notifications, la pluie d'étoiles filantes et la naissance d'une constellation.",
     [*(f"ambient_{k}" for k in ("perseids", "constellations", "milkyway")),
      *(f"banner_live_{k}" for k in ("perseids", "constellations", "milkyway")),
      "frame_starchart", "frame_meteorite", "level_starmap", "level_meteor", "notif_starmap", "notif_meteor",
      "notif_shootingstar", "effect_starshower", "levelup_constellate", "badge_meteorite", "title_astronomer"]),
    ("pack_hd_comets", "Comets and eclipses HD pack", "Pack Comètes et éclipses HD", "moon",
     "The great comet, pulsars and the total eclipse: an ambience, a banner, frames, level badges, notifications, the Big Bang and the hyperspace jump.",
     "La grande comète, les pulsars et l'éclipse totale : une ambiance, une bannière, des cadres, des badges de niveau, des notifications, le Big Bang et le saut dans l'hyperespace.",
     ["ambient_greatcomet", "banner_live_greatcomet", "frame_cometring", "frame_pulsar", "frame_eclipse", "level_comet",
      "level_pulsar", "level_totality", "notif_comet", "notif_pulsar", "notif_totality", "notif_eclipsed", "effect_bigbang",
      "levelup_hyperjump", "badge_pulsar", "title_comet_chaser", "title_event_horizon"]),
    ("pack_zodiac", "Zodiac pack", "Pack Zodiaque", "zodiac-leo",
     "The twelve constellations of the zodiac as badges, drawn by the graphics chip.",
     "Les douze constellations du zodiaque en badges, dessinées par la puce graphique.",
     _ZODIAC_KEYS),
)  # fmt: skip
for _key, _en, _fr, _icon, _aen, _afr, _held in COSMOS_PACKS:
    _p(
        _key,
        "bundle",
        None,
        "epic",
        _en,
        _fr,
        _aen,
        _afr,
        {"products": list(_held)},
        collection="packs",
        icon=_icon,
    )
_p("booster_celestial", "booster", 500, "epic", "Celestial booster", "Booster Céleste",
   "Five looks of the cosmos drawn at random — nebulae, planets, comets, constellations, the zodiac… at least one rare.",
   "Cinq looks du cosmos tirés au hasard — nébuleuses, planètes, comètes, constellations, zodiaque… dont au moins un rare.",
   {"pool": "looks", "packs": [k for k, *_ in COSMOS_PACKS], "cards": 5, "odds": {"common": 50, "rare": 32, "epic": 15, "legendary": 3},
    "guarantee": "rare", "look": "celestial"}, collection="boosters", icon="sparkles", repeatable=True)  # fmt: skip

# #130, the second wave: the sun, the moon, asteroids, the Big Bang, rockets and their crews — many light looks
# (drawn in CSS) for everyone and for the boosters, a few more drawn by the graphics chip
WAVE2: list[str] = []


def _wave2(key: str, kind: str, price: int, en: str, fr: str, about_en: str, about_fr: str, payload: dict[str, Any],
           *, collection: str, icon: str, hd: bool = False) -> None:  # fmt: skip
    _cosmos(
        key,
        kind,
        price,
        _tier(price),
        en,
        fr,
        about_en,
        about_fr,
        payload,
        collection=collection,
        icon=icon,
        hd=hd,
    )
    WAVE2.append(key)


for _k, _en, _fr, _price, _rarity, _aen, _afr in (
    ("solarflare", "Solar flare", "Éruption solaire", 1700, "legendary",
     "The sun up close: its boiling surface, dark spots, prominences arching off its edge, a flare now and then.",
     "Le soleil de tout près : sa surface en ébullition, ses taches, des protubérances qui jaillissent de son bord, parfois une éruption."),
    ("moonrise", "Moonrise", "Lever de lune", 950, "rare",
     "A full moon rising over a calm sea, its silver path trembling on the water, thin clouds drifting.",
     "Une pleine lune qui se lève sur une mer calme, son chemin d'argent qui tremble sur l'eau, de fins nuages qui passent."),
    ("asteroids", "Asteroid belt", "Ceinture d'astéroïdes", 900, "rare",
     "Rocks of every size tumbling past in three depths, lit by a far sun, dust glittering between them.",
     "Des rochers de toutes tailles qui tournoient sur trois plans, éclairés par un soleil lointain, de la poussière qui scintille."),
):  # fmt: skip
    _wave2(f"ambient_{_k}", "ambient", _price, f"{_en} ambience", f"Ambiance {_fr.lower()}", _aen, _afr, {"ambient": _k},
           collection="ambients", icon="telescope", hd=True)  # fmt: skip
    SHOP[-1]["rarity"] = _rarity
    _wave2(f"banner_live_{_k}", "profile_banner", 1100 if _rarity == "legendary" else 850, f"{_en} animated banner",
           f"Bannière animée {_fr.lower()}", f"{_en} in your profile's banner, {HD_TEXT[0]}.",
           f"{_fr} dans la bannière de votre profil, {HD_TEXT[1]}.", {"banner": f"live-{_k}"}, collection="profile",
           icon="image", hd=True)  # fmt: skip
for _fx, _frame, _en, _fr, _prices, _aen, _afr in (
    ("solar", "heliosphere", "Sun", "Soleil", (1300, 1600, 1100), "The sun's boiling surface, its corona and its prominences", "La surface en ébullition du soleil, sa couronne et ses protubérances"),
    ("lunar", "lunarhalo", "Moon", "Lune", (1200, 1500, 1000), "The moon's seas and craters, its phases sweeping across", "Les mers et les cratères de la lune, ses phases qui défilent"),
):  # fmt: skip
    _wave2(f"frame_{_frame}", "avatar_frame", _prices[0], f"{_en} frame", f"Cadre {_fr.lower()}", f"{_aen} round your avatar, {HD_TEXT[0]}.",
           f"{_afr} autour de votre avatar, {HD_TEXT[1]}.", {"frame": _frame}, collection="profile", icon="user", hd=True)  # fmt: skip
    _wave2(f"level_{_fx}", "level_badge", _prices[1], f"{_en} level badge", f"Badge de niveau {_fr.lower()}",
           f"Your level inside: {_aen.lower()}, {HD_TEXT[0]}.", f"Votre niveau au cœur : {_afr.lower()}, {HD_TEXT[1]}.",
           {"style": _fx}, collection="levels", icon="trophy", hd=True)  # fmt: skip
    _wave2(f"notif_{_fx}", "notification_style", _prices[2], f"{_en} notifications", f"Notifications {_fr.lower()}",
           f"Notifications drawn as {_aen.lower()}, {HD_TEXT[0]}.", f"Des notifications dessinées comme {_afr.lower()}, {HD_TEXT[1]}.",
           {"style": _fx}, collection="looks", icon="bell", hd=True)  # fmt: skip
for _kind, _k, _price, _en, _fr, _aen, _afr, _icon, _coll, _fld in (
    ("avatar_frame", "crescent", 650, "Crescent moon frame", "Cadre croissant de lune", "Your avatar lit on one side like a crescent moon.", "Votre avatar éclairé d'un côté comme un croissant de lune.", "user", "profile", "frame"),
    ("avatar_frame", "sunrays", 650, "Sun rays frame", "Cadre rayons de soleil", "Golden rays turning slowly round your avatar.", "Des rayons dorés qui tournent lentement autour de votre avatar.", "user", "profile", "frame"),
    ("avatar_frame", "asteroidring", 600, "Asteroid ring frame", "Cadre anneau d'astéroïdes", "Rocks going round your avatar.", "Des rochers qui tournent autour de votre avatar.", "user", "profile", "frame"),
    ("avatar_frame", "saturnring", 700, "Saturn's ring frame", "Cadre anneau de Saturne", "Your avatar as a ringed planet.", "Votre avatar en planète à anneaux.", "user", "profile", "frame"),
    ("profile_banner", "lunarsurface", 300, "Lunar surface banner", "Bannière surface lunaire", "Grey dunes and craters under a black sky, the moon high.", "Des dunes grises et des cratères sous un ciel noir.", "image", "profile", "banner"),
    ("profile_banner", "earthrise", 350, "Earthrise banner", "Bannière lever de Terre", "The blue Earth rising over the moon's horizon.", "La Terre bleue qui se lève sur l'horizon de la lune.", "image", "profile", "banner"),
    ("profile_banner", "asteroidfield", 300, "Asteroid field banner", "Bannière champ d'astéroïdes", "Rocks floating in the dark.", "Des rochers qui flottent dans le noir.", "image", "profile", "banner"),
    ("profile_banner", "launchpad", 300, "Launch pad banner", "Bannière pas de tir", "A tower on its pad at dusk, the flames of a launch below.", "Une tour sur son pas de tir au crépuscule, les flammes d'un lancement en bas.", "image", "profile", "banner"),
    ("level_badge", "moonphase", 650, "Moon phase level badge", "Badge de niveau phase de lune", "Your level beside a crescent moon.", "Votre niveau à côté d'un croissant de lune.", "trophy", "levels", "style"),
    ("level_badge", "sunbadge", 650, "Sunny level badge", "Badge de niveau soleil", "Your level on a glowing sun.", "Votre niveau sur un soleil rayonnant.", "trophy", "levels", "style"),
    ("level_badge", "rocketbadge", 600, "Rocket level badge", "Badge de niveau fusée", "Your level on a rocket's hull, its engine lit.", "Votre niveau sur la coque d'une fusée, moteur allumé.", "trophy", "levels", "style"),
    ("notification_style", "transmission", 600, "Transmission notifications", "Notifications transmission", "Notifications coming in as a radio transmission, green on black.", "Des notifications qui arrivent en transmission radio, vert sur noir.", "bell", "looks", "style"),
    ("notification_style", "missioncontrol", 650, "Mission control notifications", "Notifications contrôle de mission", "Notifications on mission control's amber screens.", "Des notifications sur les écrans ambrés du contrôle de mission.", "bell", "looks", "style"),
    ("notification_animation", "liftoff", 500, "Lift-off notification animation", "Animation de notification décollage", "Notifications shaking on the pad, then lifting off.", "Des notifications qui tremblent sur le pas de tir puis décollent.", "bell-ring", "looks", "animation"),
    ("notification_animation", "orbitin", 550, "Into orbit notification animation", "Animation de notification mise en orbite", "Notifications swinging in on an orbit.", "Des notifications qui arrivent en suivant une orbite.", "bell-ring", "looks", "animation"),
    ("effect", "comets", 300, "Comets celebration", "Célébration comètes", "Little comets streaking out of the reward.", "De petites comètes qui jaillissent de la récompense.", "party", "celebrations", "effect"),
    ("effect", "planets", 350, "Planets celebration", "Célébration planètes", "Little planets, a ringed one among them, bursting out.", "De petites planètes, dont une à anneaux, qui jaillissent.", "party", "celebrations", "effect"),
    ("name_style", "lunarsilver", 350, "Lunar silver name style", "Style de nom argent lunaire", "A name in silver, wide space-age letters.", "Un nom en argent, en larges lettres de l'ère spatiale.", "feather", "names", "style"),
    ("name_style", "solarfire", 400, "Solar fire name style", "Style de nom feu solaire", "A name burning like the sun, yellow to red.", "Un nom qui brûle comme le soleil, du jaune au rouge.", "feather", "names", "style"),
    ("name_style", "bigbang", 650, "Big Bang name style", "Style de nom Big Bang", "A name swelling with every colour of the first light.", "Un nom qui enfle de toutes les couleurs de la première lumière.", "feather", "names", "style"),
    ("palette", "solarflare", 200, "Solar flare palette", "Palette éruption solaire", "The sun's orange and fire over the theme.", "L'orange et le feu du soleil sur le thème.", "palette", "palettes", "palette"),
    ("palette", "lunar", 200, "Lunar palette", "Palette lunaire", "The moon's silver and blue over the theme.", "L'argent et le bleu de la lune sur le thème.", "palette", "palettes", "palette"),
    ("palette", "nebulateal", 200, "Teal nebula palette", "Palette nébuleuse turquoise", "A nebula's teal and violet over the theme.", "Le turquoise et le violet d'une nébuleuse sur le thème.", "palette", "palettes", "palette"),
):  # fmt: skip
    _prefix = {"avatar_frame": "frame", "profile_banner": "banner", "level_badge": "level", "notification_style": "notif",
               "notification_animation": "notif", "effect": "effect", "name_style": "name", "palette": "palette"}[_kind]  # fmt: skip
    _wave2(f"{_prefix}_{_k}", _kind, _price, _en, _fr, _aen, _afr, {_fld: _k}, collection=_coll, icon=_icon)
for _label, _fr, _icon, _style, _price, _gpu in (
    ("Moonwalker", "Badge Marcheur lunaire", "moon", "float", 250, False), ("Sun chaser", "Badge Chasseur de soleil", "sun", "pulse", 250, False),
    ("Asteroid miner", "Badge Mineur d'astéroïdes", "gem", "shimmer", 300, False), ("Big Bang", "Badge Big Bang", "sparkles", "rainbow", 450, False),
    ("Space cadet", "Badge Cadet de l'espace", "rocket", "shimmer", 200, False), ("Starship captain", "Badge Capitaine de vaisseau", "crown", "gold", 650, False),
    ("Navigator", "Badge Navigateur", "compass", "spin", 250, False), ("Ship engineer", "Badge Ingénieur de bord", "wrench", "pulse", 250, False),
    ("Satellite", "Badge Satellite", "satellite", "spin", 300, False), ("Red planet", "Badge Planète rouge", "orbit", "pulse", 300, False),
    ("Solar wind", "Badge Vent solaire", "wind", "float", 250, False), ("Lunar module", "Badge Module lunaire", "package", "shimmer", 300, False),
    ("First contact", "Badge Premier contact", "radio", "neon", 450, False), ("Stardust", "Badge Poussière d'étoiles", "sparkle", "float", 200, False),
    ("Moon base", "Badge Base lunaire", "home", "frost", 350, False), ("Sunspot", "Badge Tache solaire", "sun", "solar", 700, True),
    ("Full moon", "Badge Pleine lune", "moon", "lunar", 700, True),
):  # fmt: skip
    _wave2(f"badge_{_label.lower().replace(' ', '_')}", "badge", _price, f"{_label} badge", _fr,
           f"A « {_label} » badge on your profile{', ' + HD_TEXT[0] if _gpu else ''}.",
           f"Un badge « {_label} » sur votre profil{', ' + HD_TEXT[1] if _gpu else ''}.",
           {"label": _label, "icon": _icon, "style": _style}, collection="badges", icon="star", hd=_gpu)  # fmt: skip
for _label, _fr, _style, _price, _gpu in (
    ("Moonwalker", "Titre : Marcheur lunaire", "float", 200, False), ("Sun worshipper", "Titre : Adorateur du soleil", "gold", 250, False),
    ("Asteroid miner", "Titre : Mineur d'astéroïdes", "shimmer", 250, False), ("Space cadet", "Titre : Cadet de l'espace", "pulse", 150, False),
    ("Starship captain", "Titre : Capitaine de vaisseau", "gold", 600, False), ("Ground control", "Titre : Contrôle au sol", "neon", 300, False),
    ("Light-year traveller", "Titre : Voyageur des années-lumière", "rainbow", 450, False), ("Mission specialist", "Titre : Spécialiste de mission", "shimmer", 300, False),
    ("Orbit master", "Titre : Maître des orbites", "frost", 300, False), ("Big Bang theorist", "Titre : Théoricien du Big Bang", "rainbow", 500, False),
    ("Child of the Sun", "Titre : Enfant du Soleil", "solar", 800, True), ("Moonchild", "Titre : Enfant de la Lune", "lunar", 800, True),
):  # fmt: skip
    _wave2(f"title_{_label.lower().replace(' ', '_').replace('-', '_')}", "title", _price, f"Title: {_label}", _fr,
           f"« {_label} » under your name{', ' + HD_TEXT[0] if _gpu else ''}.",
           f"« {_label} » sous votre nom{', ' + HD_TEXT[1] if _gpu else ''}.",
           {"label": _label, "style": _style}, collection="titles", icon="trophy", hd=_gpu)  # fmt: skip
COSMOS_LEGENDARY.add("ambient_solarflare")
SHOP[[p["key"] for p in SHOP].index("ambient_solarflare")]["rarity"] = "legendary"
WAVE2_PACKS = (
    ("pack_hd_sunmoon", "Sun and Moon HD pack", "Pack Soleil et Lune HD", "sun",
     "The solar flare and the moonrise, the asteroid belt — behind the portal and in your banner — with the sun's and the moon's frames, level badges and notifications.",
     "L'éruption solaire et le lever de lune, la ceinture d'astéroïdes — derrière le portail et dans votre bannière — avec les cadres, badges de niveau et notifications du soleil et de la lune.",
     [k for k in WAVE2 if k in COSMOS_HD and not k.startswith(("badge_", "title_"))]),
    ("pack_spacecrew", "Space crew pack", "Pack Équipage", "rocket",
     "The crew's badges and titles: moonwalker, captain, navigator, engineer, first contact…",
     "Les badges et titres de l'équipage : marcheur lunaire, capitaine, navigateur, ingénieur, premier contact…",
     [k for k in WAVE2 if k not in COSMOS_HD and k.startswith(("badge_", "title_"))]),
    ("pack_sunmoon", "Sun and Moon pack", "Pack Soleil et Lune", "moon",
     "The sun's and the moon's frames, banners, level badges, notifications, celebrations, name styles and palettes.",
     "Les cadres, bannières, badges de niveau, notifications, célébrations, styles de nom et palettes du soleil et de la lune.",
     [k for k in WAVE2 if k not in COSMOS_HD and not k.startswith(("badge_", "title_"))]),
)  # fmt: skip
for _key, _en, _fr, _icon, _aen, _afr, _held in WAVE2_PACKS:
    _p(
        _key,
        "bundle",
        None,
        "epic",
        _en,
        _fr,
        _aen,
        _afr,
        {"products": list(_held)},
        collection="packs",
        icon=_icon,
    )
COSMOS_PACKS = (*COSMOS_PACKS, *WAVE2_PACKS)
next(p for p in SHOP if p["key"] == "booster_celestial")["payload"]["packs"] = [k for k, *_ in COSMOS_PACKS]

# the level each one needs, set here rather than spread: the legendary ones on the great tiers, the epic ones
# along the curve, the rare ones early, the common ones for everyone; a pack asks the highest of what it holds
COSMOS_LEVELS: dict[str, int | None] = {
    # legendary
    "ambient_orion": 20, "ambient_pillars": 30, "frame_ringedworld": 40, "levelup_hyperjump": 40, "level_totality": 30,
    "effect_bigbang": 20,
    # epic
    "ambient_crab": 12, "ambient_helix": 14, "ambient_cliffs": 16, "ambient_solarsystem": 6, "ambient_saturnrise": 9,
    "ambient_milkyway": 8, "ambient_constellations": 5,
    "banner_live_orion": 18, "banner_live_pillars": 25, "banner_live_crab": 11, "banner_live_helix": 13,
    "banner_live_cliffs": 15, "banner_live_solarsystem": 7, "banner_live_saturnrise": 10, "banner_live_milkyway": 9,
    "banner_live_constellations": 6,
    "frame_nebulaveil": 15, "frame_orrery": 11, "frame_pulsar": 13, "frame_eclipse": 31,
    "level_stellar": 47, "level_orrery": 24, "level_starmap": 12, "level_comet": 10, "level_ringworld": 44,
    "level_pulsar": 19, "level_meteor": 7,
    "notif_stellar": 9, "notif_orrery": 8, "notif_ringworld": 13, "notif_totality": 16, "notif_nebulabloom": 11,
    "effect_starshower": 10, "levelup_constellate": 29, "title_event_horizon": 15,
    # rare
    "ambient_perseids": 4, "ambient_greatcomet": 3, "banner_live_perseids": 3, "banner_live_greatcomet": 2,
    "frame_starchart": 6, "frame_cometring": 5, "frame_meteorite": 3,
    "notif_starmap": 4, "notif_comet": 3, "notif_pulsar": 6, "notif_meteor": 2, "notif_shootingstar": 3, "notif_eclipsed": 7,
    "name_starlines": 4, "title_astronomer": 5, "title_cosmonaut": 8, "badge_telescope": 6, "badge_ringed_planet": 7,
    "booster_celestial": 5,
}  # fmt: skip
COSMOS_LEVELS |= {  # the second wave
    "ambient_solarflare": 30, "banner_live_solarflare": 21, "ambient_moonrise": 4, "banner_live_moonrise": 3,
    "ambient_asteroids": 3, "banner_live_asteroids": 2,
    "frame_heliosphere": 28, "level_solar": 35, "notif_solar": 12, "frame_lunarhalo": 14, "level_lunar": 42,
    "notif_lunar": 9, "frame_crescent": 4, "frame_sunrays": 5, "frame_asteroidring": 3, "frame_saturnring": 6,
    "level_moonphase": 5, "level_sunbadge": 6, "level_rocketbadge": 4, "notif_transmission": 3, "notif_missioncontrol": 4,
    "name_bigbang": 6, "badge_starship_captain": 34, "title_starship_captain": 38, "badge_sunspot": 22, "badge_full_moon": 27,
    "title_child_of_the_sun": 48, "title_moonchild": 39,
}  # fmt: skip
for _key in COSMOS_KEYS:
    COSMOS_LEVELS.setdefault(_key, None)  # the common ones: for everyone
for _key, *_text, _held in COSMOS_PACKS:
    _most = max((COSMOS_LEVELS.get(k) or 0 for k in _held), default=0)
    # an HD pack is legendary (its worth): it unlocks on the great tier at or above what it holds
    COSMOS_LEVELS[_key] = (
        next(t for t in (10, 20, 30, 40, 50) if t >= _most)
        if _key.startswith("pack_hd_") and _most
        else _most or None
    )


UNIVERSE_MADE: dict[str, list[str]] = {theme: _looks(rows)[0] for theme, rows in UNIVERSE_ROWS.items()}
_SLOTS = ("banner_", "frame_", "name_", "notif_", "effect_", "ambient_", "badge_", "title_")


def _slot(made: list[str], prefix: str) -> str | None:
    """The first made product of a slot (a static banner, not an animated one; a notification style first)."""
    found = [key for key in made if key.startswith(prefix) and not key.startswith("banner_live_")]
    if prefix == "notif_":
        found = [
            key for key in found if any(p["key"] == key and p["type"] == "notification_style" for p in SHOP)
        ]
    return found[0] if found else None


for _theme, _made in UNIVERSE_MADE.items():
    _row = tuple(_slot(_made, prefix) for prefix in _SLOTS)
    UNIVERSES[_theme] = (
        _row[0] or "",
        _row[1] or "",
        _row[2] or "",
        _row[3] or "",
        _row[4],
        _row[5],
        _row[6] or "",
        _row[7],
    )
    UNIVERSE_EXTRAS[_theme] = tuple(key for key in _made if key not in _row)

# #130: the cosmos' interfaces and what their theme packs hold
UNIVERSES["observatory"] = ("banner_starchart", "frame_starchart", "name_staratlas", "notif_starmap",
                            "effect_starshower", "ambient_constellations", "badge_telescope", "title_astronomer")  # fmt: skip
UNIVERSE_EXTRAS["observatory"] = ("banner_live_constellations", "level_starmap", "palette_orionpink", "name_starlines",
                                  "badge_zodiac_leo", "badge_zodiac_scorpio")  # fmt: skip
UNIVERSES["spacestation"] = ("banner_orbits", "frame_orrery", "name_spaceage", "notif_orrery", "effect_bigbang",
                             "ambient_solarsystem", "badge_ringed_planet", "title_cosmonaut")  # fmt: skip
UNIVERSE_EXTRAS["spacestation"] = ("banner_live_solarsystem", "level_orrery", "palette_deepspace", "badge_pulsar",
                                   "title_comet_chaser")  # fmt: skip
UNIVERSES["starship"] = ("banner_launchpad", "frame_asteroidring", "name_lunarsilver", "notif_missioncontrol",
                         "effect_comets", "ambient_asteroids", "badge_starship_captain", "title_starship_captain")  # fmt: skip
UNIVERSE_EXTRAS["starship"] = ("banner_live_asteroids", "level_rocketbadge", "badge_navigator", "badge_ship_engineer",
                               "title_mission_specialist", "title_ground_control")  # fmt: skip


# 027 (#30): each universe's dashboard looks — its theme pack includes them (and the widget a look needs)
UNIVERSE_LOOKS: dict[str, tuple[str, ...]] = {
    "cyberpunk": ("opt_style_services_pulse", "opt_style_activity_live", "opt_style_stats_countup"),
    "matrix": ("opt_style_activity_live", "opt_style_stats_countup", "opt_style_news_ticker"),
    "futuristic": ("opt_style_progress_odometer", "opt_style_progress_chart", "opt_style_stats_countup"),
    "neowave": ("opt_style_countdown_flip", "opt_style_services_pulse", "opt_style_continue_ambient"),
    "plex": ("opt_style_continue_ambient", "opt_style_added_deck", "opt_style_wall_kenburns"),
    "nostromo": ("opt_style_services_pulse", "opt_style_countdown_flip", "opt_style_activity_live"),
    "alien": ("opt_style_services_pulse", "opt_style_stats_countup"),
    "galaxy": ("opt_style_wall_kenburns", "opt_style_progress_odometer"),
    "wizard": ("opt_style_daily_liquid", "opt_style_added_deck", "opt_style_clock_analog"),
    "middleearth": ("opt_style_daily_liquid", "opt_style_wall_kenburns", "opt_style_clock_analog"),
    "cozy": ("opt_style_continue_ambient", "opt_style_clock_analog", "opt_style_daily_liquid"),
    "christmas": ("opt_style_countdown_flip", "opt_style_continue_ambient", "opt_style_added_deck"),
    "vhs": ("opt_style_wall_kenburns", "opt_style_countdown_flip", "opt_style_news_ticker"),
    "disco": ("opt_style_wall_kenburns", "opt_style_progress_odometer", "opt_style_activity_live"),
    "sincity": ("opt_style_wall_kenburns", "opt_style_continue_ambient", "opt_style_news_ticker"),
    "comic": ("opt_style_added_deck", "opt_style_progress_odometer", "opt_style_news_ticker"),
    "manga": ("opt_style_added_deck", "opt_style_progress_odometer", "opt_style_activity_live"),
    "heroes": ("opt_style_progress_odometer", "opt_style_services_pulse", "opt_style_added_deck"),
    "cartoon": ("opt_style_daily_liquid", "opt_style_added_deck", "opt_style_progress_odometer"),
    "horror": ("opt_style_services_pulse", "opt_style_continue_ambient"),
    "halloween": ("opt_style_countdown_flip", "opt_style_daily_liquid", "opt_style_continue_ambient"),
    "upsidedown": ("opt_style_services_pulse", "opt_style_continue_ambient", "opt_style_activity_live"),
    "desert": ("opt_style_wall_kenburns", "opt_style_clock_analog"),
    "minimal": ("opt_style_clock_analog", "opt_style_stats_countup", "opt_style_progress_chart"),
    "nova": ("opt_style_progress_odometer", "opt_style_continue_ambient", "opt_style_news_ticker"),
}
# a look for a widget sold in the shop comes with that widget
LOOK_NEEDS = {
    "opt_style_clock_analog": "widget_clock",
    "opt_style_countdown_flip": "widget_countdown",
    "opt_style_wall_kenburns": "widget_poster_wall",
}


def with_widgets(looks: tuple[str, ...] | list[str]) -> list[str]:
    """The looks, each preceded by the widget it needs when that widget is sold."""
    out: list[str] = []
    for look in looks:
        if look in LOOK_NEEDS:
            out.append(LOOK_NEEDS[look])
        out.append(look)
    return out


def theme_looks(theme: str) -> list[str]:
    """The sold products a universe theme's own looks need (its notification style and entrance, ambience,
    celebration and level-up): the interface alone shows the free defaults instead, its theme pack has them."""
    definition = theme_definition(theme)
    wanted = {
        ("notification_style", "style", definition.get("notification", {}).get("style")),
        ("notification_animation", "animation", definition.get("notification", {}).get("animation")),
        ("ambient", "ambient", definition.get("background", {}).get("ambient")),
        ("effect", "effect", definition.get("motion", {}).get("celebration")),
        ("level_up", "animation", definition.get("motion", {}).get("levelUp")),
    }
    found: list[str] = []
    for kind, field, value in wanted:
        keys = [p["key"] for p in SHOP if p["type"] == kind and value and p["payload"].get(field) == value]
        found.extend(keys[:1])
    return sorted(found)


for theme, items in UNIVERSES.items():
    en, fr, _, _ = THEME_TEXT[theme]
    extras = [
        item
        for item in (
            *UNIVERSE_EXTRAS.get(theme, ()),
            *theme_looks(theme),
            *with_widgets(UNIVERSE_LOOKS.get(theme, ())),  # 027 (#30): its dashboard looks
        )
        if item not in items
    ]
    contents = [f"theme_{theme}", *[item for item in items if item], *dict.fromkeys(extras)]
    level = max(THEME_RARITY[theme][2] or 0, 8)
    _p(f"ultimate_{theme}", "bundle", None, "legendary", f"{en} theme pack", f"Pack de thème {fr}",
       f"The whole {en} theme: its interface and everything that goes with it — animated background, notifications, celebration, level-up, banner, frame, name style, level badge, its badges and its dashboard looks.",
       f"Tout le thème {fr} : son interface et tout ce qui va avec — fond animé, notifications, célébration, passage de niveau, bannière, cadre, style de nom, badge de niveau, ses badges et ses visuels de tableau de bord.",
       {"products": contents}, collection="ultimate", icon="crown", featured=theme in ("wizard", "cyberpunk"),
       level=level + 4, supply=5)  # fmt: skip

for key, en, fr, about_en, about_fr, contents, rarity, level in (
    ("pack_starter", "Starter pack", "Pack Découverte",
     "Sticky-note notifications, the drop animation, the Pioneer badge and a mint palette.",
     "Notifications post-it, l'animation de chute, le badge Pionnier et une palette menthe.",
     ["notif_paper", "notif_drop", "badge_pioneer", "palette_mint"], "common", None),
    ("pack_neon_nights", "Neon nights pack", "Pack Nuits néon",
     "Neon notifications, neon rain, a neon frame and shooting stars.",
     "Notifications néon, pluie néon, cadre néon et étoiles filantes.",
     ["notif_neon", "ambient_rain", "frame_neon", "effect_aurora"], "epic", 5),
    ("pack_cinephile", "Cinephile pack", "Pack Cinéphile",
     "The poster wall widget and its travelling camera, the ambient light of « Continue », the Cinephile title, the Binge-watcher badge and the film backdrop banner.",
     "Le widget mur d'affiches et son travelling, la lumière d'ambiance de « Continuer », le titre Cinéphile, le badge Binge-watcher et la bannière de film.",
     ["widget_poster_wall", "opt_style_wall_kenburns", "opt_style_continue_ambient", "title_cinephile",
      "badge_binge_watcher", "backdrop_banner"], "legendary", 10),
    ("pack_profile_star", "Star profile pack", "Pack Profil star",
     "The starfield banner and its animated version, the golden frame and the royal name style.",
     "La bannière étoilée et sa version animée, le cadre doré et le style de nom royal.",
     ["banner_starfield", "bg_starfield", "frame_gold", "name_royal"], "legendary", 12),
    ("pack_notifications", "Notification designer pack", "Pack Designer de notifications",
     "Nine notification styles and six animations.",
     "Neuf styles et six animations de notifications.",
     ["notif_glass", "notif_comic", "notif_terminal", "notif_pixel", "notif_parchment", "notif_hologram",
      "notif_flip", "notif_glitch", "notif_spiral", "notif_slam", "notif_square", "notif_cloud", "notif_ticket",
      "notif_melt", "notif_iris"], "epic", 6),
    ("pack_ambiences", "Ambience pack", "Pack Ambiances",
     "Snowfall, fireflies, autumn leaves, sakura petals and floating hearts behind the portal.",
     "Neige, lucioles, feuilles d'automne, pétales de sakura et cœurs flottants derrière le portail.",
     ["ambient_snow", "ambient_fireflies", "ambient_leaves", "ambient_petals", "ambient_hearts"], "rare", 3),
    ("pack_palettes", "Painter's pack", "Pack Peintre",
     "Six palettes to repaint any theme.",
     "Six palettes pour repeindre n'importe quel thème.",
     ["palette_sunset", "palette_candy", "palette_lagoon", "palette_ice", "palette_lavender",
      "palette_bubblegum"], "rare", None),
    ("pack_celebrations", "Party pack", "Pack Fête",
     "Confetti, hearts, bubbles, petals and a coin shower for every reward.",
     "Confettis, cœurs, bulles, pétales et pluie de pièces pour chaque récompense.",
     ["effect_confetti", "effect_hearts", "effect_bubbles", "effect_petals", "effect_coins"], "epic", 6),
    ("pack_statistics", "Statistician pack", "Pack Statisticien",
     "Every Media statistic, every setting of « My statistics », its counting figures and the curves of « My progression ».",
     "Toutes les statistiques Médias, toutes les options de « Mes statistiques », ses chiffres animés et les courbes de « Ma progression ».",
     ["stat_when", "stat_genres", "stat_people", "stat_decades", "stat_records", "stat_box_office",
      "stat_platforms", "opt_stats_area", "opt_stats_donut", "opt_stats_top", "opt_stats_year",
      "opt_stats_all", "opt_stats_server", "opt_style_stats_countup", "opt_style_progress_chart"], "legendary", 8),
    ("pack_dashboard", "Dashboard pack", "Pack Tableau de bord",
     "The top of the week, upcoming releases, coming-soon and next releases widgets.",
     "Les widgets top de la semaine, sorties à venir, demandes bientôt là et prochaines sorties.",
     ["widget_media_top", "widget_media_upcoming", "widget_my_soon", "widget_next_releases"], "epic", 4),
    ("pack_animated_profile", "Living profile pack", "Pack Profil vivant",
     "An animated aurora banner, the hologram frame, the rainbow name and the nebula banner.",
     "Une bannière animée aurore boréale, le cadre hologramme, le nom arc-en-ciel et la bannière nébuleuse.",
     ["bg_aurora", "frame_hologram", "name_rainbow", "banner_nebula"], "legendary", 15),
    # 027: level badges, level-up moments, elements, retro, comics, cosmos
    ("pack_level_badges", "Level badge pack", "Pack Badges de niveau",
     "Five looks for your level badge: pixel, neon, crest, gem and hologram.",
     "Cinq apparences pour votre badge de niveau : pixel, néon, blason, gemme et hologramme.",
     ["level_pixel", "level_neon", "level_crest", "level_gem", "level_hologram"], "epic", 5),
    ("pack_level_ups", "Level-up pack", "Pack Passages de niveau",
     "Four ways to celebrate a new level: arcade, cosmic, comic book and the four elements.",
     "Quatre façons de fêter un nouveau niveau : arcade, cosmique, bande dessinée et quatre éléments.",
     ["levelup_arcade", "levelup_cosmic", "levelup_comic", "levelup_elements"], "epic", 8),
    ("pack_elements", "Four elements pack", "Pack Quatre éléments",
     "Air, water, earth and fire notifications, the elements level badge, the waterbender and airbender badges, wind and tide.",
     "Notifications air, eau, terre et feu, le badge de niveau éléments, les badges maître de l'eau et de l'air, vent et marée.",
     ["notif_air", "notif_water", "notif_earth", "notif_fire", "level_elements", "levelup_elements",
      "badge_waterbender", "badge_airbender", "ambient_wind", "ambient_tide",
      "level_blaze", "level_aqua", "levelup_phoenix", "levelup_tidalwave"], "legendary", 15),
    ("pack_retro", "Retro pack", "Pack Rétro",
     "VHS notifications and ambience, pixel and VHS level badges, the arcade level-up, an 8-bit sky, two retro badges and a countdown on flip digits.",
     "Notifications et ambiance VHS, badges de niveau pixel et VHS, passage de niveau arcade, ciel 8 bits, deux badges rétro et un compte à rebours à palettes.",
     ["notif_vhs", "ambient_vhs", "level_pixel", "level_vhs", "levelup_arcade", "ambient_pixelsky",
      "badge_rewinder", "badge_8bit_hero", "badge_root", "widget_countdown", "opt_style_countdown_flip"], "epic", 6),
    ("pack_comics", "Comics pack", "Pack Comics",
     "KAPOW! notifications and level badge, the comic book level-up, manga panels and the POW banner.",
     "Notifications et badge de niveau KAPOW !, passage de niveau BD, cases de manga et bannière POW.",
     ["notif_kapow", "level_kapow", "levelup_comic", "notif_manga", "banner_pow"], "epic", 6),
    ("pack_cosmos", "Cosmos pack", "Pack Cosmos",
     "Black hole and portal notifications and level badges, the cosmic level-up and the space saga look.",
     "Notifications et badges de niveau trou noir et portail, passage de niveau cosmique et style saga spatiale.",
     ["notif_blackhole", "notif_portal", "level_blackhole", "level_portal", "levelup_cosmic", "notif_saga",
      "level_galaxy", "notif_galaxy", "frame_starlit", "levelup_supernova"],
     "legendary", 16),
    ("pack_vhs", "VHS pack", "Pack VHS",
     "Everything for the video store: VHS and bad-tracking notifications, the VHS ambience, banner, frame and name, the VHS and cassette level badges, the VHS level-up, the rewind celebration, two badges and the poster wall with its travelling camera.",
     "Tout pour le vidéoclub : notifications VHS et mauvais tracking, ambiance, bannière, cadre et nom VHS, badges de niveau VHS et cassette, passage de niveau VHS, célébration rembobinage, deux badges et le mur d'affiches avec son travelling.",
     ["notif_vhs", "notif_tracking", "ambient_vhs", "banner_vhs", "frame_vhs", "name_vhs", "level_vhs",
      "level_cassette", "levelup_vhs", "effect_rewind", "badge_rewinder", "badge_be_kind_rewind",
      "widget_poster_wall", "opt_style_wall_kenburns"], "epic", 6),
    ("pack_nova", "Nova pack", "Pack Nova",
     "A phone's look: island and morph notifications, the app-icon level badge, the sheet level-up, colour mesh, activity rings (and the odometer of « My progression »), the gradient name, bloom and bokeh.",
     "Le style d'un téléphone : notifications îlot et métamorphose, badge de niveau icône d'app, passage de niveau en volet, dégradé fluide, anneaux d'activité (et le compteur animé de « Ma progression »), nom en dégradé, éclosion et bokeh.",
     ["notif_island", "notif_morph", "level_squircle", "levelup_nova", "banner_mesh", "frame_rings", "name_nova",
      "effect_bloom", "ambient_bokeh", "opt_style_progress_odometer"], "epic", 6),
    # 027 (#30): packs of dashboard looks and widgets
    ("pack_living_dashboard", "Living dashboard pack", "Pack Tableau de bord vivant",
     "The dashboard comes alive: heartbeat services, the progression odometer, liquid objectives, the live community feed, the news carousel and counting statistics.",
     "Le tableau de bord prend vie : services qui battent, compteur de progression, objectifs liquides, fil communautaire en direct, carrousel d'actualités et statistiques animées.",
     ["opt_style_services_pulse", "opt_style_progress_odometer", "opt_style_daily_liquid", "opt_style_activity_live",
      "opt_style_news_ticker", "opt_style_stats_countup"], "epic", 4),
    ("pack_clockmaker", "Clockmaker pack", "Pack Horloger",
     "The clock with its analog face and the countdown with its flip digits.",
     "L'horloge et son cadran analogique, le compte à rebours et ses chiffres à palettes.",
     ["widget_clock", "opt_style_clock_analog", "widget_countdown", "opt_style_countdown_flip"], "rare", None),
    ("pack_dark_room", "Dark room pack", "Pack Salle obscure",
     "The cinema on your dashboard: ambient light behind « Continue », card decks for what is new, released and requested, the poster wall with its travelling camera and the living wall.",
     "Le cinéma sur votre tableau de bord : lumière d'ambiance pour « Continuer », piles de cartes pour les ajouts, sorties et demandes, le mur d'affiches et son travelling, et le mur vivant.",
     ["opt_style_continue_ambient", "opt_style_added_deck", "opt_style_releases_deck", "opt_style_requested_deck",
      "widget_poster_wall", "opt_style_wall_kenburns", "widget_living_wall"], "epic", 6),
    ("pack_organizer", "Organizer pack", "Pack Organisation",
     "Everything to lay out a dashboard: separators with a label, sticky notes, progress bars and columns.",
     "Tout pour organiser un tableau de bord : séparateurs avec titre, post-it, barres et colonnes de progression.",
     ["widget_separator", "widget_note", "widget_progress", "widget_progress_vertical"], "rare", None),
    ("pack_explorer", "Explorer pack", "Pack Explorateur",
     "The widgets to discover: next releases with their countdown, a year ago and the living wall.",
     "Les widgets pour découvrir : prochaines sorties et leur décompte, il y a un an et le mur vivant.",
     ["widget_next_releases", "widget_on_this_day", "widget_living_wall"], "epic", 4),
    # #74: the premium ambiences gathered by mood — each pack worth about 20 % less than its contents
    ("pack_cocooning", "Cocooning pack", "Pack Cocooning",
     "Stay in where it is warm: candlelight, by the fire, a knitted blanket, honey, warm steam, soft fairy lights, an amber glow and rain on the window.",
     "Bien au chaud : lueur de bougies, coin du feu, tricot douillet, miel, vapeur chaude, lumières douces, lueur ambrée et pluie à la fenêtre.",
     ["ambient_candlelight", "ambient_hearth", "ambient_knit", "ambient_honey", "ambient_steam",
      "ambient_fairybokeh", "ambient_amberglow", "ambient_windowrain"], "epic", 6),
    ("pack_paint_studio", "Paint studio pack", "Pack Atelier de peinture",
     "Warm paints that mix: stirred paint, an acrylic pour, warm watercolour, marbled paper and warm silk.",
     "Des peintures chaudes qui se mêlent : peinture mêlée, coulée acrylique, aquarelle chaude, papier marbré et soie chaude.",
     ["ambient_paintmix", "ambient_acrylicpour", "ambient_watercolor", "ambient_marbling", "ambient_warmsilk"],
     "epic", 6),
    ("pack_pop_art", "Pop art pack", "Pack Pop art",
     "Colours straight from the tube: pop paint, pour, watercolour and marbling, ribbons of paint, thick glossy paint and the lava lamp.",
     "Des couleurs sorties du tube : peinture, coulée, aquarelle et marbré pop, rubans de peinture, peinture épaisse et la lampe à lave.",
     ["ambient_poppaint", "ambient_poppour", "ambient_popwatercolor", "ambient_popmarbling", "ambient_paintribbon",
      "ambient_impasto", "ambient_lavalamp"], "epic", 10),
    ("pack_pixel_art", "Pixel art pack", "Pack Pixel art",
     "Animated pixel art: a campfire, a sunset beach, hot-air balloons and the 8-bit sky, with the pixel level badge and the arcade level-up.",
     "Du pixel art animé : feu de camp, plage au couchant, montgolfières et ciel 8 bits, avec le badge de niveau pixel et le passage de niveau arcade.",
     ["ambient_pixelcamp", "ambient_pixelbeach", "ambient_pixelballoons", "ambient_pixelsky", "level_pixel",
      "levelup_arcade"], "epic", 6),
    ("pack_christmas_eve", "Christmas eve pack", "Pack Veillée de Noël",
     "String lights, Christmas night, by the fire, candlelight and snowfall.",
     "Guirlandes, nuit de Noël, coin du feu, lueur de bougies et neige.",
     ["ambient_garland", "ambient_christmasnight", "ambient_hearth", "ambient_candlelight", "ambient_snow"],
     "epic", 6),
    ("pack_chills", "Chills pack", "Pack Frissons",
     "For the brave: a haunting, the darkness and its eyes, a lost signal, bats and red veins.",
     "Pour les courageux : hantise, ténèbres et leurs yeux, signal perdu, chauves-souris et veines rouges.",
     ["ambient_haunted", "ambient_darkness", "ambient_lostsignal", "ambient_bats", "ambient_veins"], "epic", 8),
    ("pack_wild_elements", "Wild elements pack", "Pack Éléments déchaînés",
     "Nature unleashed: a thunderstorm, a downpour, blizzards by day and night, a desert storm, a firestorm, the inferno and the volcano.",
     "La nature déchaînée : orage, averse, blizzards de jour et de nuit, tempête du désert, tempête de feu, brasier et volcan.",
     ["ambient_thunderstorm", "ambient_downpour", "ambient_blizzard", "ambient_whiteout", "ambient_sandstorm",
      "ambient_firestorm", "ambient_inferno", "ambient_volcano"], "epic", 10),
    ("pack_great_outdoors", "Great outdoors pack", "Pack Grand air",
     "Out in the open: the living forest, a summer field, an autumn lane, golden hour, lanterns over the lake, soap bubbles and the reef.",
     "Au grand air : forêt vivante, champ d'été, allée d'automne, heure dorée, lanternes sur le lac, bulles de savon et le récif.",
     ["ambient_forest", "ambient_summerfield", "ambient_autumnlane", "ambient_goldenhour", "ambient_skylanterns",
      "ambient_soapbubbles", "ambient_reef"], "epic", 8),
    ("pack_deep_space", "Deep space pack", "Pack Espace lointain",
     "Beyond the sky: deep space, the black hole, polar lights, a plasma storm and the moving mesh networks.",
     "Au-delà du ciel : espace profond, trou noir, lumières polaires, tempête de plasma et réseaux maillés.",
     ["ambient_cosmos", "ambient_blackhole", "ambient_polar", "ambient_plasma", "ambient_meshwave", "ambient_mesh"],
     "epic", 12),
    ("pack_living_badges", "Living level badges pack", "Pack Badges vivants",
     "Every level badge drawn by the graphics chip: flames, voltage, water, magma, ice, galaxy, gold, acid, holo foil, runes, digital rain, sakura, shadow, candy, aurora and plasma.",
     "Tous les badges de niveau dessinés par la puce graphique : flammes, haute tension, eau, magma, glace, galaxie, or, acide, holographique, runes, pluie numérique, sakura, ombre, bonbon, aurore et plasma.",
     ["level_blaze", "level_voltage", "level_aqua", "level_magma", "level_glacier", "level_galaxy", "level_aurum", "level_toxic", "level_holo", "level_runes", "level_matrix", "level_sakura", "level_shadow", "level_candy", "level_aurora", "level_plasma", "level_chrono"], "epic", 10),
    # #78: one pack per world drawn by the GPU, and one per kind
    ("pack_hd_blaze", "Blaze HD pack", "Pack Brasier HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge, level-up and animated banner.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge, passage de niveau et bannière animée.",
     ["level_blaze", "notif_blaze", "frame_pyre", "title_firebrand", "badge_phoenix_feather", "levelup_phoenix", "bg_inferno", "notif_ignite", "name_nameblaze", "effect_rebirth"], "epic", 10),
    ("pack_hd_voltage", "High voltage HD pack", "Pack Haute tension HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge, level-up and animated banner.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge, passage de niveau et bannière animée.",
     ["level_voltage", "notif_voltage", "frame_tesla", "title_stormcaller", "badge_thunderbolt", "levelup_thunderstrike", "bg_thunderstorm", "notif_surge", "name_namevolt", "effect_stormstrike"], "epic", 10),
    ("pack_hd_ocean", "Ocean HD pack", "Pack Océan HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge, level-up and animated banner.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge, passage de niveau et bannière animée.",
     ["level_aqua", "notif_aqua", "frame_abyssal", "title_deep_diver", "badge_trident", "levelup_tidalwave", "bg_reef", "notif_splash"], "epic", 10),
    ("pack_hd_volcano", "Volcano HD pack", "Pack Volcan HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge and animated banner.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge et bannière animée.",
     ["level_magma", "notif_magma", "frame_obsidian", "title_volcano_heart", "badge_lava_stone", "bg_volcano"], "epic", 10),
    ("pack_hd_ice", "Ice HD pack", "Pack Glace HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge and animated banner.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge et bannière animée.",
     ["level_glacier", "notif_glacier", "frame_frostcrown", "title_frostborn", "badge_snowflake", "bg_whiteout", "notif_frostbite", "name_namefrost"], "epic", 10),
    ("pack_hd_cosmos", "Cosmos HD pack", "Pack Cosmos HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge, level-up and animated banner.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge, passage de niveau et bannière animée.",
     ["level_galaxy", "notif_galaxy", "frame_starlit", "title_stargazer", "badge_comet", "levelup_supernova", "bg_blackhole", "notif_stardust", "name_namegalaxy", "effect_nova"], "epic", 10),
    ("pack_hd_treasure", "Treasure HD pack", "Pack Trésor HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge, level-up and animated banner.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge, passage de niveau et bannière animée.",
     ["level_aurum", "notif_aurum", "frame_regalia", "title_golden_one", "badge_golden_crown", "levelup_goldrush", "bg_liquidmetal", "name_namegold", "effect_goldshower"], "epic", 10),
    ("pack_hd_toxic", "Toxic HD pack", "Pack Toxique HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge.",
     ["level_toxic", "notif_toxic", "frame_biohazard", "title_mad_scientist", "badge_radioactive"], "epic", 10),
    ("pack_hd_cyber", "Cyber HD pack", "Pack Cyber HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge and animated banner.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge et bannière animée.",
     ["level_holo", "notif_holo", "frame_prism", "title_netrunner", "badge_chrome_chip", "bg_neoncity", "level_matrix", "notif_matrix", "frame_mainframe", "title_root_access", "badge_backdoor", "bg_matrix", "notif_decrypt"], "epic", 10),
    ("pack_hd_arcane", "Arcana HD pack", "Pack Arcanes HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge, level-up.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge, passage de niveau.",
     ["level_runes", "notif_runes", "frame_sigil", "title_runemaster", "badge_grimoire", "levelup_arcanum", "notif_hex", "effect_arcana"], "epic", 10),
    ("pack_hd_sakura", "Sakura HD pack", "Pack Sakura HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge, level-up and animated banner.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge, passage de niveau et bannière animée.",
     ["level_sakura", "notif_sakura", "frame_hanami", "title_spring_spirit", "badge_blossom", "levelup_sakurastorm", "bg_goldenhour", "notif_petalfall", "name_namesakura", "effect_petalstorm"], "epic", 10),
    ("pack_hd_shadow", "Shadows HD pack", "Pack Ombres HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge and animated banner.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge et bannière animée.",
     ["level_shadow", "notif_shadow", "frame_wraith", "title_shadow_walker", "badge_watcher", "bg_darkness", "notif_eclipse", "name_nameshadow"], "epic", 10),
    ("pack_hd_candy", "Candy HD pack", "Pack Bonbons HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge and animated banner.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge et bannière animée.",
     ["level_candy", "notif_candy", "frame_sweetie", "title_sugar_rush", "badge_lollipop", "bg_lavalamp"], "epic", 10),
    ("pack_hd_aurora", "Aurora HD pack", "Pack Aurore HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge, level-up and animated banner.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge, passage de niveau et bannière animée.",
     ["level_aurora", "notif_aurora", "frame_borealis", "title_northern_light", "badge_north_star", "levelup_aurorasky", "bg_polar", "name_nameaurora", "effect_skyveil"], "epic", 10),
    ("pack_hd_plasma", "Plasma HD pack", "Pack Plasma HD",
     "Everything of this world, drawn by the graphics chip: level badge, notifications, avatar frame, title and badge and animated banner.",
     "Tout cet univers, dessiné par la puce graphique : badge de niveau, notifications, cadre d'avatar, titre et badge et bannière animée.",
     ["level_plasma", "notif_plasma", "frame_corona", "title_plasma_core", "badge_atom", "bg_plasma", "name_nameplasma"], "epic", 10),
    ("pack_hd_time_portal", "Time portal HD pack", "Pack Portail temporel HD",
     "Step through time: the time rift level badge, time portal notifications and their time warp, the time gate frame, the time traveller title, the hourglass badge, the « out of time » name, the time portal level-up and the time rift celebration.",
     "Traversez le temps : badge de niveau faille temporelle, notifications portail temporel et leur distorsion, cadre porte du temps, titre voyageur temporel, badge sablier, nom « hors du temps », passage de niveau portail temporel et célébration faille temporelle.",
     ["level_chrono", "notif_chrono", "frame_chronogate", "title_time_traveller", "badge_hourglass", "levelup_timeportal",
      "notif_warp", "name_namechrono", "effect_timerift"],
     "legendary", 12),
    ("pack_hd_animations", "HD notification animations pack", "Pack Animations de notification HD",
     "Every notification animation drawn by the graphics chip: each bursts as they arrive and leave.",
     "Toutes les animations de notification dessinées par la puce graphique : chacune éclate à leur arrivée et à leur départ.",
     ["notif_ignite", "notif_surge", "notif_splash", "notif_frostbite", "notif_stardust", "notif_hex", "notif_decrypt", "notif_petalfall", "notif_eclipse", "notif_warp"], "epic", 10),
    ("pack_hd_celebrations", "HD celebrations pack", "Pack Célébrations HD",
     "Every reward celebration drawn by the graphics chip, over the whole screen.",
     "Toutes les célébrations de récompense dessinées par la puce graphique, sur tout l'écran.",
     ["effect_nova", "effect_goldshower", "effect_petalstorm", "effect_rebirth", "effect_stormstrike", "effect_skyveil", "effect_arcana", "effect_timerift"], "epic", 10),
    ("pack_hd_names", "HD name styles pack", "Pack Styles de nom HD",
     "Every name style drawn by the graphics chip: an aura around your name.",
     "Tous les styles de nom dessinés par la puce graphique : une aura autour de votre nom.",
     ["name_nameblaze", "name_namevolt", "name_namefrost", "name_namegalaxy", "name_namegold", "name_nameshadow", "name_namesakura", "name_nameplasma", "name_nameaurora", "name_namechrono"], "epic", 10),
    ("pack_hd_notifications", "HD notifications pack", "Pack Notifications HD",
     "Every notification style drawn by the graphics chip.", "Tous les styles de notification dessinés par la puce graphique.",
     ["notif_blaze", "notif_voltage", "notif_aqua", "notif_magma", "notif_glacier", "notif_galaxy", "notif_aurum", "notif_toxic", "notif_holo", "notif_runes", "notif_matrix", "notif_sakura", "notif_shadow", "notif_candy", "notif_aurora", "notif_plasma", "notif_chrono"], "epic", 10),
    ("pack_hd_frames", "HD avatar frames pack", "Pack Cadres HD",
     "Every avatar frame drawn by the graphics chip, in shapes of their own.", "Tous les cadres d'avatar dessinés par la puce graphique, chacun sa forme.",
     ["frame_pyre", "frame_tesla", "frame_abyssal", "frame_obsidian", "frame_frostcrown", "frame_starlit", "frame_regalia", "frame_biohazard", "frame_prism", "frame_sigil", "frame_mainframe", "frame_hanami", "frame_wraith", "frame_sweetie", "frame_borealis", "frame_corona", "frame_chronogate"], "epic", 10),
    ("pack_hd_level_ups", "HD level-ups pack", "Pack Passages de niveau HD",
     "Every full-stage level-up drawn by the graphics chip.", "Tous les passages de niveau plein écran dessinés par la puce graphique.",
     ["levelup_phoenix", "levelup_thunderstrike", "levelup_tidalwave", "levelup_supernova", "levelup_goldrush", "levelup_arcanum", "levelup_sakurastorm", "levelup_aurorasky", "levelup_timeportal", "levelup_rift"], "epic", 10),
    ("pack_hd_titles", "HD titles and badges pack", "Pack Titres et badges HD",
     "Every title and badge drawn by the graphics chip.", "Tous les titres et badges dessinés par la puce graphique.",
     ["title_firebrand", "title_stormcaller", "title_deep_diver", "title_volcano_heart", "title_frostborn", "title_stargazer", "title_golden_one", "title_mad_scientist", "title_netrunner", "title_runemaster", "title_root_access", "title_spring_spirit", "title_shadow_walker", "title_sugar_rush", "title_northern_light", "title_plasma_core", "badge_phoenix_feather", "badge_thunderbolt", "badge_trident", "badge_lava_stone", "badge_snowflake", "badge_comet", "badge_golden_crown", "badge_radioactive", "badge_chrome_chip", "badge_grimoire", "badge_backdoor", "badge_blossom", "badge_watcher", "badge_lollipop", "badge_north_star", "badge_atom", "title_time_traveller", "badge_hourglass"], "epic", 10),

    ("pack_city_lights", "City lights pack", "Pack Lumières de la ville",
     "The city at night: the neon city, digital rain, liquid metal and fireworks.",
     "La ville la nuit : cité néon, pluie numérique, métal liquide et feu d'artifice.",
     ["ambient_neoncity", "ambient_matrix", "ambient_liquidmetal", "ambient_fireworks"], "epic", 8),
):  # fmt: skip
    _p(key, "bundle", None, rarity, en, fr, about_en, about_fr, {"products": contents},
       collection="packs", icon="shop", featured=key == "pack_cinephile", level=level)  # fmt: skip

# #53: for those who give the most — the server's whole picture in one pack; it asks what its contents ask
# (the same contribution minimum, the highest level), never more
_p("pack_server_room", "bundle", None, "legendary", "Server room pack", "Pack Salle des serveurs",
   "For the community's pillars: the « Server », « Containers » and « Downloads » widgets and every series of « Chart » (temperatures, network, storage over time, a week of history).",
   "Pour les piliers de la communauté : les widgets « Serveur », « Conteneurs » et « Téléchargements » et toutes les séries du « Graphique » (températures, réseau, stockage dans le temps, une semaine d'historique).",
   {"products": ["widget_server", "widget_containers", "widget_downloads", "opt_chart_network",
                 "opt_chart_temperature", "opt_chart_storage", "opt_chart_week"]},
   collection="packs", icon="server", level=15, contribution=30)  # fmt: skip

# #79: no animated background behind a profile (the portal's ambience is each member's own choice): the
# profile backgrounds are retired — their animated banners take their place, in every pack that held one
_BACKGROUNDS = [product["key"] for product in SHOP if product["type"] == "profile_background"]
_KEYS = {product["key"] for product in SHOP}
for product in SHOP:
    if product["type"] == "bundle":
        held: list[str] = []
        for item in product["payload"]["products"]:
            if item.startswith("bg_"):
                item = "banner_live_" + item[3:]
                if item not in _KEYS:
                    continue
            if item not in held:
                held.append(item)
        product["payload"]["products"] = held
SHOP[:] = [product for product in SHOP if product["type"] != "profile_background"]
RETIRED = (
    *RETIRED,
    *(f"bg_{v.replace('-', '_')}" for v in (*LIVE_BANNERS, *HD_LIVE_BANNERS)),
    "bg_night_owl",
)

# #81: the seasons' looks — each season its ambience (and its animated banner), celebration, palette, name
# style, banner, title, badge (mostly common), its frame, level badge and notifications (rare), and its
# looks drawn by the graphics chip (epic, a legendary for three of them). Designs of their own, never one
# already sold.
SEASONAL: tuple[tuple[str, tuple[tuple[Any, ...], ...]], ...] = (
    ("halloween", (
        ("ambient", "cobwebs", "Cobwebs", "Toiles d'araignée", 300, None,
         "Spiders lowering themselves on their threads, webs in the corners.",
         "Des araignées qui descendent au bout de leur fil, des toiles dans les coins."),
        ("live", "cobwebs", "Cobwebs", "toiles d'araignée", 350, None, "", ""),
        ("effect", "candy", "Candy shower", "Pluie de bonbons", 250, None,
         "Wrapped sweets bursting out of the reward.", "Des bonbons emballés qui jaillissent de la récompense."),
        ("palette", "pumpkinspice", "Pumpkin spice", "Épices de citrouille", 200, None,
         "Pumpkin orange and cinnamon over the theme.", "Orange citrouille et cannelle sur le thème."),
        ("name", "slime", "Slime", "gluant", 300, None,
         "A name dripping with green slime.", "Un nom qui dégouline de bave verte."),
        ("banner", "graveyard", "Graveyard", "Cimetière", 300, None,
         "Crooked tombstones under a full moon.", "Des tombes de travers sous la pleine lune."),
        ("title", "Ghost hunter", "Titre : Chasseur de fantômes", "glitch", 150, None, "", ""),
        ("badge", "Trick or treat", "Badge Bonbon ou sort", "candy", "pulse", 200, None, "", ""),
        ("frame", "cauldron", "Cauldron", "Chaudron", 650, 4,
         "A witch's cauldron bubbling green around your avatar.",
         "Le chaudron d'une sorcière qui bouillonne en vert autour de votre avatar."),
        ("level", "jackolantern", "Jack-o'-lantern", "Citrouille-lanterne", 700, 4,
         "A carved pumpkin lit from inside.", "Une citrouille sculptée éclairée de l'intérieur."),
        ("notif", "tombstone", "Tombstone", "Pierre tombale", 650, 4,
         "Notifications carved in old stone.", "Des notifications gravées dans la vieille pierre."),
        ("hdframe", "spectre", "Spectre", "Spectre", 1200, 8,
         "Ghostly wisps rising around your avatar, drawn by the graphics chip.",
         "Des volutes spectrales qui s'élèvent autour de votre avatar, dessinées par la puce graphique."),
        ("hdname", "spectre", "Spectre", "spectral", 1100, 8, "", ""),
        ("hdlevel", "spectre", "Spectre", "Spectre", 1700, 12,
         "Your level haunted by a ghostly flame, drawn by the graphics chip.",
         "Votre niveau hanté par une flamme spectrale, dessinée par la puce graphique."),
    )),
    ("christmas", (
        ("ambient", "ornaments", "Ornaments", "Boules de Noël", 300, None,
         "Shiny baubles swinging at the top of the screen.", "Des boules brillantes qui se balancent en haut de l'écran."),
        ("live", "ornaments", "Ornaments", "boules de Noël", 350, None, "", ""),
        ("effect", "gifts", "Gift burst", "Pluie de cadeaux", 250, None,
         "Wrapped presents bursting out of the reward.", "Des paquets cadeaux qui jaillissent de la récompense."),
        ("palette", "evergreen", "Evergreen", "Sapin", 200, None,
         "Fir green and berry red over the theme.", "Vert sapin et rouge baie sur le thème."),
        ("name", "gingerbread", "Gingerbread", "pain d'épices", 300, None,
         "A name baked like gingerbread, piped with icing.", "Un nom cuit comme un pain d'épices, souligné de glaçage."),
        ("banner", "wrapping", "Wrapping paper", "Papier cadeau", 300, None,
         "Red paper with stars, tied with a golden ribbon.", "Du papier rouge étoilé noué d'un ruban doré."),
        ("title", "Santa's elf", "Titre : Lutin du Père Noël", "frost", 150, None, "", ""),
        ("badge", "Christmas tree", "Badge Sapin de Noël", "tree", "shimmer", 200, None, "", ""),
        ("frame", "candycane", "Candy cane", "Sucre d'orge", 650, 4,
         "Red and white stripes winding around your avatar.", "Des rayures rouges et blanches qui s'enroulent autour de votre avatar."),
        ("level", "bauble", "Bauble", "Boule de Noël", 700, 4,
         "Your level in a shiny Christmas bauble.", "Votre niveau dans une boule de Noël brillante."),
        ("notif", "giftwrap", "Gift wrap", "Paquet cadeau", 650, 4,
         "Notifications wrapped like presents.", "Des notifications emballées comme des cadeaux."),
        ("hdname", "tinsel", "Tinsel", "guirlande", 1100, 8, "", ""),
        ("hdlevel", "tinsel", "Tinsel", "Guirlande", 1200, 8,
         "Your level wrapped in sparkling tinsel, drawn by the graphics chip.",
         "Votre niveau enveloppé d'une guirlande scintillante, dessinée par la puce graphique."),
        ("hdframe", "tinsel", "Tinsel", "Guirlande", 1700, 12,
         "Golden and green tinsel sparkling around your avatar, drawn by the graphics chip.",
         "Une guirlande dorée et verte qui scintille autour de votre avatar, dessinée par la puce graphique."),
    )),
    ("valentine", (
        ("ambient", "loveletters", "Love letters", "Lettres d'amour", 300, None,
         "Sealed envelopes drifting up like paper boats.", "Des enveloppes scellées qui montent comme des bateaux de papier."),
        ("live", "loveletters", "Love letters", "lettres d'amour", 350, None, "", ""),
        ("effect", "cupid", "Cupid's arrows", "Flèches de Cupidon", 250, None,
         "Arrows with heart tips shooting out of the reward.", "Des flèches à pointe de cœur qui partent de la récompense."),
        ("palette", "cherry", "Cherry", "Cerise", 200, None,
         "Deep cherry red and blush pink over the theme.", "Rouge cerise profond et rose poudré sur le thème."),
        ("name", "lovestruck", "Lovestruck", "amoureux", 300, None,
         "A pink name beating like a heart.", "Un nom rose qui bat comme un cœur."),
        ("banner", "sweetheart", "Sweetheart", "Mon cœur", 300, None,
         "A pink dusk scattered with hearts.", "Un crépuscule rose parsemé de cœurs."),
        ("title", "Hopeless romantic", "Titre : Romantique incurable", "pulse", 150, None, "", ""),
        ("badge", "Cupid's arrow", "Badge Flèche de Cupidon", "heart", "float", 200, None, "", ""),
        ("frame", "heartbeat", "Heartbeat", "Battement de cœur", 650, 4,
         "A red ring beating around your avatar.", "Un anneau rouge qui bat autour de votre avatar."),
        ("level", "heart", "Heart", "Cœur", 700, 4,
         "Your level in a glossy heart.", "Votre niveau dans un cœur verni."),
        ("notif", "loveletter", "Love letter", "Lettre d'amour", 650, 4,
         "Notifications that arrive as sealed love letters.", "Des notifications qui arrivent en lettres d'amour scellées."),
        ("hdframe", "amour", "Amour", "Amour", 1200, 8,
         "Pink and red light swirling into hearts around your avatar, drawn by the graphics chip.",
         "Une lumière rose et rouge qui tourbillonne en cœurs autour de votre avatar, dessinée par la puce graphique."),
        ("hdname", "amour", "Amour", "amour", 1100, 8, "", ""),
    )),
    ("spring", (
        ("ambient", "butterflies", "Butterflies", "Papillons", 300, None,
         "Butterflies fluttering across the screen.", "Des papillons qui voltigent à travers l'écran."),
        ("live", "butterflies", "Butterflies", "papillons", 350, None, "", ""),
        ("effect", "eggs", "Easter eggs", "Œufs de Pâques", 250, None,
         "Painted eggs bouncing out of the reward.", "Des œufs peints qui rebondissent hors de la récompense."),
        ("palette", "pastel", "Pastel", "Pastel", 200, None,
         "Soft lilac and mint over the theme.", "Lilas tendre et menthe sur le thème."),
        ("name", "springtime", "Springtime", "printanier", 300, None,
         "A name in pastel colours, a small flower blooming beside it.", "Un nom aux couleurs pastel, une petite fleur qui éclot à côté."),
        ("banner", "garden", "Garden", "Jardin", 300, None,
         "A garden in bloom under a clear sky.", "Un jardin en fleurs sous un ciel clair."),
        ("title", "April showers", "Titre : Giboulées d'avril", "float", 150, None, "", ""),
        ("badge", "Easter bunny", "Badge Lapin de Pâques", "rabbit", "pulse", 200, None, "", ""),
        ("frame", "daisy", "Daisy chain", "Couronne de pâquerettes", 650, 4,
         "A ring of daisies around your avatar.", "Une couronne de pâquerettes autour de votre avatar."),
        ("level", "easteregg", "Easter egg", "Œuf de Pâques", 700, 4,
         "Your level on a painted egg.", "Votre niveau sur un œuf peint."),
        ("notif", "bloom", "Bloom", "Floraison", 650, 4,
         "Notifications framed with fresh leaves and flowers.", "Des notifications encadrées de feuilles et de fleurs fraîches."),
        ("hdframe", "verdant", "Verdant", "Verdoyant", 1200, 8,
         "Leaves of light growing around your avatar, drawn by the graphics chip.",
         "Des feuilles de lumière qui poussent autour de votre avatar, dessinées par la puce graphique."),
        ("hdlevel", "verdant", "Verdant", "Verdoyant", 1200, 8,
         "Your level sprouting leaves of light, drawn by the graphics chip.",
         "Votre niveau d'où poussent des feuilles de lumière, dessinées par la puce graphique."),
    )),
    ("summer", (
        ("ambient", "seagulls", "Seagulls", "Mouettes", 300, None,
         "Seagulls gliding over a summer sky.", "Des mouettes qui planent dans un ciel d'été."),
        ("live", "seagulls", "Seagulls", "mouettes", 350, None, "", ""),
        ("effect", "splash", "Splash", "Éclaboussures", 250, None,
         "Sea water splashing out of the reward.", "De l'eau de mer qui gicle hors de la récompense."),
        ("palette", "tropical", "Tropical", "Tropical", 200, None,
         "Lagoon turquoise and coral over the theme.", "Turquoise lagon et corail sur le thème."),
        ("name", "tropical", "Tropical", "tropical", 300, None,
         "A name in lagoon and coral colours, gently swaying.", "Un nom aux couleurs de lagon et de corail, qui ondule doucement."),
        ("banner", "seaside", "Seaside", "Bord de mer", 300, None,
         "The sea, the sun low over it, a beach.", "La mer, le soleil bas au-dessus, une plage."),
        ("title", "Beach king", "Titre : Roi de la plage", "gold", 150, None, "", ""),
        ("badge", "Seashell", "Badge Coquillage", "shell", "shimmer", 200, None, "", ""),
        ("frame", "lifebuoy", "Lifebuoy", "Bouée", 650, 4,
         "A red and white lifebuoy around your avatar.", "Une bouée rouge et blanche autour de votre avatar."),
        ("level", "sunset", "Sunset", "Coucher de soleil", 700, 4,
         "Your level over the sun setting on the sea.", "Votre niveau sur le soleil couchant sur la mer."),
        ("notif", "postcard", "Postcard", "Carte postale", 650, 4,
         "Notifications that arrive as postcards.", "Des notifications qui arrivent en cartes postales."),
        ("hdframe", "sunburst", "Sunburst", "Soleil ardent", 1200, 8,
         "A blazing summer sun flaring around your avatar, drawn by the graphics chip.",
         "Un soleil d'été qui flamboie autour de votre avatar, dessiné par la puce graphique."),
        ("hdname", "sunburst", "Sunburst", "solaire", 1700, 12, "", ""),
    )),
)  # fmt: skip
SEASONAL_LEGENDARY = ("level_spectre", "frame_tinsel", "name_namesunburst")
HD_ABOUT = ("Drawn by the graphics chip.", "Dessiné par la puce graphique.")
for _season, _items in SEASONAL:
    _made, _hd = _looks(_items, season=_season)
    _names = {
        "halloween": ("Halloween", "Halloween"),
        "christmas": ("Christmas", "Noël"),
        "valentine": ("Valentine's", "Saint-Valentin"),
        "spring": ("Spring", "Printemps"),
        "summer": ("Summer", "Été"),
    }[_season]
    _p(
        f"pack_hd_{_season}",
        "bundle",
        None,
        "epic",
        f"{_names[0]} HD pack",
        f"Pack {_names[1]} HD",
        "The season's looks drawn by the graphics chip.",
        "Les looks de la saison dessinés par la puce graphique.",
        {"products": _hd},
        collection="packs",
        icon="shop",
        level=8,
        season=_season,
    )

# #81: the seasons — what already belonged to one (the new seasonal items set theirs where they are made)
SEASON_OF: dict[str, str] = {
    **dict.fromkeys(
        ("ambient_bats", "ambient_haunted", "ambient_leaves", "ambient_autumnlane", "badge_ghost",
         "badge_pumpkin_king", "banner_halloween", "banner_live_bats", "effect_pumpkin", "frame_pumpkin",
         "levelup_pumpkin", "name_halloween", "name_horror", "theme_halloween", "theme_horror"),
        "halloween",
    ),
    **dict.fromkeys(
        ("ambient_christmasnight", "ambient_snow", "ambient_hearth", "ambient_knit", "ambient_candlelight",
         "badge_snowflake", "banner_live_snow", "banner_snowfall", "effect_snow", "effect_flicker",
         "frame_frostcrown", "frame_holly", "frame_lights", "level_frost", "level_lights", "levelup_gift",
         "levelup_hearth", "name_christmas", "name_cozy", "name_ice", "name_namefrost", "notif_frostbite",
         "palette_ice", "title_frostborn", "theme_christmas", "theme_cozy"),
        "christmas",
    ),
    **dict.fromkeys(("ambient_hearts", "banner_live_hearts", "effect_hearts", "palette_rose"), "valentine"),
    **dict.fromkeys(
        ("ambient_petals", "ambient_meadow", "badge_blossom", "banner_live_petals", "banner_sakura",
         "banner_live_meadow", "effect_bloom", "effect_petals", "effect_petalstorm", "frame_sakura",
         "level_sakura", "levelup_sakurastorm", "name_namesakura", "notif_petalfall", "notif_sakura",
         "title_spring_spirit"),
        "spring",
    ),
    **dict.fromkeys(
        ("ambient_fireflies", "ambient_summerfield", "ambient_pixelbeach", "ambient_sand", "ambient_sandstorm",
         "banner_live_fireflies", "frame_sand", "name_desert", "palette_sunset", "title_sand_lord",
         "levelup_sandstorm", "theme_desert"),
        "summer",
    ),
}  # fmt: skip
_KEYS = {product["key"] for product in SHOP}
for product in SHOP:
    product["season"] = product.get("season") or SEASON_OF.get(product["key"])

# #81: a pack per season — every look of the season together (made from the seasons, never by hand)
SEASON_PACKS: dict[str, tuple[str, str, str, str, str]] = {
    "valentine": ("Valentine's pack", "Pack Saint-Valentin", "heart",
                  "Every look of Valentine's Day together.", "Tous les looks de la Saint-Valentin réunis."),
    "spring": ("Spring pack", "Pack Printemps", "flower",
               "Every look of spring together: blossom, meadows, fresh colours.",
               "Tous les looks du printemps réunis : fleurs, prairies, couleurs fraîches."),
    "summer": ("Summer pack", "Pack Été", "sun",
               "Every look of summer together: sun, sand, sea and warm nights.",
               "Tous les looks de l'été réunis : soleil, sable, mer et nuits chaudes."),
    "halloween": ("Halloween pack", "Pack Halloween", "ghost",
                  "Every look of Halloween together: pumpkins, ghosts, bats and chills.",
                  "Tous les looks d'Halloween réunis : citrouilles, fantômes, chauves-souris et frissons."),
    "christmas": ("Christmas pack", "Pack Noël", "snowflake",
                  "Every look of Christmas together: snow, fairy lights and the fireside.",
                  "Tous les looks de Noël réunis : neige, guirlandes et coin du feu."),
}  # fmt: skip
_LOOK_TYPES = {
    "ambient", "avatar_frame", "profile_banner", "name_style", "level_badge", "level_up", "badge", "title",
    "notification_style", "notification_animation", "effect", "palette",
}  # fmt: skip
for _season, (_en, _fr, _icon, _about_en, _about_fr) in SEASON_PACKS.items():
    _held = [
        p["key"] for p in SHOP if p["season"] == _season and p["type"] in _LOOK_TYPES and not p["reward_only"]
    ]
    if len(_held) >= 3:
        _p(f"pack_season_{_season}", "bundle", None, "rare", _en, _fr, _about_en, _about_fr, {"products": _held},
           collection="packs", icon=_icon, season=_season)  # fmt: skip

# #81: the boosters — products like the others; their odds and refunds are the administrators' (the demo
# seeds them once, never back over what was tuned)
_CLASSIC_ODDS = {"common": 62, "rare": 26, "epic": 10, "legendary": 2}
_SEASON_ODDS = {"common": 55, "rare": 33, "epic": 10, "legendary": 2}
BOOSTERS: tuple[tuple[str, int, str, str, str, str, str, dict[str, Any]], ...] = (
    ("booster_cosmos", 450, "rare", "Cosmos booster", "Booster Cosmos",
     "The classic: five looks drawn at random — ambiences, frames, banners, titles, badges, styles… at least one rare.",
     "Le classique : cinq looks tirés au hasard — ambiances, cadres, bannières, titres, badges, styles… dont au moins un rare.",
     {"pool": "looks", "cards": 5, "odds": _CLASSIC_ODDS, "guarantee": "rare", "look": "cosmos"}),
    ("booster_legend", 3000, "legendary", "Legendary booster", "Booster Légendaire",
     "Three cards, none below epic, and a legendary one for sure.",
     "Trois cartes, pas une en dessous d'épique, et une légendaire assurée.",
     {"pool": "looks", "cards": 3, "odds": {"epic": 70, "legendary": 30}, "guarantee": "legendary", "look": "legend"}),
    ("booster_prestige", 1200, "epic", "Prestige HD booster", "Booster Prestige HD",
     "Only looks drawn by the graphics chip — flames, plasma, liquid gold… Three cards, at least one epic.",
     "Uniquement des looks dessinés par la puce graphique — flammes, plasma, or liquide… Trois cartes, dont au moins une épique.",
     {"pool": "hd", "cards": 3, "odds": {"rare": 20, "epic": 62, "legendary": 18}, "guarantee": "epic", "look": "prestige"}),
    ("booster_reserve", 300, "rare", "Reserve booster", "Booster Réserve",
     "Items to keep for later: extra requests, streak freezes, boosts, rescues… and maybe a film in 4K. They go to your reserve.",
     "Des objets à garder pour plus tard : demandes en plus, gels de série, boosts, sauvetages… et peut-être un film en 4K. Ils vont dans votre réserve.",
     {"pool": "reserve", "cards": 3, "odds": {"common": 60, "rare": 30, "epic": 9, "legendary": 1}, "guarantee": "rare", "look": "reserve"}),
    ("booster_discovery", 120, "common", "Discovery booster", "Booster Découverte",
     "To get started: three looks for a small price. Three openings per member.",
     "Pour commencer : trois looks pour un petit prix. Trois ouvertures par membre.",
     {"pool": "looks", "cards": 3, "odds": {"common": 72, "rare": 25, "epic": 3}, "guarantee": "common", "per_member": 3, "look": "discovery"}),
    *(
        (f"booster_{season}", 450, "epic", f"{names[0].replace(' pack', '')} booster",
         f"Booster {names[1].replace('Pack ', '')}",
         "In season: five of its looks drawn at random, at least one rare — on sale in its weeks only.",
         "De saison : cinq de ses looks tirés au hasard, dont au moins un rare — en vente pendant ses semaines seulement.",
         {"pool": "looks", "season": season, "cards": 5, "odds": _SEASON_ODDS, "guarantee": "rare",
          "look": "winter" if season == "christmas" else season})
        for season, names in SEASON_PACKS.items()
    ),
)  # fmt: skip
for _b in BOOSTERS:
    _p(_b[0], "booster", _b[1], _b[2], _b[3], _b[4], _b[5], _b[6], _b[7], collection="boosters",
       icon="sparkles", repeatable=True, season=_b[7].get("season"))  # fmt: skip

# rarities stay rare: legendary for a handful of flagship items, the cheaper « rare » ones are common
# 027: a handful of legendaries (the flagships), rare from 600 Coins, epic from 1000 — most of the shop common
LEGENDARY = {
    "badge_the_one", "badge_dragon_tamer", "frame_hologram", "theme_wizard", "theme_cyberpunk",
    "ultimate_wizard", "ultimate_cyberpunk", "effect_portal", "name_royal", "pack_server_room",
    "request_tv_channel",
    "ambient_blackhole", "ambient_volcano", "ambient_thunderstorm", "ambient_neoncity", "ambient_weather", "ambient_lavalamp", "ambient_impasto", "ambient_reef", "level_blaze",
    "frame_starlit", "levelup_supernova", "levelup_phoenix", "frame_regalia",
    "level_chrono", "notif_chrono", "frame_chronogate", "levelup_timeportal", "pack_hd_time_portal",
    "notif_warp", "effect_timerift", "effect_nova", "effect_rebirth", "name_namegold", "name_namechrono",
    *SEASONAL_LEGENDARY,
    # #130: the cosmos' flagships
    *COSMOS_LEGENDARY,
    "levelup_rift",  # #133: the Upside Down's gate
}  # fmt: skip
for product in SHOP:
    if product["rarity"] == "legendary" and product["key"] not in LEGENDARY and product["type"] != "booster":
        product["rarity"] = "epic"
    elif product["rarity"] == "rare" and (product["price"] or 0) < 600 and product["type"] != "booster":
        product["rarity"] = "common"
    if (
        product["rarity"] == "epic"
        and (product["price"] or 0) < 1000
        and product["type"] not in ("bundle", "booster")
    ):
        product["rarity"] = "rare" if (product["price"] or 0) >= 600 else "common"

_BY_KEY = {product["key"]: product for product in SHOP}
for product in SHOP:
    if product["type"] == "bundle" and product["price"] is None:
        worth: int = sum(int(_BY_KEY[key]["price"] or 0) for key in product["payload"]["products"])
        price = max(100, round(worth * 0.8 / 10) * 10)  # about 20 % saved
        product["price"] = price
        saved = worth - price
        product["descriptions"] = {
            "en": f"{product['descriptions']['en']} — {saved} Coins saved.",
            "fr": f"{product['descriptions']['fr']} — {saved} Coins d'économie.",
        }
        # 027: a pack is as rare as what it holds is worth — a few legendary flagships, then epic, rare, common
        if product["key"] in LEGENDARY or price >= 7500:
            product["rarity"] = "legendary"
        elif price >= (5000 if product["key"].startswith("ultimate_") else 3500):  # theme packs hold more
            product["rarity"] = "epic"
        elif price >= 1500:
            product["rarity"] = "rare"
        else:
            product["rarity"] = "common"

COLLECTIONS: tuple[tuple[str, str, str, int], ...] = (
    ("ultimate", "Theme packs", "crown", 1),
    ("themes", "Interfaces", "palette", 3),
    ("packs", "Packs", "shop", 5),
    ("boosters", "Boosters", "sparkles", 6),
    ("halloween", "Halloween", "moon", 10),
    ("new_wave", "New Wave", "zap", 20),
    ("badges", "Badges", "star", 22),
    ("titles", "Titles", "trophy", 24),
    ("essentials", "Essentials", "star", 30),
    ("profile", "Profile", "user", 35),
    ("names", "Name styles", "feather", 36),
    ("backgrounds", "Animated backgrounds", "sparkles", 37),
    ("looks", "Notifications", "bell", 40),
    ("ambients", "Ambiences", "snowflake", 42),
    ("celebrations", "Celebrations", "party", 43),
    ("palettes", "Palettes", "palette", 45),
    ("widgets", "Widgets", "dashboard", 50),
    ("statistics", "Statistics", "chart", 52),
    ("levels", "Level badges and level-ups", "trophy", 41),
    ("rewards", "Achievement rewards", "gift", 60),
)


def definition(product: Product) -> dict[str, Any]:
    """The catalog definition of a demo product (what ``Catalog.create``/``revise`` take)."""
    return sync_definition(product)


# --------------------------------------------------------------------------------- levels (#108)
# The level a product needs, spread over the whole curve (level 50 in about three years at a film every
# other day). Only a fifth of what is sold needs a level — the rarest looks, the dearest boosters and what
# serves (accesses, widgets, statistics, services, boosts, which keep the level given them); the rest is
# bought with Coins alone. Legendary looks unlock on the great tiers only (10, 20, 30, 40, 50); epic ones
# over the whole curve, a tier level (Argent II, Or I…) unlocking about three times what a level in
# between does, a great tier five times. Within a rarity the products keep their order: the level they
# were given here, then their price.
GATED_SHARE = 1 / 5
GREAT_TIERS = (10, 20, 30, 40, 50)
EPIC_BAND = (3, 49)
BOOSTER_LEVELS = {"booster_prestige": 15, "booster_legend": 30}  # the others are for everyone
# the Nova universe — handy on a phone — is offered whole at the first tier worth it (Bronze II, level 5)
# and is usable from there: a legendary pack early on, to make members want to go further
EARLY = {"ultimate_nova": 5, "pack_nova": 5, "theme_nova": 5}
USEFUL = {
    "early_unlock",  # #131: for everyone (it is how one gets round a level)
    "access",
    "service_access",
    "widget",
    "statistic",
    "media_rescue",
    "special_request",
    "streak_freeze",
    "xp_boost",
    "project_launch",
    "profile_backdrop",
}
TIERS = {tier["level"] for tier in LEVEL_REWARDS}


def level_weight(level: int) -> int:
    return 5 if level in GREAT_TIERS else 3 if level in TIERS else 1


def _take(products: list[Product], slots: list[int]) -> None:
    """The products, in order, take the slots evenly (a level present several times takes more)."""
    last = max(1, len(products) - 1)
    for rank, product in enumerate(products):
        product["level"] = slots[round(rank * (len(slots) - 1) / last)]


def _spread_levels(products: list[Product]) -> None:
    sold = [p for p in products if not p["reward_only"] and p["key"] not in RETIRED]
    for product in sold:
        if product["type"] == "booster":
            product["level"] = BOOSTER_LEVELS.get(product["key"])
        elif product["type"] in USEFUL and product["level"] and product["rarity"] == "legendary":
            product["level"] = next(t for t in GREAT_TIERS if t >= product["level"])  # a great tier too
    kept = sum(1 for p in sold if p["level"] and (p["type"] in USEFUL or p["type"] == "booster"))
    looks = [p for p in sold if p["type"] not in USEFUL and p["type"] != "booster"]
    order = {p["key"]: (p["level"] or 0, p["price"] or 0, p["key"]) for p in looks}
    fixed = {**EARLY, **COSMOS_LEVELS}  # #130: the cosmos sets its own
    looks = [p for p in looks if p["key"] not in fixed]
    legendary = [p for p in looks if p["rarity"] == "legendary"]
    epic = sorted((p for p in looks if p["rarity"] == "epic"), key=lambda p: (-(p["price"] or 0), p["key"]))
    gated_fixed = sum(
        1 for p in sold if fixed.get(p["key"]) and p["type"] not in USEFUL and p["type"] != "booster"
    )
    epic = epic[: max(0, round(len(sold) * GATED_SHARE) - kept - gated_fixed - len(legendary))]
    gated = {p["key"] for p in legendary + epic}
    for product in looks:
        if product["key"] not in gated:
            product["level"] = None
    _take(sorted(legendary, key=lambda p: order[p["key"]]), list(GREAT_TIERS))
    low, high = EPIC_BAND
    slots = [level for level in range(low, high + 1) for _ in range(level_weight(level))]
    _take(sorted(epic, key=lambda p: order[p["key"]]), slots)
    for product in sold:
        if product["key"] in fixed:
            product["level"] = fixed[product["key"]]


# #130: the cosmos' interfaces at the first great tier, their theme packs at the great tier at or above what
# they hold (never a way round a level)
for _theme in ("observatory", "spacestation", "starship"):
    COSMOS_LEVELS[f"theme_{_theme}"] = THEME_RARITY[_theme][2]
    _held = next(p for p in SHOP if p["key"] == f"ultimate_{_theme}")["payload"]["products"]
    _most = max((COSMOS_LEVELS.get(k) or 0 for k in _held), default=0)
    COSMOS_LEVELS[f"ultimate_{_theme}"] = next(t for t in GREAT_TIERS if t >= _most)

# a cosmos pack that came out legendary (its worth) unlocks on a great tier, at or above what it holds
for _key, *_text, _inside in COSMOS_PACKS:
    _pack = next(p for p in SHOP if p["key"] == _key)
    if _pack["rarity"] == "legendary":
        COSMOS_LEVELS[_key] = next(t for t in GREAT_TIERS if t >= (COSMOS_LEVELS.get(_key) or 1))


_spread_levels(SHOP)
