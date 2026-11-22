#include <amxmodx>
#include <engine>
#include <fakemeta>

#define PLUGIN  "3 Maktab - Ra'no Ustoz NPC"
#define VERSION "1.2.0"
#define AUTHOR  "Codex"

new const NPC_CLASSNAME[] = "maktab_rano_npc";
new const NPC_MODEL[] = "models/maktab/rano_ustoz.mdl";
new const NPC_DIALOGUE[] = "Ra'no Ustoz: Kitobni oching. Diqqat bilan o'qing.";
new const NPC_DIALOGUE_STRICT[] = "Kechikkanni kiritmayman.^n^nDarsimni Buzishga HECH KIMNING HAQQI YO'Q, KIMING KELSA KELSIN,^nSinf Rahbaringmi, Direktormi, PREZIDENTMI,^n^nPOXXXXUY MANGA";

const Float:NPC_WALK_SPEED = 85.0;
const Float:NPC_STOP_DISTANCE = 72.0;
const Float:NPC_USE_DISTANCE = 100.0;
const Float:NPC_MAX_HEALTH = 100.0;

new g_npc;
new g_followingPlayer;
new Float:g_npcHealth;
new g_dialogueVariant[33];
new Float:g_lastDoorUse[2049];
new Float:g_lastHitTime[33];

public plugin_precache()
{
    precache_model(NPC_MODEL);
}

public plugin_init()
{
    register_plugin(PLUGIN, VERSION, AUTHOR);
    register_think(NPC_CLASSNAME, "npc_think");
    register_touch("func_door_rotating", "player", "bot_touched_door");
    register_touch("func_door", "player", "bot_touched_door");
    register_forward(FM_TraceLine, "trace_line_post", 1);
    register_forward(FM_TraceHull, "trace_hull_post", 1);
    register_logevent("round_start", 2, "1=Round_Start");
    set_task(0.2, "replace_map_decoration");
}

new Float:g_npcHome[3] = { -600.0, 780.0, 136.0 };

public replace_map_decoration()
{
    new marker = find_ent_by_tname(-1, "insomnia_rano_origin");
    if (is_valid_ent(marker))
        entity_get_vector(marker, EV_VEC_origin, g_npcHome);
    remove_old_rano_entities();
    create_rano_npc();
}

remove_old_rano_entities()
{
    new ent;
    while ((ent = find_ent_by_model(-1, "env_sprite", NPC_MODEL)) > 0)
    {
        remove_entity(ent);
    }

    while ((ent = find_ent_by_tname(-1, "maktab_rano_dialogue")) > 0)
    {
        remove_entity(ent);
    }

    new target[32];
    ent = -1;
    while ((ent = find_ent_by_class(ent, "func_button")) > 0)
    {
        entity_get_string(ent, EV_SZ_target, target, charsmax(target));
        if (equal(target, "maktab_rano_dialogue"))
        {
            remove_entity(ent);
        }
    }
}

create_rano_npc()
{
    g_npc = create_entity("info_target");
    if (!is_valid_ent(g_npc))
    {
        log_amx("Could not create Ra'no Ustoz NPC");
        return;
    }

    entity_set_string(g_npc, EV_SZ_classname, NPC_CLASSNAME);
    entity_set_string(g_npc, EV_SZ_targetname, "rano_ustoz");
    entity_set_model(g_npc, NPC_MODEL);

    new Float:mins[3] = { -12.0, -12.0, 0.0 };
    new Float:maxs[3] = { 12.0, 12.0, 56.0 };
    entity_set_origin(g_npc, g_npcHome);
    entity_set_size(g_npc, mins, maxs);

    entity_set_int(g_npc, EV_INT_movetype, MOVETYPE_STEP);
    entity_set_int(g_npc, EV_INT_solid, SOLID_SLIDEBOX);
    entity_set_float(g_npc, EV_FL_takedamage, 2.0);
    entity_set_float(g_npc, EV_FL_health, NPC_MAX_HEALTH);
    entity_set_float(g_npc, EV_FL_gravity, 1.0);
    entity_set_float(g_npc, EV_FL_framerate, 1.0);
    entity_set_int(g_npc, EV_INT_sequence, 0);
    entity_set_float(g_npc, EV_FL_nextthink, get_gametime() + 0.1);
    g_npcHealth = NPC_MAX_HEALTH;
}

public round_start()
{
    if (is_valid_ent(g_npc))
    {
        remove_entity(g_npc);
    }
    g_npc = 0;
    g_followingPlayer = 0;
    create_rano_npc();
}

public client_PreThink(id)
{
    if (!is_user_alive(id) || !is_valid_ent(g_npc))
    {
        return;
    }

    new buttons = entity_get_int(id, EV_INT_button);
    new oldButtons = entity_get_int(id, EV_INT_oldbuttons);
    if (!(buttons & IN_USE) || (oldButtons & IN_USE))
    {
        return;
    }

    new target, body;
    get_user_aiming(id, target, body, floatround(NPC_USE_DISTANCE));
    if (target != g_npc)
    {
        return;
    }

    g_followingPlayer = (g_followingPlayer == id) ? 0 : id;
    if (g_dialogueVariant[id] == 0)
    {
        client_print(id, print_center, "%s", NPC_DIALOGUE);
        g_dialogueVariant[id] = 1;
    }
    else
    {
        set_hudmessage(255, 225, 180, -1.0, 0.60, 0, 0.1, 7.0, 0.15, 0.35, 4);
        show_hudmessage(id, "%s", NPC_DIALOGUE_STRICT);
        g_dialogueVariant[id] = 0;
    }

    if (g_followingPlayer == id)
    {
        client_print(id, print_chat, "[Ra'no Ustoz] Men siz bilan boraman.");
    }
    else
    {
        stop_npc();
        client_print(id, print_chat, "[Ra'no Ustoz] Men shu yerda kutaman.");
    }
}

public bot_touched_door(door, player)
{
    if (!is_valid_ent(door) || player < 1 || player > 32 || !is_user_alive(player) || !is_user_bot(player))
    {
        return;
    }

    if (door >= sizeof(g_lastDoorUse))
    {
        return;
    }

    new Float:now = get_gametime();
    if (now - g_lastDoorUse[door] < 1.5)
    {
        return;
    }

    g_lastDoorUse[door] = now;
    force_use(player, door);
}

public trace_line_post(Float:start[3], Float:end[3], noMonsters, attacker, trace)
{
    handle_npc_trace(attacker, trace);
}

public trace_hull_post(Float:start[3], Float:end[3], noMonsters, hull, attacker, trace)
{
    handle_npc_trace(attacker, trace);
}

handle_npc_trace(attacker, trace)
{
    if (!is_valid_ent(g_npc) || attacker < 1 || attacker > 32 || !is_user_alive(attacker))
    {
        return;
    }

    if (get_tr2(trace, TR_pHit) != g_npc)
    {
        return;
    }

    new buttons = entity_get_int(attacker, EV_INT_button);
    if (!(buttons & (IN_ATTACK | IN_ATTACK2)))
    {
        return;
    }

    new Float:now = get_gametime();
    if (now - g_lastHitTime[attacker] < 0.025)
    {
        return;
    }
    g_lastHitTime[attacker] = now;

    apply_npc_damage(attacker, weapon_damage(get_user_weapon(attacker)));
}

Float:weapon_damage(weapon)
{
    switch (weapon)
    {
        case CSW_AWP: return 115.0;
        case CSW_SCOUT: return 75.0;
        case CSW_DEAGLE: return 54.0;
        case CSW_AK47: return 36.0;
        case CSW_M4A1: return 33.0;
        case CSW_AUG, CSW_SG552: return 32.0;
        case CSW_G3SG1, CSW_SG550: return 70.0;
        case CSW_M249: return 32.0;
        case CSW_M3: return 30.0;
        case CSW_XM1014: return 20.0;
        case CSW_USP: return 34.0;
        case CSW_GLOCK18: return 25.0;
        case CSW_P228: return 32.0;
        case CSW_FIVESEVEN: return 20.0;
        case CSW_ELITE: return 20.0;
        case CSW_KNIFE: return 65.0;
    }
    return 28.0;
}

apply_npc_damage(attacker, Float:damage)
{
    g_npcHealth -= damage;
    if (g_npcHealth > 0.0)
    {
        entity_set_float(g_npc, EV_FL_health, g_npcHealth);
        return;
    }

    new attackerName[32];
    get_user_name(attacker, attackerName, charsmax(attackerName));
    client_print(0, print_chat, "[Ra'no Ustoz] %s Ra'no Ustozni o'ldirdi.", attackerName);
    g_followingPlayer = 0;
    remove_entity(g_npc);
    g_npc = 0;
}

public npc_think(ent)
{
    if (ent != g_npc || !is_valid_ent(ent))
    {
        return;
    }

    if (g_followingPlayer > 0 && is_user_alive(g_followingPlayer))
    {
        follow_player(ent, g_followingPlayer);
    }
    else
    {
        g_followingPlayer = 0;
        stop_npc();
    }

    entity_set_float(ent, EV_FL_nextthink, get_gametime() + 0.1);
}

follow_player(ent, player)
{
    new Float:npcOrigin[3], Float:playerOrigin[3], Float:delta[3];
    entity_get_vector(ent, EV_VEC_origin, npcOrigin);
    entity_get_vector(player, EV_VEC_origin, playerOrigin);

    delta[0] = playerOrigin[0] - npcOrigin[0];
    delta[1] = playerOrigin[1] - npcOrigin[1];
    delta[2] = 0.0;

    new Float:distance = floatsqroot(delta[0] * delta[0] + delta[1] * delta[1]);
    if (distance <= NPC_STOP_DISTANCE)
    {
        stop_npc();
        return;
    }

    new Float:velocity[3];
    velocity[0] = delta[0] / distance * NPC_WALK_SPEED;
    velocity[1] = delta[1] / distance * NPC_WALK_SPEED;
    velocity[2] = 0.0;
    entity_set_vector(ent, EV_VEC_velocity, velocity);

    new Float:angles[3];
    vector_to_angle(delta, angles);
    angles[0] = 0.0;
    angles[2] = 0.0;
    entity_set_vector(ent, EV_VEC_angles, angles);
}

stop_npc()
{
    if (!is_valid_ent(g_npc))
    {
        return;
    }

    new Float:velocity[3] = { 0.0, 0.0, 0.0 };
    entity_set_vector(g_npc, EV_VEC_velocity, velocity);
}

public client_disconnected(id)
{
    if (g_followingPlayer == id)
    {
        g_followingPlayer = 0;
        stop_npc();
    }
}
