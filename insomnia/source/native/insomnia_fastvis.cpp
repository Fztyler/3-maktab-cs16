// Spatially indexed visibility traces. Combat/physics traces are never intercepted.
#include <extdll.h>
#include <meta_api.h>
#include <algorithm>
#include <vector>
#include <chrono>
#include <cmath>

enginefuncs_t g_engfuncs;
globalvars_t *gpGlobals;
meta_globals_t *gpMetaGlobals;
gamedll_funcs_t *gpGamedllFuncs;
mutil_funcs_t *gpMetaUtilFuncs;
static constexpr int VIS_TRACE = 1 << 28;
static char one[]="1", zero[]="0";
static cvar_t mode = {"insomnia_fastvis", one, FCVAR_SERVER, 1.0f, nullptr};
static cvar_t ready = {"insomnia_fastvis_ready", zero, FCVAR_SERVER, 0.0f, nullptr};
static cvar_t coverageReady = {"insomnia_coverage_ready", zero, FCVAR_SERVER, 0.0f, nullptr};
static cvar_t *liveMode, *liveReady;
struct Object { edict_t *entity; float lo[3], hi[3]; };
struct Node { float lo[3], hi[3]; int first, last, left, right; };
#include "occlusion_proof.h"
static std::vector<Object> objects;
static std::vector<Node> nodes;
static edict_t *world;
static unsigned long long calls, clips, comparisons, mismatches;
static double milliseconds;
static double geometryMilliseconds;

static int build(int first, int last) {
    Node node = {}; node.first=first; node.last=last; node.left=node.right=-1;
    for(int axis=0;axis<3;axis++) { node.lo[axis]=1e30f;node.hi[axis]=-1e30f; }
    for(int i=first;i<last;i++) for(int axis=0;axis<3;axis++) {
        node.lo[axis]=std::min(node.lo[axis],objects[i].lo[axis]);
        node.hi[axis]=std::max(node.hi[axis],objects[i].hi[axis]);
    }
    int index=(int)nodes.size();nodes.push_back(node);
    if(last-first>6) {
        int axis=0;for(int i=1;i<3;i++)if(node.hi[i]-node.lo[i]>node.hi[axis]-node.lo[axis])axis=i;
        int middle=(first+last)/2;
        std::nth_element(objects.begin()+first,objects.begin()+middle,objects.begin()+last,
            [axis](const Object&a,const Object&b){return a.lo[axis]+a.hi[axis]<b.lo[axis]+b.hi[axis];});
        int left=build(first,middle),right=build(middle,last);
        nodes[index].left=left;nodes[index].right=right;
    }
    return index;
}

static bool intersects(const float *start,const float *delta,const float *lo,const float *hi,
                       float maximum,float &enter) {
    enter=0.0f;float leave=maximum;
    for(int axis=0;axis<3;axis++) {
        if(fabsf(delta[axis])<1e-8f) {if(start[axis]<lo[axis]||start[axis]>hi[axis])return false;}
        else {
            float a=(lo[axis]-start[axis])/delta[axis],b=(hi[axis]-start[axis])/delta[axis];
            if(a>b)std::swap(a,b);enter=std::max(enter,a);leave=std::min(leave,b);
            if(enter>leave)return false;
        }
    }
    return true;
}

static void query(int index,const float *start,const float *end,const float *delta,
                  edict_t *skip,TraceResult &result) {
    const Node &node=nodes[index];float enter;
    if(!intersects(start,delta,node.lo,node.hi,result.flFraction,enter))return;
    if(node.left>=0) {
        float l,r;bool a=intersects(start,delta,nodes[node.left].lo,nodes[node.left].hi,result.flFraction,l);
        bool b=intersects(start,delta,nodes[node.right].lo,nodes[node.right].hi,result.flFraction,r);
        if(a&&b) {if(l<r){query(node.left,start,end,delta,skip,result);query(node.right,start,end,delta,skip,result);}
                  else {query(node.right,start,end,delta,skip,result);query(node.left,start,end,delta,skip,result);}}
        else if(a)query(node.left,start,end,delta,skip,result);
        else if(b)query(node.right,start,end,delta,skip,result);
        return;
    }
    for(int i=node.first;i<node.last;i++) {
        edict_t *ent=objects[i].entity;
        if(ent->free||ent==skip||ent->v.solid!=SOLID_BSP)continue;
        if((ent->v.flags&FL_MONSTERCLIP)||
            (ent->v.rendermode!=kRenderNormal&&!(ent->v.flags&FL_WORLDBRUSH)))continue;
        if(!intersects(start,delta,(const float*)&ent->v.absmin,(const float*)&ent->v.absmax,result.flFraction,enter))continue;
        TraceResult hit={};g_engfuncs.pfnTraceModel(start,end,0,ent,&hit);clips++;
        if(hit.fAllSolid||hit.fStartSolid||hit.flFraction<result.flFraction) {
            int started=result.fStartSolid;result=hit;result.pHit=ent;
            if(started)result.fStartSolid=1;
        }
    }
}

static void fast_trace(const float *start,const float *end,edict_t *skip,TraceResult *result) {
    g_engfuncs.pfnTraceModel(start,end,0,world,result);clips++;
    if(result->flFraction<1.0f&&!result->pHit)result->pHit=world;
    if(result->fAllSolid||nodes.empty())return;
    float delta[3];for(int axis=0;axis<3;axis++)delta[axis]=end[axis]-start[axis];
    query(0,start,end,delta,skip,*result);
}

static void trace_hook(const float *start,const float *end,int flags,edict_t *skip,TraceResult *result) {
    if(!(flags&VIS_TRACE)||(!liveReady||!liveReady->value))RETURN_META(MRES_IGNORED);
    auto begin=std::chrono::steady_clock::now();calls++;
    if(liveMode->value==0)g_engfuncs.pfnTraceLine(start,end,flags&~VIS_TRACE,skip,result);
    else {
        fast_trace(start,end,skip,result);
        if(liveMode->value==2 && !(calls&63)) {
            TraceResult reference={};g_engfuncs.pfnTraceLine(start,end,flags&~VIS_TRACE,skip,&reference);comparisons++;
            if(fabsf(reference.flFraction-result->flFraction)>0.002f ||
               (reference.fStartSolid!=result->fStartSolid))mismatches++;
        }
    }
    milliseconds+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-begin).count();
    RETURN_META(MRES_SUPERCEDE);
}

// Fakemeta engfunc deliberately bypasses Metamod engine hooks. Pawn calls this
// module native directly, so combat forwards and their recursion remain intact.
struct AMX;
typedef int32_t cell;
typedef cell (*NativeFunction)(AMX*,cell*);
struct NativeInfo {const char *name;NativeFunction function;};
struct ModuleInfo {const char *name,*author,*version;int reload;const char *logtag,*library,*libclass;};
static cell *(*amx_addr)(AMX*,cell);
static void visibility_trace(const float *start,const float *end,edict_t *skip,TraceResult *result) {
    auto begin=std::chrono::steady_clock::now();calls++;
    if(!liveReady->value||liveMode->value==0)g_engfuncs.pfnTraceLine(start,end,257,skip,result);
    else {
        fast_trace(start,end,skip,result);
        if(liveMode->value==2 && !(calls&63)) {
            TraceResult reference={};g_engfuncs.pfnTraceLine(start,end,257,skip,&reference);comparisons++;
            if(fabsf(reference.flFraction-result->flFraction)>0.002f||reference.fStartSolid!=result->fStartSolid)mismatches++;
        }
    }
    milliseconds+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-begin).count();
}
static cell native_trace(AMX *amx,cell *params) {
    float start[3],end[3];cell *a=amx_addr(amx,params[1]),*b=amx_addr(amx,params[2]);
    memcpy(start,a,sizeof(start));memcpy(end,b,sizeof(end));
    int index=params[3];edict_t *skip=index>=0&&index<gpGlobals->maxEntities?g_engfuncs.pfnPEntityOfEntIndex(index):nullptr;
    TraceResult result={};visibility_trace(start,end,skip,&result);
    *amx_addr(amx,params[4])=result.pHit?g_engfuncs.pfnIndexOfEdict(result.pHit):0;
    cell value;memcpy(&value,&result.flFraction,sizeof(value));return value;
}
static cell native_box(AMX *amx,cell *params) {
    float start[3],lo[3],hi[3],point[3];
    memcpy(start,amx_addr(amx,params[1]),sizeof(start));memcpy(lo,amx_addr(amx,params[2]),sizeof(lo));memcpy(hi,amx_addr(amx,params[3]),sizeof(hi));
    edict_t *skip=g_engfuncs.pfnPEntityOfEntIndex(params[4]);
    edict_t *first=params[5]>0?g_engfuncs.pfnPEntityOfEntIndex(params[5]):nullptr;
    edict_t *second=params[6]>0?g_engfuncs.pfnPEntityOfEntIndex(params[6]):nullptr;
    if(occlusionReady && liveMode->value!=0 && liveMode->value!=3){
        // Use the full bounds, including the edge that inset ray samples omit.
        if(first){memcpy(lo,(const float*)&first->v.absmin,sizeof(lo));memcpy(hi,(const float*)&first->v.absmax,sizeof(hi));}
        auto begin=std::chrono::steady_clock::now();
        bool hidden=proven_hidden(start,lo,hi,first,second);
        geometryMilliseconds+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-begin).count();
        return hidden?0:1;
    }
    int grid=params[7],count=grid?grid*grid+1:9,tangent=hi[0]-lo[0]<hi[1]-lo[1]?1:0;
    for(int sample=0;sample<count;sample++) {
        for(int axis=0;axis<3;axis++)point[axis]=(lo[axis]+hi[axis])*0.5f;
        if(sample) {
            if(grid){int row=(sample-1)/grid,col=(sample-1)%grid;point[tangent]=lo[tangent]+col*(hi[tangent]-lo[tangent])/(grid-1);point[2]=lo[2]+row*(hi[2]-lo[2])/(grid-1);}
            else for(int axis=0;axis<3;axis++)point[axis]=((sample-1)&(1<<axis))?hi[axis]:lo[axis];
        }
        TraceResult hit={};visibility_trace(start,point,skip,&hit);
        if(hit.flFraction>=0.99f||(first&&hit.pHit==first)||(second&&hit.pHit==second))return 1;
    }
    return 0;
}
C_DLLEXPORT int AMXX_Query(int *version,ModuleInfo *out) {
    if(!version||!out)return 2;if(*version!=4){*version=4;return 1;}
    ModuleInfo info={"Insomnia indexed visibility","Insomnia project","1.3.1",0,"INSVIS","insomnia_fastvis",""};
    *out=info;return 0;
}
C_DLLEXPORT int AMXX_Attach(void *(*request)(const char*)) {
    auto add=(int(*)(const NativeInfo*))request("AddNatives");
    amx_addr=(cell*(*)(AMX*,cell))request("GetAmxAddr");
    if(!add||!amx_addr)return 3;
    static NativeInfo functions[]={{"insomnia_trace_visible",native_trace},{"insomnia_box_visible",native_box},{nullptr,nullptr}};
    add(functions);return 0;
}
C_DLLEXPORT int AMXX_Detach(){return 0;}

static void stats() {
    char coverage[180];snprintf(coverage,sizeof(coverage),"[fastvis] coverage_queries=%llu hidden=%llu ready=%d boxes=%u ms=%.3f\n",boxQueries,boxHidden,occlusionReady,unsigned(occluders.size()),geometryMilliseconds);g_engfuncs.pfnServerPrint(coverage);
    char text[256];snprintf(text,sizeof(text),"[fastvis] calls=%llu clips=%llu ms=%.3f comparisons=%llu mismatches=%llu objects=%u mode=%.0f\n",
        calls,clips,milliseconds,comparisons,mismatches,(unsigned)objects.size(),liveMode?liveMode->value:-1);
    g_engfuncs.pfnServerPrint(text);
}
static void reset_stats(){calls=clips=comparisons=mismatches=0;milliseconds=0;geometryMilliseconds=0;boxQueries=boxHidden=0;}
static void activate(edict_t *list,int count,int clients) {
    objects.clear();nodes.clear();reset_stats();world=list;
    occluders.clear();occNodes.clear();occlusionReady=false;
    g_engfuncs.pfnCVarSetFloat("insomnia_coverage_ready",0);
    g_engfuncs.pfnCVarSetFloat("insomnia_fastvis_ready",0);
    const char *map=gpGlobals->pStringBase+gpGlobals->mapname;
    if(strcmp(map,"de_insomnia_project_t"))RETURN_META(MRES_IGNORED);
    load_occlusion(count);
    g_engfuncs.pfnCVarSetFloat("insomnia_coverage_ready",occlusionReady?1:0);
    for(int i=clients+1;i<count;i++) {
        edict_t *ent=g_engfuncs.pfnPEntityOfEntIndex(i);if(ent->free||!ent->v.model)continue;
        const char *model=gpGlobals->pStringBase+ent->v.model;
        if(model[0]!='*')continue;
        Object object={};object.entity=ent;
        for(int axis=0;axis<3;axis++){object.lo[axis]=ent->v.absmin[axis]-2;object.hi[axis]=ent->v.absmax[axis]+2;}
        const char *name=gpGlobals->pStringBase+ent->v.classname;
        if(strstr(name,"rotating")) {
            float radius=0;
            for(int axis=0;axis<3;axis++)radius=std::max(radius,std::max(fabsf(ent->v.mins[axis]),fabsf(ent->v.maxs[axis])));
            radius=radius*1.733f+4;
            for(int axis=0;axis<3;axis++){object.lo[axis]=ent->v.origin[axis]-radius;object.hi[axis]=ent->v.origin[axis]+radius;}
        }
        objects.push_back(object);
    }
    if(!objects.empty())build(0,(int)objects.size());
    g_engfuncs.pfnCVarSetFloat("insomnia_fastvis_ready",1);stats();
    RETURN_META(MRES_IGNORED);
}
static void deactivate(){g_engfuncs.pfnCVarSetFloat("insomnia_fastvis_ready",0);objects.clear();nodes.clear();RETURN_META(MRES_IGNORED);}

static plugin_info_t info={META_INTERFACE_VERSION,"Insomnia indexed visibility","1.0","2026-11-19","Insomnia project","","INSVIS",PT_STARTUP,PT_NEVER};
C_DLLEXPORT void WINAPI GiveFnptrsToDll(enginefuncs_t *engine,globalvars_t *globals){g_engfuncs=*engine;gpGlobals=globals;}
C_DLLEXPORT int Meta_Query(char *,plugin_info_t **out,mutil_funcs_t *utilities){*out=&info;gpMetaUtilFuncs=utilities;return TRUE;}
C_DLLEXPORT int GetEntityAPI2_Post(DLL_FUNCTIONS *table,int *version){
    if(*version!=INTERFACE_VERSION)return FALSE;
    memset(table,0,sizeof(*table));table->pfnServerActivate=activate;table->pfnServerDeactivate=deactivate;return TRUE;
}
C_DLLEXPORT int GetEngineFunctions(enginefuncs_t *table,int *version){
    if(*version!=ENGINE_INTERFACE_VERSION)return FALSE;
    memset(table,0,sizeof(*table));table->pfnTraceLine=trace_hook;return TRUE;
}
C_DLLEXPORT int Meta_Attach(PLUG_LOADTIME,META_FUNCTIONS *table,meta_globals_t *globals,gamedll_funcs_t *game){
    gpMetaGlobals=globals;gpGamedllFuncs=game;memset(table,0,sizeof(*table));
    table->pfnGetEntityAPI2_Post=GetEntityAPI2_Post;
    g_engfuncs.pfnCVarRegister(&mode);g_engfuncs.pfnCVarRegister(&ready);g_engfuncs.pfnCVarRegister(&coverageReady);
    liveMode=g_engfuncs.pfnCVarGetPointer("insomnia_fastvis");liveReady=g_engfuncs.pfnCVarGetPointer("insomnia_fastvis_ready");
    g_engfuncs.pfnAddServerCommand("insomnia_fastvis_stats",stats);
    g_engfuncs.pfnAddServerCommand("insomnia_fastvis_reset",reset_stats);return TRUE;
}
C_DLLEXPORT int Meta_Detach(PLUG_LOADTIME,PL_UNLOAD_REASON){return FALSE;}
