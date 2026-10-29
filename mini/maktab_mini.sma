#include <amxmodx>
#include <fakemeta>
#include <reapi>

new bool:gWindow[2048],gWindowModel[2048],gWindowPair[2048];
new Float:gPaneCenter[256][3],Float:gPaneHalf[256][3];
new Float:gWindowCheckTime[33][256],bool:gPaneVisible[33][256];
new Float:gWindowCenter[2048][3],Float:gWindowRadius[2048];
new Float:gEye[33][3],Float:gForward[33][3],Float:gEyeTime[33];

// Loaded only for de_3_maktab. A penetration count includes the final hit:
// 3 = two walls then a player, 2 = one wall then a player.
public plugin_init()
{
    register_plugin("Day3 Mini support", "1.0", "Map project");
    set_cvar_float("sv_zmax",8192.0);
    new map[32]; get_mapname(map, charsmax(map));
    if (!equal(map, "de_3_maktab_mini")) return;
    RegisterHookChain(RG_CBaseEntity_FireBullets3, "OnBullet", false);
    RegisterHookChain(RG_CBaseEntity_FireBuckshots, "OnBuckshot", false);
    register_srvcmd("maktab_rules_status", "RulesStatus");
    set_task(0.2,"ConfigureModelBounds");
    set_task(0.3,"ConfigureWindowVisibility");
    register_forward(FM_AddToFullPack,"WindowVisibility",false);
    set_task(0.3,"OpenDoorsForBots",0,"",0,"b");
    register_logevent("OnRoundStart",2,"1=Round_Start");
    server_print("[maktab] penetration active: AWP two walls, other firearms one wall");
}

public OnRoundStart() { set_task(0.1,"ConfigureModelBounds"); }

public ConfigureModelBounds()
{
    new entity, model[96], configured;
    while ((entity=engfunc(EngFunc_FindEntityByString,entity,"classname","env_sprite"))>0)
    {
        pev(entity,pev_model,model,charsmax(model));
        if(contain(model,"models/maktab/")!=0) continue;
        new file=fopen(model,"rb"); if(!file) continue;
        new Float:mins[3],Float:maxs[3],raw;
        fseek(file,88,SEEK_SET);
        for(new j=0;j<3;j++){fread(file,raw,BLOCK_INT);mins[j]=Float:raw;}
        for(new j=0;j<3;j++){fread(file,raw,BLOCK_INT);maxs[j]=Float:raw;}
        fclose(file);
        set_pev(entity,pev_solid,SOLID_NOT);
        engfunc(EngFunc_SetSize,entity,mins,maxs);
        configured++;
    }
    server_print("[maktab] configured visibility bounds for %d static groups",configured);
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

public OpenDoorsForBots()
{
    for(new player=1;player<=MaxClients;player++) {
        if(!is_user_alive(player)||!is_user_bot(player))continue;
        new Float:p[3],Float:d[3];pev(player,pev_origin,p);
        new door;
        while((door=engfunc(EngFunc_FindEntityByString,door,"classname","func_door_rotating"))>0) {
            new Float:angles[3],Float:velocity[3];
            pev(door,pev_angles,angles);pev(door,pev_avelocity,velocity);
            if(vector_length(angles)>1.0 || vector_length(velocity)>1.0)continue;
            pev(door,pev_origin,d);
            if(get_distance_f(p,d)<112.0) dllfunc(DLLFunc_Use,door,player);
        }
    }
}

// Paired window entities are sent only within a generous view cone. Nearby
// windows are always kept for client collision prediction in every direction.
public ConfigureWindowVisibility()
{
    new e,name[64],count;new Float:a[3],Float:b[3];
    while((e=engfunc(EngFunc_FindEntityByString,e,"classname","func_breakable"))>0) {
        if(e>=2048)continue;
        pev(e,pev_targetname,name,charsmax(name));
        if(contain(name,"maktab_glass_")!=0 && contain(name,"maktab_frame_")!=0)continue;
        gWindow[e]=true;gWindowModel[e]=pev(e,pev_modelindex);pev(e,pev_absmin,a);pev(e,pev_absmax,b);
        gWindowPair[e]=str_to_num(name[13])+1;
        if(contain(name,"maktab_glass_")==0 && gWindowPair[e]<256){
            for(new j=0;j<3;j++){gPaneCenter[gWindowPair[e]][j]=(a[j]+b[j])*0.5;gPaneHalf[gWindowPair[e]][j]=(b[j]-a[j])*0.5-4.0;}
        }
        for(new j=0;j<3;j++)gWindowCenter[e][j]=(a[j]+b[j])*0.5;
        gWindowRadius[e]=get_distance_f(a,b)*0.5;count++;
    }
    server_print("[maktab] window visibility configured for %d paired parts",count);
}
public WindowVisibility(es,e,ent,host,flags,player,pSet)
{
    if(ent<=0 || ent>=2048 || !gWindow[ent] || host<1 || host>32)return FMRES_IGNORED;
    if(pev(ent,pev_modelindex)!=gWindowModel[ent])return FMRES_IGNORED;
    new Float:now=get_gametime();
    if(gEyeTime[host]!=now){
        new Float:v[3],Float:angles[3];pev(host,pev_origin,gEye[host]);pev(host,pev_view_ofs,v);pev(host,pev_v_angle,angles);
        for(new j=0;j<3;j++)gEye[host][j]+=v[j];
        angle_vector(angles,ANGLEVECTOR_FORWARD,gForward[host]);gEyeTime[host]=now;
    }
    new Float:delta[3],Float:d2,Float:dot;
    for(new j=0;j<3;j++){delta[j]=gWindowCenter[ent][j]-gEye[host][j];d2+=delta[j]*delta[j];dot+=delta[j]*gForward[host][j];}
    new Float:near=128.0+gWindowRadius[ent];
    if(d2<=near*near)return FMRES_IGNORED;
    if(dot>=floatsqroot(d2)*0.258819-gWindowRadius[ent]-24.0){
        if(PaneVisible(host,gWindowPair[ent],now))return FMRES_IGNORED;
    }
    forward_return(FMV_CELL,0);return FMRES_SUPERCEDE;
}

// Test the pane center and four inset corners against real world geometry.
// Glass and frame share this cached decision; no visible corner is discarded.
bool:PaneVisible(host,pair,Float:now)
{
    if(pair<=0 || pair>=256)return true;
    if(gWindowCheckTime[host][pair]>now)return gPaneVisible[host][pair];
    gWindowCheckTime[host][pair]=now+0.1;gPaneVisible[host][pair]=false;
    new trace=create_tr2();new Float:point[3],Float:f;
    new tangent=gPaneHalf[pair][0]<gPaneHalf[pair][1]?1:0;
    for(new sample=0;sample<5;sample++) {
        for(new j=0;j<3;j++)point[j]=gPaneCenter[pair][j];
        if(sample>0){point[tangent]+=(sample<=2?-1.0:1.0)*gPaneHalf[pair][tangent];point[2]+=(sample%2?-1.0:1.0)*gPaneHalf[pair][2];}
        engfunc(EngFunc_TraceLine,gEye[host],point,IGNORE_MONSTERS|IGNORE_GLASS,host,trace);
        get_tr2(trace,TR_flFraction,f);new hit=get_tr2(trace,TR_pHit);
        if(f>0.99 || (hit>0 && hit<2048 && gWindowPair[hit]==pair)){gPaneVisible[host][pair]=true;break;}
    }
    free_tr2(trace);return gPaneVisible[host][pair];
}
