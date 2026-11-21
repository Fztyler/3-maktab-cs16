#include <amxmodx>
#include <fakemeta>
#include <hamsandwich>
#include <reapi>
#include "insomnia_batches_data.inc"
#include "insomnia_visibility_view.inc"
#pragma reqlib insomnia_fastvis
#pragma loadlib insomnia_fastvis
native insomnia_box_visible(const Float:start[3],const Float:lo[3],const Float:hi[3],skip,target1,target2,grid);

new g_owner[2048],g_bit[2048],g_group[sizeof BATCH_MODELS],g_groupIndex[2048];
new g_mask[sizeof BATCH_MODELS],g_enabled,g_initialized,g_activeCvar;
new Float:g_eye[33][3],Float:g_look[33][3],Float:g_cone[33],Float:g_viewTime[33];
new Float:g_next[33][sizeof BATCH_MODELS*4],bool:g_seen[33][sizeof BATCH_MODELS*4];
new Float:g_clusterLo[sizeof BATCH_MODELS][4][3],Float:g_clusterHi[sizeof BATCH_MODELS][4][3],g_clusterBits[sizeof BATCH_MODELS][4];
new g_revision[33];
public plugin_precache(){
 new map[32];get_mapname(map,charsmax(map));if(!equal(map,"de_insomnia_project_t"))return;
 g_enabled=1;g_activeCvar=register_cvar("insomnia_batches_active","0");set_pcvar_num(g_activeCvar,0);
 new last;for(new i=0;i<sizeof BATCH_MODELS;i++)last=precache_model(BATCH_MODELS[i]);
 server_print("[batches] models=%d last_precache_index=%d",sizeof BATCH_MODELS,last);
}
public plugin_init(){
 register_plugin("Insomnia render batches","1.2","Map project");
 if(!g_enabled)return;
 register_forward(FM_AddToFullPack,"filter_packet");register_forward(FM_AddToFullPack,"hide_proxy",true);
 RegisterHam(Ham_TakeDamage,"info_target","after_damage",true);
 RegisterHam(Ham_TakeDamage,"func_breakable","after_damage",true);
 RegisterHam(Ham_Use,"func_breakable","after_damage",true);
 RegisterHam(Ham_Use,"info_target","after_damage",true);
 RegisterHookChain(RG_CSGameRules_RestartRound,"round_reset",true);
 register_srvcmd("insomnia_batches_status","status");InsomniaVisibilityInit();set_task(0.4,"initialize");
}
public initialize(){
 if(!get_cvar_num("insomnia_coverage_ready")){server_print("[batches] disabled: matching occlusion data is required");return;}
 new name[48],count;
 for(new i=0;i<sizeof BATCH_MAP;i++){
  formatex(name,charsmax(name),BATCH_MAP[i][3]==2?"maktab_glass_%03d":BATCH_MAP[i][3]==1?"maktab_frame_%03d":"insomnia_furniture_%03d",BATCH_MAP[i][0]);
  new e=engfunc(EngFunc_FindEntityByString,0,"targetname",name);
  if(e>0&&e<2048){g_owner[e]=BATCH_MAP[i][1]+1;g_bit[e]=BATCH_MAP[i][2];count++;}
 }
 if(count!=sizeof BATCH_MAP){server_print("[batches] disabled: expected=%d found=%d",sizeof BATCH_MAP,count);return;}
 for(new i=0;i<sizeof BATCH_MODELS;i++)for(new c=0;c<4;c++)for(new a=0;a<3;a++){g_clusterLo[i][c][a]=1.0e20;g_clusterHi[i][c][a]=-1.0e20;}
 for(new e=MaxClients+1;e<2048;e++)if(g_owner[e]&&pev_valid(e)){
  new i=g_owner[e]-1,c=g_bit[e]/8;new Float:lo[3],Float:hi[3];pev(e,pev_absmin,lo);pev(e,pev_absmax,hi);
  for(new a=0;a<3;a++){g_clusterLo[i][c][a]=floatmin(g_clusterLo[i][c][a],lo[a]);g_clusterHi[i][c][a]=floatmax(g_clusterHi[i][c][a],hi[a]);}
  g_clusterBits[i][c]|=1<<g_bit[e];
 }
 for(new i=0;i<sizeof BATCH_MODELS;i++){
  new e=engfunc(EngFunc_CreateNamedEntity,engfunc(EngFunc_AllocString,"info_target"));
  if(e<=0||e>=2048){server_print("[batches] disabled: entity allocation failed");return;}
  g_group[i]=e;g_groupIndex[e]=i+1;
  formatex(name,charsmax(name),"insomnia_render_group_%02d",i);set_pev(e,pev_targetname,name);
  engfunc(EngFunc_SetModel,e,BATCH_MODELS[i]);engfunc(EngFunc_SetSize,e,BATCH_LO[i],BATCH_HI[i]);
  engfunc(EngFunc_SetOrigin,e,BATCH_POS[i]);set_pev(e,pev_movetype,MOVETYPE_NONE);set_pev(e,pev_solid,SOLID_NOT);
  set_pev(e,pev_takedamage,0.0);set_pev(e,pev_framerate,0.0);set_pev(e,pev_sequence,0);set_pev(e,pev_body,0);
  if(BATCH_TRANSPARENT[i]){set_pev(e,pev_rendermode,kRenderTransTexture);set_pev(e,pev_renderamt,122.0);}
  set_pev(e,pev_skin,BATCH_SKIN[i]);
  // A large studio group can span several BSP leaves while its anchor is in
  // a solid wall. Our per-client view/occlusion filter owns its visibility.
  set_pev(e,pev_effects,pev(e,pev_effects)|EF_FORCEVISIBILITY);
 }
 g_initialized=1;set_pcvar_num(g_activeCvar,1);refresh_all();status();
}
public round_reset(){if(g_initialized)set_task(0.2,"refresh_all");}
public refresh_all(){
 arrayset(g_mask,0,sizeof g_mask);
 for(new e=MaxClients+1;e<2048;e++)if(g_owner[e]&&pev_valid(e)&&broken_proxy(e))g_mask[g_owner[e]-1]|=1<<g_bit[e];
 for(new i=0;i<sizeof BATCH_MODELS;i++)if(pev_valid(g_group[i]))set_pev(g_group[i],pev_body,g_mask[i]);
}
public after_damage(e){
 if(!g_initialized||e<=0||e>=2048||!g_owner[e])return;
 new batch=g_owner[e]-1;
 new previous=g_mask[batch];
 if(broken_proxy(e))g_mask[batch]|=1<<g_bit[e];
 else g_mask[batch]&=~(1<<g_bit[e]);
 if(pev_valid(g_group[batch]))set_pev(g_group[batch],pev_body,g_mask[batch]);
 if(previous!=g_mask[batch])set_cvar_num("insomnia_visibility_generation",get_cvar_num("insomnia_visibility_generation")+1);
}
public filter_packet(es,e,ent,host,flags,player,pSet){
 // Diagnostic only: common include owns the no-frustum switch.
 if(!g_initialized||ent<=0||ent>=2048||host<1||host>MaxClients)return FMRES_IGNORED;
 if(!g_owner[ent]&&!g_groupIndex[ent])return FMRES_IGNORED;
 new Float:now=get_gametime();
 new revision=get_cvar_num("insomnia_visibility_generation");
 if(g_viewTime[host]!=now||g_revision[host]!=revision){
  g_revision[host]=revision;
  if(InsomniaVisibilityView(host,g_eye[host],g_look[host],g_cone[host]))arrayset(g_next[host],0,sizeof BATCH_MODELS*4);
  g_viewTime[host]=now;
 }
 if(g_owner[ent]){
  // Only nearby invisible collision proxies consume packet entries.
  new Float:lo[3],Float:hi[3],Float:d2;pev(ent,pev_absmin,lo);pev(ent,pev_absmax,hi);
  for(new a=0;a<3;a++){
   new Float:d=g_eye[host][a]<lo[a]?lo[a]-g_eye[host][a]:(g_eye[host][a]>hi[a]?g_eye[host][a]-hi[a]:0.0);
   d2+=d*d;
  }
  if(d2<=16384.0)return FMRES_IGNORED;
 }else{
  new i=g_groupIndex[ent]-1,Float:lo[3],Float:hi[3],Float:center[3],Float:half[3];
  pev(ent,pev_absmin,lo);pev(ent,pev_absmax,hi);
  for(new a=0;a<3;a++){center[a]=(lo[a]+hi[a])*0.5;half[a]=(hi[a]-lo[a])*0.5;}
  if(InsomniaVisibilityInBox(host,center,half)){
   for(new c=0;c<4;c++){
    if(!g_clusterBits[i][c]||(g_mask[i]&g_clusterBits[i][c])==g_clusterBits[i][c])continue;
    for(new a=0;a<3;a++){lo[a]=g_clusterLo[i][c][a];hi[a]=g_clusterHi[i][c][a];center[a]=(lo[a]+hi[a])*0.5;half[a]=(hi[a]-lo[a])*0.5;}
    if(!InsomniaVisibilityInBox(host,center,half))continue;
    new slot=i*4+c;
    if(g_next[host][slot]<=now){g_next[host][slot]=now+0.1;g_seen[host][slot]=bool:insomnia_box_visible(g_eye[host],lo,hi,host,0,ent,0);}
    if(g_seen[host][slot])return FMRES_IGNORED;
   }
  }
 }
 forward_return(FMV_CELL,0);return FMRES_SUPERCEDE;
}
public hide_proxy(es,e,ent,host,flags,player,pSet){
 if(g_initialized&&ent>0&&ent<2048&&g_owner[ent]&&get_orig_retval()){
  set_es(es,ES_RenderMode,kRenderTransTexture);set_es(es,ES_RenderAmt,0);
 }
 return FMRES_IGNORED;
}
public status(){
 new broken;
 for(new e=MaxClients+1;e<2048;e++)if(g_owner[e]&&pev_valid(e)&&broken_proxy(e))broken++;
 server_print("[batches] active=%d groups=%d props=%d broken=%d",g_initialized,sizeof BATCH_MODELS,sizeof BATCH_MAP,broken);
}
stock bool:broken_proxy(e){return bool:((pev(e,pev_effects)&EF_NODRAW)||pev(e,pev_solid)==SOLID_NOT||!pev(e,pev_modelindex));}
