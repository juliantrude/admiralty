"""Empire data of a Snapshot extract, read from the save as stored."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from admiralty.extract.context import NO_ID, Context, as_list, block, rounded

RESOURCE_ORDER = (
    "energy", "minerals", "food", "alloys", "consumer_goods", "unity", "influence", "trade",
    "physics_research", "society_research", "engineering_research", "volatile_motes",
    "exotic_gases", "rare_crystals", "sr_living_metal", "sr_zro", "sr_dark_matter", "minor_artifacts",
    "astral_threads",
)  # fmt: skip


def _resource_sort(resource: str) -> tuple[int, str]:
    order = RESOURCE_ORDER.index(resource) if resource in RESOURCE_ORDER else len(RESOURCE_ORDER)
    return order, resource


# --- economy -------------------------------------------------------------------------


# Market trades the empire has set to repeat monthly; the save books them apart from
# the rest of the budget, but the game's top bar includes them.
MARKET = "market_monthly_trades"


def _month(country: dict[str, Any]) -> tuple[dict, dict]:
    """Income and expenses by source of the month the top bar projects ('current_month'),
    with the monthly market trades as one more source. The game recomputes the top bar
    live after loading, so it can differ from the save by a few units (golden values:
    up to about 10 energy in 2259 and 2298)."""
    month = block(block(country.get("budget")).get("current_month"))
    income = _by_resource(block(month.get("income")))
    expenses = _by_resource(block(month.get("expenses")))
    for resource, amount in _by_resource(block(month.get("trade_income"))).items():
        income.setdefault(resource, {})[MARKET] = sum(amount.values())
    for resource, amount in _by_resource(block(month.get("trade_expenses"))).items():
        expenses.setdefault(resource, {})[MARKET] = sum(amount.values())
    return income, expenses


def economy(ctx: Context, country: dict[str, Any]) -> dict[str, Any]:
    """Stockpile plus monthly income, expenses and net per resource."""
    stockpile = block(block(country["modules"].get("standard_economy_module")).get("resources"))
    income, expenses = _month(country)
    resources = sorted(set(stockpile) | set(income) | set(expenses), key=_resource_sort)
    out = {}
    for resource in resources:
        inc = sum(income.get(resource, {}).values())
        exp = sum(expenses.get(resource, {}).values())
        out[resource] = {
            "label": ctx.label(resource),
            "stockpile": rounded(stockpile.get(resource, 0)),
            "income": rounded(inc),
            "expenses": rounded(exp),
            "net": rounded(inc - exp),
        }
    return out


def economy_by_source(ctx: Context, country: dict[str, Any]) -> dict[str, Any]:
    income, expenses = _month(country)
    out = {}
    for side, by_resource in (("income", income), ("expenses", expenses)):
        out[side] = {
            resource: {
                source: rounded(amount)
                for source, amount in sorted(sources.items(), key=lambda kv: -kv[1])
                if abs(amount) >= 0.005
            }
            for resource, sources in sorted(
                by_resource.items(), key=lambda kv: _resource_sort(kv[0])
            )
        }
    return out


def _by_resource(by_source: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for source, amounts in by_source.items():
        if not isinstance(amounts, dict):
            continue
        for resource, amount in amounts.items():
            if isinstance(amount, int | float):
                out[resource][source] = out[resource].get(source, 0) + amount
    return out


# --- pops and planets ---------------------------------------------------------------


def owned_colonies(ctx: Context, country: dict[str, Any]) -> list[tuple[int, dict, dict]]:
    """(planet id, planet, colony) for each colony the empire owns; owned_planets holds
    colony ids."""
    out = []
    for colony_id in as_list(country.get("owned_planets")):
        colony = ctx.colonies.get(colony_id)
        if not colony:
            continue
        planet_id = block(colony.get("carrier")).get("reference")
        planet = ctx.planets.get(planet_id)
        if planet is not None:
            out.append((planet_id, planet, colony))
    return out


def pops(ctx: Context, colonies: list[tuple[int, dict, dict]]) -> dict[str, Any]:
    pop_groups = ctx.table("pop_groups")
    by_category: Counter[str] = Counter()
    by_species: Counter[int] = Counter()
    for _, _, colony in colonies:
        for group_id in as_list(colony.get("pop_groups")):
            group = pop_groups.get(group_id)
            if not group:
                continue
            size = group.get("size", 0)
            by_category[group["key"]["category"]] += size
            by_species[group["key"]["species"]] += size
    species_db = block(ctx.g.get("species_db"))
    return {
        "total": sum(by_category.values()),
        "unemployed": sum(colony.get("civilian", 0) for _, _, colony in colonies),
        "by_stratum": {
            ctx.label(cat, f"pop_cat_{cat}", cat): size for cat, size in by_category.most_common()
        },
        "by_species": {
            ctx.name(species_db[sid]["name"]) if sid in species_db else f"species {sid}": size
            for sid, size in by_species.most_common()
        },
    }


def _jobs(ctx: Context, colony: dict[str, Any]) -> list[dict[str, Any]]:
    pop_jobs = ctx.table("pop_jobs")
    jobs = []
    for job_id in as_list(colony.get("pop_jobs")):
        job = pop_jobs.get(job_id)
        if not job or job.get("max_workforce", -1) < 0:
            continue  # placeholder jobs (-1) exist on every planet and hold nobody
        workforce = max(job.get("workforce", 0), 0)
        maximum = job["max_workforce"]
        jobs.append(
            {
                "job": job["type"],
                "label": ctx.label(job["type"], f"job_{job['type']}"),
                "workforce": rounded(workforce),
                "max": rounded(maximum),
                "open": rounded(max(maximum - workforce, 0)),
            }
        )
    return jobs


def planet_summary(
    ctx: Context, planet_id: int, planet: dict, colony: dict, max_districts: dict[str, Any]
) -> dict[str, Any]:
    system = ctx.system_of(planet)
    jobs = _jobs(ctx, colony)
    districts = {}
    for district_id in as_list(colony.get("districts")):
        district = ctx.g["districts"].get(district_id)
        if not isinstance(district, dict):
            continue
        kind = district["type"]
        entry = districts.setdefault(kind, {"built": 0})
        entry["built"] += district.get("level", 0)
    for kind, maximum in max_districts.items():
        entry = districts.setdefault(kind, {"built": 0})
        entry["max"] = maximum
    for kind in districts:
        ctx.district_labels[kind] = ctx.label(kind)
    designation = colony.get("final_designation") or colony.get("designation")
    return {
        "id": planet_id,
        "name": ctx.name(planet["name"]),
        "system": ctx.name(system["name"]),
        "class": ctx.label(planet["planet_class"]),
        "size": planet.get("planet_size"),
        "designation": ctx.label(designation) if designation else None,
        "sector": _sector_name(ctx, system),
        "pops": colony.get("num_sapient_pops", 0),
        "unemployed": colony.get("civilian", 0),
        "open_jobs": rounded(sum(job["open"] for job in jobs)),
        "stability": rounded(colony.get("stability", 0), 1),
        "free_housing": rounded(colony.get("free_housing", 0), 1),
        "districts": districts,
    }


def planet_detail(ctx: Context, planet_id: int, planet: dict, colony: dict) -> dict[str, Any]:
    buildings_table = ctx.table("buildings")
    buildings = Counter()
    for building_id in as_list(colony.get("buildings_cache")):
        building = buildings_table.get(building_id)
        if building:
            buildings[building["type"]] += 1
    deposits_table = ctx.table("deposit")
    deposit_defs = ctx.game.category("deposits")
    deposits = []
    for deposit_id in as_list(planet.get("deposits")):
        deposit = deposits_table.get(deposit_id)
        if not deposit:
            continue
        kind = deposit["type"]
        category = str(deposit_defs.get(kind, {}).get("category", ""))
        deposits.append(
            {
                "deposit": kind,
                "label": ctx.label(kind),
                "blocker": "blocker" in category,
            }
        )
    return {
        "free_amenities": rounded(colony.get("free_amenities", 0), 1),
        "crime": rounded(colony.get("crime", 0), 1),
        "jobs": _jobs(ctx, colony),
        "buildings": [
            {"building": kind, "label": ctx.label(kind), "count": count}
            for kind, count in buildings.items()
        ],
        "deposits": deposits,
        "produces": {k: rounded(v) for k, v in block(colony.get("produces")).items()},
        "upkeep": {k: rounded(v) for k, v in block(colony.get("upkeep")).items()},
        "planet_modifiers": [
            ctx.label(m) for m in as_list(planet.get("planet_modifier")) if isinstance(m, str)
        ],
    }


def _sector_name(ctx: Context, system: dict[str, Any]) -> str | None:
    sector_id = system.get("sector")
    sector = ctx.table("sectors").get(sector_id) if sector_id is not None else None
    sectors = block(ctx.g.get("sectors"))
    if sector is None and isinstance(sectors, dict) and "sectors" in sectors:
        sector = sectors["sectors"].get(sector_id)
    if not sector or "name" not in sector:
        return None
    return ctx.name(sector["name"])


# --- room for growth -----------------------------------------------------------------

RURAL = {
    "generator": "district_generator",
    "mining": "district_mining",
    "farming": "district_farming",
}
# Resources the room section counts open jobs for; others are left out to keep the extract small.
JOB_OUTPUTS = (
    "energy", "minerals", "food", "alloys", "consumer_goods", "unity", "trade",
    "physics_research", "society_research", "engineering_research",
)  # fmt: skip


def job_output(definition: Any) -> str | None:
    """The resource a job is for: the largest positive amount in its first `produces` block,
    the one without a special trigger in the game files (Technician: energy, Physicist:
    physics_research). Jobs that produce nothing (soldiers, amenity jobs) have none."""
    if not isinstance(definition, dict):
        return None
    produces = (
        definition.get("resources", {}).get("produces")
        if isinstance(definition.get("resources"), dict)
        else None
    )
    blocks = produces if isinstance(produces, list) else [produces]
    first = next((b for b in blocks if isinstance(b, dict)), None)
    if not first:
        return None
    amounts = {
        k: v
        for k, v in first.items()
        if isinstance(v, int | float) and not isinstance(v, bool) and v > 0
    }
    return max(amounts, key=lambda k: amounts[k]) if amounts else None


# Job functions the room section counts open jobs for, by the tags the game gives its jobs
# (`tags` in common/pop_jobs): amenity jobs carry `amenities`, order jobs `soldier` or `enforcer`.
# Bureaucrats add stability only behind triggers and carry neither tag, so the order count can
# miss open places and only its non-zero values are reliable.
JOB_FUNCTION_TAGS = {
    "amenities": ("amenities",),
    "order": ("soldier", "enforcer"),
}


def job_functions(definition: Any) -> set[str]:
    """The functions (keys of JOB_FUNCTION_TAGS) a job definition serves, by its `tags`."""
    if not isinstance(definition, dict):
        return set()
    tags = definition.get("tags")
    tags = set(tags) if isinstance(tags, list) else set()
    return {name for name, wanted in JOB_FUNCTION_TAGS.items() if tags & set(wanted)}


def _slots_free(slots_by_planet: list[dict[str, Any]], family: str | None) -> int | None:
    """Free building slots over the planets, all zones or those that admit a building of `family`.
    None when the family has no buildable building, or when the sum is 0 but a zone of some planet
    is not computed (its slots may be free)."""
    total = 0
    for slots in slots_by_planet:
        if family is None:
            total += slots["free"]
        else:
            free = slots["free_by_family"][family]
            if free is None:
                return None
            total += free
    if total == 0 and any(slots["unsupported"] for slots in slots_by_planet):
        return None
    return total


def room(
    ctx: Context,
    planets: list[dict[str, Any]],
    colonies: list[tuple[int, dict, dict]],
    planet_slots: list[dict[str, Any]],
    starbase_slots: dict[str, Any],
):
    """Free places to grow into, summed over the empire's planets: district slots in all and per
    rural type (a type's free places never exceed the planet's free slots), and open jobs by the
    resource they produce and by the function they serve (amenities, order), plus free housing
    (planets over capacity count 0, so a crowded planet does not hide a free one), and free
    building slots in all zones and by building family (`planet_slots`, computed/building_slots.py),
    and free module and building slots of the starbases (`starbase_slots`,
    computed/starbase_slots.py).
    Lets the Mechanics Graph check "no free slot" Obstacles. `by_planet` repeats the free places
    planet by planet (columns named like the metrics' `by_planet` paths), so an Obstacle about the whole empire can name the planets it concerns."""
    districts_free = 0
    by_type = dict.fromkeys(RURAL, 0)
    slots_of = {pid: slots for (pid, _, _), slots in zip(colonies, planet_slots, strict=True)}
    by_planet = []
    for planet in planets:
        built = sum(d.get("built", 0) for d in planet["districts"].values())
        planet_room = max(0, int(planet["district_limit"]) - built)
        districts_free += planet_room
        type_rooms = {}
        for name, kind in RURAL.items():
            entry = planet["districts"].get(kind)
            if entry is None or "max" not in entry:
                continue
            maximum = entry["max"]
            type_room = planet_room if maximum == "uncapped" else max(0, maximum - entry["built"])
            type_rooms[name] = min(type_room, planet_room)
            by_type[name] += type_rooms[name]
        slots = slots_of[planet["id"]]
        by_planet.append(
            {
                "planet": planet["name"],
                "districts_free": planet_room,
                **{f"district_types_free.{name}": type_rooms.get(name, 0) for name in RURAL},
                # None where the planet's free slots are not known (a zone that is not computed)
                "building_slots_free": None
                if slots["unsupported"] and not slots["free"]
                else slots["free"],
                **{
                    f"building_slots_free_by_family.{family}": free
                    for family, free in slots["free_by_family"].items()
                },
                "housing_free": rounded(max(planet["free_housing"], 0), 1),
            }
        )
    job_defs = ctx.game.category("pop_jobs")
    jobs_table = ctx.table("pop_jobs")
    open_jobs = dict.fromkeys(JOB_OUTPUTS, 0)
    open_by_function = dict.fromkeys(JOB_FUNCTION_TAGS, 0)
    for _, _, colony in colonies:
        for job_id in as_list(colony.get("pop_jobs")):
            job = jobs_table.get(job_id)
            if not job or job.get("max_workforce", -1) < 0:
                continue
            open_places = max(job["max_workforce"] - max(job.get("workforce", 0), 0), 0)
            output = job_output(job_defs.get(job["type"]))
            if output in open_jobs:
                open_jobs[output] += open_places
            for function in job_functions(job_defs.get(job["type"])):
                open_by_function[function] += open_places
    return {
        "building_slots_free": _slots_free(planet_slots, None),
        "building_slots_free_by_family": {
            family: _slots_free(planet_slots, family)
            for family in (planet_slots[0]["free_by_family"] if planet_slots else {})
        },
        "starbase_slots": starbase_slots,
        "districts_free": districts_free,
        "district_types_free": by_type,
        # a table (columns, one row per planet), or the extract grows by a tenth
        "by_planet": {
            "columns": list(by_planet[0]) if by_planet else [],
            "rows": [list(entry.values()) for entry in by_planet],
        },
        "open_jobs_by_output": {k: rounded(v) for k, v in open_jobs.items()},
        "open_jobs_by_function": {k: rounded(v) for k, v in open_by_function.items()},
        "housing_free": rounded(sum(max(p["free_housing"], 0) for p in planets), 1),
    }


# --- progression --------------------------------------------------------------------


def progression(ctx: Context, country: dict[str, Any]) -> dict[str, Any]:
    tech = block(country.get("tech_status"))
    in_progress = []
    for area in ("physics", "society", "engineering"):
        for item in as_list(tech.get(f"{area}_queue"))[:1]:
            in_progress.append(
                {
                    "area": area,
                    "technology": ctx.label(item["technology"]),
                    "progress": rounded(item.get("progress", 0)),
                }
            )
    government = block(country.get("government"))
    return {
        "traditions": [ctx.label(t) for t in as_list(country.get("traditions"))],
        "tradition_trees": [ctx.label(t) for t in as_list(country.get("tradition_categories"))],
        "ascension_perks": [ctx.label(p) for p in as_list(country.get("ascension_perks"))],
        "edicts": [
            ctx.label(e["edict"], f"edict_{e['edict']}", e["edict"])
            for e in as_list(country.get("edicts"))
        ],
        "policies": {
            ctx.label(p["policy"], f"policy_{p['policy']}", p["policy"]): ctx.label(p["selected"])
            for p in as_list(country.get("active_policies"))
        },
        "technologies_researched": len(as_list(tech.get("technology"))),
        "research_in_progress": in_progress,
        "government": {
            "authority": ctx.label(government["authority"]) if "authority" in government else None,
            "civics": [ctx.label(c) for c in as_list(government.get("civics"))],
            "origin": ctx.label(government["origin"]) if "origin" in government else None,
            "ethics": [ctx.label(e) for e in as_list(block(country.get("ethos")).get("ethics"))],
        },
    }


# --- military -----------------------------------------------------------------------


def fleets(ctx: Context, country_id: int, country: dict[str, Any]) -> list[dict[str, Any]]:
    fleet_table = ctx.table("fleet")
    ships = ctx.table("ships")
    designs = ctx.table("ship_design")
    ship_sizes = ctx.game.category("ship_sizes")
    out = []
    for entry in as_list(block(country.get("fleets_manager")).get("owned_fleets")):
        fleet = fleet_table.get(entry["fleet"])
        if not fleet or fleet.get("ship_class") not in (None, "shipclass_military"):
            continue
        if block(fleet.get("properties")).get("station") == "yes" or fleet.get("civilian") == "yes":
            continue
        composition: Counter[str] = Counter()
        capacity = 0.0
        for ship_id in as_list(fleet.get("ships")):
            ship = ships.get(ship_id)
            implementation = block(ship.get("ship_design_implementation")) if ship else {}
            design = designs.get(implementation.get("design"))
            stages = as_list(design.get("growth_stages")) if design else []
            stage = min(implementation.get("growth_stage", 0), len(stages) - 1)
            size = stages[stage].get("ship_size") if stages else None
            if size:
                composition[size] += 1
                # naval capacity a ship takes is its size's size_multiplier (common/ship_sizes)
                capacity += ship_sizes.get(size, {}).get("size_multiplier", 0)
        if not composition and fleet.get("military_power", 0) <= 0:
            continue
        out.append(
            {
                "id": entry["fleet"],
                "name": ctx.name(fleet["name"]),
                "military_power": rounded(fleet.get("military_power", 0), 0),
                "ships": sum(composition.values()),
                "naval_capacity_used": rounded(capacity),
                "composition": {ctx.label(size): n for size, n in composition.most_common()},
            }
        )
    out.sort(key=lambda f: -f["military_power"])
    return out


def wars(ctx: Context, country_id: int) -> list[dict[str, Any]]:
    out = []
    for war in ctx.table("war").values():
        attackers = [a["country"] for a in as_list(war.get("attackers"))]
        defenders = [d["country"] for d in as_list(war.get("defenders"))]
        if country_id not in attackers and country_id not in defenders:
            continue
        we_attack = country_id in attackers
        goal_key = "attacker_war_goal" if we_attack else "defender_war_goal"
        their_goal_key = "defender_war_goal" if we_attack else "attacker_war_goal"
        out.append(
            {
                "name": ctx.name(war["name"]),
                "start_date": war.get("start_date"),
                "side": "attacker" if we_attack else "defender",
                "attackers": [ctx.country_name(c) for c in attackers],
                "defenders": [ctx.country_name(c) for c in defenders],
                "our_war_exhaustion": rounded(
                    war.get(
                        "attacker_war_exhaustion" if we_attack else "defender_war_exhaustion", 0
                    )
                ),
                "their_war_exhaustion": rounded(
                    war.get(
                        "defender_war_exhaustion" if we_attack else "attacker_war_exhaustion", 0
                    )
                ),
                "our_war_goal": _war_goal(ctx, war.get(goal_key)),
                "their_war_goal": _war_goal(ctx, war.get(their_goal_key)),
            }
        )
    return out


def _war_goal(ctx: Context, goal: Any) -> str | None:
    if not isinstance(goal, dict) or "type" not in goal:
        return None
    return ctx.label(goal["type"], f"war_goal_{goal['type']}", goal["type"])


# --- timeline -----------------------------------------------------------------------


def timeline(ctx: Context, country: dict[str, Any], since: str | None = None) -> list[dict]:
    out = []
    for event in as_list(country.get("timeline_events")):
        definition = event.get("definition", "")
        if definition == "timeline_event_year":
            continue
        if since and event.get("date", "") < since:
            continue
        key = definition.upper()
        candidates = [key, f"{key}_TITLE", definition]
        if definition in ctx.game.timeline_texts:
            candidates.insert(0, ctx.game.timeline_texts[definition])
        entry = {"date": event.get("date"), "event": ctx.label(definition, *candidates)}
        targets = []
        for kind, ref in zip(as_list(event.get("types")), as_list(event.get("data")), strict=False):
            name = _target_name(ctx, kind, ref)
            if name:
                targets.append(name)
        if targets:
            entry["involves"] = targets
        out.append(entry)
    return out


def _target_name(ctx: Context, kind: str, ref: Any) -> str | None:
    if kind == "country":
        if ref in ctx.countries and "name" in ctx.countries[ref]:
            return ctx.country_name(ref)
        dead = ctx.table("dead_country").get(ref)
        return ctx.name(dead["name"]) if dead and "name" in dead else None
    if kind == "planet":
        planet = ctx.planets.get(ref) or ctx.table("dead_planet").get(ref)
        return ctx.name(planet["name"]) if planet and "name" in planet else None
    if kind == "species":
        species = block(ctx.g.get("species_db")).get(ref)
        return ctx.name(species["name"]) if species and "name" in species else None
    if kind == "leader":
        leader = ctx.table("leaders").get(ref)
        if leader and "name" in leader:
            return ctx.name(leader["name"].get("full_names", leader["name"]))
    return None


# --- other empires -------------------------------------------------------------------


def intel_levels(ctx: Context) -> list[tuple[int, int, dict[str, int]]]:
    """(min intel, max intel, {category: level}) from common/intel_levels."""
    levels = []
    for definition in ctx.game.category("intel_levels").values():
        low, high = definition["intel"]
        categories = {
            key: value
            for key, value in definition.items()
            if key in ("government", "diplomacy", "economy", "technology", "military")
        }
        levels.append((low, high, categories))
    return sorted(levels)


def _contacts(ctx: Context, country_id: int, country: dict[str, Any]):
    """(id, country, relation) of every empire in contact."""
    for relation in as_list(block(country.get("relations_manager")).get("relation")):
        other_id = relation.get("country")
        other = ctx.countries.get(other_id)
        if relation.get("contact") != "yes" or not other or other_id == country_id:
            continue
        if other.get("type") not in (None, "default"):
            continue  # fauna, marauders' fleets, event countries
        yield other_id, other, relation


def known_empires(ctx: Context, country_id: int, country: dict[str, Any]) -> list[dict[str, Any]]:
    """Every empire in contact. 'visible' holds what the Tracked Empire's intel shows
    (Fair Play); 'full' holds the save's facts (God Mode)."""
    intel = {
        entry[0]: entry[1].get("intel", 0)
        for entry in as_list(block(country.get("intel_manager")).get("intel"))
        if isinstance(entry, list) and len(entry) == 2
    }
    levels = intel_levels(ctx)
    ours = country
    out = []
    for other_id, other, relation in _contacts(ctx, country_id, country):
        value = intel.get(other_id, 0)
        categories = next((c for low, high, c in levels if low <= value <= high), {})
        full = _empire_facts(ctx, other_id, other)
        visible = _visible_facts(full, categories, ours, other)
        out.append(
            {
                "country_id": other_id,
                "name": ctx.country_name(other_id),
                "player": ctx.player_by_country.get(other_id),
                "intel": value,
                "opinion": relation.get("relation_current"),
                "hostile": relation.get("hostile") == "yes",
                "shares_border": relation.get("borders") == "yes",
                "visible": visible,
                "full": _compact_full(full, visible),
            }
        )
    out.sort(key=lambda e: (e["player"] is None, -e["full"].get("military_power", 0)))
    return out


def empire_flags(ctx: Context, country_id: int, country: dict[str, Any]) -> dict[str, Any]:
    """Name to flag of every empire in contact (None for one without a flag). Kept out of the
    extract, which is at its size budget; the expansion carries it, so that a Solution Graph can
    name an empire on a node and show its flag."""
    return {
        ctx.country_name(i): _flag(other) for i, other, _ in _contacts(ctx, country_id, country)
    }


def _flag(country: dict[str, Any]) -> dict[str, Any] | None:
    """The empire's flag as the save describes it: `icon` and `background` as `category/file`
    under the game's `flags/`, and the three swatches that colour the background (slots 0 to 2,
    see flags/colors.txt). Public on the map, so it belongs to Fair Play. None when the save has none."""
    flag = block(country.get("flag"))
    icon, background = block(flag.get("icon")), block(flag.get("background"))
    colors = [c for c in as_list(flag.get("colors")) if isinstance(c, str)]
    if not (icon.get("file") and background.get("file")) or len(colors) < 3:
        return None
    return {
        "icon": f"{icon['category']}/{icon['file']}",
        "background": f"{background['category']}/{background['file']}",
        "colors": colors[:3],
    }


def _empire_facts(ctx: Context, country_id: int, country: dict[str, Any]) -> dict[str, Any]:
    government = block(country.get("government"))
    facts = {
        "military_power": rounded(country.get("military_power", 0), 0),
        "economy_power": rounded(country.get("economy_power", 0), 0),
        "tech_power": rounded(country.get("tech_power", 0), 0),
        "empire_size": country.get("empire_size"),
        "colonies": len(as_list(country.get("owned_planets"))),
        "fleet_size": country.get("fleet_size"),
        "authority": ctx.label(government["authority"]) if "authority" in government else None,
        "civics": [ctx.label(c) for c in as_list(government.get("civics"))],
        "ethics": [ctx.label(e) for e in as_list(block(country.get("ethos")).get("ethics"))],
        "origin": ctx.label(government["origin"]) if "origin" in government else None,
    }
    return facts


def _compact_full(full: dict[str, Any], visible: dict[str, Any]) -> dict[str, Any]:
    """God Mode facts minus what the visible part already says."""
    return {k: v for k, v in full.items() if visible.get(k) != v}


def _relative(ours: float, theirs: float) -> str:
    """Bands like the game's relative-power labels; thresholds are ours, not the game's."""
    if ours <= 0:
        return "unknown"
    ratio = theirs / ours
    if ratio < 0.5:
        return "much weaker"
    if ratio < 0.8:
        return "weaker"
    if ratio <= 1.25:
        return "similar"
    if ratio <= 2:
        return "stronger"
    return "much stronger"


def _visible_facts(
    full: dict[str, Any], categories: dict[str, int], ours: dict, theirs: dict
) -> dict[str, Any]:
    visible: dict[str, Any] = {}
    if categories.get("government", 0) >= 1:
        visible.update(authority=full["authority"], civics=full["civics"], ethics=full["ethics"])
    if categories.get("government", 0) >= 2:
        visible["origin"] = full["origin"]
    if categories.get("military", 0) >= 1:
        visible["relative_fleet"] = _relative(
            ours.get("military_power", 0), theirs.get("military_power", 0)
        )
    if categories.get("military", 0) >= 3:
        visible["military_power"] = full["military_power"]
    if categories.get("economy", 0) >= 1:
        visible["relative_economy"] = _relative(
            ours.get("economy_power", 0), theirs.get("economy_power", 0)
        )
    if categories.get("economy", 0) >= 4:
        visible["colonies"] = full["colonies"]
    if categories.get("technology", 0) >= 1:
        visible["relative_technology"] = _relative(
            ours.get("tech_power", 0), theirs.get("tech_power", 0)
        )
    return visible


__all__ = [
    "NO_ID",
    "economy",
    "economy_by_source",
    "empire_flags",
    "fleets",
    "known_empires",
    "owned_colonies",
    "planet_detail",
    "planet_summary",
    "pops",
    "progression",
    "timeline",
    "wars",
]
