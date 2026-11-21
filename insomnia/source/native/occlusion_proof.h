// Conservative coverage of an object's complete projected bounding box.
// Only verified full solid map brushes participate; unsupported shapes are omitted.
#include <cstdint>
#include <cstring>
#include <unordered_map>
#include <string>
struct OccBox { float lo[3],hi[3]; edict_t *owner; float origin[3]; };
static std::vector<OccBox> occluders;
static std::vector<Node> occNodes;
static unsigned long long boxQueries,boxHidden;
static bool occlusionReady;
static unsigned crc32_bytes(const unsigned char *p,int size){
    unsigned crc=~0u;
    for(int i=0;i<size;i++){crc^=p[i];for(int j=0;j<8;j++)crc=(crc>>1)^(0xedb88320u&-(crc&1));}
    return ~crc;
}
static int build_occ(int first,int last){
    Node n={};n.first=first;n.last=last;n.left=n.right=-1;
    for(int a=0;a<3;a++){n.lo[a]=1e30f;n.hi[a]=-1e30f;}
    for(int i=first;i<last;i++)for(int a=0;a<3;a++){n.lo[a]=std::min(n.lo[a],occluders[i].lo[a]);n.hi[a]=std::max(n.hi[a],occluders[i].hi[a]);}
    int index=occNodes.size();occNodes.push_back(n);
    if(last-first>8){
        int axis=0;for(int a=1;a<3;a++)if(n.hi[a]-n.lo[a]>n.hi[axis]-n.lo[axis])axis=a;
        int middle=(first+last)/2;
        std::nth_element(occluders.begin()+first,occluders.begin()+middle,occluders.begin()+last,[axis](const OccBox&a,const OccBox&b){return a.lo[axis]+a.hi[axis]<b.lo[axis]+b.hi[axis];});
        int l=build_occ(first,middle),r=build_occ(middle,last);occNodes[index].left=l;occNodes[index].right=r;
    }
    return index;
}
static void load_occlusion(int count){
    occluders.clear();occNodes.clear();boxQueries=boxHidden=0;occlusionReady=false;
    int length=0;
    auto *data=g_engfuncs.pfnLoadFileForMe("addons/amxmodx/configs/insomnia_occluders.bin",&length);
    if(!data)return;
    unsigned expected=0,num=0;
    if(length>=16){memcpy(&expected,data+8,4);memcpy(&num,data+12,4);}
    if(length<16||memcmp(data,"INSOCC01",8)||num>20000||length!=16+int(num)*84){g_engfuncs.pfnFreeFile(data);return;}
    int bspSize=0;auto *bsp=g_engfuncs.pfnLoadFileForMe("maps/de_insomnia_project_t.bsp",&bspSize);
    bool match=bsp && crc32_bytes(bsp,bspSize)==expected;
    if(bsp)g_engfuncs.pfnFreeFile(bsp);
    if(!match){g_engfuncs.pfnFreeFile(data);g_engfuncs.pfnServerPrint("[fastvis] occlusion data does not match BSP; using legacy rays\n");return;}
    std::unordered_map<std::string,edict_t*> owners;
    for(int i=gpGlobals->maxClients+1;i<count;i++){
        edict_t *e=g_engfuncs.pfnPEntityOfEntIndex(i);
        if(!e->free&&e->v.targetname)owners[gpGlobals->pStringBase+e->v.targetname]=e;
    }
    for(unsigned i=0;i<num;i++){
        const unsigned char *p=data+16+i*84;char name[49]={};memcpy(name,p,48);
        OccBox b={};memcpy(b.lo,p+48,12);memcpy(b.hi,p+60,12);memcpy(b.origin,p+72,12);
        if(name[0]){auto found=owners.find(name);if(found==owners.end())continue;b.owner=found->second;}
        occluders.push_back(b);
    }
    g_engfuncs.pfnFreeFile(data);
    if(!occluders.empty()){build_occ(0,occluders.size());occlusionReady=true;}
    char msg[100];snprintf(msg,sizeof(msg),"[fastvis] verified occlusion boxes=%u\n",unsigned(occluders.size()));g_engfuncs.pfnServerPrint(msg);
}
struct Point2 {double x,y;};
using OccPolygon=std::vector<Point2>;
static double side(Point2 a,Point2 b,Point2 p){return (b.x-a.x)*(p.y-a.y)-(b.y-a.y)*(p.x-a.x);}
static OccPolygon convex_hull(OccPolygon p){
    std::sort(p.begin(),p.end(),[](Point2 a,Point2 b){return a.x==b.x?a.y<b.y:a.x<b.x;});
    OccPolygon h;for(auto v:p){while(h.size()>1&&side(h[h.size()-2],h.back(),v)<=0)h.pop_back();h.push_back(v);}
    size_t lower=h.size();for(int i=int(p.size())-2;i>=0;i--){while(h.size()>lower&&side(h[h.size()-2],h.back(),p[i])<=0)h.pop_back();h.push_back(p[i]);}
    if(h.size()>1)h.pop_back();return h;
}
static OccPolygon project_box(const float *eye,const float *lo,const float *hi,int axis,int sign){
    OccPolygon points;int u=(axis+1)%3,v=(axis+2)%3;
    for(int bits=0;bits<8;bits++){
        double d=sign*(((bits&(1<<axis))?hi[axis]:lo[axis])-eye[axis]);
        if(d<0.01)return {};
        points.push_back({(((bits&(1<<u))?hi[u]:lo[u])-eye[u])/d,(((bits&(1<<v))?hi[v]:lo[v])-eye[v])/d});
    }
    return convex_hull(points);
}
static OccPolygon clip_half(const OccPolygon &p,Point2 a,Point2 b,bool inside){
    OccPolygon out;if(p.empty())return out;
    Point2 previous=p.back();double d0=side(a,b,previous);bool was=inside?d0>=0:d0<=0;
    for(auto current:p){
        double d1=side(a,b,current);bool now=inside?d1>=0:d1<=0;
        if(now!=was){double t=d0/(d0-d1);out.push_back({previous.x+t*(current.x-previous.x),previous.y+t*(current.y-previous.y)});}
        if(now)out.push_back(current);previous=current;d0=d1;was=now;
    }
    if(out.size()<3)out.clear();return out;
}
static bool has_area(const OccPolygon &p){
    // Keep even microscopic remaining regions: a false positive is safe here.
    if(p.size()<3)return false;double area=0;
    for(size_t i=0;i<p.size();i++){auto a=p[i],b=p[(i+1)%p.size()];area+=a.x*b.y-b.x*a.y;}
    return fabs(area)>1e-15;
}
static void occ_candidates(int n,const float *lo,const float *hi,std::vector<int>&out){
    const Node &node=occNodes[n];for(int a=0;a<3;a++)if(node.lo[a]>hi[a]||node.hi[a]<lo[a])return;
    if(node.left>=0){occ_candidates(node.left,lo,hi,out);occ_candidates(node.right,lo,hi,out);}
    else for(int i=node.first;i<node.last;i++)out.push_back(i);
}

struct OccRect {double left,bottom,right,top;};
static bool proven_hidden(const float *eye,const float *lo,const float *hi,edict_t *first,edict_t *second){
    boxQueries++;int axis=0;double greatest=0;
    for(int a=0;a<3;a++){double d=fabs((lo[a]+hi[a])*0.5-eye[a]);if(d>greatest){greatest=d;axis=a;}}
    int sign=(lo[axis]+hi[axis])*0.5>=eye[axis]?1:-1;
    double nearest=sign*((sign>0?lo[axis]:hi[axis])-eye[axis]);
    if(nearest<=1.0)return false;
    OccPolygon target=project_box(eye,lo,hi,axis,sign);if(target.empty())return false;
    OccRect bounds={1e30,1e30,-1e30,-1e30};
    for(auto p:target){bounds.left=std::min(bounds.left,p.x);bounds.right=std::max(bounds.right,p.x);bounds.bottom=std::min(bounds.bottom,p.y);bounds.top=std::max(bounds.top,p.y);}
    std::vector<OccRect> remaining={bounds},next;
    float beamLo[3],beamHi[3];for(int a=0;a<3;a++){beamLo[a]=std::min(eye[a],lo[a]);beamHi[a]=std::max(eye[a],hi[a]);}
    std::vector<int> candidates;occ_candidates(0,beamLo,beamHi,candidates);
    int u=(axis+1)%3,v=(axis+2)%3;
    for(int index:candidates){
        const OccBox &box=occluders[index];edict_t *owner=box.owner;
        if(owner&&(owner==first||owner==second||owner->free||owner->v.solid!=SOLID_BSP||owner->v.rendermode!=kRenderNormal))continue;
        float a[3],b[3];for(int d=0;d<3;d++){
            float delta=owner?owner->v.origin[d]-box.origin[d]:0.0f;
            a[d]=box.lo[d]+delta;b[d]=box.hi[d]+delta;
        }
        if(owner&&(owner->v.angles[0]!=0||owner->v.angles[1]!=0||owner->v.angles[2]!=0))continue;
        double closeDepth=sign*((sign>0?a[axis]:b[axis])-eye[axis]);
        double farDepth=sign*((sign>0?b[axis]:a[axis])-eye[axis]);
        if(closeDepth<0.01 || farDepth>=nearest-0.01)continue;
        // Both perpendicular box faces are full solid rectangles. Their shadows
        // are subsets of the true silhouette, so uncovered area stays visible.
        for(int face=0;face<2;face++){
            double depth=face?farDepth:closeDepth;
            OccRect cover={(a[u]-eye[u])/depth,(a[v]-eye[v])/depth,(b[u]-eye[u])/depth,(b[v]-eye[v])/depth};
            if(cover.right<=bounds.left||cover.left>=bounds.right||cover.top<=bounds.bottom||cover.bottom>=bounds.top)continue;
            next.clear();
            for(auto piece:remaining){
                double left=std::max(piece.left,cover.left),right=std::min(piece.right,cover.right);
                double bottom=std::max(piece.bottom,cover.bottom),top=std::min(piece.top,cover.top);
                if(left>=right||bottom>=top){next.push_back(piece);continue;}
                if(piece.left<left)next.push_back({piece.left,piece.bottom,left,piece.top});
                if(right<piece.right)next.push_back({right,piece.bottom,piece.right,piece.top});
                if(piece.bottom<bottom)next.push_back({left,piece.bottom,right,bottom});
                if(top<piece.top)next.push_back({left,top,right,piece.top});
            }
            if(next.empty()){boxHidden++;return true;}
            if(next.size()>128)return false;
            remaining.swap(next);
        }
    }
    return false;
}
