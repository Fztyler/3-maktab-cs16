#include <amxmodx>
#include <fakemeta>
#include <reapi>

// Loaded only for de_3_maktab. A penetration count includes the final hit:
// 3 = two walls then a player, 2 = one wall then a player.
public plugin_init()
{
    register_plugin("Maktab wall penetration", "1.0", "Map project");
    new map[32]; get_mapname(map, charsmax(map));
    if (!equal(map, "de_3_maktab")) return;
    RegisterHookChain(RG_CBaseEntity_FireBullets3, "OnBullet", false);
    RegisterHookChain(RG_CBaseEntity_FireBuckshots, "OnBuckshot", false);
    register_srvcmd("maktab_rules_status", "RulesStatus");
    server_print("[maktab] penetration active: AWP two walls, other firearms one wall");
}

public RulesStatus()
{
    server_print("[maktab] AWP=2 walls; other firearms=1 wall; shotguns included");
}

public OnBullet(entity, Float:src[3], Float:direction[3], Float:spread,
    Float:distance, penetration, bullet, damage, Float:rangeModifier,
    attacker, bool:pistol, seed)
{
    if (entity<1 || entity>MaxClients || !is_user_alive(entity)) return HC_CONTINUE;
    SetHookChainArg(6, ATYPE_INTEGER, get_user_weapon(entity)==CSW_AWP ? 3 : 2);
    // Equalize wall exit distance, preserving weapon damage/spread/range falloff.
    SetHookChainArg(7, ATYPE_INTEGER, BULLET_PLAYER_338MAG);
    return HC_CONTINUE;
}

public OnBuckshot(entity, shots, Float:src[3], Float:direction[3], Float:spread[3],
    Float:distance, tracer, damage, attacker)
{
    if (entity<1 || entity>MaxClients || !is_user_alive(entity)) return HC_CONTINUE;
    new Float:angles[3], Float:right[3], Float:up[3], Float:dir[3];
    pev(entity, pev_v_angle, angles);
    angle_vector(angles, ANGLEVECTOR_RIGHT, right);
    angle_vector(angles, ANGLEVECTOR_UP, up);
    for (new pellet=0; pellet<shots; pellet++)
    {
        new Float:x, Float:y;
        do {
            x=random_float(-0.5,0.5)+random_float(-0.5,0.5);
            y=random_float(-0.5,0.5)+random_float(-0.5,0.5);
        } while (x*x+y*y>1.0);
        for (new j=0;j<3;j++) dir[j]=direction[j]+x*spread[0]*right[j]+y*spread[1]*up[j];
        rg_fire_bullets3(entity, attacker, src, dir, 0.0, distance, 2,
            BULLET_PLAYER_338MAG, damage, 1.0, false, random_num(0,0x7fffffff));
    }
    return HC_SUPERCEDE;
}
