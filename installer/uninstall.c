// Starts the installed, hash-verified uninstall helper and exits so the helper
// can remove this executable. Nothing is written to the temp folder.
#define UNICODE 1
#define _UNICODE 1
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include "native.h"
#include "uninstall_script.h"

static int refuse(const wchar_t *message) {
    MessageBoxW(NULL, message, L"DekuForge uninstall", MB_OK | MB_ICONERROR);
    return 1;
}

int WINAPI wWinMain(HINSTANCE app,HINSTANCE previous,PWSTR args,int show) {
    (void)app;(void)previous;(void)show;
    wchar_t root[DEKU_PATH],parent[DEKU_PATH],script[DEKU_PATH],shell[DEKU_PATH],command[DEKU_PATH];
    DWORD count=GetModuleFileNameW(NULL,root,DEKU_PATH);
    if(!count||count>=DEKU_PATH) return 1;
    wchar_t *slash=wcsrchr(root,L'\\');if(!slash)return 1;*slash=0;
    char digest[65];
    // The helper ships in the same verified package as this executable; refuse a changed copy.
    if(swprintf(script,DEKU_PATH,L"%ls\\installer\\uninstall.ps1",root)<0||!deku_owned_path(root,script)||!deku_regular_file(script)
       ||!deku_sha256_file(script,digest)||strcmp(digest,DEKU_UNINSTALL_SCRIPT_SHA256))
        return refuse(L"The DekuForge uninstall helper is missing or does not match this uninstaller. Update or reinstall DekuForge, then try again.");
    // Run outside the installation folder so it can be removed completely.
    wcscpy(parent,root);slash=wcsrchr(parent,L'\\');
    if(!slash)return 1;
    if(slash-parent<3) slash[1]=0; else *slash=0;
    UINT length=GetSystemDirectoryW(shell,DEKU_PATH);
    if(!length||length>DEKU_PATH-64)return 1;
    wcscat(shell,L"\\WindowsPowerShell\\v1.0\\powershell.exe");
    if(swprintf(command,DEKU_PATH,L"\"%ls\" -NoProfile -STA -ExecutionPolicy Bypass -File \"%ls\" -Root \"%ls\" %ls",shell,script,root,args)<0)return 1;
    STARTUPINFOW start={0};start.cb=sizeof start;PROCESS_INFORMATION child={0};
    if(!CreateProcessW(shell,command,NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,parent,&start,&child))
        return refuse(L"Could not start the DekuForge uninstall helper.");
    CloseHandle(child.hThread);CloseHandle(child.hProcess);return 0;
}
