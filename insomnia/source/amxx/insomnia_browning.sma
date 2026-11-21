#include <amxmodx>
#include <fakemeta>
#include <hamsandwich>
#include <reapi>

#define M2_MARKER 0x4d3242
#define M2_PRICE 12500
#define M2_CLIP 100
#define M2_RESERVE 200
#define M2_VIEW "models/insomnia/v_browning_m2.mdl"
#define M2_PLAYER "models/insomnia/p_browning_m2.mdl"
#define M2_WORLD "models/insomnia/w_browning_m2.mdl"
#define M2_SOUND "insomnia/m2_fire.wav"
#define HUD_WEAPON "weapon_insomnia_m2"

new g_weaponList, g_m249Event, g_beforeClip[33];
new bool:g_hud[33];

public plugin_precache()
{
    precache_model(M2_VIEW); precache_model(M2_PLAYER); precache_model(M2_WORLD);
    precache_sound(M2_SOUND);
    new const sounds[][] = { "m2_clipin", "m2_clipin2", "m2_cliplock", "m2_clipout",
        "m2_close", "m2_draw", "m2_foley1", "m2_foley2", "m2_open" };
    new path[64];
    for (new i; i < sizeof sounds; i++) {
        formatex(path, charsmax(path), "weapons/%s.wav", sounds[i]); precache_sound(path);
    }
    precache_generic("sprites/weapon_insomnia_m2.txt");
    precache_generic("sprites/insomnia/m2_hud.spr");
    register_forward(FM_PrecacheEvent, "event_precached", true);
}

public event_precached(type, const name[])
{
    if (equal(name, "events/m249.sc")) g_m249Event = get_orig_retval();
}

public plugin_init()
{
    register_plugin("Insomnia Browning M2", "1.0", "Insomnia project");
    g_weaponList = get_user_msgid("WeaponList");
    register_clcmd("buym2", "buy_m2");
    register_clcmd("m249", "buy_mg3");
    register_clcmd("say /m2", "buy_m2");
    register_clcmd(HUD_WEAPON, "select_m2");
    register_clcmd("menuselect", "classic_choice");
    register_message(get_user_msgid("ShowMenu"), "classic_menu");
    RegisterHam(Ham_Item_Deploy, "weapon_m249", "deploy_m2", true);
    RegisterHam(Ham_Item_AddToPlayer, "weapon_m249", "add_m2", true);
    RegisterHam(Ham_Item_Holster, "weapon_m249", "holster_m2", true);
    RegisterHam(Ham_Weapon_PrimaryAttack, "weapon_m249", "before_shot");
    RegisterHam(Ham_Weapon_PrimaryAttack, "weapon_m249", "after_shot", true);
    RegisterHam(Ham_Weapon_Reload, "weapon_m249", "reload_m2", true);
    RegisterHam(Ham_Weapon_WeaponIdle, "weapon_m249", "idle_m2");
    RegisterHam(Ham_Killed, "player", "reset_hud", true);
    RegisterHookChain(RG_CBaseEntity_FireBullets3, "m2_bullet");
    RegisterHookChain(RG_CBasePlayer_ResetMaxSpeed, "m2_speed", true);
    register_forward(FM_PlaybackEvent, "fire_event");
    register_forward(FM_SetModel, "world_model");
    register_forward(FM_UpdateClientData, "disable_prediction", true);
}

bool:is_m2(weapon)
{
    return weapon > MaxClients && pev_valid(weapon) == 2 && pev(weapon, pev_iuser4) == M2_MARKER;
}

public buy_m2(id)
{
    if (!is_user_alive(id)) return PLUGIN_HANDLED;
    new Float:buyTime = get_cvar_float("mp_buytime");
    if (!(get_member(id, m_signals, US_State) & _:SIGNAL_BUY) || get_member(id, m_bIsVIP)
        || get_member_game(m_bRoundTerminating)
        || (buyTime != -1.0 && get_gametime() - Float:get_member_game(m_fRoundStartTime) > buyTime * 60.0)) {
        client_print(id, print_center, "Browning M2: buy in your buy zone during buytime.");
        return PLUGIN_HANDLED;
    }
    if (get_member(id, m_bOwnsShield)) {
        client_print(id, print_center, "Drop your shield to buy the Browning M2.");
        return PLUGIN_HANDLED;
    }
    new owned = rg_find_weapon_bpack_by_name(id, "weapon_m249");
    if (is_m2(owned)) {
        client_print(id, print_center, "You already have a Browning M2.");
        return PLUGIN_HANDLED;
    }
    if (get_member(id, m_iAccount) < M2_PRICE) {
        client_print(id, print_center, "Browning M2 costs $%d.", M2_PRICE);
        return PLUGIN_HANDLED;
    }
    // CS carries one primary. Drop it first, preserving its identity and ammunition.
    rg_drop_items_by_slot(id, PRIMARY_WEAPON_SLOT);
    new weapon = rg_give_item(id, "weapon_m249", GT_APPEND);
    if (weapon <= 0) return PLUGIN_HANDLED;
    set_pev(weapon, pev_iuser4, M2_MARKER);
    set_member(weapon, m_Weapon_iClip, M2_CLIP);
    rg_set_user_bpammo(id, WEAPON_M249, M2_RESERVE);
    rg_add_account(id, -M2_PRICE);
    weapon_list(id, true);
    rg_switch_weapon(id, weapon);
    if (get_member(id, m_pActiveItem) == weapon) deploy_m2(weapon);
    client_print(id, print_chat, "[WW2] Browning M2 .50 purchased for $%d.", M2_PRICE);
    return PLUGIN_HANDLED;
}

public select_m2(id)
{
    new weapon = rg_find_weapon_bpack_by_name(id, "weapon_m249");
    if (is_user_alive(id) && is_m2(weapon)) rg_switch_weapon(id, weapon);
    return PLUGIN_HANDLED;
}

weapon_list(id, bool:custom)
{
    if (!is_user_connected(id)) return;
    g_hud[id] = custom;
    message_begin(MSG_ONE, g_weaponList, _, id);
    write_string(custom ? HUD_WEAPON : "weapon_m249");
    write_byte(3); write_byte(200); write_byte(255); write_byte(255);
    write_byte(0); write_byte(4); write_byte(CSW_M249); write_byte(0);
    message_end();
}

public add_m2(weapon, id)
{
    weapon_list(id, is_m2(weapon));
}

public deploy_m2(weapon)
{
    new id = get_member(weapon, m_pPlayer);
    if (!is_m2(weapon)) { if (g_hud[id]) weapon_list(id, false); return; }
    set_pev(id, pev_viewmodel2, M2_VIEW);
    set_pev(id, pev_weaponmodel2, M2_PLAYER);
    weapon_list(id, true);
    set_member(weapon, m_Weapon_flTimeWeaponIdle, 1.05);
    animation(id, 4);
    m2_speed(id);
}

public holster_m2(weapon)
{
    if (is_m2(weapon)) {
        new id = get_member(weapon, m_pPlayer);
        if (g_hud[id]) weapon_list(id, true);
    }
}

public reset_hud(id)
{
    if (g_hud[id]) weapon_list(id, false);
}

public client_putinserver(id) { g_hud[id] = false; g_beforeClip[id] = -1; }

public classic_menu()
{
    new text[512]; get_msg_arg_string(4, text, charsmax(text));
    if (contain(text, "BuyMachineGun") == -1) return PLUGIN_CONTINUE;
    set_msg_arg_int(1, ARG_SHORT, (1<<0)|(1<<1)|(1<<9));
    set_msg_arg_string(4, "Machine guns^n^n1. MG3 - $9500^n2. Browning M2 .50 - $12500^n^n0. Exit");
    return PLUGIN_CONTINUE;
}

public classic_choice(id)
{
    if (get_member(id, m_iMenu) != Menu_BuyMachineGun) return PLUGIN_CONTINUE;
    new key[4]; read_argv(1, key, charsmax(key));
    if (str_to_num(key) == 1) { buy_mg3(id); return PLUGIN_CONTINUE; }
    if (str_to_num(key) != 2) return PLUGIN_CONTINUE;
    set_member(id, m_iMenu, Menu_OFF);
    show_menu(id, 0, "^n", 1);
    return buy_m2(id);
}

public buy_mg3(id)
{
    if (!is_user_alive(id)) return PLUGIN_CONTINUE;
    new weapon = rg_find_weapon_bpack_by_name(id, "weapon_m249");
    if (!is_m2(weapon)) return PLUGIN_CONTINUE;
    new Float:buyTime = get_cvar_float("mp_buytime");
    if (!(get_member(id, m_signals, US_State) & _:SIGNAL_BUY) || get_member_game(m_bRoundTerminating)
        || (buyTime != -1.0 && get_gametime() - Float:get_member_game(m_fRoundStartTime) > buyTime * 60.0)
        || get_member(id, m_iAccount) < rg_get_weapon_info(WEAPON_M249, WI_COST)) return PLUGIN_CONTINUE;
    rg_drop_item(id, "weapon_m249");
    return PLUGIN_CONTINUE;
}

public before_shot(weapon)
{
    if (!is_m2(weapon)) return;
    new id = get_member(weapon, m_pPlayer);
    g_beforeClip[id] = get_member(weapon, m_Weapon_iClip);
}

public after_shot(weapon)
{
    if (!is_m2(weapon)) return;
    new id = get_member(weapon, m_pPlayer);
    if (get_member(weapon, m_Weapon_iClip) >= g_beforeClip[id]) return;
    new Float:timeBase = Float:get_member(weapon, m_Weapon_flNextPrimaryAttack)
        - Float:get_member(weapon, m_Weapon_flPrevPrimaryAttack);
    set_member(weapon, m_Weapon_flNextPrimaryAttack, timeBase + 0.100);
    set_member(weapon, m_Weapon_flNextSecondaryAttack, timeBase + 0.100);
    set_member(weapon, m_Weapon_flPrevPrimaryAttack, 0.100);
    set_member(weapon, m_Weapon_flTimeWeaponIdle, 1.4);
    set_pev(id, pev_effects, pev(id, pev_effects) | EF_MUZZLEFLASH);
    emit_sound(id, CHAN_WEAPON, M2_SOUND, VOL_NORM, ATTN_NORM, 0, PITCH_NORM);
    animation(id, random_num(1, 2));
}

public m2_bullet(id, Float:source[3], Float:direction[3], Float:spread,
    Float:distance, penetration, bullet, damage, Float:rangeModifier, attacker, bool:pistol, seed)
{
    if (id < 1 || id > MaxClients || !is_user_alive(id) || !is_m2(get_member(id, m_pActiveItem)))
        return HC_CONTINUE;
    SetHookChainArg(4, ATYPE_FLOAT, spread * 0.45);
    SetHookChainArg(6, ATYPE_INTEGER, 3);
    SetHookChainArg(8, ATYPE_INTEGER, 60);
    SetHookChainArg(9, ATYPE_FLOAT, 0.99);
    return HC_CONTINUE;
}

public reload_m2(weapon)
{
    if (!is_m2(weapon) || !get_member(weapon, m_Weapon_fInReload)) return;
    new id = get_member(weapon, m_pPlayer);
    set_member(id, m_flNextAttack, 6.1);
    set_member(weapon, m_Weapon_flTimeWeaponIdle, 6.15);
    animation(id, 3);
}

public idle_m2(weapon)
{
    if (!is_m2(weapon)) return HAM_IGNORED;
    if (Float:get_member(weapon, m_Weapon_flTimeWeaponIdle) <= 0.0) {
        animation(get_member(weapon, m_pPlayer), 0);
        set_member(weapon, m_Weapon_flTimeWeaponIdle, 5.0);
    }
    return HAM_SUPERCEDE;
}

public fire_event(flags, invoker, eventindex)
{
    if (eventindex == g_m249Event && invoker >= 1 && invoker <= MaxClients
        && is_user_alive(invoker) && is_m2(get_member(invoker, m_pActiveItem))) return FMRES_SUPERCEDE;
    return FMRES_IGNORED;
}

public world_model(ent, const model[])
{
    if (!pev_valid(ent) || !equal(model, "models/w_m249.mdl")) return FMRES_IGNORED;
    new classname[32]; pev(ent, pev_classname, classname, charsmax(classname));
    if (!equal(classname, "weaponbox")) return FMRES_IGNORED;
    new weapon = get_member(ent, m_WeaponBox_rgpPlayerItems, PRIMARY_WEAPON_SLOT);
    if (!is_m2(weapon)) return FMRES_IGNORED;
    engfunc(EngFunc_SetModel, ent, M2_WORLD);
    return FMRES_SUPERCEDE;
}

public m2_speed(id)
{
    if (is_user_alive(id) && !get_member_game(m_bFreezePeriod)
        && is_m2(get_member(id, m_pActiveItem))) set_pev(id, pev_maxspeed, 185.0);
}

public disable_prediction(id, sendWeapons, cd)
{
    if (is_user_alive(id) && is_m2(get_member(id, m_pActiveItem)))
        set_cd(cd, CD_flNextAttack, get_gametime() + 0.05);
    return FMRES_IGNORED;
}

animation(id, sequence)
{
    set_pev(id, pev_weaponanim, sequence);
    message_begin(MSG_ONE, SVC_WEAPONANIM, _, id);
    write_byte(sequence); write_byte(0); message_end();
}
