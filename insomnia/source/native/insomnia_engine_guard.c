
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
/* ABI layouts from the locally vendored Metamod SDK plinfo.h and meta_api.h. */
typedef struct {const char *ifvers,*name,*version,*date,*author,*url,*logtag;int loadable,unloadable;} PluginInfo;
static PluginInfo info={"5:13","Insomnia PM visible-entity bounds","1.0","2026-11-19","Insomnia project","","INSPM",1,0};
typedef struct {DWORD rva;size_t size;const unsigned char *original,*fixed;} Patch;
#include "engine_guard_bytes.h"
static int apply_guard(void) {
 unsigned char *base=(unsigned char*)GetModuleHandleA("engine.dll");
 if(!base)return 0;
 IMAGE_DOS_HEADER *dos=(IMAGE_DOS_HEADER*)base;
 if(dos->e_magic!=IMAGE_DOS_SIGNATURE)return 0;
 IMAGE_NT_HEADERS32 *nt=(IMAGE_NT_HEADERS32*)(base+dos->e_lfanew);
 if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.SizeOfImage!=0x1258000)return 0;
 for(size_t i=0;i<sizeof(patches)/sizeof(*patches);i++) {
  Patch *p=patches+i;
  if(memcmp(base+p->rva,p->original,p->size))return 0;
 }
 // Validate every target and obtain write permission before making any change.
 DWORD old[4];size_t writable=0;
 for(;writable<4;writable++)if(!VirtualProtect(base+patches[writable].rva,patches[writable].size,PAGE_EXECUTE_READWRITE,old+writable))break;
 if(writable!=4){for(size_t i=0;i<writable;i++){DWORD ignored;VirtualProtect(base+patches[i].rva,patches[i].size,old[i],&ignored);}return 0;}
 // Copy the executable stubs before redirecting the original instructions.
 for(int i=3;i>=0;i--)memcpy(base+patches[i].rva,patches[i].fixed,patches[i].size);
 FlushInstructionCache(GetCurrentProcess(),base,nt->OptionalHeader.SizeOfImage);
 for(size_t i=0;i<4;i++){DWORD ignored;VirtualProtect(base+patches[i].rva,patches[i].size,old[i],&ignored);}
 return 1;
}
__declspec(dllexport) void __stdcall GiveFnptrsToDll(void *engine,void *globals){(void)engine;(void)globals;}
__declspec(dllexport) int Meta_Query(char *version,PluginInfo **result,void *utilities){(void)version;(void)utilities;*result=&info;return 1;}
__declspec(dllexport) int Meta_Attach(int now,void *functions,void *globals,void *gamedll){
 (void)now;(void)globals;(void)gamedll;memset(functions,0,8*sizeof(void*));
 int ok=apply_guard();
 FILE *log=fopen("insomnia_engine_guard.log","a");
 if(log){fprintf(log,"PM visibility guard %s: client/server cap 600, physical collisions preserved\n",ok?"APPLIED":"UNSUPPORTED ENGINE");fclose(log);}
 return ok;
}
__declspec(dllexport) int Meta_Detach(int now,int why){(void)now;(void)why;return 0;}
