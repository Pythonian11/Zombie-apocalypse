import time
import random
import threading

health = 100
location = "Base"
hunger = 10
BACKGROUND_STOP = threading.Event()
BACKGROUND_THREAD = None
BACKGROUND_TASKS_RUNNING = False
#not hungry
#Locations available in city section: Base, Supermart, Lab, Leisure center, "Skyscrapper"(intentional spelling error, theres a whole backstory), Factory, Landfill, Army base, ZCC (Zombie control center).
#Locations available in town section: Power station, Market, Inn, Bus hangar, Town hall, Bjorn's house, Airport.
#Location for beacon deployment: "The Field."
attackable = False
Incity = True
Intown = False
InField = False
ITEM_CLASSES = {
    "medkit": "healing",
    "plaster": "healing",
    "Zombie meat": "misc",
    "meat": "food",
    "apple": "food",
    "bullet": "ammo",
    "sniper bullet": "ammo",
    "burning bullet": "ammo",
    "stun bullet": "ammo",
    "tin": "scrap",
    "copper": "scrap",
    "bulb": "scrap",
    "knife": "weapon",
    "pistol": "weapon",
    "rifle": "weapon",
    "axe": "weapon",
    "stick": "weapon",
}

ITEM_PROPERTIES = {
    "medkit": {"heals": 25, "equipped": False},
    "plaster": {"heals": 10, "equipped": False},
    "meat": {"heals": 15, "hunger": 5, "equipped": False},
    "apple": {"heals": 10, "hunger": 3, "equipped": False},
    "bullet": {"damage_bonus": 0, "status_effects": [], "equipped": False},
    "sniper bullet": {"damage_bonus": 8, "status_effects": [], "equipped": False},
    "burning bullet": {"damage_bonus": 5, "status_effects": ["burning"], "equipped": False},
    "stun bullet": {"damage_bonus": 4, "status_effects": ["stunned"], "equipped": False},
    "knife": {"damage_bonus": 0, "status_effects": [], "equipped": False},
    "pistol": {"damage_bonus": 10, "status_effects": ["burning"], "equipped": False},
    "rifle": {"damage_bonus": 15, "status_effects": ["piercing"], "equipped": False},
    "axe": {"damage_bonus": 5, "status_effects": ["heavy"], "equipped": False},
    "stick": {"damage_bonus": 0, "status_effects": ["blunt"], "equipped": False},
}

inventory = {
    "medkit": {"amount": 0, "class": "healing", "properties": dict(ITEM_PROPERTIES.get("medkit", {}))},
    "food": {"amount": 0, "class": "food", "properties": {}},
    "ammo": {"amount": 0, "class": "ammo", "properties": {}},
    "scrap": {"amount": 0, "class": "scrap", "properties": {}},
    "knife": {"amount": 0, "class": "weapon", "properties": dict(ITEM_PROPERTIES.get("knife", {}))},
    "pistol": {"amount": 0, "class": "weapon", "properties": dict(ITEM_PROPERTIES.get("pistol", {}))},
    "rifle": {"amount": 0, "class": "weapon", "properties": dict(ITEM_PROPERTIES.get("rifle", {}))},
    "axe": {"amount": 0, "class": "weapon", "properties": dict(ITEM_PROPERTIES.get("axe", {}))},
    "stick": {"amount": 0, "class": "weapon", "properties": dict(ITEM_PROPERTIES.get("stick", {}))},
}

active_zombies = []


# Simple presence flag and helper so other code can check/update whether
# a zombie is currently in the player's location. Call `update_zombie_presence()`
# after any change to `active_zombies` or zombie locations so the flag stays
# correct. Use `is_zombie_at_player_location()` to query the current value.
ZOMBIE_AT_PLAYER_LOCATION = False


def update_zombie_presence():
    global ZOMBIE_AT_PLAYER_LOCATION
    ZOMBIE_AT_PLAYER_LOCATION = any(
        z.get("location", "").lower() == location.lower() for z in active_zombies
    )
    return ZOMBIE_AT_PLAYER_LOCATION


def is_zombie_at_player_location():
    return ZOMBIE_AT_PLAYER_LOCATION


def start_background_tasks(interval=2.0):
    global BACKGROUND_THREAD, BACKGROUND_TASKS_RUNNING

    if BACKGROUND_TASKS_RUNNING and BACKGROUND_THREAD is not None and BACKGROUND_THREAD.is_alive():
        print("Background task loop is already running.")
        return BACKGROUND_THREAD

    BACKGROUND_STOP.clear()

    def _background_loop():
        while not BACKGROUND_STOP.is_set():
            if attackable:
                zombie_ai_tick()
                check_for_attacks()
            time.sleep(interval)

    BACKGROUND_THREAD = threading.Thread(target=_background_loop, name="apocalypse-background", daemon=True)
    BACKGROUND_THREAD.start()
    BACKGROUND_TASKS_RUNNING = True
    print("Background apocalypse tasks started.")
    return BACKGROUND_THREAD


def stop_background_tasks():
    global BACKGROUND_TASKS_RUNNING
    BACKGROUND_STOP.set()
    BACKGROUND_TASKS_RUNNING = False
    print("Background apocalypse tasks stopped.")
    return True


def print_function_guide():
    print("""
Quick use guide for the apocalypse functions:
- add_item(item, amount=1, item_class=None, properties=None): give the player an item.
  Example: add_item('apple', 2, properties={'heals': 10, 'hunger': 3})
- get_item_count('pistol'): returns how many of that item you have.
- get_item_properties('pistol'): shows bonus details like +10 damage and burning.
- set_item_properties('pistol', damage_bonus=12, status_effects=['burning']): customises an item.
- equip_item('pistol', True): marks it as equipped.
- use_item('apple'): consumes the item and applies its effects.
- use_weapon('pistol'): equips/uses the weapon in combat.
- spawn_zombie('alpha', 'Base'): creates a zombie at a location.
- player_attack(zombie): attacks the zombie in combat.
- check_for_attacks(): checks combat at your current location.
- start_background_tasks(): starts a background zombie tick loop.
- stop_background_tasks(): stops the background loop.
""")


# --- Zombie abilities and AI ---
def apply_alpha_aura(alpha, bonus=5):
    zone = get_zone_for_location(alpha.get("location", ""))
    for z in active_zombies:
        if z is alpha:
            continue
        if get_zone_for_location(z.get("location", "")) == zone:
            z.setdefault("base_damage", z.get("damage", 0))
            if not z.get("alpha_buffed"):
                z["damage"] = z.get("base_damage", z.get("damage", 0)) + bonus
                z["alpha_buffed"] = True


def revoke_alpha_aura(alpha, bonus=5):
    # Remove alpha's buff from zombies in the same zone
    zone = get_zone_for_location(alpha.get("location", ""))
    for z in active_zombies:
        if z.get("alpha_buffed"):
            z["damage"] = z.get("base_damage", z.get("damage", 0))
            z.pop("alpha_buffed", None)


def necromancer_raise(necro, count=1):
    for _ in range(count):
        minion = {
            "type": "Normie",
            "location": necro.get("location", location),
            "health": int(ZOMBIE_TYPES["normie"]["health"] * 0.6),
            "speed": ZOMBIE_TYPES["normie"]["speed"],
            "power": ZOMBIE_TYPES["normie"]["power"],
            "damage": 6,
            "raised_by": necro.get("type"),
            "base_damage": 6,
            "ticks": 0,
        }
        active_zombies.append(minion)
        print(f"A small minion crawls from the necromancer at {minion['location']}!")
    update_zombie_presence()


def zombie_ai_tick():
    # Run per-zombie AI behaviours. Safe-iterate over a copy since list may change.
    for z in list(active_zombies):
        z["ticks"] = z.get("ticks", 0) + 1
        ztype = z.get("type", "").lower()

        if ztype == "alpha":
            apply_alpha_aura(z)

        if ztype == "strider":
            # If in same zone as player, strider may leap to player and strike first
            if get_zone_for_location(z.get("location", "")) == get_zone_for_location(location):
                if z.get("location", "").lower() != location.lower():
                    print(f"A {z['type']} leaps across the area and lands at your position!")
                    z["location"] = location
                    update_zombie_presence()
                    if attackable:
                        global health
                        print(f"The {z['type']} strikes you as it lands for {z['damage']} damage!")
                        health -= z["damage"]
                        if health <= 0:
                            print("You were overrun and the apocalypse claimed you.")
                            raise SystemExit

        if ztype == "necromancer":
            # Every 3 ticks, try to raise a small minion
            if z.get("ticks", 0) % 3 == 0 and random.random() < 0.5:
                necromancer_raise(z, count=1)



def normalize_item_name(item):
    return str(item).strip().lower()


def get_item_count(item):
    item = normalize_item_name(item)
    if item not in inventory:
        return 0
    if isinstance(inventory[item], dict):
        return inventory[item].get("amount", 0)
    return inventory[item]


def get_item_properties(item):
    item = normalize_item_name(item)
    default = dict(ITEM_PROPERTIES.get(item, {}))
    if item not in inventory:
        return default

    record = inventory[item]
    if not isinstance(record, dict):
        return default

    props = dict(default)
    item_props = record.get("properties", {})
    if isinstance(item_props, dict):
        props.update(item_props)
    props.setdefault("equipped", False)
    return props


def set_item_properties(item, **properties):
    item = normalize_item_name(item)
    if item not in inventory:
        inventory[item] = {"amount": 0, "class": ITEM_CLASSES.get(item, "misc"), "properties": {}}
    if not isinstance(inventory[item], dict):
        inventory[item] = {"amount": inventory[item], "class": ITEM_CLASSES.get(item, "misc"), "properties": {}}

    inventory[item].setdefault("properties", {})
    inventory[item]["properties"].update(properties)
    return inventory[item]["properties"]


def get_item_class(item):
    item = normalize_item_name(item)
    if item == "fists":
        return "weapon"
    if item not in inventory:
        return ITEM_CLASSES.get(item, "misc")
    if isinstance(inventory[item], dict):
        return inventory[item].get("class", ITEM_CLASSES.get(item, "misc"))
    return ITEM_CLASSES.get(item, "misc")


def set_item_class(item, item_class):
    item = normalize_item_name(item)
    if item in inventory and isinstance(inventory[item], dict):
        inventory[item]["class"] = item_class
    elif item in inventory and isinstance(inventory[item], int):
        inventory[item] = {"amount": inventory[item], "class": item_class, "properties": {}}
    else:
        inventory[item] = {"amount": 0, "class": item_class, "properties": {}}


def get_item_damage_bonus(item):
    return int(get_item_properties(item).get("damage_bonus", 0))


def equip_item(item, equipped=True):
    item = normalize_item_name(item)
    if item not in inventory:
        return False
    properties = get_item_properties(item)
    properties["equipped"] = bool(equipped)
    set_item_properties(item, **properties)
    return True


for item in list(inventory.keys()):
    if not isinstance(inventory[item], dict):
        inventory[item] = {"amount": inventory[item], "class": ITEM_CLASSES.get(item.lower(), "misc"), "properties": {}}
    inventory[item].setdefault("class", ITEM_CLASSES.get(item.lower(), "misc"))
    inventory[item].setdefault("properties", {})
    inventory[item]["properties"].setdefault("equipped", False)
    for key, value in ITEM_PROPERTIES.get(item.lower(), {}).items():
        inventory[item]["properties"].setdefault(key, value)

CITY_LOCATIONS = [
    "Base",
    "Supermart",
    "Lab",
    "Leisure center",
    "Skyscrapper",
    "Factory",
    "Landfill",
    "Army base",
    "ZCC",
]

TOWN_LOCATIONS = [
    "Power station",
    "Market",
    "Inn",
    "Bus hangar",
    "Town hall",
    "Bjorn's house",
    "Airport",
]

FIELD_LOCATIONS = ["The Field"]

ZOMBIE_TYPES = {
    "alpha": {
        "health": 180,
        "speed": "Slow but devastating",
        "power": "Roar of the pack: nearby zombies gain a strength boost and the Alpha can smash through barricades.",
    },
    "strider": {
        "health": 110,
        "speed": "Very fast",
        "power": "Long-range leap: can close distance instantly and knock survivors off balance.",
    },
    "puncher": {
        "health": 150,
        "speed": "Heavy and relentless",
        "power": "Bone-crushing punch: deals high damage and can break armor or shields.",
    },
    "necromancer": {
        "health": 120,
        "speed": "Calculated and eerie",
        "power": "Dark summons: raises weaker zombies to fight alongside it and drains the life of nearby survivors.",
    },
    "normie": {
        "health": 60,
        "speed": "Slow but numerous",
        "power": "Swarm attack: overwhelms targets with sheer numbers and panic.",
    },
}


def show_inventory():
    print("Inventory:")
    if not any(get_item_count(item) > 0 for item in inventory):
        print("  Empty")
        return

    for item in inventory:
        count = get_item_count(item)
        if count > 0:
            props = get_item_properties(item)
            bonus = props.get("damage_bonus", 0)
            effects = props.get("status_effects", [])
            info = []
            if bonus:
                info.append(f"+{bonus} damage")
            if effects:
                info.append(", ".join(effects))
            detail = f" ({', '.join(info)})" if info else ""
            print(f"  - {item}: {count}{detail}")


def add_item(item, amount=1, item_class=None, properties=None):
    item = normalize_item_name(item)
    item_class = item_class or ITEM_CLASSES.get(item, "misc")
    item_props = dict(ITEM_PROPERTIES.get(item, {}))
    if properties:
        item_props.update(properties)

    if item in inventory and isinstance(inventory[item], dict):
        inventory[item]["amount"] += amount
        inventory[item]["class"] = item_class
        inventory[item].setdefault("properties", {})
        inventory[item]["properties"].update(item_props)
    elif item in inventory:
        inventory[item] = {"amount": inventory[item] + amount, "class": item_class, "properties": item_props}
    else:
        inventory[item] = {"amount": amount, "class": item_class, "properties": item_props}

    print(f"Added {amount} {item}(s) to your inventory.")


def use_item(item):
    global hunger
    item = normalize_item_name(item)
    if item not in inventory or get_item_count(item) <= 0:
        print(f"You don't have any {item}.")
        return

    if isinstance(inventory[item], dict):
        inventory[item]["amount"] -= 1
    else:
        inventory[item] -= 1
    print(f"You used 1 {item}.")

    if item == "medkit":
        health = min(100, health + 25)
        print(f"Health restored. Current health: {health}")
    elif item == "apple":
        hunger = max(0, hunger - get_item_properties(item).get("hunger", 0))
        print(f"You eat the apple. Hunger: {hunger}")
    elif item == "meat":
        hunger = max(0, hunger - get_item_properties(item).get("hunger", 0))


def use_weapon(item):
    item = normalize_item_name(item)
    if item == "fists":
        print("You use your fists.")
        return

    if item not in inventory or get_item_count(item) <= 0:
        print("You do not have this weapon. Check your spelling.")
        return

    if get_item_class(item) != "weapon":
        print(f"{item} is not a weapon.")
        return

    item_props = get_item_properties(item)
    if item_props.get("status_effects"):
        print(f"You use {item} with {', '.join(item_props['status_effects'])} effect(s).")
    else:
        print(f"You use {item}.")

    equip_item(item, True)


def get_zone_for_location(target_location):
    normalized_location = target_location.strip().lower()
    for zone_name, zone_locations in {
        "city": CITY_LOCATIONS,
        "town": TOWN_LOCATIONS,
        "field": FIELD_LOCATIONS,
    }.items():
        if any(location.lower() == normalized_location for location in zone_locations):
            return zone_name
    return "unknown"


def move_zombie_in_zone(zombie, target_zone=None):
    if "location" not in zombie:
        return zombie

    zone_name = get_zone_for_location(zombie["location"])
    if target_zone is not None:
        zone_name = target_zone

    zone_locations = {
        "city": CITY_LOCATIONS,
        "town": TOWN_LOCATIONS,
        "field": FIELD_LOCATIONS,
    }.get(zone_name, [])

    if not zone_locations:
        return zombie

    current_location = zombie["location"]
    possible_moves = [loc for loc in zone_locations if loc.lower() != current_location.lower()]
    if not possible_moves:
        return zombie

    zombie["location"] = possible_moves[0]
    print(f"A {zombie['type']} zombie shuffled through the {zone_name} zone to {zombie['location']}.")
    # Keep presence flag in sync after movement so other systems can read it
    update_zombie_presence()
    # Trigger AI behaviours after movement
    zombie_ai_tick()
    return zombie


def spawn_zombie(zombie_type=None, spawn_location=None):
    valid_types = ", ".join(sorted(ZOMBIE_TYPES.keys())).title()
    valid_locations = CITY_LOCATIONS + TOWN_LOCATIONS + FIELD_LOCATIONS

    if zombie_type is None:
        zombie_type = input(f"Choose zombie type ({valid_types}): ").strip()
    zombie_type = zombie_type.strip().lower()

    if zombie_type not in ZOMBIE_TYPES:
        print("Invalid zombie type. Choose from: Alpha, Strider, Puncher, Necromancer, Normie.")
        return None

    if spawn_location is None:
        print("Choose a spawn location:")
        print("City: " + ", ".join(CITY_LOCATIONS))
        print("Town: " + ", ".join(TOWN_LOCATIONS))
        print("Field: " + ", ".join(FIELD_LOCATIONS))
        spawn_location = input("Spawn location: ").strip()

    spawn_location = spawn_location.strip()
    location_lookup = {name.lower(): name for name in valid_locations}
    if spawn_location.lower() not in location_lookup:
        print(f"Invalid location '{spawn_location}'. Available options: {', '.join(valid_locations)}")
        return None

    final_type = zombie_type
    final_location = location_lookup[spawn_location.lower()]
    zombie = {
        "type": final_type.title(),
        "location": final_location,
        "health": ZOMBIE_TYPES[final_type]["health"],
        "speed": ZOMBIE_TYPES[final_type]["speed"],
        "power": ZOMBIE_TYPES[final_type]["power"],
        "damage": 10 if final_type == "normie" else 15 if final_type == "alpha" else 18 if final_type == "puncher" else 20 if final_type == "strider" else 25,
        "base_damage": 10 if final_type == "normie" else 15 if final_type == "alpha" else 18 if final_type == "puncher" else 20 if final_type == "strider" else 25,
        "ticks": 0,
        "buffs": {},
    }
    active_zombies.append(zombie)

    print(f"\nA {zombie['type']} zombie has spawned at {zombie['location']}!")
    print(f"Health: {zombie['health']}")
    print(f"Speed: {zombie['speed']}")
    print(f"Power: {zombie['power']}")
    # Update presence flag after spawning and run AI tick to apply immediate effects
    update_zombie_presence()
    zombie_ai_tick()
    return zombie


def player_attack(zombie):
    global health
    if zombie["health"] <= 0:
        return False

    weapon = normalize_item_name(input("Choose a weapon from your inventory or type 'fists': "))
    weapon_damage = {
        "knife": 25,
        "pistol": 35,
        "rifle": 50,
        "axe": 30,
        "stick": 18,
        "fists": 10,
    }

    if weapon == "fists":
        damage = weapon_damage["fists"]
    elif weapon in inventory and get_item_class(weapon) == "weapon":
        if get_item_count(weapon) <= 0:
            print(f"You have no {weapon} left. You must use a weapon from inventory or fists.")
            return False
        attack_count = inventory[weapon]["amount"] if isinstance(inventory[weapon], dict) else inventory[weapon]
        if attack_count <= 0:
            print(f"You have no {weapon} left. You must use a weapon from inventory or fists.")
            return False
        base_damage = weapon_damage.get(weapon, 15)
        damage = base_damage + get_item_damage_bonus(weapon)
        inventory[weapon]["amount"] -= 1
    else:
        print("That item is not a weapon. You must use a weapon from your inventory or fists.")
        return False

    zombie["health"] -= damage
    item_effects = get_item_properties(weapon).get("status_effects", []) if weapon != "fists" else []
    if item_effects:
        print(f"Your {weapon} burns and scorches the {zombie['type']} for {damage} damage.")
    else:
        print(f"You hit the {zombie['type']} with a {weapon} for {damage} damage.")
    # Necromancer may raise a minion when damaged
    if zombie.get("type", "").lower() == "necromancer" and zombie["health"] > 0 and random.random() < 0.4:
        necromancer_raise(zombie, count=1)

    if zombie["health"] <= 0:
        print(f"The {zombie['type']} zombie collapses at {zombie['location']}.")
        # If an Alpha dies, revoke its aura before removing it
        if zombie.get("type", "").lower() == "alpha":
            revoke_alpha_aura(zombie)
        active_zombies.remove(zombie)
        # Update presence flag after a zombie is removed/killed
        update_zombie_presence()
        return True

    # Zombie counter-attack. Puncher has a chance for extra heavy damage.
    counter_damage = zombie.get("damage", 0)
    if zombie.get("type", "").lower() == "puncher" and random.random() < 0.25:
        extra = 10
        counter_damage += extra
        print(f"The {zombie['type']} lands a crushing follow-up for an extra {extra} damage!")

    health -= counter_damage
    print(f"The {zombie['type']} counters for {counter_damage} damage. Your health: {health}")
    if health <= 0:
        print("You were overrun and the apocalypse claimed you.")
        raise SystemExit
    return False


def check_for_attacks():
    global attackable
    if not attackable:
        return False
    # Gather all zombies currently at the player's location (swarm support)
    zombies_here = [z for z in list(active_zombies) if z.get("location", "").lower() == location.lower()]
    if not zombies_here:
        return False

    if len(zombies_here) > 1:
        print(f"A swarm of {len(zombies_here)} zombies surrounds you at {location}!")
    else:
        print(f"An enemy is in your location: {location}.")

    # Process each zombie present
    for zombie in zombies_here:
        if zombie not in active_zombies:
            continue
        while zombie in active_zombies and zombie.get("health", 0) > 0 and health > 0:
            player_attack(zombie)
            if zombie not in active_zombies:
                break
            move_zombie_in_zone(zombie)
            if zombie.get("location", "").lower() == location.lower():
                continue
            print(f"The {zombie['type']} drifted away from your position into {zombie['location']}.")
            break
    return True


def base_console():
    print("What would you like to do next, remember, you can always say help if you're unsure.")
    print()
    choice = input("So, what would you like? ").lower().strip()
    if choice == "help":
        print("Here are all of the base commands: help, go, monitor (coming soon), craft, to-do.")
        print("here is where you can go!")
        if Incity == True:
            print(CITY_LOCATIONS)
        elif Intown == True:
            print(TOWN_LOCATIONS)
        elif InField == True:
            print("Nowhere else to go!")
    elif choice == "go":
        while True:
            print()
            location_choice = input("Where would you like to go? ")
            if location_choice not in CITY_LOCATIONS and location_choice not in TOWN_LOCATIONS and location_choice not in FIELD_LOCATIONS:
                print("Not a valid location.")
            else:
                if location_choice == location:

                    if Incity == True:
                        if location_choice not in CITY_LOCATIONS:
                            print("You can't go there yet!")
                        else:
                            if location_choice == 


print("Welcome! If you haven't noticed, you are currently playing a Zombie apocalypse game!")
print()
input("Press enter when you are ready to play!")
print()
time.sleep(3)
print()
print("[Backstory] The scientists told many lies, 'It's Risk-Free!', 'Bring back the dead!', 'See your loved ones!'.\nThey wanted to bring people back from the dead, they wanted to cheat at life.\nThey wanted to do the impossible, They were punished for it.")
print()
input("Press enter to continue...")
print()
print("[Backstory] The zombie was created there and then, with no soul, yet a living being.\nIn the first 5 seconds of its life, 2 thoughts went through its empty skull. Alone, Hungry...")
print()
input("Press enter to continue...")
print()
print("[Backstory] The zombie was strong, it would later be the zombie leader and would be known as 'THE OMEGA' by survivors.\nThere were no security measures for it, it broke the triplex glass like it was cobwebs,\nsmashed through walls like they were cardboard, and zombified all the scientist so easily the may as well have been bugs.")
print()
input("Press enter to continue...")
print()
print("[Backstory] Where were you in all this? snoozing at 'City camp' in your tent covered in 'Ultra-Strength People Detterent'\n(you never really liked people.) while everyone else zombified, or escaped via airlift.\nYou survived because you had the spray, the zombies hate it, and you slept in it.")
print()
input("Press enter to continue...")
print()
print("[Backstory] Now that everyone is gone (One way or the other) you will need to escape on your own.\nTo do that you must build a beacon, I will leave you now.")
print()
input("Press enter to continue...")


print("You wake up at the base (City camp).")
print(f"Health: {health}")
print(f"Location: {location}")
show_inventory()
print_function_guide()
attackable = True
start_background_tasks(interval=2.5)

