native insomnia_box_visible(const Float:start[3],const Float:lo[3],const Float:hi[3],skip,target1,target2,grid);
#pragma reqlib insomnia_fastvis
#pragma loadlib insomnia_fastvis
native Float:insomnia_trace_visible(const Float:start[3],const Float:finish[3],skip,&hit);
#include <amxmodx>
#include <fakemeta>
#include <hamsandwich>
#include <reapi>
#include "insomnia_furniture_data.inc"
#include "insomnia_glass_data.inc"
#include "insomnia_visibility_view.inc"

#define MAP_EDICTS 2048

new g_modelType[MAP_EDICTS];
new g_batchesCvar;
new g_viewRevision[33];
new g_glassType[MAP_EDICTS], g_glassGibs;
new bool:g_broken[MAP_EDICTS];
new bool:g_partition[MAP_EDICTS];
new bool:g_heavyFence[MAP_EDICTS];
new bool:g_sill[MAP_EDICTS];
new g_doorMaterial[MAP_EDICTS];
new g_activeHE;
new Float:g_debrisWindow;
new g_debrisCount;
new Float:g_wallCenter[MAP_EDICTS][3], Float:g_wallRadius[MAP_EDICTS];
new Float:g_wallHalf[MAP_EDICTS][3];
new g_wallOfBoard[MAP_EDICTS];
new Float:g_wallNextCheck[33][MAP_EDICTS], bool:g_wallSeen[33][MAP_EDICTS];
new Float:g_viewTime[33], Float:g_eye[33][3], Float:g_look[33][3], Float:g_viewCone[33];

new g_visTraceFlags[33];
new Float:g_propRadius[MAP_EDICTS];
new g_gibs[3];
new const GIB_MODELS[][] = {
    "models/woodgibs.mdl", "models/metalplategibs.mdl", "models/concretegibs.mdl"
};
new const BREAK_SOUNDS[][] = {
    "debris/wood1.wav", "debris/metal1.wav", "debris/concrete1.wav"
};
new const BREAK_FLAGS[] = {BREAK_WOOD, BREAK_METAL, BREAK_CONCRETE};

public plugin_precache()
{
    new map[32];
    get_mapname(map, charsmax(map));
    if (!equal(map, "de_insomnia_project_t")) return;

    for (new type = 0; type < sizeof FURNITURE_MODELS; type++)
        precache_model(FURNITURE_MODELS[type]);
    precache_model("models/maktab/insomnia_r12_glass.mdl");
    g_glassGibs=precache_model("models/glassgibs.mdl");
    precache_sound("debris/glass1.wav");
    for (new i = 0; i < sizeof GIB_MODELS; i++) {
        g_gibs[i] = precache_model(GIB_MODELS[i]);
        precache_sound(BREAK_SOUNDS[i]);
    }
}

public plugin_init()
{
    if (!g_gibs[0]) return;

    register_plugin("Insomnia interactive props", "1.7.9", "Map project");
    RegisterHam(Ham_TakeDamage, "info_target", "furniture_damage");
    RegisterHam(Ham_TakeDamage, "func_breakable", "partition_damage");
    RegisterHam(Ham_TakeDamage, "func_breakable", "wall_broken", true);
    RegisterHam(Ham_TakeDamage, "func_door_rotating", "furniture_damage");
    RegisterHam(Ham_Use, "func_door_rotating", "door_use");
    RegisterHam(Ham_Use, "info_target", "glass_use");
    RegisterHookChain(RG_CGrenade_ExplodeHeGrenade, "start_he");
    RegisterHookChain(RG_CGrenade_ExplodeHeGrenade, "finish_he", true);
    RegisterHookChain(RG_CSGameRules_RestartRound, "restore_furniture", true);
    register_forward(FM_AddToFullPack, "furniture_visibility");
    RegisterHam(Ham_Spawn,"player","visibility_spawned",true);
    InsomniaVisibilityInit();
    g_batchesCvar=get_cvar_pointer("insomnia_batches_active");
    register_message(SVC_TEMPENTITY,"debris_budget");

    new name[48], typeText[12];
    new furnitureCount, wallCount;
    for (new ent = MaxClients+1; ent < global_get(glb_maxEntities) && ent < MAP_EDICTS; ent++) {
        if (pev_valid(ent) != 2) continue;
        pev(ent, pev_targetname, name, charsmax(name));
        if (containi(name, "insomnia_furniture_") == 0) {
            pev(ent, pev_netname, typeText, charsmax(typeText));
            new type = str_to_num(typeText);
            if (type < 0 || type >= sizeof FURNITURE_MODELS) continue;
            g_modelType[ent] = type+1;
            furnitureCount++;
        } else if (containi(name, "maktab_glass_") == 0) {
            pev(ent,pev_netname,typeText,charsmax(typeText));
            new type=str_to_num(typeText);
            if (type<0 || type>=sizeof GLASS_HALVES) continue;
            g_glassType[ent]=type+1;

        } else if (containi(name, "insomnia_partition_") == 0 || containi(name,"insomnia_sill_C_")==0) {
            g_sill[ent]=containi(name,"insomnia_sill_C_")==0;
            g_partition[ent] = true;
            g_heavyFence[ent] = pev(ent,pev_rendermode)==kRenderTransAlpha;
            new Float:min[3], Float:max[3];
            pev(ent, pev_absmin, min);
            pev(ent, pev_absmax, max);
            for (new axis=0; axis<3; axis++)
                {g_wallCenter[ent][axis]=(min[axis]+max[axis])*0.5;g_wallHalf[ent][axis]=(max[axis]-min[axis])*0.5;}
            g_wallRadius[ent]=get_distance_f(min,max)*0.5;
            wallCount++;
        } else if (containi(name, "insomnia_door_") == 0) {
            g_doorMaterial[ent] = name[strlen(name)-1] == '3' ? 2 : 1;
            restore_door(ent);
        }
    }
    set_task(0.12,"activate_props");
    server_print("[insomnia] interactive furniture=%d partitions=%d", furnitureCount, wallCount);
}

// GoldSrc creates a limited signon buffer before tasks run. Studio props are
// initialized after baseline creation, just like normal runtime entities.
public activate_props()
{
    for (new ent=MaxClients+1; ent<global_get(glb_maxEntities) && ent<MAP_EDICTS; ent++) {
        if (pev_valid(ent)!=2) continue;
        if (g_modelType[ent]) link_furniture(ent,g_modelType[ent]-1);
        else if (g_glassType[ent]) link_glass(ent,g_glassType[ent]-1);
        if(g_modelType[ent]) {new Float:a[3],Float:b[3];pev(ent,pev_mins,a);pev(ent,pev_maxs,b);g_propRadius[ent]=get_distance_f(a,b)*0.5;}
    }
    link_wall_boards();
}


link_furniture(ent, type)
{
    engfunc(EngFunc_SetModel, ent, FURNITURE_MODELS[type]);

    new Float:angles[3], Float:mins[3], Float:maxs[3], Float:origin[3];
    pev(ent, pev_angles, angles);
    new swapAxes = (floatround(angles[1]/90.0) & 1);
    maxs[0] = float(FURNITURE_HULLS[type][swapAxes]);
    maxs[1] = float(FURNITURE_HULLS[type][1-swapAxes]);
    maxs[2] = float(FURNITURE_HULLS[type][2]);
    mins[0] = -maxs[0];
    mins[1] = -maxs[1];
    mins[2] = float(FURNITURE_HULLS[type][5]);

    set_pev(ent, pev_movetype, MOVETYPE_NONE);
    set_pev(ent, pev_solid, SOLID_BBOX);
    set_pev(ent, pev_health, float(FURNITURE_HULLS[type][3]));
    set_pev(ent, pev_takedamage, 1.0);
    set_pev(ent, pev_effects, pev(ent, pev_effects) & ~EF_NODRAW);
    set_pev(ent, pev_body, type);
    set_pev(ent, pev_sequence, 0);
    set_pev(ent, pev_framerate, 0.0);
    engfunc(EngFunc_SetSize, ent, mins, maxs);
    pev(ent, pev_origin, origin);
    engfunc(EngFunc_SetOrigin, ent, origin);
}

restore_door(ent)
{
    new Float:origin[3];
    pev(ent, pev_origin, origin);
    set_pev(ent, pev_health, g_doorMaterial[ent] == 2 ? 145.0 : 105.0);
    set_pev(ent, pev_takedamage, 1.0);
    set_pev(ent, pev_solid, SOLID_BSP);
    set_pev(ent, pev_effects, pev(ent, pev_effects) & ~EF_NODRAW);
    engfunc(EngFunc_SetOrigin, ent, origin);
}

public door_use(ent)
{
    return ent > 0 && ent < MAP_EDICTS && g_doorMaterial[ent] && g_broken[ent]
           ? HAM_SUPERCEDE : HAM_IGNORED;
}

link_glass(ent,type)
{
    engfunc(EngFunc_SetModel,ent,"models/maktab/insomnia_r12_glass.mdl");
    new Float:mins[3],Float:origin[3];
    for (new axis=0;axis<3;axis++) mins[axis]=-GLASS_HALVES[type][axis];
    set_pev(ent,pev_body,type);
    set_pev(ent,pev_movetype,MOVETYPE_NONE);
    set_pev(ent,pev_solid,SOLID_BBOX);
    set_pev(ent,pev_health,20.0);
    set_pev(ent,pev_takedamage,1.0);
    set_pev(ent,pev_rendermode,kRenderTransTexture);
    set_pev(ent,pev_renderamt,122.0);
    set_pev(ent,pev_effects,pev(ent,pev_effects)&~EF_NODRAW);
    engfunc(EngFunc_SetSize,ent,mins,GLASS_HALVES[type]);
    pev(ent,pev_origin,origin);
    engfunc(EngFunc_SetOrigin,ent,origin);
}

public glass_use(ent)
{
    if (ent<=0 || ent>=MAP_EDICTS || !g_glassType[ent]) return HAM_IGNORED;
    break_glass(ent);
    return HAM_SUPERCEDE;
}

break_glass(ent)
{
    if (g_broken[ent]) return;
    g_broken[ent]=true;
    set_pev(ent,pev_takedamage,0.0);
    set_pev(ent,pev_solid,SOLID_NOT);
    set_pev(ent,pev_effects,pev(ent,pev_effects)|EF_NODRAW);
    new Float:origin[3],type=g_glassType[ent]-1;
    pev(ent,pev_origin,origin);
    engfunc(EngFunc_SetOrigin,ent,origin);
    emit_sound(ent,CHAN_BODY,"debris/glass1.wav",0.7,ATTN_NORM,0,PITCH_NORM);
    engfunc(EngFunc_MessageBegin,MSG_PVS,SVC_TEMPENTITY,origin,0);
    write_byte(TE_BREAKMODEL);
    for (new axis=0;axis<3;axis++) engfunc(EngFunc_WriteCoord,origin[axis]);
    for (new axis=0;axis<3;axis++) engfunc(EngFunc_WriteCoord,GLASS_HALVES[type][axis]*2.0);
    engfunc(EngFunc_WriteCoord,0.0);
    engfunc(EngFunc_WriteCoord,0.0);
    engfunc(EngFunc_WriteCoord,0.0);
    write_byte(10);
    write_short(g_glassGibs);
    write_byte(4);
    write_byte(12);
    write_byte(BREAK_GLASS);
    message_end();
}

public restore_furniture()
{
    set_cvar_num("insomnia_visibility_generation",get_cvar_num("insomnia_visibility_generation")+1);
    for (new ent = MaxClients+1; ent < global_get(glb_maxEntities) && ent < MAP_EDICTS; ent++) {
        if ((!g_modelType[ent] && !g_doorMaterial[ent] && !g_glassType[ent]) || pev_valid(ent) != 2) continue;
        if (g_glassType[ent]) {
            link_glass(ent,g_glassType[ent]-1);
        } else if (g_doorMaterial[ent]) {
            restore_door(ent);
        } else if (g_broken[ent]) {
            link_furniture(ent, g_modelType[ent]-1);
        } else {
            set_pev(ent, pev_health, float(FURNITURE_HULLS[g_modelType[ent]-1][3]));
        }
        g_broken[ent] = false;
    }
}

public furniture_damage(ent, inflictor, attacker, Float:damage, bits)
{
    if (ent<=0 || ent>=MAP_EDICTS) return HAM_IGNORED;
    if (g_glassType[ent]) {
        if (damage<=0.0 || g_broken[ent]) return HAM_SUPERCEDE;
        new Float:health;
        pev(ent,pev_health,health);
        health-=damage;
        set_pev(ent,pev_health,health);
        if (health<=0.0) break_glass(ent);
        return HAM_SUPERCEDE;
    }
    if (!g_modelType[ent] && !g_doorMaterial[ent]) return HAM_IGNORED;
    if (g_broken[ent] || damage <= 0.0) return HAM_SUPERCEDE;

    new Float:health;
    pev(ent, pev_health, health);
    health -= damage;
    set_pev(ent, pev_health, health);
    if (health > 0.0) return HAM_SUPERCEDE;

    g_broken[ent] = true;
    set_pev(ent, pev_takedamage, 0.0);
    set_pev(ent, pev_solid, SOLID_NOT);
    set_pev(ent, pev_effects, pev(ent, pev_effects) | EF_NODRAW);
    new Float:origin[3];
    pev(ent, pev_origin, origin);
    engfunc(EngFunc_SetOrigin, ent, origin);
    new material;
    if (g_doorMaterial[ent]) {
        material = g_doorMaterial[ent] - 1;
        new Float:mins[3], Float:maxs[3];
        pev(ent, pev_absmin, mins);
        pev(ent, pev_absmax, maxs);
        for (new axis = 0; axis < 3; axis++) origin[axis] = (mins[axis] + maxs[axis]) * 0.5;
    } else {
        material = FURNITURE_HULLS[g_modelType[ent]-1][4];
        origin[2] += 16.0;
    }
    emit_sound(ent, CHAN_BODY, BREAK_SOUNDS[material], 0.8, ATTN_NORM, 0, PITCH_NORM);
    engfunc(EngFunc_MessageBegin, MSG_PVS, SVC_TEMPENTITY, origin, 0);
    write_byte(TE_BREAKMODEL);
    for (new axis = 0; axis < 3; axis++) engfunc(EngFunc_WriteCoord, origin[axis]);
    engfunc(EngFunc_WriteCoord, 28.0);
    engfunc(EngFunc_WriteCoord, 21.0);
    engfunc(EngFunc_WriteCoord, 20.0);
    engfunc(EngFunc_WriteCoord, 0.0);
    engfunc(EngFunc_WriteCoord, 0.0);
    engfunc(EngFunc_WriteCoord, 22.0);
    write_byte(10);
    write_short(g_gibs[material]);
    write_byte(5);
    write_byte(19);
    write_byte(BREAK_FLAGS[material]);
    message_end();
    return HAM_SUPERCEDE;
}

public start_he(ent)
{
    g_activeHE = ent;
}

public finish_he(ent)
{
    if (ent == g_activeHE) g_activeHE = 0;
}

public partition_damage(ent, inflictor, attacker, Float:damage, bits)
{
    if (ent <= 0 || ent >= MAP_EDICTS || !g_partition[ent]) return HAM_IGNORED;
    if (damage <= 0.0 || attacker < 1 || attacker > MaxClients || !is_user_connected(attacker))
        return HAM_SUPERCEDE;

    if(g_sill[ent]) {
        if(bits&DMG_BULLET){SetHamParamFloat(4,1.0);return HAM_HANDLED;}
        if((bits&DMG_BLAST)||g_activeHE==inflictor){SetHamParamFloat(4,6.0);return HAM_HANDLED;}
        return HAM_SUPERCEDE;
    }
    if ((bits & DMG_BLAST) && pev_valid(inflictor) && pev(inflictor,pev_iuser2)==0x525047) {
        if(pev(inflictor,pev_iuser3)!=ent)return HAM_SUPERCEDE;
        SetHamParamFloat(4,1021.0);
        return HAM_HANDLED;
    }
    if (g_activeHE && inflictor == g_activeHE) {
        SetHamParamFloat(4, 1021.0);
        return HAM_HANDLED;
    }

    new weapon = get_member(attacker, m_pActiveItem);
    if ((bits & DMG_BULLET) && weapon > 0 && WeaponIdType:get_member(weapon, m_iId) == WEAPON_M249
        && pev(weapon, pev_iuser4) != 0x4D3242) {
        SetHamParamFloat(4, g_heavyFence[ent] ? 20.401 : 34.0);
        return HAM_HANDLED;
    }
    return HAM_SUPERCEDE;
}

link_wall_boards()
{
    new trace=create_tr2();
    for (new ent=MaxClients+1; ent<global_get(glb_maxEntities) && ent<MAP_EDICTS; ent++) {
        if (!g_modelType[ent] || FURNITURE_HULLS[g_modelType[ent]-1][5]>=0) continue;
        new Float:origin[3], Float:end[3], Float:angles[3];
        pev(ent,pev_origin,origin);
        pev(ent,pev_angles,angles);
        end=origin;
        end[0]-=floatsin(angles[1],degrees)*14.0;
        end[1]+=floatcos(angles[1],degrees)*14.0;
        engfunc(EngFunc_TraceLine,origin,end,IGNORE_MONSTERS,ent,trace);
        new wall=get_tr2(trace,TR_pHit);
        if (wall>0 && wall<MAP_EDICTS && g_partition[wall]) g_wallOfBoard[ent]=wall;
    }
    free_tr2(trace);
}

public wall_broken(ent, inflictor, attacker, Float:damage, bits)
{
    if (ent<=0 || ent>=MAP_EDICTS || !g_partition[ent] || pev(ent,pev_solid)!=SOLID_NOT)
        return HAM_IGNORED;
    set_cvar_num("insomnia_visibility_generation",get_cvar_num("insomnia_visibility_generation")+1);
    new names[768], target[40], next[768];
    pev(ent,pev_netname,names,charsmax(names));
    while (names[0]) {
        strtok2(names,target,charsmax(target),next,charsmax(next),'|');
        copy(names,charsmax(names),next);
        new frame=engfunc(EngFunc_FindEntityByString,0,"targetname",target);
        if (frame>0 && pev(frame,pev_solid)!=SOLID_NOT) dllfunc(DLLFunc_Use,frame,attacker);
    }
    for (new board=MaxClients+1; board<global_get(glb_maxEntities) && board<MAP_EDICTS; board++) {
        if (g_wallOfBoard[board]==ent && !g_broken[board] && pev_valid(board)==2)
            ExecuteHamB(Ham_TakeDamage,board,inflictor,attacker,200.0,DMG_BLAST);
    }
    return HAM_IGNORED;
}

public furniture_visibility(es, e, ent, host, hostflags, player, pSet)
{
 // Diagnostic only: common include owns the no-frustum switch.
    if (ent<=0 || ent>=MAP_EDICTS || (!g_modelType[ent] && !g_partition[ent] && !g_doorMaterial[ent])) return FMRES_IGNORED;
    if (host<1 || host>MaxClients) return FMRES_IGNORED;
    if(g_modelType[ent] && g_batchesCvar && get_pcvar_num(g_batchesCvar))return FMRES_IGNORED;

    new Float:now=get_gametime();
    new revision=get_cvar_num("insomnia_visibility_generation");
    if (g_viewTime[host]!=now || g_viewRevision[host]!=revision) {
        g_viewRevision[host]=revision;
        g_viewTime[host]=now;
        g_visTraceFlags[host]=IGNORE_MONSTERS|IGNORE_GLASS;
        if(get_cvar_num("insomnia_fastvis_ready"))g_visTraceFlags[host]|=(1<<28);
        if(InsomniaVisibilityView(host,g_eye[host],g_look[host],g_viewCone[host]))
            arrayset(g_wallNextCheck[host],0,MAP_EDICTS);
    }

    if (g_partition[ent]) {
        new Float:offset[3];
        for (new axis=0; axis<3; axis++) {
            offset[axis]=g_wallCenter[ent][axis]-g_eye[host][axis];
        }
        // Send nearby collision and all potentially visible distant walls.
        new Float:nearest2;
        for(new axis=0;axis<3;axis++){
            new Float:gap=floatmax(floatabs(offset[axis])-g_wallHalf[ent][axis],0.0);
            nearest2+=gap*gap;
        }
        new Float:near=128.0;
        if(nearest2<=near*near)return FMRES_IGNORED;
        if (InsomniaVisibilityInBox(host,g_wallCenter[ent],g_wallHalf[ent]) && wall_visible(ent,host,now))
            return FMRES_IGNORED;
    } else {
        new Float:origin[3],Float:half[3],Float:lo[3],Float:hi[3];
        pev(ent,pev_absmin,lo);pev(ent,pev_absmax,hi);
        for(new axis=0;axis<3;axis++){origin[axis]=(lo[axis]+hi[axis])*0.5;half[axis]=(hi[axis]-lo[axis])*0.5;}
        if(g_doorMaterial[ent]) {
            door_render_bounds(ent,lo,hi);
            for(new axis=0;axis<3;axis++){origin[axis]=(lo[axis]+hi[axis])*0.5;half[axis]=(hi[axis]-lo[axis])*0.5;}
            g_propRadius[ent]=get_distance_f(lo,hi)*0.5;
        }
        new Float:delta[3],Float:dot;
        for(new axis=0;axis<3;axis++){delta[axis]=origin[axis]-g_eye[host][axis];dot+=delta[axis]*g_look[host][axis];}
        new Float:distance=vector_length(delta);
        if(distance<=96.0+g_propRadius[ent])return FMRES_IGNORED;
        if((g_doorMaterial[ent]||distance<=2400.0) && InsomniaVisibilityInBox(host,origin,half) && prop_visible(ent,host,now))return FMRES_IGNORED;
    }

    forward_return(FMV_CELL,0);
    return FMRES_SUPERCEDE;
}

public visibility_spawned(id)
{
    g_viewTime[id]=-1.0;
    arrayset(g_wallNextCheck[id],0,MAP_EDICTS);
    set_cvar_num("insomnia_visibility_generation",get_cvar_num("insomnia_visibility_generation")+1);
}

bool:wall_visible(ent,host,Float:now)
{
    if(g_wallNextCheck[host][ent]>now)return g_wallSeen[host][ent];
    g_wallNextCheck[host][ent]=now+0.16;
    new Float:lo[3],Float:hi[3];pev(ent,pev_absmin,lo);pev(ent,pev_absmax,hi);
    new tangent=hi[0]-lo[0]<hi[1]-lo[1]?1:0;
    lo[tangent]+=2.0;hi[tangent]-=2.0;lo[2]+=2.0;hi[2]-=2.0;
    g_wallSeen[host][ent]=bool:insomnia_box_visible(g_eye[host],lo,hi,host,ent,0,17);
    return g_wallSeen[host][ent];
}

// Several nearby HE breaches can otherwise overflow a client's effect datagram.
// This caps visual debris bursts; damage, collision and independent health remain intact.
public debris_budget(message,destination,id)
{
    if(get_msg_args()<1 || get_msg_arg_int(1)!=TE_BREAKMODEL)return PLUGIN_CONTINUE;
    new Float:now=get_gametime();
    if(now-g_debrisWindow>=0.10){g_debrisWindow=now;g_debrisCount=0;}
    return ++g_debrisCount>6 ? PLUGIN_HANDLED : PLUGIN_CONTINUE;
}

bool:prop_visible(ent,host,Float:now)
{
    new Float:origin[3];pev(ent,pev_origin,origin);
    if(get_distance_f(origin,g_eye[host])<160.0)return true;
    if(!g_doorMaterial[ent]&&g_wallNextCheck[host][ent]>now)return g_wallSeen[host][ent];
    g_wallNextCheck[host][ent]=now+0.10;
    new Float:lo[3],Float:hi[3];pev(ent,pev_absmin,lo);pev(ent,pev_absmax,hi);
    if(g_doorMaterial[ent]){
        door_render_bounds(ent,lo,hi);
        g_wallSeen[host][ent]=bool:insomnia_box_visible(g_eye[host],lo,hi,host,0,ent,17);
        return g_wallSeen[host][ent];
    }
    for(new axis=0;axis<3;axis++){lo[axis]+=1.0;hi[axis]-=1.0;}
    g_wallSeen[host][ent]=bool:insomnia_box_visible(g_eye[host],lo,hi,host,ent,0,g_doorMaterial[ent]?17:0);
    return g_wallSeen[host][ent];
}

door_render_bounds(ent,Float:lo[3],Float:hi[3])
{
    pev(ent,pev_absmin,lo);pev(ent,pev_absmax,hi);
}
