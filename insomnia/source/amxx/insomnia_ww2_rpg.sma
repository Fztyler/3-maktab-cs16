#include <amxmodx>
#include <fakemeta>
#include <hamsandwich>
#include <reapi>

#define RPG_PRICE 7000
#define RPG_AMMO 4
#define RPG_SPEED 3960.0
#define RPG_BLAST_RADIUS 360.0
#define RPG_MARKER 0x525047
#define CARRIER "weapon_smokegrenade"
#define ROCKET "insomnia_rpg_rocket"
#define HUD_WEAPON "weapon_insomnia_rpg"
#define RPG_VIEW "models/insomnia/v_rpg7.mdl"
#define RPG_PLAYER "models/insomnia/p_rpg7.mdl"
#define RPG_MODEL "models/insomnia/pg7_rocket.mdl"
#define RPG_FIRE "weapons/rocketfire1.wav"

new g_explosion, g_smoke, g_weaponList, g_buyTime;
new bool:g_rpgHud[33];

public plugin_precache()
{
    precache_model(RPG_VIEW);
    precache_model(RPG_PLAYER);
    precache_model(RPG_MODEL);
    precache_sound(RPG_FIRE);
    g_explosion = precache_model("sprites/zerogxplode.spr");
    g_smoke = precache_model("sprites/smoke.spr");
    precache_generic("sprites/weapon_insomnia_rpg.txt");
    precache_generic("sprites/insomnia/rpg7_hud.spr");
}

public plugin_init()
{
    register_plugin("Insomnia WW2 RPG", "1.4", "Map project");
    g_buyTime = get_cvar_pointer("mp_buytime");
    g_weaponList = get_user_msgid("WeaponList");
    register_clcmd("buyrpg", "buy_rpg");
    register_clcmd("say /rpg", "show_rpg_menu");
    register_clcmd("say_team /rpg", "show_rpg_menu");
    register_clcmd(HUD_WEAPON, "select_rpg");
    register_clcmd("menuselect", "classic_rpg_choice");
    register_message(get_user_msgid("ShowMenu"), "classic_rpg_menu");
    RegisterHam(Ham_Item_Deploy, CARRIER, "deploy_rpg", true);
    RegisterHam(Ham_Weapon_PrimaryAttack, CARRIER, "fire_rpg");
    RegisterHam(Ham_Weapon_WeaponIdle, CARRIER, "idle_rpg");
    RegisterHam(Ham_Killed, "player", "reset_hud", true);
    RegisterHookChain(RG_CSGameRules_RestartRound, "clear_rockets");
    RegisterHookChain(RG_CBasePlayer_GiveAmmo, "block_rocket_refill");
    RegisterHookChain(RG_CBasePlayer_HasRestrictItem, "hide_smoke_purchase");
    register_forward(FM_Think, "rocket_flight");
    register_forward(FM_UpdateClientData, "prevent_smoke_prediction", true);
}

bool:is_rpg(weapon)
{
    return weapon > MaxClients && pev_valid(weapon) == 2 && pev(weapon, pev_iuser4) == RPG_MARKER;
}

public hide_smoke_purchase(id, ItemID:item, ItemRestType:type)
{
    if (item != ITEM_SMOKEGRENADE || !is_rpg(rg_find_weapon_bpack_by_name(id, CARRIER)))
        return HC_CONTINUE;
    SetHookChainReturn(ATYPE_BOOL, true);
    return HC_SUPERCEDE;
}

public block_rocket_refill(id, amount, const ammoName[], maximum)
{
    if (!equali(ammoName, "SmokeGrenade") || !is_rpg(rg_find_weapon_bpack_by_name(id, CARRIER)))
        return HC_CONTINUE;
    SetHookChainReturn(ATYPE_INTEGER, -1);
    return HC_SUPERCEDE;
}

public classic_rpg_menu(message, destination, id)
{
    new text[512]; get_msg_arg_string(4, text, charsmax(text));
    if (contain(text, "BuyItem") == -1) return PLUGIN_CONTINUE;
    copy(text,charsmax(text),"Equipment^n1 Kevlar $900^n2 Kevlar+helmet $1400^n3 Flash $200^n4 HE $300^n5 Smoke $300^n6 NVG $1250^n");
    if(id>=1&&id<=MaxClients&&get_member(id,m_iTeam)==TEAM_CT)
        add(text,charsmax(text),"7 Defuse kit $200^n8 Shield $2200^n");
    add(text, charsmax(text), "9 RPG-7 $7000^n0 Exit^n");
    set_msg_arg_int(1, ARG_SHORT, get_msg_arg_int(1)|(1<<8));
    set_msg_arg_string(4, text);
    return PLUGIN_CONTINUE;
}

public classic_rpg_choice(id)
{
    if (get_member(id, m_iMenu) != Menu_BuyItem) return PLUGIN_CONTINUE;
    new key[4]; read_argv(1, key, charsmax(key));
    if (str_to_num(key) != 9) return PLUGIN_CONTINUE;
    set_member(id, m_iMenu, Menu_OFF);
    show_menu(id, 0, "^n", 1);
    return buy_rpg(id);
}

public show_rpg_menu(id)
{
    new menu = menu_create("WW2 Equipment", "rpg_menu_choice");
    menu_additem(menu, "RPG-7 (2 rockets) - $7000");
    menu_display(id, menu);
    return PLUGIN_HANDLED;
}

public rpg_menu_choice(id, menu, item)
{
    menu_destroy(menu);
    if (item == 0) buy_rpg(id);
    return PLUGIN_HANDLED;
}

public buy_rpg(id)
{
    if (!is_user_alive(id)) return PLUGIN_HANDLED;
    new Float:buyTime = get_pcvar_float(g_buyTime);
    if (!(get_member(id, m_signals, US_State) & _:SIGNAL_BUY) || get_member(id, m_bIsVIP)
        || get_member_game(m_bRoundTerminating)
        || (buyTime != -1.0 && get_gametime() - Float:get_member_game(m_fRoundStartTime) > 60.0 * buyTime)) {
        client_print(id, print_center, "RPG-7: buy during buytime in your team's buy zone.");
        return PLUGIN_HANDLED;
    }
    if (get_member(id, m_iAccount) < RPG_PRICE) {
        client_print(id, print_center, "RPG-7 costs $%d.", RPG_PRICE);
        return PLUGIN_HANDLED;
    }
    if (get_member(id, m_bOwnsShield)) {
        client_print(id, print_center, "Drop your shield to buy the RPG-7.");
        return PLUGIN_HANDLED;
    }

    new weapon = rg_find_weapon_bpack_by_name(id, CARRIER);
    if (is_rpg(weapon)) {
        client_print(id, print_center, "You already have an RPG-7.");
        return PLUGIN_HANDLED;
    }
    new savedSmoke = weapon > 0 ? rg_get_user_bpammo(id, WEAPON_SMOKEGRENADE) : 0;
    if (weapon <= 0) weapon = rg_give_item(id, CARRIER, GT_APPEND);
    if (weapon <= 0) return PLUGIN_HANDLED;

    set_pev(weapon, pev_iuser3, savedSmoke);
    set_pev(weapon, pev_iuser4, RPG_MARKER);
    rg_set_user_bpammo(id, WEAPON_SMOKEGRENADE, RPG_AMMO);
    rg_add_account(id, -RPG_PRICE);
    weapon_list(id, true);
    if (get_member(id, m_pActiveItem) == weapon) deploy_rpg(weapon);
    else rg_switch_weapon(id, weapon);
    client_print(id, print_chat, "[WW2] RPG-7 purchased for $%d (2 rockets).", RPG_PRICE);
    return PLUGIN_HANDLED;
}

public select_rpg(id)
{
    if (is_user_alive(id)) {
        new weapon = rg_find_weapon_bpack_by_name(id, CARRIER);
        if (is_rpg(weapon)) rg_switch_weapon(id, weapon);
    }
    return PLUGIN_HANDLED;
}

weapon_list(id, bool:rpg)
{
    g_rpgHud[id] = rpg;
    message_begin(MSG_ONE, g_weaponList, _, id);
    if (rpg) write_string(HUD_WEAPON);
    else write_string(CARRIER);
    write_byte(13);
    write_byte(rpg ? RPG_AMMO : rg_get_weapon_info(WEAPON_SMOKEGRENADE, WI_MAX_ROUNDS));
    write_byte(255);
    write_byte(255);
    write_byte(3);
    write_byte(3);
    write_byte(CSW_SMOKEGRENADE);
    write_byte(24);
    message_end();
}

public reset_hud(id)
{
    if (is_user_connected(id) && g_rpgHud[id]) weapon_list(id, false);
}

public client_putinserver(id)
{
    g_rpgHud[id] = false;
}

public deploy_rpg(weapon)
{
    if (!is_rpg(weapon)) return HAM_IGNORED;
    new id = get_member(weapon, m_pPlayer);
    set_pev(id, pev_viewmodel2, RPG_VIEW);
    set_pev(id, pev_weaponmodel2, RPG_PLAYER);
    set_member(weapon, m_Weapon_flTimeWeaponIdle, 1.1);
    weapon_list(id, true);
    animation(id, 5);
    return HAM_IGNORED;
}

public prevent_smoke_prediction(id, sendWeapons, cd)
{
    if (is_user_alive(id) && is_rpg(get_member(id, m_pActiveItem)))
        set_cd(cd, CD_flNextAttack, get_gametime() + 0.05);
    return FMRES_IGNORED;
}

public fire_rpg(weapon)
{
    if (!is_rpg(weapon)) return HAM_IGNORED;
    new id = get_member(weapon, m_pPlayer);
    if (!is_user_alive(id) || get_member(id, m_pActiveItem) != weapon) return HAM_SUPERCEDE;
    new ammo = rg_get_user_bpammo(id, WEAPON_SMOKEGRENADE);
    if (!ammo || get_member_game(m_bFreezePeriod)) return HAM_SUPERCEDE;

    new rocket = launch_rocket(id);
    if (rocket <= 0) return HAM_SUPERCEDE;

    rg_set_user_bpammo(id, WEAPON_SMOKEGRENADE, ammo - 1);
    set_member(weapon, m_Weapon_flNextPrimaryAttack, 3.0);
    set_member(weapon, m_Weapon_flTimeWeaponIdle, ammo == 1 ? 0.56 : 3.05);
    emit_sound(id, CHAN_WEAPON, RPG_FIRE, VOL_NORM, ATTN_NORM, 0, PITCH_NORM);
    animation(id, 3);
    if (ammo == 1) set_task(0.55, "remove_empty_rpg", weapon);
    else set_task(0.85, "reload_rpg", weapon);
    return HAM_SUPERCEDE;
}

public reload_rpg(weapon)
{
    if (!is_rpg(weapon)) return;
    new id = get_member(weapon, m_pPlayer);
    if (is_user_alive(id) && get_member(id, m_pActiveItem) == weapon) animation(id, 2);
}

public idle_rpg(weapon)
{
    if (!is_rpg(weapon)) return HAM_IGNORED;
    if (Float:get_member(weapon, m_Weapon_flTimeWeaponIdle) <= 0.0) {
        new id = get_member(weapon, m_pPlayer);
        animation(id, rg_get_user_bpammo(id, WEAPON_SMOKEGRENADE) ? 0 : 8);
        set_member(weapon, m_Weapon_flTimeWeaponIdle, 4.0);
    }
    return HAM_SUPERCEDE;
}

public remove_empty_rpg(weapon)
{
    if (!is_rpg(weapon)) return;
    new id = get_member(weapon, m_pPlayer);
    if (id < 1 || id > MaxClients || !is_user_connected(id)
        || rg_find_weapon_bpack_by_name(id, CARRIER) != weapon) return;
    new savedSmoke = pev(weapon, pev_iuser3);
    if (savedSmoke > 0) {
        set_pev(weapon, pev_iuser3, 0);
        set_pev(weapon, pev_iuser4, 0);
        rg_set_user_bpammo(id, WEAPON_SMOKEGRENADE, savedSmoke);
        if (get_member(id, m_pActiveItem) == weapon) ExecuteHamB(Ham_Item_Deploy, weapon);
    } else {
        rg_remove_item(id, CARRIER, true);
    }
    weapon_list(id, false);
}

animation(id, sequence)
{
    set_pev(id, pev_weaponanim, sequence);
    message_begin(MSG_ONE, SVC_WEAPONANIM, _, id);
    write_byte(sequence);
    write_byte(0);
    message_end();
}

launch_rocket(id)
{
    new rocket = rg_create_entity("info_target");
    if (rocket <= 0) return 0;

    new Float:eye[3], Float:view[3], Float:angles[3], Float:velocity[3];
    pev(id, pev_origin, eye);
    pev(id, pev_view_ofs, view);
    pev(id, pev_v_angle, angles);
    angle_vector(angles, ANGLEVECTOR_FORWARD, velocity);
    for (new axis = 0; axis < 3; axis++) {
        eye[axis] += view[axis];
        velocity[axis] *= RPG_SPEED;
    }
    angles[0] = -angles[0];

    set_pev(rocket, pev_classname, ROCKET);
    engfunc(EngFunc_SetModel, rocket, RPG_MODEL);
    set_pev(rocket, pev_owner, id);
    set_pev(rocket, pev_iuser1, get_user_userid(id));
    set_pev(rocket, pev_iuser2, RPG_MARKER);
    set_pev(rocket, pev_angles, angles);
    // Sweep the flight segment directly. This avoids the engine's global
    // velocity clamp without raising it for players, grenades or other entities.
    set_pev(rocket, pev_movetype, MOVETYPE_NONE);
    set_pev(rocket, pev_solid, SOLID_NOT);
    set_pev(rocket, pev_velocity, velocity);
    new Float:now=get_gametime();
    set_pev(rocket,pev_fuser1,now+4.0);
    set_pev(rocket,pev_fuser2,now);
    set_pev(rocket,pev_nextthink,now+0.001);
    engfunc(EngFunc_SetSize, rocket, Float:{0.0, 0.0, 0.0}, Float:{0.0, 0.0, 0.0});
    engfunc(EngFunc_SetOrigin, rocket, eye);

    message_begin(MSG_BROADCAST, SVC_TEMPENTITY);
    write_byte(TE_BEAMFOLLOW);
    write_short(rocket);
    write_short(g_smoke);
    write_byte(9);
    write_byte(4);
    write_byte(190);
    write_byte(186);
    write_byte(164);
    write_byte(150);
    message_end();
    return rocket;
}

bool:is_rocket(ent)
{
    return ent > MaxClients && pev_valid(ent) && pev(ent, pev_iuser2) == RPG_MARKER;
}

rocket_impact(rocket, other, Float:origin[3], const Float:velocity[3])
{
    for (new axis = 0; axis < 3; axis++) origin[axis] -= velocity[axis] * (8.0 / RPG_SPEED);

    new owner = pev(rocket, pev_owner);
    if (owner < 1 || owner > MaxClients || !is_user_connected(owner)
        || get_user_userid(owner) != pev(rocket, pev_iuser1)) owner = 0;

    set_pev(rocket, pev_solid, SOLID_NOT);
    engfunc(EngFunc_MessageBegin, MSG_PVS, SVC_TEMPENTITY, origin, 0);
    write_byte(TE_EXPLOSION);
    for (new axis = 0; axis < 3; axis++) engfunc(EngFunc_WriteCoord, origin[axis]);
    write_short(g_explosion);
    write_byte(20);
    write_byte(15);
    write_byte(0);
    message_end();

    // A direct hit opens one heavy infill panel; the concrete frame is world geometry.
    set_pev(rocket, pev_iuser3, other);
    if (other > 0 && pev_valid(other) && owner > 0)
        ExecuteHamB(Ham_TakeDamage, other, rocket, owner, 1200.0, DMG_BLAST);
    rg_dmg_radius(origin, rocket, owner, 160.0, RPG_BLAST_RADIUS, CLASS_NONE, DMG_BLAST);
    kill_rocket(rocket);
}

kill_rocket(rocket)
{
    set_pev(rocket,pev_iuser2,0);
    set_pev(rocket,pev_flags,pev(rocket,pev_flags)|FL_KILLME);
}

public rocket_flight(rocket)
{
    if (!is_rocket(rocket)) return FMRES_IGNORED;
    new Float:now=get_gametime();
    new Float:expires,Float:last;
    pev(rocket,pev_fuser1,expires);
    pev(rocket,pev_fuser2,last);
    if(now>=expires){
        kill_rocket(rocket);
        return FMRES_SUPERCEDE;
    }

    new Float:from[3],Float:to[3],Float:velocity[3];
    pev(rocket,pev_origin,from);
    pev(rocket,pev_velocity,velocity);
    for(new axis;axis<3;axis++)to[axis]=from[axis]+velocity[axis]*floatmax(now-last,0.0);
    new owner=pev(rocket,pev_owner);
    if(owner<1 || owner>MaxClients || !is_user_connected(owner)
        || get_user_userid(owner)!=pev(rocket,pev_iuser1))owner=rocket;
    new trace=create_tr2();
    engfunc(EngFunc_TraceLine,from,to,DONT_IGNORE_MONSTERS,owner,trace);
    new Float:fraction;get_tr2(trace,TR_flFraction,fraction);
    new hit=get_tr2(trace,TR_pHit);
    if(fraction<1.0 || get_tr2(trace,TR_StartSolid)){
        get_tr2(trace,TR_vecEndPos,to);
        free_tr2(trace);
        rocket_impact(rocket,hit,to,velocity);
        return FMRES_SUPERCEDE;
    }
    free_tr2(trace);
    engfunc(EngFunc_SetOrigin,rocket,to);
    set_pev(rocket,pev_fuser2,now);
    set_pev(rocket,pev_nextthink,now+0.001);
    return FMRES_SUPERCEDE;
}

public clear_rockets()
{
    new ent;
    while ((ent = engfunc(EngFunc_FindEntityByString, 0, "classname", ROCKET)) > 0)
        engfunc(EngFunc_RemoveEntity, ent);
}
