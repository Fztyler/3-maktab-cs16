#include <amxmodx>
#include <hamsandwich>
#include <reapi>
#include <fakemeta>
#include <xs>

const Float:REVOLVER_CYCLE = 0.120;
const Float:MP40_CYCLE = 0.125;
const Float:MG3_CYCLE = 0.050;
const Float:MG3_BURST_PAUSE = 0.24;
const MG3_BURST_SHOTS = 4;
const MG3_MAX_WALLS = 6;
const Float:MG3_DAMAGE_FACTOR = 1.50;
const Float:MG3_WALL_EXIT_STEP = 2.0;
const Float:MG3_WALL_EXIT_LIMIT = 384.0;
const Float:MG3_WALL_DAMAGE_FACTOR = 0.85;
const Float:GALIL_CYCLE = 0.115;
const Float:FAMAS_CYCLE = 0.105;
const Float:FAMAS_BURST_CYCLE = 0.70;
const Float:HE_RADIUS_SCALE = 1.25;
const Float:TRENCH_GUN_DAMAGE_SCALE = 1.50;
const VEST_PRICE = 900;
const VEST_HELMET_PRICE = 1400;
const STOCK_VEST_PRICE = 650;
const STOCK_VEST_HELMET_PRICE = 1000;

enum _:PriceEntry
{
    WeaponIdType:PriceWeapon,
    PriceAmount,
    PriceName[24]
};

new const WEAPON_PRICES[][PriceEntry] =
{
    { WEAPON_M249, 9500, "MG3 (M249)" },
    { WEAPON_M3, 4000, "Trench Gun (M3)" },
    { WEAPON_GALIL, 2900, "Galil" },
    { WEAPON_FAMAS, 3150, "FAMAS" },
    { WEAPON_AK47, 3500, "AK-47 slot" },
    { WEAPON_M4A1, 4100, "M4A1 slot" },
    { WEAPON_AUG, 4750, "AUG slot" },
    { WEAPON_SG552, 4750, "SG552 slot" }
};

new g_primaryWeapon[MAX_PLAYERS + 1];
new g_primaryClip[MAX_PLAYERS + 1];
new Float:g_initialPunch[MAX_PLAYERS + 1][3];
new Float:g_mg3LastShot[MAX_PLAYERS + 1];
new g_mg3BurstShots[MAX_PLAYERS + 1];
new bool:g_mg3TightShot[MAX_PLAYERS + 1];
new g_stockWeaponPrices[sizeof WEAPON_PRICES];
new bool:g_pricesInstalled;
new g_stockArmorCharge[MAX_PLAYERS + 1];
new g_armorCharge[MAX_PLAYERS + 1];
new Float:g_armorPurchaseTime[MAX_PLAYERS + 1];
new g_heExplosion;
new Float:g_heOriginalDamage;
new bool:g_extendedMg3;
new bool:g_mg3Tracking[MAX_PLAYERS + 1];
new g_mg3Walls[MAX_PLAYERS + 1];
new Float:g_mg3Source[MAX_PLAYERS + 1][3];
const BROWNING_MARK = 0x4D3242;

new g_trenchShooter;
new Float:g_trenchSource[3];
new Float:g_trenchDirection[3];
new Float:g_trenchDistance;

public plugin_init()
{
    register_plugin("WW2 Weapon Balance", "1.1.8", "Codex");

    new map[32];
    get_mapname(map, charsmax(map));
    if (containi(map, "maktab") != -1 && !equali(map, "de_maktab_training"))
    {
        return;
    }

    RegisterHookChain(RG_CBaseEntity_FireBullets3, "modify_shot");
    g_extendedMg3 = equali(map, "de_dust2") || equali(map, "de_maktab_training") || equali(map, "de_insomnia_project_t");
    if (g_extendedMg3)
    {
        register_forward(FM_TraceLine, "continue_mg3_trace", true);
        RegisterHookChain(RG_CBasePlayer_TraceAttack, "scale_mg3_wall_damage");
        RegisterHookChain(RG_CBaseEntity_FireBullets3, "finish_mg3_shot", true);
    }
    RegisterHookChain(RG_CBaseEntity_FireBuckshots, "modify_buckshot");
    RegisterHookChain(RG_CBaseEntity_FireBuckshots, "finish_buckshot", true);
    register_forward(FM_TraceLine, "tighten_trench_trace");
    register_timing_hooks("weapon_deagle");
    register_timing_hooks("weapon_ump45");
    register_timing_hooks("weapon_m249");
    register_timing_hooks("weapon_galil");
    register_timing_hooks("weapon_famas");
    RegisterHookChain(RG_CBasePlayer_Spawn, "reset_burst", true);
    RegisterHookChain(RG_CBasePlayer_HasRestrictItem, "check_armor_purchase");
    RegisterHookChain(RG_CBasePlayer_AddAccount, "charge_armor_purchase", true);
    RegisterHookChain(RG_CGrenade_ExplodeHeGrenade, "increase_he_radius");
    RegisterHookChain(RG_CGrenade_ExplodeHeGrenade, "clear_he_explosion", true);
    RegisterHookChain(RG_CBasePlayer_TakeDamage, "normalize_he_damage");
    register_clcmd("ww2_prices", "show_prices");

    for (new i = 0; i < sizeof WEAPON_PRICES; i++)
    {
        new WeaponIdType:weapon = WEAPON_PRICES[i][PriceWeapon];
        g_stockWeaponPrices[i] = rg_get_weapon_info(weapon, WI_COST);
        rg_set_weapon_info(weapon, WI_COST, WEAPON_PRICES[i][PriceAmount]);
    }
    g_pricesInstalled = true;
}

public plugin_end()
{
    if (!g_pricesInstalled)
    {
        return;
    }
    for (new i = 0; i < sizeof WEAPON_PRICES; i++)
    {
        new WeaponIdType:weapon = WEAPON_PRICES[i][PriceWeapon];
        if (rg_get_weapon_info(weapon, WI_COST) == WEAPON_PRICES[i][PriceAmount])
        {
            rg_set_weapon_info(weapon, WI_COST, g_stockWeaponPrices[i]);
        }
    }
}

register_timing_hooks(const classname[])
{
    RegisterHam(Ham_Weapon_PrimaryAttack, classname, "before_primary");
    RegisterHam(Ham_Weapon_PrimaryAttack, classname, "after_primary", true);
}

public reset_burst(id)
{
    g_primaryWeapon[id] = 0;
    g_mg3BurstShots[id] = 0;
    g_mg3LastShot[id] = 0.0;
    g_mg3TightShot[id] = false;
    g_armorCharge[id] = 0;
}

public modify_shot(id, Float:source[3], Float:direction[3], Float:spread,
    Float:distance, penetration, bullet, damage, Float:rangeModifier, attacker,
    bool:pistol, seed)
{
    if (id < 1 || id > MaxClients || !is_user_alive(id))
    {
        return HC_CONTINUE;
    }

    new weapon = get_member(id, m_pActiveItem);
    if (weapon <= 0 || pev(weapon, pev_iuser4) == BROWNING_MARK)
    {
        return HC_CONTINUE;
    }

    switch (WeaponIdType:get_member(weapon, m_iId))
    {
        case WEAPON_P228: SetHookChainArg(4, ATYPE_FLOAT, spread * 0.35);
        case WEAPON_UMP45:
        {
            SetHookChainArg(4, ATYPE_FLOAT, spread * 0.10);
            // Shift damage falloff to 1.4 times the original distance.
            SetHookChainArg(9, ATYPE_FLOAT, floatpower(rangeModifier, 1.0 / 1.4));
        }
        case WEAPON_MP5N: SetHookChainArg(4, ATYPE_FLOAT, spread * 0.10);
        case WEAPON_MAC10: SetHookChainArg(8, ATYPE_INTEGER, floatround(float(damage) * 1.10));
        case WEAPON_M249:
        {
            if (g_extendedMg3)
            {
                g_mg3Tracking[id] = true;
                g_mg3Walls[id] = 0;
                xs_vec_copy(source, g_mg3Source[id]);
                SetHookChainArg(6, ATYPE_INTEGER, 1);
                SetHookChainArg(8, ATYPE_INTEGER, floatround(float(damage) * MG3_DAMAGE_FACTOR));
            }
            else
            {
                SetHookChainArg(6, ATYPE_INTEGER, MG3_MAX_WALLS + 1);
            }
            new Float:now = get_gametime();
            if (now - g_mg3LastShot[id] >= MG3_BURST_PAUSE)
            {
                g_mg3BurstShots[id] = 0;
            }
            g_mg3LastShot[id] = now;
            g_mg3TightShot[id] = (++g_mg3BurstShots[id] <= MG3_BURST_SHOTS);
            if (g_mg3TightShot[id])
            {
                SetHookChainArg(4, ATYPE_FLOAT, spread * 0.15);
            }
        }
    }
    return HC_CONTINUE;
}

public continue_mg3_trace(const Float:source[3], const Float:end[3], flags, id, originalTrace)
{
    if (id < 1 || id > MaxClients || !g_mg3Tracking[id] || flags != DONT_IGNORE_MONSTERS
        || get_distance_f(source, g_mg3Source[id]) > 0.1)
    {
        return FMRES_IGNORED;
    }
    g_mg3Tracking[id] = false;

    new Float:fraction;
    get_tr2(originalTrace, TR_flFraction, fraction);
    new cover = get_tr2(originalTrace, TR_pHit);
    if (fraction >= 1.0 || !is_mg3_cover(cover))
    {
        return FMRES_IGNORED;
    }

    new Float:aim[3], Float:entry[3], Float:exitPoint[3];
    xs_vec_sub(end, source, aim);
    new Float:distance = xs_vec_len(aim);
    xs_vec_normalize(aim, aim);
    get_tr2(originalTrace, TR_vecEndPos, entry);

    new trace = create_tr2();
    for (new walls = 1; walls <= MG3_MAX_WALLS; walls++)
    {
        new Float:remaining = distance - get_distance_f(source, entry);
        if (!find_mg3_cover_exit(id, cover, entry, aim, remaining, exitPoint, trace))
        {
            break;
        }

        engfunc(EngFunc_TraceLine, exitPoint, end, DONT_IGNORE_MONSTERS, id, trace);
        get_tr2(trace, TR_flFraction, fraction);
        if (fraction >= 1.0 || get_tr2(trace, TR_StartSolid))
        {
            break;
        }

        cover = get_tr2(trace, TR_pHit);
        get_tr2(trace, TR_vecEndPos, entry);
        if (cover >= 1 && cover <= MaxClients && is_user_alive(cover))
        {
            new Float:normal[3], Float:planeDistance;
            get_tr2(trace, TR_vecPlaneNormal, normal);
            get_tr2(trace, TR_flPlaneDist, planeDistance);
            set_tr2(originalTrace, TR_vecPlaneNormal, normal);
            set_tr2(originalTrace, TR_flPlaneDist, planeDistance);
            set_tr2(originalTrace, TR_vecEndPos, entry);
            set_tr2(originalTrace, TR_flFraction, get_distance_f(source, entry) / distance);
            set_tr2(originalTrace, TR_pHit, cover);
            set_tr2(originalTrace, TR_iHitgroup, get_tr2(trace, TR_iHitgroup));
            g_mg3Walls[id] = walls;
            break;
        }
        if (!is_mg3_cover(cover))
        {
            break;
        }
    }
    free_tr2(trace);
    return FMRES_IGNORED;
}

public scale_mg3_wall_damage(victim, id, Float:damage, Float:aim[3], trace, bits)
{
    if (id >= 1 && id <= MaxClients && g_mg3Walls[id])
    {
        new walls = g_mg3Walls[id];
        SetHookChainArg(3, ATYPE_FLOAT, damage * floatpower(MG3_WALL_DAMAGE_FACTOR, float(walls)));
        if (!is_user_bot(id))
        {
            client_print(id, print_console, "MG3: hit through %d wall(s).", walls);
        }
    }
    return HC_CONTINUE;
}

public finish_mg3_shot(id)
{
    if (id >= 1 && id <= MaxClients)
    {
        g_mg3Tracking[id] = false;
        g_mg3Walls[id] = 0;
    }
}

bool:is_mg3_cover(entity)
{
    if (entity <= 0)
    {
        return true;
    }
    if (entity <= MaxClients || !pev_valid(entity))
    {
        return false;
    }

    switch (get_entvar(entity, var_solid))
    {
        case SOLID_BSP: return true;
        case SOLID_BBOX:
        {
            new classname[32];
            get_entvar(entity, var_classname, classname, charsmax(classname));
            return equali(classname, "func_pushable") || equali(classname, "func_breakable");
        }
    }
    return false;
}

bool:find_mg3_cover_exit(id, entity, const Float:entry[3], const Float:aim[3],
    Float:remaining, Float:origin[3], trace)
{
    new bool:isBox = entity > MaxClients && pev_valid(entity) && get_entvar(entity, var_solid) == SOLID_BBOX;
    new Float:mins[3], Float:maxs[3];
    if (isBox)
    {
        get_entvar(entity, var_absmin, mins);
        get_entvar(entity, var_absmax, maxs);
    }

    new Float:limit = floatmin(remaining, MG3_WALL_EXIT_LIMIT);
    for (new Float:depth = MG3_WALL_EXIT_STEP; depth < limit; depth += MG3_WALL_EXIT_STEP)
    {
        for (new axis = 0; axis < 3; axis++)
        {
            origin[axis] = entry[axis] + aim[axis] * depth;
        }
        if (isBox && mins[0] <= origin[0] <= maxs[0] && mins[1] <= origin[1] <= maxs[1]
            && mins[2] <= origin[2] <= maxs[2])
        {
            continue;
        }
        engfunc(EngFunc_TraceHull, origin, origin, IGNORE_MONSTERS, HULL_POINT, id, trace);
        if (!get_tr2(trace, TR_StartSolid) && !get_tr2(trace, TR_AllSolid))
        {
            return true;
        }
    }
    return false;
}

public modify_buckshot(id, pellets, Float:source[3], Float:direction[3], Float:spread[3],
    Float:distance, tracerFrequency, damage, attacker)
{
    if (id < 1 || id > MaxClients || !is_user_alive(id))
    {
        return HC_CONTINUE;
    }
    new weapon = get_member(id, m_pActiveItem);
    if (weapon > 0 && WeaponIdType:get_member(weapon, m_iId) == WEAPON_M3)
    {
        g_trenchShooter = id;
        xs_vec_copy(source, g_trenchSource);
        xs_vec_copy(direction, g_trenchDirection);
        g_trenchDistance = distance * 1.80;
        SetHookChainArg(6, ATYPE_FLOAT, g_trenchDistance);
        SetHookChainArg(8, ATYPE_INTEGER, floatround(float(damage) * TRENCH_GUN_DAMAGE_SCALE));
    }
    return HC_CONTINUE;
}

public finish_buckshot(id)
{
    if (id == g_trenchShooter) g_trenchShooter = 0;
}

public tighten_trench_trace(const Float:start[3], const Float:end[3], flags, shooter, trace)
{
    if (!g_trenchShooter || shooter != g_trenchShooter || get_distance_f(start, g_trenchSource) > 0.01)
        return FMRES_IGNORED;

    new Float:pellet[3];
    xs_vec_sub(end, start, pellet);
    if (floatabs(xs_vec_dot(pellet, g_trenchDirection) - g_trenchDistance) > 1.0)
        return FMRES_IGNORED;

    // Narrow only the pellet's lateral offset. Keep the shot direction, distance and native damage flow.
    new Float:adjusted[3];
    for (new axis = 0; axis < 3; axis++)
        adjusted[axis] = start[axis] + pellet[axis] * 0.4 + g_trenchDirection[axis] * g_trenchDistance * 0.6;

    engfunc(EngFunc_TraceLine, start, adjusted, flags, shooter, trace);
    return FMRES_SUPERCEDE;
}

public before_primary(weapon)
{
    if (pev(weapon, pev_iuser4) == BROWNING_MARK) return HAM_IGNORED;

    new id = get_member(weapon, m_pPlayer);
    if (id < 1 || id > MaxClients || !is_user_alive(id))
    {
        return HAM_IGNORED;
    }

    g_primaryWeapon[id] = weapon;
    g_primaryClip[id] = get_member(weapon, m_Weapon_iClip);
    if (WeaponIdType:get_member(weapon, m_iId) == WEAPON_M249)
    {
        g_mg3TightShot[id] = false;
        get_entvar(id, var_punchangle, g_initialPunch[id]);
    }
    return HAM_IGNORED;
}

public after_primary(weapon)
{
    if (pev(weapon, pev_iuser4) == BROWNING_MARK) return HAM_IGNORED;

    new id = get_member(weapon, m_pPlayer);
    if (id < 1 || id > MaxClients || g_primaryWeapon[id] != weapon)
    {
        return HAM_IGNORED;
    }

    g_primaryWeapon[id] = 0;
    if (get_member(weapon, m_Weapon_iClip) >= g_primaryClip[id])
    {
        return HAM_IGNORED;
    }

    new Float:cycle;
    switch (WeaponIdType:get_member(weapon, m_iId))
    {
        case WEAPON_DEAGLE: cycle = REVOLVER_CYCLE;
        case WEAPON_UMP45: cycle = MP40_CYCLE;
        case WEAPON_GALIL: cycle = GALIL_CYCLE;
        case WEAPON_FAMAS:
        {
            new bool:burst = bool:(get_member(weapon, m_Weapon_iWeaponState) & WPNSTATE_FAMAS_BURST_MODE);
            cycle = burst ? FAMAS_BURST_CYCLE : FAMAS_CYCLE;
        }
        case WEAPON_M249:
        {
            cycle = MG3_CYCLE;
            if (g_mg3TightShot[id])
            {
                new Float:punch[3];
                get_entvar(id, var_punchangle, punch);
                for (new axis = 0; axis < 2; axis++)
                {
                    punch[axis] = g_initialPunch[id][axis] + (punch[axis] - g_initialPunch[id][axis]) * 0.72;
                }
                set_entvar(id, var_punchangle, punch);
            }
        }
        default: return HAM_IGNORED;
    }

    // ReGameDLL stores the previous cycle as a duration even when using absolute timers.
    new Float:timeBase = Float:get_member(weapon, m_Weapon_flNextPrimaryAttack)
        - Float:get_member(weapon, m_Weapon_flPrevPrimaryAttack);
    set_member(weapon, m_Weapon_flNextPrimaryAttack, timeBase + cycle);
    set_member(weapon, m_Weapon_flNextSecondaryAttack, timeBase + cycle);
    set_member(weapon, m_Weapon_flPrevPrimaryAttack, cycle);
    return HAM_IGNORED;
}

public check_armor_purchase(id, ItemID:item, ItemRestType:type)
{
    if (id < 1 || id > MaxClients || type != ITEM_TYPE_BUYING)
    {
        return HC_CONTINUE;
    }
    g_armorCharge[id] = 0;
    if (item != ITEM_KEVLAR && item != ITEM_ASSAULT)
    {
        return HC_CONTINUE;
    }

    new bool:fullArmor = Float:get_entvar(id, var_armorvalue) >= 100.0;
    new bool:helmet = ArmorType:get_member(id, m_iKevlar) == ARMOR_VESTHELM;
    if (fullArmor && (item == ITEM_KEVLAR || helmet))
    {
        return HC_CONTINUE;
    }

    new stockCost = STOCK_VEST_PRICE;
    new cost = VEST_PRICE;
    if (item == ITEM_ASSAULT && !helmet)
    {
        stockCost = fullArmor ? STOCK_VEST_HELMET_PRICE - STOCK_VEST_PRICE : STOCK_VEST_HELMET_PRICE;
        cost = fullArmor ? VEST_HELMET_PRICE - VEST_PRICE : VEST_HELMET_PRICE;
    }

    if (get_member(id, m_iAccount) < cost)
    {
        if (!is_user_bot(id) && !is_user_hltv(id))
        {
            client_print(id, print_center, "Armor costs $%d", cost);
        }
        SetHookChainReturn(ATYPE_BOOL, true);
        return HC_SUPERCEDE;
    }

    g_stockArmorCharge[id] = stockCost;
    g_armorCharge[id] = cost;
    g_armorPurchaseTime[id] = get_gametime();
    return HC_CONTINUE;
}

public charge_armor_purchase(id, amount, RewardType:reason, bool:trackChange)
{
    if (id >= 1 && id <= MaxClients && g_armorCharge[id] && reason == RT_PLAYER_BOUGHT_SOMETHING
        && amount == -g_stockArmorCharge[id] && g_armorPurchaseTime[id] == get_gametime())
    {
        new surcharge = g_armorCharge[id] - g_stockArmorCharge[id];
        g_armorCharge[id] = 0;
        rg_add_account(id, -surcharge, AS_ADD, true);
    }
    return HC_CONTINUE;
}

public increase_he_radius(grenade, trace, damageType)
{
    g_heExplosion = grenade;
    g_heOriginalDamage = get_entvar(grenade, var_dmg);
    set_entvar(grenade, var_dmg, g_heOriginalDamage * HE_RADIUS_SCALE);
    return HC_CONTINUE;
}

public normalize_he_damage(id, inflictor, attacker, Float:damage, damageType)
{
    if (g_heExplosion && inflictor == g_heExplosion)
    {
        SetHookChainArg(4, ATYPE_FLOAT, damage / HE_RADIUS_SCALE);
    }
    return HC_CONTINUE;
}

public clear_he_explosion(grenade, trace, damageType)
{
    if (grenade == g_heExplosion)
    {
        set_entvar(grenade, var_dmg, g_heOriginalDamage);
        g_heExplosion = 0;
    }
}

public show_prices(id)
{
    client_print(id, print_console, "WW2 shop prices");
    for (new i = 0; i < sizeof WEAPON_PRICES; i++)
    {
        client_print(id, print_console, "%s: $%d", WEAPON_PRICES[i][PriceName],
            rg_get_weapon_info(WEAPON_PRICES[i][PriceWeapon], WI_COST));
    }
    client_print(id, print_console, "Vest: $%d, vest + helmet: $%d, helmet upgrade: $%d",
        VEST_PRICE, VEST_HELMET_PRICE, VEST_HELMET_PRICE - VEST_PRICE);
    return PLUGIN_HANDLED;
}
