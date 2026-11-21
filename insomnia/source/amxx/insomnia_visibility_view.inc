// Shared by the interactive props and paired-window visibility plugins.
// This only reads the client's FOV; it never changes client video settings.
#if defined _insomnia_visibility_view_included
    #endinput
#endif
#define _insomnia_visibility_view_included

new Float:gInsomniaDefaultFov[33];
new Float:gInsomniaRight[33][3],Float:gInsomniaUp[33][3],Float:gInsomniaTanH[33],Float:gInsomniaTanV[33];
new Float:gInsomniaLastFov[33], Float:gInsomniaCone[33];
new gInsomniaLastMode[33],gInsomniaLastObserver[33],gInsomniaLastRevision[33];
new Float:gInsomniaLastEye[33][3],Float:gInsomniaLastLook[33][3];

stock InsomniaVisibilityInit()
{
    register_cvar("insomnia_visibility_generation","0");
    set_task(1.0,"InsomniaQueryFov");
    set_task(5.0,"InsomniaQueryFov",0,"",0,"b");
}

public client_connect(id)
{
    gInsomniaDefaultFov[id]=150.0;
    gInsomniaLastFov[id]=0.0;
    gInsomniaLastMode[id]=-1;
}

public client_putinserver(id)
{
    if(!is_user_bot(id))set_task(0.5,"InsomniaQueryFov");
}

public InsomniaQueryFov()
{
    new clients[32],count;
    get_players(clients,count,"ch");
    for(new i=0;i<count;i++)
        query_client_cvar(clients[i],"default_fov","InsomniaReceiveFov");
}

public InsomniaReceiveFov(id,const name[],const value[])
{
    if(!is_user_connected(id))return;
    new Float:fov=str_to_float(value);
    // Keep a conservative envelope if an older client cannot answer the query.
    if(fov>=20.0 && fov<=170.0)gInsomniaDefaultFov[id]=fov;
}

stock bool:InsomniaVisibilityView(host,Float:eye[3],Float:look[3],&Float:cone)
{
    new mode=pev(host,pev_iuser1),observer=host;
    // iuser2 is retained when changing from follow mode to Free Look.
    // Only the in-eye camera uses that player's view origin and view angles.
    if(!is_user_alive(host) && mode==4){
        new target=pev(host,pev_iuser2);
        if(target>=1 && target<=MaxClients && is_user_alive(target))observer=target;
    }
    new Float:offset[3],Float:angles[3];
    pev(observer,pev_origin,eye);pev(observer,pev_view_ofs,offset);
    for(new axis=0;axis<3;axis++)eye[axis]+=offset[axis];
    pev(observer,pev_v_angle,angles);
    angle_vector(angles,ANGLEVECTOR_FORWARD,look);
    angle_vector(angles,ANGLEVECTOR_RIGHT,gInsomniaRight[host]);
    angle_vector(angles,ANGLEVECTOR_UP,gInsomniaUp[host]);

    new Float:fov;pev(observer,pev_fov,fov);
    if(fov<=0.0)fov=90.0;
    // SetFOV/default-FOV handling is client-side; an unzoomed server value
    // of90 does not prove that the client renders only90 degrees.
    if(fov>=89.0)fov=floatmax(fov,gInsomniaDefaultFov[host]>0.0?gInsomniaDefaultFov[host]:150.0);
    new bool:changed=mode!=gInsomniaLastMode[host] || observer!=gInsomniaLastObserver[host];
    if(floatabs(fov-gInsomniaLastFov[host])>0.1){
        // Enclose the complete diagonal of a square viewport, with a margin.
        // Preserve the old generous 90-degree cone for ordinary play.
        new Float:half=fov*0.5;
        new Float:tangent=floatsin(half,degrees)/floatcos(half,degrees);
        gInsomniaCone[host]=floatmin(0.45,0.9/floatsqroot(1.0+2.0*tangent*tangent));
        // Include 16:9 clients and a margin around their rectangular viewport.
        gInsomniaTanH[host]=tangent*1.466667+0.05;
        gInsomniaTanV[host]=tangent*0.825+0.05;
        gInsomniaLastFov[host]=fov;
        changed=true;
    }
    if(get_distance_f(eye,gInsomniaLastEye[host])>0.01)changed=true;
    new revision=get_cvar_num("insomnia_visibility_generation");
    if(revision!=gInsomniaLastRevision[host])changed=true;
    gInsomniaLastRevision[host]=revision;
    gInsomniaLastEye[host]=eye;gInsomniaLastLook[host]=look;
    gInsomniaLastMode[host]=mode;gInsomniaLastObserver[host]=observer;
    cone=gInsomniaCone[host];
    return changed;
}

stock bool:InsomniaVisibilityInBox(host,const Float:center[3],const Float:half[3])
{
    new Float:delta[3],Float:depth,Float:x,Float:y;
    new Float:extentH,Float:extentV;
    for(new axis=0;axis<3;axis++){
        delta[axis]=center[axis]-gInsomniaLastEye[host][axis];
        depth+=delta[axis]*gInsomniaLastLook[host][axis];
        x+=delta[axis]*gInsomniaRight[host][axis];
        y+=delta[axis]*gInsomniaUp[host][axis];
    }
    for(new sign=-1;sign<=1;sign+=2){
        extentH=0.0;extentV=0.0;
        for(new axis=0;axis<3;axis++){
            extentH+=half[axis]*floatabs(float(sign)*gInsomniaRight[host][axis]-gInsomniaTanH[host]*gInsomniaLastLook[host][axis]);
            extentV+=half[axis]*floatabs(float(sign)*gInsomniaUp[host][axis]-gInsomniaTanV[host]*gInsomniaLastLook[host][axis]);
        }
        if(float(sign)*x-depth*gInsomniaTanH[host]>extentH+24.0)return false;
        if(float(sign)*y-depth*gInsomniaTanV[host]>extentV+24.0)return false;
    }
    return true;
}
